"use client"

import { memo, useMemo, useState } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import {
  ChevronDown,
  ChevronRight,
  GitBranch,
  HelpCircle,
  Sparkles,
} from "lucide-react"

import { LiveDistributionList } from "@/components/roomos/live-distribution-list"
import { LiveQuickCorrection } from "@/components/roomos/live-quick-correction"
import { buildLiveExplainSummary } from "@/lib/roomos/live-explain-utils"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type { LiveInferenceSnapshot } from "@/types/roomos"

const TIER_CHIP = {
  high: "border-emerald-400/35 bg-emerald-950/40 text-emerald-100",
  medium: "border-amber-400/35 bg-amber-950/35 text-amber-100",
  low: "border-rose-400/35 bg-rose-950/40 text-rose-100",
} as const

function PipelineStep({
  step,
  isLast,
}: {
  step: ReturnType<typeof buildLiveExplainSummary>["pipeline"][number]
  isLast: boolean
}) {
  return (
    <div className="flex min-w-0 flex-1 items-stretch gap-1">
      <div
        className={cn(
          "min-w-0 flex-1 rounded-lg border px-2 py-1.5 sm:px-2.5",
          step.active
            ? "border-white/14 bg-white/[0.07]"
            : "border-white/[0.06] bg-white/[0.02] opacity-75",
        )}
      >
        <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
          {step.label}
        </p>
        <p className="mt-0.5 truncate text-[11px] font-medium text-zinc-100">{step.detail}</p>
        {step.deltaPct != null && step.deltaPct !== 0 ? (
          <p
            className={cn(
              "mt-0.5 font-mono text-[10px] tabular-nums",
              step.deltaPct > 0 ? "text-teal-300/90" : "text-amber-300/90",
            )}
          >
            {step.deltaPct > 0 ? "+" : ""}
            {step.deltaPct}% vs burst
          </p>
        ) : null}
      </div>
      {!isLast ? (
        <ChevronRight className="mt-3 size-3 shrink-0 text-zinc-600" aria-hidden />
      ) : null}
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
  const [showAllStates, setShowAllStates] = useState(false)
  const [showCorrect, setShowCorrect] = useState(false)

  const explain = useMemo(() => buildLiveExplainSummary(snapshot), [snapshot])

  const chipCount = [
    explain.uncertain,
    explain.memoryApplied,
    Math.abs(explain.smoothingDeltaPct) >= 2,
    explain.smoothingChangedPrimary,
  ].filter(Boolean).length

  const collapseLabel = open
    ? "Hide explanation"
    : `Why ${explain.primaryLabel} · ${explain.shownPct}%`

  return (
    <div className="pointer-events-auto w-full">
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          roomosUi.liveStatusPillTranslucent,
          "mx-auto mb-1 flex w-full max-w-lg items-center justify-between gap-2 px-3 py-2 text-left sm:max-w-xl",
          roomosUi.focusRingDark,
        )}
        aria-expanded={open}
        aria-controls="live-explain-panel"
      >
        <span className="flex min-w-0 items-center gap-2">
          <HelpCircle className="size-3.5 shrink-0 text-teal-300/90" aria-hidden />
          <span className="truncate text-[11px] font-semibold text-zinc-200">{collapseLabel}</span>
          {!open && chipCount > 0 ? (
            <span className="shrink-0 rounded-full bg-teal-500/20 px-1.5 py-px text-[9px] font-bold text-teal-100">
              {chipCount}
            </span>
          ) : null}
        </span>
        <ChevronDown
          className={cn("size-3.5 shrink-0 text-zinc-500 transition-transform", open && "rotate-180")}
          aria-hidden
        />
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
                : { duration: 0.28, ease: [0.22, 1, 0.36, 1] }
            }
            className="overflow-hidden"
          >
            <div
              className={cn(
                roomosUi.liveOverlayGlassTranslucent,
                "mb-1 max-h-[min(48vh,400px)] overflow-hidden border-t border-white/10",
              )}
            >
              <div className="overflow-y-auto overscroll-contain p-3 sm:p-3.5">
                {/* Verdict + chips */}
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="min-w-0 flex-1 text-[12.5px] leading-snug text-zinc-200">
                    {explain.verdict}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    <span
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider",
                        TIER_CHIP[explain.confidenceTier],
                      )}
                    >
                      {explain.confidenceTier}
                    </span>
                    {explain.memoryApplied ? (
                      <span className="rounded-full border border-violet-400/30 bg-violet-950/50 px-2 py-0.5 text-[9px] font-semibold text-violet-100">
                        Memory
                      </span>
                    ) : null}
                    {Math.abs(explain.smoothingDeltaPct) >= 2 ? (
                      <span className="rounded-full border border-sky-400/30 bg-sky-950/45 px-2 py-0.5 text-[9px] font-semibold text-sky-100">
                        Smoothed
                      </span>
                    ) : null}
                    {explain.smoothingChangedPrimary ? (
                      <span className="rounded-full border border-amber-400/30 bg-amber-950/45 px-2 py-0.5 text-[9px] font-semibold text-amber-100">
                        Label shifted
                      </span>
                    ) : null}
                  </div>
                </div>

                {multiRoom && roomName ? (
                  <p className="mt-2 text-[10px] text-zinc-500">
                    Read for <span className="font-medium text-zinc-400">{roomName}</span>
                    {explain.roomId ? (
                      <span className="font-mono text-zinc-600"> · burst #{explain.sequence}</span>
                    ) : null}
                  </p>
                ) : null}

                {/* Pipeline */}
                <div className="mt-3">
                  <p className="mb-1.5 flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
                    <GitBranch className="size-3" aria-hidden />
                    How this read was formed
                  </p>
                  <div className="flex items-stretch gap-0.5 sm:gap-1">
                    {explain.pipeline.map((step, i) => (
                      <PipelineStep
                        key={step.id}
                        step={step}
                        isLast={i === explain.pipeline.length - 1}
                      />
                    ))}
                  </div>
                  <p className="mt-2 text-[10px] leading-relaxed text-zinc-600">
                    Burst read is after room-memory blend, before temporal smoothing. Nothing leaves
                    this device.
                  </p>
                </div>

                {/* Top states compact */}
                <div className="mt-3 border-t border-white/[0.06] pt-3">
                  <p className="mb-2 flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
                    <Sparkles className="size-3" aria-hidden />
                    Top states this burst
                  </p>
                  <div className="space-y-1">
                    {explain.topStates.map((row) => (
                      <div key={row.id} className="flex items-center gap-2">
                        <span
                          className={cn(
                            "w-24 shrink-0 truncate text-[11px]",
                            row.isPrimary ? "font-semibold text-zinc-50" : "text-zinc-400",
                          )}
                        >
                          {row.label}
                        </span>
                        <div className="relative h-1 flex-1 overflow-hidden rounded-full bg-white/[0.08]">
                          <motion.div
                            className={cn(
                              "absolute inset-y-0 left-0 rounded-full",
                              row.isPrimary ? "bg-teal-400/75" : "bg-white/25",
                            )}
                            initial={false}
                            animate={{ width: `${row.pct}%` }}
                            transition={
                              reduceMotion
                                ? { duration: 0.12 }
                                : { type: "spring", stiffness: 220, damping: 30 }
                            }
                          />
                        </div>
                        <span className="w-9 shrink-0 text-right font-mono text-[10px] tabular-nums text-zinc-400">
                          {row.pct}%
                        </span>
                      </div>
                    ))}
                  </div>

                  <button
                    type="button"
                    onClick={() => setShowAllStates((v) => !v)}
                    className={cn(
                      "mt-2 text-[10px] font-semibold text-teal-300/90 underline-offset-2 hover:underline",
                      roomosUi.focusRingDark,
                    )}
                  >
                    {showAllStates ? "Hide full distribution" : "All states & burst comparison"}
                  </button>

                  {showAllStates ? (
                    <div className="mt-3 space-y-4 border-t border-white/[0.06] pt-3">
                      {snapshot.modelDistribution ? (
                        <>
                          <div>
                            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-500">
                              Burst read (pre-smooth)
                            </p>
                            <LiveDistributionList
                              distribution={snapshot.modelDistribution}
                              primary={snapshot.primaryState}
                              finePercent
                            />
                          </div>
                          <div>
                            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-500">
                              Shown (smoothed)
                            </p>
                            <LiveDistributionList
                              distribution={snapshot.distribution}
                              primary={snapshot.primaryState}
                              finePercent
                            />
                          </div>
                        </>
                      ) : (
                        <LiveDistributionList
                          distribution={snapshot.distribution}
                          primary={snapshot.primaryState}
                          finePercent
                        />
                      )}
                    </div>
                  ) : null}
                </div>

                {/* Correction disclosure */}
                <div className="mt-3 border-t border-white/[0.06] pt-2">
                  <button
                    type="button"
                    onClick={() => setShowCorrect((v) => !v)}
                    className={cn(
                      "flex w-full items-center justify-between py-1.5 text-[11px] font-semibold text-zinc-300",
                      roomosUi.focusRingDark,
                    )}
                  >
                    Mark right or wrong
                    <ChevronDown
                      className={cn("size-3.5 transition-transform", showCorrect && "rotate-180")}
                    />
                  </button>
                  {showCorrect ? (
                    <div className="pt-2">
                      <LiveQuickCorrection snapshot={snapshot} compact />
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
})
