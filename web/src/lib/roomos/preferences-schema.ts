import { z } from "zod"

import type { PreferenceDocument, PreferencePreset } from "@/types/roomos"

const hex = z
  .string()
  .regex(/^#[0-9A-Fa-f]{6}$/i, "Use a 6-digit hex color (e.g. #1E2A4A)")

export const statePreferenceSchema = z.object({
  lightColorHex: hex,
  brightness: z.number().min(0).max(100),
  fanOn: z.boolean(),
  temperatureF: z.number().min(60).max(82),
})

export const preferenceMatrixSchema = z.object({
  sleep: statePreferenceSchema,
  gaming: statePreferenceSchema,
  work: statePreferenceSchema,
  relaxing: statePreferenceSchema,
  away: statePreferenceSchema,
})

export type PreferenceMatrixFormValues = z.infer<typeof preferenceMatrixSchema>

/** Stable defaults before API/local hydration (matches backend shape). */
export const EMPTY_PREFERENCE_MATRIX: PreferenceMatrixFormValues = {
  sleep: {
    lightColorHex: "#1E2A4A",
    brightness: 8,
    fanOn: true,
    temperatureF: 68,
  },
  gaming: {
    lightColorHex: "#6D4AFF",
    brightness: 78,
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
}

const CUSTOM_PREFERENCE_MATRIX: PreferenceMatrixFormValues = {
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
}

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
      preferences: { ...CUSTOM_PREFERENCE_MATRIX },
    },
  ]
  return {
    schemaVersion: 1,
    updatedAt: new Date().toISOString(),
    presets,
    activePresetId: "preset_basic",
  }
}

