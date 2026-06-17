"use client"

import { landingFocusRing } from "@/components/landing/landing-primitives"
import { cn } from "@/lib/utils"

/** Editorial seam between dark hero and pearl content — no gradient bridge. */
export function ChapterSeam({
  chapter = "02",
  label = "System",
}: {
  chapter?: string
  label?: string
}) {
  return (
    <div
      className="relative z-[5] bg-[var(--landing-canvas-pearl)]"
      aria-hidden={false}
      role="presentation"
    >
      <div className="border-t border-[#121110]" />
      <div className="flex items-center gap-4 px-5 py-5 sm:px-8 sm:py-6">
        <div className="h-px flex-1 bg-[color:var(--landing-line-strong)]" aria-hidden />
        <p className="shrink-0 font-mono text-[10px] font-semibold uppercase tracking-[0.32em] text-[color:var(--landing-faint)]">
          <span className="text-[color:var(--landing-muted)]">{chapter}</span>
          <span className="mx-2 text-[color:var(--landing-line-strong)]" aria-hidden>
            ·
          </span>
          {label}
        </p>
        <div className="h-px flex-1 bg-[color:var(--landing-line-strong)]" aria-hidden />
      </div>
    </div>
  )
}

export function ChapterSeamLink({
  href = "#how-it-works",
  className,
}: {
  href?: string
  className?: string
}) {
  return (
    <a
      href={href}
      className={cn(
        "group inline-flex items-center gap-2 rounded-full border border-white/[0.1] bg-white/[0.06] px-4 py-2 text-[10.5px] font-semibold uppercase tracking-[0.22em] text-stone-200/78 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-xl transition-[color,transform,background-color] duration-300 hover:bg-white/[0.1] hover:text-white motion-safe:hover:-translate-y-px",
        landingFocusRing,
        className,
      )}
    >
      <span className="relative flex size-1.5" aria-hidden>
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-teal-200/50 motion-reduce:hidden" />
        <span className="relative inline-flex size-1.5 rounded-full bg-teal-200/90" />
      </span>
      Continue
      <span className="transition-transform duration-300 group-hover:translate-y-0.5" aria-hidden>
        ↓
      </span>
    </a>
  )
}
