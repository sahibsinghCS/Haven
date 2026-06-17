"use client"

import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { Moon, Grid3x3, Waves, DoorClosed } from "lucide-react"

import {
  landingDuration,
  landingEase,
  landingFadeUp,
  landingStaggerParent,
  landingViewport,
} from "@/components/landing/landing-motion"
import {
  landingFontDisplay,
  LandingContainer,
  LandingDisplayH2,
  LandingEyebrow,
  LandingProse,
  LandingSectionShell,
} from "@/components/landing/landing-primitives"
import {
  ROOM_STATE_LABEL,
  ROOM_STATE_LANDING_ATMOSPHERE,
  ROOM_STATE_LANDING_SKIN,
} from "@/lib/roomos/state-meta"
import { cn } from "@/lib/utils"
import { ROOM_STATE_ORDER, type KnownRoomStateId } from "@/types/roomos"

function AtmosphereRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-stone-900/[0.06] py-2.5 last:border-b-0">
      <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[color:var(--landing-faint)]">{label}</span>
      <span className="text-[13px] leading-snug text-[color:var(--landing-ink-soft)]">{value}</span>
    </div>
  )
}

function StateInner({ id }: { id: KnownRoomStateId }) {
  const skin = ROOM_STATE_LANDING_SKIN[id]
  const atm = ROOM_STATE_LANDING_ATMOSPHERE[id]

  if (id === "sleep") {
    return (
      <>
        <div className={cn("pointer-events-none absolute inset-0 bg-gradient-to-br opacity-[0.94]", skin.wash)} aria-hidden />
        <div className={cn("pointer-events-none absolute right-0 top-0 size-[min(55%,280px)] rounded-full blur-3xl opacity-60", skin.glow)} aria-hidden />
        <div className="relative flex min-h-full flex-col lg:min-h-[320px] lg:flex-row lg:gap-10">
          <div className="flex flex-1 flex-col justify-between">
            <div>
              <div className="flex items-center gap-3">
                <Moon className="size-5 text-indigo-900/70" strokeWidth={1.75} aria-hidden />
                <span className={cn("h-[3px] w-14 rounded-full", skin.bar)} />
              </div>
              <h3 className={cn(landingFontDisplay, "mt-6 text-[clamp(1.75rem,4vw,2.35rem)] font-medium tracking-[-0.03em] text-[color:var(--landing-ink)]")}>
                {ROOM_STATE_LABEL[id]}
              </h3>
              <p className="mt-3 max-w-[22rem] text-[14px] leading-relaxed text-[color:var(--landing-muted)]">{atm.tagline}</p>
            </div>
            <p className="mt-8 max-w-xs text-[12px] font-medium leading-relaxed text-[color:var(--landing-faint)] lg:mt-0">
              Sleep is the most guarded posture: low glare, motion respected, depth preserved.
            </p>
          </div>
          <div className="mt-8 rounded-2xl border border-white/60 bg-white/45 p-5 shadow-inner backdrop-blur-md lg:mt-0 lg:w-[min(100%,240px)] lg:shrink-0">
            <AtmosphereRow label="Light" value={atm.light} />
            <AtmosphereRow label="Air" value={atm.air} />
            <AtmosphereRow label="Thermal" value={atm.thermal} />
          </div>
        </div>
      </>
    )
  }

  if (id === "work") {
    return (
      <>
        <div className={cn("pointer-events-none absolute inset-0 bg-gradient-to-br opacity-[0.94]", skin.wash)} aria-hidden />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage: "linear-gradient(to right, currentColor 1px, transparent 1px)",
            backgroundSize: "22px 100%",
          }}
          aria-hidden
        />
        <div className="relative flex min-h-full flex-col">
          <div className="flex items-center justify-between gap-3">
            <Grid3x3 className="size-5 text-sky-900/70" strokeWidth={1.65} aria-hidden />
            <span className={cn("h-px flex-1 bg-gradient-to-r from-sky-600/35 to-transparent")} aria-hidden />
          </div>
          <h3 className={cn(landingFontDisplay, "mt-6 text-2xl font-medium tracking-[-0.03em] text-[color:var(--landing-ink)]")}>
            {ROOM_STATE_LABEL[id]}
          </h3>
          <p className="mt-2 text-[13px] leading-relaxed text-[color:var(--landing-muted)]">{atm.tagline}</p>
          <div className="mt-6 grid grid-cols-3 gap-3">
            <div className="rounded-xl border border-sky-900/10 bg-white/55 px-3 py-3 text-center shadow-sm backdrop-blur-sm">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[color:var(--landing-faint)]">Field</p>
              <p className="mt-1 text-[13px] font-semibold text-sky-950">Even</p>
            </div>
            <div className="rounded-xl border border-sky-900/10 bg-white/55 px-3 py-3 text-center shadow-sm backdrop-blur-sm">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[color:var(--landing-faint)]">Air</p>
              <p className="mt-1 text-[13px] font-semibold text-sky-950">Steady</p>
            </div>
            <div className="rounded-xl border border-sky-900/10 bg-white/55 px-3 py-3 text-center shadow-sm backdrop-blur-sm">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[color:var(--landing-faint)]">Temp</p>
              <p className="mt-1 text-[13px] font-semibold text-sky-950">Held</p>
            </div>
          </div>
          <p className="mt-5 text-[12px] leading-relaxed text-[color:var(--landing-muted)]">{atm.thermal}</p>
        </div>
      </>
    )
  }

  if (id === "relaxing") {
    return (
      <>
        <div className={cn("pointer-events-none absolute inset-0 bg-gradient-to-tl opacity-[0.94]", skin.wash)} aria-hidden />
        <div className={cn("pointer-events-none absolute left-[10%] top-[40%] size-[180px] rounded-full blur-3xl opacity-50", skin.glow)} aria-hidden />
        <div className="relative flex min-h-full flex-col">
          <div>
            <div className="flex items-center gap-2 text-teal-900/75">
              <Waves className="size-6" strokeWidth={1.65} aria-hidden />
              <span className={cn("h-[3px] w-10 rounded-full", skin.bar)} />
            </div>
            <h3 className={cn(landingFontDisplay, "mt-5 text-2xl font-medium tracking-[-0.03em] text-[color:var(--landing-ink)]")}>
              {ROOM_STATE_LABEL[id]}
            </h3>
            <p className="mt-2 text-[14px] italic leading-relaxed text-[color:var(--landing-muted)]">{atm.tagline}</p>
          </div>
          <div className="mt-auto space-y-3 rounded-2xl border border-teal-900/8 bg-white/40 p-4 pt-5 backdrop-blur-md">
            <p className="text-[12px] leading-relaxed text-[color:var(--landing-muted)]">
              <span className="font-semibold text-[color:var(--landing-ink-soft)]">Light: </span>
              {atm.light}
            </p>
            <p className="text-[12px] leading-relaxed text-[color:var(--landing-muted)]">
              <span className="font-semibold text-[color:var(--landing-ink-soft)]">Air: </span>
              {atm.air}
            </p>
          </div>
        </div>
      </>
    )
  }

  /* away */
  return (
    <>
      <div className={cn("pointer-events-none absolute inset-0 bg-gradient-to-b opacity-[0.96]", skin.wash)} aria-hidden />
      <div className={cn("pointer-events-none absolute right-0 top-0 size-[min(45%,200px)] rounded-full blur-3xl opacity-40", skin.glow)} aria-hidden />
      <div className="relative flex min-h-full flex-col justify-between gap-5 py-1">
        <DoorClosed className="size-5 text-stone-600/75" strokeWidth={1.65} aria-hidden />
        <div>
          <h3 className={cn(landingFontDisplay, "text-xl font-medium tracking-[-0.03em] text-[color:var(--landing-ink)]")}>
            {ROOM_STATE_LABEL[id]}
          </h3>
          <p className="mt-3 text-[13px] leading-[1.75] text-[color:var(--landing-muted)]">{atm.tagline}</p>
        </div>
        <ul className="space-y-2 text-[12px] text-[color:var(--landing-faint)]">
          <li>{atm.light}</li>
          <li>{atm.thermal}</li>
        </ul>
      </div>
    </>
  )
}

