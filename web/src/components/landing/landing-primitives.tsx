import type { ReactNode, Ref } from "react"
import { forwardRef } from "react"

import { cn } from "@/lib/utils"

/**
 * Marketing layout scale: editorial rhythm across the landing page.
 */
export const landingLayout = {
  /** Max content width ~1152px, generous horizontal padding */
  container: "mx-auto w-full max-w-[min(100%,72rem)] px-5 sm:px-8",
  /**
   * Default section vertical rhythm: composed, not underfilled.
   * Slightly tighter than before so momentum carries between chapters.
   */
  sectionY:
    "py-[clamp(4.75rem,10vw,7.75rem)] sm:py-[clamp(5.25rem,11vw,8.5rem)] lg:py-[clamp(7rem,9vw,8.75rem)]",
  /**
   * First section after hero: pulls the narrative forward without crowding the fold.
   */
  sectionYAfterHero:
    "pb-[clamp(5rem,10vw,8rem)] pt-[clamp(3.5rem,7vw,5.5rem)] sm:pb-[clamp(5.75rem,11vw,8.75rem)] sm:pt-[clamp(4rem,7.5vw,6rem)] lg:pb-[clamp(7rem,9vw,8.75rem)] lg:pt-[clamp(4.5rem,5.5vw,6rem)]",
  sectionBorder: "border-t border-[color:color-mix(in_oklab,rgba(18,17,15,0.16)_72%,transparent)]",
  scrollMargin: "scroll-mt-28",
} as const

/** Hero bottom: compact ramp into pearl (fewer stops = less muddy band). */
export const landingHeroBottomFade =
  "linear-gradient(180deg, rgba(18,17,16,0) 0%, #1c1a17 22%, #4a443c 52%, #a89b8a 78%, var(--landing-canvas-pearl) 100%)"

/** Serif display: Fraunces via root layout variable */
export const landingFontDisplay = "[font-family:var(--landing-display)]"

/**
 * Primary elevated surface: cards, hero fragments (layered gradient + warm shadow + light rim).
 */
export const landingGlass = cn(
  "rounded-[1.35rem]",
  "border border-[color:var(--landing-line-strong)]",
  "bg-[linear-gradient(172deg,rgba(255,254,253,1)_0%,rgba(252,248,242,0.99)_36%,rgba(245,239,230,0.97)_68%,rgba(236,228,216,0.95)_100%)]",
  "shadow-[var(--landing-shadow-card)]",
  "backdrop-blur-xl supports-[backdrop-filter]:bg-[color-mix(in_oklab,var(--landing-surface)_84%,transparent)]",
  "ring-1 ring-[color:var(--landing-edge-light)]",
)

/**
 * Large marketing panels (privacy manifesto, final CTA shell): stronger lift from canvas.
 */
export const landingPanel = cn(
  "overflow-hidden rounded-[2rem]",
  "border border-[color:var(--landing-line-strong)]",
  "bg-[linear-gradient(172deg,rgba(255,254,253,0.998)_0%,rgba(251,246,238,0.97)_44%,rgba(236,228,218,0.95)_100%)]",
  "shadow-[var(--landing-shadow-elevated)]",
  "backdrop-blur-md supports-[backdrop-filter]:bg-[color-mix(in_oklab,var(--landing-surface)_84%,transparent)]",
  "ring-1 ring-[color:var(--landing-edge-light)]",
)

/** Primary marketing CTA: charcoal gradient, specular rim, teal accent ring */
export const landingBtnPrimary = cn(
  "inline-flex items-center justify-center gap-2 rounded-full font-semibold tracking-[-0.012em] text-[#fffcf9]",
  "border border-teal-950/12",
  "bg-[linear-gradient(168deg,#2e2c29_0%,#1e1c19_42%,#171513_100%)]",
  "shadow-[var(--landing-shadow-primary)]",
  "ring-1 ring-inset ring-white/16",
  "transition-[transform,box-shadow,background-color] duration-300 ease-out",
  "motion-safe:hover:-translate-y-px motion-safe:hover:shadow-[var(--landing-shadow-float)]",
  "motion-safe:active:translate-y-0 motion-safe:active:scale-[0.99]",
)

/** Compact primary: dense UI */
export const landingBtnPrimaryCompact = cn(landingBtnPrimary, "h-9 px-4 text-[13px]")

/** Marketing nav: slightly more presence than compact; still minimal */
export const landingBtnPrimaryNav = cn(
  landingBtnPrimary,
  "h-9 min-h-9 px-[1.125rem] text-[12.5px] font-semibold tracking-[-0.02em] sm:h-[2.375rem] sm:min-h-[2.375rem] sm:px-5 sm:text-[13px]",
)

/** Hero / finale primary size */
export const landingBtnPrimaryLg = cn(landingBtnPrimary, "h-[3.35rem] px-11 text-[15px]")

