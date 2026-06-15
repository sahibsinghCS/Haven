"use client"

import { memo } from "react"
import { Radio, ScanEye } from "lucide-react"

import { useRoomOrchestrationActions } from "@/hooks/use-room-orchestration-actions"
import { cn } from "@/lib/utils"
import {
  roomDisplayMood,
  roomRoleLabel,
  roomScanRole,
  roomSourceHealth,
  type RoomSourceHealth,
} from "@/lib/roomos/room-card-utils"
import { roomStateLabel } from "@/lib/roomos/state-meta"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useLiveSessionStore } from "@/stores/live-session-store"
import type { LiveInferenceSnapshot, RoomStatus } from "@/types/roomos"

const HEALTH_RING: Record<RoomSourceHealth, string> = {
  live: "ring-emerald-400/50",
  dark: "ring-amber-400/45",
  waiting: "ring-zinc-500/40",
  off: "ring-zinc-700/30",
}

export const LivePresenceRail = memo(function LivePresenceRail({
  rooms,
  activeRoomId,
  snapshot,
  onOpenGallery,
}: {
  rooms: RoomStatus[]
  activeRoomId: string | null
  snapshot: LiveInferenceSnapshot
  onOpenGallery?: () => void
}) {
  const orchestratorMode = useLiveSessionStore((s) => s.orchestratorMode)
  const { activateRoom } = useRoomOrchestrationActions()

  if (rooms.length <= 1) return null

  return (
    <div
      className="pointer-events-auto flex gap-2 overflow-x-auto pb-1 scrollbar-none"
      role="list"
      aria-label="Rooms in this home"
    >
      {rooms.map((room) => {
        const isActive = room.id === activeRoomId || room.isActive
        const mood = roomDisplayMood(room, snapshot)
        const role = roomScanRole(room, orchestratorMode)
        const health = roomSourceHealth(room)
        const switching =
          activateRoom.isPending && activateRoom.variables === room.id

        return (
          <button
            key={room.id}
            type="button"
            role="listitem"
            disabled={!room.enabled || switching || (isActive && !onOpenGallery)}
            onClick={() => {
              if (isActive) {
                onOpenGallery?.()
                return
              }
              if (room.enabled) {
                activateRoom.mutate(room.id)
              }
            }}
            className={cn(
              roomosUi.liveStatusPillTranslucent,
              "flex min-w-[9rem] shrink-0 flex-col items-start gap-0.5 px-3 py-2 text-left transition-[border-color,background-color,box-shadow] duration-150",
              "ring-2 ring-offset-1 ring-offset-zinc-950/80",
              HEALTH_RING[health],
              isActive
                ? "border-teal-400/40 bg-teal-950/45 shadow-[0_0_24px_-8px_rgba(45,212,191,0.35)]"
                : "hover:border-white/22 hover:bg-zinc-900/70",
              !room.enabled && "cursor-not-allowed opacity-45",
              room.enabled && !isActive && "cursor-pointer",
            )}
            aria-current={isActive ? "true" : undefined}
            aria-label={
              isActive
                ? `${room.name}, active room. ${roomRoleLabel(role)}${mood ? `, ${roomStateLabel(mood)}` : ""}`
                : `Switch to ${room.name}`
            }
          >
            <span className="flex w-full items-center justify-between gap-2">
              <span className="truncate text-[12px] font-semibold text-zinc-100">
                {room.name}
              </span>
              {role === "inferring" ? (
                <Radio className="size-3 shrink-0 text-teal-300" aria-hidden />
              ) : (
                <ScanEye className="size-3 shrink-0 text-zinc-500" aria-hidden />
              )}
            </span>
            <span className="text-[10px] leading-snug text-zinc-500">
              {switching
                ? "Switching…"
                : isActive
                  ? roomRoleLabel(role)
                  : room.enabled
                    ? "Tap to make active"
                    : "Disabled"}
              {mood ? ` · ${roomStateLabel(mood)}` : ""}
            </span>
          </button>
        )
      })}
    </div>
  )
})
