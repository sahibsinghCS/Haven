import type { ReactNode } from "react"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export const havenLayout = {
  container: "mx-auto w-full max-w-[min(100%,72rem)] px-5 sm:px-8",
  sectionY: "py-8 sm:py-10",
  scrollMargin: "scroll-mt-28",
} as const

export const havenFontDisplay = "haven-display"

export const havenFocusRing = roomosUi.focusRingLight

export const havenMetaRow = roomosUi.metaRow
export const havenMetaLabel = roomosUi.metaLabel
export const havenMetaValue = roomosUi.metaValue

export const havenCard = cn(
  "rounded-[1.35rem] border border-[color:var(--haven-line-strong)]",
  "bg-[linear-gradient(172deg,rgba(255,254,253,1)_0%,rgba(252,248,242,0.99)_36%,rgba(245,239,230,0.97)_68%,rgba(236,228,216,0.95)_100%)]",
  "shadow-[var(--haven-shadow-card)] ring-1 ring-[color:var(--haven-edge-light)]",
  "transition-[box-shadow,transform,border-color] duration-300 ease-out",
  "motion-safe:hover:shadow-[var(--haven-shadow-float)] motion-safe:hover:-translate-y-px",
)

export const havenCardStatic = cn(
  "rounded-[1.35rem] border border-[color:var(--haven-line-strong)]",
  "bg-[linear-gradient(172deg,rgba(255,254,253,1)_0%,rgba(252,248,242,0.99)_36%,rgba(245,239,230,0.97)_68%,rgba(236,228,216,0.95)_100%)]",
  "shadow-[var(--haven-shadow-card)] ring-1 ring-[color:var(--haven-edge-light)]",
)

export const havenPanel = cn(
  "overflow-hidden rounded-[2rem] border border-[color:var(--haven-line-strong)]",
  "bg-[linear-gradient(172deg,rgba(255,254,253,0.998)_0%,rgba(251,246,238,0.97)_44%,rgba(236,228,218,0.95)_100%)]",
  "shadow-[var(--haven-shadow-float)] ring-1 ring-[color:var(--haven-edge-light)]",
)

export const havenInsetPanel = cn(
  "rounded-xl border border-[color:var(--haven-line)]",
  "bg-[color-mix(in_oklab,#fffefb_88%,var(--haven-canvas-mist)_12%)]",
  "shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]",
)

export const havenNavIsland = cn(
  "relative shrink-0 rounded-full border border-[color:var(--haven-line-strong)]",
  "bg-[color-mix(in_oklab,#fffefb_92%,transparent)]",
  "shadow-[var(--haven-shadow-float)] ring-1 ring-[color:var(--haven-edge-light)]",
  "backdrop-blur-md md:backdrop-blur-md",
)

export const havenBtnPrimary = cn(
  "inline-flex h-11 min-h-11 items-center justify-center gap-2 rounded-full px-6 text-[13px] font-semibold",
  roomosUi.havenPrimaryBtn,
  havenFocusRing,
)

export const havenBtnOutline = cn(
  "inline-flex h-11 min-h-11 items-center justify-center gap-2 rounded-full px-6 text-[13px] font-semibold",
  "border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_92%,transparent)]",
  "text-[color:var(--haven-ink)] shadow-sm hover:bg-white hover:text-[color:var(--haven-ink)]",
  havenFocusRing,
)

const CHIP_TONES = {
  neutral:
    "border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_90%,transparent)] text-[color:var(--haven-muted)]",
  teal: "border-teal-700/30 bg-teal-50/90 text-teal-900",
  amber: "border-amber-500/35 bg-amber-50/90 text-amber-950",
  rose: "border-rose-400/40 bg-rose-50/90 text-rose-950",
  success: "border-teal-600/35 bg-teal-50 text-teal-900",
  offline: "border-[color:var(--haven-line-strong)] bg-[color:var(--haven-canvas-mist)] text-[color:var(--haven-muted)]",
} as const

export function HavenChip({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode
  tone?: keyof typeof CHIP_TONES
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-tight",
        CHIP_TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function HavenBadge({
  children,
  tone = "teal",
  className,
}: {
  children: ReactNode
  tone?: keyof typeof CHIP_TONES
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-3 py-1 text-[12px] font-semibold",
        CHIP_TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function HavenStatCard({
  eyebrow,
  value,
  hint,
  delta,
  deltaTone = "neutral",
  className,
}: {
  eyebrow: string
  value: ReactNode
  hint?: string
  delta?: string
  deltaTone?: "neutral" | "teal" | "amber" | "rose"
  className?: string
}) {
  return (
    <article className={cn(havenCard, "flex flex-col gap-2 px-5 py-4 sm:px-6 sm:py-5", className)}>
      <p className="haven-eyebrow">{eyebrow}</p>
      <p className={cn(havenFontDisplay, "haven-stat-value text-[clamp(1.5rem,3vw,2rem)] text-[color:var(--haven-ink)]")}>
        {value}
      </p>
      {hint ? <p className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">{hint}</p> : null}
      {delta ? (
        <HavenChip tone={deltaTone} className="w-fit font-mono text-[10px] uppercase tracking-[0.14em]">
          {delta}
        </HavenChip>
      ) : null}
    </article>
  )
}

export function HavenSection({
  title,
  lede,
  actions,
  children,
  className,
}: {
  title: string
  lede?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn("flex flex-col gap-5", className)}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 className="haven-section-title text-[color:var(--haven-ink)]">{title}</h2>
          {lede ? <p className="haven-lede mt-1.5 max-w-xl text-[color:var(--haven-muted)]">{lede}</p> : null}
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </div>
      {children}
    </section>
  )
}

export function HavenContainer({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn(havenLayout.container, className)}>{children}</div>
}

export function HavenPageHeader({
  eyebrow,
  title,
  lede,
  id,
  className,
  actions,
}: {
  eyebrow: string
  title: string
  lede?: ReactNode
  id?: string
  className?: string
  actions?: ReactNode
}) {
  return (
    <header className={cn("flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        <p className="haven-eyebrow">{eyebrow}</p>
        <h1 id={id} className="haven-page-title mt-2 text-[color:var(--haven-ink)]">
          {title}
        </h1>
        {lede ? (
          <p className="haven-lede mt-3 max-w-[40rem] text-pretty text-[color:var(--haven-muted)]">{lede}</p>
        ) : null}
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </header>
  )
}
