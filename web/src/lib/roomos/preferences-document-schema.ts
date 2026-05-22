import { z } from "zod"

import { preferenceMatrixSchema } from "@/lib/roomos/preferences-schema"
import type { PreferenceDocument, PreferencePreset } from "@/types/roomos"

const preferencePresetSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  description: z.string().optional(),
  isDefault: z.boolean().optional(),
  preferences: preferenceMatrixSchema,
})

export const preferenceDocumentSchema = z
  .object({
    schemaVersion: z.literal(1),
    updatedAt: z.string(),
    presets: z.array(preferencePresetSchema).min(1),
    activePresetId: z.string().min(1).optional(),
  })
  .transform((doc, ctx) => {
    const ids = doc.presets.map((p) => p.id)
    let active = doc.activePresetId
    if (!active || !ids.includes(active)) {
      active = doc.presets.find((p) => p.isDefault)?.id ?? ids[0]
    }
    if (!active) {
      ctx.addIssue({ code: "custom", message: "No active preset could be resolved" })
      return z.NEVER
    }
    return { ...doc, activePresetId: active } satisfies PreferenceDocument
  })

export function parsePreferenceDocument(raw: unknown): PreferenceDocument | null {
  const result = preferenceDocumentSchema.safeParse(raw)
  return result.success ? result.data : null
}

export function buildPreferenceDocument(
  presets: PreferencePreset[],
  activePresetId: string,
): PreferenceDocument {
  const parsed = preferenceDocumentSchema.parse({
    schemaVersion: 1,
    updatedAt: new Date().toISOString(),
    presets,
    activePresetId,
  })
  return parsed
}
