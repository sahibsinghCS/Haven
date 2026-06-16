"use client"

import {
  ArrowRight,
  LayoutGrid,
  Maximize2,
  Moon,
  Power,
  PowerOff,
  Radio,
  ScanEye,
  Sparkles,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { useRoomOrchestrationActions } from "@/hooks/use-room-orchestration-actions"
import { roomPreviewMjpegUrl } from "@/lib/roomos/api-client"
import {
  galleryLayoutDensity,
  roomDisplayMood,
  roomHealthLabel,
  roomRoleLabel,
  roomScanRole,
  roomSourceHealth,
  type GalleryLayoutDensity,
  type RoomScanRole,
  type RoomSourceHealth,
} from "@/lib/roomos/room-card-utils"
import { roomStateLabel } from "@/lib/roomos/state-meta"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useLiveSessionStore } from "@/stores/live-session-store"
import type { LiveInferenceSnapshot, OrchestratorMode, RoomStatus } from "@/types/roomos"
import { cn } from "@/lib/utils"

const ROLE_ACCENT: Record<RoomScanRole, string> = {
  inferring: "border-l-teal-400/80 bg-teal-500/[0.06]",
  active_hold: "border-l-amber-400/70 bg-amber-500/[0.05]",
  grace_scan: "border-l-amber-300/55 bg-amber-500/[0.04]",
  preview: "border-l-white/20 bg-white/[0.02]",
  standby: "border-l-zinc-600/50 bg-zinc-900/40",
  off: "border-l-zinc-700/40 bg-zinc-950/50",
}

const HEALTH_DOT: Record<RoomSourceHealth, string> = {
  live: "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.55)]",
  dark: "bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.45)]",
  waiting: "bg-zinc-500 animate-pulse",
  off: "bg-zinc-600",
}

function HealthDot({ health }: { health: RoomSourceHealth }) {
  return (
    <span
      className={cn("size-2 shrink-0 rounded-full", HEALTH_DOT[health])}
      title={roomHealthLabel(health)}
      aria-hidden
    />
  )
}

