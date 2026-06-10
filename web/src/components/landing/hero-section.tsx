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
import {
  Activity,
  ArrowRight,
  Briefcase,
  ChevronDown,
  DoorOpen,
  Gamepad2,
  Lightbulb,
  LockKeyhole,
  Moon,
  Palmtree,
  Shield,
  Sparkles,
  Thermometer,
  Wind,
} from "lucide-react"

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
import { markLiveStartIntent } from "@/lib/roomos/live-session-start"
import { cn } from "@/lib/utils"

const moodStrip = [
  { id: "sleep", label: "Sleep", Icon: Moon },
  { id: "gaming", label: "Gaming", Icon: Gamepad2 },
  { id: "work", label: "Work", Icon: Briefcase, active: true },
  { id: "relax", label: "Relax", Icon: Palmtree },
  { id: "away", label: "Away", Icon: DoorOpen },
] as const

const sceneRows = [
  { label: "Light field", value: "74%", Icon: Lightbulb, tone: "text-amber-200" },
  { label: "Airflow", value: "gentle", Icon: Wind, tone: "text-sky-200" },
  { label: "Target", value: "72F", Icon: Thermometer, tone: "text-teal-200" },
] as const

/** One rail: posture + room read — same typography, no clipping, no overlap with scroll */
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
  const continueOpacity = useTransform(scrollYProgress, [0, 0.14], [1, 0])

  const copyStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.08, 0.08), [reduceMotion])
  const copyLine = useMemo(() => landingFadeUp(reduceMotion, { y: 22, duration: landingDuration.hero }), [reduceMotion])
  const visualReveal = useMemo(
    () => landingFadeLift(reduceMotion, { y: 36, scale: 0.982, duration: landingDuration.hero }),
    [reduceMotion],
  )

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
      className="relative flex min-h-[100dvh] flex-col justify-center overflow-hidden bg-[#121110] pt-[5rem] pb-28 text-[#fbf7ef] sm:pt-[5.5rem] sm:pb-32 lg:pt-[5rem] lg:pb-24"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_90%_62%_at_50%_-10%,rgba(255,247,231,0.16),transparent_58%),radial-gradient(ellipse_70%_58%_at_8%_28%,rgba(20,184,166,0.18),transparent_54%),radial-gradient(ellipse_72%_64%_at_92%_76%,rgba(245,158,11,0.12),transparent_58%),linear-gradient(180deg,#11100e_0%,#0e0d0b_32%,#151412_58%,#1c1a17_78%,#23211e_92%,#2a2724_100%)]" />
      {!reduceMotion ? (
        <>
          <motion.div className="pointer-events-none absolute inset-0 opacity-80" style={{ background: glow }} />
          <motion.div className="pointer-events-none absolute inset-0 opacity-90 mix-blend-screen" style={{ background: pearl }} />
        </>
      ) : null}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.15]"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(255,255,255,0.18) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.12) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
          maskImage: "radial-gradient(ellipse 80% 64% at 50% 44%, black 0%, transparent 72%)",
        }}
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-[min(38vh,15rem)] sm:h-[min(36vh,17rem)]"
        style={{
          background: `linear-gradient(
            180deg,
            transparent 0%,
            rgba(18, 17, 15, 0.22) 14%,
            rgba(32, 29, 26, 0.55) 32%,
            rgba(48, 44, 40, 0.72) 52%,
            rgba(72, 66, 58, 0.55) 68%,
            rgba(120, 110, 98, 0.28) 82%,
            rgba(190, 182, 168, 0.2) 91%,
            color-mix(in oklab, var(--landing-canvas-pearl) 94%, #c4bbb0) 97%,
            var(--landing-canvas-pearl) 100%
          )`,
        }}
        aria-hidden
      />

      <motion.div
        className="relative z-10 w-full flex-1 py-8 lg:flex lg:items-center lg:py-10"
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
              <LandingEyebrow className="m-0 text-teal-50/70">
                Private ambient intelligence
              </LandingEyebrow>
            </motion.div>

            <motion.h1
              id="landing-hero-heading"
              variants={copyLine}
              className={cn(
                landingFontDisplay,
                "mt-7 max-w-[18ch] text-balance text-[#fff9ed]",
              )}
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
                  href="/live?start=1"
                  onClick={() => markLiveStartIntent()}
                  data-cursor="hover"
                  className={cn(
                    landingBtnPrimaryHero,
                    landingFocusRing,
                    "group/cta relative isolate overflow-hidden w-full border-white/12 bg-[linear-gradient(168deg,#fff7ea_0%,#d7c6ad_46%,#8b7a63_100%)] text-[#15120e] shadow-[0_18px_52px_-18px_rgba(245,222,179,0.45),inset_0_1px_0_rgba(255,255,255,0.72)] ring-white/28 sm:w-auto",
                  )}
                >
                  <span className="pointer-events-none absolute inset-0 -translate-x-full bg-[linear-gradient(110deg,transparent_0%,rgba(255,255,255,0.55)_50%,transparent_100%)] transition-transform duration-700 ease-out group-hover/cta:translate-x-full" aria-hidden />
                  <span className="relative">Open live view</span>
                  <ArrowRight className="relative size-[1.05rem] transition-transform duration-300 group-hover/cta:translate-x-0.5" strokeWidth={2} aria-hidden />
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
            <div className="landing-breathe pointer-events-none absolute -inset-8 rounded-[3rem] bg-[radial-gradient(ellipse_at_center,rgba(20,184,166,0.28),transparent_62%)] blur-2xl" />
            <div className="relative mx-auto max-w-[44rem] overflow-hidden rounded-[2.25rem] border border-white/[0.12] bg-[linear-gradient(150deg,rgba(255,255,255,0.11),rgba(255,255,255,0.035)_36%,rgba(255,255,255,0.02))] p-2 shadow-[0_46px_120px_-44px_rgba(0,0,0,0.88),0_0_0_1px_rgba(255,255,255,0.04)] backdrop-blur-2xl">
              <div className="overflow-hidden rounded-[1.8rem] border border-white/[0.08] bg-[#0e0c0a] shadow-[inset_0_1px_0_rgba(255,255,255,0.07)]">
                <div className="flex h-12 items-center gap-3 border-b border-white/[0.07] bg-white/[0.045] px-4">
                  <div className="flex gap-1.5" aria-hidden>
                    <span className="size-2 rounded-full bg-white/18" />
                    <span className="size-2 rounded-full bg-white/12" />
                    <span className="size-2 rounded-full bg-white/10" />
                  </div>
                  <p className="min-w-0 flex-1 truncate text-center text-[12px] font-semibold tracking-[-0.01em] text-stone-200/90">
                    Haven scene engine
                  </p>
                  <span className="rounded-full border border-teal-300/18 bg-teal-300/[0.08] px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-[0.22em] text-teal-100/72">
                    Local
                  </span>
                </div>

                <div className="relative min-h-[430px] overflow-hidden sm:min-h-[500px]">
                  <div className="absolute inset-0 bg-[linear-gradient(165deg,#f6efe2_0%,#d5c4aa_42%,#6e7f73_78%,#15120f_100%)]" />
                  <div className="absolute inset-0 bg-[radial-gradient(ellipse_65%_55%_at_42%_34%,rgba(255,255,255,0.86),transparent_58%),radial-gradient(ellipse_64%_48%_at_72%_70%,rgba(20,184,166,0.34),transparent_60%),radial-gradient(ellipse_52%_45%_at_18%_82%,rgba(245,158,11,0.24),transparent_56%)]" />
                  <div className="absolute inset-x-[-10%] bottom-[-8%] h-[46%] rounded-[50%] bg-[radial-gradient(ellipse_at_center,rgba(10,8,6,0.5),transparent_66%)]" />

                  <div className="absolute left-[8%] top-[11%] w-[min(84%,29rem)] rounded-[2rem] border border-white/58 bg-white/[0.72] p-5 text-stone-950 shadow-[0_34px_90px_-38px_rgba(0,0,0,0.54),inset_0_1px_0_rgba(255,255,255,0.8)] backdrop-blur-2xl sm:left-[9%] sm:p-6">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-stone-500">
                          Current read
                        </p>
                        <h2 className={cn(landingFontDisplay, "mt-2 text-[2rem] font-semibold tracking-[-0.045em] sm:text-[2.35rem]")}>
                          Work / Studying
                        </h2>
                        <p className="mt-2 max-w-[21rem] text-[12.5px] leading-relaxed text-stone-600">
                          Ambient posture favors clarity: high field light, softened glare, gentle air.
                        </p>
                      </div>
                      <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-teal-900/12 bg-teal-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-teal-900">
                        <Sparkles className="size-3" aria-hidden />
                        87%
                      </span>
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-3">
                      {sceneRows.map((row) => (
                        <div
                          key={row.label}
                          className="rounded-2xl border border-stone-200/90 bg-white/72 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.76)]"
                        >
                          <row.Icon className={cn("size-4", row.tone === "text-amber-200" ? "text-amber-700" : row.tone === "text-sky-200" ? "text-sky-700" : "text-teal-700")} strokeWidth={1.8} />
                          <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.14em] text-stone-500">
                            {row.label}
                          </p>
                          <p className="mt-1 text-[14px] font-semibold tracking-[-0.01em] text-stone-950">
                            {row.value}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="absolute bottom-[19%] right-[6%] w-[min(72%,18rem)] rounded-[1.5rem] border border-white/16 bg-[#11100e]/86 p-4 text-stone-100 shadow-[0_26px_70px_-34px_rgba(0,0,0,0.8)] backdrop-blur-xl">
                    <div className="flex items-center justify-between gap-3">
                      <span className="inline-flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-teal-100/72">
                        <Shield className="size-3.5" aria-hidden />
                        Privacy boundary
                      </span>
                      <LockKeyhole className="size-4 text-teal-100/70" aria-hidden />
                    </div>
                    <p className="mt-3 text-[12px] leading-relaxed text-stone-300/84">
                      Raw signal stays in the room. The interface exposes confidence, not a feed.
                    </p>
                  </div>

                  <div className="absolute bottom-5 left-5 right-5 rounded-[1.35rem] border border-white/[0.12] bg-[#0c0a08]/78 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mr-1 inline-flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400">
                        <Activity className="size-3.5 text-teal-200/70" aria-hidden />
                        Moods
                      </span>
                      {moodStrip.map((mood) => (
                        <span
                          key={mood.id}
                          className={cn(
                            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10.5px] font-semibold",
                            "active" in mood && mood.active
                              ? "border-teal-200/34 bg-teal-200/[0.12] text-teal-50 shadow-[0_0_24px_rgba(45,212,191,0.13)]"
                              : "border-white/[0.09] bg-white/[0.04] text-stone-400",
                          )}
                        >
                          <mood.Icon className="size-3" strokeWidth={2} aria-hidden />
                          {mood.label}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          <motion.div
            variants={copyLine}
            initial="hidden"
            animate="show"
            className="lg:col-span-12"
          >
            <div className="mt-8 lg:mt-10">
              <p className="mb-3 text-center font-mono text-[10px] font-semibold uppercase tracking-[0.28em] text-stone-500 sm:mb-4 sm:text-left">
                At a glance
              </p>
              <div className="rounded-[1.2rem] border border-white/[0.1] bg-gradient-to-b from-white/[0.08] to-white/[0.03] p-px shadow-[0_24px_70px_-40px_rgba(0,0,0,0.75),inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-xl sm:rounded-[1.35rem]">
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
            </div>

            <motion.div
              className="mt-6 flex justify-center sm:mt-8"
              style={reduceMotion ? undefined : { opacity: continueOpacity }}
            >
              <a
                href="#how-it-works"
                className={cn(
                  "group inline-flex items-center gap-2 rounded-full border border-white/[0.1] bg-white/[0.06] px-4 py-2 text-[10.5px] font-semibold uppercase tracking-[0.22em] text-stone-200/78 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-xl transition-[color,transform,background-color] duration-300 hover:bg-white/[0.1] hover:text-white motion-safe:hover:-translate-y-px",
                  landingFocusRing,
                )}
              >
                <span className="relative flex size-1.5" aria-hidden>
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-teal-200/50 motion-reduce:hidden" />
                  <span className="relative inline-flex size-1.5 rounded-full bg-teal-200/90" />
                </span>
                Continue
                <ChevronDown className="size-3.5 opacity-70 transition-transform duration-300 group-hover:translate-y-0.5" strokeWidth={2.25} aria-hidden />
              </a>
            </motion.div>
          </motion.div>
        </LandingContainer>
      </motion.div>

      <AmbientCursor />
    </section>
  )
}
