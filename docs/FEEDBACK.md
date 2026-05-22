# Feedback and room memory

Corrections are **local**, **persistent**, and adjust **future similar bursts** — they do **not** retrain the XGBoost bundle on the live path.

## What happens when you tap a correction

1. **Capture** — The last completed burst: fused feature vector + up to 5 JPEG frames.
2. **Persist** — Appended to `backend/data/feedback/` (see below).
3. **Immediate preview** — API returns model vs memory-blended probabilities for **the same features** (demo proof).
4. **Ongoing inference** — Each new burst: cosine similarity to saved corrections; matches above `similarity_floor` nudge class probabilities before smoothing.

## What is *not* happening

- No change to `data/models/latest/model.json` until you run `npm run train:*` with labeled data.
- No cloud upload.

## Storage layout

```
backend/data/feedback/
  feedback_examples.json    # feature vectors + labels (reloads on restart)
  feedback_events.jsonl     # append-only audit log
  screenshots/<id>/frame_01.jpg …
```

## Tuning (configs/inference.yaml → inference.feedback)

| Field | Demo role |
|-------|-----------|
| `influence` | How strongly a match pulls toward the corrected label |
| `similarity_floor` | Minimum cosine sim to apply a stored correction (lower = more matches) |
| `personalization_blend` | Mix weight: 1.0 = full memory blend, 0 = raw model only |

## API

- `GET /api/live/feedback/status` — memory count, paths, last correction
- `POST /api/live/feedback` — body `{ "corrected_label": "sleep", "notes": "" }` — returns `probabilityPreview`, `effects`, `memoryExamples`

## Demo tip

Correct while holding a pose, keep the pose for the next 1–2 bursts — you should see **Room memory** in rationale and higher % on the corrected label in **All states**.
