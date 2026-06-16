import {
  fetchCameras,
  fetchDeviceActionLog,
  fetchDeviceSettingsDocument,
  fetchEngineStatus,
  fetchRoomsStatus,
  type CompatReport,
  type LiveEngineStatus,
} from "@/lib/roomos/api-client"
import { countConnectedDevices } from "@/lib/roomos/device-settings-schema"
import { loadDeviceSettingsLocal } from "@/lib/roomos/device-settings-persistence"
import type { RoomsStatusResponse } from "@/types/roomos"

export type SetupCheckStatus = "pass" | "warn" | "fail" | "pending" | "skip"

export type SetupCheckId =
  | "api"
  | "model"
  | "rooms"
  | "camera"
  | "devices"
  | "device_conflicts"

export type SetupCheck = {
  id: SetupCheckId
  label: string
  status: SetupCheckStatus
  detail: string
}

export type SetupHealthSnapshot = {
  checks: SetupCheck[]
  rooms: RoomsStatusResponse | null
  engine: LiveEngineStatus | null
  apiOnline: boolean
  readyForLive: boolean
}

function modelChecks(engine: LiveEngineStatus | null): SetupCheck[] {
  if (!engine) {
    return [
      {
        id: "model",
        label: "Inference model",
        status: "pending",
        detail: "Start the camera on Live to verify the model bundle.",
      },
    ]
  }

  if (engine.compat_ok === false) {
    const mismatches = (engine.compat_report as CompatReport | null)?.mismatches?.length ?? 0
    return [
      {
        id: "model",
        label: "Inference model",
        status: "fail",
        detail:
          mismatches > 0
            ? `Model bundle failed compatibility (${mismatches} mismatch${mismatches === 1 ? "" : "es"}). Run npm run setup:model or retrain.`
            : "Model is not compatible with live inference settings.",
      },
    ]
  }

  if (engine.compat_ok === true) {
    const kind = engine.model_kind ?? "unknown"
    return [
      {
        id: "model",
        label: "Inference model",
        status: kind === "bootstrap" ? "warn" : "pass",
        detail:
          kind === "bootstrap"
            ? "Demo/bootstrap model loaded. train on your room for trustworthy reads."
            : `Model ready (${kind}).`,
      },
    ]
  }

  return [
    {
      id: "model",
      label: "Inference model",
      status: "pending",
      detail: "Model compatibility is checked when the inference engine starts.",
    },
  ]
}

function deviceConflictCheck(
  decisions: Array<{ allowed?: boolean; reason?: string }>,
): SetupCheck {
  const blocked = decisions.filter(
    (d) =>
      d.allowed === false &&
      typeof d.reason === "string" &&
      (d.reason.includes("preempted") || d.reason.includes("duplicate")),
  )
  if (blocked.length === 0) {
    return {
      id: "device_conflicts",
      label: "Device command conflicts",
      status: "pass",
      detail: "No recent arbiter blocks. scenes, automation, and tests are not fighting.",
    }
  }
  return {
    id: "device_conflicts",
    label: "Device command conflicts",
    status: "warn",
    detail: `${blocked.length} recent command${blocked.length === 1 ? "" : "s"} suppressed (duplicate or higher-priority rule). Check Connections if devices feel stuck.`,
  }
}

