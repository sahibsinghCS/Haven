"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Activity, RefreshCw } from "lucide-react"

import { HavenOfflineBanner } from "@/components/roomos/haven-offline-banner"
import { HavenSurfaceState } from "@/components/roomos/haven-surface-state"
import { MoodTimeBars } from "@/components/roomos/rhythm/mood-time-bars"
import { RhythmDailyChart } from "@/components/roomos/rhythm/rhythm-daily-chart"
import { RhythmHighlights } from "@/components/roomos/rhythm/rhythm-highlights"
import { HavenDashboardSkeleton } from "@/components/roomos/haven-loading-states"
import { HavenPageHeader, havenCard, havenNavIsland } from "@/components/roomos/haven-primitives"
import { useMoods } from "@/hooks/use-moods"
import { fetchRhythmSummaries } from "@/lib/roomos/api-client"
import { DASHBOARD_STALE_MS } from "@/lib/roomos/dashboard-queries"
import {
  formatRhythmDelta,
  formatRhythmDuration,
  rhythmRangeLabel,
} from "@/lib/roomos/rhythm-format"
import { registerMoodLabels } from "@/lib/roomos/state-meta"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type { RhythmRange } from "@/types/rhythm"
import { ROOM_STATE_ORDER } from "@/types/roomos"
import { cn } from "@/lib/utils"

const RANGES: { id: RhythmRange; label: string }[] = [
  { id: "day", label: "Day" },
  { id: "week", label: "Week" },
  { id: "month", label: "Month" },
]

const cardShell = havenCard

