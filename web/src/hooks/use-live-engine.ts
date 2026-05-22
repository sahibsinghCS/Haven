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

export type LiveEngineHookStatus = "idle" | "starting" | "running" | "error"

const STATUS_POLL_MS = 2000

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
  const [bootPhase, setBootPhase] = useState<BootPhase>("off")
  const [modelKind, setModelKind] = useState<ModelKind>("unknown")
  const [poseEnabled, setPoseEnabled] = useState<boolean | null>(null)
  const [compatReport, setCompatReport] = useState<CompatReport | null>(null)
  const [liveMode, setLiveMode] = useState<LiveMode>("off")
  const [demoMode, setDemoMode] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const refreshStatus = useCallback(() => setRefreshKey((k) => k + 1), [])

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    let pollTimer: ReturnType<typeof setInterval> | null = null

    const applyStatus = (st: LiveEngineStatus) => {
      setInferenceSource(st.inference_source ?? null)
      setPreviewAvailable(Boolean(st.preview_available))
      setPreviewMeanLuma(
        typeof st.preview_mean_luma === "number" ? st.preview_mean_luma : null,
      )
      setPreviewDark(Boolean(st.preview_dark))
      setBootPhase((st.boot_phase as BootPhase) ?? "off")
      setModelKind((st.model_kind as ModelKind) ?? "unknown")
      setPoseEnabled(
        typeof st.pose_enabled === "boolean" ? st.pose_enabled : null,
      )
      setCompatReport(st.compat_report ?? null)
      setLiveMode(st.live_mode ?? (st.demo_mode ? "replay" : "off"))
      setDemoMode(Boolean(st.demo_mode ?? st.demo_replay_active))
    }

    ;(async () => {
      try {
        const st = await fetchEngineStatus()
        if (cancelled) return
        applyStatus(st)
        if (st.engine_running) {
          setStatus("running")
          setMessage(null)
        } else {
          setStatus("starting")
          const result = (await startEngine()) as {
            status?: string
            error?: string
            inference_source?: string
            compat?: CompatReport
          }
          if (cancelled) return
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
            if (!next.engine_running) {
              setStatus("error")
              setMessage(next.engine_error ?? "Engine stopped")
            }
          } catch {
            // Transient network errors during polling shouldn't tank the UI;
            // the next tick will recover.
          }
        }, STATUS_POLL_MS)
      } catch (err) {
        if (cancelled) return
        setStatus("error")
        setMessage(err instanceof Error ? err.message : "Could not reach RoomOS API")
      }
    })()

    return () => {
      cancelled = true
      if (pollTimer) clearInterval(pollTimer)
    }
  }, [enabled, refreshKey])

  return {
    status,
    message,
    inferenceSource,
    previewAvailable,
    previewMeanLuma,
    previewDark,
    bootPhase,
    modelKind,
    poseEnabled,
    compatReport,
    liveMode,
    demoMode,
    refreshStatus,
  }
}
