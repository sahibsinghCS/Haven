/**
 * Consumer-facing setup paths for common Wi‑Fi plugs, lights, and thermostats.
 * RoomOS uses your home network (LAN) or the manufacturer’s official cloud APIs where supported.
 */

export type DeviceCategory = "smart_plug" | "lights" | "thermostat"

export type ConnectionKind = "local_wifi" | "cloud_account" | "hub_bridge" | "matter"

export interface SetupTroubleshootItem {
  problem: string
  fix: string
}

export interface DeviceSetupGuide {
  id: string
  label: string
  connectionKind: ConnectionKind
  /** One line for the brand picker */
  tagline: string
  prerequisites: string[]
  steps: string[]
  /** Shown when RoomOS can test/control this brand today */
  supportsDirectControl?: boolean
  /** Extra tip after steps */
  tip?: string
  /** Highlight a specific model (e.g. P110M) */
  featuredModel?: string
  /** Important callouts (firmware, third-party toggle, etc.) */
  warnings?: string[]
  troubleshooting?: SetupTroubleshootItem[]
  /** Short line for “no hub required” messaging */
  directControlNote?: string
}

export const CONNECTION_KIND_LABELS: Record<ConnectionKind, string> = {
  local_wifi: "Same Wi‑Fi network (local)",
  cloud_account: "Manufacturer account (cloud)",
  hub_bridge: "Brand hub on your network",
  matter: "Matter / Thread",
}

export const CATEGORY_INTROS: Record<
  DeviceCategory,
  { title: string; paragraphs: string[] }
> = {
  smart_plug: {
    title: "Connect devices to HAVEN",
    paragraphs: [
      "HAVEN talks to your gear directly over home Wi‑Fi or the manufacturer’s cloud — no Home Assistant hub required.",
      "When Live detects a mood change, HAVEN applies that mood’s Preferences (fan on/off, lights, temperature). Connect each device once here, then tune comfort on the Preferences page.",
    ],
  },
  lights: {
    title: "Smart lights",
    paragraphs: [
      "Bulbs and light strips usually connect through the maker’s app (Philips Hue, LIFX, WiZ, etc.) or a small hub plugged into your router.",
      "HAVEN adjusts brightness and color temperature from your Preferences once lights are linked. Some brands need a one-time sign-in; others work on your LAN without leaving home.",
    ],
  },
  thermostat: {
    title: "Smart thermostats",
    paragraphs: [
      "Thermostats often use Wi‑Fi plus a cloud account (Nest, Ecobee, Honeywell Home) so you can set heat and cool from your phone.",
      "HAVEN applies comfort targets from each mood (sleep cooler, work warmer). You’ll sign in with the same account you use in the thermostat app, or use a local API if your model supports it.",
    ],
  },
}

