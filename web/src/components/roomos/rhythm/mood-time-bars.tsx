"use client"

import { havenCard } from "@/components/roomos/haven-primitives"
import { roomStateLabel, roomStateLandingSkin } from "@/lib/roomos/state-meta"
import { formatRhythmDuration } from "@/lib/roomos/rhythm-format"
import type { RhythmMoodSlice } from "@/types/rhythm"
import { cn } from "@/lib/utils"

const cardShell = havenCard

export function MoodTimeBars({
  moods,
  totalTrackedSec,
  moodDeltas,
  className,
}: {
  moods: RhythmMoodSlice[]
  totalTrackedSec: number
  moodDeltas?: Record<string, number>
  className?: string
}) {
  if (!moods.length) {
    return (
      <div className={cn(cardShell, "px-6 py-10 text-center", className)}>
        <p className="text-[14px] text-[color:var(--haven-muted)]">
          No mood time recorded in this period.
        </p>
      </div>
    )
  }

  return (
    <section className={cn(cardShell, "px-5 py-6 sm:px-6", className)} aria-label="Time per mood">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="haven-display text-[1.2rem] font-semibold text-[color:var(--haven-ink)]">
            Time per mood
          </h2>
          <p className="mt-1 text-[13px] text-[color:var(--haven-muted)]">
            {formatRhythmDuration(totalTrackedSec)} tracked from live inference
          </p>
        </div>
      </div>

      <ul className="mt-6 space-y-4">
        {moods.map((mood) => {
          const skin = roomStateLandingSkin(mood.id)
          const delta = moodDeltas?.[mood.id]
          return (
            <li key={mood.id}>
              <div className="mb-1.5 flex items-baseline justify-between gap-3 text-[13px]">
                <span className="font-semibold text-[color:var(--haven-ink)]">
                  {roomStateLabel(mood.id)}
                </span>
                <span className="tabular-nums text-[color:var(--haven-muted)]">
                  <span className="font-medium text-[color:var(--haven-ink-soft)]">
                    {mood.percent.toFixed(0)}%
                  </span>
                  <span className="mx-1.5 text-[color:var(--haven-faint)]">·</span>
                  {formatRhythmDuration(mood.seconds)}
                </span>
              </div>
              <div
                className="h-2.5 overflow-hidden rounded-full bg-[color:var(--haven-canvas-mist)] ring-1 ring-[color:var(--haven-line)]"
                role="presentation"
              >
                <div
                  className={cn("h-full rounded-full transition-[width] duration-500 ease-out", skin.bar)}
                  style={{ width: `${Math.min(100, Math.max(0, mood.percent))}%` }}
                />
              </div>
              {delta !== undefined && Math.abs(delta) >= 60 ? (
                <p className="mt-1 text-[11px] text-[color:var(--haven-faint)]">
                  vs prior period:{" "}
                  <span className="tabular-nums text-[color:var(--haven-muted)]">
                    {delta > 0 ? "+" : "−"}
                    {formatRhythmDuration(Math.abs(delta))}
                  </span>
                </p>
              ) : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
