# Train / serve compatibility

## Design

Live inference always extracts features using **`configs/inference.yaml`**. The XGBoost bundle must have been trained with a **matching** feature schema.

```
train_personal.yaml  ──train──>  data/models/latest/
                                      │
inference.yaml  ──live extract──>     ├── feature_columns.json
                                      ├── label_encoder.json
                                      └── train_config.json (snapshot)
```

### Gate points

1. **Post-train** (`finalize_training`) — warn before you demo a bad bundle
2. **Engine start** (`gate_live_engine_start`) — block `/live` if skewed
3. **CLI** (`scripts/verify_bundle.py`) — manual check

### Safe alignment (already in code)

`align_features()` at predict time fills **missing** columns with `0` and reorders columns. This only works when train and inference share the **same column set**; the gate enforces set equality so you never get silent all-zero wrong features.

### Not auto-fixed

- Training with `pose: true` but live `pose: false` → **blocked**
- Different CLIP prompts → different `clip_sim__*` names → **blocked**
- Wrong label order in bundle → **blocked**

## Example failure message

```
Live engine blocked: model bundle is not compatible with inference config.

  Model bundle:      C:\RoomOS\backend\data\models\latest
  Inference config:  C:\RoomOS\backend\configs\inference.yaml
  Trained with:      configs/train.yaml

[Feature modules (clip / pose / motion / posture)]
  features.enabled.pose:
    train:      enabled
    inference:  disabled
    note:       Train and live inference must extract the same modules.

[Feature columns]
  extra in bundle:
    train:      42 columns e.g. pose_present_ratio_mean, ...
    inference:  (not produced live)
    note:       Model expects features live inference no longer computes.

Fix (recommended):
  npm run train:demo
  npm run train:verify
```

## API

`GET /api/live/status`:

```json
{
  "engine_running": false,
  "engine_error": "...",
  "compat_ok": false,
  "compat_report": { "ok": false, "mismatches": [...] }
}
```
