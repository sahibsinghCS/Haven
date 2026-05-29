# Cold start vs your room (product goal)

HAVEN is designed for two modes. This is the **main goal** the engineering work targets.

## 1. Brand-new room (never seen before)

**Goal:** Point a camera at an unfamiliar bedroom, office, or living space. Without any training on that specific room, the system should:

1. **Understand the scene** — recognize typical layout cues (bed, desk, couch, monitor, empty space) via CLIP scene/object prompts, not a hand-drawn floor plan.
2. **Estimate activity** — work, sleep, gaming, relaxing, or away with **≥ ~60% correctness** across states on average (held-out multi-room benchmark), using:
   - Multi-room training (`npm run train:multi-room` / `train:multi-room-v2`)
   - Live **occupancy gate** (no person → away)
   - Live **activity hints** (desk vs couch vs gaming screen)

**What “understand where everything is” means today**

| Today | Later (optional) |
|-------|-------------------|
| Semantic cues: “empty couch”, “unoccupied desk”, “person at desk” | Metric room map / regions you tap once |
| Works across many internet rooms | Perfect geometry per wall |

We do **not** require a user to label furniture before first use. The generic model generalizes from thousands of photos of many rooms.

**Shipped generic model (v2)** — trained on ~500 images × 5 classes from Open Images / Wikimedia-style sources:

| Metric | Typical held-out test |
|--------|----------------------:|
| Overall accuracy | ~77% |
| Macro F1 | ~79% |
| Away (empty) recall | ~95% |
| Gaming recall | ~97% |
| Work recall | ~44% (hardest — desk vs couch photos overlap) |

So **away, gaming, sleep, relaxing** usually meet the 60% bar on unseen rooms; **work** often needs the second mode below.

Commands:

```powershell
npm run train:multi-room-v2   # or train:multi-room
npm run demo
```

## 2. Your room (user-trained)

**Goal:** The resident trains **only their space** — no need to retrain the whole internet dataset.

```powershell
npm run data:init
npm run data:capture-away      # empty room, many angles
npm run data:capture-stills    # you in each activity
npm run train:my-room          # your photos weighted 12× over generic
npm run demo
```

Personal bundles override layout confusion (your couch angle, your desk, your lighting). Corrections on `/live` and **Review switches** add memory without a full retrain.

## How to think about accuracy

| Mode | Target | How |
|------|--------|-----|
| **Generic / cold start** | ≥ **60%** per-state quality on average; no class completely ignored | `train:multi-room-v2`, gates, hints |
| **Your room** | As high as you can get (~80%+ with good captures) | `train:my-room` + corrections |

## Data flow (one picture)

```text
                    ┌─────────────────────────────────────┐
  Never-seen room   │  Generic multi-room model (shipped) │
  first plug-in     │  + occupancy + activity hints       │
                    └─────────────────┬───────────────────┘
                                      │ ≥60% typical
                    ┌─────────────────▼───────────────────┐
  User's room       │  data/raw_images + train:my-room   │
  optional          │  + live corrections / review        │
                    └─────────────────────────────────────┘
```

## See also

- [`DATA-COLLECTION.md`](DATA-COLLECTION.md) — what to photograph per class  
- [`TRAINING.md`](TRAINING.md) — `train:multi-room` vs `train:my-room`  
- [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md) — false Work on empty couch  