function OrchestrationStrip({
  mode,
  graceRemainingSec,
  graceDurationSec,
  rooms,
  activeRoomId,
}: {
  mode: OrchestratorMode
  graceRemainingSec: number | null
  graceDurationSec: number
  rooms: RoomStatus[]
  activeRoomId: string | null
}) {
  const enabled = rooms.filter((r) => r.enabled)
  const inferring = rooms.find((r) => r.inferenceActive)
  const activeName =
 rooms.find((r) => r.id === activeRoomId)?.name ?? inferring?.name ?? ". "
  const graceTotal = Math.max(1, graceDurationSec)
  const gracePct =
    graceRemainingSec != null
      ? Math.max(0, Math.min(100, (graceRemainingSec / graceTotal) * 100))
      : null

  const segments: {
    id: OrchestratorMode
    label: string
    hint: string
  }[] = [
    {
      id: "active",
      label: "Active",
      hint:
        mode === "active"
          ? `${activeName} · full burst`
 : "Someone home. one room infers",
    },
    {
      id: "grace",
      label: "Grace",
      hint:
        mode === "grace"
          ? `Walkway lights · scanning other rooms${graceRemainingSec!= null? ` · ${Math.ceil(graceRemainingSec)}s`: ""}`
          : "Brief hold before away",
    },
    {
      id: "away",
      label: "Away",
      hint:
        mode === "away"
          ? "Inference paused · devices off"
          : "Nobody detected",
    },
  ]

  return (
    <div
      className={cn(
        roomosUi.liveOverlayGlassTranslucent,
        "mb-3 shrink-0 overflow-hidden p-0",
      )}
      role="status"
      aria-label="Home presence orchestration"
    >
      <div className="grid grid-cols-3 divide-x divide-white/[0.06]">
        {segments.map((seg) => {
          const active = mode === seg.id
          return (
            <div
              key={seg.id}
              className={cn(
                "relative px-3 py-3 transition-colors sm:px-4",
                active && seg.id === "active" && "bg-teal-500/[0.08]",
                active && seg.id === "grace" && "bg-amber-500/[0.08]",
                active && seg.id === "away" && "bg-zinc-800/50",
              )}
            >
              {active ? (
                <span
                  className={cn(
                    "absolute inset-x-3 top-0 h-px sm:inset-x-4",
                    seg.id === "active" && "bg-gradient-to-r from-transparent via-teal-400/70 to-transparent",
                    seg.id === "grace" && "bg-gradient-to-r from-transparent via-amber-400/70 to-transparent",
                    seg.id === "away" && "bg-gradient-to-r from-transparent via-zinc-400/40 to-transparent",
                  )}
                  aria-hidden
                />
              ) : null}
              <p
                className={cn(
                  "text-[10px] font-semibold uppercase tracking-[0.16em]",
                  active
                    ? seg.id === "grace"
                      ? "text-amber-200"
                      : seg.id === "away"
                        ? "text-zinc-300"
                        : "text-teal-200"
                    : "text-zinc-600",
                )}
              >
                {seg.label}
              </p>
              <p
                className={cn(
                  "mt-1 text-[11px] leading-snug",
                  active ? "text-zinc-200" : "text-zinc-600",
                )}
              >
 {active ? seg.hint : ". "}
              </p>
              {active && seg.id === "grace" && gracePct != null ? (
                <div
                  className="mt-2 h-1 overflow-hidden rounded-full bg-amber-950/60"
                  aria-hidden
                >
                  <div
                    className="h-full rounded-full bg-amber-400/80 transition-all duration-1000"
                    style={{ width: `${gracePct}%` }}
                  />
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.06] px-3 py-2 text-[11px] text-zinc-500 sm:px-4">
        <span>
          {enabled.length} of {rooms.length} scanning
          {inferring ? (
            <>
              {" "}
              · inferring{" "}
              <span className="font-medium text-teal-300/90">{inferring.name}</span>
            </>
          ) : null}
        </span>
        {mode === "grace" ? (
          <span className="inline-flex items-center gap-1 text-amber-200/90">
            <ScanEye className="size-3" aria-hidden />
            Motion watch on other rooms
          </span>
        ) : mode === "active" ? (
          <span className="inline-flex items-center gap-1 text-teal-200/80">
            <Radio className="size-3" aria-hidden />
            Preview scan on non-active rooms
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-zinc-500">
            <Moon className="size-3" aria-hidden />
            All rooms idle
          </span>
        )}
      </div>
    </div>
  )
}

function RoomCard({
  room,
  density,
  snapshot,
  orchestratorMode,
  onFocus,
  onActivate,
  onToggleEnabled,
  togglingEnabled,
  activating,
}: {
  room: RoomStatus
  density: GalleryLayoutDensity
  snapshot: LiveInferenceSnapshot | null
  orchestratorMode: OrchestratorMode
  onFocus: () => void
  onActivate: () => void
  onToggleEnabled: (enabled: boolean) => void
  togglingEnabled: boolean
  activating: boolean
}) {
  const health = roomSourceHealth(room)
  const role = roomScanRole(room, orchestratorMode)
  const mood = roomDisplayMood(room, snapshot)
  const compact = density === "compact"

  return (
    <article
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border border-l-[3px] bg-zinc-950/75 shadow-lg transition-[border-color,box-shadow,transform] duration-200",
        ROLE_ACCENT[role],
        room.isActive && !compact && "ring-1 ring-teal-400/20",
        !room.enabled && "opacity-55 saturate-[0.65]",
        compact ? "min-h-0" : "min-h-[11rem]",
      )}
    >
      <div
        className={cn(
          "relative w-full overflow-hidden bg-zinc-900/80",
          compact ? "aspect-[16/10]" : "aspect-video",
        )}
      >
        {room.enabled && health !== "off" ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={roomPreviewMjpegUrl(room.id)}
            alt=""
            className={cn(
              "size-full object-cover transition-opacity",
              health === "dark" && "brightness-[0.55] contrast-90",
              health === "waiting" && "opacity-40",
            )}
          />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-1.5 text-zinc-600">
            <PowerOff className="size-5 opacity-60" aria-hidden />
            <span className="text-[11px]">Not scanning</span>
          </div>
        )}
        <div
          className="pointer-events-none absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/20 to-zinc-950/50"
          aria-hidden
        />
        <div className="absolute inset-x-0 top-0 flex items-start justify-between gap-2 p-2.5 sm:p-3">
          <div className="flex min-w-0 items-start gap-2">
            <HealthDot health={health} />
            <div className="min-w-0">
              <h3
                className={cn(
                  "truncate font-semibold text-zinc-50",
                  compact ? "text-[13px]" : "text-sm",
                )}
              >
                {room.name}
              </h3>
              <p className="truncate text-[10px] text-zinc-400">
                {roomRoleLabel(role)}
                {health === "dark" ? " · check lighting" : ""}
              </p>
            </div>
          </div>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="size-8 shrink-0 text-zinc-300 hover:bg-white/10"
            aria-label={room.enabled ? `Pause ${room.name}` : `Resume ${room.name}`}
            disabled={togglingEnabled}
            onClick={() => onToggleEnabled(!room.enabled)}
          >
            {room.enabled ? (
              <Power className="size-3.5 text-emerald-300" />
            ) : (
              <PowerOff className="size-3.5 text-zinc-500" />
            )}
          </Button>
        </div>
        <div className="absolute bottom-2 left-2 right-2 flex flex-wrap items-end justify-between gap-2">
          <div className="flex flex-wrap gap-1">
            {role === "inferring" ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-teal-400/35 bg-teal-950/80 px-2 py-0.5 text-[10px] font-medium text-teal-100">
                <Radio className="size-2.5" aria-hidden />
                Inferring
              </span>
            ) : role === "grace_scan" ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/30 bg-amber-950/75 px-2 py-0.5 text-[10px] text-amber-100">
                <ScanEye className="size-2.5" aria-hidden />
                Scanning
              </span>
            ) : role === "active_hold" ? (
              <span className="rounded-full border border-amber-400/25 bg-amber-950/70 px-2 py-0.5 text-[10px] text-amber-100">
                Grace hold
              </span>
            ) : room.enabled ? (
              <span className="rounded-full border border-white/12 bg-black/50 px-2 py-0.5 text-[10px] text-zinc-400">
                Preview
              </span>
            ) : null}
            {mood ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-white/12 bg-black/55 px-2 py-0.5 text-[10px] font-medium text-zinc-100 backdrop-blur-sm">
                {role === "inferring" ? (
                  <Sparkles className="size-2.5 text-teal-300/80" aria-hidden />
                ) : null}
                {roomStateLabel(mood)}
              </span>
            ) : (
              <span className="rounded-full border border-white/8 bg-black/40 px-2 py-0.5 text-[10px] text-zinc-600">
                No recent mood
              </span>
            )}
          </div>
        </div>
      </div>

      <div
        className={cn(
          "flex items-center justify-between gap-2 border-t border-white/[0.06] px-2.5 py-2",
          compact && "px-2 py-1.5",
        )}
      >
        {room.isActive ? (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className={cn(
              "h-8 flex-1 gap-1.5 bg-teal-900/50 text-teal-100 hover:bg-teal-900/70",
              compact && "h-7 text-[11px]",
            )}
            onClick={onFocus}
          >
            <Maximize2 className="size-3.5" aria-hidden />
            Watch live
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className={cn(
              "h-8 flex-1 gap-1.5 border-white/15 bg-zinc-900/60 text-zinc-200 hover:bg-zinc-800",
              compact && "h-7 text-[11px]",
            )}
            disabled={!room.enabled || activating}
            onClick={onActivate}
          >
            <ArrowRight className="size-3.5" aria-hidden />
            Make active
          </Button>
        )}
      </div>
    </article>
  )
}

