# Training readiness — external datasets vs RoomOS

This report describes what the ingestion pipeline can supply **without claiming any model improvement** until you train and evaluate on your machine.

RoomOS production labels: `work`, `gaming`, `sleep`, `relaxing`, `away` (see `docs/DATA-COLLECTION.md`).

---

## Usable now (after `bash scripts/download_datasets.sh`)

| Asset | Best for | Limitation |
|-------|----------|------------|
| **Indoor Action Dataset** (if zip succeeds) | relaxing (`watching tv`), away (`no-action`), weak work (`cleaning`) | No gaming; transitions marked uncertain |
| **UCI Occupancy** | away vs occupied | No activity class |
| **Indoor Scene Recognition (HF)** | scene context, weak away | Not person-level activity |
| **MPII (HF)** | pose + coarse activity keywords | Gaming sparse; license limits commercial image use |
| **SLP code repo** | reference loaders for sleep research | No media without password |

Run metadata build:

```bash
pip install -r requirements-datasets.txt
python scripts/prepare_roomos_dataset.py
```

Review `data/processed/roomos_unified.jsonl` and `data/processed/prepare_report.json`.

---

## Requires manual approval

| Dataset | Blocker | Priority for RoomOS |
|---------|---------|---------------------|
| Toyota Smarthome | INRIA form + institution email | High for ADL pretrain (sleep, work, relaxing) |
| SLP media zip | Password + institution email | High for **sleep** |
| Kaggle Posture | API token | Medium — posture, not room state |
| CASAS | Per-dataset registration | Medium for **away** / occupancy timing |

Details: `docs/DATASET_ACCESS.md`.

---

## Best dataset per target state

| Target | Strongest public sources | Gap severity |
|--------|-------------------------|--------------|
| **work** | Toyota Smarthome (after approval), MPII keywords, Indoor Action `cleaning` | Medium — rarely desk-specific in public sets |
| **gaming** | MPII keyword hits, Indoor Scene `gameroom` | **Severe** — almost no labeled gaming in listed sets |
| **sleep** | SLP (gated), Toyota Smarthome, MPII sleep/bed, Indoor Action `lying` | Medium without SLP zip |
| **relaxing** | Indoor Action `watching tv`, Toyota TV activities, MPII couch/TV | Medium |
| **away** | Indoor Action `no-action`, UCI occupancy 0, empty scene classes | Medium — sensor vs vision mismatch |

---

## Major gaps

1. **Gaming** — None of the nine sources center on PC/console gaming in a bedroom/office setup. Plan dedicated capture: `npm run data:capture-stills` → `backend/data/raw_images/gaming/`.
2. **Room-specific appearance** — Public data ≠ your camera angle, lighting, and furniture.
3. **Modality mismatch** — RoomOS default live pipeline uses **CLIP + motion bursts** on RGB; UCI/CASAS are sensor-only unless you fuse separately.
4. **License** — MPII/Toyota/SLP restrict commercial use; respect terms before redistribution.

---

## Recommended next steps

1. Run `bash scripts/check_environment.sh` and `bash scripts/download_datasets.sh`.
2. Complete manual steps in `docs/DATASET_ACCESS.md` for Toyota Smarthome and SLP if you need ADL/sleep pretrain.
3. Collect **≥80 stills per class** in your room (`docs/DATA-COLLECTION.md`).
4. `python scripts/prepare_roomos_dataset.py` — audit `ambiguous: true` rows before mixing into training.
5. Train only with explicit config, e.g. `npm run train:images` or `train:my-room` — then `npm run train:verify` / eval scripts.
6. Do **not** claim accuracy gains until `backend/scripts/evaluate_model.py` (or your eval harness) reports metrics on a held-out **your-room** set.

---

## Pipeline layout

```text
manifests/datasets.yaml          # inventory + access_status
manifests/label_mapping.yaml     # mapping rules
scripts/download_datasets.sh     # fetch public / mark blocked
scripts/prepare_roomos_dataset.py
data/raw/          # downloads
data/interim/      # future transforms
data/processed/    # roomos_unified.jsonl
```

Personal training data remains under `backend/data/` (gitignored), separate from repo-root `data/`.
