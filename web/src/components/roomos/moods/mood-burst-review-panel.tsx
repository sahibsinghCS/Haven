"use client"

import { useMemo, useState } from "react"
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
import { useLiveSessionStore } from "@/stores/live-session-store"
import { moodBurstFrameUrl } from "@/lib/roomos/api-client"
import { roomStateLabel } from "@/lib/roomos/state-meta"
import { useMoodSessionStore } from "@/stores/mood-session-store"
import { cn } from "@/lib/utils"

export function MoodBurstReviewPanel() {
  const reviewMoodId = useMoodSessionStore((s) => s.reviewMoodId)
  const closeBurstReview = useMoodSessionStore((s) => s.closeBurstReview)
  const { data: moodsData } = useMoods()
  const rooms = useLiveSessionStore((s) => s.rooms)
  const [roomFilter, setRoomFilter] = useState<string | "all">("all")
  const { data, isLoading } = useMoodBursts(
    reviewMoodId,
    Boolean(reviewMoodId),
    roomFilter === "all" ? null : roomFilter,
  )
  const { deleteBurst, deleteFrame, train } = useMoodMutations()
  const setActiveTraining = useMoodSessionStore((s) => s.setActiveTraining)

  const mood = moodsData?.moods.find((m) => m.id === reviewMoodId)
  const bursts = data?.bursts ?? []
  const roomOptions = useMemo(() => {
    const ids = new Set(bursts.map((b) => b.roomId).filter(Boolean) as string[])
    return rooms.filter((r) => ids.has(r.id))
  }, [bursts, rooms])
  const readyToTrain = data?.readyToTrain ?? false
  const meetsRecommended = data?.meetsRecommended ?? false
  const minimums = data?.minimums
  const recommended = data?.recommended
  const dataset = data?.dataset

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
          {roomOptions.length > 0 ? (
            <div className="mb-4 flex flex-wrap gap-2">
              <button
                type="button"
                className={cn(
                  "rounded-full border px-3 py-1 text-[11px]",
                  roomFilter === "all"
                    ? "border-teal-500/40 bg-teal-500/10 text-teal-900"
                    : "border-[color:var(--haven-line)] text-[color:var(--haven-muted)]",
                )}
                onClick={() => setRoomFilter("all")}
              >
                All rooms
              </button>
              {roomOptions.map((room) => (
                <button
                  key={room.id}
                  type="button"
                  className={cn(
                    "rounded-full border px-3 py-1 text-[11px]",
                    roomFilter === room.id
                      ? "border-teal-500/40 bg-teal-500/10 text-teal-900"
                      : "border-[color:var(--haven-line)] text-[color:var(--haven-muted)]",
                  )}
                  onClick={() => setRoomFilter(room.id)}
                >
                  {room.name}
                </button>
              ))}
            </div>
          ) : null}
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
                        {burst.roomName ? ` · ${burst.roomName}` : null}
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
              Your captures: {dataset?.burstCount ?? 0} bursts · {dataset?.frameCount ?? 0}{" "}
              frames on this device.
              <br />
              Required to train: {minimums.bursts} bursts / {minimums.frames} frames.
              {recommended ? (
                <>
                  {" "}
                  Recommended: {recommended.bursts} bursts / {recommended.frames} frames.
                </>
              ) : null}
              {readyToTrain
                ? meetsRecommended
                  ? " You meet the recommended amount."
                  : " Minimum met — more variety (poses, lighting) still helps."
                : " Keep collecting on Live before training."}
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
