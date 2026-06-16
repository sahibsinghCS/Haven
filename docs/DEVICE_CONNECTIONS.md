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

HAVEN controls lights **locally on your LAN** when the brand supports it. Open **Connections → Lights**, pick your brand, follow the step-by-step card, then **Connect lights**.

| Brand | How HAVEN connects | You need |
|-------|-------------------|----------|
| **Tuya / Smart Life** | `tinytuya` local API | Device ID + local key from `python -m tinytuya wizard` |
| **Philips Hue** | Hue Bridge REST (group 0) | Bridge IP + one-time link-button press |
| **LIFX** | UDP LAN protocol (port 56700) | Bulb IP (Scan my network) |
| **WiZ** | UDP JSON (port 38899) | Bulb IP (Scan my network) |
| **Yeelight** | TCP LAN (port 55443) | LAN Control ON in Yeelight app + bulb IP |
| **Govee** | UDP LAN API (ports 4001–4003) | LAN Control ON per device in Govee Home app + IP |
| **TP-Link Kasa / Tapo** | `python-kasa` | Bulb IP; Tapo bulbs also need app email/password |
| **Nanoleaf** | HTTP Open API (port 16021) | Controller IP + one-time power-button pairing |
| **Matter** | Coming soon | Commission in Apple/Google/Alexa first |
| **Other** | Notes only | Use Tuya path if the bulb is Smart Life inside |

**Scan my network** on the Connections page runs the same discovery Home Assistant uses (Kasa, WiZ, Yeelight SSDP, LIFX, Govee LAN, Hue bridge, Nanoleaf mDNS).

After connecting, enable **Use in automations** and set brightness/color in **Preferences** per mood.

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
- **Brightness** → lights (Tuya, Hue, LIFX, WiZ, Yeelight, Govee, Kasa/Tapo, Nanoleaf when connected)

Set `dry_run: false` in actions config (`ROOMOS_ACTIONS_CONFIG=configs/actions.live-devices.yaml`) so changes are real, not simulated.