const shells: Record<KnownRoomStateId, string> = {
  sleep:
    "rounded-[1.5rem] border border-indigo-200/55 bg-[color-mix(in_oklab,var(--landing-surface)_52%,transparent)] p-6 shadow-[var(--landing-shadow-float)] ring-1 ring-[color:var(--landing-edge-light)] backdrop-blur-md sm:p-8",
  work:
    "rounded-[1.5rem] border border-sky-200/55 bg-[color-mix(in_oklab,var(--landing-surface)_58%,transparent)] p-6 shadow-[var(--landing-shadow-float)] ring-1 ring-[color:var(--landing-edge-light)] backdrop-blur-md sm:p-7",
  relaxing:
    "rounded-[1.5rem] border border-teal-200/48 bg-[color-mix(in_oklab,var(--landing-surface)_54%,transparent)] p-6 shadow-[var(--landing-shadow-float)] ring-1 ring-[color:var(--landing-edge-light)] backdrop-blur-md sm:p-8",
  away:
    "rounded-[1.5rem] border border-stone-300/50 bg-[color-mix(in_oklab,var(--landing-surface)_56%,transparent)] p-6 shadow-[var(--landing-shadow-float)] ring-1 ring-[color:var(--landing-edge-light)] backdrop-blur-md sm:p-7",
}

