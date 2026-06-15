"use client"

import { memo, useState } from "react"
import { ChevronDown, ChevronUp, Layers } from "lucide-react"

import { LiveDistributionList } from "@/components/roomos/live-distribution-list"
import { LiveQuickCorrection } from "@/components/roomos/live-quick-correction"
import { LiveRationaleList } from "@/components/roomos/live-rationale-list"
import { PersonalizationHint } from "@/components/roomos/personalization-hint"
import { cn } from "@/lib/utils"
import { isUncertainRead } from "@/lib/roomos/live-confidence-utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type { LiveInferenceSnapshot } from "@/types/roomos"

type InspectTab = "why" | "states" | "memory" | "correct"

const TAB_LABEL: Record<InspectTab, string> = {
  why: "Why",
  states: "States",
  memory: "Memory",
  correct: "Correct",
}

export const LiveInspectDrawer = memo(function LiveInspectDrawer({
  snapshot,
  open,
  onToggle,
}: {
  snapshot: LiveInferenceSnapshot
  open: boolean
  onToggle: () => void
}) {
  const [tab, setTab] = useState<InspectTab>("why")
  const liveDistribution = snapshot.modelDistribution ?? snapshot.distribution
  const uncertain = isUncertainRead(liveDistribution, snapshot.primaryState)
  const memoryActive = Boolean(snapshot.personalization?.applied)
  const hasRationale = snapshot.rationale.length > 0
  const badgeCount = [uncertain, memoryActive, hasRationale].filter(Boolean).length

  return (
    <div className="pointer-events-auto w-full">
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          roomosUi.liveStatusPillTranslucent,
          "mx-auto mb-1.5 flex items-center gap-2 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-300",
          roomosUi.focusRingDark,
        )}
        aria-expanded={open}
        aria-controls="live-inspect-panel"
      >
        <Layers className="size-3" aria-hidden />
        {open ? "Hide details" : "Inspect read"}
        {!open && badgeCount > 0 ? (
          <span className="rounded-full bg-teal-500/25 px-1.5 py-px text-[9px] font-bold text-teal-100">
            {badgeCount}
          </span>
        ) : null}
        {open ? (
          <ChevronDown className="size-3" aria-hidden />
        ) : (
          <ChevronUp className="size-3" aria-hidden />
        )}
      </button>

      {open ? (
        <div
          id="live-inspect-panel"
          className={cn(
            roomosUi.liveOverlayGlassTranslucent,
            "max-h-[min(52vh,440px)] overflow-hidden border-t border-white/10 bg-zinc-950/82",
          )}
        >
          <div className="flex gap-1 overflow-x-auto border-b border-white/[0.08] px-2 py-2 scrollbar-none">
            {(Object.keys(TAB_LABEL) as InspectTab[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={cn(
                  "shrink-0 rounded-full px-3 py-1 text-[11px] font-semibold transition-colors",
                  roomosUi.focusRingDark,
                  tab === key
                    ? "bg-white/12 text-zinc-50"
                    : "text-zinc-500 hover:text-zinc-300",
                )}
                aria-selected={tab === key}
                role="tab"
              >
                {TAB_LABEL[key]}
              </button>
            ))}
          </div>

          <div
            className="overflow-y-auto overscroll-contain p-3 sm:p-4"
            role="tabpanel"
          >
            {tab === "why" ? (
              <div className="space-y-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500">
                  Model rationale
                </p>
                <LiveRationaleList rationale={snapshot.rationale} />
              </div>
            ) : null}

            {tab === "states" ? (
              <div className="space-y-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500">
                  All states · this burst
                </p>
                <LiveDistributionList
                  distribution={liveDistribution}
                  primary={snapshot.primaryState}
                  showModelHint={Boolean(snapshot.modelDistribution)}
                />
                {snapshot.modelDistribution ? (
                  <div className="mt-4 border-t border-white/[0.08] pt-4">
                    <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500">
                      Shown (smoothed)
                    </p>
                    <LiveDistributionList
                      distribution={snapshot.distribution}
                      primary={snapshot.primaryState}
                    />
                  </div>
                ) : null}
              </div>
            ) : null}

            {tab === "memory" ? (
              <div className="space-y-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500">
                  Room memory
                </p>
                {memoryActive ? (
                  <>
                    <PersonalizationHint snapshot={snapshot} />
                    <dl className="grid grid-cols-2 gap-2 text-[11px] text-zinc-400">
                      <div className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-2.5 py-2">
                        <dt className="text-zinc-600">Examples</dt>
                        <dd className="mt-0.5 font-mono text-zinc-200">
                          {snapshot.personalization?.memoryExamples ??
                            snapshot.personalization?.examples ??
                            0}
                        </dd>
                      </div>
                      <div className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-2.5 py-2">
                        <dt className="text-zinc-600">Influence</dt>
                        <dd className="mt-0.5 font-mono text-zinc-200">
                          {Math.round((snapshot.personalization?.influence ?? 0) * 100)}%
                        </dd>
                      </div>
                    </dl>
                  </>
                ) : (
                  <p className="text-[12px] leading-relaxed text-zinc-500">
                    No room-memory blend on this burst — the read is straight from the local
                    classifier.
                  </p>
                )}
              </div>
            ) : null}

            {tab === "correct" ? (
              <LiveQuickCorrection snapshot={snapshot} compact />
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
})
