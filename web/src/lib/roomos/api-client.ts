import { parsePreferenceDocument } from "@/lib/roomos/preferences-document-schema"
import type {
  LiveInferenceSnapshot,
  PreferenceDocument,
  RoomStateDistribution,
  RoomStateId,
} from "@/types/roomos"
import type { LiveFeedbackEvent } from "@/types/feedback-event"
import type { LivePreferencesEvent } from "@/types/preferences-event"
import { ROOM_STATE_ORDER } from "@/types/roomos"

/**
 * Base URL of the RoomOS FastAPI server. Override at build time via
 * `NEXT_PUBLIC_ROOMOS_API_BASE` (e.g. `http://127.0.0.1:8000`).
 */
export const API_BASE: string =
  process.env.NEXT_PUBLIC_ROOMOS_API_BASE?.trim().replace(/\/+$/, "") || "http://127.0.0.1:8000"

function wsBase(): string {
  const explicit = process.env.NEXT_PUBLIC_ROOMOS_WS_BASE?.trim().replace(/\/+$/, "")
  if (explicit) return explicit
  return API_BASE.replace(/^http/i, (m) => (m.toLowerCase() === "https" ? "wss" : "ws"))
}

export const WS_SNAPSHOT_URL = `${wsBase()}/api/live/ws`

export function feedbackCorrectionScreenshotUrl(
  correctionId: string,
  cacheBust?: string,
): string {
  const base = `${API_BASE}/api/live/feedback/screenshots/${encodeURIComponent(correctionId)}/frame.jpg`
  return cacheBust ? `${base}?t=${encodeURIComponent(cacheBust)}` : base
}

export function normalizeFeedbackEvent(raw: unknown): LiveFeedbackEvent {
  if (!raw || typeof raw !== "object") {
    throw new Error("Feedback event payload is not an object")
  }
  const e = raw as Record<string, unknown>
  const source = String(e.source ?? "web")
  if (source !== "telegram" && source !== "web") {
    throw new Error(`Unknown feedback source: ${source}`)
  }
  const correctionId = String(e.correctionId ?? e.correction_id ?? "")
  if (!correctionId) throw new Error("Feedback event missing correctionId")
  const screenshotUrl =
    typeof e.screenshotUrl === "string"
      ? e.screenshotUrl.startsWith("http")
        ? e.screenshotUrl
        : `${API_BASE}${e.screenshotUrl}`
      : feedbackCorrectionScreenshotUrl(correctionId)
  return {
    source,
    correctionId,
    createdAt: String(e.createdAt ?? e.created_at ?? ""),
    predictedLabel: String(e.predictedLabel ?? e.predicted_label ?? ""),
    correctedLabel: String(e.correctedLabel ?? e.corrected_label ?? ""),
    confirmed: Boolean(e.confirmed),
    notes: String(e.notes ?? ""),
    screenshotCount: Number(e.screenshotCount ?? e.screenshot_count ?? 0),
    memoryExamples: Number(e.memoryExamples ?? e.memory_examples ?? 0),
    autoRetrainEnabled: Boolean(e.autoRetrainEnabled ?? e.auto_retrain_enabled),
    screenshotUrl,
  }
}

export function normalizePreferencesEvent(raw: unknown): LivePreferencesEvent {
  if (!raw || typeof raw !== "object") {
    throw new Error("Preferences event payload is not an object")
  }
  const e = raw as Record<string, unknown>
  const source = String(e.source ?? "web")
  if (source !== "telegram" && source !== "web") {
    throw new Error(`Unknown preferences source: ${source}`)
  }
  return {
    source,
    updatedAt: String(e.updatedAt ?? e.updated_at ?? ""),
    activePresetId: String(e.activePresetId ?? e.active_preset_id ?? ""),
    presetName: String(e.presetName ?? e.preset_name ?? ""),
    targetStates: Array.isArray(e.targetStates)
      ? e.targetStates.map(String)
      : Array.isArray(e.target_states)
        ? e.target_states.map(String)
        : [],
    changes: Array.isArray(e.changes) ? e.changes.map(String) : [],
    notes: String(e.notes ?? ""),
  }
}

