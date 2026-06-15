"use client"

import type { MoodDefinition } from "@/types/roomos"
import { moodLifecycleFilter, type MoodFilter } from "@/components/roomos/moods/mood-lifecycle-chip"
import { cn } from "@/lib/utils"

const FILTERS: { id: MoodFilter; label: string }[] = [
  { id: "all", label: "All moods" },
  { id: "live", label: "Live ready" },
  { id: "teach", label: "Needs teaching" },
  { id: "active", label: "In progress" },
]

export function MoodFilterBar({
  moods,
  value,
  onChange,
}: {
  moods: MoodDefinition[]
  value: MoodFilter
  onChange: (f: MoodFilter) => void
}) {
  if (moods.length <= 4) return null

  const counts = FILTERS.map((f) => ({
    ...f,
    count: moods.filter((m) => moodLifecycleFilter(m, f.id)).length,
  }))

  return (
    <div
      className="flex flex-wrap gap-2"
      role="tablist"
      aria-label="Filter moods by lifecycle"
    >
      {counts.map((f) => (
        <button
          key={f.id}
          type="button"
          role="tab"
          aria-selected={value === f.id}
          onClick={() => onChange(f.id)}
          className={cn(
            "rounded-full border px-3 py-1.5 text-[12px] font-semibold transition-colors",
            value === f.id
              ? "border-[color:var(--haven-ink)] bg-[color:var(--haven-ink)] text-white"
              : "border-[color:var(--haven-line-strong)] bg-white/70 text-[color:var(--haven-muted)] hover:text-[color:var(--haven-ink)]",
          )}
        >
          {f.label}
          <span className="ml-1.5 font-mono text-[10px] tabular-nums opacity-70">{f.count}</span>
        </button>
      ))}
    </div>
  )
}
