"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { ArrowRight, Loader2, RefreshCw, ThumbsUp } from "lucide-react"
import { toast } from "sonner"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import {
  correctTransition,
  fetchTransitions,
  transitionFrameUrl,
  type StateTransitionItem,
} from "@/lib/roomos/api-client"
import { ROOM_STATE_ACCENT, ROOM_STATE_LABEL } from "@/lib/roomos/state-meta"
import { ROOM_STATE_ORDER, type RoomStateId } from "@/types/roomos"

function displayLabel(label: string): string {
  if (label === "unknown") return "Uncertain"
  if ((ROOM_STATE_ORDER as readonly string[]).includes(label)) {
    return ROOM_STATE_LABEL[label as RoomStateId]
  }
  return label
}

function isUiState(label: string): label is RoomStateId {
  return (ROOM_STATE_ORDER as readonly string[]).includes(label)
}

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
  const [items, setItems] = useState<StateTransitionItem[]>([])
  const [pending, setPending] = useState(0)
  const [enabled, setEnabled] = useState(true)
  const [reason, setReason] = useState<string | undefined>()
  const [loading, setLoading] = useState(true)
  const [correctingId, setCorrectingId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await fetchTransitions({
        limit: compact ? 6 : 30,
        uncorrectedOnly: true,
      })
      setEnabled(data.enabled)
      setReason(data.reason)
      setPending(data.pendingReview ?? 0)
      setItems(data.transitions)
    } catch (err) {
      setEnabled(false)
      setReason(err instanceof Error ? err.message : "API unavailable")
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [compact])

  useEffect(() => {
    void refresh()
    const id = window.setInterval(() => void refresh(), pollMs)
    return () => window.clearInterval(id)
  }, [refresh, pollMs])

  async function relabel(transition: StateTransitionItem, to: RoomStateId) {
    if (correctingId) return
    setCorrectingId(transition.id)
    try {
      const result = await correctTransition(transition.id, {
        correctedLabel: to,
        notes: `review: ${transition.toLabel} -> ${to}`,
      })
      const predicted = isUiState(transition.toLabel) ? transition.toLabel : null
      const confirmed = result.confirmed ?? (predicted != null && to === predicted)
      toast.success(confirmed ? "Switch marked right" : "Switch marked wrong", {
        description: result.retrainsModel
          ? "Counts toward automatic model retrain."
          : `Similar scenes will bias toward ${ROOM_STATE_LABEL[to]}.`,
        duration: 5000,
      })
      if (result.probabilityPreview?.appliedAfterSave) {
        toast.message("Preview", {
          description: "This exact burst would already read differently with memory on.",
        })
      }
      await refresh()
    } catch (err) {
      toast.error("Could not save relabel", {
        description: err instanceof Error ? err.message : "Check API is running.",
      })
    } finally {
      setCorrectingId(null)
    }
  }

  if (!enabled) {
    return (
      <div className={cn(roomosUi.liveOverlayGlassTranslucent, "p-4 text-sm text-zinc-400")}>
        <p className="font-medium text-zinc-200">Switch history unavailable</p>
        <p className="mt-1 text-[12px] text-zinc-500">
          {reason ?? "Start live camera mode to log transitions."}
        </p>
      </div>
    )
  }

  return (
    <div className={cn(compact ? "space-y-3" : "mx-auto w-full max-w-3xl space-y-6 p-4 sm:p-6")}>
      <header className={cn(!compact && "flex flex-wrap items-end justify-between gap-3")}>
        <div>
          <h2
            className={cn(
              "font-semibold text-zinc-100",
              compact ? "text-[0.68rem] uppercase tracking-[0.18em] text-zinc-400" : "text-xl",
            )}
          >
            {compact ? "Recent switches" : "Review past switches"}
          </h2>
          <p className="mt-1 text-[12px] leading-relaxed text-zinc-400">
            Each row is one state change: what was on screen before, what it switched to, and the
            burst frames from that moment. Mark the <strong className="text-zinc-200">right</strong>{" "}
            prediction correct or pick what it should have been.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {pending > 0 ? (
            <span className="rounded-full border border-amber-400/30 bg-amber-950/40 px-2.5 py-0.5 text-[11px] font-medium text-amber-100">
              {pending} to review
            </span>
          ) : null}
          {compact && pending > 0 ? (
            <Link
              href="/review"
              className="rounded-lg border border-white/15 bg-white/10 px-2.5 py-1 text-[11px] font-semibold text-zinc-100 hover:bg-white/15"
            >
              Review all
            </Link>
          ) : null}
          <button
            type="button"
            onClick={() => void refresh()}
            className="inline-flex size-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-zinc-300 hover:bg-white/10"
            aria-label="Refresh switch list"
          >
            <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
          </button>
        </div>
      </header>

      {loading && items.length === 0 ? (
        <p className="flex items-center gap-2 text-sm text-zinc-500">
          <Loader2 className="size-4 animate-spin" /> Loading switches…
        </p>
      ) : items.length === 0 ? (
        <p className="rounded-xl border border-white/10 bg-white/5 px-4 py-6 text-center text-sm text-zinc-400">
          No switches logged yet. Stay on <strong className="text-zinc-200">Live camera</strong>{" "}
          until the primary state changes (e.g. relaxing → sleep).
        </p>
      ) : (
        <ul className={cn("space-y-4", compact && "space-y-3")}>
          {items.map((t) => (
            <TransitionCard
              key={t.id}
              transition={t}
              busy={correctingId === t.id}
              compact={compact}
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
  onRelabel,
}: {
  transition: StateTransitionItem
  busy: boolean
  compact?: boolean
  onRelabel: (to: RoomStateId) => void
}) {
  const predicted = isUiState(t.toLabel) ? t.toLabel : null
  const fromUi = isUiState(t.fromLabel) ? t.fromLabel : null
  const frameCount = Math.max(1, Math.min(5, t.screenshotCount))
  const confidencePct = Math.round(t.confidence * 100)

  return (
    <li className="overflow-hidden rounded-2xl border border-white/[0.08] bg-zinc-900/60 backdrop-blur-md">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
          State switch
        </span>
        <time className="font-mono text-[10px] text-zinc-500">{formatTime(t.capturedAt)}</time>
      </div>

      {/* Before → After */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-stretch gap-2 border-b border-white/[0.06] p-3 sm:gap-3 sm:p-4">
        <StateColumn
          role="before"
          label={fromUi ? ROOM_STATE_LABEL[fromUi] : displayLabel(t.fromLabel)}
          stateId={fromUi}
          caption="Before"
          subcaption="What was on screen"
          muted
        />
        <div className="flex flex-col items-center justify-center px-0.5 sm:px-1">
          <ArrowRight
            className="size-6 text-teal-400/90 sm:size-7"
            aria-hidden
          />
          <span className="mt-1 text-[9px] font-medium uppercase tracking-wider text-zinc-600">
            switched
          </span>
        </div>
        <StateColumn
          role="prediction"
          label={predicted ? ROOM_STATE_LABEL[predicted] : displayLabel(t.toLabel)}
          stateId={predicted}
          caption="Switched to"
          subcaption={`Prediction · ${confidencePct}%`}
          emphasis
        />
      </div>

      <div className="border-b border-white/[0.06] px-3 py-2 sm:px-4">
        <p className="text-[10px] text-zinc-500">
          Burst frames when it switched to{" "}
          <span className="font-medium text-zinc-300">
            {predicted ? ROOM_STATE_LABEL[predicted] : displayLabel(t.toLabel)}
          </span>
        </p>
        <div className="mt-2 flex gap-1.5 overflow-x-auto">
          {Array.from({ length: frameCount }, (_, i) => i + 1).map((idx) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={idx}
              src={transitionFrameUrl(t.id, idx)}
              alt={`Frame ${idx} at switch to ${displayLabel(t.toLabel)}`}
              className={cn(
                "shrink-0 rounded-lg border border-white/10 object-cover",
                compact ? "h-16 w-[5.5rem]" : "h-20 w-28 sm:h-24 sm:w-32",
              )}
              loading="lazy"
            />
          ))}
        </div>
      </div>

      <div className="px-4 py-3">
        {predicted ? (
          <>
            <p className="text-[11px] text-zinc-400">
              Was switching to{" "}
              <span className="font-semibold text-zinc-100">{ROOM_STATE_LABEL[predicted]}</span>{" "}
              correct?
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() => onRelabel(predicted)}
              className={cn(
                "mt-2 flex w-full min-h-10 items-center justify-center gap-2 rounded-xl border border-emerald-400/30",
                "bg-emerald-950/40 px-3 py-2 text-[12px] font-semibold text-emerald-50 hover:bg-emerald-950/55",
                busy && "opacity-60",
              )}
            >
              {busy ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <ThumbsUp className="size-3.5" aria-hidden />
              )}
              Yes — {ROOM_STATE_LABEL[predicted]}
            </button>
            <p className="mt-3 text-[10px] font-semibold uppercase tracking-[0.1em] text-zinc-500">
              No — it should have switched to
            </p>
            <div
              className="mt-2 flex flex-wrap gap-2"
              role="group"
              aria-label="Correct switch target"
            >
              {ROOM_STATE_ORDER.filter((s) => s !== predicted).map((state) => {
                const accent = ROOM_STATE_ACCENT[state]
                return (
                  <button
                    key={state}
                    type="button"
                    disabled={busy}
                    onClick={() => onRelabel(state)}
                    className={cn(
                      "inline-flex min-h-9 items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5",
                      "text-[12px] font-semibold text-zinc-100 hover:bg-white/12",
                      busy && "opacity-60",
                    )}
                  >
                    {busy ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <span className={cn("size-2 rounded-full", accent.bar)} />
                    )}
                    {ROOM_STATE_LABEL[state]}
                  </button>
                )
              })}
            </div>
          </>
        ) : (
          <p className="text-[12px] text-zinc-400">
            Unknown prediction label — pick the activity that matches the frames above.
          </p>
        )}
      </div>
    </li>
  )
}

function StateColumn({
  role,
  label,
  stateId,
  caption,
  subcaption,
  emphasis,
  muted,
}: {
  role: "before" | "prediction"
  label: string
  stateId: RoomStateId | null
  caption: string
  subcaption: string
  emphasis?: boolean
  muted?: boolean
}) {
  const accent = stateId ? ROOM_STATE_ACCENT[stateId] : null
  return (
    <div
      className={cn(
        "flex min-h-[5.5rem] flex-col rounded-xl border px-3 py-2.5 sm:min-h-[6rem] sm:px-4 sm:py-3",
        emphasis
          ? "border-teal-400/25 bg-teal-950/35"
          : "border-white/[0.08] bg-white/[0.04]",
      )}
      aria-label={`${caption}: ${label}`}
      data-role={role}
    >
      <span className="text-[9px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
        {caption}
      </span>
      <div className="mt-1.5 flex flex-1 flex-col justify-center gap-1">
        <span
          className={cn(
            "inline-flex items-center gap-2 text-[14px] font-semibold leading-tight sm:text-[15px]",
            emphasis ? "text-teal-50" : muted ? "text-zinc-300" : "text-zinc-100",
          )}
        >
          {accent ? (
            <span className={cn("size-2.5 shrink-0 rounded-full", accent.bar)} aria-hidden />
          ) : null}
          {label}
        </span>
        <span className="text-[10px] text-zinc-500">{subcaption}</span>
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
