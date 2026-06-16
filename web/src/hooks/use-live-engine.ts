"use client"

import { useCallback, useEffect, useState } from "react"

import {
  fetchEngineStatus,
  startEngine,
  type BootPhase,
  type CompatReport,
  type LiveEngineStatus,
  type LiveMode,
  type ModelKind,
} from "@/lib/roomos/api-client"
import { useLiveSessionStore } from "@/stores/live-session-store"
import { useRoomOsAmbientStore } from "@/stores/roomos-store"

export type LiveEngineHookStatus =
  | "idle"
  | "starting"
  | "running"
  | "error"
  | "camera_setup"

const STATUS_POLL_BOOT_MS = 2000
const STATUS_POLL_STREAMING_MS = 8000

/**
 * Ensures the FastAPI live inference engine is running so snapshots and
 * percentages reflect the trained model via the API.
 *
 * After the engine reports running we keep polling /api/live/status every
 * couple of seconds so derived fields (boot_phase, preview_dark, model_kind)
 * stay fresh — without those updates, the boot screen would never advance
 * past "Starting inference engine…" and the dark-camera warning would never
 * fire if the camera went dark mid-session.
 */
export function useLiveEngineAutostart(enabled = true) {
  const [status, setStatus] = useState<LiveEngineHookStatus>("idle")
  const [message, setMessage] = useState<string | null>(null)
  const [inferenceSource, setInferenceSource] = useState<string | null>(null)
  const [previewAvailable, setPreviewAvailable] = useState(false)
  const [previewMeanLuma, setPreviewMeanLuma] = useState<number | null>(null)
  const [previewDark, setPreviewDark] = useState(false)
  const [previewFit, setPreviewFit] = useState<"cover" | "contain">("cover")
  const [previewFrameShape, setPreviewFrameShape] = useState<[number, number] | null>(
    null,
  )
  const [captureSize, setCaptureSize] = useState<[number, number] | null>(null)
  const [bootPhase, setBootPhase] = useState<BootPhase>("off")
  const [modelKind, setModelKind] = useState<ModelKind>("unknown")
  const [poseEnabled, setPoseEnabled] = useState<boolean | null>(null)
  const [compatReport, setCompatReport] = useState<CompatReport | null>(null)
  const [liveMode, setLiveMode] = useState<LiveMode>("off")
  const [cameraSetupRequired, setCameraSetupRequired] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const cameraRefreshNonce = useRoomOsAmbientStore((s) => s.cameraRefreshNonce)

  const refreshStatus = useCallback(() => setRefreshKey((k) => k + 1), [])

  useEffect(() => {
    if (!enabled) {
      setStatus("idle")
      setMessage(null)
      setBootPhase("off")
      setLiveMode("off")
      setCameraSetupRequired(false)
      setPreviewAvailable(false)
      setPreviewMeanLuma(null)
      setPreviewDark(false)
      return
    }
    let cancelled = false
    let pollTimer: ReturnType<typeof setInterval> | null = null

    const applyStatus = (st: LiveEngineStatus) => {
      setInferenceSource(st.inference_source ?? null)
      setPreviewAvailable(Boolean(st.preview_available))
      setPreviewMeanLuma(
        typeof st.preview_mean_luma === "number" ? st.preview_mean_luma : null,
      )
      setPreviewDark(Boolean(st.preview_dark))
      setPreviewFit(st.preview_fit === "contain" ? "contain" : "cover")
      const shape = st.preview_frame_shape
      setPreviewFrameShape(
        Array.isArray(shape) && shape.length === 2 ? [shape[0], shape[1]] : null,
      )
      const cap = st.capture_size
      setCaptureSize(Array.isArray(cap) && cap.length === 2 ? [cap[0], cap[1]] : null)
      setBootPhase((st.boot_phase as BootPhase) ?? "off")
      setModelKind((st.model_kind as ModelKind) ?? "unknown")
      setPoseEnabled(
        typeof st.pose_enabled === "boolean" ? st.pose_enabled : null,
      )
      setCompatReport(st.compat_report ?? null)
      setLiveMode(st.live_mode ?? "off")
      setCameraSetupRequired(Boolean(st.camera_setup_required))
      if (st.rooms) {
        useLiveSessionStore.getState().setRoomsStatus({
          orchestratorMode: st.orchestratorMode ?? "away",
          activeRoomId: st.activeRoomId ?? null,
          graceDurationSec: st.graceDurationSec ?? 60,
          graceStartedAt: null,
          graceRemainingSec: st.graceRemainingSec ?? null,
          lastPrimaryState: null,
          rooms: st.rooms,
        })
      }
    }

    ;(async () => {
      try {
        const st = await fetchEngineStatus()
        if (cancelled) return
        applyStatus(st)
        if (st.engine_running) {
          setStatus("running")
          setMessage(null)
        } else if (st.camera_setup_required) {
          setStatus("camera_setup")
          setMessage(null)
        } else {
          setStatus("starting")
          const result = (await startEngine()) as {
            status?: string
            error?: string
            inference_source?: string
            camera_setup_required?: boolean
            compat?: CompatReport
          }
          if (cancelled) return
          if (result.status === "camera_setup_required" || result.camera_setup_required) {
            setStatus("camera_setup")
            setMessage(null)
            setCameraSetupRequired(true)
            setBootPhase("camera_setup")
            return
          }
          if (result.status === "error") {
            setStatus("error")
            setMessage(result.error ?? "Engine failed to start")
            if (result.compat) setCompatReport(result.compat)
            return
          }
          setStatus("running")
          setMessage(null)
          if (result.inference_source) {
            setInferenceSource(result.inference_source)
          }
          const again = await fetchEngineStatus()
          if (!cancelled) applyStatus(again)
        }

        // Keep status fresh so boot_phase / preview_dark / model_kind reflect
        // reality as the engine transitions starting -> warming_up -> streaming.
        pollTimer = setInterval(async () => {
          if (cancelled) return
          try {
            const next = await fetchEngineStatus()
            if (cancelled) return
            applyStatus(next)
            if (next.engine_running) {
              setStatus("running")
              setMessage(null)
            } else if (next.camera_setup_required) {
              setStatus("camera_setup")
              setMessage(null)
            } else if (next.engine_error) {
              const lower = next.engine_error.toLowerCase()
              const cameraRelated =
                lower.includes("camera") ||
                lower.includes("webcam") ||
                lower.includes("video source") ||
                lower.includes("droidcam") ||
                lower.includes("mjpeg") ||
                lower.includes("busy")
              if (cameraRelated) {
                setStatus("camera_setup")
                setMessage(null)
              } else {
                setStatus("error")
                setMessage(next.engine_error)
              }
            } else {
              setStatus("error")
              setMessage("Engine stopped")
            }
          } catch {
            // Transient network errors during polling shouldn't tank the UI;
            // the next tick will recover.
          }
        }, STATUS_POLL_STREAMING_MS)
      } catch (err) {
        if (cancelled) return
        setStatus("error")
        setMessage(err instanceof Error ? err.message : "Could not reach Haven")
      }
    })()

    return () => {
      cancelled = true
      if (pollTimer) clearInterval(pollTimer)
    }
  }, [enabled, refreshKey, cameraRefreshNonce])

  return {
    status,
    message,
    inferenceSource,
    previewAvailable,
    previewMeanLuma,
    previewDark,
    previewFit,
    previewFrameShape,
    captureSize,
    bootPhase,
    modelKind,
    poseEnabled,
    compatReport,
    liveMode,
    cameraSetupRequired,
    refreshStatus,
  }
}
