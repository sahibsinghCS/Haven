/** Built-in room states with bespoke styling (custom moods get fallbacks). */
export const ROOM_STATE_ORDER = [
  "sleep",
  "gaming",
  "work",
  "relaxing",
  "away",
] as const

export type KnownRoomStateId = (typeof ROOM_STATE_ORDER)[number]

/** Room states are now dynamic — any registered mood id is valid. */
export type RoomStateId = string

/** Built-in moods restorable from the “+ Add mood” flow (gaming excluded). */
export const PREFERENCE_MOOD_ORDER = [
  "sleep",
  "work",
  "relaxing",
  "away",
] as const

export type KnownPreferenceMoodId = (typeof PREFERENCE_MOOD_ORDER)[number]

/** Preference moods are dynamic mood-registry ids. */
export type PreferenceMoodId = string

/** Per-state probability mass; sums to ~1 when normalized for display. */
export type RoomStateDistribution = Record<string, number>

// --- dynamic mood registry (backend /api/moods) -----------------------------

export type MoodMlStatus = "untrained" | "collecting" | "training" | "ready" | "error"

export interface MoodMlInfo {
  enabled: boolean
  status: MoodMlStatus
  frameCount: number
  burstCount: number
  lastTrainedAt?: string | null
}

export interface MoodDefinition {
  id: string
  displayName: string
  kind: "builtin" | "custom"
  builtinKey?: string
  createdAt: string
  updatedAt: string
  ml: MoodMlInfo
}

export interface MoodCollectionSession {
  moodId: string
  active: boolean
  startedAt: string
  durationSec: number
  elapsedSec: number
  remainingSec: number
  burstsSaved: number
  framesSaved: number
  skipped?: { dark: number; blurry: number; duplicate: number }
  stopReason?: "timer" | "user" | null
  finishedAt?: string | null
}

export interface MoodDatasetCounts {
  burstCount: number
  frameCount: number
}

export interface MoodBurstSummary {
  id: string
  frames: string[]
  frameCount: number
  capturedAt?: string | null
  meanLuma?: number | null
  blurScore?: number | null
}

export type TrainingJobPhase =
  | "queued"
  | "extracting_features"
  | "training"
  | "validating"
  | "promoting"
  | "reloading"
  | "done"
  | "error"

export interface TrainingJob {
  id: string
  moodId: string
  phase: TrainingJobPhase
  progress: number
  startedAt: string
  finishedAt?: string | null
  ok?: boolean | null
  error?: string | null
  warnings: string[]
  result?: {
    classes: string[]
    accuracy: number
    macroF1: number
    nEvalSamples: number
    perClass: Record<string, { precision: number; recall: number; f1: number; support: number }>
    personalBurstsByClass: Record<string, number>
    clearedFrames: number
    bundleDir: string
  } | null
}

export interface MoodsResponse {
  moods: MoodDefinition[]
  restorableBuiltins: Array<{ builtinKey: string; displayName: string }>
  consent: { accepted: boolean; acceptedAt?: string | null }
  datasetFolder: string
  collection: MoodCollectionSession | null
  trainingActive: boolean
}

export interface LiveStreamMeta {
  /** When wired to WebRTC/HLS, e.g. `wss://…` or playlist URL */
  streamUrl?: string | null
  /** Optional poster for loading / paused states */
  posterUrl?: string | null
  /** e.g. "16/9", used for layout only */
  aspectLabel?: string
}

export type ConnectedDeviceCategory = "smartPlugs" | "lights" | "thermostats"

export interface RoomDeviceTargets {
  lightColorHex?: string
  brightness?: number
  fanOn?: boolean
  /** Fahrenheit; backend may later use Celsius with a unit field */
  temperatureF?: number
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
  /** Connected + enabled device categories from Settings (drives room scene summary). */
  connectedCategories?: ConnectedDeviceCategory[]
  personalization?: LivePersonalizationMeta
  lastAutomation?: LastAutomationEvent
  automationMode?: AutomationMode
  /** `roomos-ml` = live model; `demo-replay` = prerecorded sequence */
  dataSource?: "roomos-ml" | "demo-replay" | string
  /** Rolling history for charts / debugging (timestamps ISO; one key per mood) */
  confidenceHistory: Array<{ t: string; [stateId: string]: number | string }>
}

export interface DevicePreferenceTarget {
  fanOn?: boolean
  brightness?: number
  lightColorHex?: string
  temperatureF?: number
}

export interface StateEnvironmentPreference {
  devices: Record<string, DevicePreferenceTarget>
}

export type PreferenceMatrix = Record<string, StateEnvironmentPreference>

export interface PreferencePreset {
  id: string
  name: string
  description?: string
  isDefault?: boolean
  preferences: PreferenceMatrix
}

export interface PreferenceDocument {
  schemaVersion: 2
  updatedAt: string
  presets: PreferencePreset[]
  /** Preset id used by live inference for appliedScene (canonical active preset). */
  activePresetId: string
}

export type ConnectedDeviceRef = {
  id: string
  category: "smart_plug" | "lights" | "thermostat"
  label: string
  brand: string
}
