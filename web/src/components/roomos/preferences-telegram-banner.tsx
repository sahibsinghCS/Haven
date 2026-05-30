"use client"

import { useEffect, useState } from "react"
import { Settings2, X } from "lucide-react"

import { ROOM_STATE_LABEL } from "@/lib/roomos/state-meta"
import { cn } from "@/lib/utils"
import type { LivePreferencesEvent } from "@/types/preferences-event"
import type { RoomStateId } from "@/types/roomos"

const VISIBLE_MS = 20_000

export function PreferencesTelegramBanner({
  event,
  onDismiss,
}: {
  event: LivePreferencesEvent | null
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

  const isTelegram = event.source === "telegram"
  const moodLabels = event.targetStates
    .map((s) => ROOM_STATE_LABEL[s as RoomStateId] ?? s)
    .join(", ")

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
            ? "border-violet-400/70 bg-violet-950/92 ring-2 ring-violet-400/30"
            : "border-teal-400/60 bg-teal-950/90",
        )}
      >
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-violet-500/25 text-violet-200">
          <Settings2 className="size-5" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-violet-200/90">
            {isTelegram ? "Preferences updated from Telegram" : "Preferences saved"}
          </p>
          <p className="mt-1 text-sm font-semibold text-zinc-50">
            {event.presetName}
            {moodLabels ? ` · ${moodLabels}` : ""}
          </p>
          {event.notes ? (
            <p className="mt-1 line-clamp-2 text-xs italic text-zinc-300/95">
              &ldquo;{event.notes}&rdquo;
            </p>
          ) : null}
          <ul className="mt-2 space-y-0.5 text-[11px] text-zinc-300">
            {event.changes.slice(0, 4).map((line) => (
              <li key={line}>• {line}</li>
            ))}
          </ul>
          <p className="mt-2 text-[10px] text-zinc-500">
            Saved to <code className="rounded bg-black/30 px-1">data/preferences.json</code> — open
            /preferences to edit more.
          </p>
        </div>
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
