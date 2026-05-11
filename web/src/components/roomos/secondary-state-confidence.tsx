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
        className={cn(roomosUi.liveOverlayGlass, "w-full p-4 sm:p-5")}
      >
        <div className="flex items-center justify-between gap-3 px-0.5 pb-3.5">
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-zinc-400">
            Also considering
          </p>
          <span className="text-[0.65rem] font-medium uppercase tracking-[0.14em] text-zinc-600">
            Distribution
          </span>
        </div>
        <div
          role="list"
          aria-label="Confidence for other room states"
          className="flex flex-col gap-1.5"
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
                  "group/sec relative flex min-w-0 items-center gap-3 rounded-xl border px-3 py-2 transition-colors duration-300",
                  active
                    ? "border-white/[0.16] bg-white/[0.07] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]"
                    : "border-white/[0.06] bg-white/[0.025] hover:bg-white/[0.04]",
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
                <div className="relative h-[3px] w-20 overflow-hidden rounded-full bg-white/[0.08]" aria-hidden>
                  <motion.div
                    className={cn("absolute inset-y-0 left-0 rounded-full", accent.bar, !active && "opacity-80")}
                    initial={false}
                    animate={{ width: `${Math.round(value * 100)}%` }}
                    transition={barTransition}
                  />
                </div>
                <span className="w-9 shrink-0 text-right font-mono text-[11.5px] font-semibold tabular-nums text-zinc-300">
                  {pct}
                </span>
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
