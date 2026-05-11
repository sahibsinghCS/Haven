"use client"

import { motion, useReducedMotion } from "framer-motion"

import { roomosUi } from "@/lib/roomos/roomos-ui"
import { ROOM_STATE_LABEL } from "@/lib/roomos/state-meta"
import type { RoomStateId } from "@/types/roomos"

import { cn } from "@/lib/utils"

export function PrimaryStateOverlay({
  state,
  confidence,
  sceneSummary,
}: {
  state: RoomStateId
  confidence: number
  /** One-line device summary — not color-coded state alone */
  sceneSummary: string
}) {
  const reduceMotion = useReducedMotion()
  const pct = Math.round(confidence * 100)
  const pctLabel = `${pct} percent confidence in ${ROOM_STATE_LABEL[state]}`

  return (
    <div className="pointer-events-none flex w-full min-w-0 max-w-lg flex-col lg:max-w-xl">
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
          roomosUi.liveOverlayGlass,
          "px-6 py-5 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.07)] sm:px-7 sm:py-6",
        )}
      >
        <p
          id="roomos-primary-state-label"
          className="text-[0.6875rem] font-semibold uppercase tracking-[0.18em] text-zinc-300"
        >
          Right now
        </p>
        <p
          id="roomos-live-trust"
          className="mt-1.5 max-w-md text-xs leading-relaxed text-zinc-400 sm:text-[0.8125rem]"
        >
          Inferred on this device from your camera and signals — nothing is uploaded as video.
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-x-5 gap-y-2">
          <h3 className="text-balance text-4xl font-semibold leading-[1.05] tracking-tight text-zinc-50 sm:text-5xl lg:text-[3.25rem]">
            {ROOM_STATE_LABEL[state]}
          </h3>
          <p
            id="roomos-primary-confidence"
            className="mb-0.5 flex items-baseline gap-2.5 tabular-nums text-zinc-100"
          >
            <span className="text-3xl font-semibold sm:text-4xl" aria-label={pctLabel}>
              {pct}
              <span className="text-lg font-medium text-zinc-400">%</span>
            </span>
            <span className="pb-0.5 text-[0.7rem] font-medium uppercase tracking-[0.12em] text-zinc-400">
              confidence
            </span>
          </p>
        </div>
        <div className="mt-5 border-t border-white/[0.1] pt-4">
          <p
            id="roomos-scene-label"
            className="text-[0.65rem] font-semibold uppercase tracking-[0.14em] text-zinc-400"
          >
            Room scene
          </p>
          <p
            id="roomos-scene-summary"
            className="mt-1.5 max-w-prose text-sm leading-relaxed text-zinc-300"
          >
            {sceneSummary}
          </p>
        </div>
      </motion.article>
    </div>
  )
}
