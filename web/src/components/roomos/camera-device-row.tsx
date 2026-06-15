"use client"

import type { ReactNode } from "react"
import { useEffect, useRef, useState } from "react"
import type { LucideIcon } from "lucide-react"
import { ChevronDown, Loader2, Trash2, Unplug } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

function InlineRenameHeadline({
  value,
  onSave,
  variant,
  disabled,
}: {
  value: string
  onSave: (name: string) => void
  variant: "light" | "dark"
  disabled?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setDraft(value)
  }, [value])

  useEffect(() => {
    if (editing) inputRef.current?.select()
  }, [editing])

  const commit = () => {
    const trimmed = draft.trim()
    if (trimmed && trimmed !== value) onSave(trimmed)
    else setDraft(value)
    setEditing(false)
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit()
          if (e.key === "Escape") {
            setDraft(value)
            setEditing(false)
          }
        }}
        className={cn(
          "w-full min-w-0 rounded-lg border px-2 py-0.5 font-serif text-[1.35rem] font-medium leading-tight tracking-[-0.02em] outline-none ring-2 ring-teal-500/40 sm:text-[1.45rem]",
          variant === "dark"
            ? "border-white/15 bg-black/40 text-zinc-50"
            : "border-stone-300/80 bg-white text-stone-900",
        )}
        aria-label="Room name"
      />
    )
  }

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => setEditing(true)}
      className={cn(
        "group/name max-w-full text-left font-serif text-[1.35rem] font-medium leading-tight tracking-[-0.02em] sm:text-[1.45rem]",
        variant === "dark" ? "text-zinc-50" : "text-stone-900",
        disabled ? "cursor-default" : "cursor-text",
      )}
    >
      <span className={cn(!disabled && "border-b border-dashed border-transparent group-hover/name:border-teal-500/50")}>
        {value}
      </span>
    </button>
  )
}

