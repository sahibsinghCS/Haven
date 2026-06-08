import { z } from "zod"

import type {
  DeviceSettingsDocument,
  LightsBrand,
  SmartPlugBrand,
  ThermostatBrand,
} from "@/types/device-settings"
import { migrateLegacyProvider } from "@/lib/roomos/device-setup-guides"

const smartPlugBrandSchema = z.enum([
  "tplink_kasa",
  "tapo",
  "tuya",
  "meross",
  "wyze",
  "shelly",
  "wemo",
  "amazon",
  "other_plug",
])

const lightsBrandSchema = z.enum([
  "none",
  "philips_hue",
  "lifx",
  "wiz",
  "yeelight",
  "govee",
  "kasa_light",
  "tuya",
  "matter",
  "nanoleaf",
  "other_lights",
])

const thermostatBrandSchema = z.enum([
  "none",
  "nest",
  "ecobee",
  "honeywell_home",
  "honeywell_tcc",
  "sensi",
  "amazon",
  "tuya",
  "other_thermostat",
])

const smartPlugSchema = z.object({
  enabled: z.boolean(),
  connected: z.boolean(),
  brand: smartPlugBrandSchema,
  host: z.string(),
  label: z.string(),
  tuyaDeviceId: z.string().optional(),
  tuyaLocalKey: z.string().optional(),
  tuyaVersion: z.string().optional(),
  merossEmail: z.string().optional(),
  merossPassword: z.string().optional(),
  shellyGen: z.string().optional(),
  tapoEmail: z.string().optional(),
  tapoPassword: z.string().optional(),
})

const lightsSchema = z.object({
  enabled: z.boolean(),
  connected: z.boolean(),
  brand: lightsBrandSchema,
  notes: z.string(),
  host: z.string().optional(),
  tuyaDeviceId: z.string().optional(),
  tuyaLocalKey: z.string().optional(),
  tuyaVersion: z.string().optional(),
})

const thermostatSchema = z.object({
  enabled: z.boolean(),
  connected: z.boolean(),
  brand: thermostatBrandSchema,
  notes: z.string(),
  username: z.string().optional(),
  password: z.string().optional(),
  deviceId: z.string().optional(),
  ecobeeApiKey: z.string().optional(),
  ecobeeRefreshToken: z.string().optional(),
  ecobeeThermostatId: z.string().optional(),
  nestProjectId: z.string().optional(),
  nestClientId: z.string().optional(),
  nestClientSecret: z.string().optional(),
  nestRefreshToken: z.string().optional(),
  nestDeviceId: z.string().optional(),
  targetHeatF: z.number().optional(),
  targetCoolF: z.number().optional(),
})

export const deviceSettingsDocumentSchema = z.object({
  schemaVersion: z.literal(1),
  updatedAt: z.string(),
  devices: z.object({
    smartPlug: smartPlugSchema,
    lights: lightsSchema,
    thermostat: thermostatSchema,
  }),
})

export function defaultDeviceSettingsDocument(): DeviceSettingsDocument {
  const now = new Date().toISOString()
  return {
    schemaVersion: 1,
    updatedAt: now,
    devices: {
      smartPlug: {
        enabled: false,
        connected: false,
        brand: "tapo",
        host: "",
        label: "Desk plug",
        tapoEmail: "",
        tapoPassword: "",
      },
      lights: {
        enabled: false,
        connected: false,
        brand: "none",
        notes: "",
      },
      thermostat: {
        enabled: false,
        connected: false,
        brand: "none",
        notes: "",
      },
    },
  }
}

function coerceSmartPlug(raw: Record<string, unknown>): Record<string, unknown> {
  const legacyBrand = raw.brand ?? raw.provider
  let brand = typeof legacyBrand === "string" ? legacyBrand : "tapo"
  if (brand === "kasa" || brand === "other") {
    brand = brand === "kasa" ? "tplink_kasa" : "other_plug"
  }
  if (!smartPlugBrandSchema.safeParse(brand).success) {
    brand = migrateLegacyProvider("smart_plug", String(legacyBrand ?? "tapo"))
  }
  const tapoEmail = String(raw.tapoEmail ?? "").trim()
  const tapoPassword = String(raw.tapoPassword ?? "").trim()
  if (tapoEmail && tapoPassword) {
    brand = "tapo"
  }
  return { ...raw, brand }
}

function coerceLights(raw: Record<string, unknown>): Record<string, unknown> {
  const legacy = raw.brand ?? raw.provider
  let brand = typeof legacy === "string" ? legacy : "none"
  if (!lightsBrandSchema.safeParse(brand).success) {
    brand = migrateLegacyProvider("lights", String(legacy ?? "none"))
  }
  return { ...raw, brand }
}

function coerceThermostat(raw: Record<string, unknown>): Record<string, unknown> {
  const legacy = raw.brand ?? raw.provider
  let brand = typeof legacy === "string" ? legacy : "none"
  if (!thermostatBrandSchema.safeParse(brand).success) {
    brand = migrateLegacyProvider("thermostat", String(legacy ?? "none"))
  }
  return { ...raw, brand }
}

export function parseDeviceSettingsDocument(raw: unknown): DeviceSettingsDocument {
  if (!raw || typeof raw !== "object") {
    return defaultDeviceSettingsDocument()
  }
  const doc = raw as Record<string, unknown>
  const devicesIn = doc.devices
  const defaults = defaultDeviceSettingsDocument()
  if (!devicesIn || typeof devicesIn !== "object") {
    return defaults
  }
  const devices = devicesIn as Record<string, unknown>
  const smartPlug =
    devices.smartPlug && typeof devices.smartPlug === "object"
      ? coerceSmartPlug(devices.smartPlug as Record<string, unknown>)
      : defaults.devices.smartPlug
  const lights =
    devices.lights && typeof devices.lights === "object"
      ? coerceLights(devices.lights as Record<string, unknown>)
      : defaults.devices.lights
  const thermostat =
    devices.thermostat && typeof devices.thermostat === "object"
      ? coerceThermostat(devices.thermostat as Record<string, unknown>)
      : defaults.devices.thermostat

  return deviceSettingsDocumentSchema.parse({
    schemaVersion: 1,
    updatedAt: typeof doc.updatedAt === "string" ? doc.updatedAt : defaults.updatedAt,
    devices: {
      smartPlug,
      lights,
      thermostat,
    },
  })
}

export type { SmartPlugBrand, LightsBrand, ThermostatBrand }
