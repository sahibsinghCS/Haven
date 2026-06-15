"use client"

import Link from "next/link"
import { useCallback, useEffect, useState, type ReactNode } from "react"
import { Brain, Loader2, RefreshCw, Shield } from "lucide-react"

import {
  fetchFeedbackStatus,
  fetchTransitions,
  type FeedbackStatus,
} from "@/lib/roomos/api-client"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { cn } from "@/lib/utils"

export function TeachingLoopSummary({
  variant = "light",
  className,
}: {
  variant?: "light" | "dark"
  className?: string
}) {
  const [status, setStatus] = useState<FeedbackStatus | null>(null)
  const [pendingTransitions, setPendingTransitions] = useState(0)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [fb, tr] = await Promise.all([
        fetchFeedbackStatus(),
        fetchTransitions({ limit: 1, uncorrectedOnly: true }),
      ])
      setStatus(fb)
      setPendingTransitions(tr.pendingReview ?? 0)
    } catch {
      setStatus(null)
      setPendingTransitions(0)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const isDark = variant === "dark"
  const shell = isDark
    ? cn(roomosUi.liveOverlayGlass, "border-white/10")
    : cn(roomosUi.prefsCallout, "border-[color:var(--haven-line-strong)]")

  const ar = status?.autoRetrain
  const examples = status?.memoryExamples ?? 0

  return (
    <section className={cn(shell, "p-4 sm:p-5", className)} aria-labelledby="teaching-loop-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Brain
              className={cn("size-4 shrink-0", isDark ? "text-teal-300" : "text-teal-700")}
              aria-hidden
            />
            <h2
              id="teaching-loop-heading"
              className={cn(
                "haven-section-title text-[1.15rem]",
                isDark ? "text-zinc-100" : "text-[color:var(--haven-ink)]",
              )}
            >
              Teaching loop
            </h2>
          </div>
          <p
            className={cn(
              "haven-lede mt-1.5 max-w-xl",
              isDark ? "text-zinc-400" : "text-[color:var(--haven-muted)]",
            )}
          >
            Corrections and switch reviews stay on this machine. They bias room memory immediately;
            enough answers can trigger a local XGBoost retrain — never uploaded.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          className={cn(
            "inline-flex size-8 items-center justify-center rounded-lg border",
            isDark
              ? "border-white/10 bg-black/30 text-zinc-400 hover:text-zinc-200"
              : "border-[color:var(--haven-line)] bg-white/80 text-[color:var(--haven-muted)] hover:text-[color:var(--haven-ink)]",
            roomosUi.focusRingLight,
          )}
          aria-label="Refresh teaching stats"
        >
          <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
        </button>
      </div>

      <dl className="mt-4 grid gap-2 sm:grid-cols-3">
        <StatTile
          label="Memory examples"
          value={loading ? "…" : String(examples)}
          hint="Right/wrong answers stored"
          isDark={isDark}
        />
        <StatTile
          label="Switches to review"
          value={loading ? "…" : String(pendingTransitions)}
          hint={pendingTransitions > 0 ? "Open Review tab below" : "Caught up"}
          isDark={isDark}
          highlight={pendingTransitions > 0}
        />
        <StatTile
          label="Auto-retrain"
          value={
            loading ? (
              "…"
            ) : ar?.enabled ? (
              ar.running ? (
                <span className="inline-flex items-center gap-1">
                  <Loader2 className="size-3 animate-spin" /> Running
                </span>
              ) : (
                `${ar.correctionsSinceLastRun ?? 0}/${ar.minCorrections ?? 3}`
              )
            ) : (
              "Off"
            )
          }
          hint={
            ar?.enabled
              ? "Corrections until background retrain"
              : "Enable via live feedback settings"
          }
          isDark={isDark}
        />
      </dl>

      <div
        className={cn(
          "mt-4 flex flex-wrap items-center gap-3 border-t pt-3 text-[11px]",
          isDark ? "border-white/10 text-zinc-500" : "border-[color:var(--haven-line)] text-[color:var(--haven-muted)]",
        )}
      >
        <span className="inline-flex items-center gap-1.5">
          <Shield className="size-3.5 shrink-0" aria-hidden />
          Local-first · data stays on this device
        </span>
        <Link
          href="/live"
          className={cn(
            "font-semibold underline-offset-2 hover:underline",
            isDark ? "text-teal-300" : "text-teal-800",
          )}
        >
          Correct on Live
        </Link>
        {pendingTransitions > 0 ? (
          <Link
            href="/review"
            className={cn(
              "font-semibold underline-offset-2 hover:underline",
              isDark ? "text-teal-300" : "text-teal-800",
            )}
          >
            Review {pendingTransitions} switch{pendingTransitions === 1 ? "" : "es"}
          </Link>
        ) : null}
      </div>
    </section>
  )
}

function StatTile({
  label,
  value,
  hint,
  isDark,
  highlight,
}: {
  label: string
  value: ReactNode
  hint: string
  isDark: boolean
  highlight?: boolean
}) {
  return (
    <div
      className={cn(
        "rounded-xl border px-3 py-2.5",
        isDark
          ? "border-white/[0.08] bg-black/25"
          : "border-[color:var(--haven-line)] bg-white/60",
        highlight && !isDark && "border-amber-400/40 bg-amber-50/80",
        highlight && isDark && "border-amber-400/30 bg-amber-950/30",
      )}
    >
      <dt className="haven-eyebrow text-[color:var(--haven-faint)]">{label}</dt>
      <dd
        className={cn(
          "haven-stat-value mt-1 text-lg",
          isDark ? "text-zinc-50" : "text-[color:var(--haven-ink)]",
        )}
      >
        {value}
      </dd>
      <dd className="mt-0.5 text-[10px] leading-snug opacity-80">{hint}</dd>
    </div>
  )
}