export function RhythmPageClient() {
  const [range, setRange] = useState<RhythmRange>("week")
  const moodsQuery = useMoods()

  useEffect(() => {
    const moods = moodsQuery.data?.moods
    if (moods?.length) registerMoodLabels(moods)
  }, [moodsQuery.data?.moods])

  const rhythmQuery = useQuery({
    queryKey: ["roomos", "rhythm", "all"],
    queryFn: ({ signal }) => fetchRhythmSummaries(signal),
    staleTime: DASHBOARD_STALE_MS,
    retry: 1,
  })

  const moodOrder = useMemo(() => {
    const fromApi = moodsQuery.data?.moods.map((m) => m.id) ?? []
    return [...new Set([...ROOM_STATE_ORDER, ...fromApi])]
  }, [moodsQuery.data?.moods])

  const summary = rhythmQuery.data?.[range]
  const initialLoading = rhythmQuery.isPending
  const apiError = rhythmQuery.isError

  if (initialLoading) {
    return <HavenDashboardSkeleton />
  }

  if (apiError) {
    return (
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <RhythmHeader range={range} onRangeChange={setRange} disabled />
        <HavenOfflineBanner context="rhythm" />
        <HavenSurfaceState
          variant="light"
          tone="error"
          role="alert"
          title="Rhythm could not load"
          description={
            rhythmQuery.error instanceof Error
              ? rhythmQuery.error.message
              : "Haven may be offline on this machine. Start the backend and refresh."
          }
          footer={
            <button
              type="button"
              className={cn(
                "mt-4 inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-semibold",
                roomosUi.havenOutlineBtn,
              )}
              onClick={() => void rhythmQuery.refetch()}
            >
              <RefreshCw className="size-3.5" aria-hidden />
              Retry
            </button>
          }
          className="mx-auto"
        />
      </div>
    )
  }

  if (!summary) {
    return null
  }

  const empty = summary.totalTrackedSec <= 0
  const totalDelta = summary.totalTrackedSec - summary.comparison.previousTotalSec

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 pb-16">
      <RhythmHeader
        range={range}
        onRangeChange={setRange}
        onRefresh={() => void rhythmQuery.refetch()}
        refreshing={rhythmQuery.isFetching}
      />

      <div
        className={cn(
          "flex flex-col gap-8 transition-opacity duration-150",
          rhythmQuery.isFetching && !initialLoading && "opacity-80",
        )}
      >
        {empty && summary.coverageNote ? (
          <HavenSurfaceState
            variant="light"
            tone="empty"
            icon={<Activity className="size-5" aria-hidden />}
            title="Run Live to build your rhythm"
            description={summary.coverageNote}
            footer={
              <Link
                href="/live"
                className={cn(
                  "mt-4 inline-flex rounded-full px-5 py-2.5 text-[13px] font-semibold",
                  roomosUi.havenPrimaryBtn,
                )}
              >
                Open Live
              </Link>
            }
            className="mx-auto w-full max-w-xl"
          />
        ) : null}

        {!empty ? (
          <>
            <section className={cn(cardShell, "px-5 py-5 sm:px-6", roomosUi.pageEnterStagger1)}>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--haven-faint)]">
                {rhythmRangeLabel(summary.range)}
              </p>
              <p className="haven-display mt-1 text-[2rem] font-semibold leading-none text-[color:var(--haven-ink)] sm:text-[2.35rem]">
                {formatRhythmDuration(summary.totalTrackedSec)}
              </p>
              <p className="mt-2 text-[13px] text-[color:var(--haven-muted)]">
                {summary.comparison.previousTotalSec > 0 ? (
                  <>
                    {formatRhythmDelta(totalDelta)} vs prior{" "}
                    {range === "day" ? "day" : range === "week" ? "week" : "month"}
                  </>
                ) : (
                  "First period with tracked inference in this range"
                )}
              </p>
            </section>

            <div className={roomosUi.pageEnterStagger1}>
              <MoodTimeBars
                moods={summary.moods}
                totalTrackedSec={summary.totalTrackedSec}
                moodDeltas={summary.comparison.moodDeltaSec}
              />
            </div>

            <div className={roomosUi.pageEnterStagger2}>
              <RhythmHighlights highlights={summary.highlights} />
            </div>

            {summary.dailyBreakdown.length > 0 ? (
              <div className={roomosUi.pageEnterStagger2}>
                <RhythmDailyChart days={summary.dailyBreakdown} moodOrder={moodOrder} />
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  )
}

function RhythmHeader({
  range,
  onRangeChange,
  onRefresh,
  refreshing,
  disabled,
}: {
  range: RhythmRange
  onRangeChange: (r: RhythmRange) => void
  onRefresh?: () => void
  refreshing?: boolean
  disabled?: boolean
}) {
  return (
    <HavenPageHeader
      className={roomosUi.pageEnter}
      eyebrow="Insights"
      title="Rhythm"
      lede="How your moods add up over time — sleep patterns, focus blocks, and estimated savings from automations."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <div
            className={cn(havenNavIsland, "inline-flex p-0.5")}
            role="tablist"
            aria-label="Time range"
          >
            {RANGES.map((r) => {
              const active = range === r.id
              return (
                <button
                  key={r.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  disabled={disabled}
                  className={cn(
                    "rounded-full px-3.5 py-2 text-[13px] font-semibold transition-colors min-h-9",
                    roomosUi.focusRingLight,
                    active
                      ? "bg-[linear-gradient(168deg,#1d1c1a_0%,#0d0c0b_100%)] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]"
                      : "text-[color:var(--haven-muted)] hover:text-[color:var(--haven-ink)]",
                    disabled && "opacity-60",
                  )}
                  onClick={() => onRangeChange(r.id)}
                >
                  {r.label}
                </button>
              )
            })}
          </div>
          {onRefresh ? (
            <button
              type="button"
              aria-label="Refresh rhythm data"
              disabled={refreshing}
              className={cn(
                "inline-flex size-9 min-h-9 min-w-9 items-center justify-center rounded-full border border-[color:var(--haven-line-strong)]",
                "bg-[color-mix(in_oklab,#fffefb_92%,transparent)] text-[color:var(--haven-muted)] shadow-sm",
                roomosUi.focusRingLight,
              )}
              onClick={onRefresh}
            >
              <RefreshCw className={cn("size-4", refreshing && "animate-spin")} aria-hidden />
            </button>
          ) : null}
        </div>
      }
    />
  )
}
