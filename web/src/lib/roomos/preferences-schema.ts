import { z } from "zod"

import type { PreferenceDocument, PreferencePreset } from "@/types/roomos"
import { PREFERENCE_MOOD_ORDER } from "@/types/roomos"

const hex = z
  .string()
  .regex(/^#[0-9A-Fa-f]{6}$/i, "Use a 6-digit hex color (e.g. #1E2A4A)")

export const devicePreferenceTargetSchema = z.object({
  fanOn: z.boolean().optional(),
  brightness: z.number().min(0).max(100).optional(),
  lightColorHex: hex.optional(),
  temperatureF: z.number().min(60).max(82).optional(),
})

export const statePreferenceSchema = z.object({
  devices: z.record(z.string(), devicePreferenceTargetSchema),
})

/** Dynamic: any registered mood id maps to a device scene. */
export const preferenceMatrixSchema = z.record(z.string(), statePreferenceSchema)

export type PreferenceMatrixFormValues = z.infer<typeof preferenceMatrixSchema>

/** Legacy v1 defaults. used when seeding per-device targets. */
export const LEGACY_MOOD_DEFAULTS = {
  sleep: {
    lightColorHex: "#1E2A4A",
    brightness: 8,
    fanOn: true,
    temperatureF: 68,
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
} as const

/** Defaults for a mood id. builtin values, or work-like neutrals for custom moods. */
export function legacyDefaultsForMood(stateId: string): {
  lightColorHex: string
  brightness: number
  fanOn: boolean
  temperatureF: number
} {
  if (stateId in LEGACY_MOOD_DEFAULTS) {
    return LEGACY_MOOD_DEFAULTS[stateId as keyof typeof LEGACY_MOOD_DEFAULTS]
  }
  return { lightColorHex: "#F5E6C8", brightness: 55, fanOn: false, temperatureF: 72 }
}

/** Stable defaults before API/local hydration (matches backend shape). */
export const EMPTY_PREFERENCE_MATRIX: PreferenceMatrixFormValues = PREFERENCE_MOOD_ORDER.reduce(
  (acc, stateId) => {
    acc[stateId] = { devices: {} }
    return acc
  },
  {} as PreferenceMatrixFormValues,
)

const CUSTOM_LEGACY_MOOD_DEFAULTS = {
  sleep: {
    lightColorHex: "#0F172A",
    brightness: 4,
    fanOn: true,
    temperatureF: 67,
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
} as const

/** Defaults when the API is offline (matches backend ``_DEFAULT_DOC``). */
export function defaultPreferenceDocument(): PreferenceDocument {
  const presets: PreferencePreset[] = [
    {
      id: "preset_basic",
      name: "Basic Preference",
      description: "Balanced defaults for day-to-night transitions.",
      isDefault: true,
      preferences: { ...EMPTY_PREFERENCE_MATRIX },
    },
    {
      id: "preset_custom",
      name: "Custom",
      description: "Your personal mix. Adjust any mood, then save.",
      isDefault: false,
      preferences: PREFERENCE_MOOD_ORDER.reduce((acc, stateId) => {
        acc[stateId] = { devices: {} }
        return acc
      }, {} as PreferenceMatrixFormValues),
    },
  ]
  return {
    schemaVersion: 2,
    updatedAt: new Date().toISOString(),
    presets,
    activePresetId: "preset_basic",
  }
}

export { CUSTOM_LEGACY_MOOD_DEFAULTS }
