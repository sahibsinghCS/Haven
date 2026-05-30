"use client"

import { useEffect, useRef } from "react"
import { toast } from "sonner"

import { WS_SNAPSHOT_URL, parseLiveWsMessage } from "@/lib/roomos/api-client"
import { createRoomSocket } from "@/lib/realtime"

/**
 * Refetch preferences when Telegram (or API) saves an update via WebSocket.
 */
export function usePreferencesWsRefresh(onRefresh: () => void, enabled = true) {
  const lastAtRef = useRef("")

  useEffect(() => {
    if (!enabled) return
    let cancelled = false

    const socket = createRoomSocket(WS_SNAPSHOT_URL, {
      onMessage: (data) => {
        if (cancelled) return
        const parsed = parseLiveWsMessage(data)
        if (!parsed || parsed.kind !== "preferences") return
        if (parsed.event.updatedAt === lastAtRef.current) return
        lastAtRef.current = parsed.event.updatedAt
        onRefresh()
        if (parsed.event.source === "telegram") {
          toast.info("Preferences updated from Telegram", {
            description: parsed.event.changes.slice(0, 2).join(" · "),
          })
        }
      },
    })

    return () => {
      cancelled = true
      try {
        socket.close()
      } catch {
        // ignore
      }
    }
  }, [enabled, onRefresh])
}
