# External dataset access (manual steps)

Automated ingestion is implemented in `scripts/download_datasets.sh`. This document lists sources that **cannot** be fetched without human approval, credentials, or passwords. The download script **does not** bypass these gates.

Status values in `manifests/datasets.yaml`: `downloaded`, `partial`, `blocked`.

---

## Blocked — action required

### Toyota Smarthome

| Field | Value |
|-------|--------|
| **URL** | https://project.inria.fr/toyotasmarthome/ |
| **Local path** | `data/raw/toyota_smarthome/` |
| **Requirement** | Online **request form** + **work/institution email** (personal Gmail ignored) |
| **Approval** | Manual review; download link emailed (~3 days) |
| **License** | Academic research only ([License v2](https://project.inria.fr/toyotasmarthome/files/2020/12/License_v2.pdf)) |
| **Manual steps** | 1. Read license. 2. Submit form (Trimmed / Untrimmed / Both). 3. Place extracted data under `data/raw/toyota_smarthome/`. 4. Re-run `python scripts/prepare_roomos_dataset.py`. |

Alternate form: https://docs.google.com/forms/d/e/1FAIpQLSdl-wH5xMitp6Nh88Ieu3gRcpuFSB_Ja_IgCZ2gGdf8Bn0Kjw/viewform

Pre-extracted **features** (not raw video) may be available without full video request:
- RGB I3D: https://mybox.inria.fr/f/63c80895c71643f0abde/
- 3D pose: https://mybox.inria.fr/f/a46938b7995c46f28855/

---

### SLP multimodal in-bed dataset (media)

| Field | Value |
|-------|--------|
| **URL** | https://ostadabbas.sites.northeastern.edu/slp-dataset-for-multimodal-in-bed-pose-estimation-3/ |
| **Zip** | https://coe.neu.edu/Research/AClab/SLP/SLP2022.zip |
| **Local path** | `data/raw/slp_dataset/` |
| **Requirement** | **Request form** for password + **institution email** (not personal) |
| **Approval** | Manual |
| **License** | **Non-commercial purposes** only (research, teaching, publication) |
| **Manual steps** | 1. Request password via site form. 2. Download zip. 3. Unzip into `data/raw/slp_dataset/`. 4. Run prepare script. |

**Note:** `scripts/download_datasets.sh` clones https://github.com/ostadabbas/SLP-Dataset-and-Code (code only, no password zip).

---

### Kaggle — Posture Keypoints Detection

| Field | Value |
|-------|--------|
| **URL** | https://www.kaggle.com/datasets/melsmm/posture-keypoints-detection |
| **Local path** | `data/raw/kaggle_posture_keypoints/` |
| **Requirement** | **Kaggle account** + **API token** |
| **Credentials** | `~/.kaggle/kaggle.json` (from Kaggle → Account → Create New Token) |
| **Manual steps** | 1. Accept dataset rules on Kaggle. 2. Install CLI: `pip install kaggle`. 3. Place token file. 4. Run `bash scripts/download_datasets.sh` or `kaggle datasets download -d melsmm/posture-keypoints-detection -p data/raw/kaggle_posture_keypoints --unzip` |

---

### CASAS smart home datasets

| Field | Value |
|-------|--------|
| **URL** | https://casas.wsu.edu/datasets/ |
| **Local path** | `data/raw/casas/<dataset_name>/` |
| **Requirement** | **Per-dataset registration** and agreement (varies by release) |
| **Approval** | Manual for most collections |
| **Manual steps** | 1. Choose dataset (e.g. Kyoto, Cairo). 2. Complete WSU request/download flow. 3. Extract under `data/raw/casas/`. 4. Document which release in `manifests/datasets.yaml` notes. |

---

## Public or partially automated

| Dataset | Automated | Notes |
|---------|-----------|--------|
| Indoor Action Dataset | Clone + public zip (UGR) | Videos via `setup_video_data.sh` URL; see `data/raw/indoor_action_dataset/` |
| UCI Occupancy Detection | Direct zip from UCI | Sensor CSV, not video |
| MPII Human Pose (HF) | `huggingface_hub` snapshot | Install `requirements-datasets.txt` |
| Indoor Scene Recognition (HF) | Same | 67 scene classes |
| SLP code repo | `git clone` | No multimodal zip |

---

## Environment

```bash
bash scripts/check_environment.sh
pip install -r requirements-datasets.txt
bash scripts/download_datasets.sh
python scripts/prepare_roomos_dataset.py
```

On Windows, run the same commands in **Git Bash** or WSL; native PowerShell does not run `.sh` directly.
