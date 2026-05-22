# Live hackathon demo

## One command (after setup)

```bash
npm run demo
```

Checks venv, npm deps, and `backend/data/models/latest/`, then starts:

- **Web:** http://127.0.0.1:3000/live  
- **API:** http://127.0.0.1:8000/api/health  

## Personal room model (recommended before judges)

```bash
npm run data:init
npm run data:capture-stills
npm run data:audit
npm run train:images
npm run train:verify
```

See [`DATA-COLLECTION.md`](DATA-COLLECTION.md).

## First-time setup

```bash
npm install
npm install --prefix web
cd backend && python -m venv .venv
# activate venv, then:
pip install -r requirements.txt
cd ..
npm run setup:model    # ~5–15 min; downloads OpenCLIP once
npm run demo
```

Or run `npm run setup` for a checklist (add `--install-deps` to auto-run root/web `npm install`).

## When the model is missing

`npm run demo` stops before starting servers and prints:

- which files are missing under `backend/data/models/latest/`
- `npm run setup:model` to train a demo bundle

If the API starts without a bundle (e.g. `npm run dev`), `/api/health` returns `"status": "degraded"` with `missing_artifacts` and the live engine returns the same guidance via `engine_error`.

## Other commands

| Command | Purpose |
|---------|---------|
| `npm run preflight` | Check only (no servers) |
| `npm run dev` | Web + API without preflight |
| `npm run train:verify` | Train/serve schema check |
| `npm run setup:model` | Synthetic demo training |

Works on Windows, macOS, and Linux (uses `backend/.venv` — no hardcoded `Scripts\\python.exe` in npm scripts).

## Optional: prove room automation (local webhook)

```bash
# Terminal 1
npm run demo:receiver

# Terminal 2 — point actions at local demo config (PowerShell)
$env:ROOMOS_ACTIONS_CONFIG="configs/actions.demo-local.yaml"
npm run demo
```

When state holds on **work** / **sleep**, Terminal 1 prints JSON POSTs. See [`AUTOMATION.md`](AUTOMATION.md) for Home Assistant.

## Judge demo path (~2 minutes)

1. **Start:** `npm run demo` → open **http://127.0.0.1:3000/live** (fullscreen if presenting).
2. **10-second read:** Top status chips (camera · model · updated · automations simulated). Hero shows **state + confidence %**. Right column: all-state bars, **room response** preset targets, **teach the room** buttons.
3. **Act out a state** (sit at desk = work, recline = relaxing, leave frame = away). Point at confidence and one “why” bullet.
4. **Correction:** Tap a wrong label under **Teach the room** — panel shows **What we learned** (before/after %, disk path). Hold the pose ~10s — **Room memory** line appears in rationale.
5. **Preferences (optional):** **Preferences** tab → change preset → return to Live; **room response** targets update.
6. **Honest labels:** “Automations simulated” = dry-run; “same camera as preview” = no fake browser webcam.
