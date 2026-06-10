"use client"

import { useEffect } from "react"
import { CheckCircle2, Loader2, XCircle } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { useMoodMutations, useMoods, useTrainingJob } from "@/hooks/use-moods"
import { roomStateLabel } from "@/lib/roomos/state-meta"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useMoodSessionStore } from "@/stores/mood-session-store"
import type { TrainingJobPhase } from "@/types/roomos"
import { cn } from "@/lib/utils"

const PHASE_LABEL: Record<TrainingJobPhase, string> = {
  queued: "Queued…",
  extracting_features: "Extracting features…",
  training: "Training model…",
  validating: "Validating accuracy…",
  promoting: "Applying new model…",
  reloading: "Applying to live camera…",
  done: "Training complete",
  error: "Training failed",
}

export function MoodTrainingProgress() {
  const jobId = useMoodSessionStore((s) => s.activeTrainingJobId)
  const moodId = useMoodSessionStore((s) => s.activeTrainingMoodId)
  const clearActiveTraining = useMoodSessionStore((s) => s.clearActiveTraining)
  const { data: job } = useTrainingJob(jobId)
  const { invalidateMoods } = useMoodMutations()
  const { refetch: refetchMoods } = useMoods()

  const phase = job?.phase ?? "queued"
  const done = phase === "done"
  const failed = phase === "error"
  const active = Boolean(jobId) && !done && !failed

  useEffect(() => {
    if (done) {
      void refetchMoods()
      invalidateMoods()
    }
  }, [done, refetchMoods, invalidateMoods])

  if (!jobId || !job) return null

  return (
    <div
      className="absolute inset-0 z-50 flex items-center justify-center bg-black/75 p-6 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="mood-training-title"
    >
      <div
        className={cn(
          roomosUi.liveOverlayGlass,
          "w-full max-w-md border-white/10 px-6 py-8 text-center shadow-2xl",
        )}
      >
        {active ? (
          <Loader2 className="mx-auto size-10 animate-spin text-teal-300" aria-hidden />
        ) : done ? (
          <CheckCircle2 className="mx-auto size-10 text-emerald-400" aria-hidden />
        ) : (
          <XCircle className="mx-auto size-10 text-rose-400" aria-hidden />
        )}

        <h2
          id="mood-training-title"
          className="mt-4 text-lg font-semibold text-zinc-50"
        >
          {moodId ? roomStateLabel(moodId) : "Personal model"}
        </h2>
        <p className="mt-2 text-sm text-zinc-300">{PHASE_LABEL[phase]}</p>

        {active ? (
          <Progress value={job.progress * 100} className="mt-5 h-2 bg-white/10" />
        ) : null}

        {job.warnings?.length ? (
          <ul className="mt-4 max-h-24 overflow-y-auto text-left text-[11px] text-amber-200/90">
            {job.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        ) : null}

        {done && job.result ? (
          <p className="mt-4 text-[12px] leading-relaxed text-zinc-400">
            Accuracy {Math.round(job.result.accuracy * 100)}% on hold-out bursts.
            {job.result.clearedFrames > 0
              ? ` Training complete — ${job.result.clearedFrames} review frames cleared from device.`
              : ""}
          </p>
        ) : null}

        {failed ? (
          <p className="mt-4 text-[12px] text-rose-200/90">{job.error ?? "Unknown error"}</p>
        ) : null}

        {!active ? (
          <Button
            type="button"
            className="mt-6 rounded-full"
            onClick={clearActiveTraining}
          >
            {done ? "Continue" : "Close"}
          </Button>
        ) : null}
      </div>
    </div>
  )
}
