#!/usr/bin/env bash
# Reproducible download of public external datasets for RoomOS room-state research.
# Gated sources are detected and documented in docs/DATASET_ACCESS.md (not faked).
#
# Usage (from repo root):
#   bash scripts/check_environment.sh
#   bash scripts/download_datasets.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RAW="${ROOT}/data/raw"
INTERIM="${ROOT}/data/interim"
PROCESSED="${ROOT}/data/processed"
MANIFEST_PY="${ROOT}/scripts/dataset_manifest.py"

mkdir -p "$RAW" "$INTERIM" "$PROCESSED"

log() { printf '[download] %s\n' "$*"; }
warn() { printf '[download][warn] %s\n' "$*" >&2; }
fail() { printf '[download][fail] %s\n' "$*" >&2; }

update_manifest() {
  local id="$1"
  local status="$2"
  local blocker="${3:-}"
  local local_path="${4:-}"
  local notes="${5:-}"
  if [[ ! -f "$MANIFEST_PY" ]]; then
    warn "manifest updater missing; skip status for $id"
    return 0
  fi
  local args=(python3 "$MANIFEST_PY" "$id" --access-status "$status")
  [[ -n "$blocker" ]] && args+=(--blocker-reason "$blocker")
  [[ -n "$local_path" ]] && args+=(--local-path "$local_path")
  [[ -n "$notes" ]] && args+=(--notes "$notes")
  "${args[@]}" || warn "could not update manifest for $id"
}

http_download() {
  local url="$1"
  local dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [[ -f "$dest" ]]; then
    log "already exists: $dest"
    return 0
  fi
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --connect-timeout 30 -o "$dest" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -q --show-progress -O "$dest" "$url"
  else
    fail "need curl or wget"
    return 1
  fi
}

git_clone() {
  local url="$1"
  local dest="$2"
  if [[ -d "$dest/.git" ]]; then
    log "repo present: $dest (git pull skipped; delete dir to re-clone)"
    return 0
  fi
  git clone --depth 1 "$url" "$dest"
}

# --- 1) Toyota Smarthome (request form) ---
log "Toyota Smarthome: academic request only — skipping automated download"
update_manifest "toyota_smarthome" "blocked" \
  "License + web form; work/institution email required. See docs/DATASET_ACCESS.md." \
  "data/raw/toyota_smarthome"

# --- 2) IndoorActionDataset ---
INDOOR_REPO="${RAW}/indoor_action_dataset"
INDOOR_ZIP="${INDOOR_REPO}/IndoorActionDataset-video.zip"
git_clone "https://github.com/DaniDeniz/IndoorActionDataset.git" "$INDOOR_REPO"
if http_download \
  "https://atcdatos.ugr.es/index.php/s/zqPA9ajR78Bn6qB/download" \
  "$INDOOR_ZIP"; then
  if command -v unzip >/dev/null 2>&1; then
    if [[ ! -d "${INDOOR_REPO}/train" ]] && [[ ! -d "${INDOOR_REPO}/IndoorActionDataset-video/train" ]]; then
      log "unzipping Indoor Action videos..."
      (cd "$INDOOR_REPO" && unzip -q -o "$INDOOR_ZIP")
    fi
    # Normalize layout: some archives extract to IndoorActionDataset-video/{train,...}
    if [[ -d "${INDOOR_REPO}/IndoorActionDataset-video/train" ]] && [[ ! -d "${INDOOR_REPO}/train" ]]; then
      log "hoisting IndoorActionDataset-video/ to repo root"
      (cd "$INDOOR_REPO" && mv IndoorActionDataset-video/train IndoorActionDataset-video/validation IndoorActionDataset-video/test . 2>/dev/null || true)
    fi
    update_manifest "indoor_action_dataset" "downloaded" "" "data/raw/indoor_action_dataset" \
      "GitHub repo + public zip from atcdatos.ugr.es"
  else
    update_manifest "indoor_action_dataset" "partial" "unzip not available" \
      "data/raw/indoor_action_dataset" "zip downloaded; install unzip"
  fi
else
  update_manifest "indoor_action_dataset" "partial" "video zip download failed" \
    "data/raw/indoor_action_dataset" "repo cloned; retry zip manually"
fi

