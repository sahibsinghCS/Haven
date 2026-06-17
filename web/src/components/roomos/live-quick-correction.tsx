"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { AlertTriangle, Brain, CheckCircle2, Loader2, ThumbsDown, ThumbsUp } from "lucide-react"
import { toast } from "sonner"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { FeedbackEvidenceStrip } from "@/components/roomos/feedback-evidence-strip"
import {
  fetchFeedbackStatus,
  submitLiveFeedback,
  type FeedbackResponse,
  type FeedbackStatus,
} from "@/lib/roomos/api-client"
import { roomStateAccent, roomStateLabel } from "@/lib/roomos/state-meta"
import {
  ROOM_STATE_ORDER,
  type LiveInferenceSnapshot,
  type RoomStateDistribution,
  type RoomStateId,
} from "@/types/roomos"

type PendingConfirm = {
  label: RoomStateId
  mode: "confirm" | "correct"
}

/** Memory/retrain badge. no need to hammer the API on every snapshot tick. */
const FEEDBACK_STATUS_POLL_MS = 10_000

/**
 * Right / wrong feedback — each tap trains room memory and counts toward auto-retrain.
 */
export function LiveQuickCorrection({
  snapshot,
  disabled = false,
  disabledReason = "Feedback unavailable.",
  compact = false,
}: {
  snapshot: LiveInferenceSnapshot
  disabled?: boolean
  disabledReason?: string
  compact?: boolean
}) {
  const [pending, setPending] = useState<RoomStateId | "confirm" | null>(null)
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null)
  const [lastSaved, setLastSaved] = useState<RoomStateId | "confirm" | null>(null)
  const [lastResult, setLastResult] = useState<FeedbackResponse | null>(null)
  const [memoryStatus, setMemoryStatus] = useState<FeedbackStatus | null>(null)

  const primary = snapshot.primaryState
  const distKeys = Object.keys(snapshot.distribution ?? {})
  const stateOrder =
    distKeys.length > 0 ? distKeys : [...ROOM_STATE_ORDER]
  const alternatives = stateOrder.filter((s) => s !== primary && s !== "unknown")
  const primaryAccent = roomStateAccent(primary)
  const evidence = memoryStatus?.evidence
  const frameCount = evidence?.available ? (evidence.frameCount ?? 0) : 0
  const evidenceCacheKey = `${snapshot.sequence}-${evidence?.capturedAt ?? ""}`

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
    const id = window.setInterval(() => {
      if (document.visibilityState === "hidden") return
      void refreshStatus()
    }, FEEDBACK_STATUS_POLL_MS)
    return () => window.clearInterval(id)
  }, [refreshStatus])

  useEffect(() => {
    if (lastResult == null) return
    void refreshStatus()
  }, [lastResult, refreshStatus])

  async function submit(label: RoomStateId, mode: "confirm" | "correct") {
    if (disabled || pending) return
    setPending(mode === "confirm" ? "confirm" : label)
    setLastResult(null)
    try {
      const result = await submitLiveFeedback({
        correctedLabel: label,
        notes: mode === "confirm" ? "confirmed" : "",
      })
      setLastSaved(mode === "confirm" ? "confirm" : label)
      setLastResult(result)
      setPendingConfirm(null)
      void refreshStatus()

      const minN = memoryStatus?.autoRetrain?.minCorrections ?? 3
      const progress = memoryStatus?.autoRetrain?.correctionsSinceLastRun
      toast.success(mode === "confirm" ? "Marked as right" : "Marked as wrong", {
        description: result.retrainsModel
          ? "Saved snapshot. model retraining in background."
          : `Saved locally. ${result.memoryExamples} examples in memory.`,
        duration: 5000,
      })
    } catch (err) {
      toast.error("Could not save feedback", {
        description: err instanceof Error ? err.message : "Check that the API is running.",
      })
    } finally {
      setPending(null)
    }
  }

  function requestSubmit(label: RoomStateId, mode: "confirm" | "correct") {
    if (disabled || pending) return
    const mismatch =
      mode === "correct" &&
      label !== primary &&
      (evidence?.primaryState == null || evidence.primaryState === primary)
    if (mismatch) {
      setPendingConfirm({ label, mode })
      return
    }
    void submit(label, mode)
  }

  const memoryCount = memoryStatus?.memoryExamples ?? lastResult?.memoryExamples ?? 0
  const autoRt = memoryStatus?.autoRetrain
  const retrainTaps = autoRt?.correctionsSinceLastRun ?? 0
  const retrainNeed = autoRt?.minCorrections ?? 3
  const storedTotal = autoRt?.storedCorrections ?? memoryCount
  const retrainProgress =
    autoRt?.enabled
      ? `${retrainTaps}/${retrainNeed} taps · ${storedTotal} in model memory`
      : null
  const lastRetrain = autoRt?.lastResult as { ok?: boolean; error?: string } | null | undefined

  const confirmBusy = pending === "confirm"
  const confirmSaved = lastSaved === "confirm"

  return (
    <aside
      className={cn(
        roomosUi.liveOverlayGlassTranslucent,
        "pointer-events-auto",
        compact ? "p-3" : "p-4 sm:p-5",
      )}
      aria-labelledby="roomos-quick-correct"
    >
      <div className="flex items-start justify-between gap-2">
        <h3
          id="roomos-quick-correct"
          className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-zinc-400"
        >
          Right or wrong? (now)
        </h3>
        <span
          className="inline-flex items-center gap-1 rounded-full border border-violet-400/25 bg-violet-950/40 px-2 py-0.5 text-[10px] font-semibold text-violet-100"
          title="Each tap improves the model automatically"
        >
          <Brain className="size-3" aria-hidden />
          {retrainProgress ?? `${memoryCount} saved`}
        </span>
      </div>

      {autoRt?.enabled && lastRetrain && lastRetrain.ok === false ? (
        <p className="mt-1 text-[10px] text-amber-300/90">
 Retrain pending. run{" "}
          <code className="font-mono text-[10px]">npm run train:reinforce</code> once, then restart dev.
        </p>
      ) : null}
      {autoRt?.running ? (
        <p className="mt-1 text-[10px] text-teal-300/90">Retraining model now…</p>
      ) : null}

      {!compact ? (
        <p className="mt-1.5 text-[12px] leading-relaxed text-zinc-300">
          Each tap <strong className="text-zinc-100">screenshots your video now</strong> and trains
          from that frame. For past switches use{" "}
          <Link href="/review" className="font-semibold text-teal-300 underline-offset-2 hover:underline">
            Review
          </Link>{" "}
          (burst history).
        </p>
      ) : null}

      {!compact && frameCount > 0 ? (
        <div className="mt-2.5">
          <p className="mb-1 text-[10px] font-medium uppercase tracking-[0.1em] text-zinc-500">
            Live video frame (saved on tap)
          </p>
          <FeedbackEvidenceStrip
            frameCount={1}
            cacheKey={evidenceCacheKey}
            frameClassName="h-24 w-40"
          />
        </div>
      ) : null}

      {pendingConfirm ? (
        <MismatchConfirm
          primary={primary}
          target={pendingConfirm.label}
          busy={pending !== null}
          onCancel={() => setPendingConfirm(null)}
          onConfirm={() => void submit(pendingConfirm.label, pendingConfirm.mode)}
        />
      ) : null}

      {!compact && autoRt?.enabled ? (
        <p className="mt-2 text-[10px] leading-relaxed text-zinc-500">
          After {autoRt.minCorrections ?? 3} right/wrong answers, XGBoost updates in the background
          and reloads live.
        </p>
      ) : null}

      {disabled ? (
        <p className="mt-2 rounded-lg border border-amber-400/25 bg-amber-950/35 px-2.5 py-1.5 text-[11px] text-amber-100/95">
          {disabledReason}
        </p>
      ) : null}

      {snapshot.personalization?.applied ? (
        <p className="mt-2 rounded-lg border border-violet-400/20 bg-violet-950/30 px-2.5 py-1.5 text-[11px] text-violet-100/95">
          Your past answers are shaping this read now
        </p>
      ) : null}

      <button
        type="button"
        disabled={disabled || (pending !== null && !confirmBusy) || Boolean(pendingConfirm)}
        onClick={() => requestSubmit(primary, "confirm")}
        className={cn(
          "mt-3 flex w-full min-h-11 items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-[13px] font-semibold transition",
          "focus:outline-none focus:ring-2 focus:ring-emerald-400/40",
          confirmSaved
            ? "border-emerald-400/40 bg-emerald-500/20 text-emerald-50"
            : "border-emerald-400/30 bg-emerald-950/40 text-emerald-50 hover:bg-emerald-950/55",
          confirmBusy && "opacity-80",
        )}
      >
        {confirmBusy ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : confirmSaved ? (
          <CheckCircle2 className="size-4" aria-hidden />
        ) : (
          <ThumbsUp className="size-4" aria-hidden />
        )}
        <span className={cn("size-3.5 shrink-0 rounded-full ring-2 ring-white/15", primaryAccent.bar)} aria-hidden />
 Yes. {roomStateLabel(primary)}
      </button>

      <p className="mt-3 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-500">
        <ThumbsDown className="size-3" aria-hidden />
        No, actually
      </p>

      <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Wrong activity">
        {alternatives.map((state) => {
          const accent = roomStateAccent(state)
          const isPending = pending === state
          const isSaved = lastSaved === state
          return (
            <button
              key={state}
              type="button"
              disabled={disabled || (pending !== null && !isPending) || Boolean(pendingConfirm)}
              onClick={() => requestSubmit(state, "correct")}
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
                <span className={cn("size-3.5 shrink-0 rounded-full ring-2 ring-white/10", accent.bar)} aria-hidden />
              )}
              {roomStateLabel(state)}
            </button>
          )
        })}
      </div>

      {lastResult && !compact ? <LearningSummary result={lastResult} /> : null}
    </aside>
  )
}

