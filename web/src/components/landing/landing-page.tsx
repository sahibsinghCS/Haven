"use client"

import Link from "next/link"

import { ChapterSeam } from "@/components/landing/chapter-seam"
import { FinalCtaSection } from "@/components/landing/final-cta-section"
import { HeroSection } from "@/components/landing/hero-section"
import { HowSection } from "@/components/landing/how-section"
import { LandingChapterRail } from "@/components/landing/landing-chapter-rail"
import { LandingNav } from "@/components/landing/landing-nav"
import {
  landingFocusRing,
  landingFontDisplay,
  landingLayout,
  LandingContainer,
} from "@/components/landing/landing-primitives"
import { MoodsSection } from "@/components/landing/moods-section"
import { PersonalizeSection } from "@/components/landing/personalize-section"
import { PreferencesPreviewSection } from "@/components/landing/preferences-preview-section"
import { PrivacySection } from "@/components/landing/privacy-section"
import { ScrollProgress } from "@/components/landing/scroll-progress"
import { cn } from "@/lib/utils"
import { havenAppHref } from "@/lib/roomos/app-entry"

const footerColumns: {
  title: string
  items: { label: string; href: string; external?: boolean }[]
}[] = [
  {
    title: "Product",
    items: [
      { label: "How it works", href: "#how-it-works" },
      { label: "Moods", href: "#room-states" },
      { label: "Privacy", href: "#privacy" },
      { label: "Personalization", href: "#personalization" },
    ],
  },
  {
    title: "Open the app",
    items: [
      { label: "Live view", href: havenAppHref("/live?start=1") },
      { label: "Preferences", href: havenAppHref("/preferences") },
    ],
  },
  {
    title: "Posture",
    items: [
      { label: "Local first by default", href: "#privacy" },
      { label: "Readable confidence", href: "#how-it-works" },
      { label: "Local demo only", href: "#privacy" },
    ],
  },
]

export function LandingPage() {
  const year = new Date().getFullYear()

  return (
    <div className="landing landing-grain relative min-h-full overflow-x-clip text-[color:var(--landing-ink)]">
      <ScrollProgress />
      <LandingChapterRail />
      <LandingNav />
      <main id="main" className="relative">
        <HeroSection />
        <ChapterSeam chapter="02" label="System" />
        <HowSection />
        <MoodsSection />
        <PrivacySection />
        <PersonalizeSection />
        <PreferencesPreviewSection />
        <FinalCtaSection />
      </main>
      <footer
        className={cn(
          landingLayout.sectionBorder,
          "relative border-[color:var(--landing-line-strong)]",
          "bg-[linear-gradient(180deg,color-mix(in_oklab,var(--landing-canvas-deep)_72%,transparent)_0%,color-mix(in_oklab,var(--landing-canvas-shade)_92%,transparent)_100%)]",
        )}
        aria-labelledby="landing-footer-heading"
      >
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[color:var(--landing-line-strong)] to-transparent"
          aria-hidden
        />
        <h2 id="landing-footer-heading" className="sr-only">
          Haven, site information
        </h2>

        <LandingContainer className="grid gap-12 py-14 sm:py-[4.5rem] lg:grid-cols-[1.35fr_repeat(3,1fr)] lg:gap-10">
          <div className="max-w-md">
            <Link
              href="/"
              className={cn(
                "group inline-flex items-center gap-3 rounded-xl py-1 pr-2 outline-none",
                landingFocusRing,
              )}
            >
              <span
                className="relative grid size-9 shrink-0 place-items-center rounded-[0.7rem] bg-[linear-gradient(152deg,#242220_0%,#121110_48%,#0a0908_100%)] shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_10px_22px_-12px_rgba(0,0,0,0.45)] ring-1 ring-white/14"
                aria-hidden
              >
                <span className="absolute inset-[1px] rounded-[0.6rem] bg-gradient-to-br from-white/10 to-transparent opacity-80" />
                <span
                  className={cn(
                    landingFontDisplay,
                    "relative text-[15px] font-semibold tracking-[-0.08em] text-[#f7f4ef]",
                  )}
                >
                  H
                </span>
                <span className="absolute -bottom-0.5 -right-0.5 size-1.5 rounded-full border border-white/25 bg-teal-500 shadow-[0_0_0_2px_rgba(247,243,235,0.95)]" />
              </span>
              <span className="leading-none">
                <span
                  className={cn(
                    landingFontDisplay,
                    "block text-[18px] font-semibold tracking-[-0.04em] text-[color:var(--landing-ink)]",
                  )}
                >
                  Haven
                </span>
              </span>
            </Link>
            <p className="mt-6 max-w-[26rem] text-pretty text-[14px] leading-[1.7] text-[color:var(--landing-muted)]">
              Adaptive intelligence for the space you already occupy. Local inference, coherent
              scenes, environments that refine from how you adjust them.
            </p>
            <p className="mt-5 inline-flex items-center gap-2 rounded-full border border-[color:var(--landing-line-strong)] bg-[color-mix(in_oklab,var(--landing-surface)_92%,transparent)] px-3 py-1.5 text-[10.5px] font-semibold uppercase tracking-[0.22em] text-[color:var(--landing-muted)] shadow-[var(--landing-shadow-card)] backdrop-blur-sm">
              <span className="size-1.5 rounded-full bg-teal-500 shadow-[0_0_0_3px_rgba(15,118,110,0.18)]" aria-hidden />
              On device, quiet by default
            </p>
          </div>

          {footerColumns.map((col) => (
            <nav
              key={col.title}
              aria-label={col.title}
              className="flex flex-col"
            >
              <p className="text-[10.5px] font-semibold uppercase tracking-[0.28em] text-[color:var(--landing-faint)]">
                {col.title}
              </p>
              <ul className="mt-5 space-y-3">
                {col.items.map((item) => {
                  const isHash = item.href.startsWith("#")
                  const className = cn(
                    "group inline-flex items-center gap-2 rounded-md text-[13.5px] font-medium text-[color:var(--landing-ink-soft)] transition-colors hover:text-[color:var(--landing-ink)]",
                    landingFocusRing,
                  )
                  return (
                    <li key={item.label}>
                      {isHash ? (
                        <a href={item.href} className={className}>
                          <span className="size-1 rounded-full bg-[color:var(--landing-faint)]/60 transition-all duration-300 group-hover:scale-125 group-hover:bg-teal-700/80" aria-hidden />
                          {item.label}
                        </a>
                      ) : (
                        <Link href={item.href} className={className}>
                          <span className="size-1 rounded-full bg-[color:var(--landing-faint)]/60 transition-all duration-300 group-hover:scale-125 group-hover:bg-teal-700/80" aria-hidden />
                          {item.label}
                        </Link>
                      )}
                    </li>
                  )
                })}
              </ul>
            </nav>
          ))}
        </LandingContainer>

        <div
          className="border-t border-[color:var(--landing-line)]"
          aria-hidden
        />

        <LandingContainer className="flex flex-col items-start justify-between gap-4 py-8 sm:flex-row sm:items-center">
          <p className="text-[12px] font-medium leading-relaxed text-[color:var(--landing-faint)]">
            © {year} Haven. Built for spaces that prefer silence to spectacle.
          </p>
          <p
            className={cn(
              landingFontDisplay,
              "max-w-[24rem] text-balance text-[13px] italic leading-snug text-[color:var(--landing-muted)] sm:text-right",
            )}
          >
            Signal where it earns trust; silence everywhere else.
          </p>
        </LandingContainer>
      </footer>
    </div>
  )
}