export type LiveWsMessage =
  | { kind: "snapshot"; snapshot: LiveInferenceSnapshot }
  | { kind: "feedback"; event: LiveFeedbackEvent }
  | { kind: "preferences"; event: LivePreferencesEvent }

/** Parse multiplexed WebSocket payloads (or legacy bare snapshots). */
export function parseLiveWsMessage(raw: unknown): LiveWsMessage | null {
  if (!raw || typeof raw !== "object") return null
  const o = raw as Record<string, unknown>
  if (o.type === "feedback" && o.payload) {
    return { kind: "feedback", event: normalizeFeedbackEvent(o.payload) }
  }
  if (o.type === "preferences" && o.payload) {
    return { kind: "preferences", event: normalizePreferencesEvent(o.payload) }
  }
  if (o.type === "snapshot" && o.payload) {
    return { kind: "snapshot", snapshot: normalizeSnapshot(o.payload) }
  }
  if (o.schemaVersion != null) {
    return { kind: "snapshot", snapshot: normalizeSnapshot(o) }
  }
  return null
}

/**
 * The backend may produce a primary state of "unknown" (low-confidence
 * abstain). The frontend type system only knows about 5 real states, so we
 * map "unknown" -> the state with the highest probability anyway. If even
 * that fails we default to "relaxing" which is the safest UI fallback.
 */
function normalizeSnapshot(raw: unknown): LiveInferenceSnapshot {
  if (!raw || typeof raw !== "object") {
    throw new Error("Snapshot payload is not an object")
  }
  const s = raw as Record<string, unknown>

  const distribution = normalizeDistribution({
    sleep: clampProb((s.distribution as Record<string, unknown> | undefined)?.sleep),
    gaming: clampProb((s.distribution as Record<string, unknown> | undefined)?.gaming),
    work: clampProb((s.distribution as Record<string, unknown> | undefined)?.work),
    relaxing: clampProb((s.distribution as Record<string, unknown> | undefined)?.relaxing),
    away: clampProb((s.distribution as Record<string, unknown> | undefined)?.away),
  })

  const modelRaw = (s.modelDistribution ?? s.distribution ?? {}) as Record<string, unknown>
  const modelDistribution = normalizeDistribution({
    sleep: clampProb(modelRaw.sleep),
    gaming: clampProb(modelRaw.gaming),
    work: clampProb(modelRaw.work),
    relaxing: clampProb(modelRaw.relaxing),
    away: clampProb(modelRaw.away),
  })

  const primaryRaw = String(s.primaryState ?? "unknown")
  const primary: RoomStateId = (ROOM_STATE_ORDER as readonly string[]).includes(primaryRaw)
    ? (primaryRaw as RoomStateId)
    : argmaxState(distribution)

  const primaryConfidence =
    typeof s.primaryConfidence === "number" ? s.primaryConfidence : distribution[primary]

  const appliedSceneRaw = (s.appliedScene ?? {}) as Record<string, unknown>
  const appliedScene = {
    lightColorHex: String(appliedSceneRaw.lightColorHex ?? "#2A2A2A"),
    brightness: Number(appliedSceneRaw.brightness ?? 0),
    fanOn: Boolean(appliedSceneRaw.fanOn ?? false),
    temperatureF: Number(appliedSceneRaw.temperatureF ?? 72),
  }

  const streamRaw = (s.stream ?? {}) as Record<string, unknown>

  const historyRaw = Array.isArray(s.confidenceHistory) ? s.confidenceHistory : []
  const confidenceHistory = historyRaw
    .map((h) => {
      const r = h as Record<string, unknown>
      const t = typeof r.t === "string" ? r.t : new Date().toISOString()
      return {
        t,
        sleep: clampProb(r.sleep),
        gaming: clampProb(r.gaming),
        work: clampProb(r.work),
        relaxing: clampProb(r.relaxing),
        away: clampProb(r.away),
      }
    })
    .slice(-120)

  const personalizationRaw = (s.personalization ?? {}) as Record<string, unknown>
  const autoRaw = (s.lastAutomation ?? {}) as Record<string, unknown>
  const automationModeRaw = String(s.automationMode ?? "off")
  const automationMode =
    automationModeRaw === "live" || automationModeRaw === "dry_run"
      ? automationModeRaw
      : "off"

  return {
    schemaVersion: 1,
    sequence: typeof s.sequence === "number" ? s.sequence : Number(s.sequence) || undefined,
    capturedAt: String(s.capturedAt ?? new Date().toISOString()),
    stream: {
      streamUrl: (streamRaw.streamUrl as string | null | undefined) ?? null,
      posterUrl: (streamRaw.posterUrl as string | null | undefined) ?? null,
      aspectLabel: typeof streamRaw.aspectLabel === "string" ? streamRaw.aspectLabel : "16/9",
    },
    primaryState: primary,
    primaryConfidence,
    distribution,
    modelDistribution,
    rationale: Array.isArray(s.rationale) ? s.rationale.map(String) : [],
    appliedScene,
    personalization: {
      applied: Boolean(personalizationRaw.applied),
      examples: Number(personalizationRaw.examples ?? personalizationRaw.memory_examples ?? 0),
      memoryExamples: Number(
        personalizationRaw.memory_examples ?? personalizationRaw.examples ?? 0,
      ),
      matches: Number(personalizationRaw.matches ?? 0),
      nearestSimilarity: Number(
        personalizationRaw.nearest_similarity ?? personalizationRaw.nearestSimilarity ?? 0,
      ),
      influence: Number(personalizationRaw.influence ?? 0),
      boostedLabel:
        typeof personalizationRaw.boosted_label === "string"
          ? personalizationRaw.boosted_label
          : typeof personalizationRaw.boostedLabel === "string"
            ? personalizationRaw.boostedLabel
            : undefined,
    },
    dataSource: typeof s.dataSource === "string" ? s.dataSource : "roomos-ml",
    lastAutomation:
      autoRaw.summary || autoRaw.rule
        ? {
            at: typeof autoRaw.at === "string" ? autoRaw.at : undefined,
            rule: typeof autoRaw.rule === "string" ? autoRaw.rule : undefined,
            activity: typeof autoRaw.activity === "string" ? autoRaw.activity : undefined,
            actionType:
              typeof autoRaw.actionType === "string" ? autoRaw.actionType : undefined,
            dryRun: Boolean(autoRaw.dryRun),
            executed: Boolean(autoRaw.executed),
            skipped: Boolean(autoRaw.skipped),
            summary: String(autoRaw.summary ?? ""),
          }
        : undefined,
    automationMode,
    confidenceHistory,
  }
}

