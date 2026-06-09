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
  /** Tapo app account (P110M and newer plugs use KLAP — same login as the mobile app). */
  tapoEmail?: string
  tapoPassword?: string
}

export interface LightsSettings {
  enabled: boolean
  connected: boolean
  brand: LightsBrand
  notes: string
  host?: string
  label?: string
  tuyaDeviceId?: string
  tuyaLocalKey?: string
  tuyaVersion?: string
  /** Philips Hue local bridge application key (minted via the link button). */
  hueAppKey?: string
  /** Nanoleaf auth token (minted by holding the power button). */
  nanoleafToken?: string
  /** Govee cloud API key (LAN control uses host only). */
  goveeApiKey?: string
  /** Tapo/Kasa bulb login — same account as the mobile app (KLAP). */
  tapoEmail?: string
  tapoPassword?: string
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

export type DeviceInstance<T> = T & { id: string }

export type SmartPlugDevice = DeviceInstance<SmartPlugSettings>
export type LightsDevice = DeviceInstance<LightsSettings>
export type ThermostatDevice = DeviceInstance<ThermostatSettings>

export type DeviceCategoryKey = "smartPlugs" | "lights" | "thermostats"

export interface DeviceSettingsDocument {
  schemaVersion: 2
  updatedAt: string
  devices: {
    smartPlugs: SmartPlugDevice[]
    lights: LightsDevice[]
    thermostats: ThermostatDevice[]
  }
}
