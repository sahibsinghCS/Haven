"use client"

import {
  Activity,
  BedDouble,
  Brain,
  DollarSign,
  Moon,
  Shuffle,
  Timer,
  TrendingUp,
} from "lucide-react"

import { HavenStatCard } from "@/components/roomos/haven-primitives"
import {
  formatClockLabel,
  formatRhythmDuration,
  sleepConsistencyLabel,
} from "@/lib/roomos/rhythm-format"
import type { RhythmHighlights } from "@/types/rhythm"

export function RhythmHighlights({ highlights }: { highlights: RhythmHighlights }) {
  const sleepTime = formatClockLabel(highlights.usualSleepStart)
  const consistency = sleepConsistencyLabel(highlights.sleepConsistency)
  const savingsDetail =
    highlights.savingsIncludesDryRun
      ? "Includes dry-run automations; estimate only."
      : highlights.savingsIsEstimate
        ? "Rough estimate from automations run."
        : undefined

  const cards: Array<{
    key: string
    icon: React.ReactNode
    eyebrow: string
    value: string
    hint?: string
    delta?: string
    deltaTone?: "neutral" | "teal" | "amber" | "rose"
  }> = [
    {
      key: "sleep",
      icon: <Moon className="size-4" aria-hidden />,
      eyebrow: "Usual sleep start",
      value: sleepTime ?? "—",
      hint:
        highlights.sleepStartSamples > 0
          ? `${highlights.sleepStartSamples} sample${highlights.sleepStartSamples === 1 ? "" : "s"}`
          : consistency ?? "Need more sleep blocks in Live",
    },
    {
      key: "savings",
      icon: <DollarSign className="size-4" aria-hidden />,
      eyebrow: "Est. savings",
      value: `$${highlights.estimatedSavingsUsd.toFixed(2)}`,
      hint:
        highlights.automationsRun > 0
          ? `${highlights.automationsRun} automation${highlights.automationsRun === 1 ? "" : "s"}`
          : savingsDetail,
      delta: highlights.estimatedSavingsUsd > 0 ? "This week" : undefined,
      deltaTone: "teal",
    },
    {
      key: "switches",
      icon: <Shuffle className="size-4" aria-hidden />,
      eyebrow: "Mood switches",
      value: String(highlights.moodSwitches),
      hint: "Times Haven changed your detected mood",
    },
    {
      key: "deep",
      icon: <Brain className="size-4" aria-hidden />,
      eyebrow: "Deep work",
      value:
        highlights.deepWorkBlocks > 0
          ? `${highlights.deepWorkBlocks} block${highlights.deepWorkBlocks === 1 ? "" : "s"}`
          : "—",
      hint:
        highlights.deepWorkMinutes > 0
          ? `${Math.round(highlights.deepWorkMinutes)} min in 45+ min focus runs`
          : "45+ minute work stretches",
    },
    {
      key: "away",
      icon: <BedDouble className="size-4" aria-hidden />,
      eyebrow: "Away",
      value: highlights.awayHours > 0 ? `${highlights.awayHours.toFixed(1)}h` : "—",
      hint: "Desk empty or camera off gaps excluded",
    },
    {
      key: "wind",
      icon: <Timer className="size-4" aria-hidden />,
      eyebrow: "Wind-down",
      value:
        highlights.windDownMinutes != null
          ? `${Math.round(highlights.windDownMinutes)} min`
          : "—",
      hint: "Relaxing → sleep when both appear",
    },
    {
      key: "confidence",
      icon: <TrendingUp className="size-4" aria-hidden />,
      eyebrow: "Avg confidence",
      value:
        highlights.avgConfidence != null
          ? `${Math.round(highlights.avgConfidence * 100)}%`
          : "—",
      hint:
        highlights.uncertainPercent != null
          ? `${highlights.uncertainPercent}% low-confidence frames`
          : undefined,
      delta:
        highlights.avgConfidence != null && highlights.avgConfidence >= 0.7
          ? "Strong reads"
          : highlights.avgConfidence != null
            ? "Mixed reads"
            : undefined,
      deltaTone:
        highlights.avgConfidence != null && highlights.avgConfidence >= 0.7 ? "teal" : "amber",
    },
    {
      key: "consistency",
      icon: <Activity className="size-4" aria-hidden />,
      eyebrow: "Sleep rhythm",
      value: consistency ?? "—",
      hint: sleepTime ? `Median start ${sleepTime}` : "Track sleep in Live",
    },
  ]

  const heroKeys = new Set(["sleep", "savings", "switches"])
  const heroCards = cards.filter((c) => heroKeys.has(c.key))
  const restCards = cards.filter((c) => !heroKeys.has(c.key))

  return (
    <section aria-label="Rhythm highlights">
      <h2 className="haven-display mb-4 text-[1.2rem] font-semibold text-[color:var(--haven-ink)]">
        Highlights
      </h2>
      <div className="grid gap-3 sm:grid-cols-3">
        {heroCards.map((c) => (
          <HavenStatCard
            key={c.key}
            eyebrow={c.eyebrow}
            value={c.value}
            hint={c.hint}
            delta={c.delta}
            deltaTone={c.deltaTone}
          />
        ))}
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 haven-list-stagger">
        {restCards.map((c) => (
          <HavenStatCard
            key={c.key}
            eyebrow={c.eyebrow}
            value={c.value}
            hint={c.hint}
            delta={c.delta}
            deltaTone={c.deltaTone}
            className="!py-4"
          />
        ))}
      </div>
    </section>
  )
}
