# Label mapping → RoomOS room states

Canonical RoomOS labels (match `backend/data` and the live app):

| Display | ID |
|---------|-----|
| Working | `work` |
| Gaming | `gaming` |
| Sleeping | `sleep` |
| Relaxing | `relaxing` |
| Away | `away` |

Meta labels used during ingestion (not trained as primary classes unless you choose to):

- **`uncertain`** — weak or ambiguous mapping; keep for review, do not silently train as a confident class.
- **`discard`** — out of scope (safety events, outdoor sports, irrelevant ADLs).

Machine-readable rules: `manifests/label_mapping.yaml`. Applied by `scripts/prepare_roomos_dataset.py`.

---

## Indoor Action Dataset (10 classes)

| Source label | → RoomOS | Confidence | Notes |
|--------------|----------|------------|-------|
| watching tv | relaxing | high | Closest steady-state match |
| eating | relaxing | medium | Could be work at desk |
| cleaning | work | medium | Chore, not desk work |
| no-action | away | high | Empty / no activity |
| lying on the floor | sleep | medium | May be fall — review |
| falling down | **discard** | high | Safety, not room mood |
| blowing nose / sneezing | **discard** | high | Not a room state |
| sitting down | **uncertain** | low | Transition |
| standing up | **uncertain** | low | Transition |
| walking | **uncertain** | low | Transit |

---

## UCI Occupancy Detection

| Source | → RoomOS | Notes |
|--------|----------|-------|
| 0 (not occupied) | away | Strong empty-room proxy |
| 1 (occupied) | **uncertain** | Person present; activity unknown |

Use for **away vs occupied** weak supervision only, not gaming/work discrimination.

---

## MPII Human Pose (410 activities)

Default: **`uncertain`** unless keyword match.

| Pattern (examples) | → RoomOS |
|--------------------|----------|
| computer, laptop, office, studying | work |
| sleep, nap, lying, bed | sleep |
| tv, sofa, couch, resting | relaxing |
| game, gaming, console | gaming |
| sports, outdoor, stadium | **discard** |

Commercial use of MPII **images** is restricted; annotations are BSD-2-Clause.

---

## Indoor Scene Recognition (67 scenes)

Scene labels are **not** person activities. Most map **`uncertain`** or weak proxies:

| Pattern | → RoomOS | Notes |
|---------|----------|-------|
| office, computerroom, library | work | low — room may be empty |
| gameroom | gaming | medium |
| livingroom, tvroom | relaxing | low |
| corridor, garage, closet | away | medium — often empty |
| bedroom | uncertain | sleep vs relaxing vs away |

Best used for **scene context** features, not direct state labels.

---

## Toyota Smarthome (31+ ADL)

Blocked until approved. After download, build a CSV mapping fine labels → RoomOS:

- Desk / reading / meal prep → often `work` or `relaxing`
- Watch TV → `relaxing`
- Sleep / lie in bed → `sleep`
- Leave home / no person → `away`
- **Gaming** — rarely labeled explicitly → gap

---

## SLP (in-bed poses)

Pose categories (supine, left/right side) → **`sleep`** with high confidence. Not gaming/work/relaxing.

---

## Kaggle Posture Keypoints

Inspect released class names after download. Body posture ≠ room activity; default **`uncertain`** until manual schema review.

---

## CASAS

Sensor streams → **`uncertain`** for activity; motion absence may support **`away`** heuristics only.

---

## Principles

1. **Never silently upgrade** `uncertain` to a primary class in training configs.
2. Keep `source_label` and `provenance` in unified metadata (`data/processed/roomos_unified.jsonl`).
3. Prefer **your room** (`backend/data/raw_images/`) for production; external data is pretrain / augmentation only.
