import { z } from "zod"

import { preferenceMatrixSchema } from "@/lib/roomos/preferences-schema"

const preferencePresetSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().optional(),
  isDefault: z.boolean().optional(),
  preferences: preferenceMatrixSchema,
})

export const persistedPreferencesSchema = z.object({
  version: z.literal(1),
  presets: z.array(preferencePresetSchema).min(1),
  selectedPresetId: z.string(),
})

export type PersistedPreferencesV1 = z.infer<typeof persistedPreferencesSchema>

const STORAGE_KEY = "roomos.preferences.v1"

export function loadRoomOsPreferences(): PersistedPreferencesV1 | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    const result = persistedPreferencesSchema.safeParse(parsed)
    return result.success ? result.data : null
  } catch {
    return null
  }
}

export function saveRoomOsPreferences(data: PersistedPreferencesV1): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch {
    /* quota or private mode */
  }
}

export function clearRoomOsPreferencesStorage(): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
}
