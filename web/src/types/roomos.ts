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

export interface LivePersonalizationMeta {
  applied?: boolean
  examples?: number
  memoryExamples?: number
  matches?: number
  nearestSimilarity?: number
  influence?: number
  boostedLabel?: string
}

/** Last fired automation rule (honest dry-run / live / failed state). */
export interface LastAutomationEvent {
  at?: string
  rule?: string
  activity?: string
  actionType?: string
  dryRun: boolean
  executed: boolean
  skipped?: boolean
  summary: string
}

export type AutomationMode = "dry_run" | "live" | "off"

export interface LiveInferenceSnapshot {
  schemaVersion: 1
  /** Monotonic burst counter from the live engine (proves UI is receiving updates). */
  sequence?: number
  capturedAt: string
  stream: LiveStreamMeta
  primaryState: RoomStateId
  /** 0–1 confidence in primaryState */
  primaryConfidence: number
  /** Smoothed probabilities shown in the UI (sum ~1) */
  distribution: RoomStateDistribution
  /** Raw model probabilities before personalization blend */
  modelDistribution?: RoomStateDistribution
  /** Human-readable bullets for the overlay explainer */
  rationale: string[]
  appliedScene: RoomDeviceTargets
  personalization?: LivePersonalizationMeta
  lastAutomation?: LastAutomationEvent
  automationMode?: AutomationMode
  /** `roomos-ml` = live model; `demo-replay` = prerecorded sequence */
  dataSource?: "roomos-ml" | "demo-replay" | string
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
  /** Preset id used by live inference for appliedScene (canonical active preset). */
  activePresetId: string
}
