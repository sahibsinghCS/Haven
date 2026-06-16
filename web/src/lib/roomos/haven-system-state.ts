import type { BootPhase, CompatReport, ModelKind } from "@/lib/roomos/api-client"
import type { LiveInferenceStatus } from "@/hooks/use-live-inference"
import type { LiveEngineHookStatus } from "@/hooks/use-live-engine"
import type { LiveInferenceSnapshot } from "@/types/roomos"

/** Operator-facing mode. one label per surface state. */
export type HavenSystemMode =
  | "camera_off"
  | "setup"
  | "booting"
  | "live"
  | "demo_model"
  | "replay"
  | "api_offline"
  | "compat_error"
  | "model_missing"
  | "engine_error"
  | "camera_error"

export type LiveFailureKind =
  | "api_offline"
  | "compat_error"
  | "model_missing"
  | "engine_error"
  | "camera_error"
  | "no_data"

export type InferenceDisplayMode = "live" | "demo_model" | "replay" | "unknown"

export function resolveInferenceDisplayMode(
  modelKind: ModelKind,
  dataSource?: string | null,
): InferenceDisplayMode {
  if (dataSource === "demo-replay") return "replay"
  if (modelKind === "bootstrap") return "demo_model"
  if (
    dataSource === "roomos-ml" ||
    modelKind === "personal" ||
    modelKind === "trained" ||
    modelKind === "generic"
  ) {
    return "live"
  }
  return "unknown"
}

export function isCameraRelatedMessage(message: string | null | undefined): boolean {
  if (!message) return false
  const lower = message.toLowerCase()
  return (
    lower.includes("camera") ||
    lower.includes("webcam") ||
    lower.includes("video source") ||
    lower.includes("droidcam") ||
    lower.includes("mjpeg") ||
    lower.includes("busy")
  )
}

export function classifyLiveFailure(input: {
  engineStatus: LiveEngineHookStatus | string
  liveStatus: LiveInferenceStatus
  engineMessage: string | null
  liveMessage: string | null
  compatReport?: CompatReport | null
}): LiveFailureKind {
  const msgs = [input.engineMessage, input.liveMessage].filter(Boolean) as string[]
  const joined = msgs.join(" ").toLowerCase()

  if (
    input.compatReport?.mismatches?.length ||
    joined.includes("compatibility") ||
    joined.includes("compat")
  ) {
    return "compat_error"
  }

  if (
    msgs.some(
      (m) =>
        m.toLowerCase().includes("model") ||
        m.toLowerCase().includes("bundle") ||
        m.toLowerCase().includes("no trained"),
    )
  ) {
    return "model_missing"
  }

  if (
    input.liveStatus === "error" &&
    (joined.includes("fetch") ||
      joined.includes("network") ||
      joined.includes("failed to fetch") ||
      joined.includes("econnrefused") ||
      joined.includes("cannot reach"))
  ) {
    return "api_offline"
  }

  if (msgs.some(isCameraRelatedMessage)) return "camera_error"

  if (input.engineStatus === "error") return "engine_error"
  if (input.liveStatus === "error") return "api_offline"
  if (input.liveStatus === "no-data") return "no_data"
  return "engine_error"
}

export const FAILURE_COPY: Record<
  LiveFailureKind,
  { title: string; description: string; actions: Array<{ step: string; detail?: string }> }
> = {
  api_offline: {
    title: "Haven unreachable",
    description:
 "The web UI cannot reach the local FastAPI server. No snapshots are being fabricated. start the backend on this machine.",
    actions: [
      { step: "From repo root, run npm run demo", detail: "Starts API + inference stack" },
      { step: "Confirm http://localhost:8000/api/live/status responds" },
      { step: "Reload /live and enable the camera" },
    ],
  },
  compat_error: {
    title: "Model bundle incompatible",
    description:
      "Train and inference configs disagree. Live inference is blocked until the bundle matches what the engine expects.",
    actions: [
      { step: "Retrain or copy a matching bundle to data/models/latest" },
      { step: "Align configs/train_multi_room.yaml with configs/inference.yaml feature groups" },
      { step: "Restart npm run demo and check /api/live/status compat_ok" },
    ],
  },
  model_missing: {
    title: "No trained model on disk",
    description:
      "The engine started but there is no personal model bundle to run against your camera.",
    actions: [
      { step: "npm run setup:model", detail: "Bootstrap weights if needed" },
      { step: "npm run train:images", detail: "Or train on bursts from /preferences" },
      { step: "npm run demo then open /live" },
    ],
  },
  engine_error: {
    title: "Inference engine failed",
    description:
 "The live pipeline exited or refused to start. See the message below. nothing is shown from cache.",
    actions: [
      { step: "Check terminal logs for the roomos inference worker" },
      { step: "Close apps holding the webcam, then retry" },
      { step: "npm run demo from repo root" },
    ],
  },
  camera_error: {
    title: "Camera could not open",
    description:
 "The phone stream or webcam is in use or unreachable. Haven will try the DroidCam virtual webcam when the WiFi feed is busy.",
    actions: [
      { step: "Quit the DroidCam Windows client (File → Exit) or pick DroidCam Video in the camera list" },
      { step: "Confirm the phone app is connected on the same WiFi as this PC" },
      { step: "Reload /live and turn the camera on again" },
    ],
  },
  no_data: {
    title: "API up. no snapshot yet",
    description:
      "Connected to Haven but no burst has been published. The camera may still be opening or warming OpenCLIP.",
    actions: [
 { step: "Wait 15 to 30s for the first burst on a cold start" },
      { step: "Confirm camera permission and device selection" },
      { step: "Check engine_running in /api/live/status" },
    ],
  },
}

export const MODE_LABEL: Record<HavenSystemMode, string> = {
  camera_off: "Camera off",
  setup: "Setup",
  booting: "Booting",
  live: "Live inference",
  demo_model: "Demo model",
  replay: "Replay",
  api_offline: "API offline",
  compat_error: "Compat error",
  model_missing: "No model",
  engine_error: "Engine error",
  camera_error: "Camera error",
}

export function bootPhaseCopy(
  bootPhase: BootPhase,
  engineStatus: string,
  liveStatus: LiveInferenceStatus,
): { title: string; description: string } {
  if (bootPhase === "opening_camera") {
    return {
      title: "Opening camera",
      description:
        "Negotiating capture with the OS. Close Teams, Zoom, or OBS if this stalls beyond ~10s.",
    }
  }
  if (bootPhase === "warming_up") {
    return {
      title: "First burst · OpenCLIP",
      description:
        "Capturing a 2.5s burst and running the local classifier. Cold start is often 10 to 25s. not an error.",
    }
  }
  if (bootPhase === "starting" || engineStatus === "starting") {
    return {
      title: "Starting inference engine",
      description: "Loading model weights and worker threads on this device.",
    }
  }
  if (liveStatus === "connecting") {
    return {
      title: "Waiting for first snapshot",
      description: "Engine is up; polling for the first published burst over WebSocket/HTTP.",
    }
  }
  return {
    title: "Almost ready",
 description: "Finishing boot. live read will appear when the first burst lands.",
  }
}

export function streamingModeFromSnapshot(
  snapshot: LiveInferenceSnapshot,
  modelKind: ModelKind,
): HavenSystemMode {
  const inf = resolveInferenceDisplayMode(modelKind, snapshot.dataSource)
  if (inf === "replay") return "replay"
  if (inf === "demo_model") return "demo_model"
  return "live"
}
