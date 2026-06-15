"use client"

import { AlertCircle, CheckCircle2, CircleDashed, Loader2, MinusCircle } from "lucide-react"

import { cn } from "@/lib/utils"
import type { SetupCheck, SetupCheckStatus } from "@/lib/roomos/setup-health"
import { roomosUi } from "@/lib/roomos/roomos-ui"

const STATUS_ICON: Record<SetupCheckStatus, typeof CheckCircle2> = {
  pass: CheckCircle2,
  warn: AlertCircle,
  fail: AlertCircle,
  pending: CircleDashed,
  skip: MinusCircle,
}

const STATUS_CLASS: Record<SetupCheckStatus, string> = {
  pass: "text-emerald-400",
  warn: "text-amber-400",
  fail: "text-rose-400",
  pending: "text-zinc-500",
  skip: "text-zinc-600",
}

export function SetupHealthPanel({
  checks,
  loading = false,
  className,
  variant = "dark",
}: {
  checks: SetupCheck[]
  loading?: boolean
  className?: string
  variant?: "dark" | "light"
}) {
  const shell =
    variant === "dark"
      ? roomosUi.liveOverlayGlass
      : cn(roomosUi.prefsCallout, "border-stone-200/90")

  return (
    <div className={cn(shell, "px-4 py-4 sm:px-5", className)} role="status" aria-live="polite">
      <div className="flex items-center justify-between gap-3">
        <p
          className={cn(
            "text-[11px] font-semibold uppercase tracking-[0.18em]",
            variant === "dark" ? "text-zinc-500" : "text-stone-500",
          )}
        >
          Setup health
        </p>
        {loading ? (
          <Loader2
            className={cn("size-3.5 animate-spin", variant === "dark" ? "text-zinc-500" : "text-stone-400")}
            aria-label="Refreshing checks"
          />
        ) : null}
      </div>
      <ul className="mt-3 space-y-2">
        {checks.map((check) => {
          const Icon = STATUS_ICON[check.status]
          return (
            <li
              key={check.id}
              className={cn(
                "flex gap-2.5 rounded-xl border px-3 py-2.5 text-[12.5px] leading-snug",
                variant === "dark"
                  ? "border-white/[0.08] bg-black/20 text-zinc-300"
                  : "border-stone-200/80 bg-white/60 text-stone-700",
              )}
            >
              <Icon
                className={cn("mt-0.5 size-4 shrink-0", STATUS_CLASS[check.status])}
                aria-hidden
              />
              <div className="min-w-0">
                <p className={cn("font-semibold", variant === "dark" ? "text-zinc-100" : "text-stone-900")}>
                  {check.label}
                </p>
                <p className={cn("mt-0.5", variant === "dark" ? "text-zinc-500" : "text-stone-600")}>
                  {check.detail}
                </p>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
