export type RhythmRange = "day" | "week" | "month"

export type RhythmMoodSlice = {
  id: string
  label: string
  seconds: number
  percent: number
}

export type RhythmHighlights = {
  moodSwitches: number
  usualSleepStart: string | null
  sleepStartSamples: number
  sleepConsistency: "steady" | "mixed" | "variable" | null
  windDownMinutes: number | null
  deepWorkBlocks: number
  deepWorkMinutes: number
  awayHours: number
  estimatedSavingsUsd: number
  savingsIsEstimate: boolean
  savingsIncludesDryRun: boolean
  automationsRun: number
  avgConfidence: number | null
  uncertainPercent: number | null
}

export type RhythmDailyBreakdown = {
  date: string
  totalSec: number
  moods: Record<string, number>
}

export type RhythmSummary = {
  range: RhythmRange
  rangeStart: string
  rangeEnd: string
  timezone: string
  totalTrackedSec: number
  coverageNote: string | null
  moods: RhythmMoodSlice[]
  highlights: RhythmHighlights
  dailyBreakdown: RhythmDailyBreakdown[]
  comparison: {
    previousTotalSec: number
    moodDeltaSec: Record<string, number>
  }
  sources: {
    predictionsLog: string
    actionsLog: string
  }
}

export type RhythmSummaries = Record<RhythmRange, RhythmSummary>
