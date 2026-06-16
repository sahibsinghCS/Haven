"use client"

import type { MoodDefinition, MoodLifecycle } from "@/types/roomos"
import { cn } from "@/lib/utils"

const LIFECYCLE_META: Record<
  MoodLifecycle,
  { label: string; tone: string; explain: string }
> = {
  ready: {
    label: "Live ready",
    tone: "bg-emerald-500/10 text-emerald-900 ring-emerald-500/25",
    explain: "In the model bundle and eligible for live inference.",
  },
  collecting: {
    label: "Collecting",
    tone: "bg-sky-500/10 text-sky-900 ring-sky-500/25",
 explain: "Camera capture in progress. review bursts before training.",
  },
  training: {
    label: "Training",
    tone: "bg-violet-500/10 text-violet-900 ring-violet-500/25",
    explain: "Personal XGBoost head is retraining on this device.",
  },
  error: {
    label: "Needs attention",
    tone: "bg-rose-500/10 text-rose-900 ring-rose-500/25",
    explain: "Training or ML pipeline reported an error. check captures.",
  },
  custom_untrained: {
    label: "Needs captures",
    tone: "bg-amber-500/10 text-amber-900 ring-amber-500/25",
    explain: "Custom mood. teach the camera and train before live use.",
  },
  builtin_untrained: {
    label: "Needs training",
    tone: "bg-amber-500/10 text-amber-900 ring-amber-500/25",
    explain: "Built-in label exists but no personal training data yet.",
  },
  builtin_deleted: {
    label: "Removed",
    tone: "bg-stone-500/10 text-stone-700 ring-stone-400/25",
    explain: "Hidden from preferences; restore from Add mood if needed.",
  },
  inference_hidden: {
    label: "Hidden from live",
    tone: "bg-stone-500/10 text-stone-600 ring-stone-400/25",
    explain: "Not in the active model bundle. scenes may still apply.",
  },
}

function resolveLifecycle(mood: MoodDefinition): MoodLifecycle {
  if (mood.lifecycle) return mood.lifecycle
  const s = mood.ml?.status ?? "untrained"
  if (s === "ready") return "ready"
  if (s === "collecting") return "collecting"
  if (s === "training") return "training"
  if (s === "error") return "error"
  return mood.kind === "custom" ? "custom_untrained" : "builtin_untrained"
}

export function MoodLifecycleChip({ mood }: { mood: MoodDefinition }) {
  const lifecycle = resolveLifecycle(mood)
  const meta = LIFECYCLE_META[lifecycle]
  const bursts = mood.ml?.burstCount ?? 0
  const frames = mood.ml?.frameCount ?? 0

  return (
    <div className="flex flex-col gap-1 px-1">
      <span
        className={cn(
          "inline-flex w-fit items-center rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ring-1",
          meta.tone,
        )}
        title={meta.explain}
      >
        {meta.label}
      </span>
      <p className="text-[11px] leading-snug text-[color:var(--haven-faint)]">{meta.explain}</p>
      {(bursts > 0 || frames > 0) && (
        <p className="text-[10px] tabular-nums text-[color:var(--haven-faint)]">
          {frames} frames · {bursts} bursts you captured (this mood only)
          {mood.ml?.lastTrainedAt
            ? ` · trained ${new Date(mood.ml.lastTrainedAt).toLocaleDateString()}`
            : ""}
        </p>
      )}
    </div>
  )
}

export function moodLifecycleFilter(mood: MoodDefinition, filter: MoodFilter): boolean {
  if (filter === "all") return true
  const lc = resolveLifecycle(mood)
  if (filter === "live") return mood.inferenceEligible === true || lc === "ready"
  if (filter === "teach") return lc === "custom_untrained" || lc === "builtin_untrained"
  if (filter === "active") return lc === "collecting" || lc === "training"
  return true
}

export type MoodFilter = "all" | "live" | "teach" | "active"
