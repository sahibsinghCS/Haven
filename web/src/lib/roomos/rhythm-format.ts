/** Human-readable duration from seconds (e.g. "2h 14m"). */
export function formatRhythmDuration(totalSec: number): string {
  if (!Number.isFinite(totalSec) || totalSec <= 0) return "0m"
  const sec = Math.round(totalSec)
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (h > 0 && m > 0) return `${h}h ${m}m`
  if (h > 0) return `${h}h`
  if (m > 0) return `${m}m`
  return `${sec}s`
}

/** Compact signed delta (e.g. "+12m", "-1.2h"). */
export function formatRhythmDelta(deltaSec: number): string {
  if (!Number.isFinite(deltaSec) || Math.abs(deltaSec) < 30) return "—"
  const sign = deltaSec > 0 ? "+" : "−"
  return `${sign}${formatRhythmDuration(Math.abs(deltaSec))}`
}

/** 24h clock string like "22:30" → "10:30 PM" in local locale. */
export function formatClockLabel(hhmm: string | null | undefined): string | null {
  if (!hhmm) return null
  const match = /^(\d{1,2}):(\d{2})$/.exec(hhmm.trim())
  if (!match) return hhmm
  const hour = Number(match[1])
  const minute = Number(match[2])
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return hhmm
  const d = new Date()
  d.setHours(hour, minute, 0, 0)
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
}

export function rhythmRangeLabel(range: "day" | "week" | "month"): string {
  if (range === "day") return "Today"
  if (range === "week") return "This week"
  return "This month"
}

export function sleepConsistencyLabel(
  value: "steady" | "mixed" | "variable" | null | undefined,
): string | null {
  if (!value) return null
  if (value === "steady") return "Steady bedtime"
  if (value === "mixed") return "Mixed bedtime"
  return "Variable bedtime"
}
