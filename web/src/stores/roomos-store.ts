"use client"

import { create } from "zustand"

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
          description: "Your personal mix — adjust any mood, then save.",
        }
      : p,
  )
}

function normalizeSelectedId(selectedPresetId: string, presets: PreferencePreset[]): string {
  const ids = new Set(presets.map((p) => p.id))
  if (ids.has(selectedPresetId)) return selectedPresetId
  if (selectedPresetId === "preset_focus" && ids.has("preset_custom")) return "preset_custom"
  return presets.find((p) => p.isDefault)?.id ?? presets[0]?.id ?? selectedPresetId
}

type RoomOsPreferencesState = {
  presets: PreferencePreset[] | null
  selectedPresetId: string | null
  /** True after first hydrate from server or disk */
  hasHydrated: boolean
  hydrate: (doc: PreferenceDocument) => void
  selectPreset: (id: string) => void
  replacePreset: (preset: PreferencePreset) => void
}

function persistSnapshot(presets: PreferencePreset[], selectedPresetId: string) {
  const payload: PersistedPreferencesV1 = {
    version: 1,
    presets,
    selectedPresetId,
  }
  saveRoomOsPreferences(payload)
}

export const useRoomOsPreferencesStore = create<RoomOsPreferencesState>((set, get) => ({
  presets: null,
  selectedPresetId: null,
  hasHydrated: false,
  hydrate: (doc) => {
    if (get().hasHydrated) return

    const fromDisk = loadRoomOsPreferences()
    if (fromDisk) {
      const presets = migratePresetsFromStorage(fromDisk.presets)
      const selectedPresetId = normalizeSelectedId(fromDisk.selectedPresetId, presets)
      set({
        presets,
        selectedPresetId,
        hasHydrated: true,
      })
      if (
        selectedPresetId !== fromDisk.selectedPresetId ||
        JSON.stringify(presets) !== JSON.stringify(fromDisk.presets)
      ) {
        persistSnapshot(presets, selectedPresetId)
      }
      return
    }

    const defaultId =
      doc.presets.find((p) => p.isDefault)?.id ?? doc.presets[0]?.id ?? null
    set({
      presets: doc.presets,
      selectedPresetId: defaultId,
      hasHydrated: true,
    })
  },
  selectPreset: (id) => {
    const presets = get().presets
    set({ selectedPresetId: id })
    if (presets) persistSnapshot(presets, id)
  },
  replacePreset: (preset) => {
    const nextPresets = (get().presets ?? []).map((p) => (p.id === preset.id ? preset : p))
    const selected = get().selectedPresetId ?? preset.id
    set({ presets: nextPresets })
    persistSnapshot(nextPresets, selected)
  },
}))

export const useRoomOsAmbientStore = create<{
  primaryState: RoomStateId | null
  setPrimaryState: (state: RoomStateId | null) => void
}>((set) => ({
  primaryState: null,
  setPrimaryState: (primaryState) => set({ primaryState }),
}))
