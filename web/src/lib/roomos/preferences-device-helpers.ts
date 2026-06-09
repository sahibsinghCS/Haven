import type { DeviceSettingsDocument } from "@/types/device-settings"
import type {
  ConnectedDeviceRef,
  DevicePreferenceTarget,
  PreferenceMatrix,
  PreferenceMoodId,
} from "@/types/roomos"
import { PREFERENCE_MOOD_ORDER } from "@/types/roomos"

import { LEGACY_MOOD_DEFAULTS } from "@/lib/roomos/preferences-schema"

export function listConnectedDevices(doc: DeviceSettingsDocument | null | undefined): ConnectedDeviceRef[] {
  const devices = doc?.devices
  if (!devices) return []

  const out: ConnectedDeviceRef[] = []
  for (const plug of devices.smartPlugs ?? []) {
    if (plug.connected && plug.enabled) {
      out.push({
        id: plug.id,
        category: "smart_plug",
        label: plug.label?.trim() || "Smart plug",
        brand: plug.brand,
      })
    }
  }
  for (const lights of devices.lights ?? []) {
    if (lights.connected && lights.enabled) {
      out.push({
        id: lights.id,
        category: "lights",
        label: lights.label?.trim() || lights.notes?.trim() || "Lights",
        brand: lights.brand,
      })
    }
  }
  for (const thermo of devices.thermostats ?? []) {
    if (thermo.connected && thermo.enabled && thermo.brand !== "none") {
      out.push({
        id: thermo.id,
        category: "thermostat",
        label: thermo.notes?.trim() || "Thermostat",
        brand: thermo.brand,
      })
    }
  }
  return out
}

export function defaultTargetForDevice(
  stateId: PreferenceMoodId,
  category: ConnectedDeviceRef["category"],
): DevicePreferenceTarget {
  const legacy = LEGACY_MOOD_DEFAULTS[stateId]
  if (category === "smart_plug") {
    return { fanOn: legacy.fanOn }
  }
  if (category === "lights") {
    return { brightness: legacy.brightness, lightColorHex: legacy.lightColorHex }
  }
  return { temperatureF: legacy.temperatureF }
}

export function emptyPreferenceMatrix(): PreferenceMatrix {
  return PREFERENCE_MOOD_ORDER.reduce((acc, stateId) => {
    acc[stateId] = { devices: {} }
    return acc
  }, {} as PreferenceMatrix)
}

type LegacyScene = {
  lightColorHex?: string
  brightness?: number
  fanOn?: boolean
  temperatureF?: number
}

export function migrateSceneToV2(
  scene: LegacyScene & { devices?: Record<string, DevicePreferenceTarget> },
  integrations: DeviceSettingsDocument,
  stateId?: PreferenceMoodId,
): { devices: Record<string, DevicePreferenceTarget> } {
  const legacy = stateId ? LEGACY_MOOD_DEFAULTS[stateId] : undefined
  const fanOn = scene.fanOn ?? legacy?.fanOn ?? false
  const brightness = scene.brightness ?? legacy?.brightness ?? 30
  const lightColorHex = scene.lightColorHex ?? legacy?.lightColorHex ?? "#2A2A2A"
  const temperatureF = scene.temperatureF ?? legacy?.temperatureF ?? 72

  const devices: Record<string, DevicePreferenceTarget> =
    scene.devices && typeof scene.devices === "object" ? { ...scene.devices } : {}

  const deviceLists = integrations?.devices
  if (!deviceLists) return { devices }

  for (const plug of deviceLists.smartPlugs ?? []) {
    if (plug.connected && plug.enabled && !devices[plug.id]) {
      devices[plug.id] = { fanOn: Boolean(fanOn) }
    }
  }
  for (const lights of deviceLists.lights ?? []) {
    if (lights.connected && lights.enabled && !devices[lights.id]) {
      devices[lights.id] = { brightness: Number(brightness), lightColorHex: String(lightColorHex) }
    }
  }
  for (const thermo of deviceLists.thermostats ?? []) {
    if (thermo.connected && thermo.enabled && thermo.brand !== "none" && !devices[thermo.id]) {
      devices[thermo.id] = { temperatureF: Number(temperatureF) }
    }
  }
  return { devices }
}

export function mergeDevicesIntoMatrix(
  matrix: PreferenceMatrix,
  connected: ConnectedDeviceRef[],
): PreferenceMatrix {
  const next = structuredClone(matrix)
  const connectedIds = new Set(connected.map((d) => d.id))

  for (const stateId of PREFERENCE_MOOD_ORDER) {
    const scene = next[stateId]
    for (const id of Object.keys(scene.devices)) {
      if (!connectedIds.has(id)) {
        delete scene.devices[id]
      }
    }
    for (const device of connected) {
      if (!scene.devices[device.id]) {
        scene.devices[device.id] = defaultTargetForDevice(stateId, device.category)
      }
    }
  }
  return next
}

export function migratePreferenceMatrix(
  matrix: Record<string, unknown>,
  integrations: DeviceSettingsDocument,
): PreferenceMatrix {
  const out = emptyPreferenceMatrix()
  for (const stateId of PREFERENCE_MOOD_ORDER) {
    const scene = matrix[stateId]
    if (scene && typeof scene === "object") {
      out[stateId] = migrateSceneToV2(
        scene as LegacyScene & { devices?: Record<string, DevicePreferenceTarget> },
        integrations,
        stateId,
      )
    }
  }
  return mergeDevicesIntoMatrix(out, listConnectedDevices(integrations))
}
