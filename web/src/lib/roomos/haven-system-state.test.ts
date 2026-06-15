/**
 * run: npx tsx src/lib/roomos/haven-system-state.test.ts
 */
import assert from "node:assert/strict"

import {
  classifyLiveFailure,
  resolveInferenceDisplayMode,
} from "./haven-system-state"

assert.equal(resolveInferenceDisplayMode("bootstrap", "roomos-ml"), "demo_model")
assert.equal(resolveInferenceDisplayMode("personal", "roomos-ml"), "live")
assert.equal(resolveInferenceDisplayMode("trained", "demo-replay"), "replay")

assert.equal(
  classifyLiveFailure({
    engineStatus: "error",
    liveStatus: "error",
    engineMessage: null,
    liveMessage: "Failed to fetch",
    compatReport: null,
  }),
  "api_offline",
)

assert.equal(
  classifyLiveFailure({
    engineStatus: "error",
    liveStatus: "connecting",
    engineMessage: "DroidCam at http://192.168.1.18:4747/video is busy",
    liveMessage: null,
    compatReport: null,
  }),
  "camera_error",
)

assert.equal(
  classifyLiveFailure({
    engineStatus: "error",
    liveStatus: "error",
    engineMessage: "compatibility check failed",
    liveMessage: null,
    compatReport: { ok: false, mismatches: [{ category: "features", field: "x", train: "a", inference: "b" }], bundle_dir: "", inference_config: "", train_config_source: "", bundle_classes: [], inference_classes: [], n_bundle_columns: 0, n_expected_columns: 0 },
  }),
  "compat_error",
)

console.log("haven-system-state.test.ts: ok")
