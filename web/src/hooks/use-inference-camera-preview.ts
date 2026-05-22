"use client"

import { useEffect, useState } from "react"

import { LIVE_PREVIEW_URL } from "@/lib/roomos/api-client"

export type InferencePreviewStatus = "idle" | "waiting" | "live" | "error"

/**
 * Polls the backend inference camera preview (same OpenCV source as ML bursts).
 * Not the browser getUserMedia path.
 */
export function useInferenceCameraPreview(enabled: boolean, pollKey?: number) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [status, setStatus] = useState<InferencePreviewStatus>("idle")
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) {
      setStatus("idle")
      setMessage(null)
      return
    }

    let cancelled = false
    let currentUrl: string | null = null

    const poll = async () => {
      try {
        const res = await fetch(`${LIVE_PREVIEW_URL}?t=${Date.now()}`, {
          cache: "no-store",
        })
        if (cancelled) return
        if (res.status === 503) {
          setStatus("waiting")
          setMessage("Waiting for the inference camera to produce a frame…")
          return
        }
        if (!res.ok) {
          setStatus("error")
          setMessage(`Preview unavailable (${res.status})`)
          return
        }
        const blob = await res.blob()
        if (cancelled) return
        const next = URL.createObjectURL(blob)
        if (currentUrl) URL.revokeObjectURL(currentUrl)
        currentUrl = next
        setObjectUrl(next)
        setStatus("live")
        setMessage(null)
      } catch (err) {
        if (cancelled) return
        setStatus("error")
        setMessage(err instanceof Error ? err.message : "Could not load inference preview")
      }
    }

    void poll()
    const timer = setInterval(poll, 80)

    return () => {
      cancelled = true
      clearInterval(timer)
      if (currentUrl) URL.revokeObjectURL(currentUrl)
    }
  }, [enabled, pollKey])

  return { objectUrl, status, message }
}
