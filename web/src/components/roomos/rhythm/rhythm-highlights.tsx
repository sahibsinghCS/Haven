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

import {
  formatClockLabel,
  formatRhythmDuration,
  sleepConsistencyLabel,
} from "@/lib/roomos/rhythm-format"
import type { RhythmHighlights } from "@/types/rhythm"
import { cn } from "@/lib/utils"

const cardShell =
  "rounded-[1.35rem] border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_96%,transparent)] shadow-[var(--haven-shadow-card)] ring-1 ring-[color:var(--haven-edge-light)]"

function HighlightCard({
  icon,
  label,
  value,
  detail,
}: {
  icon: React.ReactNode
  label: string
  value: string
  detail?: string
}) {
  return (
    <div className={cn(cardShell, "flex flex-col gap-3 px-4 py-4 sm:px-5 sm:py-5")}>
      <div className="flex items-center gap-2 text-[color:var(--haven-faint)]">
        <span className="flex size-8 items-center justify-center rounded-xl bg-[color:var(--haven-accent-soft)] text-teal-800">
          {icon}
        </span>
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em]">{label}</span>
      </div>
      <p className="haven-display text-[1.35rem] font-semibold leading-tight text-[color:var(--haven-ink)]">
        {value}
      </p>
      {detail ? (
        <p className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">{detail}</p>
      ) : null}
    </div>
  )
}

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
    label: string
    value: string
    detail?: string
  }> = [
    {
      key: "sleep",
      icon: <Moon className="size-4" aria-hidden />,
      label: "Usual sleep start",
      value: sleepTime ?? "—",
      detail:
        highlights.sleepStartSamples > 0
          ? `${highlights.sleepStartSamples} sample${highlights.sleepStartSamples === 1 ? "" : "s"}`
          : consistency ?? "Need more sleep blocks in Live",
    },
    {
      key: "savings",
      icon: <DollarSign className="size-4" aria-hidden />,
      label: "Est. savings",
      value: `$${highlights.estimatedSavingsUsd.toFixed(2)}`,
      detail:
        highlights.automationsRun > 0
          ? `${highlights.automationsRun} automation${highlights.automationsRun === 1 ? "" : "s"}`
          : savingsDetail,
    },
    {
      key: "switches",
      icon: <Shuffle className="size-4" aria-hidden />,
      label: "Mood switches",
      value: String(highlights.moodSwitches),
      detail: "Times Haven changed your detected mood",
    },
    {
      key: "deep",
      icon: <Brain className="size-4" aria-hidden />,
      label: "Deep work",
      value:
        highlights.deepWorkBlocks > 0
          ? `${highlights.deepWorkBlocks} block${highlights.deepWorkBlocks === 1 ? "" : "s"}`
          : "—",
      detail:
        highlights.deepWorkMinutes > 0
          ? `${Math.round(highlights.deepWorkMinutes)} min in 45+ min focus runs`
          : "45+ minute work stretches",
    },
    {
      key: "away",
      icon: <BedDouble className="size-4" aria-hidden />,
      label: "Away",
      value: highlights.awayHours > 0 ? `${highlights.awayHours.toFixed(1)}h` : "—",
      detail: "Desk empty or camera off gaps excluded",
    },
    {
      key: "wind",
      icon: <Timer className="size-4" aria-hidden />,
      label: "Wind-down",
      value:
        highlights.windDownMinutes != null
          ? `${Math.round(highlights.windDownMinutes)} min`
          : "—",
      detail: "Relaxing → sleep when both appear",
    },
    {
      key: "confidence",
      icon: <TrendingUp className="size-4" aria-hidden />,
      label: "Avg confidence",
      value:
        highlights.avgConfidence != null
          ? `${Math.round(highlights.avgConfidence * 100)}%`
          : "—",
      detail:
        highlights.uncertainPercent != null
          ? `${highlights.uncertainPercent}% low-confidence frames`
          : undefined,
    },
    {
      key: "consistency",
      icon: <Activity className="size-4" aria-hidden />,
      label: "Sleep rhythm",
      value: consistency ?? "—",
      detail: sleepTime ? `Median start ${sleepTime}` : "Track sleep in Live",
    },
  ]

  return (
    <section aria-label="Rhythm highlights">
      <h2 className="haven-display mb-4 text-[1.2rem] font-semibold text-[color:var(--haven-ink)]">
        Highlights
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((c) => (
          <HighlightCard
            key={c.key}
            icon={c.icon}
            label={c.label}
            value={c.value}
            detail={c.detail}
          />
        ))}
      </div>
    </section>
  )
}
