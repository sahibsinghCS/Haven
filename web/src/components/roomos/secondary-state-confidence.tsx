"use client"

import { motion, useReducedMotion } from "framer-motion"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { ROOM_STATE_ACCENT, ROOM_STATE_LABEL } from "@/lib/roomos/state-meta"
import type { RoomStateDistribution, RoomStateId } from "@/types/roomos"
import { ROOM_STATE_ORDER } from "@/types/roomos"

function formatPct(value: number) {
  return `${Math.round(value * 100)}%`
}

export function SecondaryStateConfidence({
  variant = "inline",
  distribution,
  primary,
}: {
  variant?: "inline" | "overlay"
  distribution: RoomStateDistribution
  primary: RoomStateId
}) {
  const reduceMotion = useReducedMotion()
  const barTransition = reduceMotion
    ? { duration: 0.15, ease: "easeOut" as const }
    : { type: "spring" as const, stiffness: 200, damping: 28 }

  if (variant === "overlay") {
    return (
      <motion.div
        layout={!reduceMotion}
        transition={reduceMotion ? { duration: 0.15 } : { duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className={cn(
          roomosUi.liveOverlayGlass,
          "w-full p-4",
          "shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)]",
        )}
      >
        <p className="px-0.5 pb-3 text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-zinc-400">
          Also considering
        </p>
        <div
          role="list"
          aria-label="Confidence for other room states"
          className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-2"
        >
          {ROOM_STATE_ORDER.map((id) => {
            const value = distribution[id]
            const active = id === primary
            const accent = ROOM_STATE_ACCENT[id]
            const label = ROOM_STATE_LABEL[id]
            const pct = formatPct(value)
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
                  "flex min-h-[3.5rem] min-w-0 flex-col justify-center gap-1.5 rounded-xl border px-2.5 py-2 sm:px-3",
                  "border-white/[0.09] bg-white/[0.055]",
                  active && "border-white/[0.16] bg-white/[0.1] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]",
                )}
              >
                <div className="flex min-w-0 items-start justify-between gap-2">
                  <span
                    className={cn(
                      "min-w-0 flex-1 text-left text-[0.75rem] font-medium leading-snug sm:text-[0.8125rem]",
                      active ? "text-zinc-50" : "text-zinc-300",
                    )}
                  >
                    <span className="line-clamp-2 text-pretty">{label}</span>
                  </span>
                  <span className="shrink-0 self-start pt-0.5 text-xs font-semibold tabular-nums text-zinc-300">
                    {pct}
                  </span>
                </div>
                <div className="h-[2px] overflow-hidden rounded-full bg-white/[0.12]" aria-hidden>
                  <motion.div
                    className={cn("h-full rounded-full", accent.bar)}
                    initial={false}
                    animate={{ width: `${Math.round(value * 100)}%` }}
                    transition={barTransition}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </motion.div>
    )
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
      {ROOM_STATE_ORDER.map((id) => {
        const value = distribution[id]
        const active = id === primary
        const accent = ROOM_STATE_ACCENT[id]
        return (
          <div
            key={id}
            className={cn(
              "rounded-xl border border-white/[0.08] bg-white/[0.03] p-3 backdrop-blur-md",
              active && "border-white/[0.14] bg-white/[0.06]",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <p
                className={cn(
                  "text-[0.8125rem] font-medium",
                  active ? "text-zinc-100" : "text-zinc-500",
                )}
              >
                {ROOM_STATE_LABEL[id]}
              </p>
              <span className="text-sm font-medium tabular-nums text-zinc-400">
                {formatPct(value)}
              </span>
            </div>
            <div className="mt-2 h-[2px] overflow-hidden rounded-full bg-zinc-800/70">
              <motion.div
                className={cn("h-full rounded-full", accent.bar)}
                initial={false}
                animate={{ width: `${Math.round(value * 100)}%` }}
                transition={barTransition}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
