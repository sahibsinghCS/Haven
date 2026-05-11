export const ROOM_STATE_ORDER = [
  "sleep",
  "gaming",
  "work",
  "relaxing",
  "away",
] as const

export type RoomStateId = (typeof ROOM_STATE_ORDER)[number]

/** Per-state probability mass; sums to ~1 when normalized for display. */
export type RoomStateDistribution = Record<RoomStateId, number>

export interface LiveStreamMeta {
  /** When wired to WebRTC/HLS, e.g. `wss://…` or playlist URL */
  streamUrl?: string | null
  /** Optional poster for loading / paused states */
  posterUrl?: string | null
  /** e.g. "16/9", used for layout only */
  aspectLabel?: string
}

export interface RoomDeviceTargets {
  lightColorHex: string
  brightness: number
  fanOn: boolean
  /** Fahrenheit; backend may later use Celsius with a unit field */
  temperatureF: number
}

export interface LiveInferenceSnapshot {
  schemaVersion: 1
  capturedAt: string
  stream: LiveStreamMeta
  primaryState: RoomStateId
  /** 0–1 confidence in primaryState */
  primaryConfidence: number
  distribution: RoomStateDistribution
  /** Human-readable bullets for the overlay explainer */
  rationale: string[]
  appliedScene: RoomDeviceTargets
  /** Rolling history for charts / debugging (timestamps ISO) */
  confidenceHistory: Array<{
    t: string
    sleep: number
    gaming: number
    work: number
    relaxing: number
    away: number
  }>
}

export interface StateEnvironmentPreference {
  lightColorHex: string
  brightness: number
  fanOn: boolean
  temperatureF: number
}

export type PreferenceMatrix = Record<RoomStateId, StateEnvironmentPreference>

export interface PreferencePreset {
  id: string
  name: string
  description?: string
  isDefault?: boolean
  preferences: PreferenceMatrix
}

export interface PreferenceDocument {
  schemaVersion: 1
  updatedAt: string
  presets: PreferencePreset[]
}
