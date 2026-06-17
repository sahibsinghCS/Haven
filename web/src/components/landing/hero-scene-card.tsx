"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import {
  Activity,
  Briefcase,
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

import { landingFontDisplay } from "@/components/landing/landing-primitives"
import { LEGACY_MOOD_DEFAULTS } from "@/lib/roomos/preferences-schema"
import { roomStateLabel } from "@/lib/roomos/state-meta"
import { cn } from "@/lib/utils"
import type { KnownRoomStateId } from "@/types/roomos"

type HeroMoodId = KnownRoomStateId | "gaming"

const MOOD_STRIP: {
  id: HeroMoodId
  label: string
  Icon: typeof Moon
}[] = [
  { id: "sleep", label: "Sleep", Icon: Moon },
  { id: "gaming", label: "Gaming", Icon: Gamepad2 },
  { id: "work", label: "Work", Icon: Briefcase },
  { id: "relaxing", label: "Relax", Icon: Palmtree },
  { id: "away", label: "Away", Icon: DoorOpen },
]

const GAMING_DEFAULTS = {
  lightColorHex: "#8B5CF6",
  brightness: 58,
  fanOn: true,
  temperatureF: 70,
}

const MOOD_COPY: Record<HeroMoodId, { body: string; confidence: number }> = {
  work: {
    body: "Ambient posture favors clarity: high field light, softened glare, gentle air.",
    confidence: 87,
  },
  sleep: {
    body: "Low light, cooler target, airflow eases for rest without a jarring switch.",
    confidence: 91,
  },
  gaming: {
    body: "Focused immersion: moderate field light, steady air, comfort held in range.",
    confidence: 79,
  },
  relaxing: {
    body: "Warmer tone, softer field, room breathes with you rather than performing.",
    confidence: 84,
  },
  away: {
    body: "Lights down, climate holds. Nothing runs harder than the empty room needs.",
    confidence: 93,
  },
}

function sceneForMood(moodId: HeroMoodId) {
  const base =
    moodId === "gaming"
      ? GAMING_DEFAULTS
      : LEGACY_MOOD_DEFAULTS[moodId as keyof typeof LEGACY_MOOD_DEFAULTS]
  return {
    light: `${base.brightness}%`,
    airflow: base.fanOn ? "gentle" : "off",
    target: `${base.temperatureF}F`,
  }
}

const API_BASE = process.env.NEXT_PUBLIC_ROOMOS_API_URL ?? "http://127.0.0.1:8000"

