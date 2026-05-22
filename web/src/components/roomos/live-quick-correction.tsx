"use client"

import { useCallback, useEffect, useState } from "react"
import { Brain, CheckCircle2, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import {
  fetchFeedbackStatus,
  submitLiveFeedback,
  type FeedbackResponse,
  type FeedbackStatus,
} from "@/lib/roomos/api-client"
import { ROOM_STATE_ACCENT, ROOM_STATE_LABEL } from "@/lib/roomos/state-meta"
import {
  ROOM_STATE_ORDER,
  type LiveInferenceSnapshot,
  type RoomStateDistribution,
  type RoomStateId,
} from "@/types/roomos"

/**
 * One-tap correction — shows honest learning scope and probability preview from API.
 */
export function LiveQuickCorrection({
  snapshot,
  disabled = false,
  disabledReason = "Corrections unavailable in demo replay.",
}: {
  snapshot: LiveInferenceSnapshot
  disabled?: boolean
  disabledReason?: string
}) {
  const [pending, setPending] = useState<RoomStateId | null>(null)
  const [lastSaved, setLastSaved] = useState<RoomStateId | null>(null)
  const [lastResult, setLastResult] = useState<FeedbackResponse | null>(null)
  const [memoryStatus, setMemoryStatus] = useState<FeedbackStatus | null>(null)

  const primary = snapshot.primaryState
  const alternatives = ROOM_STATE_ORDER.filter((s) => s !== primary)

  const refreshStatus = useCallback(async () => {
    try {
      const st = await fetchFeedbackStatus()
      setMemoryStatus(st)
    } catch {
      setMemoryStatus(null)
    }
  }, [])

  useEffect(() => {
    void refreshStatus()
  }, [refreshStatus, lastResult?.memoryExamples])

  async function correct(to: RoomStateId) {
    if (disabled || pending) return
    setPending(to)
    setLastResult(null)
    try {
      const result = await submitLiveFeedback({ correctedLabel: to, notes: "" })
      setLastSaved(to)
      setLastResult(result)
      void refreshStatus()

      const preview = result.probabilityPreview
      const applied = preview?.appliedAfterSave
      toast.success("Saved to room memory", {
        description: applied
          ? `${ROOM_STATE_LABEL[to]} boosted on similar bursts (not a full retrain).`
          : `${result.memoryExamples} examples stored — nudges apply when the next burst looks similar.`,
        duration: 6000,
      })
    } catch (err) {
      toast.error("Could not save correction", {
        description: err instanceof Error ? err.message : "Check that the API is running.",
      })
    } finally {
      setPending(null)
    }
  }

  const memoryCount = memoryStatus?.memoryExamples ?? lastResult?.memoryExamples ?? 0

  return (
    <aside
      className={cn(roomosUi.liveOverlayGlassTranslucent, "pointer-events-auto p-4 sm:p-5")}
      aria-labelledby="roomos-quick-correct"
    >
      <div className="flex items-start justify-between gap-2">
        <h3
          id="roomos-quick-correct"
          className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-zinc-400"
        >
          Teach the room
        </h3>
        <span
          className="inline-flex items-center gap-1 rounded-full border border-violet-400/25 bg-violet-950/40 px-2 py-0.5 text-[10px] font-semibold text-violet-100"
          title="Local similarity memory — not XGBoost retraining"
        >
          <Brain className="size-3" aria-hidden />
          {memoryCount} in memory
        </span>
      </div>

      <p className="mt-1.5 text-[12px] leading-relaxed text-zinc-300">
        Model says{" "}
        <span className="font-semibold text-zinc-100">{ROOM_STATE_LABEL[primary]}</span>. Tap the
        real activity — saved locally with burst frames and features.
      </p>

      <p className="mt-2 text-[10px] leading-relaxed text-zinc-500">
        Adjusts <span className="text-zinc-400">future similar bursts</span> via memory — does{" "}
        <span className="text-zinc-400">not</span> retrain the classifier weights.
      </p>

      {disabled ? (
        <p className="mt-2 rounded-lg border border-amber-400/25 bg-amber-950/35 px-2.5 py-1.5 text-[11px] text-amber-100/95">
          {disabledReason}
        </p>
      ) : null}

      {snapshot.personalization?.applied ? (
        <p className="mt-2 rounded-lg border border-violet-400/20 bg-violet-950/30 px-2.5 py-1.5 text-[11px] text-violet-100/95">
          Memory is shaping this read now
          {typeof snapshot.personalization.matches === "number" &&
          snapshot.personalization.matches > 0
            ? ` · ${snapshot.personalization.matches} match${snapshot.personalization.matches === 1 ? "" : "es"}`
            : ""}
          {typeof snapshot.personalization.nearestSimilarity === "number" &&
          snapshot.personalization.nearestSimilarity > 0
            ? ` · sim ${(snapshot.personalization.nearestSimilarity * 100).toFixed(0)}%`
            : ""}
        </p>
      ) : memoryCount > 0 ? (
        <p className="mt-2 text-[10px] text-zinc-500">
          Memory loaded — waiting for a burst similar to a past correction.
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Correct activity">
        {alternatives.map((state) => {
          const accent = ROOM_STATE_ACCENT[state]
          const isPending = pending === state
          const isSaved = lastSaved === state
          return (
            <button
              key={state}
              type="button"
              disabled={disabled || (pending !== null && !isPending)}
              onClick={() => void correct(state)}
              className={cn(
                "inline-flex min-h-10 items-center justify-center gap-1.5 rounded-xl border px-3.5 py-2 text-[12px] font-semibold transition",
                "focus:outline-none focus:ring-2 focus:ring-teal-400/40",
                isSaved
                  ? "border-teal-400/35 bg-teal-500/20 text-teal-50"
                  : "border-white/[0.1] bg-white/[0.06] text-zinc-100 hover:bg-white/[0.12]",
                isPending && "opacity-80",
              )}
            >
              {isPending ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : isSaved ? (
                <CheckCircle2 className="size-3.5 text-teal-200" aria-hidden />
              ) : (
                <span className={cn("size-2 rounded-full", accent.bar)} aria-hidden />
              )}
              {ROOM_STATE_LABEL[state]}
            </button>
          )
        })}
      </div>

      {lastResult ? <LearningSummary result={lastResult} /> : null}
    </aside>
  )
}

function LearningSummary({ result }: { result: FeedbackResponse }) {
  const preview = result.probabilityPreview
  const corrected = result.correctedLabel as RoomStateId

  return (
    <div
      className="mt-4 space-y-3 rounded-xl border border-teal-400/20 bg-teal-950/25 p-3"
      role="status"
      aria-live="polite"
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-teal-200/90">
        What we learned
      </p>
      <ul className="space-y-1.5 text-[11px] leading-relaxed text-zinc-300">
        <li>
          <span className="text-zinc-500">Saved:</span> {result.screenshotCount} frames + feature
          fingerprint → disk
        </li>
        <li>
          <span className="text-zinc-500">Memory:</span> {result.memoryExamples} correction
          {result.memoryExamples === 1 ? "" : "s"} total
        </li>
        <li>
          <span className="text-zinc-500">Next similar bursts:</span> bias toward{" "}
          {ROOM_STATE_LABEL[corrected]}
        </li>
        <li className="text-zinc-500">{result.effects.notIncluded}</li>
      </ul>

      {preview?.before && preview.after ? (
        <ProbabilityShift
          before={preview.before}
          after={preview.after}
          highlight={corrected}
          applied={preview.appliedAfterSave}
        />
      ) : null}

      <p className="font-mono text-[9px] leading-snug text-zinc-600">
        id {result.id.slice(0, 8)}… · logged to feedback_events.jsonl
      </p>
    </div>
  )
}

function ProbabilityShift({
  before,
  after,
  highlight,
  applied,
}: {
  before: RoomStateDistribution
  after: RoomStateDistribution
  highlight: RoomStateId
  applied?: boolean
}) {
  return (
    <div>
      <p className="text-[10px] text-zinc-500">
        Same burst — model vs after memory{applied ? "" : " (waiting for similarity match)"}:
      </p>
      <div className="mt-2 space-y-1.5">
        {ROOM_STATE_ORDER.map((id) => {
          const b = Math.round((before[id] ?? 0) * 100)
          const a = Math.round((after[id] ?? 0) * 100)
          const delta = a - b
          const isHighlight = id === highlight
          return (
            <div key={id} className="flex items-center gap-2 text-[10px]">
              <span
                className={cn(
                  "w-16 truncate",
                  isHighlight ? "font-semibold text-teal-100" : "text-zinc-500",
                )}
              >
                {ROOM_STATE_LABEL[id]}
              </span>
              <span className="w-8 tabular-nums text-zinc-500">{b}%</span>
              <span className="text-zinc-600">→</span>
              <span
                className={cn(
                  "w-8 tabular-nums",
                  isHighlight ? "font-semibold text-teal-100" : "text-zinc-400",
                )}
              >
                {a}%
              </span>
              {delta !== 0 ? (
                <span
                  className={cn(
                    "tabular-nums",
                    delta > 0 ? "text-emerald-300/90" : "text-rose-300/80",
                  )}
                >
                  {delta > 0 ? "+" : ""}
                  {delta}
                </span>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