export const SMART_PLUG_GUIDES: DeviceSetupGuide[] = [
  {
    id: "tplink_kasa",
    label: "TP-Link Kasa",
    connectionKind: "local_wifi",
    tagline: "HS103, KP115, and classic Kasa plugs",
    supportsDirectControl: true,
    prerequisites: [
      "Plug is set up in the Kasa app and online.",
      "PC running HAVEN is on the same Wi‑Fi (or Ethernet on the same router).",
    ],
    steps: [
      "In the Kasa app, open the plug and note its name (e.g. “Fan”).",
      "On your phone or laptop, open your router’s admin page (often 192.168.1.1) → Connected devices, and find the plug’s IP address.",
      "Enter that IP below and use Test connection. The plug should click on.",
      "If the plug doesn’t respond, in Kasa go to Me → Settings → Third-Party Compatibility and turn on local control if shown.",
    ],
    tip: "Fans on a plug only run when power is on — many fans need you to leave the physical switch on “high” so they start after power returns.",
  },
  {
    id: "tuya",
    label: "Tuya / Smart Life",
    connectionKind: "local_wifi",
    tagline: "Gosund, Teckin, and many budget Wi‑Fi plugs",
    supportsDirectControl: true,
    prerequisites: [
      "Plug set up in the Smart Life or Tuya Smart app.",
      "PC running HAVEN on the same Wi‑Fi.",
    ],
    steps: [
      "Install tinytuya once: pip install tinytuya (included with HAVEN backend).",
      "Run python -m tinytuya wizard and sign in with the same Tuya account as the app.",
      "Copy Device ID, Local Key, and IP into the fields below (protocol version is usually 3.3).",
      "Tap Test connection — the plug should turn on.",
    ],
    tip: "If control fails after a factory reset, run the wizard again — the local key changes when you re-add the device.",
  },
  {
    id: "tapo",
    label: "TP-Link Tapo",
    connectionKind: "local_wifi",
    tagline: "P110M energy monitor, P110, P105, P100",
    featuredModel: "Tapo P110M",
    supportsDirectControl: true,
    directControlNote:
      "Direct LAN control from this PC — you do not need Home Assistant, Alexa, or a separate hub.",
    prerequisites: [
      "Plug paired in the Tapo app and toggles on/off from your phone.",
      "Phone and this computer on the same home Wi‑Fi (2.4 GHz during setup is most reliable).",
      "Tapo account email + password (same login as the Tapo mobile app).",
    ],
    warnings: [
      "Firmware 1.4.1 or newer: in the Tapo app open Me → Voice Assistant → Third-Party Compatibility and turn it ON. Without this, local control from HAVEN may fail with an auth error.",
      "Close the Tapo desktop client on your PC while testing if you use it — only one local connection to the plug is allowed at a time.",
    ],
    steps: [
      "In the Tapo app, add the P110M and confirm you can turn it on/off from your phone.",
      "Enable Third-Party Compatibility (Me → Voice Assistant) if your firmware is recent.",
      "Find the plug’s IP: Tapo app → your plug → Settings (gear) → Device Info → IP Address. Or check your router’s connected-devices list for a device named TAPO or your plug label.",
      "Enter your Tapo account email and password below (HAVEN uses the same secure local protocol as other Tapo tools — credentials stay on this machine).",
      "Paste the IP address, pick a name (e.g. “Fan”), and tap Connect & test plug. You should hear a click and see the plug turn on.",
      "Turn on Mood automations on this card, then open Preferences to choose when the fan runs for each mood.",
    ],
    tip: "P110M also supports Matter — you can use Matter with Apple/Google Home separately. For HAVEN, use the Tapo Wi‑Fi path above (fastest, includes energy monitoring later).",
    troubleshooting: [
      {
        problem: "“Device response did not match our challenge” (even with correct email/password)",
        fix:
          "This is a Tapo firmware handshake issue, not always a typo. In the Tapo app: Me → Tapo Lab (or Voice Assistant) → Third-Party Compatibility → ON — toggle OFF, wait 10s, ON again. Close the Tapo PC app. If it still fails: unplug all other TP-Link/Tapo devices, factory-reset the plug, enable Third-Party Compatibility, then add only this plug in Tapo.",
      },
      {
        problem: "Authentication failed or 403 error",
        fix: "Double-check Tapo email/password. Enable Third-Party Compatibility in the Tapo app. Update plug firmware in the app if offered.",
      },
      {
        problem: "Cannot reach plug / timeout",
        fix: "Confirm the IP is correct and the plug is online in Tapo. This PC must be on the same LAN (not guest Wi‑Fi).",
      },
      {
        problem: "Plug is busy or unavailable",
        fix: "Quit the Tapo PC client or any other app controlling the plug, wait 10 seconds, and test again.",
      },
      {
        problem: "Test works but Live does not control the plug",
        fix: "Enable Mood automations here, set fan on/off in Preferences, and ensure actions run for real (ROOMOS_ACTIONS_CONFIG=configs/actions.live-devices.yaml).",
      },
    ],
  },
  {
    id: "meross",
    label: "Meross",
    connectionKind: "cloud_account",
    tagline: "MSS110 and similar",
    supportsDirectControl: true,
    prerequisites: ["Meross app account.", "Plug online in the Meross app."],
    steps: [
      "Enter the same email and password you use in the Meross app below.",
      "Use the device name field to match your plug if you have more than one.",
      "Tap Test connection — HAVEN signs in to Meross cloud and toggles the plug.",
    ],
  },
  {
    id: "wyze",
    label: "Wyze Plug",
    connectionKind: "cloud_account",
    tagline: "Wyze Plug / Outdoor Plug",
    prerequisites: ["Wyze account and plug paired in the Wyze app."],
    steps: [
      "Keep the plug online in the Wyze app.",
      "Wyze devices are usually controlled through Wyze’s cloud. HAVEN will link via your Wyze account in a future update.",
      "For now, note the plug name below so automations can target it once cloud linking is enabled.",
    ],
  },
  {
    id: "shelly",
    label: "Shelly",
    connectionKind: "local_wifi",
    tagline: "Shelly Plug, Plug S, etc.",
    supportsDirectControl: true,
    prerequisites: ["Shelly app or web UI configured.", "Same LAN as HAVEN."],
    steps: [
      "Open the Shelly device page in the app and find its IP (or use Shelly’s discovery).",
      "Enter the IP below. Pick Gen 2 if your plug uses the newer Shelly app only.",
      "Tap Test connection.",
    ],
  },
  {
    id: "wemo",
    label: "Wemo",
    connectionKind: "local_wifi",
    tagline: "Wemo Mini Smart Plug",
    supportsDirectControl: true,
    prerequisites: ["Set up in the Wemo app.", "Same Wi‑Fi network."],
    steps: [
      "Confirm the plug works from the Wemo app.",
      "Find its IP on your router’s connected-device list.",
      "Enter the IP below and tap Test connection.",
    ],
  },
  {
    id: "amazon",
    label: "Amazon Smart Plug",
    connectionKind: "cloud_account",
    tagline: "Amazon Smart Plug",
    prerequisites: ["Configured in the Alexa app."],
    steps: [
      "Amazon’s plug is designed for Alexa and does not expose a simple local IP for third-party apps.",
      "Use the plug with Alexa routines today, or choose a plug with local control (Kasa, Shelly, Meross) for direct HAVEN control.",
      "Note your plug name below for reference.",
    ],
  },
  {
    id: "other_plug",
    label: "Other brand",
    connectionKind: "local_wifi",
    tagline: "IKEA, Gosund, Tuya-based, etc.",
    prerequisites: ["Device works in its manufacturer app.", "Same Wi‑Fi as HAVEN when possible."],
    steps: [
      "Check the app for “local control”, “LAN control”, or “third-party” options and turn them on if available.",
      "Look up whether your model has a fixed IP on the router.",
      "Enter any IP or notes below so you can finish wiring when HAVEN adds your brand.",
    ],
  },
]

