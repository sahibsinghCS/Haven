# HAVEN / RoomOS — demo runbook

Use this during setup and on stage. Deep reference: [`README.md`](README.md) · fixes: [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)

---

## Exact startup order

### A. First machine setup (once per laptop)

Do this **before** the judging room, on the same machine you will present from.

| Step | Command / action | Done when |
|------|------------------|-----------|
| 1 | Clone repo, `cd RoomOS` | You are at repo root |
| 2 | `npm install && npm install --prefix web` | No npm errors |
| 3 | `npm run setup:venv` | `backend/.venv` with Python **3.11** (Windows-safe; do not use bare `python -m venv`) |
| 4 | `npm run demo` (or `npm run preflight` first) | Pre-trained model copies from `backend/shipped_models/multi_room_v2/` → `data/models/latest/` |
| 5 | `npm run train:verify` | Prints compatibility OK |
| 6 | Copy `backend/.env.example` → `backend/.env` (optional) | Ports/autostart as you want |
| 7 | Set camera in setup wizard on `/live` (or `configs/default.yaml`) | Webcam index or DroidCam |
| 8 | Confirm preview + state updates on `/live` | Within ~30s after camera connect |
| 9 | (Optional) Personal model: `data:init` → `capture-stills` → `train:images` → `train:verify` | Better labels for your room |

### B. Day-of demo (every session)

| Step | Command / action | Notes |
|------|------------------|-------|
| 1 | Close other apps using the webcam (Zoom, Teams, Camera app) | Prevents black preview |
| 2 | Plug in power; disable sleep on the laptop | — |
| 3 | Terminal at **repo root** | Not `backend/` alone |
| 4 | `npm run preflight` | Fix blockers before judges arrive |
| 5 | `npm run demo` | Waits for preflight, starts web :3000 + API :8000 |
| 6 | Browser: http://127.0.0.1:3000/live (fullscreen) | Not `localhost` if firewall is picky—use `127.0.0.1` |
| 7 | Confirm status chips: camera · model · updated | “Automations simulated” is expected |
| 8 | (Backup terminal ready) `npm run demo:replay` | Only if step 5 fails close to show time |

**Do not start** the archived `frontend/` Vite app—it is not wired to this API.

---

## Pre-demo checklist (5 minutes)

Print or skim this before walking on stage.

- [ ] `npm run preflight` passes (or you know you will use **demo replay**)
- [ ] `backend/data/models/latest/` has `model.json`, `label_encoder.json`, `feature_columns.json`
- [ ] Webcam works in OS camera app at the index in `configs/default.yaml` (`video.source`)
- [ ] `/live` shows **inference preview** (not only gradient background)
- [ ] Primary state changes when you change pose (or you will use **Demo replay** honestly)
- [ ] `GET http://127.0.0.1:8000/api/health` → `"status": "ok"` (or `"degraded"` with known reason)
- [ ] Browser zoom 100%; `/live` readable from 6 feet
- [ ] You know one sentence each for: privacy, accuracy, automation (below)
- [ ] Optional: `eval_report/REPORT.md` open for Q&A
- [ ] Optional: `demo:receiver` terminal if showing webhook automation

---

## 90-second demo script

**Tone:** calm, literal, no hype. Point at the UI while you talk.

| Time | Say | Do |
|------|-----|-----|
| 0–10s | “Everything runs on this laptop—no video upload.” | Show terminal with `npm run demo` or status chips on `/live`. |
| 10–20s | “This preview is the **same camera** the classifier uses—backend OpenCV, not a fake browser feed.” | Point at video + **Camera live** chip. |
| 20–35s | “Every few seconds we take a **burst** of five frames, fuse scene and motion features, and run a small **XGBoost** model.” | Show hero state + % bars + one rationale bullet. |
| 35–50s | “Preferences turn the mood into **concrete targets**—brightness, fan, temperature.” | Point at **room response** card. |
| 50–65s | “If it’s wrong, I **teach the room**—we store burst evidence locally and nudge similar moments. That’s not full retraining.” | Tap one correction; mention disk path in toast if it appears. |
| 65–80s | (Optional) Open **Preferences**, tweak a preset, return to Live. | Scene targets change. |
| 80–90s | “Automations are **simulated** in this build—rules log what would fire. We can wire Home Assistant when enabled.” | Point at **Automations simulated** chip. |

