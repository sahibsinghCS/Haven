export type PreferencesEventSource = "telegram" | "web"

export interface LivePreferencesEvent {
  source: PreferencesEventSource
  updatedAt: string
  activePresetId: string
  presetName: string
  targetStates: string[]
  changes: string[]
  notes: string
}
