import type { QueryClient } from "@tanstack/react-query"

import { MOODS_QUERY_KEY } from "@/hooks/use-moods"
import {
  fetchDeviceSettingsDocument,
  fetchMoods,
  fetchPreferenceDocument,
  fetchRhythmSummaries,
  fetchTransitions,
} from "@/lib/roomos/api-client"
import { defaultDeviceSettingsDocument } from "@/lib/roomos/device-settings-schema"
import { loadDeviceSettingsLocal } from "@/lib/roomos/device-settings-persistence"
import {
  defaultPreferenceDocument,
} from "@/lib/roomos/preferences-schema"
import {
  parsePreferenceDocument,
} from "@/lib/roomos/preferences-document-schema"
import { loadRoomOsPreferences } from "@/lib/roomos/preferences-persistence"
import { registerMoodLabels } from "@/lib/roomos/state-meta"
import type { DeviceSettingsDocument } from "@/types/device-settings"
import type { PreferenceDocument } from "@/types/roomos"

export const DASHBOARD_STALE_MS = 5 * 60_000

export type IntegrationsQueryResult = {
  doc: DeviceSettingsDocument
  apiOnline: boolean
  authRequired: boolean
}

export type PreferencesQueryResult = {
  doc: PreferenceDocument
  apiOnline: boolean
  authRequired: boolean
}

export function integrationsQueryKey(userId?: string | null) {
  return ["roomos", "integrations", userId ?? "local"] as const
}

export function preferencesQueryKey(userId?: string | null) {
  return ["roomos", "preferences", userId ?? "local"] as const
}

export function integrationsInitialData(): IntegrationsQueryResult | undefined {
  const local = loadDeviceSettingsLocal()
  if (!local) return undefined
  return { doc: local, apiOnline: false, authRequired: false }
}

export function preferencesInitialData(): PreferencesQueryResult | undefined {
  const disk = loadRoomOsPreferences()
  if (!disk) return undefined
  const doc =
    parsePreferenceDocument({
      schemaVersion: 2,
      updatedAt: new Date().toISOString(),
      presets: disk.presets,
      activePresetId: disk.activePresetId,
    }) ?? defaultPreferenceDocument()
  return { doc, apiOnline: false, authRequired: false }
}

export async function fetchIntegrationsQuery(
  userId?: string | null,
): Promise<IntegrationsQueryResult> {
  try {
    const doc = await fetchDeviceSettingsDocument()
    return { doc, apiOnline: true, authRequired: false }
  } catch (e) {
    const message = e instanceof Error ? e.message : ""
    const authRequired = message.includes("Sign in required")
    const local = loadDeviceSettingsLocal()
    return {
      doc: local ?? defaultDeviceSettingsDocument(),
      apiOnline: false,
      authRequired,
    }
  }
}

export async function fetchPreferencesQuery(
  userId?: string | null,
): Promise<PreferencesQueryResult> {
  try {
    const doc = await fetchPreferenceDocument()
    return { doc, apiOnline: true, authRequired: false }
  } catch (e) {
    const message = e instanceof Error ? e.message : ""
    const authRequired = message.includes("Sign in required")
    const disk = loadRoomOsPreferences()
    if (disk) {
      const doc =
        parsePreferenceDocument({
          schemaVersion: 2,
          updatedAt: new Date().toISOString(),
          presets: disk.presets,
          activePresetId: disk.activePresetId,
        }) ?? defaultPreferenceDocument()
      return { doc, apiOnline: false, authRequired }
    }
    return { doc: defaultPreferenceDocument(), apiOnline: false, authRequired }
  }
}

export function integrationsQueryOptions(userId?: string | null) {
  return {
    queryKey: integrationsQueryKey(userId),
    queryFn: () => fetchIntegrationsQuery(userId),
    staleTime: DASHBOARD_STALE_MS,
  } as const
}

export function preferencesQueryOptions(userId?: string | null) {
  return {
    queryKey: preferencesQueryKey(userId),
    queryFn: () => fetchPreferencesQuery(userId),
    staleTime: DASHBOARD_STALE_MS,
    retry: 1,
  } as const
}

export function prefetchMoods(queryClient: QueryClient) {
  return queryClient.prefetchQuery({
    queryKey: MOODS_QUERY_KEY,
    queryFn: async ({ signal }) => {
      const data = await fetchMoods(signal)
      registerMoodLabels(data.moods)
      return data
    },
    staleTime: DASHBOARD_STALE_MS,
  })
}

export function prefetchIntegrations(queryClient: QueryClient, userId?: string | null) {
  return queryClient.prefetchQuery(integrationsQueryOptions(userId))
}

export function prefetchPreferences(queryClient: QueryClient, userId?: string | null) {
  return queryClient.prefetchQuery(preferencesQueryOptions(userId))
}

export function prefetchRhythm(queryClient: QueryClient) {
  return queryClient.prefetchQuery({
    queryKey: ["roomos", "rhythm", "all"],
    queryFn: ({ signal }) => fetchRhythmSummaries(signal),
    staleTime: DASHBOARD_STALE_MS,
  })
}

export function prefetchReview(queryClient: QueryClient) {
  return queryClient.prefetchQuery({
    queryKey: ["roomos", "transitions", "full", "pending"],
    queryFn: () =>
      fetchTransitions({ limit: 40, uncorrectedOnly: true }),
    staleTime: 30_000,
  })
}

/** Warm caches shared across most dashboard tabs. */
export function prefetchDashboardCore(queryClient: QueryClient, userId?: string | null) {
  void prefetchMoods(queryClient)
  void prefetchIntegrations(queryClient, userId)
}

const ROUTE_PREFETCH: Record<string, (qc: QueryClient, userId?: string | null) => void> = {
  "/preferences": (qc, userId) => {
    prefetchDashboardCore(qc, userId)
    void prefetchPreferences(qc, userId)
  },
  "/connections": (qc, userId) => {
    void prefetchIntegrations(qc, userId)
  },
  "/rhythm": (qc) => {
    void prefetchRhythm(qc)
  },
  "/review": (qc) => {
    void prefetchMoods(qc)
    void prefetchReview(qc)
  },
}

export function prefetchDashboardRoute(
  queryClient: QueryClient,
  href: string,
  userId?: string | null,
) {
  ROUTE_PREFETCH[href]?.(queryClient, userId)
}