export function normalizeDistribution(d: RoomStateDistribution): RoomStateDistribution {
  const sum = ROOM_STATE_ORDER.reduce((acc, k) => acc + d[k], 0)
  if (sum <= 1e-9) {
    const uniform = 1 / ROOM_STATE_ORDER.length
    return Object.fromEntries(
      ROOM_STATE_ORDER.map((k) => [k, uniform]),
    ) as RoomStateDistribution
  }
  const out = { ...d }
  ROOM_STATE_ORDER.forEach((k) => {
    out[k] = out[k] / sum
  })
  return out
}

function clampProb(v: unknown): number {
  const n = typeof v === "number" ? v : Number(v)
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(1, n))
}

function argmaxState(d: RoomStateDistribution): RoomStateId {
  let best: RoomStateId = "relaxing"
  let bestVal = -1
  for (const k of ROOM_STATE_ORDER) {
    if (d[k] > bestVal) {
      bestVal = d[k]
      best = k
    }
  }
  return best
}

/** Fetch the latest snapshot once. Returns `null` if the engine has no data yet. */
export async function fetchLiveSnapshot(signal?: AbortSignal): Promise<LiveInferenceSnapshot | null> {
  const res = await fetch(`${API_BASE}/api/live/snapshot`, { signal, cache: "no-store" })
  if (res.status === 503) return null
  if (!res.ok) {
    throw new Error(`fetchLiveSnapshot failed: ${res.status} ${res.statusText}`)
  }
  const raw = await res.json()
  return normalizeSnapshot(raw)
}

export type CompatMismatch = {
  category: string
  field: string
  train: string
  inference: string
  detail?: string
}

export type CompatReport = {
  ok: boolean
  bundle_dir: string
  inference_config: string
  train_config_source: string
  bundle_classes: string[]
  inference_classes: string[]
  n_bundle_columns: number
  n_expected_columns: number
  mismatches: CompatMismatch[]
}

