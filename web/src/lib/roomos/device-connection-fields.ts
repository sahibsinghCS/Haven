/**
 * Per-brand fields and validation for the Connections page.
 */

import type { DeviceCategory } from "@/lib/roomos/device-setup-guides"
import { getGuide } from "@/lib/roomos/device-setup-guides"
import type {
  DeviceSettingsDocument,
  LightsBrand,
  SmartPlugBrand,
  ThermostatBrand,
} from "@/types/device-settings"

export type ConnectionFieldType = "text" | "email" | "password" | "number"

export interface ConnectionFieldSpec {
  key: string
  label: string
  type: ConnectionFieldType
  placeholder?: string
  hint?: string
  mono?: boolean
}

const PLUG_CLOUD_ONLY: SmartPlugBrand[] = ["wyze", "amazon"]

export function plugFields(brand: SmartPlugBrand): ConnectionFieldSpec[] {
  switch (brand) {
    case "tapo":
      return [
        {
          key: "label",
          label: "Name in Haven",
          type: "text",
          placeholder: "Fan, desk lamp, heater…",
          hint: "Anything you like — shown on this card after you connect.",
        },
        { key: "tapoEmail", label: "Tapo email", type: "email", placeholder: "you@email.com" },
        { key: "tapoPassword", label: "Tapo password", type: "password" },
        {
          key: "host",
          label: "Plug IP address",
          type: "text",
          placeholder: "192.168.1.50",
          hint: "Tapo app → plug → Settings → Device Info → IP",
          mono: true,
        },
      ]
    case "meross":
      return [
        { key: "merossEmail", label: "Meross email", type: "email" },
        { key: "merossPassword", label: "Meross password", type: "password" },
        { key: "label", label: "Plug name in Meross app", type: "text", placeholder: "Fan" },
      ]
    case "tuya":
    case "other_plug":
      return [
        {
          key: "tuyaDeviceId",
          label: "Tuya device ID",
          type: "text",
          hint: "From: python -m tinytuya wizard",
          mono: true,
        },
        { key: "tuyaLocalKey", label: "Local key", type: "password", mono: true },
        {
          key: "host",
          label: "IP address (optional)",
          type: "text",
          placeholder: "192.168.1.50 or Auto",
          mono: true,
        },
        { key: "tuyaVersion", label: "Protocol version", type: "text", placeholder: "3.3", mono: true },
      ]
    case "tplink_kasa":
    case "shelly":
      return [
        {
          key: "host",
          label: "Plug IP address",
          type: "text",
          placeholder: "192.168.1.50",
          hint: "Shelly app → device → network",
          mono: true,
        },
        {
          key: "shellyGen",
          label: "Generation",
          type: "text",
          placeholder: "1 or 2",
          hint: "Gen 2 if you only use the newer Shelly app",
        },
        { key: "label", label: "Name in your home", type: "text", placeholder: "Fan plug" },
      ]
    case "wemo":
      return [
        {
          key: "host",
          label: "Plug IP address",
          type: "text",
          placeholder: "192.168.1.50",
          hint: "Router admin → connected devices",
          mono: true,
        },
        { key: "label", label: "Name in your home", type: "text", placeholder: "Fan plug" },
      ]
    default:
      return [{ key: "label", label: "Device name", type: "text" }]
  }
}

export function lightsFields(brand: LightsBrand): ConnectionFieldSpec[] {
  if (brand === "tuya") {
    return [
      { key: "tuyaDeviceId", label: "Tuya device ID", type: "text", mono: true },
      { key: "tuyaLocalKey", label: "Local key", type: "password", mono: true },
      { key: "host", label: "Bulb IP (optional)", type: "text", mono: true },
    ]
  }
  return [
    {
      key: "notes",
      label: "Room / scene names",
      type: "text",
      placeholder: "Bedroom main, Desk strip…",
      hint: "Names from the brand’s app — used when HAVEN adds direct control for this brand.",
    },
  ]
}

export function thermostatFields(brand: ThermostatBrand): ConnectionFieldSpec[] {
  if (brand === "nest") {
    return [
      { key: "nestProjectId", label: "Nest project ID", type: "text", mono: true },
      { key: "nestClientId", label: "OAuth client ID", type: "text", mono: true },
      { key: "nestClientSecret", label: "OAuth client secret", type: "password", mono: true },
      { key: "nestRefreshToken", label: "Refresh token", type: "password", mono: true },
    ]
  }
  if (brand === "ecobee") {
    return [
      { key: "ecobeeApiKey", label: "Ecobee API key", type: "text", mono: true },
      { key: "ecobeeRefreshToken", label: "Refresh token", type: "password", mono: true },
    ]
  }
  if (brand === "honeywell_home" || brand === "honeywell_tcc") {
    return [
      { key: "username", label: "Account email", type: "email" },
      { key: "password", label: "Password", type: "password" },
      { key: "targetHeatF", label: "Test heat setpoint (°F)", type: "number", placeholder: "70" },
    ]
  }
  return [
    {
      key: "notes",
      label: "Brand, model, account notes",
      type: "text",
      placeholder: "Carrier Infinity, app email…",
    },
  ]
}