# --- 3) SLP dataset (password) ---
log "SLP multimodal dataset: password via request form — skipping zip"
update_manifest "slp_dataset" "blocked" \
  "Password-protected zip; institution email + request form. See docs/DATASET_ACCESS.md." \
  "data/raw/slp_dataset"

# --- 4) SLP code repo ---
SLP_CODE="${RAW}/slp_dataset_and_code"
git_clone "https://github.com/ostadabbas/SLP-Dataset-and-Code.git" "$SLP_CODE"
update_manifest "slp_code" "downloaded" "" "data/raw/slp_dataset_and_code" \
  "Code and docs only; multimodal SLP zip is separate (gated)"

# --- 5) UCI Occupancy Detection ---
UCI_DIR="${RAW}/uci_occupancy_detection"
UCI_ZIP="${UCI_DIR}/occupancy_detection.zip"
mkdir -p "$UCI_DIR"
if http_download \
  "https://archive.ics.uci.edu/static/public/357/occupancy+detection.zip" \
  "$UCI_ZIP"; then
  if command -v unzip >/dev/null 2>&1; then
    if [[ ! -f "${UCI_DIR}/datatraining.txt" ]]; then
      (cd "$UCI_DIR" && unzip -q -o "$UCI_ZIP")
    fi
  fi
  update_manifest "uci_occupancy_detection" "downloaded" "" "data/raw/uci_occupancy_detection" \
    "CC BY 4.0; binary occupancy from env sensors (not RGB)"
else
  update_manifest "uci_occupancy_detection" "blocked" "HTTP download failed" \
    "data/raw/uci_occupancy_detection"
fi

# --- 6) Kaggle Posture Keypoints ---
KAGGLE_DIR="${RAW}/kaggle_posture_keypoints"
mkdir -p "$KAGGLE_DIR"
if [[ -f "${HOME}/.kaggle/kaggle.json" ]] && command -v kaggle >/dev/null 2>&1; then
  if kaggle datasets download -d melsmm/posture-keypoints-detection -p "$KAGGLE_DIR" --unzip; then
    update_manifest "kaggle_posture_keypoints" "downloaded" "" \
      "data/raw/kaggle_posture_keypoints" "Requires Kaggle account + API token"
  else
    update_manifest "kaggle_posture_keypoints" "blocked" "kaggle CLI download failed" \
      "data/raw/kaggle_posture_keypoints"
  fi
else
  log "Kaggle: no credentials — documenting as blocked"
  update_manifest "kaggle_posture_keypoints" "blocked" \
    "Kaggle API credentials missing (~/.kaggle/kaggle.json). See docs/DATASET_ACCESS.md." \
    "data/raw/kaggle_posture_keypoints"
fi

# --- 7–8) Hugging Face (Voxel51 mirrors) ---
HF_PY="${ROOT}/scripts/download_hf_dataset.py"
if python3 -c "import huggingface_hub" 2>/dev/null; then
  python3 "$HF_PY" --repo-id Voxel51/MPII_Human_Pose_Dataset \
    --local-dir "${RAW}/mpii_human_pose_hf" && \
    update_manifest "mpii_human_pose_hf" "downloaded" "" "data/raw/mpii_human_pose_hf" \
      "BSD-2-Clause annotations; images not for commercial use"

  python3 "$HF_PY" --repo-id Voxel51/IndoorSceneRecognition \
    --local-dir "${RAW}/indoor_scene_recognition_hf" && \
    update_manifest "indoor_scene_recognition_hf" "downloaded" "" \
      "data/raw/indoor_scene_recognition_hf" "MIT; 67 indoor scene classes"
else
  warn "huggingface_hub not installed — skipping HF datasets"
  update_manifest "mpii_human_pose_hf" "blocked" \
    "pip install -r requirements-datasets.txt (huggingface_hub)" \
    "data/raw/mpii_human_pose_hf"
  update_manifest "indoor_scene_recognition_hf" "blocked" \
    "pip install -r requirements-datasets.txt (huggingface_hub)" \
    "data/raw/indoor_scene_recognition_hf"
fi

# --- 9) CASAS (registration hub) ---
log "CASAS: per-dataset registration — see docs/DATASET_ACCESS.md"
update_manifest "casas_hub" "blocked" \
  "No single public bundle; most CASAS releases require registration at casas.wsu.edu" \
  "data/raw/casas"

log "Done. Review manifests/datasets.yaml and docs/DATASET_ACCESS.md"
