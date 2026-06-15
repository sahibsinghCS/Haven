"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  createMood,
  deleteMood,
  deleteMoodBurst,
  deleteMoodFrame,
  fetchMoodBursts,
  fetchMoodCollectionStatus,
  fetchMoods,
  fetchTrainingJob,
  recordTrainingConsent,
  startMoodCollection,
  startMoodTraining,
  stopMoodCollection,
} from "@/lib/roomos/api-client"
import { registerMoodLabels } from "@/lib/roomos/state-meta"
import type { MoodsResponse } from "@/types/roomos"

export const MOODS_QUERY_KEY = ["roomos", "moods"] as const

function burstsKey(moodId: string) {
  return ["roomos", "moods", moodId, "bursts"] as const
}

function collectionKey(moodId: string) {
  return ["roomos", "moods", moodId, "collection"] as const
}

function trainingJobKey(jobId: string) {
  return ["roomos", "training", jobId] as const
}

export function useMoods() {
  return useQuery({
    queryKey: MOODS_QUERY_KEY,
    queryFn: async ({ signal }) => {
      const data = await fetchMoods(signal)
      registerMoodLabels(data.moods)
      return data
    },
    staleTime: 5_000,
    retry: 1,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.collection?.active || data?.trainingActive) return 1_000
      return false
    },
  })
}

export function useMoodBursts(
  moodId: string | null,
  enabled = true,
  roomId?: string | null,
) {
  return useQuery({
    queryKey: [...burstsKey(moodId ?? ""), roomId ?? "all"],
    queryFn: ({ signal }) => fetchMoodBursts(moodId!, signal, roomId),
    enabled: Boolean(moodId) && enabled,
    staleTime: 2_000,
    refetchInterval: (query) => {
      const session = query.state.data?.session
      return session?.active ? 1_500 : false
    },
  })
}

export function useMoodCollectionStatus(moodId: string | null, enabled = true) {
  return useQuery({
    queryKey: collectionKey(moodId ?? ""),
    queryFn: ({ signal }) => fetchMoodCollectionStatus(moodId!, signal),
    enabled: Boolean(moodId) && enabled,
    refetchInterval: 1_000,
  })
}

export function useTrainingJob(jobId: string | null) {
  return useQuery({
    queryKey: trainingJobKey(jobId ?? ""),
    queryFn: ({ signal }) => fetchTrainingJob(jobId!, signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const phase = query.state.data?.phase
      if (!phase || phase === "done" || phase === "error") return false
      return 800
    },
  })
}

export function useMoodMutations() {
  const qc = useQueryClient()

  const invalidateMoods = () => void qc.invalidateQueries({ queryKey: MOODS_QUERY_KEY })

  const create = useMutation({
    mutationFn: createMood,
    onSuccess: (mood) => {
      registerMoodLabels([mood])
      invalidateMoods()
      toast.success(`Added “${mood.displayName}”`)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const remove = useMutation({
    mutationFn: (args: { moodId: string; deleteData?: boolean }) =>
      deleteMood(args.moodId, { deleteData: args.deleteData }),
    onSuccess: () => {
      invalidateMoods()
      void qc.invalidateQueries({ queryKey: ["roomos", "preferences"] })
      toast.success("Mood removed")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const consent = useMutation({
    mutationFn: (accepted: boolean) => recordTrainingConsent(accepted),
    onSuccess: invalidateMoods,
    onError: (e: Error) => toast.error(e.message),
  })

  const startCollection = useMutation({
    mutationFn: (args: { moodId: string; durationSec: number; roomIds?: string[] }) =>
      startMoodCollection(args.moodId, args.durationSec, args.roomIds),
    onSuccess: (_data, vars) => {
      invalidateMoods()
      void qc.invalidateQueries({ queryKey: collectionKey(vars.moodId) })
      void qc.invalidateQueries({ queryKey: burstsKey(vars.moodId) })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const stopCollection = useMutation({
    mutationFn: stopMoodCollection,
    onSuccess: (_data, moodId) => {
      invalidateMoods()
      void qc.invalidateQueries({ queryKey: collectionKey(moodId) })
      void qc.invalidateQueries({ queryKey: burstsKey(moodId) })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const train = useMutation({
    mutationFn: startMoodTraining,
    onSuccess: () => invalidateMoods(),
    onError: (e: Error) => toast.error(e.message),
  })

  const deleteBurst = useMutation({
    mutationFn: (args: { moodId: string; burstId: string }) =>
      deleteMoodBurst(args.moodId, args.burstId),
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({ queryKey: burstsKey(vars.moodId) })
      invalidateMoods()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const deleteFrame = useMutation({
    mutationFn: (args: { moodId: string; burstId: string; frameName: string }) =>
      deleteMoodFrame(args.moodId, args.burstId, args.frameName),
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({ queryKey: burstsKey(vars.moodId) })
      invalidateMoods()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return {
    create,
    remove,
    consent,
    startCollection,
    stopCollection,
    train,
    deleteBurst,
    deleteFrame,
    invalidateMoods,
  }
}

export function activeCollectionFromMoods(data: MoodsResponse | undefined) {
  return data?.collection?.active ? data.collection : null
}
