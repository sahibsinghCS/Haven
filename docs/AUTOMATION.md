# Room automation (hackathon demo)

RoomOS can trigger **real** automations when inferred state is stable. Defaults are safe: **no outbound calls** until you opt in.

## Safety gates (both required for real HA calls)

| Setting | Default | Meaning |
|---------|---------|---------|
| `actions.dry_run` | `true` | When true, handlers log only — no HTTP |
| `integrations.home_assistant.enabled` | `false` | Second gate for Home Assistant |

Generic `webhook` rules only check `dry_run`.

For **direct Kasa plugs** (HS103, EP25, KP125M, …), both `dry_run: false` and `integrations.kasa.enabled: true` are required.

## Integration paths

### 0. Direct Kasa plug (no Home Assistant)

Control a TP-Link Kasa smart plug from RoomOS over your LAN (`python-kasa`). Good for **HS103** and similar Wi‑Fi plugs.

1. Set up the plug in the **Kasa Smart** app (2.4 GHz Wi‑Fi).
2. Find the plug IP (router device list) or scan:

   ```bash
   npm run kasa:probe
   ```

3. In `backend/.env`:

   ```env
   ROOMOS_ACTIONS_CONFIG=configs/actions.kasa.yaml
   KASA_PLUG_HOST=192.168.1.50
   ```

   Newer firmware may need TP-Link cloud login:

   ```env
   KASA_USERNAME=you@example.com
   KASA_PASSWORD=your_password
   ```

4. In `backend/configs/actions.yaml`, set `enabled: true` on `sleep_fan_kasa` and `work_fan_off_kasa`.
5. `pip install python-kasa` (or re-run `npm run setup:venv`), then `npm run demo`.

Test manually:

```bash
npm run kasa:on
npm run kasa:off
```

Rules use `action.type: kasa` with `state: on` or `off` when activity is sleep / work.

### 1. Home Assistant webhook (recommended)

1. In Home Assistant: **Settings → Automations → Create automation**
2. Trigger: **Webhook**, Webhook ID: `roomos_work` (match YAML)
3. Action: your scene (e.g. `scene.turn_on` for office focus)
4. In `backend/configs/actions.yaml`:
   - `integrations.home_assistant.enabled: true`
   - `actions.dry_run: false`
   - Enable rule `focus_mode_ha` (`enabled: true`)
5. Set `integrations.home_assistant.base_url` to your HA URL (e.g. `http://homeassistant.local:8123`)

RoomOS POSTs JSON:

```json
{
  "source": "roomos",
  "rule": "focus_mode_ha",
  "activity": "work",
  "confidence": 0.82,
  "at": "2026-05-21T12:00:00+00:00",
  "scene": "focus"
}
```

Use `trigger.json.activity` / `trigger.json.rule` in HA templates.

### 2. Home Assistant REST service (optional)

For `mode: service` rules, set a long-lived token:

```yaml
integrations:
  home_assistant:
    enabled: true
    token_env: HOME_ASSISTANT_TOKEN
```

```bash
export HOME_ASSISTANT_TOKEN=your_long_lived_token
```

Rule example:

```yaml
action:
  type: home_assistant
  mode: service
  domain: scene
  service: turn_on
  entity_id: scene.office_focus
```

### 3. Local webhook demo (no HA)

**Terminal A:**

```bash
npm run demo:receiver
```

**Terminal B** (from repo root):

```bash
# Windows PowerShell
$env:ROOMOS_ACTIONS_CONFIG="configs/actions.demo-local.yaml"
npm run demo

# macOS/Linux
export ROOMOS_ACTIONS_CONFIG=configs/actions.demo-local.yaml
npm run demo
```

Hold **work** / **sleep** state on `/live` — receiver terminal prints POST payloads.

## Logs and UI

- API logs: `[rule] home_assistant webhook -> ... status=200`
- Event log: `backend/data/events/actions.jsonl`
- Live UI: **Room automation** chip on `/live` (`automationMode`: `dry_run` | `live` | `off`)

## Fallback when integration is unavailable

- **Default `actions.yaml`:** log-only rules always run; HA/webhook rules disabled.
- **Webhook/HA errors:** logged as `FAILED`; inference continues; UI shows failed summary.
- **Receiver not running:** webhook rules log connection errors; use `demo:receiver` or re-enable `dry_run: true`.

## Config example (Home Assistant)

```yaml
actions:
  dry_run: false
  integrations:
    home_assistant:
      enabled: true
      base_url: "http://192.168.1.50:8123"
      verify_ssl: false
  rules:
    - name: focus_mode_ha
      enabled: true
      when:
        activity: work
        min_confidence: 0.6
        sustain_windows: 1
      action:
        type: home_assistant
        mode: webhook
        webhook_id: roomos_work
      cooldown_sec: 180
```

Point the API at a config file via `ROOMOS_ACTIONS_CONFIG` in `backend/.env`.
