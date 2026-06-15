"use client"

import Link from "next/link"
import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { Fan, SlidersHorizontal, Thermometer } from "lucide-react"

import {
  landingDuration,
  landingEase,
  landingFadeLift,
  landingFadeUp,
  landingStaggerParent,
  landingViewport,
} from "@/components/landing/landing-motion"
import {
  landingBtnPrimaryMd,
  landingFocusRing,
  landingFontDisplay,
  LandingContainer,
  LandingDisplayH2,
  LandingEyebrow,
  LandingSectionShell,
} from "@/components/landing/landing-primitives"
import { ROOM_STATE_LABEL, ROOM_STATE_LANDING_SKIN } from "@/lib/roomos/state-meta"
import { cn } from "@/lib/utils"
import { ROOM_STATE_ORDER, type KnownRoomStateId } from "@/types/roomos"

const PREVIEW: Record<
  KnownRoomStateId,
  { hex: string; brightness: number; temp: number; fan: boolean }
> = {
  sleep: { hex: "#4f46e5", brightness: 22, temp: 68, fan: false },
  work: { hex: "#38bdf8", brightness: 82, temp: 72, fan: true },
  relaxing: { hex: "#14b8a6", brightness: 44, temp: 73, fan: true },
  away: { hex: "#a8a29e", brightness: 18, temp: 69, fan: false },
}

