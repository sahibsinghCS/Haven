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
import { roomStateLabel } from "@/lib/roomos/state-meta"
import { ROOM_STATE_ORDER, type RoomStateId } from "@/types/roomos"

function displayLabel(label: string): string {
  if (label === "unknown") return "Uncertain"
  if ((ROOM_STATE_ORDER as readonly string[]).includes(label)) {
    return roomStateLabel(label as RoomStateId)
  }
  return label
}

function isUiState(label: string): label is RoomStateId {
  return (ROOM_STATE_ORDER as readonly string[]).includes(label)
}

const cardShell =
  "rounded-[1.35rem] border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_96%,transparent)] shadow-[var(--haven-shadow-card)] ring-1 ring-[color:var(--haven-edge-light)]"

const panelMuted = "text-[color:var(--haven-muted)]"
const panelInk = "text-[color:var(--haven-ink)]"

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
          : `Similar scenes will bias toward ${roomStateLabel(to)}.`,
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
      <div className={cn(roomosUi.prefsCallout, "p-4 text-sm", panelMuted)}>
        <p className={cn("font-medium", panelInk)}>Switch history unavailable</p>
        <p className="mt-1 text-[12px]">{reason ?? "Start live camera mode to log transitions."}</p>
      </div>
    )
  }

  return (
    <div className={cn(compact ? "space-y-3" : "mx-auto w-full max-w-3xl space-y-6 p-4 sm:p-6")}>
      <header className={cn(!compact && "flex flex-wrap items-end justify-between gap-3")}>
        <div>
          <h2
            className={cn(
              "font-semibold",
              panelInk,
              compact ? "text-[0.68rem] uppercase tracking-[0.18em] text-[color:var(--haven-faint)]" : "haven-display text-2xl tracking-tight",
            )}
          >
            {compact ? "Recent switches" : "Review past switches"}
          </h2>
          <p className={cn("mt-1 text-[13px] leading-relaxed", panelMuted)}>
            Each row is one state change: what was on screen before, what it switched to, and the
            burst frames from that moment. Mark the <strong className={panelInk}>right</strong>{" "}
            prediction correct or pick what it should have been.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {pending > 0 ? (
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
        </div>
      </header>

      {loading && items.length === 0 ? (
        <p className={cn("flex items-center gap-2 text-sm", panelMuted)}>
          <Loader2 className="size-4 animate-spin" /> Loading switches…
        </p>
      ) : items.length === 0 ? (
        <p
          className={cn(
            cardShell,
            "px-4 py-6 text-center text-sm",
            panelMuted,
          )}
        >
          No switches logged yet. Stay on <strong className={panelInk}>Live camera</strong> until the
          primary state changes (e.g. relaxing → sleep).
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
    <li className={cn(cardShell, "overflow-hidden")}>
      <div className="flex items-center justify-between border-b border-[color:var(--haven-line)] px-4 py-2.5">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--haven-faint)]">
          State switch
        </span>
        <time className="font-mono text-[10px] text-[color:var(--haven-faint)]">
          {formatTime(t.capturedAt)}
        </time>
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-stretch gap-2 border-b border-[color:var(--haven-line)] p-3 sm:gap-3 sm:p-4">
        <StateColumn
          label={fromUi ? roomStateLabel(fromUi) : displayLabel(t.fromLabel)}
          caption="Before"
          subcaption="What was on screen"
          muted
        />
        <div className="flex flex-col items-center justify-center px-0.5 sm:px-1">
          <ArrowRight className={cn("size-6 sm:size-7", "text-[color:var(--haven-accent)]")} aria-hidden />
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

      <div className="border-b border-[color:var(--haven-line)] px-3 py-2 sm:px-4">
        <p className={cn("text-[10px]", panelMuted)}>
          Burst frames when it switched to{" "}
          <span className={cn("font-medium", panelInk)}>
            {predicted ? roomStateLabel(predicted) : displayLabel(t.toLabel)}
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
                "shrink-0 rounded-lg border border-[color:var(--haven-line-strong)] bg-[color:var(--haven-canvas-mist)] object-cover",
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
              Yes — {roomStateLabel(predicted)}
            </button>
            <p className="mt-3 text-[10px] font-semibold uppercase tracking-[0.1em] text-[color:var(--haven-faint)]">
              No — it should have switched to
            </p>
            <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Correct switch target">
              {ROOM_STATE_ORDER.filter((s) => s !== predicted).map((state) => (
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
          <p className={cn("text-[12px]", panelMuted)}>
            Unknown prediction label — pick the activity that matches the frames above.
          </p>
        )}
      </div>
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
            emphasis ? "text-[color:var(--haven-accent)]" : muted ? "text-[color:var(--haven-muted)]" : panelInk,
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