/** Hero fold: flagship primary (first screen, high confidence) */
export const landingBtnPrimaryHero = cn(
  landingBtnPrimary,
  "h-[3.65rem] min-h-[3.65rem] min-w-[12.5rem] px-12 text-[16px] sm:h-[3.8rem] sm:min-h-[3.8rem] sm:px-14 sm:text-[17px]",
)

/** Hero secondary: quiet text action (primary CTA dominates) */
export const landingHeroSecondaryLink = cn(
  "group/hs inline-flex items-center gap-2 rounded-lg px-2 py-2.5 text-[14px] font-semibold tracking-[-0.02em] text-[color:var(--landing-muted)]",
  "transition-[color,transform] duration-300 ease-out hover:text-[color:var(--landing-ink)]",
  "motion-safe:hover:translate-x-px",
)

/** Mid primary: preference preview strip */
export const landingBtnPrimaryMd = cn(landingBtnPrimary, "h-11 px-7 text-[13px]")

/** Secondary pill: glass surface, confident hover lift */
export const landingBtnSecondary = cn(
  "inline-flex items-center justify-center rounded-full border border-[color:var(--landing-line-strong)] bg-[color-mix(in_oklab,var(--landing-surface)_90%,transparent)] px-5 py-2.5 text-[13px] font-semibold text-[color:var(--landing-ink-soft)]",
  "shadow-[var(--landing-shadow-card)] backdrop-blur-md",
  "ring-1 ring-inset ring-white/58",
  "transition-[transform,background-color,color,box-shadow,border-color] duration-300 ease-out",
  "motion-safe:hover:-translate-y-px motion-safe:hover:border-[color:rgba(27,25,23,0.14)] motion-safe:hover:bg-[color-mix(in_oklab,var(--landing-surface)_97%,transparent)] motion-safe:hover:text-[color:var(--landing-ink)]",
)

/** Outline / tertiary: preferences links */
export const landingBtnOutline = cn(
  "inline-flex items-center justify-center gap-2 rounded-full border border-[color:var(--landing-line-strong)] bg-[color-mix(in_oklab,var(--landing-surface)_92%,transparent)] px-6 text-[13px] font-semibold text-[color:var(--landing-ink)] shadow-[var(--landing-shadow-card)] backdrop-blur-md",
  "ring-1 ring-inset ring-white/52",
  "transition-[transform,background-color,box-shadow] duration-300 ease-out",
  "motion-safe:hover:-translate-y-px motion-safe:hover:bg-[color-mix(in_oklab,var(--landing-surface)_98%,transparent)]",
)

/** Focus ring matched to page canvas */
export const landingFocusRing =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700/38 focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--landing-canvas)]"

export function LandingContainer({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn(landingLayout.container, className)}>{children}</div>
}

export const LandingSectionShell = forwardRef(function LandingSectionShell(
  {
    id,
    labelledBy,
    className,
    children,
    /** `afterHero`: tighter top + pulls section slightly toward hero for continuity */
    rhythm = "default",
  }: {
    id?: string
    labelledBy?: string
    className?: string
    children: ReactNode
    rhythm?: "default" | "afterHero"
  },
  ref: Ref<HTMLElement>,
) {
  return (
    <section
      ref={ref}
      id={id}
      aria-labelledby={labelledBy}
      className={cn(
        "relative",
        landingLayout.scrollMargin,
        landingLayout.sectionBorder,
        rhythm === "afterHero" ? landingLayout.sectionYAfterHero : landingLayout.sectionY,
        className,
      )}
    >
      {children}
    </section>
  )
})

export function LandingEyebrow({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <p
      className={cn(
        "text-[11px] font-semibold uppercase tracking-[0.28em] text-[color:var(--landing-muted)] sm:text-[11.5px]",
        className,
      )}
    >
      {children}
    </p>
  )
}

export function LandingDisplayH2({
  id,
  className,
  children,
}: {
  id?: string
  className?: string
  children: ReactNode
}) {
  return (
    <h2
      id={id}
      className={cn(
        landingFontDisplay,
        "text-balance text-[2rem] font-semibold tracking-[-0.035em] text-[color:var(--landing-ink)]",
        "sm:text-[2.5rem] sm:leading-[1.14] lg:text-[2.875rem] lg:leading-[1.1]",
        className,
      )}
    >
      {children}
    </h2>
  )
}

export function LandingProse({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <p
      className={cn(
        "mt-5 max-w-[40rem] text-pretty text-[0.9375rem] font-normal leading-[1.72] text-[color:var(--landing-muted)]",
        "sm:text-lg sm:leading-[1.66]",
        className,
      )}
    >
      {children}
    </p>
  )
}

export function LandingProseMuted({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <p
      className={cn(
        "mt-4 max-w-[40rem] text-pretty text-sm font-normal leading-relaxed text-[color:var(--landing-faint)] sm:text-[0.9375rem]",
        className,
      )}
    >
      {children}
    </p>
  )
}
