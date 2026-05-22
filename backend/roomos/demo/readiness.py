"""Check whether a trained model bundle exists for live demo."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from ..config import Config, load_config
from ..model.registry import MODEL_ARTIFACT_FILES

DEFAULT_INFERENCE_CONFIG = Path("configs/inference.yaml")


def resolve_bundle_dir(cfg: Optional[Config] = None) -> Path:
    if cfg is None:
        cfg = load_config(DEFAULT_INFERENCE_CONFIG)
    raw = (cfg.get("inference", {}) or {}).get("model_dir", "data/models/latest")
    p = Path(raw)
    return p if p.is_absolute() else cfg.resolve_path(p)


def bundle_readiness(bundle_dir: str | Path) -> dict[str, Any]:
    """Return structured readiness without importing heavy ML deps."""
    bundle = Path(bundle_dir)
    missing = [name for name in MODEL_ARTIFACT_FILES if not (bundle / name).exists()]
    return {
        "bundle_dir": str(bundle.resolve()),
        "ready": len(missing) == 0,
        "missing_artifacts": missing,
    }


def format_missing_model_help(*, bundle_dir: str | Path) -> str:
    return (
        "No trained model found for live inference.\n\n"
        f"  Expected bundle: {Path(bundle_dir).resolve()}\n"
        "  Required files: model.json, label_encoder.json, feature_columns.json\n\n"
        "Fix (from repo root, ~5–15 min on first run — downloads OpenCLIP):\n"
        "  npm run setup:model\n"
        "  npm run train:verify\n"
        "  npm run demo\n"
    )
