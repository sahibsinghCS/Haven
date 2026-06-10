"use client"

import { Trash2, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { useMoodBursts, useMoodMutations, useMoods } from "@/hooks/use-moods"
import { moodBurstFrameUrl } from "@/lib/roomos/api-client"
import { roomStateLabel } from "@/lib/roomos/state-meta"
import { useMoodSessionStore } from "@/stores/mood-session-store"
import { cn } from "@/lib/utils"

export function MoodBurstReviewPanel() {
  const reviewMoodId = useMoodSessionStore((s) => s.reviewMoodId)
  const closeBurstReview = useMoodSessionStore((s) => s.closeBurstReview)
  const { data: moodsData } = useMoods()
  const { data, isLoading } = useMoodBursts(reviewMoodId, Boolean(reviewMoodId))
  const { deleteBurst, deleteFrame, train } = useMoodMutations()
  const setActiveTraining = useMoodSessionStore((s) => s.setActiveTraining)

  const mood = moodsData?.moods.find((m) => m.id === reviewMoodId)
  const bursts = data?.bursts ?? []
  const readyToTrain = data?.readyToTrain ?? false
  const minimums = data?.minimums

  async function handleTrain() {
    if (!reviewMoodId) return
    const job = await train.mutateAsync(reviewMoodId)
    setActiveTraining(job.id, reviewMoodId)
    closeBurstReview()
  }

  return (
    <Sheet open={Boolean(reviewMoodId)} onOpenChange={(open) => !open && closeBurstReview()}>
      <SheetContent side="right" className="flex w-full flex-col gap-0 p-0 sm:max-w-lg">
        <SheetHeader className="border-b border-[color:var(--haven-line)] px-5 py-4 text-left">
          <SheetTitle className="haven-display text-lg font-semibold">
            Review captures — {mood ? roomStateLabel(mood.id) : ""}
          </SheetTitle>
          <SheetDescription className="text-[13px]">
            Delete bad frames or whole bursts before training. Data stays on this device.
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {isLoading ? (
            <p className="text-sm text-[color:var(--haven-muted)]">Loading bursts…</p>
          ) : bursts.length === 0 ? (
            <p className="text-sm text-[color:var(--haven-muted)]">
              No bursts yet. Teach the camera on Live to collect frames.
            </p>
          ) : (
            <ul className="space-y-4">
              {bursts.map((burst) => (
                <li
                  key={burst.id}
                  className="rounded-xl border border-[color:var(--haven-line)] bg-white/60 p-3"
                >
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-[11px] text-[color:var(--haven-faint)]">
                        {burst.id}
                      </p>
                      <p className="text-[12px] text-[color:var(--haven-muted)]">
                        {burst.frameCount} frames
                        {burst.meanLuma != null ? ` · luma ${burst.meanLuma.toFixed(0)}` : ""}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-8 shrink-0 text-rose-700 hover:bg-rose-50"
                      aria-label="Delete burst"
                      disabled={deleteBurst.isPending}
                      onClick={() => {
                        if (!reviewMoodId) return
                        void deleteBurst.mutateAsync({
                          moodId: reviewMoodId,
                          burstId: burst.id,
                        })
                      }}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                  <div className="grid grid-cols-5 gap-1">
                    {burst.frames.map((frame) => (
                      <div key={frame} className="group relative aspect-[4/3] overflow-hidden rounded-md bg-stone-200">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={moodBurstFrameUrl(reviewMoodId!, burst.id, frame)}
                          alt=""
                          className="size-full object-cover"
                          loading="lazy"
                        />
                        <button
                          type="button"
                          className={cn(
                            "absolute right-0.5 top-0.5 flex size-5 items-center justify-center rounded bg-black/55 text-white opacity-0 transition group-hover:opacity-100",
                          )}
                          aria-label={`Delete ${frame}`}
                          onClick={() => {
                            if (!reviewMoodId) return
                            void deleteFrame.mutateAsync({
                              moodId: reviewMoodId,
                              burstId: burst.id,
                              frameName: frame,
                            })
                          }}
                        >
                          <X className="size-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="border-t border-[color:var(--haven-line)] px-5 py-4">
          {minimums ? (
            <p className="mb-3 text-[12px] text-[color:var(--haven-muted)]">
              Minimum to train: {minimums.bursts} bursts and {minimums.frames} frames.
              {readyToTrain ? " You have enough." : " Keep collecting if needed."}
            </p>
          ) : null}
          <Button
            type="button"
            className="w-full rounded-full"
            disabled={!readyToTrain || train.isPending}
            onClick={() => void handleTrain()}
          >
            {train.isPending ? "Starting training…" : "Train model"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
