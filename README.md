# HAVEN — Local Room Intelligence

*RoomOS is the engineering codebase for this hackathon build.*

**HAVEN** is a local-first room intelligence demo: your machine watches the room in short **multi-frame bursts**, estimates what you are probably doing (work, gaming, sleep, relaxing, away), maps that to **preference-driven scene targets** (light, fan, temperature), and lets you **correct mistakes** so similar moments improve over time—all without sending video to the cloud.

**Pitch & Devpost copy:** [`HACKATHON-PITCH.md`](HACKATHON-PITCH.md) · **Product goal (cold start vs your room):** [`docs/COLD-START.md`](docs/COLD-START.md) · **Operator docs:** [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md) · [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) · [`docs/`](docs/README.md)

---

## Try it on your laptop

Follow these steps **in order** on the machine you want to run the demo from. Everything stays on `127.0.0.1`—no cloud account required.

**Time:** ~10–15 minutes the first time (mostly Python deps). The **classifier is already trained and included in the repo**—you do not need to run training to try the demo.

### What you need

| Requirement | Notes |
|-------------|--------|
| **Git** | To clone the repo |
| **Node.js 18+** | `node --version` |
| **Python 3.11** | **Required.** On Windows use `py -3.11 --version`. Do **not** use Python 3.12+ for the backend venv—it breaks numpy/OpenCV wheels. |
| **A camera** | Built-in webcam **or** a phone on the same Wi‑Fi with [DroidCam](https://www.dev47apps.com/) (optional but great for demos) |
| **Disk + network** | ~2 GB free; OpenCLIP weights download once when live inference first runs |

**Camera tip:** Close Zoom, Teams, and the OS Camera app before starting HAVEN—they often lock the webcam and cause a black preview.

---

### Step 1 — Clone and open the repo

```bash
git clone <repo-url>
cd RoomOS
```

All commands below are run from this **repo root** folder (the one that contains `package.json`).

---

### Step 2 — Install JavaScript dependencies

```bash
npm install
npm install --prefix web
```

You should end up with `node_modules/` at the root and in `web/`.

---

### Step 3 — Create the Python environment (3.11)

**Use the project script** (recommended on Windows):

```bash
npm run setup:venv
```

This creates `backend/.venv` with Python **3.11** and installs `backend/requirements.txt`.

<details>
<summary>Windows: install Python 3.11 if <code>setup:venv</code> fails</summary>

1. Download [Python 3.11](https://www.python.org/downloads/release/python-3119/) and check **“Add python.exe to PATH”** during install.
2. Verify: `py -3.11 --version` → `Python 3.11.x`
3. Run `npm run setup:venv` again.

**Do not** run bare `python -m venv` on Windows unless `python --version` is already 3.11.x.
</details>

<details>
<summary>macOS / Linux</summary>

Install Python 3.11 via your package manager or [python.org](https://www.python.org/downloads/), then:

```bash
npm run setup:venv
```
</details>

---

### Step 4 — Start the app (model installs automatically)

The repo includes a **pre-trained multi-room classifier** under `backend/shipped_models/multi_room_v2/` (trained on public room photos—not synthetic placeholders).

When you run the demo, preflight **copies that bundle** into `backend/data/models/latest/` on first launch. No training step required.

```bash
npm run demo
```

Optional one-time check (recommended):

```bash
npm run train:verify
```

This confirms the shipped model matches live inference config. If it fails, see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) → “Config mismatch”.

`npm run demo` starts:

| Service | URL |
|---------|-----|
| **Web UI** | http://127.0.0.1:3000 |
| **Live view** | http://127.0.0.1:3000/live |
| **API health** | http://127.0.0.1:8000/api/health |

Leave this terminal open. Stop with **Ctrl+C**.

**First burst:** After you connect a camera, the first inference burst can take **15–30 seconds** while OpenCLIP loads. Status chips on `/live` show progress.

Optional: copy `backend/.env.example` → `backend/.env` if you need custom ports or autostart behavior.

<details>
<summary>Advanced: re-install or replace the model</summary>

| Goal | Command |
|------|---------|
| Re-copy shipped bundle | `npm run setup:shipped-model` |
| Train synthetic bootstrap (weaker on real rooms) | `npm run setup:model` |
| Train on your own room photos | `npm run train:images` — see [Training overview](#training-overview) |
</details>

---

### Step 5 — Connect your camera (in the UI)

Open **http://127.0.0.1:3000/live**. On first visit you should see the **setup wizard**.

1. **Room** — Confirm or create a room (e.g. “Main room”) and enable it.
2. **Camera** — Pick a video source from the dropdown (the app scans webcams and DroidCam on your LAN).
3. **Devices** — Optional; skip or add simulated devices.
4. **Start live camera** — Enables inference on the feed you selected.

#### Built-in webcam

- In the camera dropdown, choose something like **Webcam 0** / **USB camera**.
- If preview stays black, close other apps using the camera and try index **1** or **2** in the picker.
- You can also probe from the terminal: `npm run probe:cameras`

#### Phone camera (DroidCam)

1. Install **DroidCam** on your phone and the PC client (or use Wi‑Fi mode only).
2. Put phone and laptop on the **same Wi‑Fi**.
3. Start DroidCam on the phone; note the IP (e.g. `192.168.1.18`).
4. In HAVEN’s camera dropdown, pick **DroidCam (auto)** (`droidcam:auto`) or the scanned HTTP entry.
5. If framing looks wrong, prefer the HTTP stream (matches the phone preview better). Advanced: set `video.source` in `backend/configs/inference.yaml` — see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) → “DroidCam / phone camera”.

The **same** camera stream drives both the on-screen preview and the classifier (backend OpenCV—not a separate browser webcam trick).

---

### Step 6 — Try what we built

Once preview is live and status chips show **Camera live** / model ready:

| Page | What to do |
|------|------------|
| **[/live](http://127.0.0.1:3000/live)** | Watch the hero state (work, gaming, sleep, …) update every few seconds. Read rationale bullets and confidence bars. |
| **[/preferences](http://127.0.0.1:3000/preferences)** | Edit mood presets; see how scene targets (light, fan, temp) change. |
| **Teach the room** | On `/live`, if the mood is wrong, tap a correction. Evidence saves under `backend/data/feedback/` and nudges similar bursts—**not** full XGBoost retraining until you run `train:images` again. |
| **Automations** | Chip **Automations simulated** is expected—rules log what would fire unless you wire Home Assistant ([`docs/AUTOMATION.md`](docs/AUTOMATION.md)). |

**Privacy line for demos:** “Video never leaves this laptop in this build.”

---

### No camera or flaky venue? Use demo replay

Same `/live` UI, clearly labeled **demo replay** (not live ML):

```bash
npm run demo:replay
```

Or toggle **Demo replay** on `/live` while the API is running. Details: [`docs/DEMO-REPLAY.md`](docs/DEMO-REPLAY.md).

---

### Every session after setup

```bash
npm run preflight    # optional quick check
npm run demo         # start web + API
```

Then open **http://127.0.0.1:3000/live**.

---

### Something broke?

| Symptom | First fix |
|---------|-----------|
| Preflight fails on venv | `npm run setup:venv` (see [TROUBLESHOOTING](TROUBLESHOOTING.md) → “Broken venv”) |
| Missing model | `npm run demo` copies the shipped bundle automatically; or `npm run setup:shipped-model` |
| Black / frozen preview | Close other camera apps; re-pick camera in setup wizard |
| “Cannot reach RoomOS API” | Confirm `npm run demo` terminal is still running; hit http://127.0.0.1:8000/api/health |
| Compat error on `/live` | `npm run train:verify`; `npm run setup:shipped-model` |

Full symptom index: [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) · presenter script: [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md)

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

## Training overview

The live path uses **`configs/train_personal.yaml`** and **`configs/inference.yaml`** with the **same feature modules** (default: CLIP + motion only). Training writes `backend/data/models/latest/`.

| Goal | Command | Data layout |
|------|---------|-------------|
| Try it out (included in clone) | Automatic on `npm run demo` / `npm run setup:shipped-model` |
| Fastest synthetic | `npm run setup:model` | Auto-generated demo stills |
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
- **Shipped model** — included in the repo; copied to `data/models/latest/` on first demo. Labels improve after **your** room data (`train:images`).
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
| [`backend/shipped_models/`](backend/shipped_models/multi_room_v2/README.md) | Pre-trained bundle (committed) |
| [`web/`](web/README.md) | Next.js demo UI |
| [`frontend/`](frontend/ARCHIVE.md) | **Archived** Vite scratch — do not run for demo |
| [`docs/`](docs/README.md) | Training, automation, compatibility, replay |
| [`scripts/`](scripts/) | Cross-platform `demo.mjs`, preflight, setup |

---

## Common commands

```bash
npm run demo              # Live demo (preflight + web + API)
npm run demo:replay       # Deterministic replay (no camera/model required)
npm run dev               # Web + API, skip preflight
npm run preflight         # Check deps + model only
npm run setup:shipped-model  # Install pre-trained classifier (recommended)
npm run setup:model       # Train synthetic bootstrap bundle
npm run setup:venv        # Python 3.11 venv + pip
npm run train:images      # Train from raw_images/
npm run train:verify      # Train/serve compatibility gate
npm run eval:report       # Refresh eval_report/ for judges
npm run probe:cameras     # List OpenCV / DroidCam sources
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
