/**
 * Lightweight checks for setup-health pure helpers (run: npx tsx src/lib/roomos/setup-health.test.ts)
 */
import assert from "node:assert/strict"

import {
  confidenceTier,
  findRunnerUp,
  isUncertainRead,
} from "./live-confidence-utils"

assert.equal(confidenceTier(72), "high")
assert.equal(confidenceTier(50), "medium")
assert.equal(confidenceTier(30), "low")

const dist = { work: 0.52, sleep: 0.48, relaxing: 0.0, gaming: 0.0, away: 0.0 }
assert.equal(findRunnerUp(dist, "work")?.id, "sleep")
assert.equal(isUncertainRead(dist, "work"), true)

const clear = { work: 0.82, sleep: 0.1, relaxing: 0.04, gaming: 0.02, away: 0.02 }
assert.equal(isUncertainRead(clear, "work"), false)

console.log("setup-health.test.ts: ok")
