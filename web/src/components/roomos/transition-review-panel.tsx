"use client"

import Link from "next/link"
import { useCallback, useMemo, useState } from "react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { ArrowRight, CheckCircle2, Loader2, RefreshCw, ThumbsUp, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { CorrectionOutcomeCard } from "@/components/roomos/teaching/correction-outcome-card"
import { useMoods } from "@/hooks/use-moods"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import {
  clearAllTransitions,
  correctTransition,
  fetchTransitions,
  transitionFrameUrl,
  type FeedbackResponse,
  type StateTransitionItem,
} from "@/lib/roomos/api-client"import { roomStateLabel } from "@/lib/roomos/state-meta"
import { ROOM_STATE_ORDER, type RoomStateId } from "@/types/roomos"

function displayLabel(label: string): string {
  if (label === "unknown") return "Uncertain"
  return roomStateLabel(label)
}

function isResolvableLabel(label: string, knownIds: readonly string[]): label is RoomStateId {
  return knownIds.includes(label)
}

const cardShell =
  "rounded-[1.35rem] border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_96%,transparent)] shadow-[var(--haven-shadow-card)] ring-1 ring-[color:var(--haven-edge-light)]"

/** Full frame visible. matches Live preview (contain), not a center crop. */
const evidenceFrameClass =
  "h-full w-full object-contain object-center"
const evidenceShellClass =
  "flex aspect-video w-full items-center justify-center overflow-hidden rounded-xl border border-[color:var(--haven-line-strong)] bg-[color:var(--haven-canvas-mist)]"

const panelMuted = "text-[color:var(--haven-muted)]"
const panelInk = "text-[color:var(--haven-ink)]"

type ReviewTab = "pending" | "reviewed"

/**
 * Review past label switches: before → after with burst frames and right/wrong on the prediction.
 */
