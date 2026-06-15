"use client"

import type { ReactNode } from "react"
// ReactNode used for flexible eyebrow slot (badge or string)
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export type HavenSurfaceVariant = "dark" | "light"
export type HavenSurfaceTone =
  | "neutral"
  | "loading"
  | "empty"
  | "error"
  | "warn"
  | "demo"
  | "replay"
  | "offline"

const TONE_BORDER: Record<HavenSurfaceTone, { dark: string; light: string }> = {
  neutral: { dark: "border-white/10", light: "border-[color:var(--haven-line-strong)]" },
  loading: { dark: "border-teal-500/25", light: "border-teal-600/25" },
  empty: { dark: "border-white/10", light: "border-[color:var(--haven-line-strong)]" },
  error: { dark: "border-rose-400/30", light: "border-rose-300/70" },
  warn: { dark: "border-amber-400/30", light: "border-amber-400/45" },
  demo: { dark: "border-amber-400/40", light: "border-amber-400/45" },
  replay: { dark: "border-violet-400/35", light: "border-violet-400/40" },
  offline: { dark: "border-stone-400/30", light: "border-stone-400/35" },
}

/**
 * Consistent empty / loading / error panels — cinematic on Live, pearl on Preferences.
 */
export function HavenSurfaceState({
  variant = "light",
  tone = "neutral",
  icon,
  eyebrow,
  title,
  description,
  children,
  footer,
  className,
  role = "status",
  ariaLive,
}: {
  variant?: HavenSurfaceVariant
  tone?: HavenSurfaceTone
  icon?: ReactNode
  eyebrow?: ReactNode
  title: string
  description?: ReactNode
  children?: ReactNode
  footer?: ReactNode
  className?: string
  role?: "status" | "alert"
  ariaLive?: "polite" | "assertive" | "off"
}) {
  const isDark = variant === "dark"
  const border = TONE_BORDER[tone][variant]

  return (
    <div
      className={cn(
        isDark ? roomosUi.liveOverlayGlass : roomosUi.prefsCallout,
        "w-full max-w-xl px-6 py-8 text-center sm:px-8",
        border,
        tone === "error" && !isDark && "bg-rose-50/90",
        tone === "warn" && isDark && "border-amber-500/20",
        className,
      )}
      role={role}
      aria-live={ariaLive}
    >
      {icon ? (
        <div
          className={cn(
            "mx-auto flex size-12 items-center justify-center rounded-2xl",
            isDark ? "bg-white/[0.06] text-zinc-300" : "bg-[color:var(--haven-accent-soft)] text-teal-800",
          )}
          aria-hidden
        >
          {icon}
        </div>
      ) : null}
      {eyebrow ? (
        <div className={cn("mt-4", typeof eyebrow === "string" && "haven-eyebrow", isDark && typeof eyebrow === "string" && "text-zinc-500")}>
          {eyebrow}
        </div>
      ) : null}
      <h2
        className={cn(
          "haven-section-title mt-2 text-balance",
          isDark ? "text-zinc-50" : "text-[color:var(--haven-ink)]",
          !eyebrow && !icon && "mt-0",
        )}
      >
        {title}
      </h2>
      {description ? (
        <p
          className={cn(
            "haven-lede mx-auto mt-2.5 max-w-md text-pretty",
            isDark ? "text-zinc-400" : "text-[color:var(--haven-muted)]",
            tone === "error" && isDark && "text-rose-200/90",
          )}
        >
          {description}
        </p>
      ) : null}
      {children ? <div className="mt-5 text-left">{children}</div> : null}
      {footer ? <div className="mt-6 flex flex-col items-center gap-3">{footer}</div> : null}
    </div>
  )
}

/** Compact status chips for live boot / idle states */
export function HavenStatusChips({
  items,
  variant = "dark",
}: {
  items: Array<{ label: string; active?: boolean }>
  variant?: HavenSurfaceVariant
}) {
  const isDark = variant === "dark"
  return (
    <div
      className={cn(
        "flex flex-wrap justify-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em]",
        isDark ? "text-zinc-500" : "text-[color:var(--haven-faint)]",
      )}
    >
      {items.map((item) => (
        <span
          key={item.label}
          className={cn(
            "rounded-full border px-2.5 py-1",
            item.active
              ? isDark
                ? "border-emerald-400/40 text-emerald-200"
                : "border-teal-600/35 bg-teal-50/80 text-teal-900"
              : isDark
                ? "border-white/10"
                : "border-[color:var(--haven-line)] bg-white/50",
          )}
        >
          {item.label}
        </span>
      ))}
    </div>
  )
}
