import {
  confidenceTier,
  findRunnerUp,
  isUncertainRead,
  sortedDistributionEntries,
} from "@/lib/roomos/live-confidence-utils"
import { roomStateLabel } from "@/lib/roomos/state-meta"
import type { LiveInferenceSnapshot, RoomStateDistribution, RoomStateId } from "@/types/roomos"

export type ExplainPipelineStep = {
  id: "burst" | "memory" | "smoothed"
  label: string
  detail: string
  active: boolean
  deltaPct?: number
}

export type LiveExplainSummary = {
  primary: RoomStateId
  primaryLabel: string
  shownPct: number
  burstPct: number | null
  smoothingDeltaPct: number
  smoothingChangedPrimary: boolean
  memoryApplied: boolean
  memoryExamples: number
  memoryMatches: number
  memoryInfluencePct: number
  memoryBoostedLabel: string | null
  uncertain: boolean
  runnerUp: { id: string; label: string; pct: number } | null
  confidenceTier: ReturnType<typeof confidenceTier>
  verdict: string
  pipeline: ExplainPipelineStep[]
  topStates: Array<{ id: string; label: string; pct: number; isPrimary: boolean }>
  rationalePreview: string[]
  rationaleMore: string[]
  hasRationale: boolean
  roomId: string | null
  sequence: number
}

function pct(value: number): number {
  return Math.round(value * 100)
}

function primaryPct(dist: RoomStateDistribution, primary: string): number {
  return pct(dist[primary] ?? 0)
}

export function buildLiveExplainSummary(snapshot: LiveInferenceSnapshot): LiveExplainSummary {
  const primary = snapshot.primaryState
  const primaryLabel = roomStateLabel(primary)
  const shownDist = snapshot.distribution
  const burstDist = snapshot.modelDistribution ?? null
  const shownPct = primaryPct(shownDist, primary)
  const burstPct = burstDist ? primaryPct(burstDist, primary) : null
  const smoothingDeltaPct = burstPct != null ? shownPct - burstPct : 0
  const uncertain = isUncertainRead(shownDist, primary)
  const runner = findRunnerUp(shownDist, primary)
  const tier = confidenceTier(shownPct)

  const p = snapshot.personalization
  const memoryApplied = Boolean(p?.applied)
  const memoryExamples = p?.memoryExamples ?? p?.examples ?? 0
  const memoryMatches = p?.matches ?? 0
  const memoryInfluencePct = Math.round((p?.influence ?? 0) * 100)
  const memoryBoostedLabel = p?.boostedLabel ? roomStateLabel(p.boostedLabel) : null

  const burstLeader = burstDist
    ? sortedDistributionEntries(burstDist)[0]
    : null
  const smoothingChangedPrimary =
    Boolean(burstLeader && burstLeader[0] !== primary && Math.abs(smoothingDeltaPct) >= 2)

  let verdict: string
  if (uncertain && runner) {
    verdict = `${primaryLabel} leads at ${shownPct}% — ${roomStateLabel(runner.id)} is close at ${pct(runner.value)}%.`
  } else if (tier === "low") {
    verdict = `Low confidence (${shownPct}%) — treat automation cautiously this burst.`
  } else if (memoryApplied && Math.abs(smoothingDeltaPct) >= 2) {
    verdict = `${primaryLabel} after room memory and temporal smoothing.`
  } else if (memoryApplied) {
    verdict = `${primaryLabel} — room memory influenced this burst read.`
  } else if (Math.abs(smoothingDeltaPct) >= 2) {
    verdict = `${primaryLabel} — smoothing adjusted the burst read by ${smoothingDeltaPct > 0 ? "+" : ""}${smoothingDeltaPct}%.`
  } else {
    verdict = `${primaryLabel} leads this burst at ${shownPct}% confidence.`
  }

  const pipeline: ExplainPipelineStep[] = []

  if (burstPct != null) {
    pipeline.push({
      id: "burst",
      label: "Burst read",
      detail: `${primaryLabel} ${burstPct}%`,
      active: true,
    })
  }

  pipeline.push({
    id: "memory",
    label: "Room memory",
    detail: memoryApplied
      ? memoryMatches > 0
        ? `${memoryMatches} similar · ${memoryInfluencePct}% blend`
        : `Active · ${memoryExamples} saved`
      : memoryExamples > 0
        ? `${memoryExamples} saved · no match`
        : "Not applied",
    active: memoryApplied,
    deltaPct: memoryApplied && memoryBoostedLabel ? undefined : undefined,
  })

  pipeline.push({
    id: "smoothed",
    label: "Smoothed",
    detail: `${primaryLabel} ${shownPct}%`,
    active: true,
    deltaPct: burstPct != null && smoothingDeltaPct !== 0 ? smoothingDeltaPct : undefined,
  })

  const topStates = sortedDistributionEntries(shownDist)
    .filter(([, value]) => value >= 0.005)
    .slice(0, 6)
    .map(([id, value]) => ({
      id,
      label: roomStateLabel(id),
      pct: pct(value),
      isPrimary: id === primary,
    }))

  const rationale = snapshot.rationale ?? []
  const rationalePreview = rationale.slice(0, 2)
  const rationaleMore = rationale.slice(2)

  return {
    primary,
    primaryLabel,
    shownPct,
    burstPct,
    smoothingDeltaPct,
    smoothingChangedPrimary,
    memoryApplied,
    memoryExamples,
    memoryMatches,
    memoryInfluencePct,
    memoryBoostedLabel,
    uncertain,
    runnerUp: runner
      ? { id: runner.id, label: roomStateLabel(runner.id), pct: pct(runner.value) }
      : null,
    confidenceTier: tier,
    verdict,
    pipeline,
    topStates,
    rationalePreview,
    rationaleMore,
    hasRationale: rationale.length > 0,
    roomId: snapshot.roomId ?? snapshot.activeRoomId ?? null,
    sequence: snapshot.sequence ?? 0,
  }
}
