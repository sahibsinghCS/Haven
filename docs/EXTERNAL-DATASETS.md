# External dataset ingestion (repo root)

Reproducible pipeline for **public ADL / pose / scene** sources used to pretrain or audit label coverage — separate from personal room data in `backend/data/`.

## Quick start

```bash
bash scripts/check_environment.sh
pip install -r requirements-datasets.txt
bash scripts/download_datasets.sh
python scripts/prepare_roomos_dataset.py
```

Outputs:

| Path | Purpose |
|------|---------|
| `data/raw/` | Downloads |
| `data/processed/roomos_unified.jsonl` | Mapped metadata + provenance |
| `manifests/datasets.yaml` | Inventory & `access_status` |

See also: [DATASET_ACCESS.md](DATASET_ACCESS.md), [LABEL_MAPPING.md](LABEL_MAPPING.md), [TRAINING_READINESS.md](TRAINING_READINESS.md).
