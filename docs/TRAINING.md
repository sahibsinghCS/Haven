# RoomOS training guide (hackathon)

All commands assume a venv in `backend/.venv` and CWD either **repo root** (npm) or **`backend/`** (python).

## Install once

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
cd ..
npm install
```

## Collect data first (hackathon)

See **[`DATA-COLLECTION.md`](DATA-COLLECTION.md)** for 2h / 4h / 1-day plans, sample counts, and quality risks.

Quick path: `npm run data:init` → `npm run data:capture-stills` → `npm run data:audit` → `npm run train:images`

## Choose one path

| Path | When to use | One command |
|------|-------------|-------------|
| **C — Demo** | Fresh clone, judges, no camera data | `npm run train:demo` |
| **A — Images** | You have labeled photos per mood | `npm run train:images` |
| **B — Videos** | You recorded room clips per mood | `npm run train:videos` |

Unified CLI (same actions):

```powershell
cd backend
python scripts/train_roomos.py layout    # print folder layout
python scripts/train_roomos.py demo
python scripts/train_roomos.py images
python scripts/train_roomos.py videos
python scripts/train_roomos.py verify
```

## Path C — Demo model (no raw data)

```powershell
npm run train:demo
```

- Writes synthetic stills under `backend/data/demo_bootstrap/<label>/`
- Features → `backend/data/features/bootstrap_demo_features.csv`
- Model → **`backend/data/models/latest/`**
- Runs **train/serve compatibility check** automatically
- First run downloads OpenCLIP (~400MB)

## Path A — Personal still images

```text
backend/data/raw_images/
  work/*.jpg
  gaming/*.jpg
  sleep/*.jpg
  relaxing/*.jpg
  away/*.jpg
```

Need ~6 bursts per class by default (≈30 images with stride 5). Then:

```powershell
npm run train:images
```

Uses **`configs/train_personal.yaml`** (CLIP + motion only, same as live).

## Path B — Personal videos

```text
backend/data/raw/
  work/*.mp4
  gaming/*.mp4
  sleep/*.mp4
  relaxing/*.mp4
  away/*.mp4
```

Each file is treated as that label for its **full duration**. For mixed activities in one file, use the manual pipeline (capture → label windows → extract → train).

```powershell
npm run train:videos
```

Default: at least **1 video per class** (raise with `--min-videos-per-class 3` for better splits).

## Manual pipeline (advanced)

Use the **same config** for extract and train: `configs/train_personal.yaml`.

```powershell
cd backend

# 1. Capture
python scripts/capture_video.py -o data/raw/work/session01.mp4 --source 0 --duration 90

# 2. Label time ranges (optional if whole file is one class)
python scripts/label_windows.py data/raw/work/session01.mp4 -o data/labels/labels.csv

# 3. Extract burst features
python scripts/extract_features.py data/raw/work/session01.mp4 `
  --labels data/labels/labels.csv `
  --out data/features/session01.parquet `
  -c configs/train_personal.yaml

# 4. Train
python scripts/train_model.py -c configs/train_personal.yaml -f data/features/session01.parquet

# 5. Evaluate (optional)
python scripts/evaluate_model.py -b data/models/latest -f data/features/session01.parquet

# 6. Verify live compatibility
python scripts/verify_bundle.py -b data/models/latest
```

## Artifacts (`data/models/latest/`)

| File | Purpose |
|------|---------|
| `model.json` | XGBoost classifier |
| `label_encoder.json` | Class order |
| `feature_columns.json` | Schema for inference alignment |
| `train_config.json` | Config snapshot at train time |
| `metrics.json` | Train/val/test metrics |
| `eval_report/` | **Judge-ready report** — see [`EVALUATION.md`](EVALUATION.md) |
| `confusion_matrix.png` | Optional plot |
| `feature_importance.png` | Optional plot |

Live FastAPI reads `configs/inference.yaml` → `inference.model_dir` (default `data/models/latest`).

## Train/serve compatibility (automatic)

### At train time

After every training script, RoomOS checks the same rules and writes `data/models/latest/live_compat.json`.

### At live engine start (strict gate)

When the FastAPI engine starts (`ROOMOS_AUTOSTART` or `POST /api/live/start`), RoomOS **refuses to run** if the bundle does not match `configs/inference.yaml`.

Checked dimensions:

| Category | What is compared |
|----------|------------------|
| **Labels** | `label_encoder.json` class list/order vs `labels.classes` |
| **Feature modules** | `clip` / `pose` / `motion` / `posture` enabled flags |
| **CLIP prompts** | prompt list and order (column names) |
| **Motion grid** | `features.motion.grid` |
| **Burst** | `frame_count`, `duration_seconds`, `stride_seconds`, `sampling_strategy`, `min_collected_frames` |
| **Feature columns** | `feature_columns.json` vs columns live fusion produces |

Runtime **does not** silently switch to the train config for extraction — inference always uses `configs/inference.yaml`. The gate prevents starting with a mismatched bundle.

Failure surfaces in:

- API `GET /api/live/status` → `compat_report`, `engine_error`
- Live UI “Model not compatible with live inference” panel with mismatch bullets

Manual check:

```powershell
npm run train:verify
# or
cd backend && python scripts/verify_bundle.py
```

## npm scripts (repo root)

| Script | Action |
|--------|--------|
| `npm run train:demo` | Synthetic demo → `data/models/latest` |
| `npm run train:images` | `data/raw_images/` → model |
| `npm run train:videos` | `data/raw/<label>/` → model |
| `npm run train:verify` | Compatibility check only |
| `npm run eval:report` | Build `eval_report/` from trained bundle |
| `npm run capture` | Record webcam clip |
| `npm run pytest` | Backend tests |

## Assumptions & limits

- **`backend/data/` is gitignored** — every machine trains locally.
- **Demo/bootstrap models** are pipeline smoke tests, not room-accurate.
- **Pose/posture disabled** in personal + inference configs until MediaPipe path is stable on your OS.
- **Full-video labels** (Path B) are weak if one file contains multiple activities; use `label_windows.py` instead.
- **Class order** is fixed in `configs/default.yaml` labels.classes (must match UI).
- Retrain after changing `features.clip.prompts` or enabled flags.

## After training

```powershell
npm run dev
```

Open http://127.0.0.1:3000/live — engine autostarts if `ROOMOS_AUTOSTART=1`.
