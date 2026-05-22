"use client"

import { Camera, CircleDot, Clapperboard, Home, Sparkles } from "lucide-react"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type { LiveInferenceStatus } from "@/hooks/use-live-inference"
import type { LiveEngineHookStatus } from "@/hooks/use-live-engine"
import type { LiveMode } from "@/lib/roomos/api-client"
import type { AutomationMode, LiveInferenceSnapshot } from "@/types/roomos"

export function LiveDemoStatusBar({
  engineStatus,
  inferenceSource,
  connectionStatus,
  snapshot,
  previewStatus,
  liveMode = "live",
  demoMode = false,
}: {
  engineStatus: LiveEngineHookStatus
  inferenceSource: string | null
  connectionStatus: LiveInferenceStatus
  snapshot: LiveInferenceSnapshot
  previewStatus: "idle" | "waiting" | "live" | "error"
  liveMode?: LiveMode
  demoMode?: boolean
}) {
  const isReplay = demoMode || liveMode === "replay" || snapshot.dataSource === "demo-replay"

  const cameraLabel = isReplay
    ? "Demo replay feed"
    : previewStatus === "live"
      ? "Camera live"
      : previewStatus === "waiting"
        ? "Camera starting"
        : engineStatus === "running"
          ? "Camera waiting"
          : "Camera off"

  const modelLabel = isReplay
    ? `Replay step${typeof snapshot.sequence === "number" ? ` · ${snapshot.sequence}` : ""}`
    : connectionStatus === "live"
      ? `Model live${typeof snapshot.sequence === "number" ? ` · burst ${snapshot.sequence}` : ""}`
      : connectionStatus === "connecting"
        ? "Model connecting"
        : "Model polling"

  const automation = snapshot.automationMode ?? "off"
  const automationLabel =
    automation === "live"
      ? "Devices contacted"
      : automation === "dry_run"
        ? "Automations simulated"
        : "Automations off"

  return (
    <div
      className="pointer-events-none flex w-full flex-wrap items-center gap-2"
      role="status"
      aria-label="Live demo system status"
    >
      {isReplay ? (
        <StatusChip
          icon={Clapperboard}
          label="Demo replay ON"
          detail="Prerecorded states — not live inference"
          warn
          active
        />
      ) : null}
      <StatusChip
        icon={Camera}
        label={cameraLabel}
        detail={isReplay ? "Synthetic preview frames" : shortSource(inferenceSource)}
        active={previewStatus === "live"}
        warn={previewStatus === "waiting" || isReplay}
      />
      <StatusChip
        icon={Sparkles}
        label={modelLabel}
        detail={isReplay ? "Scripted walkthrough" : "Burst classifier on this machine"}
        active={connectionStatus === "live"}
        warn={isReplay}
      />
      <StatusChip
        icon={CircleDot}
        label={formatUpdatedShort(snapshot.capturedAt)}
        detail="Smoothed over recent bursts"
        active
      />
      <StatusChip
        icon={Home}
        label={automationLabel}
        detail={
          automation === "dry_run"
            ? "Logs only — no smart-home calls"
            : snapshot.lastAutomation?.summary ?? "Rules from actions config"
        }
        active={automation === "live"}
        warn={automation === "dry_run"}
      />
    </div>
  )
}

function StatusChip({
  icon: Icon,
  label,
  detail,
  active,
  warn,
}: {
  icon: typeof Camera
  label: string
  detail: string
  active?: boolean
  warn?: boolean
}) {
  return (
    <div
      className={cn(
        roomosUi.liveStatusPillTranslucent,
        "inline-flex min-w-0 max-w-full flex-col gap-0.5 px-3 py-2 sm:max-w-[14rem]",
        active && "border-emerald-400/25 bg-emerald-950/35",
        warn && !active && "border-amber-400/20 bg-amber-950/30",
      )}
      title={detail}
    >
      <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-100">
        <Icon className="size-3 shrink-0 text-teal-200/90" aria-hidden />
        <span className="truncate">{label}</span>
      </span>
      <span className="truncate pl-[1.15rem] text-[10px] leading-snug text-zinc-500">{detail}</span>
    </div>
  )
}

function shortSource(source: string | null): string {
  if (!source) return "Backend OpenCV feed"
  if (source.includes("Webcam index")) return source.replace(" (RoomOS / OpenCV)", "")
  return source.length > 42 ? `${source.slice(0, 40)}…` : source
}

function formatUpdatedShort(iso: string): string {
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return "Just updated"
  const sec = Math.max(0, Math.round((Date.now() - t) / 1000))
  if (sec < 3) return "Updated now"
  if (sec < 60) return `Updated ${sec}s ago`
  return `Updated ${Math.round(sec / 60)}m ago`
}
