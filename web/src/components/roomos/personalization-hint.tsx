"use client"

import { Brain } from "lucide-react"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { ROOM_STATE_LABEL } from "@/lib/roomos/state-meta"
import type { LiveInferenceSnapshot, RoomStateId } from "@/types/roomos"

/** Shown when model distribution differs from displayed (memory-adjusted) distribution. */
export function PersonalizationHint({ snapshot }: { snapshot: LiveInferenceSnapshot }) {
  const p = snapshot.personalization
  const model = snapshot.modelDistribution
  const shown = snapshot.distribution
  if (!model || !p?.applied) return null

  const primary = snapshot.primaryState
  const modelPct = Math.round((model[primary] ?? 0) * 100)
  const shownPct = Math.round((shown[primary] ?? 0) * 100)
  const delta = shownPct - modelPct
  if (Math.abs(delta) < 2 && (p.matches ?? 0) === 0) return null

  const boosted = p.boostedLabel as RoomStateId | undefined

  return (
    <div
      className={cn(
        roomosUi.liveOverlayGlassTranslucent,
        "flex gap-2 border-violet-400/20 bg-violet-950/30 px-3 py-2.5",
      )}
      role="note"
    >
      <Brain className="mt-0.5 size-3.5 shrink-0 text-violet-300" aria-hidden />
      <p className="text-[11px] leading-snug text-violet-100/95">
        <span className="font-semibold text-violet-50">Room memory</span> nudged this read: raw model{" "}
        {ROOM_STATE_LABEL[primary]} {modelPct}% → shown {shownPct}%
        {boosted && boosted !== primary
          ? ` (memory favors ${ROOM_STATE_LABEL[boosted]})`
          : null}
        . Not a retrain.
      </p>
    </div>
  )
}
