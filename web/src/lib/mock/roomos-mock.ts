import type {
  LiveInferenceSnapshot,
  PreferenceDocument,
  PreferencePreset,
  RoomStateDistribution,
  RoomStateId,
} from "@/types/roomos"
import { ROOM_STATE_ORDER } from "@/types/roomos"

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

function clamp01(n: number) {
  return Math.min(1, Math.max(0, n))
}

function normalizeDistribution(d: RoomStateDistribution): RoomStateDistribution {
  const sum = ROOM_STATE_ORDER.reduce((acc, k) => acc + d[k], 0)
  if (sum <= 0) return d
  const out = { ...d }
  ROOM_STATE_ORDER.forEach((k) => {
    out[k] = out[k] / sum
  })
  return out
}

function jitter(base: RoomStateDistribution, magnitude: number): RoomStateDistribution {
  const next: RoomStateDistribution = { ...base }
  ROOM_STATE_ORDER.forEach((k) => {
    next[k] = clamp01(base[k] + (Math.random() - 0.5) * magnitude)
  })
  return normalizeDistribution(next)
}

const baseLive: LiveInferenceSnapshot = {
  schemaVersion: 1,
  capturedAt: new Date().toISOString(),
  stream: {
    streamUrl: null,
    posterUrl: null,
    aspectLabel: "16/9",
  },
  primaryState: "gaming",
  primaryConfidence: 0.81,
  distribution: normalizeDistribution({
    sleep: 0.06,
    gaming: 0.52,
    work: 0.22,
    relaxing: 0.12,
    away: 0.08,
  }),
  rationale: [
    "Controller-forward posture near the bed zone",
    "Steam is the focused application",
    "Recent mouse movement (last 90s)",
    "Prior correction: similar context prefers Gaming over Sleep",
  ],
  appliedScene: {
    lightColorHex: "#6D4AFF",
    brightness: 78,
    fanOn: true,
    temperatureF: 70,
  },
  confidenceHistory: [
    {
      t: "2026-05-10T21:40:00.000Z",
      sleep: 0.12,
      gaming: 0.38,
      work: 0.28,
      relaxing: 0.14,
      away: 0.08,
    },
    {
      t: "2026-05-10T21:41:00.000Z",
      sleep: 0.09,
      gaming: 0.45,
      work: 0.26,
      relaxing: 0.12,
      away: 0.08,
    },
    {
      t: "2026-05-10T21:42:00.000Z",
      sleep: 0.07,
      gaming: 0.52,
      work: 0.24,
      relaxing: 0.11,
      away: 0.06,
    },
    {
      t: "2026-05-10T21:43:00.000Z",
      sleep: 0.06,
      gaming: 0.55,
      work: 0.22,
      relaxing: 0.11,
      away: 0.06,
    },
    {
      t: "2026-05-10T21:44:00.000Z",
      sleep: 0.06,
      gaming: 0.58,
      work: 0.2,
      relaxing: 0.1,
      away: 0.06,
    },
    {
      t: "2026-05-10T21:45:00.000Z",
      sleep: 0.06,
      gaming: 0.61,
      work: 0.18,
      relaxing: 0.1,
      away: 0.05,
    },
  ],
}

const basicPreset: PreferencePreset = {
  id: "preset_basic",
  name: "Basic Preference",
  description: "Balanced defaults for day-to-night transitions.",
  isDefault: true,
  preferences: {
    sleep: {
      lightColorHex: "#1E2A4A",
      brightness: 8,
      fanOn: true,
      temperatureF: 68,
    },
    gaming: {
      lightColorHex: "#6D4AFF",
      brightness: 80,
      fanOn: true,
      temperatureF: 70,
    },
    work: {
      lightColorHex: "#E8F4FF",
      brightness: 72,
      fanOn: false,
      temperatureF: 72,
    },
    relaxing: {
      lightColorHex: "#2FB8A8",
      brightness: 42,
      fanOn: false,
      temperatureF: 73,
    },
    away: {
      lightColorHex: "#2A2A2A",
      brightness: 0,
      fanOn: false,
      temperatureF: 76,
    },
  },
}

const customPreset: PreferencePreset = {
  id: "preset_custom",
  name: "Custom",
  description: "Your personal mix. Adjust any mood, then save.",
  isDefault: false,
  preferences: {
    sleep: {
      lightColorHex: "#0F172A",
      brightness: 4,
      fanOn: true,
      temperatureF: 67,
    },
    gaming: {
      lightColorHex: "#7C3AED",
      brightness: 88,
      fanOn: true,
      temperatureF: 69,
    },
    work: {
      lightColorHex: "#D7F9FF",
      brightness: 85,
      fanOn: false,
      temperatureF: 71,
    },
    relaxing: {
      lightColorHex: "#14B8A6",
      brightness: 35,
      fanOn: false,
      temperatureF: 74,
    },
    away: {
      lightColorHex: "#18181B",
      brightness: 0,
      fanOn: false,
      temperatureF: 78,
    },
  },
}

export async function fetchMockLiveSnapshot(): Promise<LiveInferenceSnapshot> {
  await delay(320)
  const distribution = jitter(baseLive.distribution, 0.06)
  let primary: RoomStateId = "gaming"
  let best = -1
  ROOM_STATE_ORDER.forEach((k) => {
    if (distribution[k] > best) {
      best = distribution[k]
      primary = k
    }
  })
  const primaryConfidence = distribution[primary]
  return {
    ...baseLive,
    capturedAt: new Date().toISOString(),
    distribution,
    primaryState: primary,
    primaryConfidence,
    appliedScene: {
      ...baseLive.appliedScene,
      brightness: Math.round(65 + Math.random() * 20),
    },
  }
}

export async function fetchMockPreferenceDocument(): Promise<PreferenceDocument> {
  await delay(240)
  return {
    schemaVersion: 1,
    updatedAt: new Date().toISOString(),
    presets: [basicPreset, customPreset],
  }
}
