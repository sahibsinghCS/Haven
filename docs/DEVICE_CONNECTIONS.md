# Connecting devices in HAVEN

Settings (`/settings`) is where you link **physical devices**. Preferences define comfort targets per mood; Settings defines **which brands and devices** HAVEN talks to.

## How connections work

| Method | Best for | What you do |
|--------|----------|-------------|
| **Local Wi‑Fi** | Many plugs (Kasa, Shelly, Meross), some bulbs (LIFX, Yeelight) | Same router as HAVEN; find the device IP in your router or app; optional “local control” in the brand app |
| **Brand hub** | Philips Hue | Hue Bridge on Ethernet; bulbs paired in the Hue app |
| **Cloud account** | Nest, ecobee, Honeywell Home, Wyze, Govee | Sign in with the same account as the manufacturer app (rolling out per brand) |
| **Matter** | Matter bulbs/switches | Commission in Apple Home, Google Home, or Alexa first; HAVEN links through supported controllers |

You do **not** need a separate home-automation server for many devices. HAVEN prefers **local control on your LAN** when the device supports it (faster, works if the internet blips).

## Smart plugs (Settings → Test connection)

| Brand | How HAVEN connects |
|-------|-------------------|
| TP-Link Kasa / Tapo | Local IP (`python-kasa`) |
| Tuya / Smart Life | Device ID + local key + IP (`tinytuya`) |
| Shelly | Local HTTP (Gen 1 or Gen 2) |
| Wemo | Local IP (`pywemo`) |
| Meross | Meross app email + password (cloud) |
| Wyze, Amazon | Not supported for direct control yet |

**Fan tip:** A plug only supplies power. Leave the fan’s physical speed on “on” so it restarts after the plug energizes.

## Lights

| Brand | Typical connection |
|-------|-------------------|
| Philips Hue | Hue Bridge on LAN |
| LIFX, WiZ, Yeelight | Wi‑Fi; enable LAN/local in app if offered |
| Govee, Tuya / Smart Life | Often cloud; some models expose a local key |
| Matter | Via your phone’s Matter controller |

Note **room and scene names** from the brand app in Settings so mood automations can target them.

## Thermostats (Settings → Test thermostat)

| Brand | How HAVEN connects |
|-------|-------------------|
| Honeywell Home / Total Connect | Same username + password as the Honeywell app (`somecomfort`) |
| ecobee | API key + refresh token from developer.ecobee.com |
| Google Nest | Device Access project ID + OAuth client ID/secret + refresh token |
| Sensi, Amazon | Coming soon |

Heat and cool limits should stay within what you already set in the thermostat app.

## Saving settings

- With the app running: saved to `backend/data/integrations.json`
- Offline: saved in the browser until the API is back

Enable **Use in automations** on each device card, save, then use **Test**.

### Automatic control when mood changes

When HAVEN detects a **new room state** (sleep → work, etc.), it reads that state’s row from **Preferences** and:

- **Fan** preference → smart plug on/off  
- **Temperature** → thermostat setpoint (heat; cool = heat + 2°F)  
- **Brightness** → lights (Tuya bulbs today; other brands logged until added)

Set `dry_run: false` in actions config (`ROOMOS_ACTIONS_CONFIG=configs/actions.live-devices.yaml`) so changes are real, not simulated.
