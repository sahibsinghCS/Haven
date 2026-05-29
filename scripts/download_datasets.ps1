# Windows wrapper for the dataset download pipeline (Git Bash preferred for .sh).
# Usage: .\scripts\download_datasets.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (Get-Command bash -ErrorAction SilentlyContinue) {
    bash scripts/download_datasets.sh
    exit $LASTEXITCODE
}

Write-Host "Git Bash not found. Running core public steps via PowerShell..."
New-Item -ItemType Directory -Force -Path data/raw, data/interim, data/processed | Out-Null
pip install -q -r requirements-datasets.txt

if (-not (Test-Path data/raw/indoor_action_dataset/.git)) {
    git clone --depth 1 https://github.com/DaniDeniz/IndoorActionDataset.git data/raw/indoor_action_dataset
}
if (-not (Test-Path data/raw/indoor_action_dataset/IndoorActionDataset-video.zip)) {
    curl.exe -fL -o data/raw/indoor_action_dataset/IndoorActionDataset-video.zip `
        "https://atcdatos.ugr.es/index.php/s/zqPA9ajR78Bn6qB/download"
}
if (-not (Test-Path data/raw/uci_occupancy_detection/datatraining.txt)) {
    New-Item -ItemType Directory -Force -Path data/raw/uci_occupancy_detection | Out-Null
    curl.exe -fL -o data/raw/uci_occupancy_detection/occupancy_detection.zip `
        "https://archive.ics.uci.edu/static/public/357/occupancy+detection.zip"
    Expand-Archive -Force data/raw/uci_occupancy_detection/occupancy_detection.zip `
        data/raw/uci_occupancy_detection
}

python scripts/prepare_roomos_dataset.py
Write-Host "For HF/Kaggle/gated sets, see docs/DATASET_ACCESS.md"
