/**
 * Per-brand fields and validation for the Connections page.
 */

import type { DeviceCategory } from "@/lib/roomos/device-setup-guides"
import { getGuide } from "@/lib/roomos/device-setup-guides"
import type {
  LightsDevice,
  LightsSettings,
  SmartPlugDevice,
  SmartPlugSettings,
  ThermostatDevice,
  ThermostatSettings,
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

const PLUG_CLOUD_ONLY: SmartPlugSettings["brand"][] = ["wyze", "amazon"]

export function plugFields(brand: SmartPlugSettings["brand"]): ConnectionFieldSpec[] {
  switch (brand) {
    case "tapo":
      return [
        {
          key: "label",
          label: "Name in Haven",
          type: "text",
          placeholder: "Fan, desk lamp, heater…",
          hint: "Anything you like. shown on this card after you connect.",
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

const LIGHTS_LOCAL_BRANDS: LightsSettings["brand"][] = [
  "tuya",
  "philips_hue",
  "lifx",
  "wiz",
  "yeelight",
  "govee",
  "kasa_light",
  "nanoleaf",
]

const hostField = (hint: string, optional = false): ConnectionFieldSpec => ({
  key: "host",
  label: optional ? "Device IP (optional. Scan fills it)" : "Device IP address",
  type: "text",
  placeholder: "192.168.1.50",
  hint,
  mono: true,
})

const nameField: ConnectionFieldSpec = {
  key: "label",
  label: "Name in Haven",
  type: "text",
  placeholder: "Bedroom lamp, desk strip…",
}

export function lightsFields(brand: LightsSettings["brand"]): ConnectionFieldSpec[] {
  switch (brand) {
    case "tuya":
      return [
        { key: "tuyaDeviceId", label: "Tuya device ID", type: "text", mono: true },
        { key: "tuyaLocalKey", label: "Local key", type: "password", mono: true },
        hostField("Optional. leave blank for Auto", true),
        nameField,
      ]
    case "philips_hue":
      return [
        hostField("Hue bridge IP. Press the round link button, then Connect."),
        {
          key: "hueAppKey",
          label: "Bridge key (auto filled after pairing)",
          type: "password",
 hint: "Leave blank the first time. HAVEN mints it when you press the link button.",
          mono: true,
        },
        nameField,
      ]
    case "nanoleaf":
      return [
        hostField("Nanoleaf controller IP."),
        {
          key: "nanoleafToken",
          label: "Token (auto filled after pairing)",
          type: "password",
 hint: "Leave blank the first time. hold the power button ~6s, then Connect.",
          mono: true,
        },
        nameField,
      ]
    case "govee":
      return [
        hostField("Enable 'LAN Control' in the Govee Home app, then scan."),
        nameField,
      ]
    case "kasa_light":
      return [
        hostField("Run 'Scan my network' to fill this in.", true),
        { key: "tapoEmail", label: "Tapo/Kasa email (Tapo bulbs only)", type: "email" },
        { key: "tapoPassword", label: "Tapo/Kasa password (Tapo bulbs only)", type: "password" },
        nameField,
      ]
    case "lifx":
    case "wiz":
    case "yeelight":
      return [
        hostField(
          brand === "yeelight"
            ? "Enable LAN Control in the Yeelight app, then scan."
            : "Run 'Scan my network' to fill this in.",
        ),
        nameField,
      ]
    default:
      return [
        {
          key: "notes",
          label: "Room / scene names",
          type: "text",
          placeholder: "Bedroom main, Desk strip…",
 hint: "Names from the brand's app. used when HAVEN adds direct control for this brand.",
        },
      ]
  }
}

export function thermostatFields(brand: ThermostatSettings["brand"]): ConnectionFieldSpec[] {
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

export function canConnectPlug(plug: SmartPlugSettings): boolean {
  const brand = resolveSmartPlugBrand(plug)
  if (PLUG_CLOUD_ONLY.includes(brand)) return false
  return Boolean(getGuide("smart_plug", brand)?.supportsDirectControl)
}

export function canConnectLights(lights: LightsSettings): boolean {
  return LIGHTS_LOCAL_BRANDS.includes(lights.brand)
}

export function canConnectThermostat(thermo: ThermostatSettings): boolean {
  return ["nest", "ecobee", "honeywell_home", "honeywell_tcc"].includes(thermo.brand)
}

export function canConnectCategory(category: DeviceCategory, device: SmartPlugSettings | LightsSettings | ThermostatSettings): boolean {
  if (category === "smart_plug") return canConnectPlug(device as SmartPlugSettings)
  if (category === "lights") return canConnectLights(device as LightsSettings)
  if (category === "thermostat") return canConnectThermostat(device as ThermostatSettings)
  return false
}

export function validatePlugConnect(plug: SmartPlugSettings): string | null {
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
    return "Enter the plug's IP address."
  }
  return null
}

export function validateLightsConnect(lights: LightsSettings): string | null {
  const brand = lights.brand
  if (!LIGHTS_LOCAL_BRANDS.includes(brand)) {
    return "Direct connect isn't available for this brand yet. Pick a supported brand or note your setup below."
  }
  if (brand === "tuya") {
    if (!lights.tuyaDeviceId?.trim() || !lights.tuyaLocalKey?.trim()) {
      return "Enter Tuya device ID and local key."
    }
    return null
  }
  if (!lights.host?.trim()) {
    return "Enter the device IP, or run 'Scan my network' to fill it in."
  }
  return null
}

export function validateThermostatConnect(thermo: ThermostatSettings): string | null {
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

export function resolveSmartPlugBrand(plug: SmartPlugSettings): SmartPlugSettings["brand"] {
  const brand = plug.brand
  // Honor an explicit brand pick (Shelly, Meross, etc.) even if Tapo fields are still filled.
  if (brand && brand !== "other_plug") {
    return brand
  }
  // Legacy / ambiguous rows: infer Tapo when credentials are present.
  if (plug.tapoEmail?.trim() && plug.tapoPassword?.trim()) {
    return "tapo"
  }
  return brand
}

export type DeviceRowPresentation = {
  eyebrow: string
  headline: string
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

export function deviceRowPresentation(
  category: DeviceCategory,
  device: SmartPlugDevice | LightsDevice | ThermostatDevice,
): DeviceRowPresentation {
  if (category === "smart_plug") {
    const plug = device as SmartPlugDevice
    const custom = deviceCustomName(plug, "Smart plug")
    return {
      eyebrow: "Smart plug",
      headline: custom ?? "Smart plug",
      detail: plug.connected ? null : "Open setup to choose your plug brand and connect.",
    }
  }
  if (category === "lights") {
    const lights = device as LightsDevice
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
  const thermo = device as ThermostatDevice
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
  device: SmartPlugDevice | LightsDevice | ThermostatDevice,
): string {
  const row = deviceRowPresentation(category, device)
  return row.detail ?? row.headline
}