export function RoomViewToggle({
  view,
  onViewChange,
}: {
  view: "gallery" | "focus"
  onViewChange: (view: "gallery" | "focus") => void
}) {
  const orchestratorMode = useLiveSessionStore((s) => s.orchestratorMode)
  const graceRemainingSec = useLiveSessionStore((s) => s.graceRemainingSec)

  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-zinc-950/80 p-0.5">
        <Button
          type="button"
          size="sm"
          variant={view === "gallery" ? "secondary" : "ghost"}
          className="h-7 gap-1.5 text-xs"
          onClick={() => onViewChange("gallery")}
        >
          <LayoutGrid className="size-3.5" />
          Rooms
        </Button>
        <Button
          type="button"
          size="sm"
          variant={view === "focus" ? "secondary" : "ghost"}
          className="h-7 gap-1.5 text-xs"
          onClick={() => onViewChange("focus")}
        >
          <Maximize2 className="size-3.5" />
          Focus
        </Button>
      </div>
      {orchestratorMode === "grace" && graceRemainingSec != null ? (
        <p
          className={cn(
            roomosUi.liveStatusPillTranslucent,
            "rounded-full px-3 py-1 text-[11px] text-amber-100",
          )}
        >
          Grace · {Math.ceil(graceRemainingSec)}s
        </p>
      ) : null}
    </div>
  )
}

export function RoomsGallery({
  snapshot,
  onFocus,
}: {
  snapshot: LiveInferenceSnapshot | null
  onFocus: () => void
}) {
  const rooms = useLiveSessionStore((s) => s.rooms)
  const activeRoomId = useLiveSessionStore((s) => s.activeRoomId)
  const orchestratorMode = useLiveSessionStore((s) => s.orchestratorMode)
  const graceRemainingSec = useLiveSessionStore((s) => s.graceRemainingSec)
  const graceDurationSec = useLiveSessionStore((s) => s.graceDurationSec)
  const { activateRoom, toggleEnabled } = useRoomOrchestrationActions()

  const density = galleryLayoutDensity(rooms.length)

  if (rooms.length === 0) {
    return null
  }

  const handleActivate = (roomId: string) => {
    activateRoom.mutate(roomId, {
      onSuccess: () => onFocus(),
    })
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <OrchestrationStrip
        mode={orchestratorMode}
        graceRemainingSec={graceRemainingSec}
        graceDurationSec={graceDurationSec}
        rooms={rooms}
        activeRoomId={activeRoomId}
      />
      <div
        className={cn(
          "grid min-h-0 flex-1 gap-2.5 overflow-y-auto sm:gap-3",
          density === "compact"
            ? "grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
            : rooms.length === 2
              ? "grid-cols-1 sm:grid-cols-2"
              : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
        )}
      >
        {rooms.map((room) => (
          <RoomCard
            key={room.id}
            room={room}
            density={density}
            snapshot={snapshot}
            orchestratorMode={orchestratorMode}
            onFocus={onFocus}
            onActivate={() => handleActivate(room.id)}
            onToggleEnabled={(enabled) =>
              toggleEnabled.mutate({ roomId: room.id, enabled })
            }
            togglingEnabled={
              toggleEnabled.isPending && toggleEnabled.variables?.roomId === room.id
            }
            activating={activateRoom.isPending && activateRoom.variables === room.id}
          />
        ))}
      </div>
    </div>
  )
}