function MismatchConfirm({
  primary,
  target,
  busy,
  onCancel,
  onConfirm,
}: {
  primary: RoomStateId
  target: RoomStateId
  busy: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <div
      className="mt-3 space-y-2 rounded-xl border border-amber-400/35 bg-amber-950/45 p-3"
      role="alertdialog"
      aria-labelledby="mismatch-title"
    >
      <p id="mismatch-title" className="flex items-start gap-2 text-[12px] font-semibold text-amber-50">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
        These frames look like {roomStateLabel(primary)} now
      </p>
      <p className="text-[11px] leading-relaxed text-amber-100/90">
        Saving as <strong>{roomStateLabel(target)}</strong> teaches the model that this
        video frame means {roomStateLabel(target)}. For an earlier moment, use{" "}
        <Link href="/review" className="font-semibold text-amber-50 underline">
          Review past switches
        </Link>{" "}
        so the saved burst matches that moment.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={onCancel}
          className="rounded-lg border border-white/15 bg-white/10 px-3 py-1.5 text-[12px] font-semibold text-zinc-100 hover:bg-white/15"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onConfirm}
          className="rounded-lg border border-amber-400/40 bg-amber-500/25 px-3 py-1.5 text-[12px] font-semibold text-amber-50 hover:bg-amber-500/35"
        >
          {busy ? "Saving…" : `Save as ${roomStateLabel(target)} anyway`}
        </button>
      </div>
    </div>
  )
}