export type LiveMode = "off" | "live" | "replay"

export type BootPhase =
  | "off"
  | "starting"
  | "opening_camera"
  | "warming_up"
  | "streaming"

export type ModelKind =
  | "bootstrap"
  | "generic"
  | "personal"
  | "trained"
  | "replay"
  | "unknown"

export type LiveEngineStatus = {
  engine_running: boolean
  engine_error: string | null
  has_snapshot: boolean
  live_mode?: LiveMode
  demo_mode?: boolean
  demo_replay_active?: boolean
  compat_ok?: boolean | null
  compat_report?: CompatReport | null
  /** OpenCV source label or demo replay label */
  inference_source?: string | null
  preview_available?: boolean
  /** True when /preview.jpg is the same OpenCV feed as burst inference */
  preview_is_inference_feed?: boolean
  /** 0..255 average brightness of the latest preview frame (null until first frame). */
  preview_mean_luma?: number | null
  /** True when preview frames are effectively black (typical Windows MSMF symptom). */
  preview_dark?: boolean
  preview_frames_seen?: number
  /** UI object-fit: cover (fill stage) or contain (full frame, letterboxed). */
  preview_fit?: "cover" | "contain"
  /** [width, height] of processed frames sent to preview + ML. */
  preview_frame_shape?: [number, number] | null
  /** [width, height] negotiated with the camera driver. */
  capture_size?: [number, number] | null
  /** Coarse engine boot phase for boot-screen copy. */
  boot_phase?: BootPhase
  /** Source of the loaded model: bootstrap demo vs real training. */
  model_kind?: ModelKind
  /** Whether MediaPipe pose features are active in this inference run. */
  pose_enabled?: boolean | null
  data_source?: string | null
  demo_fixture?: string | null
}

export const LIVE_PREVIEW_URL = `${API_BASE}/api/live/preview.jpg`

export async function fetchEngineStatus(signal?: AbortSignal): Promise<LiveEngineStatus> {
  const res = await fetch(`${API_BASE}/api/live/status`, { signal, cache: "no-store" })
  if (!res.ok) throw new Error(`status ${res.status}`)
  return (await res.json()) as LiveEngineStatus
}

export async function startEngine(): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/live/start`, { method: "POST" })
  return res.json()
}

export async function stopEngine(): Promise<unknown> {
  const res = await fetch(`${API_BASE}/api/live/stop`, { method: "POST" })
  return res.json()
}

export type SetLiveModeResult = {
  status: string
  live_mode?: LiveMode
  error?: string
  inference_source?: string
}

/** Switch between live camera + model and deterministic demo replay. */
export async function setLiveMode(mode: "live" | "replay" | "off"): Promise<SetLiveModeResult> {
  const res = await fetch(`${API_BASE}/api/live/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  })
  const body = (await res.json()) as SetLiveModeResult
  if (!res.ok) {
    throw new Error(body.error ?? `setLiveMode failed: ${res.status}`)
  }
  return body
}

export type FeedbackProbabilityPreview = {
  before: RoomStateDistribution
  after: RoomStateDistribution
  corrected_label: string
  appliedAfterSave?: boolean
  applied_after_save?: boolean
  nearest_similarity?: number
}

function normalizeFeedbackProbs(raw: unknown): RoomStateDistribution {
  const r = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>
  return {
    sleep: Number(r.sleep ?? 0),
    gaming: Number(r.gaming ?? 0),
    work: Number(r.work ?? 0),
    relaxing: Number(r.relaxing ?? 0),
    away: Number(r.away ?? 0),
  }
}

export type FeedbackEffects = {
  immediate: string
  ongoing: string
  notIncluded: string
}

export type FeedbackResponse = {
  status: "recorded"
  id: string
  createdAt: string
  predictedLabel: string
  correctedLabel: string
  confirmed?: boolean
  screenshotCount: number
  influence: number
  memoryExamples: number
  retrainsModel: boolean
  effects: FeedbackEffects
  probabilityPreview?: FeedbackProbabilityPreview
  storage?: {
    dir?: string
    examplesFile?: string
    eventsLog?: string
    screenshotsDir?: string
  }
}

