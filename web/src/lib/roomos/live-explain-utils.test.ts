/**
 * Pure helper checks (run: npx tsx src/lib/roomos/live-explain-utils.test.ts)
 */
import assert from "node:assert/strict"

import { buildLiveExplainSummary } from "./live-explain-utils"
import type { LiveInferenceSnapshot } from "@/types/roomos"

function baseSnapshot(overrides: Partial<LiveInferenceSnapshot> = {}): LiveInferenceSnapshot {
  return {
    schemaVersion: 1,
    sequence: 1,
    capturedAt: new Date().toISOString(),
    stream: { streamUrl: null, posterUrl: null, aspectLabel: "16/9" },
    primaryState: "relaxing",
    primaryConfidence: 0.62,
    distribution: { relaxing: 0.62, work: 0.28, sleep: 0.1 },
    modelDistribution: { relaxing: 0.55, work: 0.32, sleep: 0.13 },
    rationale: ["Very little motion in the burst."],
    appliedScene: {},
    confidenceHistory: [],
    ...overrides,
  }
}

const smoothed = buildLiveExplainSummary(baseSnapshot())
assert.equal(smoothed.shownPct, 62)
assert.equal(smoothed.burstPct, 55)
assert.equal(smoothed.smoothingDeltaPct, 7)

const memory = buildLiveExplainSummary(
  baseSnapshot({
    personalization: {
      applied: true,
      memoryExamples: 12,
      matches: 2,
      influence: 0.38,
      boostedLabel: "relaxing",
    },
  }),
)
assert.equal(memory.memoryApplied, true)
assert.equal(memory.memoryMatches, 2)

const empty = buildLiveExplainSummary(
  baseSnapshot({
    modelDistribution: undefined,
    rationale: [],
    distribution: { work: 0.4, relaxing: 0.35, sleep: 0.25 },
    primaryState: "work",
  }),
)
assert.equal(empty.burstPct, null)
assert.equal(empty.hasRationale, false)
assert.equal(empty.uncertain, true)

console.log("live-explain-utils.test.ts: ok")
