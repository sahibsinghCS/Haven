"use client"

import { useEffect, useState } from "react"
import { MessageCircle, X } from "lucide-react"

import { roomStateLabel } from "@/lib/roomos/state-meta"
import { cn } from "@/lib/utils"
import type { LiveFeedbackEvent } from "@/types/feedback-event"
import type { RoomStateId } from "@/types/roomos"

const VISIBLE_MS = 18_000

export function TelegramCorrectionBanner({
  event,
  onDismiss,
}: {
  event: LiveFeedbackEvent | null
  onDismiss: () => void
}) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!event) {
      setVisible(false)
      return
    }
    setVisible(true)
    const t = window.setTimeout(() => {
      setVisible(false)
      onDismiss()
    }, VISIBLE_MS)
    return () => window.clearTimeout(t)
  }, [event, onDismiss])

  if (!event || !visible) return null

  const corrected = event.correctedLabel as RoomStateId
  const predicted = event.predictedLabel as RoomStateId
  const label = (id: RoomStateId) => roomStateLabel(id) ?? id

  const isTelegram = event.source === "telegram"

  return (
    <div
      className={cn(
        "pointer-events-auto absolute inset-x-2 top-14 z-30 sm:inset-x-4 sm:top-16",
        "animate-in fade-in slide-in-from-top-2 duration-500",
      )}
      role="status"
      aria-live="assertive"
    >
      <div
        className={cn(
          "mx-auto flex max-w-2xl gap-3 rounded-xl border-2 p-3 shadow-2xl backdrop-blur-xl sm:p-4",
          isTelegram
            ? "border-sky-400/70 bg-sky-950/92 ring-2 ring-sky-400/30"
            : "border-teal-400/60 bg-teal-950/90 ring-2 ring-teal-400/25",
        )}
      >
        <div
          className={cn(
            "flex size-10 shrink-0 items-center justify-center rounded-lg",
            isTelegram ? "bg-sky-500/25 text-sky-200" : "bg-teal-500/25 text-teal-200",
          )}
          aria-hidden
        >
          <MessageCircle className="size-5" />
        </div>

        <div className="min-w-0 flex-1 text-left">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-sky-200/90">
            {isTelegram ? "Correction from Telegram" : "Room correction saved"}
          </p>
          <p className="mt-1 text-sm font-semibold text-zinc-50">
            {event.confirmed ? (
              <>Confirmed: {label(corrected)}</>
            ) : (
              <>
                {label(predicted)} → <span className="text-sky-300">{label(corrected)}</span>
              </>
            )}
          </p>
          {event.notes ? (
            <p className="mt-1 line-clamp-2 text-xs italic text-zinc-300/95">
              &ldquo;{event.notes}&rdquo;
            </p>
          ) : null}
          <p className="mt-2 text-[11px] leading-relaxed text-zinc-400">
            Saved this exact webcam frame to training memory
            {event.autoRetrainEnabled ? " · retrain queued in background" : ""}.
          </p>
        </div>

        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`${event.screenshotUrl}?t=${encodeURIComponent(event.createdAt)}`}
          alt="Snapshot saved for training"
          className="hidden size-20 shrink-0 rounded-lg border border-white/15 object-cover sm:block"
        />

        <button
          type="button"
          onClick={() => {
            setVisible(false)
            onDismiss()
          }}
          className="shrink-0 rounded-md p-1 text-zinc-400 hover:bg-white/10 hover:text-zinc-100"
          aria-label="Dismiss"
        >
          <X className="size-4" />
        </button>
      </div>
    </div>
  )
}
