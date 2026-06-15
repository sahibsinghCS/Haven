"use client"

import { memo, useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"

import { cn } from "@/lib/utils"
import { sortedDistributionEntries } from "@/lib/roomos/live-confidence-utils"
import { roomStateAccent, roomStateLabel } from "@/lib/roomos/state-meta"
import type { RoomStateDistribution, RoomStateId } from "@/types/roomos"

function formatPct(value: number, fine = false) {
  if (fine) {
    const pct = Math.round(value * 1000) / 10
    return `${pct % 1 === 0 ? pct.toFixed(0) : pct.toFixed(1)}%`
  }
  return `${Math.round(value * 100)}%`
}

export const LiveDistributionList = memo(function LiveDistributionList({
  distribution,
  primary,
  finePercent = true,
  showModelHint = false,
}: {
  distribution: RoomStateDistribution
  primary: RoomStateId
  finePercent?: boolean
  showModelHint?: boolean
}) {
  const reduceMotion = useReducedMotion()
  const entries = useMemo(() => sortedDistributionEntries(distribution), [distribution])
  const barTransition = reduceMotion
    ? { duration: 0.15, ease: "easeOut" as const }
    : { type: "spring" as const, stiffness: 200, damping: 28 }

  return (
    <div>
      {showModelHint ? (
        <p className="mb-3 text-[11px] leading-relaxed text-zinc-500">
          Raw model likelihoods for this burst — before room-memory smoothing.
        </p>
      ) : null}
      <div
        role="list"
        aria-label="Confidence for all room states"
        className="flex flex-col gap-1.5"
      >
        {entries.map(([id, value]) => {
          const active = id === primary
          const accent = roomStateAccent(id)
          const label = roomStateLabel(id)
          const pct = formatPct(value, finePercent)
          return (
            <div
              key={id}
              role="listitem"
              aria-label={
                active
                  ? `${label}, ${pct} likelihood, matches primary state`
                  : `${label}, ${pct} likelihood`
              }
              className={cn(
                "relative flex min-w-0 items-center gap-3 rounded-xl border px-3 py-2 transition-colors duration-300",
                active
                  ? "border-white/[0.18] bg-white/[0.12] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.07)]"
                  : "border-white/[0.08] bg-white/[0.055]",
              )}
            >
              <span
                className={cn(
                  "size-1.5 shrink-0 rounded-full",
                  accent.bar,
                  !active && "opacity-65",
                )}
                aria-hidden
              />
              <span
                className={cn(
                  "min-w-0 flex-1 truncate text-[12.5px] font-medium leading-snug",
                  active ? "text-zinc-50" : "text-zinc-300",
                )}
              >
                {label}
              </span>
              <div
                className="relative h-[3px] w-20 overflow-hidden rounded-full bg-white/[0.08]"
                aria-hidden
              >
                <motion.div
                  className={cn(
                    "absolute inset-y-0 left-0 rounded-full",
                    accent.bar,
                    !active && "opacity-80",
                  )}
                  initial={false}
                  animate={{ width: `${Math.round(value * 100)}%` }}
                  transition={barTransition}
                />
              </div>
              <span className="w-10 shrink-0 text-right font-mono text-[11.5px] font-semibold tabular-nums text-zinc-300">
                {pct}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
})
