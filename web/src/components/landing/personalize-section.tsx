"use client"

import Link from "next/link"
import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { ArrowRight, SlidersHorizontal } from "lucide-react"

import {
  landingDuration,
  landingEase,
  landingFadeLift,
  landingFadeUp,
  landingStaggerParent,
  landingViewport,
} from "@/components/landing/landing-motion"
import {
  landingBtnOutline,
  landingFocusRing,
  landingFontDisplay,
  LandingContainer,
  LandingDisplayH2,
  LandingSectionShell,
} from "@/components/landing/landing-primitives"
import { cn } from "@/lib/utils"

const beats = [
  {
    phase: "Correction",
    description: "You nudge the gradient once while focusing. Haven reads it as intent, not noise.",
  },
  {
    phase: "Memory",
    description: "Preferences compound on device; the space develops its own comfort dialect.",
  },
  {
    phase: "Adaptation",
    description: "Later, baselines arrive softer, without a survey or a guilt trip.",
  },
] as const

export function PersonalizeSection() {
  const reduceMotion = useReducedMotion()
  const headStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.08, 0.07), [reduceMotion])
  const headPiece = useMemo(() => landingFadeUp(reduceMotion, { y: 18, duration: landingDuration.slow }), [reduceMotion])
  const beatStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.12, 0.06), [reduceMotion])
  const beatCard = useMemo(() => landingFadeLift(reduceMotion, { y: 22, scale: 0.988, duration: landingDuration.slow }), [reduceMotion])

  return (
    <LandingSectionShell id="personalization" labelledBy="personal-heading">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_70%_50%_at_20%_80%,rgba(167,139,250,0.075),transparent_52%),radial-gradient(ellipse_55%_45%_at_88%_15%,rgba(253,224,71,0.065),transparent_48%),linear-gradient(180deg,var(--landing-canvas-pearl)_0%,var(--landing-canvas)_100%)]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-violet-400/20 via-transparent to-amber-300/25"
        aria-hidden
      />

      <LandingContainer className="relative">
        <motion.div
          className="mx-auto max-w-2xl text-center"
          variants={headStagger}
          initial="hidden"
          whileInView="show"
          viewport={landingViewport.headline}
        >
          <motion.div variants={headPiece} className="flex justify-center">
            <span className="inline-flex items-center rounded-full border border-violet-200/75 bg-[color-mix(in_oklab,var(--landing-surface)_88%,transparent)] px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-violet-950/85 shadow-[var(--landing-shadow-card)] backdrop-blur-md">
              Personalization
            </span>
          </motion.div>
          <motion.div variants={headPiece} className="mt-7">
            <LandingDisplayH2 id="personal-heading">Defaults that learn from your corrections</LandingDisplayH2>
          </motion.div>
          <motion.p
            variants={headPiece}
            className="mt-5 text-[17px] leading-[1.65] text-[color:var(--landing-muted)] sm:text-lg"
          >
            Haven doesn&apos;t run questionnaires. It notices posture. Small adjustments rewrite baselines until the room
            feels authored, not assigned.
          </motion.p>
        </motion.div>

        {/* Light memory strip (product metaphor) */}
        <motion.div
          className="relative mx-auto mt-11 max-w-3xl overflow-hidden rounded-2xl border border-[color:var(--landing-line-strong)] bg-[color-mix(in_oklab,var(--landing-surface)_82%,transparent)] p-6 shadow-[var(--landing-shadow-float)] backdrop-blur-md ring-1 ring-[color:var(--landing-edge-light)] sm:mt-12 sm:p-8"
          initial={reduceMotion ? false : { opacity: 0, y: 26, scale: 0.987 }}
          whileInView={{ opacity: 1, y: 0, scale: 1 }}
          viewport={landingViewport.section}
          transition={{ duration: landingDuration.slow, ease: landingEase.velvet, delay: reduceMotion ? 0 : 0.06 }}
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[color:var(--landing-faint)]">
              Tone memory
            </p>
            <span className="rounded-md bg-stone-900/[0.06] px-2 py-1 font-mono text-[11px] text-[color:var(--landing-muted)]">
              Focus to evening
            </span>
          </div>
          <div className="relative mt-6 rounded-xl border border-[color:var(--landing-line)] bg-gradient-to-r from-amber-50/95 via-white to-sky-50/90 px-4 py-4 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.92)] sm:px-5 sm:py-5">
            <p className="relative z-[1] text-pretty text-[13px] font-medium leading-[1.65] text-[color:var(--landing-ink-soft)] sm:text-[14px] sm:leading-[1.7]">
              After two{" "}
              <span className="rounded-md bg-gradient-to-r from-amber-200/95 to-amber-100/75 px-1.5 py-0.5 text-[color:var(--landing-ink)] shadow-[0_1px_0_rgba(255,255,255,0.65)] [box-decoration-break:clone]">
                light corrections
              </span>
              , scenes drift{" "}
              <span className="rounded-md bg-gradient-to-r from-sky-200/90 to-teal-100/75 px-1.5 py-0.5 text-[color:var(--landing-ink)] shadow-[0_1px_0_rgba(255,255,255,0.65)] [box-decoration-break:clone]">
                cooler and softer
              </span>
              , without another prompt.
            </p>
          </div>
        </motion.div>

        {/* Story beats (not duplicate cards) */}
        <motion.div
          className="mx-auto mt-14 grid max-w-5xl gap-5 sm:gap-6 lg:mt-[3.75rem] lg:grid-cols-3 lg:gap-7"
          variants={beatStagger}
          initial="hidden"
          whileInView="show"
          viewport={landingViewport.section}
        >
          {beats.map((beat, i) => (
            <motion.div
              key={beat.phase}
              variants={beatCard}
              className={cn(
                "relative rounded-2xl border bg-[color-mix(in_oklab,var(--landing-surface)_78%,transparent)] p-7 shadow-[var(--landing-shadow-card)] ring-1 ring-[color:var(--landing-edge-light)] backdrop-blur-md",
                i === 0 && "border-teal-200/65 lg:translate-y-3",
                i === 1 && "border-violet-200/58 lg:-translate-y-1",
                i === 2 && "border-amber-200/58 lg:translate-y-2",
              )}
            >
              {i < beats.length - 1 ? (
                <motion.span
                  className="pointer-events-none absolute -right-4 top-1/2 hidden -translate-y-1/2 text-[color:var(--landing-faint)] lg:block"
                  aria-hidden
                  initial={reduceMotion ? false : { opacity: 0, x: -6 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={landingViewport.card}
                  transition={{
                    duration: landingDuration.micro,
                    delay: reduceMotion ? 0 : 0.2 + i * 0.15,
                    ease: landingEase.lux,
                  }}
                >
                  <ArrowRight className="size-5" strokeWidth={1.5} />
                </motion.span>
              ) : null}
              <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.2em] text-[color:var(--landing-faint)]">
                {String(i + 1).padStart(2, "0")}
              </p>
              <p className={cn(landingFontDisplay, "mt-4 text-xl font-medium tracking-[-0.02em] text-[color:var(--landing-ink)]")}>
                {beat.phase}
              </p>
              <p className="mt-3 text-[14px] leading-[1.66] text-[color:var(--landing-muted)]">{beat.description}</p>
            </motion.div>
          ))}
        </motion.div>

        <motion.div
          className="mt-11 flex flex-col items-center justify-center gap-5 border-t border-[color:var(--landing-line)] pt-10 text-center sm:flex-row sm:gap-10 lg:mt-12 lg:pt-11"
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={landingViewport.section}
          transition={{ duration: landingDuration.standard, ease: landingEase.lux, delay: reduceMotion ? 0 : 0.12 }}
        >
          <p className="max-w-md text-[14px] leading-relaxed text-[color:var(--landing-muted)]">
            Preferences stay on this device. Haven is explicit about what it knows, and
            where uncertainty remains.
          </p>
          <Link
            href="/preferences"
            className={cn(landingBtnOutline, landingFocusRing, "inline-flex h-11 shrink-0 items-center gap-2")}
          >
            <SlidersHorizontal className="size-4" strokeWidth={1.75} aria-hidden />
            Tune moods
          </Link>
        </motion.div>
      </LandingContainer>
    </LandingSectionShell>
  )
}
