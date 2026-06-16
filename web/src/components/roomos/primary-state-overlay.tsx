"use client"

import { motion, useReducedMotion } from "framer-motion"
import { Activity } from "lucide-react"

import { roomosUi } from "@/lib/roomos/roomos-ui"
import { roomStateAccent, roomStateLabel } from "@/lib/roomos/state-meta"
import type { RoomStateId } from "@/types/roomos"

import { cn } from "@/lib/utils"

export function PrimaryStateOverlay({
  state,
  confidence,
  sceneSummary,
  uncertaintyNote,
  trustLine,
  overlayShellClassName,
  className,
}: {
  state: RoomStateId
  confidence: number
  /** One-line device summary (not color-coded state alone) */
  sceneSummary: string
 /** Shown when top labels are close. honest mixed read */
  uncertaintyNote?: string | null
  /** Overrides default local-inference trust copy */
  trustLine?: string
  /** Replaces default `liveOverlayGlass` (e.g. translucent over video) */
  overlayShellClassName?: string
  className?: string
}) {
  const reduceMotion = useReducedMotion()
  const pct = Math.round(confidence * 100)
  const pctLabel = `${pct} percent confidence in ${roomStateLabel(state)}`
  const accent = roomStateAccent(state)

  return (
    <div className="pointer-events-none flex w-full min-w-0 max-w-lg flex-col lg:max-w-2xl 2xl:max-w-3xl">
      <motion.article
        key={state}
        layout={!reduceMotion}
        initial={reduceMotion ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={
          reduceMotion
            ? { duration: 0.15 }
            : { duration: 0.42, ease: [0.22, 1, 0.36, 1] }
        }
        role="region"
        aria-label="Current primary room state"
        aria-live="polite"
        aria-atomic="true"
        aria-labelledby="roomos-primary-state-label"
        aria-describedby="roomos-live-trust roomos-primary-confidence roomos-scene-label roomos-scene-summary"
        className={cn(
          overlayShellClassName ?? roomosUi.liveOverlayGlass,
          "relative isolate overflow-hidden px-6 py-5 sm:px-7 sm:py-6",
          className,
        )}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_78%_58%_at_8%_0%,rgba(255,255,255,0.08),transparent_62%),linear-gradient(180deg,rgba(255,255,255,0.035),transparent_36%)]"
        />
        <div className="relative">
          <div className="flex items-center gap-2.5">
            <span
              className="relative flex size-2 items-center justify-center"
              aria-hidden
            >
              {!reduceMotion ? (
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400/55 motion-reduce:animate-none" />
              ) : null}
              <span className="relative inline-flex size-2 rounded-full bg-emerald-400/95" />
            </span>
            <p
              id="roomos-primary-state-label"
              className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-zinc-300"
            >
              Right now
            </p>
          </div>
          <p
            id="roomos-live-trust"
            className="mt-2 max-w-md text-xs leading-relaxed text-zinc-500 sm:text-[0.8125rem]"
          >
            {trustLine ??
              "Local burst classifier · same camera as preview · nothing uploaded"}
          </p>
          {uncertaintyNote ? (
            <p
              className="mt-2 max-w-md rounded-lg border border-amber-400/25 bg-amber-950/35 px-2.5 py-1.5 text-[11px] leading-snug text-amber-100/95"
              role="note"
            >
              {uncertaintyNote}
            </p>
          ) : null}
          <div className="mt-5 flex flex-wrap items-end gap-x-6 gap-y-3">
            <h3 className="haven-display text-balance text-4xl font-semibold leading-[1.02] tracking-[-0.04em] text-zinc-50 sm:text-5xl lg:text-[3.75rem] xl:text-[4.25rem] 2xl:text-[4.75rem]">
              {roomStateLabel(state)}
            </h3>
            <p
              id="roomos-primary-confidence"
              className="mb-1 flex items-baseline gap-2 tabular-nums text-zinc-100"
            >
              <span
                className="text-3xl font-semibold tracking-tight sm:text-[2.5rem] xl:text-[2.75rem] 2xl:text-[3rem]"
                aria-label={pctLabel}
              >
                {pct}
                <span className="text-lg font-medium text-zinc-500">%</span>
              </span>
              <span className="pb-1 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-zinc-500">
                confidence
              </span>
            </p>
          </div>

          {/* Confidence meter: visualizes the read */}
          <div
            className="relative mt-5 h-1 overflow-hidden rounded-full bg-white/[0.07] ring-1 ring-white/[0.03]"
            aria-hidden
          >
            <motion.div
              className={cn("absolute inset-y-0 left-0 rounded-full", accent.bar)}
              initial={false}
              animate={{ width: `${pct}%` }}
              transition={
                reduceMotion
                  ? { duration: 0.15 }
                  : { type: "spring", stiffness: 200, damping: 28 }
              }
            />
            <span className="absolute inset-y-0 right-0 w-px bg-white/[0.08]" />
          </div>

          <div className="mt-5 flex items-start gap-4 border-t border-white/[0.08] pt-4">
            <span
              className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-zinc-300"
              aria-hidden
            >
              <Activity className="size-3.5" strokeWidth={1.85} />
            </span>
            <div className="min-w-0">
              <p
                id="roomos-scene-label"
                className="text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-zinc-500"
              >
                Room scene
              </p>
              <p
                id="roomos-scene-summary"
                className="mt-1 max-w-prose text-[13.5px] leading-relaxed text-zinc-200"
              >
                {sceneSummary}
              </p>
            </div>
          </div>
        </div>
      </motion.article>
    </div>
  )
}
