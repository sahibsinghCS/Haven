# HAVEN / RoomOS — troubleshooting

Symptom-first fixes for operators and teammates. Presentation flow: [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md).

---

## How to diagnose in 60 seconds

```bash
npm run preflight
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/live/status
```

| Check | Good sign | Bad sign |
|-------|-----------|----------|
| Preflight | All green | Missing venv, npm, or model files |
| `/api/health` | `"status": "ok"` | `"degraded"`, connection refused |
| `/api/live/status` | `engine_running: true`, `live_mode: "live"` | `engine_error` set, `compat_ok: false` |
| `/live` UI | Status chips + updating burst # | “Cannot reach RoomOS API”, compat panel |

Open browser devtools → Network: requests to `127.0.0.1:8000` should succeed (not blocked CORS).

---

## Broken venv (Python 3.14 / numpy / pydantic_core)

### Symptoms

- `numpy._multiarray_umath.cp311-win_amd64` incompatible with **Python 3.14**
- `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`
- API crashes on startup; `npm run setup:model` fails on `import cv2` / `numpy`

### Cause

`backend/.venv` was created with **`python`** (3.14 on your machine) but packages were built for **3.11**, or a mixed upgrade left broken wheels.

### Fix (from repo root)

```powershell
cd C:\Users\SS\RoomOS
npm run setup:venv
npm run setup:model
npm run demo
```

`setup:venv` deletes the bad `.venv`, recreates it with **`py -3.11`**, and reinstalls `requirements.txt`.

**Do not use** bare `python -m venv .venv` on Windows unless `python --version` shows 3.11.x.

Verify:

```powershell
backend\.venv\Scripts\python.exe -c "import numpy, pydantic_core, fastapi; print('ok')"
backend\.venv\Scripts\python.exe --version
```

Should print `ok` and `Python 3.11.x`.

---

## Missing model

### Symptoms

- `npm run demo` exits before starting servers; preflight lists missing `model.json` / `label_encoder.json` / `feature_columns.json`
- `/live` says train a model / bundle missing
- `GET /api/health` → `"status": "degraded"`, `missing_artifacts` populated

### Fix

From **repo root**:

```bash
npm run setup:model
npm run train:verify
npm run demo
```

First run downloads **OpenCLIP** weights (~minutes, needs network once).

### Verify files exist

```text
backend/data/models/latest/
  model.json
  label_encoder.json
  feature_columns.json
  train_config.json   # recommended
```

### Still failing

- Run from repo root (`npm run …`), not only inside `backend/`
- Confirm `backend/.venv` exists and `pip install -r requirements.txt` completed
- Disk space; antivirus blocking writes under `data/`
- See backend train logs in terminal during `setup:model`

### Demo without a model

For **presentation only** (not live ML):

```bash
npm run demo:replay
```

Skips model preflight; uses `configs/demo_replay.json`. UI shows **Demo replay active**.

---

## Camera problems

### Symptoms

- Black or frozen preview on `/live`
- Chip stuck on **Camera waiting** / **Camera starting**
- `GET /api/live/preview.jpg` → 503
- States never update in **live** mode (replay mode is different—scripted)

### Fix (in order)

1. **Close other apps** using the webcam (Zoom, Teams, Windows Camera).
2. **Test OS camera** — confirm a device works at all.
3. **Set source index** in `backend/configs/default.yaml`:

   ```yaml
   video:
     source: 0   # try 1, 2 if 0 is wrong
   ```

4. **Restart stack:** Ctrl+C → `npm run demo`.
5. **Permissions (macOS):** grant Terminal/Cursor camera access.
6. **RTSP / file instead of webcam** (advanced):

   ```yaml
   video:
     source: "rtsp://..."
     # or: "/path/to/room.mp4"
   ```

7. Check `read_timeout_sec` if stream is slow (increase in `default.yaml`).

### Live vs replay

| Mode | Preview source |
|------|----------------|
| **Live camera** | OpenCV frames from `video.source` |
| **Demo replay** | Synthetic JPEG labeled “DEMO REPLAY” |

If replay works but live doesn’t → camera/model issue, not the UI.

### DroidCam / phone camera

Use documented source string, e.g. `droidcam:auto` or HTTP URL per [`backend/README.md`](backend/README.md). Same `video.source` drives preview and inference.

### Preview looks zoomed out vs DroidCam app

Virtual webcams often ship frames with **black letterbox bars**. Haven strips those automatically (`video.frame_preprocess.strip_letterbox` in `configs/inference.yaml`).

If framing still does not match the phone:

