import type {
  LiveInferenceSnapshot,
  PreferenceDocument,
  RoomStateDistribution,
  RoomStateId,
} from "@/types/roomos"
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
      examples: Number(personalizationRaw.examples ?? 0),
      matches: Number(personalizationRaw.matches ?? 0),
      nearestSimilarity: Number(personalizationRaw.nearest_similarity ?? personalizationRaw.nearestSimilarity ?? 0),
      influence: Number(personalizationRaw.influence ?? 0),
    },
    dataSource: typeof s.dataSource === "string" ? s.dataSource : "roomos-ml",
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

export type LiveEngineStatus = {
  engine_running: boolean
  engine_error: string | null
  has_snapshot: boolean
}

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

export type FeedbackResponse = {
  status: "recorded"
  id: string
  createdAt: string
  predictedLabel: string
  correctedLabel: string
  screenshotCount: number
  influence: number
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
  return (await res.json()) as FeedbackResponse
}

export async function fetchPreferenceDocument(signal?: AbortSignal): Promise<PreferenceDocument> {
  const res = await fetch(`${API_BASE}/api/preferences`, { signal, cache: "no-store" })
  if (!res.ok) throw new Error(`preferences fetch failed: ${res.status}`)
  return (await res.json()) as PreferenceDocument
}

export async function savePreferenceDocument(doc: PreferenceDocument): Promise<PreferenceDocument> {
  const res = await fetch(`${API_BASE}/api/preferences`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(doc),
  })
  if (!res.ok) throw new Error(`preferences save failed: ${res.status}`)
  return (await res.json()) as PreferenceDocument
}

export { normalizeSnapshot }