export function CameraDeviceRow({
  icon: Icon,
  eyebrow,
  headline,
  onRename,
  renaming,
  detail,
  connected,
  expanded,
  onToggleSetup,
  onDisconnect,
  onRemove,
  removing,
  disconnecting,
  variant = "light",
  children,
}: {
  icon: LucideIcon
  eyebrow: string
  headline: string
  onRename?: (name: string) => void
  renaming?: boolean
  detail: string | null
  connected: boolean
  expanded: boolean
  onToggleSetup: () => void
  onDisconnect?: () => void
  onRemove?: () => void
  removing?: boolean
  disconnecting?: boolean
  variant?: "light" | "dark"
  children?: ReactNode
}) {
  const isDark = variant === "dark"

  return (
    <article
      className={cn(
        "overflow-hidden rounded-2xl border transition-[border-color,box-shadow] duration-200",
        connected
          ? isDark
            ? "border-teal-500/35 bg-black/30 ring-1 ring-teal-500/15"
            : "border-teal-700/30 bg-[linear-gradient(165deg,rgba(255,254,251,0.98)_0%,rgba(252,249,243,0.94)_100%)] ring-1 ring-teal-800/10 shadow-[var(--haven-shadow-card)]"
          : isDark
            ? "border-white/10 bg-black/20"
            : "border-[color:var(--haven-line-strong)] bg-white/70 shadow-[var(--haven-shadow-card)]",
        connected && "border-l-[3px] border-l-teal-500",
        expanded && (isDark ? "shadow-lg shadow-black/20" : "shadow-[var(--haven-shadow-float)]"),
      )}
    >
      <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:gap-5 sm:p-5">
        <div className="flex min-w-0 flex-1 items-start gap-3.5">
          <span
            className={cn(
              "relative flex size-11 shrink-0 items-center justify-center rounded-xl border",
              connected
                ? isDark
                  ? "border-teal-500/30 bg-teal-950/50 text-teal-200"
                  : "border-teal-600/25 bg-teal-50 text-teal-900"
                : isDark
                  ? "border-white/10 bg-black/30 text-zinc-400"
                  : "border-[color:var(--haven-line)] bg-white text-stone-500",
            )}
          >
            <Icon className="size-5" strokeWidth={1.85} aria-hidden />
            {connected ? (
              <span
                className="absolute -top-0.5 -right-0.5 size-2 rounded-full border-2 border-white bg-teal-500"
                aria-hidden
              />
            ) : null}
          </span>

          <div className="min-w-0 flex-1">
            <p
              className={cn(
                "text-[10px] font-semibold uppercase tracking-[0.22em]",
                isDark ? "text-zinc-500" : "text-stone-500",
              )}
            >
              {eyebrow}
            </p>
            <div className="mt-1">
              {onRename ? (
                <InlineRenameHeadline
                  value={headline}
                  onSave={onRename}
                  variant={variant}
                  disabled={renaming}
                />
              ) : (
                <h2
                  className={cn(
                    "font-serif text-[1.35rem] font-medium leading-tight tracking-[-0.02em] sm:text-[1.45rem]",
                    isDark ? "text-zinc-50" : "text-stone-900",
                  )}
                >
                  {headline}
                </h2>
              )}
            </div>
            {detail ? (
              <p
                className={cn(
                  "mt-1 text-[13px] leading-relaxed",
                  isDark ? "text-zinc-500" : "text-stone-600",
                )}
              >
                {detail}
              </p>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide",
              connected
                ? isDark
                  ? "border-teal-500/35 bg-teal-950/40 text-teal-200"
                  : "border-teal-600/35 bg-teal-50 text-teal-900"
                : isDark
                  ? "border-white/10 bg-black/30 text-zinc-500"
                  : "border-stone-300/90 bg-stone-100/90 text-stone-600",
            )}
          >
            <span
              className={cn("size-1.5 rounded-full", connected ? "bg-teal-500" : "bg-stone-400")}
              aria-hidden
            />
            {connected ? "Connected" : "Not connected"}
          </span>

          {connected && onDisconnect ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={disconnecting}
              onClick={onDisconnect}
              className={cn(
                "h-8 gap-1.5 px-3 text-xs",
                isDark
                  ? "border-white/15 bg-transparent text-zinc-300 hover:bg-white/5 hover:text-zinc-100"
                  : roomosUi.havenOutlineBtn,
              )}
            >
              {disconnecting ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : (
                <Unplug className="size-3.5" aria-hidden />
              )}
              Disconnect
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              onClick={onToggleSetup}
              className={cn(
                "h-8 gap-1.5 px-3 text-xs font-semibold",
                expanded
                  ? isDark
                    ? "border border-white/15 bg-transparent text-zinc-300"
                    : cn(roomosUi.havenOutlineBtn, "border-teal-700/25 text-teal-900")
                  : roomosUi.havenPrimaryBtn,
              )}
            >
              {expanded ? "Hide setup" : "Connect"}
              <ChevronDown
                className={cn("size-3.5 transition-transform", expanded && "rotate-180")}
                aria-hidden
              />
            </Button>
          )}

          {connected ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onToggleSetup}
              className={cn(
                "h-8 px-2.5 text-xs",
                isDark
                  ? "text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
                  : "text-stone-600 hover:bg-stone-900/5 hover:text-stone-900",
              )}
            >
              {expanded ? "Close" : "Settings"}
            </Button>
          ) : null}

          {onRemove ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={removing || disconnecting}
              onClick={onRemove}
              className={cn(
                "h-8 w-8 px-0",
                isDark
                  ? "text-zinc-500 hover:bg-rose-950/40 hover:text-rose-300"
                  : "text-stone-500 hover:bg-rose-50 hover:text-rose-800",
              )}
            >
              {removing ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : (
                <Trash2 className="size-3.5" aria-hidden />
              )}
              <span className="sr-only">Remove camera</span>
            </Button>
          ) : null}
        </div>
      </div>

      {expanded && children ? (
        <div
          className={cn(
            "border-t px-4 py-5 sm:px-5",
            isDark
              ? "border-white/10 bg-black/25"
              : "border-[color:var(--haven-line)] bg-[linear-gradient(180deg,rgba(255,254,251,0.92)_0%,rgba(247,243,235,0.75)_100%)]",
          )}
        >
          {children}
        </div>
      ) : null}
    </article>
  )
}
