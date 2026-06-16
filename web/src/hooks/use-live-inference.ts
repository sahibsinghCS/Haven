"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import {
  API_BASE,
  WS_SNAPSHOT_URL,
  fetchLiveSnapshot,
  normalizeSnapshot,
  parseLiveWsMessage,
} from "@/lib/roomos/api-client"
import { createRoomSocket } from "@/lib/realtime"
import type { LiveFeedbackEvent } from "@/types/feedback-event"
import type { LivePreferencesEvent } from "@/types/preferences-event"
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
  /** Fires when Telegram or web saves a correction (WebSocket push). */
  lastFeedbackEvent: LiveFeedbackEvent | null
  dismissFeedbackEvent: () => void
  /** Fires when Telegram updates preferences (WebSocket push). */
  lastPreferencesEvent: LivePreferencesEvent | null
  dismissPreferencesEvent: () => void
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
export function useLiveInference(enabled = true): UseLiveInferenceResult {
  const [snapshot, setSnapshot] = useState<LiveInferenceSnapshot | null>(null)
  const [status, setStatus] = useState<LiveInferenceStatus>("connecting")
  const [message, setMessage] = useState<string | null>(null)
  const [lastFeedbackEvent, setLastFeedbackEvent] = useState<LiveFeedbackEvent | null>(null)
  const [lastPreferencesEvent, setLastPreferencesEvent] = useState<LivePreferencesEvent | null>(null)
  const lastSeqRef = useRef<number>(0)
  const lastFeedbackIdRef = useRef<string>("")
  const lastPreferencesAtRef = useRef<string>("")

  const dismissFeedbackEvent = useCallback(() => {
    setLastFeedbackEvent(null)
  }, [])

  const dismissPreferencesEvent = useCallback(() => {
    setLastPreferencesEvent(null)
  }, [])

  useEffect(() => {
    if (!enabled) {
      setSnapshot(null)
      setStatus("connecting")
      setMessage(null)
      return
    }

    // Engine restart resets snapshot sequence — drop stale seq filter + UI state.
    lastSeqRef.current = 0
    lastFeedbackIdRef.current = ""
    lastPreferencesAtRef.current = ""
    setSnapshot(null)
    setStatus("connecting")
    setMessage(null)

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

    const onWsPayload = (raw: unknown) => {
      const parsed = parseLiveWsMessage(raw)
      if (!parsed) return
      if (parsed.kind === "snapshot") {
        onSnap(parsed.snapshot)
        return
      }
      if (parsed.kind === "feedback") {
        if (parsed.event.correctionId === lastFeedbackIdRef.current) return
        lastFeedbackIdRef.current = parsed.event.correctionId
        setLastFeedbackEvent(parsed.event)
        return
      }
      if (parsed.kind === "preferences") {
        if (parsed.event.updatedAt === lastPreferencesAtRef.current) return
        lastPreferencesAtRef.current = parsed.event.updatedAt
        setLastPreferencesEvent(parsed.event)
      }
    }

    const socket = createRoomSocket(WS_SNAPSHOT_URL, {
      onOpen: () => {
        if (cancelled) return
        setMessage(null)
      },
      onMessage: (data) => onWsPayload(data),
      onError: () => {
        if (cancelled) return
        setStatus((s) => (s === "live" ? s : "error"))
        setMessage(
          `Cannot reach Haven at ${API_BASE}. From repo root run: npm run demo`,
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
              ? `Haven is not running (${API_BASE}). From repo root: npm run demo`
              : err.message
            : "Could not reach Haven. Run: npm run demo",
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
  }, [enabled])

  return {
    snapshot,
    status,
    message,
    lastFeedbackEvent,
    dismissFeedbackEvent,
    lastPreferencesEvent,
    dismissPreferencesEvent,
  }
}