function LearningSummary({ result }: { result: FeedbackResponse }) {
  const preview = result.probabilityPreview
  const corrected = result.correctedLabel as RoomStateId
  const wasConfirm = result.confirmed ?? result.predictedLabel === result.correctedLabel

  return (
    <div
      className="mt-4 space-y-3 rounded-xl border border-teal-400/20 bg-teal-950/25 p-3"
      role="status"
      aria-live="polite"
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-teal-200/90">
        {wasConfirm ? "Reinforced" : "Corrected"}
      </p>
      <ul className="space-y-1.5 text-[11px] leading-relaxed text-zinc-300">
        <li>
          <span className="text-zinc-500">Saved:</span> {result.screenshotCount} snapshot → trains
          the model
        </li>
        <li>
          <span className="text-zinc-500">Total answers:</span> {result.memoryExamples}
        </li>
        <li>
          <span className="text-zinc-500">Label:</span> {roomStateLabel(corrected)}
          {wasConfirm ? " (you confirmed)" : ""}
        </li>
        <li className="text-zinc-500">{result.effects.notIncluded}</li>
      </ul>

      {!wasConfirm && preview?.before && preview.after ? (
        <ProbabilityShift
          before={preview.before}
          after={preview.after}
          highlight={corrected}
          applied={preview.appliedAfterSave}
        />
      ) : null}
    </div>
  )
}

function distributionStateIds(
  before: RoomStateDistribution,
  after: RoomStateDistribution,
): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const id of [...Object.keys(before), ...Object.keys(after), ...ROOM_STATE_ORDER]) {
    if (seen.has(id)) continue
    seen.add(id)
    out.push(id)
  }
  return out
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
 Same burst. before vs after memory{applied ? "" : " (similar scene needed)"}:
      </p>
      <div className="mt-2 space-y-1.5">
        {distributionStateIds(before, after).map((id) => {
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
                {roomStateLabel(id)}
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
