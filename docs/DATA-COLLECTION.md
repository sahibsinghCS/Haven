# Hackathon data collection (HAVEN / RoomOS)

Quality over volume. The live pipeline uses **5-frame bursts** (~2.5s) with CLIP + motion — your job is to supply **clear, single-activity** examples per class.

## Classes (fixed order)

| Label | Collect when… |
|-------|----------------|
| **work** | Desk, laptop, studying — upright, screen visible |
| **sleep** | In bed / lying down, lights low |
| **gaming** | Controller or intense play, not casual couch scroll |
| **relaxing** | Couch, reading, chill — not desk, not asleep |
| **away** | Empty room or you're out of frame |

Names must match folders exactly: `work`, `sleep`, `gaming`, `relaxing`, `away`.

---

## Highest-leverage path (recommended)

**Still images via webcam** → `npm run train:images`

Why: fastest labeling (folder = label), no timeline editor, matches burst stride, reproducible.

```bash
npm run data:init
npm run data:capture-stills    # SPACE to save, N next class, Q quit
npm run data:audit
npm run train:images
npm run train:verify
npm run demo
```

**Secondary path:** one **short video per class** (60–90s) → `npm run train:videos`

```bash
npm run data:capture-commands   # prints npm run capture ... lines
npm run train:videos
```

**Avoid for hackathon:** 50k public `base_images` import unless you only need a coarse pretrain — your room will still need `raw_images`.

---

## Folder structure

```
backend/data/
  raw_images/          # Path A — stills (preferred)
    work/*.jpg
    sleep/*.jpg
    gaming/*.jpg
    relaxing/*.jpg
    away/*.jpg
  raw/                 # Path B — videos (one activity per file)
    work/desk_session.mp4
    gaming/...
  labels/              # Path B advanced — CSV segments
  features/            # auto-written at train time
  models/latest/       # trained bundle
```

All under `data/` is gitignored — copy `data/` between machines if needed.

**Viewing images in Cursor:** the IDE hides gitignored folders by default. Use one of:

- `npm run data:open-images` — opens `backend/data/base_images/` in File Explorer / Finder
- `npm run data:open-personal` — opens `backend/data/raw_images/`
- Or paste in Explorer: `backend/data/base_images/work` (full path under your repo)
- Cursor setting: **Explorer: Exclude Git Ignore** → off, then `backend/data/` appears in the sidebar

---

## Sample counts per class

Burst settings (default): **5 frames**, **stride 5** between burst starts.

| Tier | Stills/class | Bursts/class | Use when |
|------|--------------|--------------|----------|
| **Minimum** | 30 | ~6 | Smoke train / time crunch |
| **Good demo** | 60 | ~12 | Hackathon judging |
| **Strong day** | 80+ | ~16+ | Best live accuracy |

Videos: **1× 60–90s clip** per class ≈ many bursts (often enough alone with `train:videos`). For splits, prefer **2–3 clips/class**.

---

## Time-boxed plans

### 2 hours

| Time | Action |
|------|--------|
| 0:00–0:10 | `npm run data:init` · read `npm run data:plan -- --which 2h` |
| 0:10–0:50 | `npm run data:capture-stills` — 40 shots × 5 classes |
| 0:50–0:55 | `npm run data:audit` |
| 0:55–1:25 | `npm run train:images` · `npm run train:verify` |
| 1:25–2:00 | `npm run demo` — rehearse poses + 1–2 corrections |

If rushed: prioritize **work, sleep, away** (30 shots each), then gaming/relaxing.

### 4 hours

Add **50 stills/class**, then **1 video/class** (75s):

```bash
npm run data:capture-commands
# run each printed capture line
npm run train:videos   # or train:images if skipping video
```

Include **2–3 “Teach the room”** corrections on `/live` after train.

### 1 day

- **Morning:** 60–80 stills/class, three lighting setups (window open / normal / lamp only).
- **Midday:** 3–5 videos/class; one 5-min mixed clip + `label_windows.py` only if needed.
- **Afternoon:** Extra **away** + **work vs relaxing** negatives (common confusions).
- **Evening:** `npm run data:audit -- --target-bursts 20` · train · verify · demo script.

---

## Commands reference

