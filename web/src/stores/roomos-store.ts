"use client"

import { create } from "zustand"

import { savePreferenceDocument } from "@/lib/roomos/api-client"
import { buildPreferenceDocument } from "@/lib/roomos/preferences-document-schema"
import {
  loadRoomOsPreferences,
  saveRoomOsPreferences,
  type PersistedPreferencesV1,
} from "@/lib/roomos/preferences-persistence"
import type { PreferenceDocument, PreferencePreset, RoomStateId } from "@/types/roomos"

function migratePresetsFromStorage(presets: PreferencePreset[]): PreferencePreset[] {
  return presets.map((p) =>
    p.id === "preset_focus"
      ? {
          ...p,
          id: "preset_custom",
          name: "Custom",
          description: "Your personal mix. Adjust any mood, then save.",
        }
      : p,
  )
}

function normalizeActiveId(activePresetId: string, presets: PreferencePreset[]): string {
  const ids = new Set(presets.map((p) => p.id))
  if (ids.has(activePresetId)) return activePresetId
  if (activePresetId === "preset_focus" && ids.has("preset_custom")) return "preset_custom"
  return presets.find((p) => p.isDefault)?.id ?? presets[0]?.id ?? activePresetId
}

function resolveActiveFromDoc(doc: PreferenceDocument): string {
  if (doc.activePresetId) {
    return normalizeActiveId(doc.activePresetId, doc.presets)
  }
  return normalizeActiveId("", doc.presets)
}

type RoomOsPreferencesState = {
  presets: PreferencePreset[] | null
  activePresetId: string | null
  hasHydrated: boolean
  hydrate: (doc: PreferenceDocument) => void
  selectPreset: (id: string) => void
  replacePreset: (preset: PreferencePreset) => void
}

function persistLocalCache(presets: PreferencePreset[], activePresetId: string) {
  const payload: PersistedPreferencesV1 = {
    version: 1,
    presets,
    activePresetId,
  }
  saveRoomOsPreferences(payload)
}

async function syncDocumentToApi(presets: PreferencePreset[], activePresetId: string) {
  await savePreferenceDocument(buildPreferenceDocument(presets, activePresetId))
}

const boot = (() => {
  const disk = loadRoomOsPreferences()
  if (!disk) {
    return { presets: null as PreferencePreset[] | null, activePresetId: null as string | null, hasHydrated: false }
  }
  const presets = migratePresetsFromStorage(disk.presets)
  const activePresetId = normalizeActiveId(disk.activePresetId, presets)
  return { presets, activePresetId, hasHydrated: true }
})()

export const useRoomOsPreferencesStore = create<RoomOsPreferencesState>((set, get) => ({
  presets: boot.presets,
  activePresetId: boot.activePresetId,
  hasHydrated: boot.hasHydrated,

  hydrate: (doc) => {
    const presets = migratePresetsFromStorage(doc.presets)
    const activePresetId = resolveActiveFromDoc({ ...doc, presets })

    set({ presets, activePresetId, hasHydrated: true })
    persistLocalCache(presets, activePresetId)
  },

  selectPreset: (id) => {
    const presets = get().presets
    if (!presets) return
    const activePresetId = normalizeActiveId(id, presets)
    set({ activePresetId })
    persistLocalCache(presets, activePresetId)
    void syncDocumentToApi(presets, activePresetId).catch(() => {
      /* offline: local file will sync on next successful save */
    })
  },

  replacePreset: (preset) => {
    const nextPresets = (get().presets ?? []).map((p) => (p.id === preset.id ? preset : p))
    const activePresetId = get().activePresetId ?? preset.id
    set({ presets: nextPresets })
    persistLocalCache(nextPresets, activePresetId)
  },
}))

/** @deprecated Use activePresetId. alias for components mid-migration */
export function useSelectedPresetId(): string | null {
  return useRoomOsPreferencesStore((s) => s.activePresetId)
}

export const useRoomOsAmbientStore = create<{
  primaryState: RoomStateId | null
 /** Last mood seen on Live. soft ambient tint on light dashboard pages */
  lastAmbientMood: RoomStateId | null
  setPrimaryState: (state: RoomStateId | null) => void
  cameraRefreshNonce: number
  bumpCameraRefresh: () => void
}>((set) => ({
  primaryState: null,
  lastAmbientMood: null,
  setPrimaryState: (primaryState) =>
    set((s) => ({
      primaryState,
      lastAmbientMood: primaryState ?? s.lastAmbientMood,
    })),
  cameraRefreshNonce: 0,
  bumpCameraRefresh: () =>
    set((s) => ({ cameraRefreshNonce: s.cameraRefreshNonce + 1 })),
}))
