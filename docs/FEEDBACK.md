# Feedback and room memory

The product loop is **right or wrong**: confirm the current read, or tap the real activity. Every answer is saved locally and makes the system better.

Two layers apply:

1. **Room memory** — immediate probability nudges on similar bursts (cosine similarity).
2. **Auto-retrain** (default **on**) — after enough answers, XGBoost **retrains in the background** on `multi_room_features` + your labeled bursts, then **reloads** `data/models/latest` without restarting the app.

## What happens when you answer

**Yes (confirmed)** — `corrected_label` matches what the model showed. Saved as a positive training row (`user_confirmation`) with the same weight as corrections.

**No (wrong)** — pick the real activity. Saved as `user_correction`; memory penalizes the wrong label on similar scenes.

## What happens when you tap a correction

1. **Capture** — The last completed burst: fused feature vector + up to 5 JPEG frames.
2. **Persist** — Appended to `backend/data/feedback/` (see below).
3. **Immediate preview** — API returns model vs memory-blended probabilities for **the same features** (demo proof).
4. **Ongoing inference** — Each new burst: cosine similarity to saved corrections; matches above `similarity_floor` nudge class probabilities before smoothing.

## Auto-retrain (`inference.auto_retrain` in `configs/inference.yaml`)

| Field | Default | Meaning |
|-------|---------|---------|
| `enabled` | `true` | Background retrain after corrections |
| `min_corrections` | `3` | Right/wrong taps before a retrain starts |
| `min_interval_sec` | `60` | Cooldown between retrains |
| `correction_row_weight` | `1` | Same pull as base rows (1×) |
| `confirmation_row_weight` | `1` | Confirmed taps also 1× |

Manual retrain anytime:

```bash
npm run train:reinforce
```

## What is *not* happening

- No cloud upload.
- Auto-retrain does **not** replace capturing your room (`npm run data:capture-stills` + `train:my-room`) for best webcam accuracy.

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
- `POST /api/live/feedback` — body `{ "corrected_label": "sleep", "notes": "" }` — use the **shown** label to confirm (`confirmed: true`), or another label to correct — returns `probabilityPreview`, `effects`, `memoryExamples`, `autoRetrain`

## Demo tip

Correct while holding a pose, keep the pose for the next 1–2 bursts — you should see **Room memory** in rationale and higher % on the corrected label in **All states**.

## Review switches (frame history)

When the **displayed** primary state changes (after smoothing confirm + cooldown), RoomOS saves that moment:

| Storage | Contents |
|---------|----------|
| `backend/data/transitions/transitions.jsonl` | Full record + feature vector |
| `backend/data/transitions/screenshots/<id>/frame_*.jpg` | Up to 5 burst frames |

**UI:** `/review` or the compact **Recent switches** panel on `/live`.

**API:**

- `GET /api/live/transitions` — list recent switches
- `GET /api/live/transitions/{id}/frames/{n}.jpg` — frame JPEG
- `POST /api/live/transitions/{id}/correct` — body `{ "corrected_label": "relaxing" }` → same right/wrong loop as live (confirm with `toLabel`, or pick another state)

Relabeling a past **sleep** switch as **relaxing** stores that burst’s fingerprint; the next time you’re in a similar bed pose, memory nudges toward relaxing automatically.

## Empty-room / "no person" gate

Feedback memory only kicks in **after** you tap a correction. Bootstrap models trained on synthetic stills frequently confuse an empty couch / desk / bed for `work` or `relaxing`, which is bad UX *before* any feedback exists.

To handle this, the live pipeline runs a cheap **occupancy gate** after each XGBoost prediction (see `backend/roomos/inference/occupancy.py`). It uses signals already present in the fused burst row:

| Signal | When used |
|--------|-----------|
| `clip_sim__an_empty_room_with_no_people_mean` vs `max(clip_sim__a_person_*_mean)` | Always (when `features.enabled.clip: true`) |
| `motion_mean_mean` | Always — a high-motion burst is never treated as empty (avoids walk-through flips) |
| `pose_present_ratio` | Only when `features.enabled.pose: true` |

When the gate fires it forces at least `inference.occupancy.away_floor_prob` (default `0.78`) onto the `away` class **before** feedback personalization and smoothing. The user can still correct an empty-room read via "Teach the room" — the gate is a prior, not a hard veto.

Knobs (in `backend/configs/inference.yaml`):

```yaml
inference:
  occupancy:
    enabled: true
    empty_margin: 0.015          # empty-prompt sim must beat person-prompt sim by this
    motion_max_for_empty: 0.02   # gate is off above this much burst-average motion
    pose_present_floor: 0.2      # only used when features.enabled.pose is true
    away_floor_prob: 0.78        # mass forced onto 'away' when gate fires
```

Rationale bullets surface the gate transparently, e.g.:

> Occupancy gate: scene looks empty (CLIP 'empty room' > 'a person', margin=+0.04).

Until a personal model (`npm run train:images`) is trained on your own empty-room captures, expect occasional flips back to `work`/`relaxing` when CLIP genuinely sees you with a laptop. The gate is intentionally conservative.

