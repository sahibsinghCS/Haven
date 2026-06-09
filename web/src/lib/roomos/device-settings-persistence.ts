import {
  defaultDeviceSettingsDocument,
  parseDeviceSettingsDocument,
} from "@/lib/roomos/device-settings-schema"
import type { DeviceSettingsDocument } from "@/types/device-settings"

const STORAGE_KEY = "roomos.integrations.v1"

export function loadDeviceSettingsLocal(): DeviceSettingsDocument | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    return parseDeviceSettingsDocument(parsed)
  } catch {
    return null
  }
}

export function saveDeviceSettingsLocal(doc: DeviceSettingsDocument): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(doc))
  } catch {
    /* quota */
  }
}

export function loadDeviceSettingsWithFallback(): DeviceSettingsDocument {
  return loadDeviceSettingsLocal() ?? defaultDeviceSettingsDocument()
}
