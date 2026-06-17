"use client"

import Link from "next/link"
import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { ArrowRight } from "lucide-react"

import {
  landingDuration,
  landingEase,
  landingFadeLift,
  landingFadeUp,
  landingStaggerParent,
  landingViewport,
} from "@/components/landing/landing-motion"
import {
  landingBtnPrimaryLg,
  landingBtnSecondary,
  landingFocusRing,
  landingFontDisplay,
  landingPanel,
  LandingContainer,
  LandingEyebrow,
  LandingSectionShell,
} from "@/components/landing/landing-primitives"
import { havenAppHref } from "@/lib/roomos/app-entry"
import { markLiveStartIntent } from "@/lib/roomos/live-session-start"
import { cn } from "@/lib/utils"

export function FinalCtaSection() {
  const reduceMotion = useReducedMotion()
  const shellLift = useMemo(
    () => landingFadeLift(reduceMotion, { y: 44, scale: 0.982, duration: landingDuration.cta }),
    [reduceMotion],
  )
  const leftStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.11, 0.09), [reduceMotion])
  const leftLine = useMemo(() => landingFadeUp(reduceMotion, { y: 24, duration: landingDuration.slow }), [reduceMotion])
  const rightStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.12, 0.16), [reduceMotion])
  const rightLine = useMemo(() => landingFadeUp(reduceMotion, { y: 18, duration: landingDuration.standard }), [reduceMotion])

  return (
    <LandingSectionShell
      id="final-cta"
      labelledBy="final-cta-heading"
      className="!border-t-0 !pb-0 !pt-[clamp(3.75rem,8vw,6.75rem)] sm:!pt-[clamp(4.25rem,8vw,7.25rem)]"
    >
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_95%_72%_at_50%_108%,var(--landing-accent-mist),transparent_56%),linear-gradient(180deg,var(--landing-canvas-pearl)_0%,var(--landing-canvas-mist)_42%,var(--landing-canvas-deep)_72%,var(--landing-canvas-shade)_100%)]"
        aria-hidden
      />

      <LandingContainer className="relative pb-14 pt-5 sm:pb-16 sm:pt-6 lg:pb-20">
        <motion.div
          className={landingPanel}
          variants={shellLift}
          initial="hidden"
          whileInView="show"
          viewport={landingViewport.finale}
        >
          <div className="grid lg:grid-cols-12 lg:items-stretch">
            <motion.div
              className="relative border-b border-[color:var(--landing-line)] p-10 sm:p-12 lg:col-span-7 lg:border-b-0 lg:border-r lg:p-14"
              variants={leftStagger}
              initial="hidden"
              whileInView="show"
              viewport={landingViewport.finale}
            >
              <div
                className="pointer-events-none absolute -left-[30%] top-1/2 size-[min(90vw,420px)] -translate-y-1/2 rounded-full bg-[color:var(--landing-accent-soft)] blur-3xl"
                aria-hidden
              />
              <motion.div variants={leftLine}>
                <LandingEyebrow className="relative tracking-[0.32em]">Haven</LandingEyebrow>
              </motion.div>
              <motion.div variants={leftLine} className="relative mt-8">
                <h2
                  id="final-cta-heading"
                  className={cn(
                    landingFontDisplay,
                    "text-balance text-[clamp(2.15rem,4.8vw,3.5rem)] font-semibold leading-[1.05] tracking-[-0.038em] text-[color:var(--landing-ink)]",
                  )}
                >
                  Step into a room that adjusts with you, and knows when to stay quiet.
                </h2>
              </motion.div>
              <motion.div variants={leftLine} className="relative mt-8">
                <p className="max-w-[28rem] text-[16px] leading-[1.68] text-[color:var(--landing-muted)]">
                  Open live view, let inference settle against your space, then tune moods when you&apos;re ready. Local posture,
                  legible UI, deliberate environmental control.
                </p>
              </motion.div>
            </motion.div>

            <motion.div
              className="relative flex flex-col justify-center gap-8 bg-[linear-gradient(148deg,rgba(255,253,250,0.98)_0%,rgba(236,253,251,0.44)_42%,rgba(255,251,235,0.34)_100%)] p-10 sm:p-12 lg:col-span-5 lg:p-14"
              variants={rightStagger}
              initial="hidden"
              whileInView="show"
              viewport={landingViewport.finale}
            >
              <div className="pointer-events-none absolute inset-0 opacity-[0.35]" aria-hidden>
                <div className="absolute right-6 top-6 size-24 rounded-full border border-teal-700/10" />
                <div className="absolute bottom-10 left-8 size-16 rounded-full border border-amber-400/20" />
              </div>

              <motion.div variants={rightLine} className="relative space-y-4">
                <Link
                  href={havenAppHref("/live?start=1")}
                  onClick={() => markLiveStartIntent()}
                  className={cn(
                    landingBtnPrimaryLg,
                    landingFocusRing,
                    "h-[3.25rem] w-full min-w-[220px] gap-2 sm:inline-flex sm:w-auto",
                  )}
                >
                  Get Started
                  <ArrowRight className="size-4 opacity-90" strokeWidth={2} aria-hidden />
                </Link>
                <Link
                  href="/preferences"
                  className={cn(
                    landingBtnSecondary,
                    landingFocusRing,
                    "flex min-h-[3.25rem] w-full items-center justify-center px-8 py-3 text-[14px] sm:inline-flex sm:w-auto sm:min-w-[220px]",
                  )}
                >
                  Open preferences
                </Link>
              </motion.div>
              <motion.p
                variants={rightLine}
                className="relative text-[12px] leading-relaxed text-[color:var(--landing-faint)]"
              >
                No theatrics: a calmer room that keeps inching toward how you actually live.
              </motion.p>
            </motion.div>
          </div>

          <motion.div
            className="h-1 bg-gradient-to-r from-teal-700/28 via-amber-400/35 to-violet-500/28"
            initial={reduceMotion ? false : { scaleX: 0 }}
            whileInView={{ scaleX: 1 }}
            viewport={landingViewport.finale}
            transition={{
              duration: landingDuration.cta,
              ease: landingEase.lux,
              delay: reduceMotion ? 0 : 0.18,
            }}
            style={{ transformOrigin: "left center" }}
            aria-hidden
          />
        </motion.div>
      </LandingContainer>
    </LandingSectionShell>
  )
}
