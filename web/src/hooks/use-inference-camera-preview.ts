"use client"

import { useCallback, useEffect, useState } from "react"

import { livePreviewMjpegUrl } from "@/lib/roomos/api-client"
import { useLiveSessionStore } from "@/stores/live-session-store"
import { useRoomOsAmbientStore } from "@/stores/roomos-store"

export type InferencePreviewStatus = "idle" | "waiting" | "live" | "error"

/**
 * Displays the backend inference camera via MJPEG (same OpenCV feed as ML).
 * Not the browser getUserMedia path.
 */
export function useInferenceCameraPreview(
  enabled: boolean,
  options?: { resumeLive?: boolean },
) {
  const resumeLive = Boolean(options?.resumeLive)
  const [status, setStatus] = useState<InferencePreviewStatus>(
    enabled && resumeLive ? "live" : "idle",
  )
  const [message, setMessage] = useState<string | null>(null)
  const cameraRefreshNonce = useRoomOsAmbientStore((s) => s.cameraRefreshNonce)
  const setPreviewStreamLive = useLiveSessionStore((s) => s.setPreviewStreamLive)

  const streamSrc = enabled
    ? `${livePreviewMjpegUrl()}?v=${cameraRefreshNonce}`
    : null

  useEffect(() => {
    if (!enabled) {
      setStatus("idle")
      setMessage(null)
      return
    }
    if (resumeLive) {
      setStatus("live")
      setMessage(null)
      return
    }
    setStatus("waiting")
    setMessage("Connecting to inference camera…")
  }, [enabled, resumeLive, streamSrc])

  const onStreamLoad = useCallback(() => {
    setStatus("live")
    setMessage(null)
    setPreviewStreamLive(true)
  }, [setPreviewStreamLive])

  const onStreamError = useCallback(() => {
    setStatus("error")
    setMessage("Camera preview unavailable — restart the RoomOS API (npm run dev)")
  }, [])

  return { streamSrc, status, message, onStreamLoad, onStreamError }
}