export const LIGHTS_GUIDES: DeviceSetupGuide[] = [
  {
    id: "none",
    label: "Not connected",
    connectionKind: "local_wifi",
    tagline: "Skip lights for now",
    prerequisites: [],
    steps: ["You can connect lights later from this page."],
  },
  {
    id: "philips_hue",
    label: "Philips Hue",
    connectionKind: "hub_bridge",
    tagline: "Bulbs with Hue Bridge",
    prerequisites: ["Hue Bridge powered and on Ethernet to your router.", "Bulbs paired in the Hue app."],
    steps: [
      "Install bulbs and add them to a room in the Philips Hue app.",
      "Press the bridge button when the app asks during pairing.",
      "HAVEN will connect to your Hue Bridge on the LAN (bridge IP from your router) or via Philips’ cloud sign-in — pick the path shown when linking is available.",
      "Note room and scene names you want for sleep vs work below.",
    ],
  },
  {
    id: "lifx",
    label: "LIFX",
    connectionKind: "local_wifi",
    tagline: "Wi‑Fi bulbs, no hub",
    prerequisites: ["Bulbs set up in the LIFX app.", "Same network as HAVEN."],
    steps: [
      "Confirm each bulb is online in the LIFX app.",
      "LIFX bulbs can be discovered on your Wi‑Fi; HAVEN will use local LAN control where supported.",
      "Note bulb names (e.g. “Desk”) below for mood scenes.",
    ],
  },
  {
    id: "wiz",
    label: "WiZ",
    connectionKind: "local_wifi",
    tagline: "WiZ Connected bulbs",
    prerequisites: ["WiZ app setup complete."],
    steps: [
      "Pair bulbs in the WiZ app and assign them to a room.",
      "Enable “Local connection” or equivalent in WiZ settings if offered.",
      "Note room names below for Preferences.",
    ],
  },
  {
    id: "yeelight",
    label: "Yeelight",
    connectionKind: "local_wifi",
    tagline: "Yeelight bulbs and strips",
    prerequisites: ["Yeelight app, same Wi‑Fi."],
    steps: [
      "In the Yeelight app, open device settings and enable LAN control if you see it.",
      "Find the bulb IP on your router if needed.",
      "Note device names for automations.",
    ],
  },
  {
    id: "govee",
    label: "Govee",
    connectionKind: "cloud_account",
    tagline: "Govee lights and strips",
    prerequisites: ["Govee Home app account."],
    steps: [
      "Add lights in the Govee Home app.",
      "Many Govee models use Bluetooth plus Wi‑Fi; keep the Wi‑Fi model online.",
      "HAVEN will link through Govee’s cloud API when enabled; note device names below.",
    ],
  },
  {
    id: "kasa_light",
    label: "TP-Link Kasa / Tapo lights",
    connectionKind: "local_wifi",
    tagline: "Kasa or Tapo smart bulbs",
    prerequisites: ["Configured in Kasa or Tapo app."],
    steps: [
      "Same network as HAVEN.",
      "Find bulb IP or use app grouping; note the room name below.",
    ],
  },
  {
    id: "tuya",
    label: "Tuya / Smart Life",
    connectionKind: "local_wifi",
    tagline: "Smart Life, Gosund, and many budget bulbs",
    supportsDirectControl: true,
    prerequisites: [
      "Bulb added in Smart Life or Tuya Smart app.",
      "HAVEN backend running on the same Wi‑Fi.",
    ],
    steps: [
      "Confirm the bulb toggles in the Smart Life app.",
      "On the HAVEN computer, run: python -m tinytuya wizard (sign in with your Tuya account).",
      "Copy Device ID, Local Key, and IP from the wizard output.",
      "Paste them below and tap Connect lights — the bulb should brighten.",
    ],
    tip: "After a factory reset you must run the wizard again — the local key changes.",
  },
  {
    id: "matter",
    label: "Matter",
    connectionKind: "matter",
    tagline: "Matter bulbs and switches",
    prerequisites: ["Matter device commissioned in your phone’s Home app, Google Home, or Alexa."],
    steps: [
      "Finish Matter pairing in the app that came with your ecosystem.",
      "Matter devices need a controller on your network; HAVEN will connect through supported Matter controllers as they are added.",
      "Note the room and device label below.",
    ],
  },
  {
    id: "nanoleaf",
    label: "Nanoleaf",
    connectionKind: "local_wifi",
    tagline: "Panels and bulbs",
    prerequisites: ["Nanoleaf app setup."],
    steps: [
      "Pair panels in the Nanoleaf app.",
      "Enable LAN/API access in Nanoleaf settings if available.",
      "Note layout or scene names for moods.",
    ],
  },
  {
    id: "other_lights",
    label: "Other",
    connectionKind: "local_wifi",
    tagline: "Any other smart light brand",
    prerequisites: ["Works in the manufacturer app."],
    steps: [
      "Look for LAN, local, or API options in the app or manual.",
      "Write the app name, room, and device labels in the notes field.",
    ],
  },
]

