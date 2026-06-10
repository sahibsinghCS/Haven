"use client"

import { create } from "zustand"

type MoodSessionStore = {
  /** Mood id to auto-start collection for on /live mount. */
  pendingCollectMoodId: string | null
  pendingCollectDurationSec: number
  /** Active training job id for full-screen progress overlay. */
  activeTrainingJobId: string | null
  /** Mood id linked to the active training job. */
  activeTrainingMoodId: string | null
  /** Open burst review panel for this mood (preferences or live). */
  reviewMoodId: string | null
  setPendingCollect: (moodId: string, durationSec?: number) => void
  clearPendingCollect: () => void
  setActiveTraining: (jobId: string, moodId: string) => void
  clearActiveTraining: () => void
  openBurstReview: (moodId: string) => void
  closeBurstReview: () => void
}

export const useMoodSessionStore = create<MoodSessionStore>((set) => ({
  pendingCollectMoodId: null,
  pendingCollectDurationSec: 300,
  activeTrainingJobId: null,
  activeTrainingMoodId: null,
  reviewMoodId: null,
  setPendingCollect: (moodId, durationSec = 300) =>
    set({ pendingCollectMoodId: moodId, pendingCollectDurationSec: durationSec }),
  clearPendingCollect: () => set({ pendingCollectMoodId: null }),
  setActiveTraining: (jobId, moodId) =>
    set({ activeTrainingJobId: jobId, activeTrainingMoodId: moodId }),
  clearActiveTraining: () =>
    set({ activeTrainingJobId: null, activeTrainingMoodId: null }),
  openBurstReview: (moodId) => set({ reviewMoodId: moodId }),
  closeBurstReview: () => set({ reviewMoodId: null }),
}))
