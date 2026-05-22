"use client"

import { useEffect, useRef, useState } from "react"

import {
  API_BASE,
  WS_SNAPSHOT_URL,
  fetchLiveSnapshot,
  normalizeSnapshot,
} from "@/lib/roomos/api-client"
import { createRoomSocket } from "@/lib/realtime"
import type { LiveInferenceSnapshot } from "@/types/roomos"

export type LiveInferenceStatus =
  | "connecting"
  | "live"
  | "no-data"
  | "error"

export interface UseLiveInferenceResult {
  snapshot: LiveInferenceSnapshot | null
  status: LiveInferenceStatus
  /** Latest error message, if any. */
  message: string | null
}

const POLL_MS = 2000

function applySnapshot(
  snap: LiveInferenceSnapshot,
  setSnapshot: (s: LiveInferenceSnapshot) => void,
  setStatus: (s: LiveInferenceStatus) => void,
  setMessage: (m: string | null) => void,
) {
  if (process.env.NODE_ENV !== "production") {
    // eslint-disable-next-line no-console
    console.debug(
      "[roomos] snapshot applied",
      "seq=", snap.sequence,
      "primary=", snap.primaryState,
      "src=", snap.dataSource,
    )
  }
  setSnapshot(snap)
  setStatus("live")
  setMessage(null)
}

/**
 * Subscribe to the FastAPI live-inference stream.
 *
 * WebSocket for push updates + HTTP poll every 2s so percentages stay fresh
 * even if the WS queue drops or the browser only applied the first message.
 */
export function useLiveInference(): UseLiveInferenceResult {
  const [snapshot, setSnapshot] = useState<LiveInferenceSnapshot | null>(null)
  const [status, setStatus] = useState<LiveInferenceStatus>("connecting")
  const [message, setMessage] = useState<string | null>(null)
  const lastSeqRef = useRef<number>(0)

  useEffect(() => {
    let cancelled = false
    const ac = new AbortController()

    const onSnap = (raw: unknown) => {
      if (cancelled) return
      try {
        const snap = normalizeSnapshot(raw)
        if (
          typeof snap.sequence === "number" &&
          snap.sequence > 0 &&
          snap.sequence <= lastSeqRef.current
        ) {
          return
        }
        if (typeof snap.sequence === "number" && snap.sequence > 0) {
          lastSeqRef.current = snap.sequence
        }
        applySnapshot(snap, setSnapshot, setStatus, setMessage)
      } catch (err) {
        setMessage(err instanceof Error ? err.message : "Bad snapshot payload")
      }
    }

    const socket = createRoomSocket(WS_SNAPSHOT_URL, {
      onOpen: () => {
        if (cancelled) return
        setMessage(null)
      },
      onMessage: (data) => onSnap(data),
      onError: () => {
        if (cancelled) return
        setStatus((s) => (s === "live" ? s : "error"))
        setMessage(
          `Cannot reach RoomOS API at ${API_BASE}. From repo root run: npm run demo`,
        )
      },
      onClose: (e) => {
        if (cancelled) return
        if (e.code !== 1000) {
          setMessage(`WebSocket closed (${e.code})`)
        }
      },
    })

    const poll = async () => {
      if (cancelled) return
      try {
        const snap = await fetchLiveSnapshot(ac.signal)
        if (cancelled || !snap) return
        onSnap(snap)
      } catch (err) {
        if (cancelled) return
        setStatus((s) => (s === "live" ? s : "error"))
        setMessage(
          err instanceof Error
            ? err.message.includes("fetch")
              ? `RoomOS API is not running (${API_BASE}). From repo root: npm run demo`
              : err.message
            : "Could not reach the RoomOS API. Run: npm run demo",
        )
      }
    }

    void poll()
    const pollTimer = setInterval(poll, POLL_MS)

    return () => {
      cancelled = true
      clearInterval(pollTimer)
      ac.abort()
      try {
        socket.close()
      } catch {
        // ignore
      }
    }
  }, [])

  return { snapshot, status, message }
}