export const THERMOSTAT_GUIDES: DeviceSetupGuide[] = [
  {
    id: "none",
    label: "Not connected",
    connectionKind: "cloud_account",
    tagline: "Skip thermostat for now",
    prerequisites: [],
    steps: ["You can connect a thermostat later."],
  },
  {
    id: "nest",
    label: "Google Nest",
    connectionKind: "cloud_account",
    tagline: "Nest Thermostat",
    supportsDirectControl: true,
    prerequisites: [
      "Nest thermostat in the Google Home app.",
      "Google Device Access project (console.nest.google.com) with SDM API enabled.",
      "OAuth client + refresh token from Google Cloud.",
    ],
    steps: [
      "Create a project at console.nest.google.com and enable Device Access (one-time fee may apply).",
      "In Google Cloud, create OAuth credentials (Desktop app) and note Client ID and Secret.",
      "Authorize once to get a refresh token (OAuth playground or HAVEN helper script).",
      "Paste Project ID, Client ID, Client Secret, and Refresh Token below, then Test thermostat.",
    ],
    tip: "Nest does not use one API key — you need Project ID plus OAuth client credentials and a refresh token.",
  },
  {
    id: "ecobee",
    label: "ecobee",
    connectionKind: "cloud_account",
    tagline: "ecobee thermostats",
    supportsDirectControl: true,
    prerequisites: [
      "ecobee app account.",
      "Developer API key from developer.ecobee.com (free registration).",
    ],
    steps: [
      "Register an app at developer.ecobee.com and note your API key.",
      "Authorize once to get a refresh token (Pin flow on the developer portal).",
      "Paste API key and refresh token below, then Test connection with a heat setpoint.",
    ],
  },
  {
    id: "honeywell_home",
    label: "Honeywell Home",
    connectionKind: "cloud_account",
    tagline: "T6, T9, and Wi‑Fi thermostats",
    supportsDirectControl: true,
    prerequisites: ["Honeywell Home app account (US cloud)."],
    steps: [
      "Enter the same username and password you use in the Honeywell Home app.",
      "Set a test heat target (e.g. 70°F) and tap Test connection.",
      "HAVEN reads and updates your thermostat through Honeywell’s cloud.",
    ],
  },
  {
    id: "honeywell_tcc",
    label: "Honeywell Total Connect",
    connectionKind: "cloud_account",
    tagline: "Total Connect Comfort (mytotalconnectcomfort.com)",
    supportsDirectControl: true,
    prerequisites: ["Total Connect Comfort account."],
    steps: [
      "Use the same login as the Total Connect Comfort website.",
      "Enter username and password below, then Test connection.",
    ],
  },
  {
    id: "sensi",
    label: "Sensi (Emerson)",
    connectionKind: "cloud_account",
    tagline: "Sensi Wi‑Fi thermostats",
    prerequisites: ["Sensi app."],
    steps: [
      "Finish Wi‑Fi setup in the Sensi app.",
      "HAVEN will target Sensi’s cloud API when available.",
    ],
  },
  {
    id: "amazon",
    label: "Amazon Smart Thermostat",
    connectionKind: "cloud_account",
    tagline: "Amazon-branded thermostat",
    prerequisites: ["Alexa app."],
    steps: [
      "Set up in the Alexa app.",
      "Control is often via Alexa; note device name for future linking.",
    ],
  },
  {
    id: "tuya",
    label: "Tuya / Smart Life HVAC",
    connectionKind: "cloud_account",
    tagline: "Some Smart Life thermostats",
    prerequisites: ["Smart Life app."],
    steps: [
      "Add the thermostat in Smart Life.",
      "Note whether it’s heat-only or heat/cool in the notes field.",
    ],
  },
  {
    id: "other_thermostat",
    label: "Other",
    connectionKind: "cloud_account",
    tagline: "Carrier, Trane, etc.",
    prerequisites: ["Manufacturer app working."],
    steps: [
      "Check whether your brand offers a public API or IFTTT.",
      "Write brand, model, and app account email in notes so support can help wire it up.",
    ],
  },
]

export function getGuide(
  category: DeviceCategory,
  id: string,
): DeviceSetupGuide | undefined {
  const list =
    category === "smart_plug"
      ? SMART_PLUG_GUIDES
      : category === "lights"
        ? LIGHTS_GUIDES
        : THERMOSTAT_GUIDES
  return list.find((g) => g.id === id)
}

export function migrateLegacyProvider(
  category: DeviceCategory,
  legacy: string,
): string {
  if (legacy === "tuya") return category === "smart_plug" ? "tuya" : legacy
  if (legacy === "home_assistant" || legacy === "kasa") {
    if (category === "smart_plug") return "tplink_kasa"
    if (category === "lights" && legacy === "kasa") return "kasa_light"
    return "other_lights"
  }
  if (legacy === "matter") return "matter"
  if (legacy === "none") return category === "smart_plug" ? "tapo" : "none"
  if (legacy === "other") {
    return category === "smart_plug"
      ? "other_plug"
      : category === "lights"
        ? "other_lights"
        : "other_thermostat"
  }
  if (category === "smart_plug") return "other_plug"
  if (category === "lights") return "other_lights"
  if (category === "thermostat") return "other_thermostat"
  return legacy
}
