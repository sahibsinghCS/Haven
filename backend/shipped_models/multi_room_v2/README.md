# Pre-trained multi-room model (v2)

This folder is **committed to Git** so new clones get the same classifier the maintainer trained on public room photos (`backend/data/base_images/` on the training machine).

## Install (from repo root)

```bash
npm run setup:shipped-model
npm run train:verify
```

Copies these files into `backend/data/models/latest/` (gitignored at runtime).

## Do not confuse with bootstrap

| Command | Training data | Use |
|---------|---------------|-----|
| `npm run setup:shipped-model` | Real multi-room photos (maintainer's train run) | **Default for judges / try it out** |
| `npm run setup:model` | Synthetic colored stills generated in code | Pipeline smoke test only |

## Refresh this bundle (maintainers)

After `npm run train:multi-room-v2` on a machine with `base_images/`:

```powershell
Copy-Item backend\data\models\latest\model.json, backend\data\models\latest\label_encoder.json, backend\data\models\latest\feature_columns.json, backend\data\models\latest\train_config.json, backend\data\models\latest\live_compat.json, backend\data\models\latest\metrics.json, backend\data\models\latest\training_summary.json -Destination backend\shipped_models\multi_room_v2\
```

Then commit `backend/shipped_models/multi_room_v2/`.
