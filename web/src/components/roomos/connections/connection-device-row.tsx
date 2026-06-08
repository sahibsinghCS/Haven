"use client"

import type { ReactNode } from "react"
import type { LucideIcon } from "lucide-react"
import { ChevronDown, Loader2, Unplug, Zap } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export function ConnectionDeviceRow({
  icon: Icon,
  eyebrow,
  headline,
  detail,
  connected,
  expanded,
  onToggleSetup,
  onDisconnect,
  disconnecting,
  onTest,
  testing,
  testLabel = "Test",
  children,
}: {
  icon: LucideIcon
  eyebrow: string
  headline: string
  detail: string | null
  connected: boolean
  expanded: boolean
  onToggleSetup: () => void
  onDisconnect?: () => void
  disconnecting?: boolean
  onTest?: () => void
  testing?: boolean
  testLabel?: string
  children?: ReactNode
}) {
  return (
    <article
      className={cn(
        "group relative overflow-hidden rounded-[1.4rem] border transition-[border-color,box-shadow,transform] duration-300",
        "bg-[linear-gradient(165deg,rgba(255,254,251,0.98)_0%,rgba(252,249,243,0.94)_55%,rgba(247,243,235,0.9)_100%)]",
        "shadow-[var(--haven-shadow-card)] backdrop-blur-sm",
        connected
          ? "border-teal-700/35 ring-1 ring-teal-800/12"
          : "border-[color:var(--haven-line-strong)] hover:border-teal-800/20 hover:shadow-[var(--haven-shadow-float)]",
        expanded && "shadow-[var(--haven-shadow-float)]",
      )}
    >
      <div
        className={cn(
          "pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100",
          !connected && "bg-[radial-gradient(ellipse_80%_60%_at_100%_0%,rgba(20,184,166,0.07),transparent_55%)]",
        )}
        aria-hidden
      />

      <div
        className={cn(
          "absolute inset-y-3 left-0 w-1 rounded-full transition-all duration-300",
          connected
            ? "bg-gradient-to-b from-teal-400 via-teal-600 to-teal-900 shadow-[0_0_12px_rgba(20,184,166,0.35)]"
            : "bg-gradient-to-b from-stone-300 to-stone-400/80",
        )}
        aria-hidden
      />

      <div className="relative flex flex-col gap-4 p-5 pl-6 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:p-6 sm:pl-8">
        <div className="flex min-w-0 flex-1 items-start gap-4">
          <span
            className={cn(
              "relative flex size-[3.25rem] shrink-0 items-center justify-center rounded-2xl border transition-all duration-300",
              connected
                ? "border-teal-600/30 bg-gradient-to-br from-teal-50 via-white to-teal-50/40 text-teal-900 shadow-[inset_0_1px_0_rgba(255,255,255,1),0_8px_20px_-12px_rgba(15,118,110,0.35)]"
                : "border-[color:var(--haven-line)] bg-white/90 text-stone-600 shadow-[inset_0_1px_0_rgba(255,255,255,0.95)] group-hover:border-teal-700/20 group-hover:text-teal-900",
            )}
          >
            <Icon className="size-5" strokeWidth={1.85} aria-hidden />
            {connected ? (
              <span
                className="absolute -top-0.5 -right-0.5 size-2.5 animate-pulse rounded-full border-2 border-white bg-teal-500"
                aria-hidden
              />
            ) : null}
          </span>

          <div className="min-w-0 pt-0.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.26em] text-stone-500">
              {eyebrow}
            </p>
            <h2 className="mt-1 font-serif text-[1.4rem] font-medium leading-tight tracking-[-0.02em] text-stone-900 sm:text-[1.5rem]">
              {headline}
            </h2>
            {detail ? (
              <p className="mt-1.5 max-w-md text-[13px] leading-relaxed text-stone-600">{detail}</p>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:max-w-[22rem] sm:shrink-0 sm:justify-end">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide",
              connected
                ? "border-teal-600/35 bg-teal-50 text-teal-900"
                : "border-stone-300/90 bg-stone-100/90 text-stone-600",
            )}
          >
            <span
              className={cn("size-1.5 rounded-full", connected ? "bg-teal-500" : "bg-stone-400")}
              aria-hidden
            />
            {connected ? "Connected" : "Not connected"}
          </span>

          {connected && onTest ? (
            <Button
              type="button"
              size="sm"
              disabled={testing || disconnecting}
              onClick={onTest}
              className={cn("gap-1.5 px-3.5", roomosUi.havenPrimaryBtn)}
            >
              {testing ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : (
                <Zap className="size-3.5" aria-hidden />
              )}
              {testLabel}
            </Button>
          ) : null}

          {connected && onDisconnect ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={disconnecting || testing}
              onClick={onDisconnect}
              className={cn("gap-1.5 px-3.5", roomosUi.havenOutlineBtn)}
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
                "gap-1.5 px-4 font-semibold",
                expanded
                  ? cn(roomosUi.havenOutlineBtn, "border-teal-700/25 text-teal-900")
                  : roomosUi.havenPrimaryBtn,
              )}
            >
              {expanded ? "Hide setup" : "Connect"}
              <ChevronDown
                className={cn("size-3.5 transition-transform duration-300", expanded && "rotate-180")}
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
              className="text-stone-600 hover:bg-stone-900/5 hover:text-stone-900"
            >
              {expanded ? "Close" : "Settings"}
            </Button>
          ) : null}
        </div>
      </div>

      {expanded && children ? (
        <div className="relative border-t border-[color:var(--haven-line)] bg-[linear-gradient(180deg,rgba(255,254,251,0.92)_0%,rgba(247,243,235,0.75)_100%)] px-5 py-6 sm:px-8 sm:py-7">
          {children}
        </div>
      ) : null}
    </article>
  )
}