export function PreferencesPreviewSection() {
  const reduceMotion = useReducedMotion()
  const headStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.07, 0.05), [reduceMotion])
  const headLine = useMemo(() => landingFadeUp(reduceMotion, { y: 14, duration: landingDuration.standard }), [reduceMotion])
  const tileStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.08, 0.04), [reduceMotion])
  const tileLift = useMemo(() => landingFadeLift(reduceMotion, { y: 18, scale: 0.992, duration: landingDuration.slow }), [reduceMotion])

  return (
    <LandingSectionShell id="preferences-preview" labelledBy="prefs-preview-heading">
      <div
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(198deg,rgba(224,242,249,0.32)_0%,var(--landing-canvas-pearl)_48%,var(--landing-canvas-mist)_100%)]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-sky-400/25 via-transparent to-stone-400/30"
        aria-hidden
      />

      <LandingContainer className="relative">
        <motion.div
          className="max-w-2xl"
          variants={headStagger}
          initial="hidden"
          whileInView="show"
          viewport={landingViewport.headline}
        >
            <motion.div variants={headLine}>
              <LandingEyebrow>Preferences</LandingEyebrow>
            </motion.div>
            <motion.div variants={headLine} className="mt-5">
              <LandingDisplayH2 id="prefs-preview-heading">Defaults you can still refine</LandingDisplayH2>
            </motion.div>
            <motion.p variants={headLine} className="mt-5 text-[16px] leading-[1.68] text-[color:var(--landing-muted)] sm:text-[17px]">
              Each mood keeps its own envelope. Haven proposes baselines; you set light, airflow, and thermal targets that
              match how you actually live.
            </motion.p>
            <motion.div variants={headLine} className="mt-8 flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-center sm:gap-6">
              <Link
                href="/preferences"
                className={cn(landingBtnPrimaryMd, landingFocusRing, "inline-flex w-fit items-center gap-2")}
              >
                <SlidersHorizontal className="size-4 opacity-90" strokeWidth={2} aria-hidden />
                Open preferences
              </Link>
              <p
                className={cn(
                  landingFontDisplay,
                  "text-[14px] italic leading-snug text-[color:var(--landing-muted)] sm:max-w-[20rem] sm:text-[15px] lg:ml-auto lg:text-right",
                )}
              >
                Five moods, five authored envelopes.
              </p>
            </motion.div>
        </motion.div>

        {/* Product tiles: grid keeps cards wide enough so labels never clip */}
        <motion.div
          className="mt-11 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5 xl:gap-5"
          variants={tileStagger}
          initial="hidden"
          whileInView="show"
          viewport={landingViewport.section}
        >
          {ROOM_STATE_ORDER.map((id, i) => {
            const row = PREVIEW[id]
            const skin = ROOM_STATE_LANDING_SKIN[id]
            return (
              <motion.article
                key={id}
                variants={tileLift}
                className={cn(
                  "relative flex min-h-0 flex-col rounded-[1.35rem] border border-[color:var(--landing-line-strong)] bg-[linear-gradient(165deg,rgba(255,253,250,0.96)_0%,rgba(249,246,240,0.9)_100%)] p-5 shadow-[var(--landing-shadow-card)] backdrop-blur-md sm:p-6",
                  "ring-1 ring-[color:var(--landing-edge-light)]",
                  id === "away" && "opacity-[0.92] saturate-[0.88]",
                )}
              >
                <div className={cn("absolute left-0 top-6 h-[calc(100%-3rem)] w-[3px] rounded-full", skin.bar)} aria-hidden />
                <header className="min-w-0 pl-4 pr-1">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[color:var(--landing-faint)]">
                    Mood
                  </p>
                  <h3
                    className={cn(
                      landingFontDisplay,
                      "mt-2 text-lg font-medium tracking-[-0.025em] text-[color:var(--landing-ink)] sm:text-xl",
                    )}
                  >
                    {ROOM_STATE_LABEL[id]}
                  </h3>
                </header>

                <div className="mt-5 flex min-w-0 flex-1 flex-col gap-4 pl-4 pr-2 sm:flex-row sm:items-stretch sm:pr-3">
                  <div
                    className="relative mx-auto size-14 shrink-0 rounded-2xl border border-white/80 shadow-[inset_0_2px_8px_rgba(255,255,255,0.55)] sm:mx-0"
                    style={{
                      background: `radial-gradient(circle at 30% 25%, rgba(255,255,255,0.65), transparent), ${row.hex}`,
                    }}
                  />
                  <div className="min-w-0 flex-1 space-y-3">
                    <div className="min-w-0">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-[color:var(--landing-faint)]">
                        Brightness
                      </p>
                      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-stone-200/95">
                        <motion.div
                          className="h-full rounded-full bg-gradient-to-r from-stone-700/45 to-teal-700/55"
                          initial={reduceMotion ? false : { scaleX: 0 }}
                          whileInView={{ scaleX: 1 }}
                          viewport={landingViewport.tactile}
                          transition={{
                            duration: 0.82,
                            delay: reduceMotion ? 0 : 0.06 + i * 0.05,
                            ease: landingEase.lux,
                          }}
                          style={{ width: `${row.brightness}%`, transformOrigin: "left center" }}
                        />
                      </div>
                    </div>
                    <div className="flex min-w-0 flex-col gap-2 text-[13px] leading-tight text-[color:var(--landing-muted)] sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-4 sm:gap-y-1">
                      <span className="inline-flex min-w-0 shrink-0 items-center gap-1.5 tabular-nums">
                        <Thermometer className="size-3.5 shrink-0 text-teal-800/65" strokeWidth={1.75} aria-hidden />
                        {row.temp}°F
                      </span>
                      <span className="inline-flex min-w-0 items-center gap-1.5">
                        <Fan className="size-3.5 shrink-0 text-sky-800/60" strokeWidth={1.75} aria-hidden />
                        <span className="truncate">{row.fan ? "Air on" : "Still"}</span>
                      </span>
                    </div>
                  </div>
                </div>
              </motion.article>
            )
          })}
        </motion.div>

        <p className="mt-6 max-w-[52rem] text-center text-[13px] leading-relaxed text-[color:var(--landing-muted)] sm:mt-7 sm:text-left">
          Illustrative snapshot: live preferences include presets, finer controls, and per room lanes as the product matures.
        </p>
      </LandingContainer>
    </LandingSectionShell>
  )
}
