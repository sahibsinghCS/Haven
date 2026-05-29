#!/usr/bin/env bash
# Verify tools needed by scripts/download_datasets.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ok=0
warn=0
fail=0

check() {
  local name="$1"
  local cmd="$2"
  local required="${3:-yes}"
  if command -v "$cmd" >/dev/null 2>&1; then
    local ver
    ver="$("$cmd" --version 2>/dev/null | head -n1 || "$cmd" -V 2>/dev/null | head -n1 || echo "present")"
    printf "  [ok]   %-18s %s\n" "$name" "$ver"
    ok=$((ok + 1))
  else
    if [[ "$required" == "yes" ]]; then
      printf "  [FAIL] %-18s not found (%s)\n" "$name" "$cmd"
      fail=$((fail + 1))
    else
      printf "  [warn] %-18s not found (%s) — optional\n" "$name" "$cmd"
      warn=$((warn + 1))
    fi
  fi
}

echo "RoomOS dataset environment check (root: $ROOT)"
echo

check "git" git
check "python3" python3
check "pip" pip3 no
if ! command -v pip3 >/dev/null 2>&1; then
  check "pip (python -m)" python no
fi
check "kaggle" kaggle no
check "hf (Hub CLI)" hf no
if ! command -v hf >/dev/null 2>&1; then
  if command -v huggingface-cli >/dev/null 2>&1; then
    printf "  [warn] %-18s use 'hf' instead (huggingface-cli is deprecated)\n" "huggingface-cli"
    warn=$((warn + 1))
  elif python3 -c "import huggingface_hub" 2>/dev/null; then
    printf "  [warn] %-18s package OK; add Scripts to PATH or use: python -m huggingface_hub.cli.hf\n" "huggingface_hub"
    warn=$((warn + 1))
  fi
fi
check "wget" wget no
check "curl" curl no
if ! command -v wget >/dev/null 2>&1 && ! command -v curl >/dev/null 2>&1; then
  printf "  [FAIL] %-18s need wget or curl for HTTP downloads\n" "http client"
  fail=$((fail + 1))
fi
check "unzip" unzip no

echo
if [[ -f "$HOME/.kaggle/kaggle.json" ]]; then
  echo "  [ok]   Kaggle credentials   ~/.kaggle/kaggle.json"
else
  echo "  [warn] Kaggle credentials   missing — Kaggle datasets will be documented as blocked"
  warn=$((warn + 1))
fi

if [[ -f "$ROOT/requirements-datasets.txt" ]]; then
  if python3 -c "import yaml" 2>/dev/null; then
    echo "  [ok]   PyYAML             installed"
  else
    echo "  [warn] PyYAML             pip install -r requirements-datasets.txt"
    warn=$((warn + 1))
  fi
fi

echo
echo "Summary: $ok ok, $warn warnings, $fail required missing"
if [[ "$fail" -gt 0 ]]; then
  exit 1
fi
exit 0
