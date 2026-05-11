"use client"

import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"
import Link from "next/link"

import {
  landingDuration,
  landingEase,
  landingFadeUp,
  landingStaggerParent,
  landingViewport,
} from "@/components/landing/landing-motion"
import {
  landingFocusRing,
  landingFontDisplay,
  LandingContainer,
  LandingDisplayH2,
  LandingEyebrow,
  LandingProse,
  LandingSectionShell,
} from "@/components/landing/landing-primitives"
import { cn } from "@/lib/utils"

const pipeline = [
  {
    key: "sense",
    label: "Sense",
    glyph: "○",
    accent: "from-teal-600/90 to-teal-500/50",
    ring: "ring-teal-600/35",
    body: "Light, motion, sound, presence: ordinary signals, interpreted where you live.",
    aside: "No exotic hardware pitch, just context done locally.",
  },
  {
    key: "infer",
    label: "Infer",
    glyph: "◈",
    accent: "from-violet-600/85 to-violet-400/45",
    ring: "ring-violet-500/30",
    body: "Estimates what you're likely doing, with confidence surfaced in the UI, not buried or exaggerated.",
    aside: "When certainty is low, the interface says so.",
  },
  {
    key: "adapt",
    label: "Adapt",
    glyph: "◇",
    accent: "from-amber-600/80 to-amber-400/40",
    ring: "ring-amber-500/28",
    body: "Brightness, color tone, airflow, and temperature move as one scene, matched to the active mood.",
    aside: "One coherent adjustment beats four unrelated toggles.",
  },
  {
    key: "learn",
    label: "Learn",
    glyph: "◎",
    accent: "from-teal-800/85 to-emerald-500/45",
    ring: "ring-emerald-600/28",
    body: "Preferences and small corrections reshape defaults over time, without surveys or nag screens.",
    aside: "Trust compounds in increments you barely notice.",
  },
] as const