/** Aggregate setup health from existing APIs (no dedicated backend endpoint yet). */
export async function evaluateSetupHealth(signal?: AbortSignal): Promise<SetupHealthSnapshot> {
  const checks: SetupCheck[] = []
  let apiOnline = false
  let rooms: RoomsStatusResponse | null = null
  let engine: LiveEngineStatus | null = null

  try {
    engine = await fetchEngineStatus(signal)
    apiOnline = true
  } catch {
    checks.push({
      id: "api",
      label: "HAVEN API",
      status: "fail",
 detail: "Cannot reach the API. run npm run demo from the repo root.",
    })
  }

  if (apiOnline) {
    checks.push({
      id: "api",
      label: "HAVEN API",
      status: "pass",
      detail: "API is reachable on this machine.",
    })
    checks.push(...modelChecks(engine))
  }

  if (apiOnline) {
    try {
      rooms = await fetchRoomsStatus(signal)
      if (rooms.rooms.length === 0) {
        checks.push({
          id: "rooms",
          label: "Rooms",
          status: "fail",
 detail: "No rooms yet. add at least one space with a camera.",
        })
      } else {
        const enabled = rooms.rooms.filter((r) => r.enabled)
        checks.push({
          id: "rooms",
          label: "Rooms",
          status: enabled.length > 0 ? "pass" : "warn",
          detail:
            enabled.length > 0
              ? `${enabled.length} room${enabled.length === 1 ? "" : "s"} enabled.`
              : "Rooms exist but all cameras are off.",
        })
      }
    } catch {
      checks.push({
        id: "rooms",
        label: "Rooms",
        status: "fail",
        detail: "Could not load room list.",
      })
    }
  }

  if (apiOnline) {
    try {
      const camData = await fetchCameras(signal)
      const available = camData.cameras.filter((c) => c.available)
      const needsPick = Boolean(engine?.camera_setup_required)
      if (available.length === 0) {
        checks.push({
          id: "camera",
          label: "Camera",
          status: "fail",
 detail: "No usable cameras found. plug in a webcam or open DroidCam, then rescan.",
        })
      } else if (needsPick) {
        checks.push({
          id: "camera",
          label: "Camera",
          status: "fail",
          detail: "Pick a camera source before live inference can start.",
        })
      } else {
        const dark = available.some((c) => c.mean_luma != null && c.mean_luma < 15)
        checks.push({
          id: "camera",
          label: "Camera",
          status: dark ? "warn" : "pass",
          detail: dark
 ? "Camera responds but looks very dark. close other apps using the webcam."
            : `${available.length} camera${available.length === 1 ? "" : "s"} available.`,
        })
      }
    } catch {
      checks.push({
        id: "camera",
        label: "Camera",
        status: "fail",
        detail: "Camera scan failed. is the API running?",
      })
    }
  }

  let deviceDoc = loadDeviceSettingsLocal()
  if (apiOnline) {
    try {
      deviceDoc = await fetchDeviceSettingsDocument()
    } catch {
      /* keep local fallback */
    }
  }
  if (deviceDoc) {
    const { connected, total } = countConnectedDevices(deviceDoc)
    if (total === 0) {
      checks.push({
        id: "devices",
        label: "Smart devices",
        status: "skip",
 detail: "Optional. connect plugs, lights, or thermostats on Connections.",
      })
    } else if (connected === 0) {
      checks.push({
        id: "devices",
        label: "Smart devices",
        status: "warn",
        detail: `${total} device${total === 1 ? "" : "s"} added but none connected yet.`,
      })
    } else {
      const unassigned =
        rooms?.rooms.some((r) => r.deviceIds.length === 0) && connected > 0
      checks.push({
        id: "devices",
        label: "Smart devices",
        status: unassigned ? "warn" : "pass",
        detail: unassigned
 ? `${connected} connected. assign devices to rooms so scenes stay intentional.`
          : `${connected} device${connected === 1 ? "" : "s"} connected.`,
      })
    }
  }

  if (apiOnline) {
    try {
      const decisions = await fetchDeviceActionLog(8, signal)
      checks.push(deviceConflictCheck(decisions))
    } catch {
      checks.push({
        id: "device_conflicts",
        label: "Device command conflicts",
        status: "skip",
        detail: "Conflict log unavailable until integrations API responds.",
      })
    }
  }

  const blocking = new Set<SetupCheckId>(["api", "rooms", "camera"])
  const readyForLive = checks.every(
    (c) => !blocking.has(c.id) || c.status === "pass" || c.status === "warn",
  )

  return { checks, rooms, engine, apiOnline, readyForLive }
}
