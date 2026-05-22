# Hackathon handoff (judges & teammates)

**Product:** HAVEN / RoomOS — local room-activity recognition + preference scenes.  
**Run this repo:** `backend/` (Python/FastAPI) + `web/` (Next.js). Ignore `frontend/` (archived Vite scratch).

**Canonical operator docs (repo root):** [`README.md`](../README.md) · [`DEMO_RUNBOOK.md`](../DEMO_RUNBOOK.md) · [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md)

---

## 60-second start

```bash
npm install && npm install --prefix web
cd backend && python -m venv .venv && pip install -r requirements.txt && cd ..
npm run setup:model    # once: trains demo model (~5–15 min)
npm run demo           # every session: http://127.0.0.1:3000/live
```

Preflight fails fast if the model or venv is missing. Details: [`DEMO.md`](DEMO.md).

---

## What is real vs marketing

| Claim | Truth |
|-------|--------|
| Live state on `/live` | Real XGBoost on backend OpenCV camera bursts |
| Video preview | Same camera as inference (`GET /api/live/preview.jpg`) — **not** browser webcam |
| API down | Empty/error UI — **no fake inference overlay** |
| Demo replay | Scripted states — **banner + `demo-replay` data source** ([`DEMO-REPLAY.md`](DEMO-REPLAY.md)) |
| Preferences | `PUT /api/preferences` + local browser backup if API offline (banner shown) |
| Teach the room | Stores burst evidence; nudges similar live bursts — **not full retrain** |
| Automations | Dry-run by default; HA/webhook only when explicitly enabled |
| Landing “cloud/hub” | Aspirational copy trimmed — demo is **local only** |
| Pose in pipeline | **Off** in live config (`configs/inference.yaml`: CLIP + motion) |
| Demo model | Synthetic bootstrap — say “pipeline demo” until `train:images` on your room |

---

## Judge demo path (~90s)

1. `npm run demo` → **/live**
2. Point at preview: “Backend camera, same frames as the classifier.”
3. Show state + % bars + one rationale line
4. **Teach the room** → correction saved on disk
5. **/preferences** → change preset → back to live → room response targets update
6. Offline metrics (optional): `data/models/latest/eval_report/REPORT.md` — see [`EVALUATION.md`](EVALUATION.md)

Full script: [`HACKATHON-SCOPE.md`](HACKATHON-SCOPE.md) §4.

---

## Doc map

| Doc | When to read |
|-----|----------------|
| [`DEMO.md`](DEMO.md) | Running the stack, preflight, ports |
| [`TRAINING.md`](TRAINING.md) | Personal images/videos → model |
| [`DATA-COLLECTION.md`](DATA-COLLECTION.md) | Capture stills, audit counts |
| [`EVALUATION.md`](EVALUATION.md) | Confusion matrix, per-class metrics, Q&A |
| [`COMPATIBILITY.md`](COMPATIBILITY.md) | Train/serve gate, label order |
| [`FEEDBACK.md`](FEEDBACK.md) | Corrections & personalization |
| [`PREFERENCES.md`](PREFERENCES.md) | Presets & `activePresetId` |
| [`AUTOMATION.md`](AUTOMATION.md) | Home Assistant / local webhook |
| [`HACKATHON-SCOPE.md`](HACKATHON-SCOPE.md) | Scope tiers, risks, API list |

---

## npm commands (canonical)

| Command | Purpose |
|---------|---------|
| `npm run demo` | Preflight + web + API |
| `npm run demo:replay` | **Deterministic replay** — no camera/model required ([`DEMO-REPLAY.md`](DEMO-REPLAY.md)) |
| `npm run dev` | Same stack, skip preflight |
| `npm run setup:model` | Train `data/models/latest/` (synthetic demo) |
| `npm run train:images` | Train from `data/raw_images/<label>/` |
| `npm run train:verify` | Bundle vs `inference.yaml` |
| `npm run eval:report` | Refresh `eval_report/` for judges |
| `npm run data:capture-stills` | Webcam stills into `data/raw_images/` |

`bootstrap:demo` is an alias for `setup:model`.

---

## Repo layout

```text
RoomOS/
├── backend/          # RoomOS Python, FastAPI, configs, scripts
├── web/              # Next.js UI (/ , /live, /preferences)
├── frontend/         # ARCHIVED Vite scratch — do not demo
├── docs/             # Handoff guides (this file + topic docs)
├── scripts/          # Cross-platform npm helpers (demo.mjs, …)
└── package.json      # npm run demo, train:*, data:*
```

Removed dead UI code is listed in [`web/src/_archive/README.md`](../web/src/_archive/README.md).