export type AutoRetrainStatus = {
  enabled: boolean
  running?: boolean
  correctionsSinceLastRun?: number
  storedCorrections?: number
  minCorrections?: number
  minIntervalSec?: number
  lastRunAt?: number | null
  lastResult?: Record<string, unknown> | null
}

export type FeedbackEvidenceStatus = {
  available: boolean
  capturedAt?: string
  primaryState?: string
  confidence?: number
  frameCount?: number
}

export type FeedbackStatus = {
  enabled: boolean
  memoryExamples: number
  hasEvidence?: boolean
  evidence?: FeedbackEvidenceStatus
  similarityFloor?: number
  influence?: number
  storageDir?: string
  autoRetrain?: AutoRetrainStatus
  lastCorrection?: {
    id?: string
    at?: string
    predicted_label?: string
    corrected_label?: string
  } | null
}

export function feedbackEvidenceFrameUrl(frameIndex: number, cacheBust?: string): string {
  const base = `${API_BASE}/api/live/feedback/evidence/frames/${frameIndex}.jpg`
  return cacheBust ? `${base}?t=${encodeURIComponent(cacheBust)}` : base
}

export async function fetchFeedbackStatus(signal?: AbortSignal): Promise<FeedbackStatus> {
  const res = await fetch(`${API_BASE}/api/live/feedback/status`, { signal, cache: "no-store" })
  if (!res.ok) throw new Error(`feedback status failed: ${res.status}`)
  const raw = (await res.json()) as Record<string, unknown>
  const arRaw = raw.autoRetrain ?? raw.auto_retrain
  let autoRetrain: AutoRetrainStatus | undefined
  if (arRaw && typeof arRaw === "object") {
    const ar = arRaw as Record<string, unknown>
    autoRetrain = {
      enabled: Boolean(ar.enabled),
      running: Boolean(ar.running),
      correctionsSinceLastRun: Number(
        ar.correctionsSinceLastRun ?? ar.corrections_since_last_run ?? 0,
      ),
      storedCorrections: Number(ar.storedCorrections ?? ar.stored_corrections ?? 0),
      minCorrections: Number(ar.minCorrections ?? ar.min_corrections ?? 3),
      minIntervalSec: Number(ar.minIntervalSec ?? ar.min_interval_sec ?? 90),
      lastRunAt:
        ar.lastRunAt != null
          ? Number(ar.lastRunAt)
          : ar.last_run_at != null
            ? Number(ar.last_run_at)
            : null,
      lastResult:
        ar.lastResult && typeof ar.lastResult === "object"
          ? (ar.lastResult as Record<string, unknown>)
          : ar.last_result && typeof ar.last_result === "object"
            ? (ar.last_result as Record<string, unknown>)
            : null,
    }
  }
  return {
    enabled: Boolean(raw.enabled),
    memoryExamples: Number(raw.memory_examples ?? raw.examples ?? 0),
    hasEvidence: Boolean(raw.has_evidence),
    evidence: parseFeedbackEvidence(raw.evidence),
    similarityFloor: Number(raw.similarity_floor ?? 0),
    influence: Number(raw.influence ?? 0),
    storageDir: typeof raw.storage_dir === "string" ? raw.storage_dir : undefined,
    autoRetrain,
    lastCorrection:
      raw.last_correction && typeof raw.last_correction === "object"
        ? (raw.last_correction as FeedbackStatus["lastCorrection"])
        : null,
  }
}

function parseFeedbackEvidence(raw: unknown): FeedbackEvidenceStatus | undefined {
  if (!raw || typeof raw !== "object") return undefined
  const e = raw as Record<string, unknown>
  return {
    available: Boolean(e.available),
    capturedAt:
      typeof e.capturedAt === "string"
        ? e.capturedAt
        : typeof e.captured_at === "string"
          ? e.captured_at
          : undefined,
    primaryState:
      typeof e.primaryState === "string"
        ? e.primaryState
        : typeof e.primary_state === "string"
          ? e.primary_state
          : undefined,
    confidence: Number(e.confidence ?? 0),
    frameCount: Number(e.frameCount ?? e.frame_count ?? 0),
  }
}

