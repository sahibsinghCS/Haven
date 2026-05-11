import { z } from "zod"

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

/** Stable defaults for form boot before mock hydration (matches backend shape). */
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
