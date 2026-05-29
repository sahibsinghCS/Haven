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
 * Review past label switches: shows burst frames and one-tap relabel into room memory.
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
      const confirmed = result.confirmed ?? to === transition.toLabel
      toast.success(confirmed ? "Marked switch as right" : "Marked switch as wrong", {
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
            {compact ? "Recent switches" : "Review switches"}
          </h2>
          <p className="mt-1 text-[12px] leading-relaxed text-zinc-400">
            Each time Haven switches your room state, the burst frames and model guess are saved
            here automatically. Tap one of the five labels — the entry disappears once you pick.
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
  onRelabel,
}: {
  transition: StateTransitionItem
  busy: boolean
  onRelabel: (to: RoomStateId) => void
}) {
  const predicted = isUiState(t.toLabel) ? t.toLabel : null
  const frameCount = Math.max(1, Math.min(5, t.screenshotCount))

  return (
    <li className="overflow-hidden rounded-2xl border border-white/[0.08] bg-zinc-900/60 backdrop-blur-md">
      <div className="flex flex-wrap items-center gap-2 border-b border-white/[0.06] px-4 py-3">
        <StatePill label={t.fromLabel} />
        <ArrowRight className="size-4 text-zinc-500" aria-hidden />
        <StatePill label={t.toLabel} emphasis />
        <time className="ml-auto font-mono text-[10px] text-zinc-500">
          {formatTime(t.capturedAt)}
        </time>
      </div>

      <div className="flex gap-1.5 overflow-x-auto p-3">
        {Array.from({ length: frameCount }, (_, i) => i + 1).map((idx) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={idx}
            src={transitionFrameUrl(t.id, idx)}
            alt={`Frame ${idx} when state became ${displayLabel(t.toLabel)}`}
            className="h-20 w-28 shrink-0 rounded-lg border border-white/10 object-cover sm:h-24 sm:w-32"
            loading="lazy"
          />
        ))}
      </div>

      <div className="border-t border-white/[0.06] px-4 py-3">
        <p className="text-[11px] text-zinc-400">
          It switched to{" "}
          <span className="font-semibold text-zinc-200">
            {displayLabel(predicted ?? t.toLabel)}
          </span>
          . Was that right?
        </p>
        {predicted ? (
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
        ) : null}
        <p className="mt-3 text-[10px] font-semibold uppercase tracking-[0.1em] text-zinc-500">
          No, actually
        </p>
        <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Wrong activity for this switch">
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
      </div>
    </li>
  )
}

function StatePill({
  label,
  emphasis,
}: {
  label: string
  emphasis?: boolean
}) {
  const ui = isUiState(label) ? label : null
  const accent = ui ? ROOM_STATE_ACCENT[ui] : null
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg px-2 py-0.5 text-[12px] font-semibold",
        emphasis ? "bg-white/10 text-zinc-50" : "bg-white/5 text-zinc-300",
      )}
    >
      {accent ? <span className={cn("size-2 rounded-full", accent.bar)} /> : null}
      {displayLabel(label)}
    </span>
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
