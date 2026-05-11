"use client"

import { FinalCtaSection } from "@/components/landing/final-cta-section"
import { HeroSection } from "@/components/landing/hero-section"
import { HowSection } from "@/components/landing/how-section"
import { LandingNav } from "@/components/landing/landing-nav"
import { landingLayout, LandingContainer } from "@/components/landing/landing-primitives"
import { MoodsSection } from "@/components/landing/moods-section"
import { PersonalizeSection } from "@/components/landing/personalize-section"
import { PreferencesPreviewSection } from "@/components/landing/preferences-preview-section"
import { PrivacySection } from "@/components/landing/privacy-section"
import { cn } from "@/lib/utils"

export function LandingPage() {
  return (
    <div className="landing landing-grain relative min-h-full text-[color:var(--landing-ink)]">
      <LandingNav />
      <main id="main" className="relative">
        <HeroSection />
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
          "border-[color:var(--landing-line-strong)] bg-[linear-gradient(180deg,color-mix(in_oklab,var(--landing-canvas-shade)_62%,transparent)_0%,color-mix(in_oklab,var(--landing-canvas-deep)_48%,transparent)_100%)] py-14 sm:py-[4.5rem]",
        )}
      >
        <LandingContainer className="flex flex-col items-center gap-4 text-center">
          <p className="text-[10px] font-semibold uppercase tracking-[0.38em] text-[color:var(--landing-faint)]">Haven</p>
          <p className="max-w-lg text-[14px] font-normal leading-relaxed text-[color:var(--landing-muted)]">
            Adaptive intelligence for the space you already occupy.
          </p>
        </LandingContainer>
      </footer>
    </div>
  )
}
