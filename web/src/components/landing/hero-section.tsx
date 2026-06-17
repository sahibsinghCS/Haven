"use client"

import { useEffect, useMemo, useRef } from "react"
import Link from "next/link"
import {
  motion,
  useMotionTemplate,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from "framer-motion"
import { ArrowRight } from "lucide-react"

import { ChapterSeamLink } from "@/components/landing/chapter-seam"
import { HavenLogo } from "@/components/brand/haven-logo"
import { HeroSceneCard } from "@/components/landing/hero-scene-card"
import {
  landingDuration,
  landingFadeLift,
  landingFadeUp,
  landingStaggerParent,
} from "@/components/landing/landing-motion"
import {
  landingBtnPrimaryHero,
  landingFocusRing,
  landingFontDisplay,
  LandingContainer,
  LandingEyebrow,
} from "@/components/landing/landing-primitives"
import { AmbientCursor } from "@/components/landing/ambient-cursor"
import { Magnetic, SplitText } from "@/components/landing/landing-text"
import { havenAppHref } from "@/lib/roomos/app-entry"
import { markLiveStartIntent } from "@/lib/roomos/live-session-start"
import { cn } from "@/lib/utils"

const heroTelemetry = [
  { label: "Video egress", value: "0", note: "Nothing leaves as video." },
  { label: "Moods", value: "5", note: "One envelope each." },
  { label: "Control plane", value: "1", note: "Light · air · thermal together." },
  { label: "Occupancy", value: "Present", note: null },
  { label: "Glare", value: "Low", note: null },
  { label: "Air", value: "Steady", note: null },
  { label: "Noise floor", value: "Quiet", note: null },
] as const

export function HeroSection() {
  const reduceMotion = useReducedMotion()
  const sectionRef = useRef<HTMLElement>(null)
  const mx = useMotionValue(52)
  const my = useMotionValue(42)
  const sx = useSpring(mx, { stiffness: 28, damping: 32, mass: 0.5 })
  const sy = useSpring(my, { stiffness: 28, damping: 32, mass: 0.5 })

  const glow = useMotionTemplate`radial-gradient(820px circle at ${sx}% ${sy}%, rgba(20,184,166,0.28), transparent 62%)`
  const pearl = useMotionTemplate`radial-gradient(620px ellipse at ${sx}% ${sy}%, rgba(255,248,232,0.18), transparent 58%)`

  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start start", "end start"],
  })
  const heroLift = useTransform(scrollYProgress, [0, 1], [0, -34])
  const roomLift = useTransform(scrollYProgress, [0, 1], [0, 42])
  const roomRotate = useTransform(scrollYProgress, [0, 1], [0, -1.8])
  const continueOpacity = useTransform(scrollYProgress, [0, 0.18], [1, 0])

  const copyStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.08, 0.08), [reduceMotion])
  const copyLine = useMemo(() => landingFadeUp(reduceMotion, { y: 22, duration: landingDuration.hero }), [reduceMotion])
  const visualReveal = useMemo(
    () => landingFadeLift(reduceMotion, { y: 36, scale: 0.982, duration: landingDuration.hero }),
    [reduceMotion],
  )

  const liveHref = havenAppHref("/live?start=1")

  useEffect(() => {
    if (reduceMotion) return
    const el = sectionRef.current
    if (!el) return
    const onMove = (event: PointerEvent) => {
      const r = el.getBoundingClientRect()
      mx.set(Math.min(100, Math.max(0, ((event.clientX - r.left) / r.width) * 100)))
      my.set(Math.min(100, Math.max(0, ((event.clientY - r.top) / r.height) * 100)))
    }
    el.addEventListener("pointermove", onMove)
    return () => el.removeEventListener("pointermove", onMove)
  }, [mx, my, reduceMotion])

  return (
    <section
      ref={sectionRef}
      id="hero"
      aria-labelledby="landing-hero-heading"
      className="relative flex min-h-[min(100dvh,920px)] flex-col overflow-x-clip bg-[#121110] pt-[5rem] text-[#fbf7ef] sm:pt-[5.5rem] lg:min-h-[100dvh] lg:pt-[5rem]"
    >
      <div
        className="pointer-events-none absolute inset-0 bg-[#121110]"
        style={{
          maskImage: "linear-gradient(180deg, black 0%, black 88%, transparent 100%)",
          WebkitMaskImage: "linear-gradient(180deg, black 0%, black 88%, transparent 100%)",
        }}
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_90%_62%_at_50%_-10%,rgba(255,247,231,0.16),transparent_58%),radial-gradient(ellipse_70%_58%_at_8%_28%,rgba(20,184,166,0.18),transparent_54%),radial-gradient(ellipse_72%_64%_at_92%_76%,rgba(245,158,11,0.12),transparent_58%),linear-gradient(180deg,#11100e_0%,#0e0d0b_32%,#151412_58%,#1c1a17_76%,#24211e_90%,#121110_100%)]"
        aria-hidden
      />
      {!reduceMotion ? (
        <div className="pointer-events-none absolute inset-0" aria-hidden>
          <motion.div className="absolute inset-0 opacity-80" style={{ background: glow }} />
          <motion.div className="absolute inset-0 opacity-90 mix-blend-screen" style={{ background: pearl }} />
        </div>
      ) : null}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.15]"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(255,255,255,0.18) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.12) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
          maskImage: "radial-gradient(ellipse 80% 55% at 50% 38%, black 0%, transparent 68%)",
          WebkitMaskImage: "radial-gradient(ellipse 80% 55% at 50% 38%, black 0%, transparent 68%)",
        }}
        aria-hidden
      />
      <HavenLogo
        variant="mark"
        size="hero"
        aria-hidden
        className="pointer-events-none absolute -right-[min(8vw,4rem)] top-[18%] z-[1] opacity-[0.07] mix-blend-screen blur-[0.5px] lg:right-[8%] lg:top-[14%] lg:opacity-[0.09]"
      />

      <motion.div
        className="relative z-10 flex flex-1 flex-col justify-center py-8 lg:py-10"
        style={reduceMotion ? undefined : { y: heroLift }}
      >
        <LandingContainer className="grid w-full grid-cols-1 gap-10 lg:grid-cols-12 lg:items-center lg:gap-8 xl:gap-12">
          <motion.div
            className="relative z-[2] max-w-[42rem] lg:col-span-5 lg:max-w-none"
            variants={copyStagger}
            initial="hidden"
            animate="show"
          >
            <motion.div variants={copyLine} className="flex flex-wrap items-center gap-3">
              <span className="font-mono text-[12px] font-semibold tabular-nums text-teal-200/70">01</span>
              <span className="h-3 w-px bg-white/18" aria-hidden />
              <LandingEyebrow className="m-0 text-teal-50/70">Private ambient intelligence</LandingEyebrow>
            </motion.div>

            <motion.h1
              id="landing-hero-heading"
              variants={copyLine}
              className={cn(landingFontDisplay, "mt-7 max-w-[18ch] text-balance text-[#fff9ed]")}
            >
              <SplitText
                as="span"
                text="HAVEN"
                immediate
                delay={0.18}
                stagger={0.06}
                y={36}
                tilt
                shimmer
                glossChars
                shimmerColor="rgba(255,247,231,0.9)"
                className="block text-[clamp(3.35rem,9.5vw,6.35rem)] font-semibold leading-[0.9] tracking-[0.04em]"
              />
              <SplitText
                as="span"
                text="learns your rhythm."
                immediate
                delay={0.62}
                stagger={0.018}
                y={18}
                tilt={false}
                className="mt-2 block text-[clamp(1.7rem,4.1vw,2.85rem)] font-medium leading-[1.08] tracking-[-0.03em] text-stone-200/92"
              />
            </motion.h1>

            <motion.p
              variants={copyLine}
              className="mt-6 max-w-[30rem] text-pretty text-[1.02rem] font-semibold leading-snug tracking-[-0.018em] text-teal-50/88 sm:text-[1.1rem]"
            >
              Local context, one composed scene: light, air, and warmth moving together.
            </motion.p>

            <motion.p
              variants={copyLine}
              className="mt-3 max-w-[28rem] text-pretty text-[0.9375rem] leading-[1.65] text-stone-300/78 sm:text-[0.97rem]"
            >
              No dashboards. No feeds. A room that quietly improves when you nudge it.
            </motion.p>

            <motion.div
              variants={copyLine}
              className="mt-9 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center"
            >
              <Magnetic strength={0.28} radius={140}>
                <Link
                  href={liveHref}
                  onClick={() => markLiveStartIntent()}
                  data-cursor="hover"
                  className={cn(
                    landingBtnPrimaryHero,
                    landingFocusRing,
                    "group/cta relative isolate overflow-hidden w-full border-white/12 bg-[linear-gradient(168deg,#fff7ea_0%,#d7c6ad_46%,#8b7a63_100%)] text-[#15120e] shadow-[0_18px_52px_-18px_rgba(245,222,179,0.45),inset_0_1px_0_rgba(255,255,255,0.72)] ring-white/28 sm:w-auto",
                  )}
                >
                  <span
                    className="pointer-events-none absolute inset-0 -translate-x-full bg-[linear-gradient(110deg,transparent_0%,rgba(255,255,255,0.55)_50%,transparent_100%)] transition-transform duration-700 ease-out group-hover/cta:translate-x-full"
                    aria-hidden
                  />
                  <span className="relative">Open live view</span>
                  <ArrowRight
                    className="relative size-[1.05rem] transition-transform duration-300 group-hover/cta:translate-x-0.5"
                    strokeWidth={2}
                    aria-hidden
                  />
                </Link>
              </Magnetic>
              <Magnetic strength={0.22} radius={120}>
                <a
                  href="#how-it-works"
                  data-cursor="hover"
                  className={cn(
                    "group inline-flex items-center justify-center gap-2 rounded-full border border-white/12 bg-white/[0.06] px-5 py-3 text-[13px] font-semibold text-stone-100/82 shadow-[inset_0_1px_0_rgba(255,255,255,0.07)] backdrop-blur-md transition-[transform,color,background-color] duration-300 hover:bg-white/[0.1] hover:text-white motion-safe:hover:-translate-y-px",
                    landingFocusRing,
                  )}
                >
                  See the loop
                  <ArrowRight className="size-4 opacity-70 transition-transform duration-300 group-hover:translate-x-0.5" />
                </a>
              </Magnetic>
            </motion.div>
          </motion.div>

          <motion.div
            variants={visualReveal}
            initial="hidden"
            animate="show"
            className="relative z-[1] lg:col-span-7"
            style={reduceMotion ? undefined : { y: roomLift, rotate: roomRotate }}
          >
            <HeroSceneCard />
          </motion.div>
        </LandingContainer>
      </motion.div>

      <motion.div
        variants={copyLine}
        initial="hidden"
        animate="show"
        className="relative z-10 mt-auto w-full pb-6"
      >
        <LandingContainer>
          <p className="mb-3 text-center font-mono text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-500 sm:mb-4 sm:text-left">
            At a glance
          </p>
          <div className="rounded-[1.2rem] border border-white/[0.1] bg-gradient-to-b from-white/[0.08] to-white/[0.03] p-px shadow-[0_24px_70px_-40px_rgba(0,0,0,0.75),inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-xl sm:rounded-[1.35rem] md:backdrop-blur-xl">
            <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[1.12rem] bg-white/[0.12] sm:grid-cols-4 lg:grid-cols-7">
              {heroTelemetry.map((cell) => (
                <div
                  key={cell.label}
                  className="relative flex min-h-[6.75rem] flex-col justify-between gap-2 bg-[#141210]/95 px-3.5 py-4 sm:min-h-[7rem] sm:px-4 sm:py-4"
                >
                  <p className="font-mono text-[10px] font-semibold uppercase leading-snug tracking-[0.2em] text-stone-500">
                    {cell.label}
                  </p>
                  <div>
                    <p
                      className={cn(
                        landingFontDisplay,
                        "text-[1.35rem] font-semibold leading-[1.15] tracking-[-0.03em] text-[#fff7ea] sm:text-[1.5rem]",
                      )}
                    >
                      {cell.value}
                    </p>
                    {cell.note ? (
                      <p className="mt-1.5 text-[11px] leading-snug text-stone-500/90">{cell.note}</p>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <motion.div
            className="mt-5 flex justify-center sm:mt-6"
            style={reduceMotion ? undefined : { opacity: continueOpacity }}
          >
            <ChapterSeamLink />
          </motion.div>
        </LandingContainer>
      </motion.div>

      <AmbientCursor />
    </section>
  )
}