export type StateTransitionItem = {
  id: string
  capturedAt: string
  fromLabel: string
  toLabel: string
  confidence: number
  sequence: number
  screenshotCount: number
  correctedLabel?: string | null
  correctionId?: string | null
  notes?: string
  corrected: boolean
}

export type TransitionsListResponse = {
  enabled: boolean
  transitions: StateTransitionItem[]
  total?: number
  pendingReview?: number
  reason?: string
}

export function transitionFrameUrl(transitionId: string, frameIndex: number): string {
  return `${API_BASE}/api/live/transitions/${encodeURIComponent(transitionId)}/frames/${frameIndex}.jpg`
}

export async function fetchTransitions(
  opts?: { limit?: number; uncorrectedOnly?: boolean },
  signal?: AbortSignal,
): Promise<TransitionsListResponse> {
  const params = new URLSearchParams()
  if (opts?.limit) params.set("limit", String(opts.limit))
  if (opts?.uncorrectedOnly) params.set("uncorrected_only", "true")
  const q = params.toString()
  const res = await fetch(
    `${API_BASE}/api/live/transitions${q ? `?${q}` : ""}`,
    { signal, cache: "no-store" },
  )
  if (!res.ok) throw new Error(`transitions fetch failed: ${res.status}`)
  const raw = (await res.json()) as Record<string, unknown>
  const items = Array.isArray(raw.transitions) ? raw.transitions : []
  return {
    enabled: Boolean(raw.enabled),
    total: Number(raw.total ?? 0),
    pendingReview: Number(raw.pendingReview ?? raw.pending_review ?? 0),
    reason: typeof raw.reason === "string" ? raw.reason : undefined,
    transitions: items.map((t) => {
      const row = t as Record<string, unknown>
      return {
        id: String(row.id ?? ""),
        capturedAt: String(row.capturedAt ?? row.captured_at ?? ""),
        fromLabel: String(row.fromLabel ?? row.from_label ?? ""),
        toLabel: String(row.toLabel ?? row.to_label ?? ""),
        confidence: Number(row.confidence ?? 0),
        sequence: Number(row.sequence ?? 0),
        screenshotCount: Number(row.screenshotCount ?? row.screenshot_count ?? 0),
        correctedLabel:
          row.correctedLabel != null
            ? String(row.correctedLabel)
            : row.corrected_label != null
              ? String(row.corrected_label)
              : null,
        correctionId:
          row.correctionId != null
            ? String(row.correctionId)
            : row.correction_id != null
              ? String(row.correction_id)
              : null,
        notes: String(row.notes ?? ""),
        corrected: Boolean(row.corrected ?? row.corrected_label),
      }
    }),
  }
}

export async function correctTransition(
  transitionId: string,
  input: { correctedLabel: RoomStateId; notes?: string },
): Promise<FeedbackResponse & { transitionId?: string; fromLabel?: string }> {
  const res = await fetch(
    `${API_BASE}/api/live/transitions/${encodeURIComponent(transitionId)}/correct`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        corrected_label: input.correctedLabel,
        notes: input.notes ?? "",
      }),
    },
  )
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    const msg =
      typeof detail?.detail === "string"
        ? detail.detail
        : `transition correct failed: ${res.status}`
    throw new Error(msg)
  }
  const raw = (await res.json()) as Record<string, unknown>
  const previewRaw = raw.probabilityPreview ?? raw.probability_preview
  const effectsRaw = raw.effects as Record<string, string> | undefined
  let probabilityPreview: FeedbackResponse["probabilityPreview"]
  if (previewRaw && typeof previewRaw === "object") {
    const p = previewRaw as Record<string, unknown>
    probabilityPreview = {
      before: normalizeFeedbackProbs(p.before),
      after: normalizeFeedbackProbs(p.after),
      corrected_label: String(p.corrected_label ?? p.correctedLabel ?? ""),
      appliedAfterSave: Boolean(p.appliedAfterSave ?? p.applied_after_save),
      nearest_similarity: Number(p.nearest_similarity ?? 0),
    }
  }
  return {
    status: "recorded",
    id: String(raw.id ?? ""),
    createdAt: String(raw.createdAt ?? raw.created_at ?? ""),
    predictedLabel: String(raw.predictedLabel ?? raw.predicted_label ?? ""),
    correctedLabel: String(raw.correctedLabel ?? raw.corrected_label ?? ""),
    confirmed: Boolean(raw.confirmed ?? false),
    screenshotCount: 0,
    influence: 0,
    memoryExamples: Number(raw.memoryExamples ?? raw.memory_examples ?? 0),
    retrainsModel: Boolean(raw.retrainsModel ?? raw.retrains_model),
    transitionId: String(raw.transitionId ?? raw.transition_id ?? transitionId),
    fromLabel: String(raw.fromLabel ?? raw.from_label ?? ""),
    effects: {
      immediate: String(effectsRaw?.immediate ?? ""),
      ongoing: String(effectsRaw?.ongoing ?? ""),
      notIncluded: String(effectsRaw?.notIncluded ?? effectsRaw?.not_included ?? ""),
    },
    probabilityPreview,
  }
}

