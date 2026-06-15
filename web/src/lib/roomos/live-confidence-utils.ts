import type { RoomStateDistribution } from "@/types/roomos"

export type ConfidenceTier = "high" | "medium" | "low"

export function confidenceTier(pct: number): ConfidenceTier {
  if (pct >= 70) return "high"
  if (pct >= 45) return "medium"
  return "low"
}

export function findRunnerUp(
  distribution: RoomStateDistribution,
  primary: string,
): { id: string; value: number } | null {
  let best: { id: string; value: number } | null = null
  for (const [id, value] of Object.entries(distribution)) {
    if (id === primary) continue
    if (!best || value > best.value) best = { id, value }
  }
  return best
}

/** True when the read is close between top labels or overall confidence is weak. */
export function isUncertainRead(
  distribution: RoomStateDistribution,
  primary: string,
  gapThreshold = 0.15,
): boolean {
  const primaryVal = distribution[primary] ?? 0
  if (primaryVal < 0.55) return true
  const runner = findRunnerUp(distribution, primary)
  if (!runner) return false
  return runner.value >= primaryVal - gapThreshold
}

export function sortedDistributionEntries(
  distribution: RoomStateDistribution,
): Array<[string, number]> {
  return Object.entries(distribution).sort((a, b) => b[1] - a[1])
}
