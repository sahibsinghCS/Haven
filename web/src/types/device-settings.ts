/** Brand / ecosystem IDs stored in integrations.json */

export type SmartPlugBrand =
  | "tplink_kasa"
  | "tapo"
  | "tuya"
  | "meross"
  | "wyze"
  | "shelly"
  | "wemo"
  | "amazon"
  | "other_plug"

export type LightsBrand =
  | "none"
  | "philips_hue"
  | "lifx"
  | "wiz"
  | "yeelight"
  | "govee"
  | "kasa_light"
  | "tuya"
  | "matter"
  | "nanoleaf"
  | "other_lights"

export type ThermostatBrand =
  | "none"
  | "nest"
  | "ecobee"
  | "honeywell_home"
  | "honeywell_tcc"
  | "sensi"
  | "amazon"
  | "tuya"
  | "other_thermostat"

export interface SmartPlugSettings {
  enabled: boolean
  connected: boolean
  brand: SmartPlugBrand
  host: string
  label: string
  tuyaDeviceId?: string
  tuyaLocalKey?: string
  tuyaVersion?: string
  merossEmail?: string
  merossPassword?: string
  shellyGen?: string
}

export interface LightsSettings {
  enabled: boolean
  connected: boolean
  brand: LightsBrand
  notes: string
  host?: string
  tuyaDeviceId?: string
  tuyaLocalKey?: string
  tuyaVersion?: string
}

export interface ThermostatSettings {
  enabled: boolean
  connected: boolean
  brand: ThermostatBrand
  notes: string
  username?: string
  password?: string
  deviceId?: string
  ecobeeApiKey?: string
  ecobeeRefreshToken?: string
  ecobeeThermostatId?: string
  /** Google Nest Device Access (not a single API key) */
  nestProjectId?: string
  nestClientId?: string
  nestClientSecret?: string
  nestRefreshToken?: string
  nestDeviceId?: string
  targetHeatF?: number
  targetCoolF?: number
}

export interface DeviceSettingsDocument {
  schemaVersion: 1
  updatedAt: string
  devices: {
    smartPlug: SmartPlugSettings
    lights: LightsSettings
    thermostat: ThermostatSettings
  }
}