export async function submitLiveFeedback(input: {
  correctedLabel: RoomStateId
  notes?: string
}): Promise<FeedbackResponse> {
  const res = await fetch(`${API_BASE}/api/live/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      corrected_label: input.correctedLabel,
      notes: input.notes ?? "",
    }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    const msg =
      typeof detail?.detail === "string"
        ? detail.detail
        : `feedback submit failed: ${res.status}`
    throw new Error(msg)
  }
  const raw = (await res.json()) as Record<string, unknown>
  const previewRaw = raw.probabilityPreview ?? raw.probability_preview
  const effectsRaw = raw.effects as Record<string, string> | undefined
  let probabilityPreview: FeedbackResponse["probabilityPreview"]
  if (previewRaw && typeof previewRaw === "object") {
    const p = previewRaw as Record<string, unknown>
    probabilityPreview = {
      before: normalizeFeedbackProbs(p.before),
      after: normalizeFeedbackProbs(p.after),
      corrected_label: String(p.corrected_label ?? p.correctedLabel ?? ""),
      appliedAfterSave: Boolean(p.appliedAfterSave ?? p.applied_after_save),
      nearest_similarity: Number(p.nearest_similarity ?? 0),
    }
  }
  return {
    status: "recorded",
    id: String(raw.id ?? ""),
    createdAt: String(raw.createdAt ?? raw.created_at ?? ""),
    predictedLabel: String(raw.predictedLabel ?? raw.predicted_label ?? ""),
    correctedLabel: String(raw.correctedLabel ?? raw.corrected_label ?? ""),
    confirmed: Boolean(raw.confirmed ?? false),
    screenshotCount: Number(raw.screenshotCount ?? raw.screenshot_count ?? 0),
    influence: Number(raw.influence ?? 0),
    memoryExamples: Number(raw.memoryExamples ?? raw.memory_examples ?? 0),
    retrainsModel: Boolean(raw.retrainsModel ?? raw.retrains_model),
    effects: {
      immediate: String(effectsRaw?.immediate ?? ""),
      ongoing: String(effectsRaw?.ongoing ?? ""),
      notIncluded: String(effectsRaw?.notIncluded ?? effectsRaw?.not_included ?? ""),
    },
    probabilityPreview,
    storage:
      raw.storage && typeof raw.storage === "object"
        ? (raw.storage as FeedbackResponse["storage"])
        : undefined,
  }
}

export async function fetchPreferenceDocument(signal?: AbortSignal): Promise<PreferenceDocument> {
  const res = await fetch(`${API_BASE}/api/preferences`, { signal, cache: "no-store" })
  if (!res.ok) throw new Error(`preferences fetch failed: ${res.status}`)
  const raw: unknown = await res.json()
  const doc = parsePreferenceDocument(raw)
  if (!doc) throw new Error("preferences response failed validation")
  return doc
}

export async function savePreferenceDocument(doc: PreferenceDocument): Promise<PreferenceDocument> {
  const res = await fetch(`${API_BASE}/api/preferences`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(doc),
  })
  if (!res.ok) throw new Error(`preferences save failed: ${res.status}`)
  const raw: unknown = await res.json()
  const parsed = parsePreferenceDocument(raw)
  if (!parsed) throw new Error("preferences save response failed validation")
  return parsed
}

export { normalizeSnapshot }
