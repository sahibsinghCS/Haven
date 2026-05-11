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
  ArrowRight,
  Lightbulb,
  Moon,
  Palmtree,
  Sparkles,
  Thermometer,
  Wind,
  Gamepad2,
  Briefcase,
  DoorOpen,
} from "lucide-react"

import {
  landingDuration,
  landingFadeScale,
  landingFadeUp,
  landingStaggerParent,
} from "@/components/landing/landing-motion"
import {
  landingBtnPrimaryHero,
  landingFocusRing,
  landingFontDisplay,
  landingHeroSecondaryLink,
  LandingContainer,
  LandingEyebrow,
} from "@/components/landing/landing-primitives"
import { cn } from "@/lib/utils"

const moodStrip = [
  { id: "sleep", label: "Sleep", Icon: Moon },
  { id: "gaming", label: "Gaming", Icon: Gamepad2 },
  { id: "work", label: "Work", Icon: Briefcase, active: true },
  { id: "relax", label: "Relax", Icon: Palmtree },
  { id: "away", label: "Away", Icon: DoorOpen },
] as const

export function HeroSection() {
  const reduceMotion = useReducedMotion()
  const sectionRef = useRef<HTMLElement>(null)
  const mx = useMotionValue(48)
  const my = useMotionValue(38)
  const sx = useSpring(mx, { stiffness: 30, damping: 30, mass: 0.5 })
  const sy = useSpring(my, { stiffness: 30, damping: 30, mass: 0.5 })

  const driftX = useMotionValue(0)
  const driftY = useMotionValue(0)

  const fragParallax = useTransform([sx, sy, driftX, driftY], ([x, y, dx, dy]) => {
    const px = (Number(x) - 50) * -0.06 + Number(dx) * 0.012
    const py = (Number(y) - 50) * -0.05 + Number(dy) * 0.01
    return `translate3d(${px}px, ${py}px, 0)`
  })

  const wash = useMotionTemplate`radial-gradient(720px circle at ${sx}% ${sy}%, rgba(15,118,110,0.12), transparent 58%)`
  const bloom = useMotionTemplate`radial-gradient(520px ellipse at ${sx}% ${sy}%, rgba(255,255,255,0.72), transparent 52%)`

  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start start", "end start"],
  })
  const heroLift = useTransform(scrollYProgress, [0, 1], [0, -28])
  const exploreOpacity = useTransform(scrollYProgress, [0, 0.15], [1, 0])
  const bgParallaxDeep = useTransform(scrollYProgress, [0, 1], [0, 52])
  const bgParallaxWarm = useTransform(scrollYProgress, [0, 1], [0, 36])
  const meshParallax = useTransform(scrollYProgress, [0, 1], [0, 14])

  const copyStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.09, 0.06), [reduceMotion])
  const copyEyebrow = useMemo(() => landingFadeUp(reduceMotion, { y: 10, duration: landingDuration.micro }), [reduceMotion])
  const copyTitle = useMemo(() => landingFadeUp(reduceMotion, { y: 28, duration: landingDuration.hero }), [reduceMotion])
  const copyLead = useMemo(() => landingFadeUp(reduceMotion, { y: 14, duration: landingDuration.standard }), [reduceMotion])
  const copyBody = useMemo(() => landingFadeUp(reduceMotion, { y: 12, duration: landingDuration.standard }), [reduceMotion])
  const copyCtas = useMemo(() => landingFadeUp(reduceMotion, { y: 14, duration: landingDuration.slow }), [reduceMotion])
  const visualShell = useMemo(() => landingFadeUp(reduceMotion, { y: 40, duration: landingDuration.hero }), [reduceMotion])
  const visualStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.11, 0.22), [reduceMotion])
  const visualLayer = useMemo(() => landingFadeScale(reduceMotion, { scale: 0.979, duration: landingDuration.hero }), [reduceMotion])

  useEffect(() => {
    if (reduceMotion) return
    const el = sectionRef.current
    if (!el) return
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect()
      mx.set(Math.min(100, Math.max(0, ((e.clientX - r.left) / r.width) * 100)))
      my.set(Math.min(100, Math.max(0, ((e.clientY - r.top) / r.height) * 100)))
    }
    el.addEventListener("pointermove", onMove)
    return () => el.removeEventListener("pointermove", onMove)
  }, [mx, my, reduceMotion])

  useEffect(() => {
    if (reduceMotion) return
    let raf = 0
    const t0 = performance.now()
    const tick = (t: number) => {
      const elapsed = (t - t0) / 1000
      driftX.set(Math.sin(elapsed * 0.16) * 10)
      driftY.set(Math.cos(elapsed * 0.13) * 8)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [driftX, driftY, reduceMotion])

  return (
    <section
      ref={sectionRef}
      aria-labelledby="landing-hero-heading"
      className="relative flex min-h-[100dvh] flex-col justify-center overflow-hidden pt-[4.35rem] pb-20 sm:pt-[4.75rem] sm:pb-28 lg:pb-20"
    >
      {/* Layered light canvas */}
      <div className="pointer-events-none absolute inset-0 bg-[color:var(--landing-canvas-pearl)]" aria-hidden />
      <motion.div
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(168deg,var(--landing-canvas-pearl)_0%,var(--landing-canvas)_38%,var(--landing-canvas-mist)_74%,var(--landing-canvas-deep)_100%)]"
        style={reduceMotion ? undefined : { y: bgParallaxDeep }}
        aria-hidden
      />
      <motion.div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_95%_65%_at_85%_-8%,rgba(253,230,138,0.62),transparent_52%),radial-gradient(ellipse_70%_55%_at_5%_95%,rgba(167,243,208,0.28),transparent_48%),radial-gradient(ellipse_50%_40%_at_55%_48%,rgba(255,255,255,0.58),transparent_62%)]"
        style={reduceMotion ? undefined : { y: bgParallaxWarm }}
        aria-hidden
      />
      {/* Depth vignettes — keeps the hero from reading as flat ivory */}
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_88%_72%_at_50%_118%,rgba(18,17,15,0.09),transparent_58%),radial-gradient(ellipse_42%_48%_at_8%_12%,rgba(18,17,15,0.045),transparent_62%),radial-gradient(ellipse_38%_44%_at_96%_28%,rgba(15,118,110,0.06),transparent_55%)]"
        aria-hidden
      />
      {!reduceMotion ? (
        <motion.div className="pointer-events-none absolute inset-0 opacity-[0.78]" style={{ background: wash }} aria-hidden />
      ) : (
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(680px_circle_at_55%_38%,rgba(15,118,110,0.075),transparent_58%)]"
          aria-hidden
        />
      )}
      {!reduceMotion ? (
        <motion.div className="pointer-events-none absolute inset-0 opacity-45 mix-blend-soft-light" style={{ background: bloom }} aria-hidden />
      ) : null}

      {/* Quiet structure — not empty void */}
      <motion.div
        className="pointer-events-none absolute inset-0 opacity-[0.42]"
        style={
          reduceMotion
            ? {
                backgroundImage:
                  "linear-gradient(to right, rgba(27,25,23,0.042) 1px, transparent 1px), linear-gradient(to bottom, rgba(27,25,23,0.036) 1px, transparent 1px)",
                backgroundSize: "min(100%, 72rem) 100%",
                backgroundPosition: "center top",
              }
            : {
                y: meshParallax,
                backgroundImage:
                  "linear-gradient(to right, rgba(27,25,23,0.042) 1px, transparent 1px), linear-gradient(to bottom, rgba(27,25,23,0.036) 1px, transparent 1px)",
                backgroundSize: "min(100%, 72rem) 100%",
                backgroundPosition: "center top",
              }
        }
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[color:var(--landing-line-strong)] to-transparent"
        aria-hidden
      />

      <motion.div
        className="relative z-10 w-full flex-1 py-8 lg:flex lg:items-center lg:py-12 xl:py-16"
        style={reduceMotion ? undefined : { y: heroLift }}
      >
        <LandingContainer className="grid w-full grid-cols-1 gap-14 lg:grid-cols-12 lg:items-center lg:gap-x-6 lg:gap-y-12 xl:gap-x-10 xl:gap-y-14">
          {/* Copy — editorial index + dominant typographic lockup */}
          <div className="relative z-[1] lg:col-span-4 xl:col-span-4">
            <div
              className="pointer-events-none absolute -left-[min(38vw,340px)] top-[-12%] hidden h-[125%] w-[min(100%,480px)] rounded-[50%_50%_48%_52%/50%_52%_48%_50%] bg-[radial-gradient(ellipse_70%_58%_at_20%_42%,rgba(15,118,110,0.11),transparent_72%)] blur-[1.5px] lg:block"
              aria-hidden
            />
            <div
              className="pointer-events-none absolute -left-2 top-0 hidden h-full w-1 rounded-full bg-gradient-to-b from-teal-800/90 via-stone-600/50 to-transparent shadow-[0_0_32px_rgba(15,118,110,0.25)] xl:-left-3 xl:block"
              aria-hidden
            />

            <motion.div
              variants={copyStagger}
              initial="hidden"
              animate="show"
              className="relative max-w-[40rem] lg:max-w-none"
            >
              <motion.div variants={copyEyebrow} className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <span className="font-mono text-[12px] font-semibold tabular-nums text-[color:var(--landing-faint)] sm:text-[13px]">
                  01
                </span>
                <span className="hidden h-3 w-px bg-[color:var(--landing-line-strong)] sm:block" aria-hidden />
                <LandingEyebrow className="m-0 max-w-[20rem] leading-relaxed sm:max-w-none">
                  Adaptive room intelligence · Local first
                </LandingEyebrow>
              </motion.div>

              <motion.div variants={copyTitle} className="mt-7 sm:mt-8">
                <h1 id="landing-hero-heading" className="text-[color:var(--landing-ink)]">
                  <span
                    className={cn(
                      landingFontDisplay,
                      "block bg-gradient-to-br from-[#080807] via-[#141211] to-[#115e59] bg-clip-text text-[clamp(3.85rem,12.5vw,7.75rem)] font-semibold leading-[0.9] tracking-[-0.052em] text-transparent",
                    )}
                  >
                    Haven
                  </span>
                  <span
                    className={cn(
                      landingFontDisplay,
                      "mt-6 block max-w-[18ch] text-balance text-[clamp(1.55rem,3.1vw,2.5rem)] font-medium leading-[1.12] tracking-[-0.034em] text-[color:var(--landing-ink-soft)] sm:mt-7",
                    )}
                  >
                    Your room, read on your network, tuned with intent.
                  </span>
                </h1>
              </motion.div>

              <motion.p
                variants={copyLead}
                className="mt-8 max-w-[30rem] text-pretty text-[1.08rem] font-semibold leading-snug tracking-[-0.02em] text-[color:var(--landing-ink-soft)] sm:mt-9 sm:text-[1.15rem] lg:max-w-[28rem]"
              >
                Context in. Scene out. Adjust once. The baseline remembers.
              </motion.p>

              <motion.p
                variants={copyBody}
                className="mt-5 max-w-[28rem] text-pretty text-[0.9375rem] leading-[1.72] text-[color:var(--landing-muted)] sm:text-[1rem] lg:max-w-[26rem]"
              >
                Haven aligns light, airflow, and temperature as one quiet layer. Inference stays on your network, with
                confidence you can read at a glance.
              </motion.p>

              <motion.div
                variants={copyCtas}
                className="mt-10 flex max-w-lg flex-col gap-4 sm:mt-11 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-5 sm:gap-y-3"
              >
                <Link
                  href="/live"
                  className={cn(landingBtnPrimaryHero, landingFocusRing, "inline-flex w-full items-center justify-center gap-2 sm:w-auto")}
                >
                  Get Started
                  <ArrowRight className="size-[1.1rem] sm:size-[1.12rem]" strokeWidth={2} aria-hidden />
                </Link>
                <a
                  href="#how-it-works"
                  className={cn(landingHeroSecondaryLink, landingFocusRing, "sm:pl-1")}
                >
                  See how it works
                  <ArrowRight
                    className="size-4 opacity-70 transition-[opacity,transform] duration-300 group-hover/hs:translate-x-0.5 group-hover/hs:opacity-100"
                    strokeWidth={2}
                    aria-hidden
                  />
                </a>
              </motion.div>
            </motion.div>
          </div>

          {/* Visual — dark bezel “product window” + layered story (laptop scale) */}
          <div className="relative z-0 min-h-0 lg:col-span-8 lg:-mr-1 xl:col-span-8 xl:-mr-4 2xl:-mr-0">
            <svg
              className="pointer-events-none absolute -right-[4%] top-[-2%] z-0 hidden h-[min(520px,62vh)] w-[min(520px,62vh)] text-teal-900 lg:block"
              viewBox="0 0 200 200"
              fill="none"
              aria-hidden
            >
              <defs>
                <linearGradient id="heroOrbitFr" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="currentColor" stopOpacity="0" />
                  <stop offset="48%" stopColor="currentColor" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
                </linearGradient>
              </defs>
              <ellipse
                cx="100"
                cy="102"
                rx="91"
                ry="84"
                stroke="url(#heroOrbitFr)"
                strokeWidth="1.15"
                strokeDasharray="7 16"
                opacity="0.92"
                transform="rotate(-13 100 102)"
              />
            </svg>

            <motion.div
              className="relative z-[1] mx-auto w-full max-w-[40rem] lg:mx-0 lg:max-w-none"
              variants={visualShell}
              initial="hidden"
              animate="show"
              transition={{ delay: reduceMotion ? 0 : 0.14 }}
            >
              <motion.div
                className="relative min-h-[min(76dvh,620px)] sm:min-h-[600px] lg:min-h-[min(68vh,680px)] xl:min-h-[min(66vh,720px)]"
                style={reduceMotion ? undefined : { transform: fragParallax }}
                variants={visualStagger}
                initial="hidden"
                animate="show"
              >
                <motion.div variants={visualLayer} className="relative mx-auto w-full lg:translate-x-0">
                  <div className="relative rounded-[2.45rem] bg-[linear-gradient(172deg,#343230_0%,#161514_38%,#070706_100%)] p-[10px] shadow-[var(--landing-shadow-bezel)] ring-1 ring-white/[0.1] sm:rounded-[2.65rem] sm:p-3">
                    <div className="relative overflow-hidden rounded-[1.85rem] bg-[#0a0908] shadow-[inset_0_1px_0_rgba(255,255,255,0.07),inset_0_-32px_72px_rgba(0,0,0,0.48)] sm:rounded-[2.1rem]">
                      {/* Product chrome — intentional framing, not decoration */}
                      <div className="flex h-11 shrink-0 items-center gap-3 border-b border-white/[0.07] bg-gradient-to-b from-white/[0.09] to-transparent px-4 sm:h-12 sm:px-5">
                        <div className="flex gap-1.5 opacity-90" aria-hidden>
                          <span className="size-2.5 rounded-full bg-white/14 shadow-inner" />
                          <span className="size-2.5 rounded-full bg-white/11 shadow-inner" />
                          <span className="size-2.5 rounded-full bg-white/[0.09] shadow-inner" />
                        </div>
                        <p
                          className={cn(
                            landingFontDisplay,
                            "min-w-0 flex-1 truncate text-center text-[12px] font-medium tracking-[-0.02em] text-white/[0.92] sm:text-[13px]",
                          )}
                        >
                          Evening settle
                        </p>
                        <span className="inline-flex shrink-0 rounded-full border border-white/12 bg-white/[0.06] px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-[0.24em] text-white/45 sm:text-[10px]">
                          Preview
                        </span>
                      </div>

                      {/* Moods — fused into the window (toolbar rhythm) */}
                      <div className="border-b border-white/[0.06] bg-black/25 px-3 py-2.5 backdrop-blur-md sm:px-4 sm:py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="mr-0.5 inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-white/50">
                            <span className="size-1.5 rounded-full bg-teal-400 shadow-[0_0_0_2px_rgba(10,9,8,0.95)]" aria-hidden />
                            Moods
                          </span>
                          <div className="flex flex-wrap gap-1.5 sm:gap-2">
                            {moodStrip.map((m) => (
                              <span
                                key={m.id}
                                className={cn(
                                  "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold sm:px-2.5 sm:py-1 sm:text-[10.5px]",
                                  "active" in m && m.active
                                    ? "border-teal-400/40 bg-teal-950/55 text-teal-50 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.14)] ring-1 ring-teal-400/25"
                                    : "border-white/12 bg-white/[0.06] text-white/55 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]",
                                )}
                              >
                                <m.Icon className="size-3 opacity-80" strokeWidth={2} aria-hidden />
                                {m.label}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>

                      {/* Room canvas + layered composition (anchor → support → depth) */}
                      <div className="relative min-h-[280px] sm:min-h-[320px] lg:min-h-[380px] xl:min-h-[420px]">
                        <div className="absolute inset-0 overflow-hidden">
                          <div className="absolute inset-0 bg-[linear-gradient(188deg,#fffefb_0%,#ebe2d6_46%,#c8b8a8_100%)]" />
                          <div className="absolute inset-x-0 bottom-0 h-[62%] bg-[linear-gradient(to_top,rgba(253,230,199,0.48)_0%,transparent_90%)]" />
                          <div className="absolute inset-x-0 bottom-0 h-[52%] bg-[linear-gradient(to_top,rgba(18,16,14,0.2)_0%,transparent_95%)]" />
                          <div className="absolute left-[6%] right-[20%] top-[18%] h-[46%] rounded-[40%_60%_70%_30%/55%_45%_35%_65%] bg-[radial-gradient(ellipse_at_30%_28%,rgba(255,255,255,0.97),rgba(255,250,240,0.28)_46%,transparent_72%)] opacity-[0.94] blur-[1px]" />
                          <div className="absolute -left-[22%] bottom-[-10%] h-[58%] w-[82%] rounded-full bg-teal-400/18 blur-3xl" />
                          <div className="absolute -right-[18%] top-[8%] h-[52%] w-[66%] rounded-full bg-amber-300/38 blur-3xl" />
                          {/* Intelligence bloom — ties surfaces to “scene” without noise */}
                          <div
                            className="absolute bottom-[6%] left-1/2 z-[4] h-[58%] w-[118%] -translate-x-1/2 bg-[radial-gradient(ellipse_52%_72%_at_50%_92%,rgba(15,118,110,0.18),transparent_68%)]"
                            aria-hidden
                          />
                          <div
                            className="absolute inset-x-[6%] bottom-[10%] top-[22%] z-[5] rounded-[2rem] bg-[radial-gradient(ellipse_80%_72%_at_50%_78%,rgba(255,253,250,0.45),transparent_72%)] opacity-90 mix-blend-soft-light"
                            aria-hidden
                          />
                          <div className="absolute left-[5%] right-[10%] top-[44%] z-[6] h-px bg-gradient-to-r from-transparent via-stone-900/22 to-transparent" />
                          <div className="absolute left-1/2 top-[38%] z-[6] w-[min(92%,340px)] -translate-x-1/2">
                            <svg viewBox="0 0 320 48" className="w-full text-teal-800/42" aria-hidden>
                              <defs>
                                <linearGradient id="heroArcBezel" x1="0%" y1="0%" x2="100%" y2="0%">
                                  <stop offset="0%" stopColor="currentColor" stopOpacity="0" />
                                  <stop offset="50%" stopColor="currentColor" stopOpacity="0.62" />
                                  <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
                                </linearGradient>
                              </defs>
                              <path
                                d="M 16 40 Q 160 -4 304 40"
                                fill="none"
                                stroke="url(#heroArcBezel)"
                                strokeWidth="2"
                                strokeLinecap="round"
                              />
                            </svg>
                            <p className="sr-only">Decorative arc suggesting ambient lighting</p>
                          </div>
                          {/* Floor shadow pool — grounds the stack */}
                          <div
                            className="absolute inset-x-[4%] bottom-0 z-[7] h-[28%] bg-[radial-gradient(ellipse_70%_95%_at_50%_100%,rgba(28,24,20,0.14),transparent_72%)]"
                            aria-hidden
                          />
                        </div>

                        {/* Tertiary — memory card recedes, peeking from behind anchor */}
                        <motion.div
                          variants={visualLayer}
                          className={cn(
                            "absolute left-[6%] top-[23%] z-[16] hidden w-[13.25rem] p-[1.05rem] sm:left-[8%] sm:top-[24%] sm:block sm:w-[14rem] sm:p-4",
                            "rounded-[1.2rem] border border-white/50 bg-[linear-gradient(152deg,rgba(255,254,252,0.94)_0%,rgba(245,240,232,0.9)_100%)]",
                            "shadow-[var(--landing-shadow-card)]",
                            "ring-1 ring-[color:var(--landing-edge-light)] backdrop-blur-md",
                            "-rotate-[3deg] scale-[0.96]",
                          )}
                        >
                          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[color:var(--landing-faint)]">
                            From feedback
                          </p>
                          <p className="mt-2 text-[12px] leading-snug text-[color:var(--landing-muted)]">
                            Corrections stack quietly. Defaults drift toward how you actually live.
                          </p>
                        </motion.div>

                        {/* Primary anchor — scene + control (dominant plane) */}
                        <motion.div
                          variants={visualLayer}
                          className={cn(
                            "absolute left-[10%] top-[26%] z-[30] w-[min(92%,22.5rem)] p-4 sm:left-[14%] sm:top-[27%] sm:w-[24.5rem] sm:p-5 lg:left-[12%] lg:top-[28%]",
                            "rounded-[1.55rem] border border-stone-200/90",
                            "bg-[linear-gradient(168deg,rgba(255,254,253,1)_0%,rgba(252,248,242,0.98)_42%,rgba(244,238,228,0.96)_100%)]",
                            "shadow-[var(--landing-shadow-float)]",
                            "ring-1 ring-[color:var(--landing-edge-light)] ring-offset-[2px] ring-offset-teal-950/[0.025]",
                            "-rotate-[1.85deg]",
                          )}
                        >
                          <div className="pointer-events-none absolute -right-8 -top-6 size-24 rounded-full bg-teal-400/15 blur-2xl" aria-hidden />
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[color:var(--landing-muted)]">
                                Now reading
                              </p>
                              <p className={cn(landingFontDisplay, "mt-1.5 text-[1.2rem] font-semibold tracking-[-0.034em] text-[color:var(--landing-ink)] sm:mt-2 sm:text-[1.28rem]")}>
                                Work, studying
                              </p>
                              <p className="mt-1.5 max-w-[19rem] text-[11px] leading-relaxed text-[color:var(--landing-muted)] sm:mt-2 sm:text-[12px]">
                                Scene trimmed for focus: light eases up, airflow steady.
                              </p>
                            </div>
                            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-teal-900/14 bg-[linear-gradient(168deg,rgba(255,253,250,1)_0%,rgba(236,253,245,0.88)_100%)] px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-teal-900 shadow-[var(--landing-shadow-card)] ring-1 ring-teal-700/18 backdrop-blur-sm">
                              <Sparkles className="size-3 text-teal-700/90" strokeWidth={2} aria-hidden />
                              Local
                            </span>
                          </div>

                          <div className="mt-4 grid gap-2.5 sm:mt-5 sm:grid-cols-2 sm:gap-3">
                            <div className="rounded-xl border border-stone-200/95 bg-[linear-gradient(180deg,rgba(255,254,252,0.99)_0%,rgba(250,246,240,0.95)_100%)] p-3 shadow-[var(--landing-shadow-card)] sm:p-3.5">
                              <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-[color:var(--landing-faint)] sm:text-[10px]">
                                Scene
                              </p>
                              <div className="mt-1.5 flex items-center gap-1.5 sm:mt-2 sm:gap-2">
                                <Lightbulb className="size-3.5 text-amber-800/85 sm:size-4" strokeWidth={1.85} aria-hidden />
                                <span className="text-[11px] font-semibold text-[color:var(--landing-ink-soft)] sm:text-[12px]">Brightness</span>
                                <span className="ml-auto tabular-nums text-[10px] font-semibold text-[color:var(--landing-muted)] sm:text-[11px]">
                                  74%
                                </span>
                              </div>
                              <div className="mt-2 h-[5px] overflow-hidden rounded-full bg-stone-200/90 shadow-[inset_0_1px_2px_rgba(18,16,14,0.06)] sm:mt-2.5 sm:h-[6px]">
                                <motion.div
                                  className="h-full rounded-full bg-gradient-to-r from-teal-900/88 via-teal-700/75 to-teal-500/60 shadow-[0_0_18px_rgba(15,118,110,0.22)]"
                                  initial={false}
                                  animate={{ width: reduceMotion ? "74%" : ["68%", "79%", "72%", "76%"] }}
                                  transition={
                                    reduceMotion
                                      ? { duration: 0 }
                                      : { duration: 11, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }
                                  }
                                />
                              </div>
                            </div>
                            <div className="rounded-xl border border-stone-200/92 bg-[linear-gradient(180deg,rgba(255,254,252,0.98)_0%,rgba(248,244,238,0.94)_100%)] p-3 shadow-[var(--landing-shadow-card)] sm:p-3.5">
                              <div className="flex items-center gap-1.5 text-[color:var(--landing-muted)] sm:gap-2">
                                <Thermometer className="size-3.5 text-teal-800/85 sm:size-4" strokeWidth={1.75} aria-hidden />
                                <span className="text-[9px] font-semibold uppercase tracking-[0.12em] sm:text-[10px]">Target</span>
                                <span className="ml-auto text-[11px] font-semibold tabular-nums text-[color:var(--landing-ink)] sm:text-[12px]">
                                  72°F
                                </span>
                              </div>
                              <div className="mt-2.5 flex items-center gap-1.5 text-[color:var(--landing-muted)] sm:mt-3 sm:gap-2">
                                <Wind className="size-3.5 text-sky-800/78 sm:size-4" strokeWidth={1.75} aria-hidden />
                                <span className="text-[9px] font-semibold uppercase tracking-[0.12em] sm:text-[10px]">Airflow</span>
                                <span className="ml-auto text-[11px] font-semibold text-[color:var(--landing-ink)] sm:text-[12px]">Gentle</span>
                              </div>
                            </div>
                          </div>
                        </motion.div>

                        {/* Privacy — secondary plane, tucked under anchor corner */}
                        <motion.div
                          variants={visualLayer}
                          className={cn(
                            "absolute bottom-[5%] right-[3%] z-[24] w-[min(92%,16.25rem)] p-4 sm:bottom-[6%] sm:right-[5%] sm:w-[17.25rem] sm:p-[1.15rem]",
                            "rounded-[1.25rem] border border-stone-300/80 bg-[linear-gradient(158deg,rgba(253,251,248,0.98)_0%,rgba(238,233,224,0.95)_100%)]",
                            "shadow-[var(--landing-shadow-card)]",
                            "ring-1 ring-[color:var(--landing-edge-light)]",
                            "rotate-[2.25deg] sm:translate-x-1",
                          )}
                        >
                          <div className="pointer-events-none absolute -left-10 bottom-0 h-16 w-16 rounded-full bg-violet-500/10 blur-2xl" aria-hidden />
                          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[color:var(--landing-muted)]">
                            On device
                          </p>
                          <p className="mt-2 text-[12px] font-semibold leading-snug text-[color:var(--landing-ink-soft)] sm:text-[13px]">
                            Signal stays here, not packaged for a feed.
                          </p>
                          <p className="mt-2 text-[12px] leading-relaxed text-[color:var(--landing-muted)]">
                            Enough context to adapt the room. Nothing staged for an outsider&apos;s dashboard.
                          </p>
                        </motion.div>
                      </div>
                    </div>
                  </div>
                </motion.div>
              </motion.div>
            </motion.div>
          </div>
        </LandingContainer>
      </motion.div>

      <motion.a
        href="#how-it-works"
        style={reduceMotion ? undefined : { opacity: exploreOpacity }}
        className={cn(
          "absolute bottom-5 left-1/2 z-10 -translate-x-1/2 text-[11px] font-semibold uppercase tracking-[0.2em] text-[color:var(--landing-faint)] sm:bottom-8",
          "transition-colors hover:text-[color:var(--landing-muted)]",
          landingFocusRing,
          "rounded-md px-2 py-1.5",
        )}
      >
        Continue
      </motion.a>
    </section>
  )
}