export function MoodsSection() {
  const reduceMotion = useReducedMotion()
  const headStagger = useMemo(() => landingStaggerParent(reduceMotion, 0.07, 0.06), [reduceMotion])
  const headPiece = useMemo(() => landingFadeUp(reduceMotion, { y: 14, duration: landingDuration.standard }), [reduceMotion])

  return (
    <LandingSectionShell id="room-states" labelledBy="moods-heading">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_88%_58%_at_50%_-8%,rgba(254,243,199,0.28),transparent_54%),linear-gradient(180deg,var(--landing-canvas-pearl)_0%,var(--landing-canvas-mist)_65%,var(--landing-canvas-deep)_100%)]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-amber-200/40 to-transparent"
        aria-hidden
      />

      <LandingContainer className="relative">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between lg:gap-10">
          <motion.div
            variants={headStagger}
            initial="hidden"
            whileInView="show"
            viewport={landingViewport.headline}
            className="max-w-3xl lg:max-w-[min(100%,36rem)]"
          >
            <motion.div variants={headPiece}>
              <LandingEyebrow>Moods</LandingEyebrow>
            </motion.div>
            <motion.div variants={headPiece} className="mt-4">
              <LandingDisplayH2 id="moods-heading">Four moods, four environments</LandingDisplayH2>
            </motion.div>
            <motion.div variants={headPiece}>
              <LandingProse className="mt-3 sm:mt-4">
                Haven doesn&apos;t chase brittle scripts. Each mood defines how light, air, and temperature behave together,
                and each one has its own lane in preferences.
              </LandingProse>
            </motion.div>
          </motion.div>
          <motion.p
            variants={headPiece}
            initial="hidden"
            whileInView="show"
            viewport={landingViewport.headline}
            className={cn(
              landingFontDisplay,
              "hidden max-w-[14rem] text-right text-[15px] font-normal italic leading-snug text-[color:var(--landing-faint)] lg:block",
            )}
          >
            Same engine, four distinct atmospheres.
          </motion.p>
        </div>

        <ul className="mt-11 grid grid-cols-1 gap-4 sm:gap-5 lg:mt-12 lg:grid-cols-2 lg:items-stretch lg:gap-5">
          {ROOM_STATE_ORDER.map((id, i) => (
            <motion.li
              key={id}
              className={cn("flex min-h-[min(100%,280px)]", shells[id])}
              initial={
                reduceMotion
                  ? false
                  : {
                      opacity: 0,
                      y: 22 + i * 4,
                      scale: 0.98,
                    }
              }
              whileInView={{ opacity: 1, y: 0, scale: 1 }}
              viewport={landingViewport.cardDeep}
              transition={{
                duration: landingDuration.slow,
                delay: reduceMotion ? 0 : i * 0.07,
                ease: landingEase.grounded,
              }}
            >
              <article className="relative flex min-h-full w-full flex-col overflow-hidden rounded-[inherit]">
                <StateInner id={id} />
              </article>
            </motion.li>
          ))}
        </ul>
      </LandingContainer>
    </LandingSectionShell>
  )
}
