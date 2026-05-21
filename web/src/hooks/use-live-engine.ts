"use client"

import { useEffect, useState } from "react"

import { fetchEngineStatus, startEngine } from "@/lib/roomos/api-client"

export type LiveEngineHookStatus = "idle" | "starting" | "running" | "error"

/**
 * Ensures the FastAPI live inference engine is running so snapshots and
 * percentages reflect the trained model (not the UI mock).
 */
export function useLiveEngineAutostart(enabled = true) {
  const [status, setStatus] = useState<LiveEngineHookStatus>("idle")
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) return
    let cancelled = false

    ;(async () => {
      try {
        const st = await fetchEngineStatus()
        if (cancelled) return
        if (st.engine_running) {
          setStatus("running")
          setMessage(null)
          return
        }
        setStatus("starting")
        const result = (await startEngine()) as { status?: string; error?: string }
        if (cancelled) return
        if (result.status === "error") {
          setStatus("error")
          setMessage(result.error ?? "Engine failed to start")
          return
        }
        setStatus("running")
        setMessage(null)
      } catch (err) {
        if (cancelled) return
        setStatus("error")
        setMessage(err instanceof Error ? err.message : "Could not reach RoomOS API")
      }
    })()

    return () => {
      cancelled = true
    }
  }, [enabled])

  return { status, message }
}
