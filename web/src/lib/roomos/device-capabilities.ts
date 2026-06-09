/**
 * Per-brand control capabilities — drives which preference fields appear.
 * Smart plugs are almost always relay (on/off only). Lights vary by ecosystem.
 */

import type { LightsBrand, SmartPlugBrand } from "@/types/device-settings"

export type DeviceCapabilities = {
  powerOnly: boolean
  brightness: boolean
  color: boolean
  temperature: boolean
}

const PLUG_CAPABILITIES: Record<SmartPlugBrand, DeviceCapabilities> = {
  tplink_kasa: { powerOnly: true, brightness: false, color: false, temperature: false },
  tapo: { powerOnly: true, brightness: false, color: false, temperature: false },
  tuya: { powerOnly: true, brightness: false, color: false, temperature: false },
  meross: { powerOnly: true, brightness: false, color: false, temperature: false },
  wyze: { powerOnly: true, brightness: false, color: false, temperature: false },
  shelly: { powerOnly: true, brightness: false, color: false, temperature: false },
  wemo: { powerOnly: true, brightness: false, color: false, temperature: false },
  amazon: { powerOnly: true, brightness: false, color: false, temperature: false },
  other_plug: { powerOnly: true, brightness: false, color: false, temperature: false },
}

const LIGHTS_CAPABILITIES: Record<LightsBrand, DeviceCapabilities> = {
  none: { powerOnly: false, brightness: false, color: false, temperature: false },
  philips_hue: { powerOnly: false, brightness: true, color: true, temperature: false },
  lifx: { powerOnly: false, brightness: true, color: true, temperature: false },
  wiz: { powerOnly: false, brightness: true, color: true, temperature: false },
  yeelight: { powerOnly: false, brightness: true, color: true, temperature: false },
  govee: { powerOnly: false, brightness: true, color: true, temperature: false },
  kasa_light: { powerOnly: false, brightness: true, color: false, temperature: false },
  tuya: { powerOnly: false, brightness: true, color: false, temperature: false },
  matter: { powerOnly: false, brightness: true, color: true, temperature: false },
  nanoleaf: { powerOnly: false, brightness: true, color: true, temperature: false },
  other_lights: { powerOnly: false, brightness: false, color: false, temperature: false },
}

export function smartPlugCapabilities(brand: SmartPlugBrand): DeviceCapabilities {
  return PLUG_CAPABILITIES[brand] ?? PLUG_CAPABILITIES.other_plug
}

export function lightsCapabilities(brand: LightsBrand): DeviceCapabilities {
  return LIGHTS_CAPABILITIES[brand] ?? LIGHTS_CAPABILITIES.other_lights
}

export function thermostatCapabilities(): DeviceCapabilities {
  return { powerOnly: false, brightness: false, color: false, temperature: true }
}
