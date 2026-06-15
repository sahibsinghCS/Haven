"use client"

import { Loader2 } from "lucide-react"

import { Progress } from "@/components/ui/progress"
import { useMoods, useTrainingJob } from "@/hooks/use-moods"
import { roomStateLabel } from "@/lib/roomos/state-meta"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useMoodSessionStore } from "@/stores/mood-session-store"
import type { TrainingJobPhase } from "@/types/roomos"
import { cn } from "@/lib/utils"

const PHASE_LABEL: Record<TrainingJobPhase, string> = {
  queued: "Queued on this device",
  extracting_features: "Extracting features from saved bursts",
  training: "Training personal XGBoost head",
  validating: "Validating on hold-out bursts",
  promoting: "Applying new model weights",
  reloading: "Reloading live camera pipeline",
  done: "Training complete",
  error: "Training failed",
}

/** Non-blocking training status for preferences — honest phases, no full-screen overlay. */
export function PreferencesTrainingInline() {
  const jobId = useMoodSessionStore((s) => s.activeTrainingJobId)
  const moodId = useMoodSessionStore((s) => s.activeTrainingMoodId)
  const { data: moodsData } = useMoods()
  const { data: job } = useTrainingJob(jobId)

  const activeFromApi = moodsData?.trainingActive
  const phase = job?.phase
  const show =
    Boolean(jobId && job && phase && phase !== "done" && phase !== "error") || activeFromApi

  if (!show || !job) return null

  return (
    <section
      className={cn(roomosUi.prefsCallout, "border-violet-500/25 bg-violet-50/70 p-4 sm:p-5")}
      aria-live="polite"
      aria-labelledby="prefs-training-heading"
    >
      <div className="flex flex-wrap items-start gap-3">
        <Loader2 className="mt-0.5 size-5 shrink-0 animate-spin text-violet-700" aria-hidden />
        <div className="min-w-0 flex-1">
          <h2 id="prefs-training-heading" className="text-sm font-semibold text-violet-950">
            Training {moodId ? roomStateLabel(moodId) : "personal model"}
          </h2>
          <p className="mt-1 text-[12.5px] leading-relaxed text-violet-900/85">
            {PHASE_LABEL[phase ?? "queued"]}. This runs locally — live may briefly pause while
            weights reload.
          </p>
          <Progress value={(job.progress ?? 0) * 100} className="mt-3 h-1.5 bg-violet-200/60" />
          {job.warnings?.length ? (
            <ul className="mt-2 space-y-0.5 text-[11px] text-amber-900/90">
              {job.warnings.slice(0, 3).map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  )
}