| Command | Purpose |
|---------|---------|
| `npm run data:init` | Create `data/raw_images/<label>/` trees |
| `npm run data:plan` | Print 2h / 4h / 1d schedules |
| `npm run data:capture-stills` | Webcam → `raw_images` (fastest) |
| `npm run data:capture-stills -- --class work --count 50` | Single class session |
| `npm run data:audit` | Burst balance table (fails if any class LOW) |
| `npm run data:capture-commands` | Print video capture one-liners |
| `npm run train:images` | Train from stills |
| `npm run train:videos` | Train from `data/raw/<label>/` |
| `npm run train:verify` | Train/serve schema check |

Advanced (mixed activity in one file):

```bash
cd backend
python scripts/capture_video.py -o data/raw/work/mixed.mp4 -d 300
python scripts/label_windows.py data/raw/work/mixed.mp4 -o data/labels/mixed.csv
python scripts/extract_features.py data/raw/work/mixed.mp4 -l data/labels/mixed.csv -c configs/train_personal.yaml
```

---

## Person vs away (nobody in the room)

RoomOS learns **person + activity** from labeled photos. **Away** means *no person* — empty couch, empty desk, empty bed, or you fully out of frame. That is different from “relaxing” or “work” with nobody there (a common bug).

Use **two layers**:

| Layer | What it does |
|-------|----------------|
| **Training data** | Teaches the classifier that your camera’s empty room looks like `away` |
| **Live occupancy gate** | At runtime, if CLIP sees no person (empty couch/desk prompts win), forces `away` even when the old model guesses Work |

### More rooms + poses (public pretrain)

Download more stills from the internet into `data/base_images/` (many bedrooms, offices, couches — people in many poses):

```powershell
# Optional: pull extra empty-room photos only (needs network + fiftyone for Open Images)
npm run import:base-images -- --per-class 500 --labels away

# Augment + train on ~350+ images per class from many real rooms
npm run train:expand-augs
npm run train:multi-room
```

You already have hundreds of `away` images under `backend/data/base_images/away/` if a prior import ran; re-run `train:multi-room` after any import.

### Your room + your camera (best for /live)

Capture **your** empty room and **you** in each activity (different poses: sitting, lying, side angle, lights on/off):

```powershell
npm run data:init

# Empty room — critical (60+ shots): leave frame, couch only, desk only, night + day
npm run data:capture-away

# You in each activity (40–60 each): work at desk, sleep in bed, couch, gaming
npm run data:capture-stills

npm run data:audit
npm run train:my-room
npm run demo
```

`train:my-room` weights **your** stills 12× higher than generic multi-room photos so the model learns *your* layout and when *you* are actually there.

### What to capture for `away`

- Nobody visible — full frame is furniture/walls only  
- Same desk/couch/bed that falsely triggered Work or Relaxing when empty  
- Lights on and lights dim  
- Door open / door closed if that changes the view  

### What to capture for person classes

- **work** — you at desk, laptop open, several angles  
- **sleep** — you in bed, low light  
- **relaxing** — you on couch, no keyboard focus  
- **gaming** — you + screen/controller  

Do **not** put empty-room photos in `work/` or `relaxing/` folders.

---

## Biggest data quality risks

1. **Label bleed** — same folder, different activities (desk photo in `relaxing`). *Fix:* one pose per folder; re-capture outliers.
2. **Work vs relaxing confusion** — couch with laptop can look like both. *Fix:* relaxing = no keyboard focus; work = clear desk setup.
3. **Away not empty** — partial body at edge. *Fix:* leave frame entirely or door-open empty room.
4. **Sleep vs relaxing** — horizontal on couch. *Fix:* sleep = darker, bed/bedding; relaxing = seated/lounging awake.
5. **Lighting shift** — train only at noon, demo at night. *Fix:* 10+ shots per lighting condition.
6. **Whole-video wrong label** — 90s clip with activity change. *Fix:* shorter clips or `label_windows.py`.
7. **Too few away/gaming** — model biased to work/sleep. *Fix:* `data:audit` until balanced.
8. **Train/serve skew** — always `configs/train_personal.yaml` + `train:verify`.

---

## Reproducibility checklist

- [ ] `configs/train_personal.yaml` for all extract/train steps  
- [ ] `npm run train:verify` before demo  
- [ ] Record commit hash + image counts in a note (`data/audit` output)  
- [ ] Same webcam position as `/live` inference  
- [ ] Do not edit files under `data/models/latest/` by hand  

See also: [`TRAINING.md`](TRAINING.md), [`DEMO.md`](DEMO.md), [`FEEDBACK.md`](FEEDBACK.md).
