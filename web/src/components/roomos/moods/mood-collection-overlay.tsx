"use client"

import { useEffect } from "react"
import { Camera, Square, Timer } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { useMoodMutations, useMoodCollectionStatus, useMoods } from "@/hooks/use-moods"
import { roomStateLabel } from "@/lib/roomos/state-meta"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useMoodSessionStore } from "@/stores/mood-session-store"
import { cn } from "@/lib/utils"

function formatTime(sec: number): string {
  const s = Math.max(0, Math.round(sec))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${String(r).padStart(2, "0")}`
}

export function MoodCollectionOverlay({
  moodId,
  previewDark,
  onCollectionEnded,
}: {
  moodId: string
  previewDark?: boolean
  onCollectionEnded?: () => void
}) {
  const { data: moodsData } = useMoods()
  const { data: statusData } = useMoodCollectionStatus(moodId, true)
  const { stopCollection } = useMoodMutations()
  const openBurstReview = useMoodSessionStore((s) => s.openBurstReview)

  const session = statusData?.session ?? moodsData?.collection ?? null
  const dataset = statusData?.dataset
  const minimums = statusData?.minimums
  const recommended = statusData?.recommended
  const burstTotal = Math.max(session?.burstsSaved ?? 0, dataset?.burstCount ?? 0)
  const frameTotal = Math.max(session?.framesSaved ?? 0, dataset?.frameCount ?? 0)
  const minBursts = minimums?.bursts ?? 12
  const recBursts = recommended?.bursts ?? 20
  const canStopCapture = burstTotal >= minBursts && frameTotal >= (minimums?.frames ?? 60)
  const active = session?.active && session.moodId === moodId
  const elapsed = session?.elapsedSec ?? 0
  const remaining = session?.remainingSec ?? 0
  const duration = session?.durationSec ?? 300
  const progress = duration > 0 ? Math.min(100, (elapsed / duration) * 100) : 0

  useEffect(() => {
    if (session && !session.active && session.moodId === moodId && session.stopReason) {
      onCollectionEnded?.()
    }
  }, [session, moodId, onCollectionEnded])

  if (!session || session.moodId !== moodId) return null

  return (
    <div
      className="pointer-events-none absolute inset-x-0 top-14 z-40 flex justify-center px-4 sm:top-16"
      role="status"
      aria-live="polite"
    >
      <div
        className={cn(
          roomosUi.liveOverlayGlass,
          "pointer-events-auto w-full max-w-md border-teal-400/25 px-4 py-4 shadow-2xl sm:px-5",
          !active && "border-white/15",
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-teal-200/90">
              {active ? "Training capture" : "Capture finished"}
            </p>
            <p className="mt-1 truncate text-base font-semibold text-zinc-50">
              {roomStateLabel(moodId)}
            </p>
          </div>
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-teal-500/15 text-teal-200 ring-1 ring-teal-400/25">
            <Camera className="size-4" aria-hidden />
          </span>
        </div>

        {active ? (
          <>
            <div className="mt-3 flex items-center justify-between text-[12px] text-zinc-300">
              <span className="inline-flex items-center gap-1.5">
                <Timer className="size-3.5" aria-hidden />
                {formatTime(remaining)} left
              </span>
              <span className="font-mono tabular-nums text-zinc-500">
                {burstTotal}/{minBursts} bursts min
                {recBursts > minBursts ? ` · ${recBursts} rec.` : ""}
              </span>
            </div>
            <p className="mt-1 text-[10px] leading-relaxed text-zinc-500">
              {frameTotal} frames saved for {roomStateLabel(moodId)} on your device — only these
              photos train this mood, not the built-in multi-room Sleep/Work dataset.
            </p>
            <Progress value={progress} className="mt-2 h-1.5 bg-white/10" />
            {previewDark ? (
              <p className="mt-2 text-[11px] leading-relaxed text-amber-200/90">
                Scene looks dark — add light so frames are usable.
              </p>
            ) : null}
            {session.skipped ? (
              <p className="mt-1 text-[10px] text-zinc-500">
                Skipped: {session.skipped.dark} dark · {session.skipped.blurry} blurry ·{" "}
                {session.skipped.duplicate} duplicate
              </p>
            ) : null}
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="mt-3 h-9 w-full gap-2 rounded-full border-white/15 bg-white/5 text-zinc-100 hover:bg-white/10"
              disabled={stopCollection.isPending || !canStopCapture}
              onClick={() => void stopCollection.mutateAsync(moodId)}
            >
              <Square className="size-3.5" aria-hidden />
              {canStopCapture ? "Finish capture" : `Need ${minBursts - burstTotal} more bursts`}
            </Button>
            {!canStopCapture ? (
              <p className="mt-2 text-[10px] leading-relaxed text-amber-200/90">
                Keep acting out this mood until you hit the minimum. Stopping early used to allow
                training with too few photos.
              </p>
            ) : null}
          </>
        ) : (
          <div className="mt-3 space-y-2">
            <p className="text-[12px] leading-relaxed text-zinc-300">
              Saved {frameTotal} frames in {burstTotal} bursts for this mood.
              {statusData?.readyToTrain
                ? statusData.meetsRecommended
                  ? " Ready to train the model."
                  : " Minimum reached — more varied poses help accuracy."
                : ` Need ${Math.max(0, minBursts - burstTotal)} more bursts before training.`}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                className="h-8 rounded-full bg-white/10 text-zinc-100 hover:bg-white/15"
                onClick={() => openBurstReview(moodId)}
              >
                Review bursts
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