export function HowSection() {
  const reduceMotion = useReducedMotion()
  const headStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.065, 0.05), [reduceMotion])
  const headLine = useMemo(() => landingFadeUp(reduceMotion, { y: 16, duration: landingDuration.standard }), [reduceMotion])

  return (
    <LandingSectionShell
      id="how-it-works"
      labelledBy="how-heading"
      rhythm="afterHero"
      className="!border-t-0 -mt-[clamp(1.25rem,4vw,2.75rem)]"
    >
      <div
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(178deg,transparent_0px,color-mix(in_oklab,var(--landing-canvas-pearl)_38%,transparent)_4rem,color-mix(in_oklab,var(--landing-canvas-pearl)_78%,transparent)_7.25rem,var(--landing-canvas-pearl)_10.5rem,var(--landing-canvas-pearl)_22%,var(--landing-canvas)_48%,var(--landing-canvas-mist)_88%,var(--landing-canvas-deep)_100%)]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-[min(12rem,22vh)] bg-[linear-gradient(180deg,color-mix(in_oklab,var(--landing-ink)_12%,transparent)_0%,color-mix(in_oklab,var(--landing-ink)_4%,transparent)_38%,transparent_100%)]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[color:var(--landing-line-strong)] to-transparent opacity-70"
        aria-hidden
      />

      <LandingContainer className="relative">
        <div className="grid gap-11 lg:grid-cols-12 lg:gap-11">
          <header className="lg:col-span-4 lg:pt-2">
            <motion.div
              className="lg:sticky lg:top-[calc(4.5rem+2rem)]"
              variants={headStagger}
              initial="hidden"
              whileInView="show"
              viewport={landingViewport.headline}
            >
              <motion.div variants={headLine}>
                <LandingEyebrow>System</LandingEyebrow>
              </motion.div>
              <motion.div variants={headLine} className="mt-5">
                <LandingDisplayH2 id="how-heading">
                  Sense, infer, adapt, learn
                </LandingDisplayH2>
              </motion.div>
              <motion.div variants={headLine}>
                <LandingProse className="mt-4 max-w-[28rem] lg:mt-6">
                  Four phases, one loop, executed on device. Transparent enough to trust; quiet enough to live beside.
                </LandingProse>
              </motion.div>
              <motion.p variants={headLine} className="mt-6 font-mono text-[11px] leading-relaxed text-[color:var(--landing-faint)]">
                LOCAL, READABLE CONFIDENCE, SCENE COHERENCE, FEEDBACK MEMORY
              </motion.p>
            </motion.div>
          </header>

          <div className="relative lg:col-span-8">
            {/* Spine + flow */}
            <motion.div
              className="pointer-events-none absolute left-[1.125rem] top-6 bottom-10 hidden w-px origin-top md:block"
              initial={reduceMotion ? false : { scaleY: 0.42, opacity: 0 }}
              whileInView={{ scaleY: 1, opacity: 1 }}
              viewport={landingViewport.section}
              transition={{ duration: landingDuration.spine, ease: landingEase.grounded }}
              aria-hidden
              style={{
                background:
                  "linear-gradient(to bottom, rgba(13,148,136,0.35), rgba(214,211,209,0.55), rgba(245,158,11,0.35))",
              }}
            />

            <ol className="relative space-y-0">
              {pipeline.map((step, i) => {
                const isRight = i % 2 === 1
                return (
                  <motion.li
                    key={step.key}
                    initial={
                      reduceMotion
                        ? false
                        : {
                            opacity: 0,
                            x: isRight ? 28 : -28,
                            y: 14,
                          }
                    }
                    whileInView={{ opacity: 1, x: 0, y: 0 }}
                    viewport={landingViewport.pipelineStep}
                    transition={{
                      duration: landingDuration.slow,
                      delay: reduceMotion ? 0 : i * 0.035,
                      ease: landingEase.lux,
                    }}
                    className={cn("relative pb-11 md:pb-16", i === pipeline.length - 1 && "pb-5 md:pb-7")}
                  >
                    <div className="flex gap-5 md:gap-8">
                      <div className="relative flex shrink-0 flex-col items-center md:w-10">
                        <span
                          className={cn(
                            "relative z-[1] flex size-9 items-center justify-center rounded-full border border-white/90 bg-white text-[13px] font-semibold shadow-[0_12px_28px_-16px_rgba(28,24,20,0.35)] md:size-10",
                            step.ring,
                            "ring-2 ring-offset-2 ring-offset-[color:var(--landing-canvas-deep)]",
                          )}
                          aria-hidden
                        >
                          <span className={cn("bg-gradient-to-br bg-clip-text text-transparent", step.accent)}>
                            {step.glyph}
                          </span>
                        </span>
                      </div>

                      <div
                        className={cn(
                          "min-w-0 flex-1 pt-0.5",
                          isRight ? "md:ml-[18%] md:max-w-[min(100%,26rem)]" : "md:mr-[12%] md:max-w-[min(100%,28rem)]",
                        )}
                      >
                        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                          <span className="font-mono text-[12px] font-medium tabular-nums text-[color:var(--landing-faint)]">
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          <h3
                            className={cn(
                              landingFontDisplay,
                              "text-[1.65rem] font-medium tracking-[-0.035em] text-[color:var(--landing-ink)] sm:text-[1.85rem]",
                            )}
                          >
                            {step.label}
                          </h3>
                        </div>
                        <p className="mt-4 text-[15px] leading-[1.68] text-[color:var(--landing-muted)]">{step.body}</p>
                        <motion.p
                          className={cn(
                            landingFontDisplay,
                            "mt-5 border-l-2 border-stone-300/80 pl-4 text-[0.9375rem] font-normal italic leading-snug text-[color:var(--landing-ink-soft)]",
                          )}
                          initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                          whileInView={{ opacity: 1, y: 0 }}
                          viewport={landingViewport.pipelineStep}
                          transition={{
                            duration: landingDuration.standard,
                            delay: reduceMotion ? 0 : 0.12 + i * 0.04,
                            ease: landingEase.lux,
                          }}
                        >
                          {step.aside}
                        </motion.p>
                      </div>
                    </div>

                    {i < pipeline.length - 1 ? (
                      <div
                        className={cn(
                          "pointer-events-none absolute left-[4.25rem] right-0 top-[60%] hidden h-px md:block",
                          isRight
                            ? "bg-gradient-to-l from-transparent via-stone-400/25 to-transparent"
                            : "bg-gradient-to-r from-transparent via-stone-400/25 to-transparent",
                        )}
                        aria-hidden
                      />
                    ) : null}
                  </motion.li>
                )
              })}
            </ol>

            <motion.div
              className="mt-2 md:pl-[4.5rem]"
              initial={reduceMotion ? false : { opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={landingViewport.card}
              transition={{ duration: landingDuration.micro, delay: reduceMotion ? 0 : 0.25, ease: landingEase.lux }}
            >
              <Link
                href="#room-states"
                className={cn(
                  "inline-flex items-center text-[13px] font-semibold text-[color:var(--landing-ink-soft)] underline-offset-[6px] transition-colors hover:text-[color:var(--landing-ink)]",
                  landingFocusRing,
                  "rounded-sm",
                )}
              >
                Explore moods
              </Link>
            </motion.div>
          </div>
        </div>
      </LandingContainer>
    </LandingSectionShell>
  )
}
