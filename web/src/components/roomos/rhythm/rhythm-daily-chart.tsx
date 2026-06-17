"use client"

import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"

import { havenCard } from "@/components/roomos/haven-primitives"
import { roomStateLandingSkin, roomStateLabel } from "@/lib/roomos/state-meta"
import { formatRhythmDuration } from "@/lib/roomos/rhythm-format"
import type { RhythmDailyBreakdown } from "@/types/rhythm"
import { cn } from "@/lib/utils"

function dayLabel(isoDate: string): string {
  const d = new Date(`${isoDate}T12:00:00`)
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })
}

export function RhythmDailyChart({
  days,
  moodOrder,
}: {
  days: RhythmDailyBreakdown[]
  moodOrder: string[]
}) {
  const reduceMotion = useReducedMotion()
  const orderedMoods = useMemo(() => {
    const seen = new Set<string>()
    const order: string[] = []
    for (const id of moodOrder) {
      if (!seen.has(id)) {
        seen.add(id)
        order.push(id)
      }
    }
    for (const day of days) {
      for (const id of Object.keys(day.moods)) {
        if (!seen.has(id)) {
          seen.add(id)
          order.push(id)
        }
      }
    }
    return order
  }, [days, moodOrder])

  if (!days.length) return null

  const maxTotal = Math.max(...days.map((d) => d.totalSec), 1)

  return (
    <section className={cn(havenCard, "px-5 py-6 sm:px-6")} aria-label="Daily rhythm">
      <h2 className="haven-display text-[1.2rem] font-semibold text-[color:var(--haven-ink)]">
        Daily breakdown
      </h2>
      <p className="mt-1 text-[13px] text-[color:var(--haven-muted)]">
        Stacked mood time per day
      </p>

      <div className="mt-6 flex items-end justify-between gap-2 sm:gap-3">
        {days.map((day, dayIndex) => {
          const heightPct = day.totalSec > 0 ? (day.totalSec / maxTotal) * 100 : 4
          const segments = orderedMoods
            .map((id) => ({ id, sec: day.moods[id] ?? 0 }))
            .filter((s) => s.sec > 0)

          return (
            <div
              key={day.date}
              className="flex min-w-0 flex-1 flex-col items-center gap-2"
            >
              <div
                className="flex w-full max-w-[3.25rem] flex-col justify-end overflow-hidden rounded-lg bg-[color:var(--haven-canvas-mist)] ring-1 ring-[color:var(--haven-line)]"
                style={{ height: "9rem" }}
                title={formatRhythmDuration(day.totalSec)}
              >
                <motion.div
                  className="flex w-full flex-col justify-end"
                  initial={reduceMotion ? false : { height: "4%" }}
                  animate={{ height: `${Math.max(4, heightPct)}%` }}
                  transition={
                    reduceMotion
                      ? { duration: 0 }
                      : { duration: 0.55, delay: dayIndex * 0.05, ease: [0.22, 1, 0.36, 1] }
                  }
                >
                  {segments.map((seg) => {
                    const pct = day.totalSec > 0 ? (seg.sec / day.totalSec) * 100 : 0
                    const skin = roomStateLandingSkin(seg.id)
                    return (
                      <div
                        key={seg.id}
                        className={cn("w-full min-h-[2px]", skin.bar)}
                        style={{ height: `${pct}%` }}
                        title={`${roomStateLabel(seg.id)}: ${formatRhythmDuration(seg.sec)}`}
                      />
                    )
                  })}
                </motion.div>
              </div>
              <span className="max-w-full truncate text-center text-[10px] font-medium text-[color:var(--haven-faint)]">
                {dayLabel(day.date)}
              </span>
            </div>
          )
        })}
      </div>

      {orderedMoods.length > 0 ? (
        <ul className="mt-6 flex flex-wrap gap-x-4 gap-y-2">
          {orderedMoods.map((id) => {
            const skin = roomStateLandingSkin(id)
            return (
              <li
                key={id}
                className="flex items-center gap-1.5 text-[11px] text-[color:var(--haven-muted)]"
              >
                <span className={cn("size-2 rounded-full", skin.bar)} aria-hidden />
                {roomStateLabel(id)}
              </li>
            )
          })}
        </ul>
      ) : null}
    </section>
  )
}