export function canConnectCategory(
  category: DeviceCategory,
  devices: DeviceSettingsDocument["devices"],
): boolean {
  if (category === "smart_plug") {
    const brand = resolveSmartPlugBrand(devices.smartPlug)
    if (PLUG_CLOUD_ONLY.includes(brand)) return false
    return Boolean(getGuide("smart_plug", brand)?.supportsDirectControl)
  }
  if (category === "lights") {
    return devices.lights.brand === "tuya"
  }
  if (category === "thermostat") {
    return ["nest", "ecobee", "honeywell_home", "honeywell_tcc"].includes(devices.thermostat.brand)
  }
  return false
}

export function validatePlugConnect(plug: DeviceSettingsDocument["devices"]["smartPlug"]): string | null {
  const brand = resolveSmartPlugBrand(plug)
  if (PLUG_CLOUD_ONLY.includes(brand)) {
    return `${brand === "wyze" ? "Wyze" : "Amazon"} plugs are not supported for direct connect yet.`
  }
  const fields = plugFields(brand)
  for (const f of fields) {
    const val = String((plug as unknown as Record<string, unknown>)[f.key] ?? "").trim()
    if (f.key === "host" && plug.brand === "tuya" && !val) continue
    if (f.key === "tuyaVersion" && !val) continue
    if (f.key === "label" && !val) continue
    if (!val && f.type !== "number") {
      return `Enter ${f.label.toLowerCase()}.`
    }
  }
  if (["tplink_kasa", "shelly", "wemo", "tapo"].includes(brand) && !plug.host?.trim()) {
    return "Enter the plug’s IP address."
  }
  return null
}

export function validateLightsConnect(lights: DeviceSettingsDocument["devices"]["lights"]): string | null {
  if (lights.brand !== "tuya") {
    return "Direct connect is available for Tuya / Smart Life bulbs today. Pick that brand or note your setup below."
  }
  if (!lights.tuyaDeviceId?.trim() || !lights.tuyaLocalKey?.trim()) {
    return "Enter Tuya device ID and local key."
  }
  return null
}

export function validateThermostatConnect(
  thermo: DeviceSettingsDocument["devices"]["thermostat"],
): string | null {
  if (thermo.brand === "honeywell_home" || thermo.brand === "honeywell_tcc") {
    if (!thermo.username?.trim() || !thermo.password?.trim()) {
      return "Enter your Honeywell account email and password."
    }
    return null
  }
  if (thermo.brand === "ecobee") {
    if (!thermo.ecobeeApiKey?.trim() || !thermo.ecobeeRefreshToken?.trim()) {
      return "Enter Ecobee API key and refresh token."
    }
    return null
  }
  if (thermo.brand === "nest") {
    if (!thermo.nestRefreshToken?.trim() || !thermo.nestProjectId?.trim()) {
      return "Complete Nest Device Access setup (project ID + OAuth + refresh token)."
    }
    return null
  }
  return "Pick Nest, ecobee, or Honeywell Home to connect here."
}

/** Prefer Tapo when Tapo credentials are saved (legacy docs may still say tplink_kasa). */
export function resolveSmartPlugBrand(
  plug: DeviceSettingsDocument["devices"]["smartPlug"],
): SmartPlugBrand {
  if (plug.tapoEmail?.trim() && plug.tapoPassword?.trim()) {
    return "tapo"
  }
  return plug.brand
}

export type DeviceRowPresentation = {
  /** Small caps line above the headline (device category). */
  eyebrow: string
  /** Primary line on the card. */
  headline: string
  /** Secondary line — only when disconnected or extra context when connected. */
  detail: string | null
}

function deviceCustomName(
  device: { connected: boolean; label?: string; notes?: string },
  fallback: string,
): string | null {
  if (!device.connected) return null
  const name = device.label?.trim() || device.notes?.trim()
  return name || fallback
}

/** Card copy: custom name only after connect; no brand label on the row. */
export function deviceRowPresentation(
  category: DeviceCategory,
  devices: DeviceSettingsDocument["devices"],
): DeviceRowPresentation {
  if (category === "smart_plug") {
    const plug = devices.smartPlug
    const custom = deviceCustomName(plug, "Smart plug")
    return {
      eyebrow: "Smart plug",
      headline: custom ?? "Smart plug",
      detail: plug.connected
        ? null
        : "Open setup to choose your plug brand and connect.",
    }
  }
  if (category === "lights") {
    const lights = devices.lights
    const custom = deviceCustomName(lights, "Lights")
    return {
      eyebrow: "Lights",
      headline: custom ?? "Lights",
      detail: lights.connected
        ? null
        : lights.brand === "none"
          ? "Open setup to choose your lights brand."
          : "Open setup to finish connecting.",
    }
  }
  const thermo = devices.thermostat
  const custom = deviceCustomName(thermo, "Thermostat")
  return {
    eyebrow: "Thermostat",
    headline: custom ?? "Thermostat",
    detail: thermo.connected
      ? null
      : thermo.brand === "none"
        ? "Open setup to choose your thermostat brand."
        : "Open setup to finish connecting.",
  }
}

/** @deprecated Use deviceRowPresentation */
export function deviceBrandLabel(
  category: DeviceCategory,
  devices: DeviceSettingsDocument["devices"],
): string {
  const row = deviceRowPresentation(category, devices)
  return row.detail ?? row.headline
}