**One-liner close:** “Local burst classifier, explainable confidence, preferences, and honest correction memory—same UI path whether we’re on live camera or demo replay.”

---

## Fallback plan

Use in order. **Never** pretend replay is live inference.

| # | Symptom | Action | What to say |
|---|---------|--------|-------------|
| 1 | Black / frozen preview | Fix `video.source` (try `0`, `1`), close other camera apps, retry `npm run demo` | “Camera index was wrong—we’re on OpenCV index N.” |
| 2 | Engine won’t start (model) | `npm run setup:model` then `npm run train:verify` | “First run trains a small local model; takes a few minutes once.” |
| 3 | Compat error on `/live` | `npm run train:verify`; retrain with `train:images` or `setup:model` | “Train and live configs must match—we gate that on purpose.” |
| 4 | API unreachable | Confirm terminal running; hit http://127.0.0.1:8000/api/health | “UI only shows real API data—starting the backend.” |
| 5 | **Still broken near show time** | `npm run demo:replay` **or** on `/live` click **Demo replay** | “This is a **recorded walkthrough** on the same product UI so you still see the story; live mode uses the real classifier.” |
| 6 | Correction fails in replay | Switch **Live camera** (needs working model + camera) | “Corrections require live mode.” |

Amber banner **Demo replay active** must stay visible in replay mode—that’s intentional honesty.

---

## Judge Q&A — what to say

### Privacy

> “Video stays on this machine. The live path uses a local webcam through OpenCV; we don’t upload frames to a cloud service in this demo. Preferences and correction memory are stored under `backend/data/` on disk. There’s no account or hub required to run the hackathon build.”

If asked about landing “cloud” copy: “Marketing is forward-looking; **this build is local-first**.”

### Accuracy

> “Numbers in `eval_report` are on **held-out training bursts** from my room—or a synthetic bootstrap if we haven’t retrained yet—not a published benchmark. Live accuracy depends on lighting, camera angle, and whether the scene matches training photos. The UI shows **confidence and per-class bars** so low certainty is visible. Corrections improve **similar future bursts** via memory; retraining is `npm run train:images`.”

Show `backend/data/models/latest/eval_report/REPORT.md` or confusion matrix PNG if they want depth.

### Automation

> “By default everything is **dry-run**: the action engine logs what **would** happen—lights, fan, temperature targets from preferences—without calling smart-home APIs. You’ll see **Automations simulated** on `/live`. To hit a real webhook or Home Assistant you enable it in `actions.yaml` and set tokens in `.env`—we can show a local receiver in a second terminal for the hackathon.”

See [`docs/AUTOMATION.md`](docs/AUTOMATION.md).

### “Is this really AI?”

> “It’s a **practical stack**: pretrained OpenCLIP for scene context, hand-crafted motion features, and **XGBoost** on burst rows—not an end-to-end video transformer. That keeps it debuggable on a laptop and matches how we explain each prediction.”

### Demo replay vs live

> “Replay cycles a **scripted** work → gaming → relaxing → sleep → away sequence with an on-screen label **DEMO REPLAY**. Live mode runs the trained model on the camera. Same routes, same HUD—we label the source explicitly.”

---

## Post-demo shutdown

1. Ctrl+C in the terminal running `npm run demo`
2. Optional: `curl -X POST http://127.0.0.1:8000/api/live/stop` if API still up
3. Do not commit `backend/data/` or `.env` with secrets

---

## Quick reference

| Item | Value |
|------|--------|
| Live UI | http://127.0.0.1:3000/live |
| API health | http://127.0.0.1:8000/api/health |
| Camera config | `backend/configs/default.yaml` → `video.source` |
| Model bundle | `backend/data/models/latest/` |
| Replay fixture | `backend/configs/demo_replay.json` |
| Eval slide pack | `backend/data/models/latest/eval_report/` |
