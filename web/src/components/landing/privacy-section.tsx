"use client"

import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"

import {
  landingDuration,
  landingEase,
  landingFadeGrounded,
  landingFadeUp,
  landingStaggerParent,
  landingViewport,
} from "@/components/landing/landing-motion"
import {
  landingFontDisplay,
  landingPanel,
  LandingContainer,
  LandingDisplayH2,
  LandingEyebrow,
  LandingSectionShell,
} from "@/components/landing/landing-primitives"
import { cn } from "@/lib/utils"

const principles = [
  {
    title: "Local first by default",
    body: "Inference and preferences anchor on your device and LAN, not a warehouse of raw footage you never opted into.",
  },
  {
    title: "Restraint, not theater",
    body: "No voyeuristic timelines or panic dashboards. Signal appears where it earns space, and stays quiet elsewhere.",
  },
  {
    title: "No cloud required for the demo",
    body: "This hackathon build runs on your machine. A future optional sync layer is not part of the live path.",
  },
] as const

export function PrivacySection() {
  const reduceMotion = useReducedMotion()
  const panelReveal = useMemo(() => landingFadeGrounded(reduceMotion, { y: 14, duration: landingDuration.spine }), [reduceMotion])
  const pillarStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.055, 0.08), [reduceMotion])
  const pillFade = useMemo(() => landingFadeUp(reduceMotion, { y: 6, duration: landingDuration.micro }), [reduceMotion])

  return (
    <LandingSectionShell id="privacy" labelledBy="privacy-heading">
      <div
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(185deg,var(--landing-canvas-pearl)_0%,rgba(236,253,251,0.42)_38%,var(--landing-canvas-mist)_92%,var(--landing-canvas-deep)_100%)]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-teal-700/15 via-stone-400/25 to-teal-700/15"
        aria-hidden
      />

      <LandingContainer className="relative">
        <motion.div
          className={landingPanel}
          variants={panelReveal}
          initial="hidden"
          whileInView="show"
          viewport={landingViewport.assured}
        >
          <div className="grid lg:grid-cols-12">
            <div className="border-b border-[color:var(--landing-line)] p-8 sm:p-10 lg:col-span-5 lg:border-b-0 lg:border-r lg:p-12">
              <LandingEyebrow>Privacy</LandingEyebrow>
              <LandingDisplayH2 id="privacy-heading" className="mt-5">
                Privacy as product discipline.
              </LandingDisplayH2>
              <p className="mt-6 max-w-[26rem] text-[15px] leading-[1.72] text-[color:var(--landing-muted)]">
                Intelligence in the room should read as craft, not as surveillance packaged as convenience for someone
                else&apos;s roadmap.
              </p>
              <blockquote
                className={cn(
                  landingFontDisplay,
                  "mt-10 border-l-[3px] border-teal-700/35 pl-6 text-[1.25rem] font-semibold leading-snug tracking-[-0.02em] text-[color:var(--landing-ink)] sm:text-[1.4rem]",
                )}
              >
                Signal where it earns trust; silence everywhere else.
              </blockquote>
            </div>

            <div className="flex flex-col justify-center lg:col-span-7">
              <motion.div
                variants={pillarStagger}
                initial="hidden"
                whileInView="show"
                viewport={landingViewport.assured}
                className="flex flex-wrap gap-2 border-b border-[color:var(--landing-line)] px-8 py-6 sm:px-10 lg:px-12 lg:pt-10"
              >
                {["Local first posture", "Readable confidence", "Demo: no upload"].map((label) => (
                  <motion.span
                    key={label}
                    variants={pillFade}
                    className="rounded-full border border-[color:var(--landing-line-strong)] bg-[color-mix(in_oklab,var(--landing-surface)_92%,transparent)] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--landing-muted)] shadow-[var(--landing-shadow-card)] backdrop-blur-sm"
                  >
                    {label}
                  </motion.span>
                ))}
              </motion.div>

              <ul className="divide-y divide-[color:var(--landing-line)]">
                {principles.map((item, i) => (
                  <motion.li
                    key={item.title}
                    initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={landingViewport.card}
                    transition={{
                      duration: landingDuration.slow,
                      delay: reduceMotion ? 0 : 0.05 + i * 0.07,
                      ease: landingEase.grounded,
                    }}
                    className="px-8 py-8 sm:px-10 lg:px-12 lg:py-9"
                  >
                    <div className="flex gap-6">
                      <span className="font-mono text-[12px] font-medium tabular-nums text-teal-800/55">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0">
                        <h3 className={cn(landingFontDisplay, "text-lg font-medium tracking-[-0.02em] text-[color:var(--landing-ink)]")}>
                          {item.title}
                        </h3>
                        <p className="mt-3 max-w-[34rem] text-[14px] leading-[1.68] text-[color:var(--landing-muted)]">{item.body}</p>
                      </div>
                    </div>
                  </motion.li>
                ))}
              </ul>
            </div>
          </div>
        </motion.div>
      </LandingContainer>
    </LandingSectionShell>
  )
}