1. **Use the HTTP stream** (matches DroidCam Client preview more closely). Quit DroidCam Client, then in `configs/inference.yaml`:

   ```yaml
   video:
     source: "http://192.168.x.x:4747/video"
     backend: any
   ```

2. **Optional center crop** — uncomment `aspect_ratio: "16:9"` under `frame_preprocess`.

3. **Show full frame in UI** — set `video.preview.fit: contain` (may show bars on the sides).

4. Restart: Ctrl+C → `npm run dev`.

---

## Config mismatch (train / serve)

### Symptoms

- Engine fails to start; error mentions **compatibility** or **feature columns**
- `/api/live/status` → `compat_ok: false`, `compat_report.mismatches` non-empty
- `/live` shows compatibility failure panel

### Cause

Model was trained with different features/labels/burst settings than `configs/inference.yaml` uses live.

Default live stack: **CLIP + motion only** (`pose: false` in `inference.yaml`).

### Fix

```bash
npm run train:verify
```

If it fails:

```bash
# Retrain with the personal config that matches inference
npm run setup:model
# or, with your images:
npm run train:images
npm run train:verify
npm run demo
```

Do **not** hand-edit `feature_columns.json` to “match”—retrain.

Details: [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md).

### Label order

Bundle classes must match `configs/default.yaml` → `labels.classes` order (work, gaming, sleep, relaxing, away)—not alphabetical sklearn order. Retrain if you changed YAML labels.

---

## Action integration failure

### Symptoms

- Expected Home Assistant or webhook fires; nothing happens
- `/live` always shows **Automations simulated**
- Receiver terminal never prints POSTs

### Expected in default demo

**Dry-run is on by default.** No external devices are contacted. Chip **Automations simulated** is correct.

### To test local webhook

**Terminal 1:**

```bash
npm run demo:receiver
```

**Terminal 2 (PowerShell example):**

```powershell
$env:ROOMOS_ACTIONS_CONFIG="configs/actions.demo-local.yaml"
npm run demo
```

Hold a state (e.g. work) for several seconds; receiver should log JSON.

### Home Assistant

- Set `integrations.home_assistant.enabled: true` and `dry_run: false` in actions config
- Provide `HOME_ASSISTANT_TOKEN` in `backend/.env`
- See [`docs/AUTOMATION.md`](docs/AUTOMATION.md)

### Common mistakes

| Mistake | Result |
|---------|--------|
| Only `dry_run: false` but HA still disabled | No HA calls |
| Wrong webhook URL | HTTP errors in API logs |
| Firewall blocking localhost | Receiver never sees POST |
| Expecting actions in **demo replay** | Replay uses fixture automation text only |

Actions run from the **live** inference engine thread, not from demo replay fixtures (unless scripted in fixture JSON).

---

## Frontend / backend connection failure

### Symptoms

- `/live`: “Cannot reach RoomOS API”, WebSocket errors
- Network tab: `fetch` to `:8000` failed (ERR_CONNECTION_REFUSED)
- CORS errors in browser console

### Fix

1. **Confirm API is running** — terminal should show uvicorn on port 8000 after `npm run demo` or `npm run dev`.
2. **Hit health directly:** http://127.0.0.1:8000/api/health
3. **Use 127.0.0.1** in the browser, not only `localhost`, if the OS resolves them differently.
4. **Port conflict:** change `API_PORT` in `backend/.env`, restart; set `NEXT_PUBLIC_ROOMOS_API_BASE=http://127.0.0.1:NEW_PORT` in `web/.env.local`.
5. **Firewall:** allow Python/Node on private networks for localhost.
6. **Web not started:** `npm run demo` starts both; if you only ran API, also `npm run dev:web` from root.

### CORS

Allowed origins are in `backend/app/core/config.py` (`cors_allow_origins`). Default includes `http://127.0.0.1:3000` and `http://localhost:3000`. Add your origin if using a custom host.

### WebSocket

Live snapshots use `WS /api/live/ws` plus HTTP poll every 2s. If WS fails but poll works, UI may still update—check poll errors first.

### Environment variables (web)

| Variable | Default |
|----------|---------|
| `NEXT_PUBLIC_ROOMOS_API_BASE` | `http://127.0.0.1:8000` |
| `NEXT_PUBLIC_ROOMOS_WS_BASE` | derived from API base |

Rebuild/restart Next dev server after changing `.env.local`.

---

## Demo replay issues

### Symptoms

- No amber banner but expected replay
- Stuck on one state
- “Teach the room” does nothing

### Fix

