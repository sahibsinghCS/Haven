import { z } from "zod"

import type {
  DeviceSettingsDocument,
  LightsBrand,
  LightsDevice,
  SmartPlugBrand,
  SmartPlugDevice,
  ThermostatBrand,
  ThermostatDevice,
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
  label: z.string().optional(),
  tuyaDeviceId: z.string().optional(),
  tuyaLocalKey: z.string().optional(),
  tuyaVersion: z.string().optional(),
  hueAppKey: z.string().optional(),
  nanoleafToken: z.string().optional(),
  goveeApiKey: z.string().optional(),
  tapoEmail: z.string().optional(),
  tapoPassword: z.string().optional(),
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

const smartPlugDeviceSchema = smartPlugSchema.extend({ id: z.string().min(1) })
const lightsDeviceSchema = lightsSchema.extend({ id: z.string().min(1) })
const thermostatDeviceSchema = thermostatSchema.extend({ id: z.string().min(1) })

export const deviceSettingsDocumentSchema = z.object({
  schemaVersion: z.literal(2),
  updatedAt: z.string(),
  devices: z.object({
    smartPlugs: z.array(smartPlugDeviceSchema),
    lights: z.array(lightsDeviceSchema),
    thermostats: z.array(thermostatDeviceSchema),
  }),
})

function newDeviceId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `device-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

export function defaultSmartPlugDevice(): SmartPlugDevice {
  return {
    id: newDeviceId(),
    enabled: false,
    connected: false,
    brand: "tapo",
    host: "",
    label: "Desk plug",
    tapoEmail: "",
    tapoPassword: "",
  }
}

export function defaultLightsDevice(): LightsDevice {
  return {
    id: newDeviceId(),
    enabled: false,
    connected: false,
    brand: "none",
    notes: "",
  }
}

export function defaultThermostatDevice(): ThermostatDevice {
  return {
    id: newDeviceId(),
    enabled: false,
    connected: false,
    brand: "none",
    notes: "",
  }
}

export function defaultDeviceSettingsDocument(): DeviceSettingsDocument {
  const now = new Date().toISOString()
  return {
    schemaVersion: 2,
    updatedAt: now,
    devices: {
      smartPlugs: [],
      lights: [],
      thermostats: [],
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
  if (tapoEmail && tapoPassword && (brand === "other_plug" || brand === "none")) {
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

function normalizeDeviceArray<T extends { id: string }>(
  itemsIn: unknown,
  legacyBlock: unknown,
  coerce: (raw: Record<string, unknown>) => Record<string, unknown>,
  fallback: () => T,
  schema: z.ZodType<T>,
): T[] {
  const out: T[] = []
  if (Array.isArray(itemsIn)) {
    for (const item of itemsIn) {
      if (!item || typeof item !== "object") continue
      const raw = item as Record<string, unknown>
      const id = String(raw.id ?? "").trim() || newDeviceId()
      const { id: _drop, ...rest } = raw
      const coerced = coerce(rest)
      out.push(schema.parse({ id, ...coerced }))
    }
    return out
  }
  if (legacyBlock && typeof legacyBlock === "object") {
    const raw = legacyBlock as Record<string, unknown>
    const id = String(raw.id ?? "").trim() || newDeviceId()
    const { id: _drop, ...rest } = raw
    const coerced = coerce(rest)
    out.push(schema.parse({ id, ...coerced }))
  }
  if (out.length === 0) {
    return []
  }
  return out
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

  const smartPlugs = normalizeDeviceArray(
    devices.smartPlugs,
    devices.smartPlug,
    coerceSmartPlug,
    defaultSmartPlugDevice,
    smartPlugDeviceSchema,
  )
  const lights = normalizeDeviceArray(
    Array.isArray(devices.lights) ? devices.lights : null,
    !Array.isArray(devices.lights) ? devices.lights : null,
    coerceLights,
    defaultLightsDevice,
    lightsDeviceSchema,
  )
  const thermostats = normalizeDeviceArray(
    devices.thermostats,
    devices.thermostat,
    coerceThermostat,
    defaultThermostatDevice,
    thermostatDeviceSchema,
  )

  return deviceSettingsDocumentSchema.parse({
    schemaVersion: 2,
    updatedAt: typeof doc.updatedAt === "string" ? doc.updatedAt : defaults.updatedAt,
    devices: { smartPlugs, lights, thermostats },
  })
}

/** Legacy settings page — ensure one editable row per category. */
export function ensureMinimumDevices(doc: DeviceSettingsDocument): DeviceSettingsDocument {
  const next = structuredClone(doc)
  if (next.devices.smartPlugs.length === 0) {
    next.devices.smartPlugs = [defaultSmartPlugDevice()]
  }
  if (next.devices.lights.length === 0) {
    next.devices.lights = [defaultLightsDevice()]
  }
  if (next.devices.thermostats.length === 0) {
    next.devices.thermostats = [defaultThermostatDevice()]
  }
  return next
}

export function countConnectedDevices(doc: DeviceSettingsDocument): { connected: number; total: number } {
  const all = [
    ...doc.devices.smartPlugs,
    ...doc.devices.lights,
    ...doc.devices.thermostats,
  ]
  const connected = all.filter((d) => d.connected).length
  return { connected, total: all.length }
}

export type { SmartPlugBrand, LightsBrand, ThermostatBrand }