export function HeroSceneCard({ className }: { className?: string }) {
  const reduceMotion = useReducedMotion()
  const [activeMood, setActiveMood] = useState<HeroMoodId>("work")
  const [liveLabel, setLiveLabel] = useState<string | null>(null)
  const [liveConfidence, setLiveConfidence] = useState<number | null>(null)

  const scene = useMemo(() => sceneForMood(activeMood), [activeMood])
  const copy = MOOD_COPY[activeMood]
  const displayLabel = liveLabel ?? roomStateLabel(activeMood)
  const displayConfidence = liveConfidence ?? copy.confidence

  const pollLive = useCallback(async () => {
    try {
      const health = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(2000) })
      if (!health.ok) return
      const snap = await fetch(`${API_BASE}/api/live/snapshot`, { signal: AbortSignal.timeout(3000) })
      if (!snap.ok) return
      const data = (await snap.json()) as {
        label?: string
        confidence?: number
        primary_label?: string
        primary_confidence?: number
      }
      const label = data.label ?? data.primary_label
      const conf = data.confidence ?? data.primary_confidence
      if (label) setLiveLabel(roomStateLabel(label))
      if (typeof conf === "number") setLiveConfidence(Math.round(conf * (conf <= 1 ? 100 : 1)))
    } catch {
      /* API offline — static demo */
    }
  }, [])

  useEffect(() => {
    void pollLive()
    const id = window.setInterval(pollLive, 8000)
    return () => window.clearInterval(id)
  }, [pollLive])

  return (
    <div className={cn("relative mx-auto max-w-[44rem]", className)}>
      <div className="landing-breathe pointer-events-none absolute -inset-8 rounded-[3rem] bg-[radial-gradient(ellipse_at_center,rgba(20,184,166,0.28),transparent_62%)] blur-2xl" />
      <div className="relative overflow-hidden rounded-[2.25rem] border border-white/[0.12] bg-[linear-gradient(150deg,rgba(255,255,255,0.11),rgba(255,255,255,0.035)_36%,rgba(255,255,255,0.02))] p-2 shadow-[0_46px_120px_-44px_rgba(0,0,0,0.88),0_0_0_1px_rgba(255,255,255,0.04)] backdrop-blur-2xl md:backdrop-blur-2xl">
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
              {liveLabel ? "Live" : "Local"}
            </span>
          </div>

          <div className="relative min-h-[380px] overflow-hidden sm:min-h-[460px]">
            <div className="absolute inset-0 bg-[linear-gradient(165deg,#f6efe2_0%,#d5c4aa_42%,#6e7f73_78%,#15120f_100%)]" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_65%_55%_at_42%_34%,rgba(255,255,255,0.86),transparent_58%),radial-gradient(ellipse_64%_48%_at_72%_70%,rgba(20,184,166,0.34),transparent_60%),radial-gradient(ellipse_52%_45%_at_18%_82%,rgba(245,158,11,0.24),transparent_56%)]" />

            <div className="absolute left-[8%] top-[11%] w-[min(84%,29rem)] rounded-[2rem] border border-white/58 bg-white/[0.72] p-5 text-stone-950 shadow-[0_34px_90px_-38px_rgba(0,0,0,0.54),inset_0_1px_0_rgba(255,255,255,0.8)] backdrop-blur-xl sm:left-[9%] sm:p-6 md:backdrop-blur-2xl">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-mono text-[10px] font-bold uppercase tracking-[0.24em] text-stone-500">
                    Current read
                  </p>
                  <AnimatePresence mode="wait">
                    <motion.h2
                      key={displayLabel}
                      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={reduceMotion ? undefined : { opacity: 0, y: -6 }}
                      transition={{ duration: 0.28 }}
                      className={cn(
                        landingFontDisplay,
                        "mt-2 text-[2rem] font-semibold tracking-[-0.045em] sm:text-[2.35rem]",
                      )}
                    >
                      {displayLabel}
                    </motion.h2>
                  </AnimatePresence>
                  <p className="mt-2 max-w-[21rem] text-[12.5px] leading-relaxed text-stone-600">{copy.body}</p>
                </div>
                <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-teal-900/12 bg-teal-50 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-teal-900">
                  <Sparkles className="size-3" aria-hidden />
                  {displayConfidence}%
                </span>
              </div>

              <motion.div layout className="mt-5 grid gap-3 sm:grid-cols-3">
                {[
                  { label: "Light field", value: scene.light, Icon: Lightbulb, tone: "text-amber-700" },
                  { label: "Airflow", value: scene.airflow, Icon: Wind, tone: "text-sky-700" },
                  { label: "Target", value: scene.target, Icon: Thermometer, tone: "text-teal-700" },
                ].map((row) => (
                  <motion.div
                    key={row.label}
                    layout
                    className="rounded-2xl border border-stone-200/90 bg-white/72 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.76)]"
                  >
                    <row.Icon className={cn("size-4", row.tone)} strokeWidth={1.8} />
                    <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.14em] text-stone-500">
                      {row.label}
                    </p>
                    <p className="mt-1 font-mono text-[14px] font-semibold tracking-[-0.01em] text-stone-950">
                      {row.value}
                    </p>
                  </motion.div>
                ))}
              </motion.div>
            </div>

            <div className="absolute bottom-[19%] right-[6%] w-[min(72%,18rem)] rounded-[1.5rem] border border-white/16 bg-[#11100e]/86 p-4 text-stone-100 shadow-[0_26px_70px_-34px_rgba(0,0,0,0.8)] backdrop-blur-xl md:backdrop-blur-xl">
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

            <div className="absolute bottom-5 left-5 right-5 rounded-[1.35rem] border border-white/[0.12] bg-[#0c0a08]/78 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl md:backdrop-blur-xl">
              <div className="flex flex-wrap items-center gap-2">
                <span className="mr-1 inline-flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-stone-400">
                  <Activity className="size-3.5 text-teal-200/70" aria-hidden />
                  Moods
                </span>
                {MOOD_STRIP.map((mood) => (
                  <button
                    key={mood.id}
                    type="button"
                    onClick={() => {
                      setLiveLabel(null)
                      setLiveConfidence(null)
                      setActiveMood(mood.id)
                    }}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10.5px] font-semibold transition-[border-color,background-color,color,box-shadow] duration-200",
                      activeMood === mood.id
                        ? "border-teal-200/34 bg-teal-200/[0.12] text-teal-50 shadow-[0_0_24px_rgba(45,212,191,0.13)]"
                        : "border-white/[0.09] bg-white/[0.04] text-stone-400 hover:border-white/16 hover:text-stone-200",
                    )}
                  >
                    <mood.Icon className="size-3" strokeWidth={2} aria-hidden />
                    {mood.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
