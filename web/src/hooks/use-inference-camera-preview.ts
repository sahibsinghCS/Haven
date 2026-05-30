"use client"

import { useCallback, useEffect, useState } from "react"

import { livePreviewMjpegUrl } from "@/lib/roomos/api-client"

export type InferencePreviewStatus = "idle" | "waiting" | "live" | "error"

/**
 * Displays the backend inference camera via MJPEG (same OpenCV feed as ML).
 * Not the browser getUserMedia path.
 */
export function useInferenceCameraPreview(enabled: boolean) {
  const [status, setStatus] = useState<InferencePreviewStatus>("idle")
  const [message, setMessage] = useState<string | null>(null)

  const streamSrc = enabled ? livePreviewMjpegUrl() : null

  useEffect(() => {
    if (!enabled) {
      setStatus("idle")
      setMessage(null)
      return
    }
    setStatus("waiting")
    setMessage("Connecting to inference camera…")
    const t = window.setTimeout(() => {
      setStatus((s) => (s === "waiting" ? "live" : s))
      setMessage(null)
    }, 1200)
    return () => window.clearTimeout(t)
  }, [enabled, streamSrc])

  const onStreamLoad = useCallback(() => {
    setStatus("live")
    setMessage(null)
  }, [])

  const onStreamError = useCallback(() => {
    setStatus("error")
    setMessage("Camera preview unavailable — restart the RoomOS API (npm run dev)")
  }, [])

  return { streamSrc, status, message, onStreamLoad, onStreamError }
}
