# HAVEN — Local Room Intelligence

*RoomOS is the engineering codebase for this hackathon build.*

**HAVEN** is a local-first room intelligence demo: your machine watches the room in short **multi-frame bursts**, estimates what you are probably doing (work, gaming, sleep, relaxing, away), maps that to **preference-driven scene targets** (light, fan, temperature), and lets you **correct mistakes** so similar moments improve over time—all without sending video to the cloud.

**Pitch & Devpost copy:** [`HACKATHON-PITCH.md`](HACKATHON-PITCH.md) · **Operator docs:** [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md) · [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) · [`docs/`](docs/README.md)

---

## Architecture (30 seconds)

```text
┌─────────────┐     WebSocket + HTTP      ┌──────────────┐
│  web/       │ ◄──────────────────────► │  backend/    │
│  Next.js    │   /api/live/snapshot     │  FastAPI     │
│  /live      │   /api/live/preview.jpg  │              │
│  /preferences                          │  Live engine │
└─────────────┘                          │  (thread)    │
                                         └──────┬───────┘
                                                │
                    OpenCV camera ──► burst sampler (5 frames / ~2.5s)
                                                │
                    OpenCLIP (scene) + motion ──► fuse ──► XGBoost
                                                │
                    smooth ──► preferences ──► actions (dry-run default)
```

| Layer | Technology | Role |
|-------|------------|------|
| UI | Next.js (`web/`) | Live HUD, preferences, honest empty states |
| Transport | FastAPI | Snapshots, preview JPEG, prefs, feedback |
| Perception | OpenCLIP + motion | Tabular features per burst (pose off in default config) |
| Classifier | XGBoost | Five-class burst labels |
| Data | `backend/data/` (gitignored) | Model bundle, raw images, feedback memory |

**Not in this repo:** cloud accounts, multi-user auth, always-on upload, or guaranteed smart-home control (automations are **simulated by default**).

---

## Quick start

### First time (~15–20 minutes)

```bash
git clone <repo-url> && cd RoomOS
npm install && npm install --prefix web

cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cd ..

npm run setup:model    # synthetic demo model; downloads OpenCLIP once
npm run train:verify   # optional but recommended
```

### Every demo session

```bash
npm run demo
```

Open **http://127.0.0.1:3000/live** (UI) and **http://127.0.0.1:8000/api/health** (API).

Copy `backend/.env.example` → `backend/.env` if you need custom ports or autostart behavior.

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:3000/live | Live inference + preview |
| http://127.0.0.1:3000/preferences | Mood presets → scene targets |
| http://127.0.0.1:8000/api/health | API + model readiness |
| http://127.0.0.1:8000/api/live/status | Engine mode, compat, errors |

**Flaky camera or no model on the judge laptop?** `npm run demo:replay` — same `/live` UI, clearly labeled **demo replay** ([`docs/DEMO-REPLAY.md`](docs/DEMO-REPLAY.md)).

---

## Training overview

The live path uses **`configs/train_personal.yaml`** and **`configs/inference.yaml`** with the **same feature modules** (default: CLIP + motion only). Training writes `backend/data/models/latest/`.

| Goal | Command | Data layout |
|------|---------|-------------|
| Fastest (synthetic) | `npm run setup:model` | Auto-generated demo stills |
| Your room (recommended) | `npm run train:images` | `backend/data/raw_images/<label>/*.jpg` |
| From video | `npm run train:videos` | `backend/data/raw/<label>/*.mp4` |
| Verify train/serve | `npm run train:verify` | — |
| Judge metrics | `npm run eval:report` | `data/models/latest/eval_report/REPORT.md` |

**Collect personal stills:** `npm run data:init` → `npm run data:capture-stills` → `npm run data:audit` — see [`docs/DATA-COLLECTION.md`](docs/DATA-COLLECTION.md).

**Full pipeline:** [`docs/TRAINING.md`](docs/TRAINING.md) · **Evaluation / Q&A:** [`docs/EVALUATION.md`](docs/EVALUATION.md)

---

## Live demo overview

1. **One command:** `npm run demo` (preflight checks venv, deps, model).
2. **Same camera for ML and preview:** backend OpenCV → `GET /api/live/preview.jpg` (not the browser webcam).
3. **Real states** from `data/models/latest/` via WebSocket + 2s HTTP poll—no fake overlay when the API is down.
4. **Teach the room:** saves burst evidence under `data/feedback/`; nudges similar live bursts—**does not retrain XGBoost** until you run `train:images` again.
5. **Demo replay fallback:** toggle on `/live` or `npm run demo:replay`—prerecorded walkthrough, amber banner, `dataSource: demo-replay`.
6. **Automations:** dry-run logs only unless you opt into Home Assistant or a local webhook ([`docs/AUTOMATION.md`](docs/AUTOMATION.md)).

**Step-by-step script and judge talking points:** [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md)

---

## Limitations (say these out loud)

- **Personal, small data** — metrics on held-out **training bursts**, not a public benchmark or guaranteed live-session accuracy.
- **Burst classifier, not video AI** — five frames every ~2.5s; not continuous pose tracking in the default config.
- **Bootstrap model** — `setup:model` proves the pipeline; labels match synthetic scenes until you train on **your** room.
- **Corrections ≠ retrain** — memory steers similar bursts; offline metrics change only after retraining.
- **Automations** — “Automations simulated” on `/live` means **no devices contacted** unless explicitly configured.
- **Demo replay** — scripted states for presentation; **not** live camera inference (UI labels this clearly).
- **Local only** — no required cloud; landing copy is aspirational in places; the hackathon build runs on **127.0.0.1**.

---

## Repo layout

| Path | Use |
|------|-----|
| [`backend/`](backend/README.md) | Python ML + FastAPI |
| [`web/`](web/README.md) | Next.js demo UI |
| [`frontend/`](frontend/ARCHIVE.md) | **Archived** Vite scratch — do not run for demo |
| [`docs/`](docs/README.md) | Training, automation, compatibility, replay |
| [`scripts/`](scripts/) | Cross-platform `demo.mjs`, preflight, etc. |

---

## Common commands

```bash
npm run demo              # Live demo (preflight + web + API)
npm run demo:replay       # Deterministic replay (no camera/model required)
npm run dev               # Web + API, skip preflight
npm run preflight         # Check deps + model only
npm run setup:model       # Train synthetic bundle
npm run train:images      # Train from raw_images/
npm run train:verify      # Train/serve compatibility gate
npm run eval:report       # Refresh eval_report/ for judges
npm run test:backend      # pytest
```

---

## Documentation map

| Doc | Audience |
|-----|----------|
| [**DEMO_RUNBOOK.md**](DEMO_RUNBOOK.md) | Presenter — startup, 90s script, fallbacks |
| [**TROUBLESHOOTING.md**](TROUBLESHOOTING.md) | Operator — fixes when something breaks |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | Teammates / judges — truth table |
| [`docs/DEMO-REPLAY.md`](docs/DEMO-REPLAY.md) | Replay mode |
| [`docs/TRAINING.md`](docs/TRAINING.md) | Full training workflow |
| [`docs/EVALUATION.md`](docs/EVALUATION.md) | Metrics for Q&A |
| [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) | Train/serve gate |
| [`docs/AUTOMATION.md`](docs/AUTOMATION.md) | Home Assistant / webhook |
| [`docs/FEEDBACK.md`](docs/FEEDBACK.md) | Teach the room |
| [`docs/PREFERENCES.md`](docs/PREFERENCES.md) | Presets |

---

## License / hackathon note

Built for a **local, explainable** room-state demo. Extend with your own labeled data before claiming room-specific accuracy.
