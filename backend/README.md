# RoomOS — local-first room activity recognition

Real-time room-activity recognition from a webcam / DroidCam / RTSP / video
file, served end-to-end on your machine. Perception uses pretrained OpenCLIP
(scene/context) and MediaPipe Pose (body). The trainable head is a **burst-level**
XGBoost classifier: each sample is a **short multi-frame burst** (default five
frames spread over ~2.5 s of stream time), not a dense continuous video model.
Predictions are smoothed across successive bursts, optionally trigger safe local
actions, and stream to the Next.js frontend via FastAPI.

```
camera → frame sampling → [ OpenCLIP + pose + motion + posture per frame ]
       → burst interval [t, t+duration] → subsample N frames → fuse → XGBoost
       → (live: repeat)   (file: stride between burst starts)
```

## Why burst-based (not full video modeling)

* **Local hardware friendly.** A small number of frames per decision keeps
  GPU/CPU cost bounded; there are no 3D CNNs, LSTMs, or video transformers.
* **Same modular perception stack.** Per-frame CLIP, pose, motion, and posture
  features are aggregated **across the burst only** into one tabular row.
* **Tabular = debuggable.** XGBoost feature columns are named
  (`clip_sim__…`, `posture_lying_ratio`, `motion_grid_07_std`, …).
* **Live = repeated bursts.** The live engine collects the next burst from
  the camera stream, classifies, smooths over time, then starts the next burst.
* **Files = many bursts.** Prerecorded video is scanned with
  `burst_stride_seconds` between burst start times (overlapping bursts when
  stride is shorter than duration).

## Layout

```
backend/
├── app/                     FastAPI app (transports the ML pipeline)
├── roomos/
│   ├── config.py
│   ├── video/               frame source, sampler, burst subsampling helpers
│   ├── features/            CLIP / pose / motion / posture / burst.py / fusion
│   ├── dataset/             schemas, burst feature extraction, labeling
│   ├── model/
│   ├── inference/           live burst loop, smoothing, overlays
│   ├── actions/
│   └── utils/
├── scripts/
├── configs/
├── data/
└── tests/
```

## Install

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
```

If `mediapipe` is unavailable, pose features zero out; heavy deps load lazily.

## End-to-end workflow (CWD = `backend/`)

### 1. Capture or import videos

```powershell
python scripts/capture_video.py --out data/raw/session_01.mp4 --source 0 --duration 60
```

### 2. (Optional) label time segments

```powershell
python scripts/label_windows.py data/raw/session_01.mp4 --out data/labels/labels.csv
```

Labels describe **wall-clock intervals** in the source file. Each **burst row**
overlaps `[start_time, end_time]`; the builder picks the best-overlapping
segment (see `label_for_burst` in `roomos/dataset/schemas.py`).

### 3. Extract burst-level features

```powershell
python scripts/extract_features.py data/raw/session_01.mp4 `
    --labels data/labels/labels.csv `
    --out data/features/features.parquet
```

Each row is **one burst** (after subsampling to `burst.frame_count` frames).
Metadata columns: `source`, `start_time`, `end_time`, `num_frames`, `burst_index`.

### 4. Train

```powershell
python scripts/train_model.py --config configs/train.yaml
```

Artifacts in `data/models/latest/` unchanged (`model.json`, `label_encoder.json`,
`feature_columns.json`, metrics, plots).

### Train from pictures instead of videos

Put still images into labeled folders:

```text
data/raw_images/work/*.jpg
data/raw_images/gaming/*.jpg
data/raw_images/sleep/*.jpg
data/raw_images/relaxing/*.jpg
data/raw_images/away/*.jpg
```

Then run:

```powershell
python scripts/train_personal_images.py
```

The script groups sorted images into 5-frame bursts by default. Each burst is
one training sample, matching live inference: RoomOS waits for five sampled
frames, fuses their OpenCLIP / pose / motion / posture features, then predicts.

### 5. Evaluate

```powershell
python scripts/evaluate_model.py `
    --bundle data/models/latest `
    --features data/features/features.parquet `
    --labels data/labels/labels.csv
```

### 6. Live inference (CLI)

```powershell
python scripts/run_live_inference.py --config configs/inference.yaml --show
```

Repeated burst capture → classify → temporal smoothing → optional actions.
Prediction log JSONL uses keys `burst_start`, `burst_end`, `burst_index`.

### 7. Serve to the frontend

```powershell
python run.py
```

`ROOMOS_AUTOSTART=1` or `POST /api/live/start`. Next.js: `web/src/hooks/use-live-inference.ts`.

## Burst configuration (`configs/default.yaml` → `burst:`)

| Key | Meaning |
| --- | --- |
| `frame_count` | Frames kept per burst after subsampling (e.g. 5) |
| `duration_seconds` | Wall-clock span to collect candidates (e.g. 2.5) |
| `sampling_strategy` | `uniform` or `endpoints` — how to pick `frame_count` indices |
| `stride_seconds` | Start-to-start spacing for the next burst (overlapping bursts when stride is shorter than duration) |
| `min_collected_frames` | Minimum raw samples in the interval before emitting |

Also tune `video.sample_fps` — higher gives more candidates inside each burst.

## Smoothing (`smoothing:`)

| Key | Meaning |
| --- | --- |
| `confirm_bursts` | Consecutive agreeing **burst** predictions before UI label switches |
| `confirm_windows` | **Legacy alias** — read only if `confirm_bursts` is absent |
| `prob_ema_alpha`, `min_confidence`, `cooldown_sec` | unchanged |

## Action engine

Rules still use `sustain_windows` (consecutive smoothed predictions). Evaluated
after each new burst classification.

## API surface

Unchanged — see previous docs for `/api/live/*` and `/api/preferences`.

## Tests

```powershell
cd backend
pytest -q
```

From the repo root you can also use the checked-in npm aliases:

```powershell
npm run python -- --version
npm run pytest
npm run import:base-images -- --target-total 50000
npm run train:images
npm run train:videos
```

These aliases use `backend/.venv/Scripts/python.exe`. If that virtualenv is
broken, reinstall Python 3.10-3.12, then recreate it:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Covers burst subsampling, `BurstAggregator`, burst-level fusion shapes, training
smoke test, smoothing (including legacy `confirm_windows` config), rule engine.

## Public/base image import

Public images can bootstrap the classifier, but they are weak labels. Keep them
separate from your room-specific images:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-data.txt
.\.venv\Scripts\python.exe scripts\import_base_images.py --target-total 50000
```

Output goes to `data/base_images/<label>/` with manifests in
`data/base_images/_manifests/`. The whole `data/` folder is gitignored.

Then train from the imported base images:

```powershell
.\.venv\Scripts\python.exe scripts\train_personal_images.py --images-dir data/base_images --min-bursts-per-class 20
```

For best accuracy, combine this with your own room images in `data/raw_images/`
and retrain on both or fine-tune by adding local examples to the same label
folders.

## Limitations

* Retrain after this refactor if old feature bundles used different `window.*`
  settings — config keys moved to `burst.*`.
* Very low `video.sample_fps` may yield too few frames per burst; lower
  `min_collected_frames` or raise `duration_seconds`.