- Start replay: `npm run demo:replay` or **Demo replay** on `/live`
- Confirm `/api/live/status` → `"live_mode": "replay"`, `"demo_mode": true`
- Edit timing/content: `backend/configs/demo_replay.json`
- Corrections **disabled** in replay by design—switch to **Live camera**

---

## OpenCLIP / first-run slowness

### Symptoms

- Long pause after engine start (~minutes)
- CPU high, first burst late

### Fix

- Run `npm run setup:model` once before judges; model + CLIP cached locally afterward
- Stay on power adapter
- Subsequent `npm run demo` starts faster

---

## Empty room shows "Work / Studying" (or another activity)

### Symptoms

- Camera shows **only furniture** (couch, bed, desk) with **no person** in frame
- `/live` UI still shows a primary state like **Work / Studying** or **Relaxing**
- This happens on the **bootstrap** model (default after `npm run setup:model`)

### Cause

The legacy **bootstrap** XGBoost is trained on synthetic flat-color stills and never saw clean "empty room" negatives. With `features.enabled.pose: false` (Windows DroidCam default) there is also no native presence signal in the feature vector, so the model latches onto room context (a desk == work, a couch == relaxing).

The repo now ships a **multi-room** model trained on ~1,750 photos from Open Images v7 / Wikimedia covering many real bedrooms, offices, gaming rooms, couches, and empty spaces. That model alone fixes the empty-couch case for most users — `away` test recall is ~0.85. Run it with:

```powershell
npm run train:multi-room
```

The occupancy gate below is still useful as a guardrail (especially when CLIP is uncertain), even with the multi-room model in place.

### Fix (already shipped — verify it is enabled)

The live pipeline runs an **occupancy gate** (`backend/roomos/inference/occupancy.py`) that uses existing CLIP + motion features to detect empty scenes and force `away`. It is enabled by default in `backend/configs/inference.yaml`:

```yaml
inference:
  occupancy:
    enabled: true
    empty_margin: 0.012          # generic "empty room" vs "a person" CLIP margin
    scene_empty_margin: 0.006    # empty couch / unoccupied desk (easier trigger)
    motion_max_for_empty: 0.028
    away_floor_prob: 0.82        # forced 'away' when scene is empty
    activity_prob_cap: 0.12      # caps Work/Relaxing/Sleep when no person in CLIP
```

The gate also reads the same CLIP prompts as training (`empty living room couch`, `unoccupied office desk`, etc.), not only the generic empty-room string.

To check it is actually firing on an empty couch:

```powershell
curl http://127.0.0.1:8000/api/live/status   # confirms engine_running + model_kind
# point camera at empty room for ~10s, then open /live; rationale should say:
# "Occupancy gate: no person in scene (empty couch/desk/room > person prompts, margin=+0.04) — not Work/Studying."
```

### If the gate is too aggressive (flips to `away` when you are present)

Raise the CLIP margin or lower the away floor:

```yaml
inference:
  occupancy:
    empty_margin: 0.025
    away_floor_prob: 0.65
```

### If the gate is too lax (still shows `work` on empty couch)

Lower the margin and raise the floor:

```yaml
inference:
  occupancy:
    empty_margin: 0.008
    scene_empty_margin: 0.004
    away_floor_prob: 0.88
    activity_prob_cap: 0.08
```

You can also temporarily disable the gate with `enabled: false` to confirm it is the cause.

### Long-term fix

Train a personal model with your own empty-room captures:

```powershell
# capture 6–12 empty stills into backend/data/base_images/away/ then:
npm run train:images
npm run train:verify
npm run demo
```

Details: [`docs/FEEDBACK.md`](docs/FEEDBACK.md) → "Empty-room / 'no person' gate".

---

## Preferences not saving

### Symptoms

- Changes lost on refresh
- Banner about API offline

### Fix

- Confirm `PUT /api/preferences` succeeds (Network tab)
- API stores `backend/data/preferences.json`
- Offline: UI may use browser backup—banner should say API offline
- See [`docs/PREFERENCES.md`](docs/PREFERENCES.md)

---

## pytest / dev tooling

```bash
npm run test:backend
cd web && npm run lint
cd web && npm run build
```

---

## Escalation path

| Level | Action |
|-------|--------|
| 1 | This doc + `npm run preflight` |
| 2 | [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md) fallback → `demo:replay` |
| 3 | Topic docs in [`docs/`](docs/README.md) |
| 4 | Logs: terminal uvicorn output, `backend/data/logs/` if enabled |

When reporting a bug, include: OS, `npm run preflight` output, `/api/live/status` JSON (redact tokens), and whether you were in **live** or **replay** mode.
