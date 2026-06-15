"use client"

import { roomStateLabel } from "@/lib/roomos/state-meta"
import type { FeedbackResponse } from "@/lib/roomos/api-client"
import type { RoomStateDistribution, RoomStateId } from "@/types/roomos"
import { cn } from "@/lib/utils"

function ProbabilityShift({
  before,
  after,
  highlight,
  applied,
}: {
  before: RoomStateDistribution
  after: RoomStateDistribution
  highlight: RoomStateId
  applied?: boolean
}) {
  const keys = Object.keys(after).filter((k) => (after[k] ?? 0) > 0.02 || k === highlight)
  return (
    <div className="mt-3 space-y-2">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[color:var(--haven-faint)]">
        Memory preview {applied ? "(applied)" : "(estimate)"}
      </p>
      <ul className="space-y-1">
        {keys.slice(0, 5).map((id) => {
          const b = Math.round((before[id] ?? 0) * 100)
          const a = Math.round((after[id] ?? 0) * 100)
          const delta = a - b
          return (
            <li key={id} className="flex items-center justify-between gap-2 text-[11px]">
              <span className={cn(id === highlight && "font-semibold text-[color:var(--haven-ink)]")}>
                {roomStateLabel(id)}
              </span>
              <span className="font-mono tabular-nums text-[color:var(--haven-muted)]">
                {b}% → {a}%
                {delta !== 0 ? (
                  <span className={cn("ml-1", delta > 0 ? "text-teal-700" : "text-amber-700")}>
                    ({delta > 0 ? "+" : ""}
                    {delta})
                  </span>
                ) : null}
              </span>
            </li>
          )
        })}
      </ul>
      <p className="text-[10px] leading-relaxed text-[color:var(--haven-faint)]">
        Room memory nudges similar bursts — not a full model retrain unless noted.
      </p>
    </div>
  )
}

/** Honest post-correction summary (live dark or preferences light). */
export function CorrectionOutcomeCard({
  result,
  variant = "light",
}: {
  result: FeedbackResponse
  variant?: "light" | "dark"
}) {
  const preview = result.probabilityPreview
  const corrected = result.correctedLabel as RoomStateId
  const wasConfirm = result.confirmed ?? result.predictedLabel === result.correctedLabel
  const isDark = variant === "dark"

  return (
    <div
      className={cn(
        "rounded-xl border p-3",
        isDark
          ? "border-teal-400/20 bg-teal-950/25 text-zinc-300"
          : "border-teal-600/20 bg-teal-50/80 text-[color:var(--haven-muted)]",
      )}
      role="status"
      aria-live="polite"
    >
      <p
        className={cn(
          "text-[11px] font-semibold uppercase tracking-[0.14em]",
          isDark ? "text-teal-200/90" : "text-teal-900",
        )}
      >
        {wasConfirm ? "Reinforced" : "Corrected"}
        {result.retrainsModel ? " · counts toward retrain" : ""}
      </p>
      <ul className="mt-2 space-y-1 text-[12px] leading-relaxed">
        <li>
          <span className="opacity-70">Burst saved:</span> {result.screenshotCount} frame
          {result.screenshotCount === 1 ? "" : "s"} on this device
        </li>
        <li>
          <span className="opacity-70">Total answers:</span> {result.memoryExamples}
        </li>
        <li>
          <span className="opacity-70">Label:</span> {roomStateLabel(corrected)}
          {wasConfirm ? " (confirmed)" : ` (was ${roomStateLabel(result.predictedLabel as RoomStateId)})`}
        </li>
        <li className="text-[11px] opacity-80">{result.effects.notIncluded}</li>
      </ul>
      {!wasConfirm && preview?.before && preview.after ? (
        <ProbabilityShift
          before={preview.before}
          after={preview.after}
          highlight={corrected}
          applied={preview.appliedAfterSave}
        />
      ) : null}
    </div>
  )
}
