# Model evaluation (hackathon / Q&A)

All judge-ready artifacts live in one folder:

```text
backend/data/models/latest/eval_report/
```

## Generate the report

**Automatic after training** — `npm run train:images`, `train:videos`, or `train:demo` writes `eval_report/` when training finishes.

**Refresh from existing bundle:**

```bash
npm run eval:report
# or
cd backend
python scripts/generate_eval_report.py -b data/models/latest
```

**Re-evaluate on a features file** (optional holdout parquet):

```bash
cd backend
python scripts/generate_eval_report.py -b data/models/latest \
  -f data/features/personal_image_features.parquet --recompute
```

## What’s in `eval_report/`

| File | Purpose |
|------|---------|
| **REPORT.md** | One-page summary — start here for judges |
| `metrics_summary.json` | Accuracy, macro/weighted F1, per-class table |
| `metrics_all_splits.json` | Train / val / test if available |
| `confusion_matrix_normalized.png` | Slide-friendly CM (row %) |
| `confusion_matrix_counts.png` | Raw burst counts |
| `class_distribution.png` | Training bursts per class |
| `class_distribution.json` | Same data as JSON |
| `feature_importance_top30.png` | Top XGBoost features |
| `feature_importance_groups.json` | CLIP vs motion vs pose share |
| `LIMITATIONS.md` | Honest caveats (read aloud in Q&A) |

Legacy bundle root files still exist: `metrics.json`, `confusion_matrix.png`, `training_summary.json`.

## How to explain results honestly

**Opening line:**  
“We trained a small tabular classifier on **5-frame bursts** from *my* room — CLIP scene context plus motion. These metrics are on a **held-out split of those bursts**, not a published benchmark.”

**Headline numbers** (from `REPORT.md`):

- **Accuracy** — overall correct bursts; misleading if classes are imbalanced.
- **Macro F1** — treats each mood equally; use when you balanced data.
- **Weighted F1** — favors common classes; compare to macro to show imbalance.

**Per-class table** — “For **sleep**, recall is X: when I’m actually asleep, we catch it Y% of the time. Precision is Z: when we say sleep, we’re usually right.”

**Confusion matrix** — “The main mix-up is **work → relaxing** (point at off-diagonal). That’s why we collect clear desk vs couch photos.”

**Class distribution** — “We had N bursts per class; away is thin — live demo may wobble there.”

**Feature groups** — “Most gain comes from **CLIP + motion**, not a giant neural end-to-end model.”

**Limitations** (from `LIMITATIONS.md`) — always mention:

1. Offline bursts ≠ live webcam session accuracy  
2. Small N per class → directional, not research-grade  
3. Personal room only  
4. Live **Teach the room** memory is separate until retrain  

## npm commands

| Command | Action |
|---------|--------|
| `npm run eval:report` | Build `eval_report/` from `metrics.json` |
| `npm run train:images` | Train + report |
| `npm run train:verify` | Train/serve schema check |

See also: [`TRAINING.md`](TRAINING.md), [`DATA-COLLECTION.md`](DATA-COLLECTION.md).
