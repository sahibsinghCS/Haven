"use client"

import { memo, useMemo } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { Brain, ChevronDown, ChevronRight } from "lucide-react"

import { LiveQuickCorrection } from "@/components/roomos/live-quick-correction"
import { buildLiveExplainSummary } from "@/lib/roomos/live-explain-utils"
import { roomStateAccent } from "@/lib/roomos/state-meta"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type { LiveInferenceSnapshot } from "@/types/roomos"

const TIER_CHIP = {
  high: "border-teal-400/35 bg-teal-500/10 text-teal-100",
  medium: "border-amber-400/35 bg-amber-500/10 text-amber-100",
  low: "border-rose-400/35 bg-rose-500/10 text-rose-100",
} as const

function CompactStateBars({
  states,
}: {
  states: ReturnType<typeof buildLiveExplainSummary>["topStates"]
}) {
  return (
    <ul className="space-y-2.5" aria-label="State confidence">
      {states.slice(0, 4).map((state) => {
        const accent = roomStateAccent(state.id)
        return (
          <li key={state.id} className="space-y-1">
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <span
                  className={cn(
                    "size-2.5 shrink-0 rounded-full",
                    accent.bar,
                    !state.isPrimary && "opacity-50",
                  )}
                  aria-hidden
                />
                <span
                  className={cn(
                    "truncate text-[12px] font-medium leading-none",
                    state.isPrimary ? "text-zinc-100" : "text-zinc-400",
                  )}
                >
                  {state.label}
                </span>
              </div>
              <span
                className={cn(
                  "shrink-0 font-mono text-[12px] font-semibold tabular-nums",
                  state.isPrimary ? "text-zinc-200" : "text-zinc-500",
                )}
              >
                {state.pct}%
              </span>
            </div>
            <div
              className="h-3.5 w-full overflow-hidden rounded-full bg-white/[0.1] ring-1 ring-inset ring-white/[0.06]"
              aria-hidden
            >
              <div
                className={cn(
                  "h-full rounded-full transition-[width] duration-300",
                  accent.bar,
                  !state.isPrimary && "opacity-75",
                )}
                style={{ width: `${Math.min(100, state.pct)}%` }}
              />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

function PipelineStrip({
  steps,
}: {
  steps: ReturnType<typeof buildLiveExplainSummary>["pipeline"]
}) {
  return (
    <div className="flex flex-wrap items-stretch gap-1" aria-label="How the read was formed">
      {steps.map((step, i) => (
        <div key={step.id} className="flex min-w-0 items-stretch gap-1">
          <div
            className={cn(
              "min-w-[5.5rem] flex-1 rounded-lg border px-2 py-1.5",
              step.active
                ? "border-white/10 bg-white/[0.05]"
                : "border-white/[0.05] bg-white/[0.02] text-zinc-500",
            )}
          >
            <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-zinc-500">
              {step.label}
            </p>
            <p className="mt-0.5 truncate text-[11px] font-medium text-zinc-100">{step.detail}</p>
            {step.deltaPct != null && step.deltaPct !== 0 ? (
              <p
                className={cn(
                  "mt-0.5 font-mono text-[9px] tabular-nums",
                  step.deltaPct > 0 ? "text-teal-300/90" : "text-amber-300/90",
                )}
              >
                {step.deltaPct > 0 ? "+" : ""}
                {step.deltaPct}%
              </p>
            ) : null}
          </div>
          {i < steps.length - 1 ? (
            <ChevronRight className="mt-2 size-3 shrink-0 text-zinc-600" aria-hidden />
          ) : null}
        </div>
      ))}
    </div>
  )
}

export const LiveExplainPanel = memo(function LiveExplainPanel({
  snapshot,
  open,
  onToggle,
  roomName,
  multiRoom,
}: {
  snapshot: LiveInferenceSnapshot
  open: boolean
  onToggle: () => void
  roomName?: string | null
  multiRoom?: boolean
}) {
  const reduceMotion = useReducedMotion()
  const explain = useMemo(() => buildLiveExplainSummary(snapshot), [snapshot])

  const memoryHint =
    explain.memoryExamples > 0 ? `${explain.memoryExamples} saved` : null

  const rationaleLines = [...explain.rationalePreview, ...explain.rationaleMore].slice(0, 2)

  return (
    <div className="pointer-events-auto w-full">
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          roomosUi.liveOverlayGlassTranslucent,
          "flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left transition-colors hover:bg-zinc-950/88 sm:px-4",
          roomosUi.focusRingDark,
        )}
        aria-expanded={open}
        aria-controls="live-explain-panel"
      >
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-semibold tracking-tight text-zinc-50">
            Why · {explain.primaryLabel} · {explain.shownPct}%
          </p>
          <p className="mt-0.5 truncate text-[11px] text-zinc-500">
            {open ? "Tap to collapse" : explain.verdict}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {memoryHint ? (
            <span className="hidden items-center gap-1 rounded-full border border-violet-400/20 bg-violet-950/40 px-2 py-0.5 text-[9px] font-medium text-violet-100 sm:inline-flex">
              <Brain className="size-3" aria-hidden />
              {memoryHint}
            </span>
          ) : null}
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-[8px] font-bold uppercase tracking-wider",
              TIER_CHIP[explain.confidenceTier],
            )}
          >
            {explain.confidenceTier}
          </span>
          <ChevronDown
            className={cn(
              "size-4 shrink-0 text-zinc-500 transition-transform duration-200",
              open && "rotate-180",
            )}
            aria-hidden
          />
        </div>
      </button>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id="live-explain-panel"
            key="explain-panel"
            initial={reduceMotion ? false : { opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={reduceMotion ? undefined : { opacity: 0, height: 0 }}
            transition={
              reduceMotion
                ? { duration: 0.12 }
                : { duration: 0.24, ease: [0.22, 1, 0.36, 1] }
            }
            className="overflow-hidden"
          >
            <div
              className={cn(
                roomosUi.liveOverlayGlassTranslucent,
                "mt-1 border-t border-white/[0.08] px-3 py-3 sm:px-3.5",
              )}
            >
              {multiRoom && roomName ? (
                <p className="mb-2 text-[9px] font-medium uppercase tracking-[0.14em] text-zinc-600">
                  {roomName}
                  {explain.roomId ? (
                    <span className="font-mono text-zinc-700"> · #{explain.sequence}</span>
                  ) : null}
                </p>
              ) : null}

              <div className="grid gap-3 lg:grid-cols-[minmax(0,10.5rem)_1fr] lg:gap-5">
                <section aria-labelledby="live-explain-breakdown">
                  <h4
                    id="live-explain-breakdown"
                    className="mb-1.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-zinc-500"
                  >
                    Confidence
                  </h4>
                  <CompactStateBars states={explain.topStates} />
                </section>

                <section aria-labelledby="live-explain-why" className="min-w-0 space-y-2">
                  <div>
                    <h4
                      id="live-explain-why"
                      className="mb-1 text-[9px] font-semibold uppercase tracking-[0.14em] text-zinc-500"
                    >
                      Why this read
                    </h4>
                    {explain.hasRationale ? (
                      <ul className="space-y-1">
                        {rationaleLines.map((line, i) => (
                          <li
                            key={`${i}-${line.slice(0, 20)}`}
                            className="flex gap-1.5 text-[11px] leading-snug text-zinc-300"
                          >
                            <span
                              className="mt-1.5 size-1 shrink-0 rounded-full bg-teal-400/60"
                              aria-hidden
                            />
                            <span className="line-clamp-2">{line}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="line-clamp-2 text-[11px] leading-snug text-zinc-400">
                        {explain.verdict}
                      </p>
                    )}
                    {explain.uncertain && explain.runnerUp ? (
                      <p className="mt-1.5 text-[10px] text-amber-200/90">
                        Close: {explain.runnerUp.label} {explain.runnerUp.pct}%
                      </p>
                    ) : null}
                  </div>
                  <PipelineStrip steps={explain.pipeline} />
                </section>
              </div>

              <div className="mt-3 border-t border-white/[0.06] pt-3">
                <LiveQuickCorrection snapshot={snapshot} compact embedded dense />
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
})
