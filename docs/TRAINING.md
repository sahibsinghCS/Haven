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

**Main product goal:** generic model works in a **brand-new room** (~60%+ on held-out multi-room photos); **your room** is optional self-training — see **[`COLD-START.md`](COLD-START.md)**.

For **person vs away** (empty room must read as Away, not Work): see **[`DATA-COLLECTION.md` — Person vs away](DATA-COLLECTION.md#person-vs-away-nobody-in-the-room)**. Use `npm run train:multi-room` for many rooms/poses, then `npm run train:my-room` for your camera.

## Choose one path

| Path | When to use | One command |
|------|-------------|-------------|
| **C — Demo** | Fresh clone, judges, no camera data | `npm run train:demo` |
| **A — Images** | You have labeled photos per mood | `npm run train:images` |
| **B — Videos** | You recorded room clips per mood | `npm run train:videos` |
| **D — Multi-room** | Want a baseline classifier that has seen many real rooms before personalization | `npm run train:multi-room` |
| **E — My room (weighted)** | You have stills of *your* layout and want them to dominate generic rooms | `npm run train:my-room` |

### E — Your room weighted over generic data (recommended for `/live`)

After you capture stills with `npm run data:capture-stills`, train with **your**
photos at **12× row weight** and a **subsampled** multi-room prior at **1×**:

```powershell
npm run data:capture-stills
npm run train:my-room
```

This uses `configs/train_my_room.yaml`. Personal bursts from
`data/raw_images/<label>/` are tagged `dataset=personal_room`; optional rows from
`data/features/multi_room_features.parquet` are capped at ~22% of the row *count*
(but only 1× weight each), so the optimizer still sees generic rooms for
regularization without washing out your couch angle, lighting, and desk layout.

Flags:

| Flag | Effect |
|------|--------|
| `--personal-only` | Skip multi-room parquet entirely |
| `--personal-weight 16` | Override 12× default |
| `--multi-weight 1` | Generic prior weight |

`npm run train:images` also applies **12×** weights when `train_personal.yaml`
has `use_row_weights: true` (personal-only, no generic merge).

### D — Multi-room (recommended baseline)

The bundled bootstrap model is trained on synthetic flat-color stills and does
not generalize to real camera input. The **multi-room** path uses photos
already imported into `backend/data/base_images/<label>/` (originally from
Open Images v7 / Wikimedia / Zenodo via `scripts/import_base_images.py`) and
trains a model that has seen **many different rooms** per class.

```powershell
# 1. (Optional) bulk-augment your imported images to ~350/class
npm run train:expand-augs

# 2. Train. Each image becomes a single-image burst of 5 identical frames so
#    motion features are exactly zero and CLIP carries all the signal.
npm run train:multi-room
```

This is wired to `configs/train_multi_room.yaml` and writes the bundle into
`backend/data/models/latest`. The script enforces a minimum test accuracy of
**0.78** (the npm script raises 0.78 to 0.80 inside `train_multi_room.py`
when invoked directly via `--min-test-accuracy 0.80`).

Expected metrics on the shipped image set (~350 images × 5 classes, ~615
unique source clusters):

| Split | Accuracy | Macro F1 |
|-------|---------:|---------:|
| Train | ~0.97 | ~0.97 |
| Val | ~0.75 | ~0.77 |
| Test | **~0.80** | ~0.78 |

Per-class F1 (test split): `away` 0.89, `gaming` 0.89, `sleep` 0.87,
`work` 0.64, `relaxing` 0.58. The persistent weakness is the
`work` ↔ `relaxing` confusion (laptop on a couch could be either) —
fix this by personalizing on `/live` with the "Teach the room" button.

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

Mood lifecycle states (active, deleted, inference-eligible): [`MOODS-LIFECYCLE.md`](MOODS-LIFECYCLE.md).

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