export function TransitionReviewPanel({
  pollMs = 4000,
  compact = false,
}: {
  pollMs?: number
  compact?: boolean
}) {
  const { data: moodsData } = useMoods()
  const [correctingId, setCorrectingId] = useState<string | null>(null)
  const [clearing, setClearing] = useState(false)
  const [tab, setTab] = useState<ReviewTab>("pending")  const [lastOutcome, setLastOutcome] = useState<FeedbackResponse | null>(null)

  const transitionsQuery = useQuery({
    queryKey: ["roomos", "transitions", compact ? "compact" : "full", tab],
    queryFn: () =>
      fetchTransitions({
        limit: compact ? 6 : 40,
        uncorrectedOnly: tab === "pending",
      }),
    staleTime: 30_000,
    refetchInterval: pollMs,
    placeholderData: keepPreviousData,
  })

  const enabled = transitionsQuery.isError
    ? false
    : (transitionsQuery.data?.enabled ?? true)
  const reason = transitionsQuery.isError
    ? transitionsQuery.error instanceof Error
      ? transitionsQuery.error.message
      : "API unavailable"
    : transitionsQuery.data?.reason
  const pending = transitionsQuery.data?.pendingReview ?? 0
  const total = transitionsQuery.data?.total ?? 0
  const loading = transitionsQuery.isLoading && !transitionsQuery.data  const items = useMemo(() => {
    const list = transitionsQuery.data?.transitions ?? []
    return tab === "reviewed" ? list.filter((t) => t.corrected) : list
  }, [transitionsQuery.data?.transitions, tab])

  const refresh = useCallback(() => {
    void transitionsQuery.refetch()
  }, [transitionsQuery])

  const correctionIds = useMemo(() => {
    const fromMoods = moodsData?.moods.map((m) => m.id) ?? []
    const merged = new Set<string>([...ROOM_STATE_ORDER, ...fromMoods])
    return [...merged]
  }, [moodsData?.moods])

  async function relabel(transition: StateTransitionItem, to: RoomStateId) {
    if (correctingId) return
    setCorrectingId(transition.id)
    try {
      const result = await correctTransition(transition.id, {
        correctedLabel: to,
        notes: `review: ${transition.toLabel} -> ${to}`,
      })
      setLastOutcome(result)
      const predicted = isResolvableLabel(transition.toLabel, correctionIds)
        ? transition.toLabel
        : null
      const confirmed = result.confirmed ?? (predicted != null && to === predicted)
      toast.success(confirmed ? "Switch marked right" : "Switch marked wrong", {
        description: result.retrainsModel
          ? "Counts toward automatic model retrain."
          : `Similar scenes will bias toward ${roomStateLabel(to)}.`,
        duration: 5000,
      })
      await refresh()
    } catch (err) {
      toast.error("Could not save relabel", {
        description: err instanceof Error ? err.message : "Check API is running.",
      })
    } finally {
      setCorrectingId(null)
    }
  }

  async function clearAll() {
    if (clearing || total === 0) return
    const label =
      tab === "pending" && pending > 0
        ? `Delete all ${pending} switch${pending === 1 ? "" : "es"} waiting for review? This cannot be undone.`
        : `Delete all ${total} saved switch${total === 1 ? "" : "es"}? This cannot be undone.`
    if (!window.confirm(label)) return
    setClearing(true)
    try {
      const result = await clearAllTransitions()
      setLastOutcome(null)
      toast.success("Switch history cleared", {
        description: `Removed ${result.removed} saved switch${result.removed === 1 ? "" : "es"} from this device.`,
      })
      await refresh()
    } catch (err) {
      toast.error("Could not clear switches", {
        description: err instanceof Error ? err.message : "Check API is running.",
      })
    } finally {
      setClearing(false)
    }
  }

  if (!enabled) {    const hint =
      reason === "transitions_disabled"
        ? "Transition logging is turned off in inference config."
        : reason === "engine_off"
          ? "Could not read saved switch history. is the Haven backend running?"
          : (reason ?? "Switch history is not available yet.")
    return (
      <div className={cn(roomosUi.prefsCallout, "p-4 text-sm", panelMuted)}>
        <p className={cn("font-medium", panelInk)}>Switch history unavailable</p>
        <p className="mt-1 text-[12px]">{hint}</p>
        <p className="mt-2 text-[11px] leading-relaxed">
          Switches are saved on this machine while Live is running (not in Supabase). Go to{" "}
          <Link href="/live" className="font-semibold text-teal-800 underline-offset-2 hover:underline">
            Live
          </Link>{" "}
          to generate new ones.
        </p>
      </div>
    )
  }

  return (
    <div className={cn(compact ? "space-y-3" : "mx-auto w-full max-w-4xl space-y-6 p-4 sm:p-6")}>
      {lastOutcome && !compact ? (        <CorrectionOutcomeCard result={lastOutcome} variant="light" />
      ) : null}

      <header className={cn(!compact && "flex flex-wrap items-end justify-between gap-3")}>
        <div>
          {!compact ? <p className="haven-eyebrow">Teaching evidence</p> : null}
          <h2
            className={cn(
              compact
                ? "text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-[color:var(--haven-faint)]"
                : "haven-page-title mt-1 text-[color:var(--haven-ink)]",
            )}
          >
            {compact ? "Recent switches" : "Review past switches"}
          </h2>
          <p className={cn("haven-lede mt-2", panelMuted)}>
            Compare <strong className={panelInk}>before → after</strong> with burst frames at the
            switch moment. Mark predictions right or pick the label that should have won.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!compact ? (
            <div
              className="flex rounded-full border border-[color:var(--haven-line-strong)] bg-white/60 p-0.5"
              role="tablist"
              aria-label="Switch review filter"
            >
              {(
                [
                  { id: "pending" as const, label: "To review" },
                  { id: "reviewed" as const, label: "Reviewed" },
                ] as const
              ).map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  onClick={() => setTab(t.id)}
                  className={cn(
                    "rounded-full px-3 py-1 text-[11px] font-semibold",
                    tab === t.id
                      ? "bg-[color:var(--haven-ink)] text-white"
                      : "text-[color:var(--haven-muted)] hover:text-[color:var(--haven-ink)]",
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          ) : null}
          {pending > 0 && tab === "pending" ? (
            <span className="rounded-full border border-[color:var(--haven-line-strong)] bg-[color:var(--haven-accent-soft)] px-2.5 py-0.5 text-[11px] font-semibold text-[color:var(--haven-accent)]">
              {pending} to review
            </span>
          ) : null}
          {compact && pending > 0 ? (
            <Link
              href="/review"
              className={cn(
                roomosUi.focusRingLight,
                "rounded-lg border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_92%,transparent)] px-2.5 py-1 text-[11px] font-semibold",
                panelInk,
                "hover:bg-[color-mix(in_oklab,#fffefb_100%,transparent)]",
              )}
            >
              Review all
            </Link>
          ) : null}
          <button
            type="button"
            onClick={() => void refresh()}
            className={cn(
              roomosUi.focusRingLight,
              "inline-flex size-8 items-center justify-center rounded-lg border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_92%,transparent)]",
              panelMuted,
              "hover:text-[color:var(--haven-ink)]",
            )}
            aria-label="Refresh switch list"
          >
            <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
          </button>
          {!compact && total > 0 ? (
            <button
              type="button"
              onClick={() => void clearAll()}
              disabled={clearing}
              className={cn(
                roomosUi.focusRingLight,
                "inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-rose-300/80 bg-rose-50/90 px-2.5 py-1 text-[11px] font-semibold text-rose-900 hover:bg-rose-50",
                clearing && "opacity-60",
              )}
            >
              {clearing ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : (
                <Trash2 className="size-3.5" aria-hidden />
              )}
              Clear all
            </button>
          ) : null}
        </div>
      </header>
      {loading && items.length === 0 ? (
        <p className={cn("flex items-center gap-2 text-sm", panelMuted)}>
          <Loader2 className="size-4 animate-spin" /> Loading switches…
        </p>
      ) : items.length === 0 ? (
        <p className={cn(cardShell, "haven-lede px-4 py-8 text-center", panelMuted)}>
          {tab === "reviewed"
            ? "No reviewed switches yet. mark a few on the To review tab."
            : "No switches waiting. Stay on Live camera until the primary state changes."}
        </p>
      ) : (
        <ul className={cn("space-y-4", compact && "space-y-3")}>
          {items.map((t) => (
            <TransitionCard
              key={t.id}
              transition={t}
              busy={correctingId === t.id}
              compact={compact}
              readOnly={tab === "reviewed" || t.corrected}
              correctionIds={correctionIds}
              onRelabel={(to) => void relabel(t, to)}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function TransitionCard({
  transition: t,
  busy,
  compact,
  readOnly,
  correctionIds,
  onRelabel,
}: {
  transition: StateTransitionItem
  busy: boolean
  compact?: boolean
  readOnly?: boolean
  correctionIds: readonly string[]
  onRelabel: (to: RoomStateId) => void
}) {
  const [focusFrame, setFocusFrame] = useState(1)
  const predicted = isResolvableLabel(t.toLabel, correctionIds) ? t.toLabel : null
  const fromUi = isResolvableLabel(t.fromLabel, correctionIds) ? t.fromLabel : null
  const frameCount = Math.max(1, Math.min(5, t.screenshotCount))
  const confidencePct = Math.round(t.confidence * 100)
  const lastFrame = frameCount

  return (
    <li className={cn(cardShell, "overflow-hidden")}>
      <div className="flex items-center justify-between border-b border-[color:var(--haven-line)] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--haven-faint)]">
            State switch
          </span>
          {readOnly && t.correctedLabel ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 ring-1 ring-emerald-500/20">
              <CheckCircle2 className="size-3" aria-hidden />
              {displayLabel(t.correctedLabel)}
            </span>
          ) : null}
        </div>
        <time className="font-mono text-[10px] text-[color:var(--haven-faint)]">
          {formatTime(t.capturedAt)}
        </time>
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-stretch gap-2 border-b border-[color:var(--haven-line)] p-3 sm:gap-3 sm:p-4">
        <StateColumn
          label={fromUi ? roomStateLabel(fromUi) : displayLabel(t.fromLabel)}
          caption="Before"
          subcaption="Prior primary state"
          muted
        />
        <div className="flex flex-col items-center justify-center px-0.5 sm:px-1">
          <ArrowRight className="size-6 text-[color:var(--haven-accent)] sm:size-7" aria-hidden />
          <span className="mt-1 text-[9px] font-medium uppercase tracking-wider text-[color:var(--haven-faint)]">
            switched
          </span>
        </div>
        <StateColumn
          label={predicted ? roomStateLabel(predicted) : displayLabel(t.toLabel)}
          caption="Switched to"
          subcaption={`Prediction · ${confidencePct}%`}
          emphasis
        />
      </div>

      <div className="border-b border-[color:var(--haven-line)] px-3 py-3 sm:px-4">
        <p className={cn("text-[10px] font-semibold uppercase tracking-[0.12em] text-[color:var(--haven-faint)]")}>
          Evidence at switch
        </p>
        <p className="mt-1 text-[11px] text-[color:var(--haven-muted)]">
 Full camera view at the switch. same framing as Live preview.
        </p>
        <div className={cn("mt-2", evidenceShellClass, compact ? "max-h-44" : "max-h-[min(28rem,70vh)]")}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={transitionFrameUrl(t.id, focusFrame)}
            alt={`Frame ${focusFrame} of ${frameCount} at switch`}
            className={evidenceFrameClass}
            loading="lazy"
          />
        </div>
        {frameCount > 1 ? (
          <div
            className="mt-2 flex gap-2 overflow-x-auto pb-0.5"
            role="tablist"
            aria-label="Burst frames at switch"
          >
            {Array.from({ length: frameCount }, (_, i) => i + 1).map((idx) => (
              <button
                key={idx}
                type="button"
                role="tab"
                aria-selected={focusFrame === idx}
                onClick={() => setFocusFrame(idx)}
                className={cn(
                  "shrink-0 overflow-hidden rounded-lg border-2 transition-colors",
                  focusFrame === idx
                    ? "border-[color:var(--haven-accent)] ring-1 ring-[color:var(--haven-accent)]/25"
                    : "border-[color:var(--haven-line)] opacity-80 hover:opacity-100",
                )}
 aria-label={`Frame ${idx}${idx === 1 ? ". start of burst" : idx === lastFrame ? ". end of burst" : ""}`}
              >
                <span
                  className={cn(
                    "flex items-center justify-center bg-[color:var(--haven-canvas-mist)]",
                    compact ? "h-14 w-[4.5rem]" : "h-16 w-24",
                  )}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={transitionFrameUrl(t.id, idx)}
                    alt=""
                    className="max-h-full max-w-full object-contain"
                    loading="lazy"
                  />
                </span>
              </button>
            ))}
          </div>
        ) : null}
        {frameCount > 1 ? (
          <p className="mt-2 text-[10px] text-[color:var(--haven-faint)]">
            Frame {focusFrame} of {frameCount}
            {focusFrame === 1 && fromUi ? ` · early read (${roomStateLabel(fromUi)})` : null}
            {focusFrame === lastFrame && predicted
              ? ` · toward ${roomStateLabel(predicted)}`
              : null}
          </p>
        ) : null}
      </div>

      {!readOnly ? (
        <div className="px-4 py-3">
          {predicted ? (
            <>
              <p className={cn("text-[12px]", panelMuted)}>
                Was switching to{" "}
                <span className={cn("font-semibold", panelInk)}>{roomStateLabel(predicted)}</span>{" "}
                correct?
              </p>
              <button
                type="button"
                disabled={busy}
                onClick={() => onRelabel(predicted)}
                className={cn(
                  roomosUi.focusRingLight,
                  "mt-2 flex w-full min-h-10 items-center justify-center gap-2 rounded-xl border border-[color:var(--haven-line-strong)]",
                  "bg-[color:var(--haven-accent-soft)] px-3 py-2 text-[12px] font-semibold text-[color:var(--haven-accent)]",
                  "hover:border-[color:var(--haven-accent)]/40",
                  busy && "opacity-60",
                )}
              >
                {busy ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <ThumbsUp className="size-3.5" aria-hidden />
                )}
 Yes. {roomStateLabel(predicted)}
              </button>
              <p className="mt-3 text-[10px] font-semibold uppercase tracking-[0.1em] text-[color:var(--haven-faint)]">
 No. it should have switched to
              </p>
              <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Correct switch target">
                {correctionIds
                  .filter((s) => s !== predicted)
                  .map((state) => (
                    <button
                      key={state}
                      type="button"
                      disabled={busy}
                      onClick={() => onRelabel(state)}
                      className={cn(
                        roomosUi.focusRingLight,
                        "inline-flex min-h-9 items-center gap-1.5 rounded-xl border border-[color:var(--haven-line-strong)]",
                        "bg-[color-mix(in_oklab,#fffefb_92%,transparent)] px-3 py-1.5 text-[12px] font-semibold",
                        panelInk,
                        "hover:border-[color:var(--haven-accent)]/35 hover:bg-[color:var(--haven-accent-soft)]",
                        busy && "opacity-60",
                      )}
                    >
                      {busy ? <Loader2 className="size-3.5 animate-spin" /> : null}
                      {roomStateLabel(state)}
                    </button>
                  ))}
              </div>
            </>
          ) : (
            <>
              <p className={cn("text-[12px]", panelMuted)}>
 Unknown prediction. pick the activity that matches the frames above.
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {correctionIds.map((state) => (
                  <button
                    key={state}
                    type="button"
                    disabled={busy}
                    onClick={() => onRelabel(state)}
                    className={cn(
                      roomosUi.focusRingLight,
                      "inline-flex min-h-9 items-center rounded-xl border border-[color:var(--haven-line-strong)] px-3 py-1.5 text-[12px] font-semibold",
                      panelInk,
                      busy && "opacity-60",
                    )}
                  >
                    {roomStateLabel(state)}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      ) : (
        <div className={cn("border-t border-[color:var(--haven-line)] px-4 py-3 text-[12px]", panelMuted)}>
          {t.correctedLabel ? (
            <p>
              You marked this as{" "}
              <span className={cn("font-semibold", panelInk)}>{displayLabel(t.correctedLabel)}</span>
 . Room memory uses this burst for similar scenes. retrain is separate.
            </p>
          ) : (
            <p>Reviewed. Saved to on device memory.</p>
          )}
        </div>
      )}
    </li>
  )
}

function StateColumn({
  label,
  caption,
  subcaption,
  emphasis,
  muted,
}: {
  label: string
  caption: string
  subcaption: string
  emphasis?: boolean
  muted?: boolean
}) {
  return (
    <div
      className={cn(
        "flex min-h-[5.5rem] flex-col rounded-xl border px-3 py-2.5 sm:min-h-[6rem] sm:px-4 sm:py-3",
        emphasis
          ? "border-[color:var(--haven-accent)]/35 bg-[color:var(--haven-accent-soft)]"
          : "border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_88%,transparent)]",
      )}
      aria-label={`${caption}: ${label}`}
    >
      <span className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[color:var(--haven-faint)]">
        {caption}
      </span>
      <div className="mt-1.5 flex flex-1 flex-col justify-center gap-1">
        <span
          className={cn(
            "text-[14px] font-semibold leading-tight sm:text-[15px]",
            emphasis
              ? "text-[color:var(--haven-accent)]"
              : muted
                ? "text-[color:var(--haven-muted)]"
                : panelInk,
          )}
        >
          {label}
        </span>
        <span className="text-[10px] text-[color:var(--haven-faint)]">{subcaption}</span>
      </div>
    </div>
  )
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    })
  } catch {
    return iso
  }
}
