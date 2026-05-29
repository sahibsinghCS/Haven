#!/usr/bin/env python3
"""Ingest MPII Human Pose (Voxel51/FiftyOne) into ``data/base_images/<label>/``.

Uses activity metadata from the FiftyOne dataset (not filenames).

Usage (backend venv via npm)::

    python scripts/ingest_mpii_fiftyone.py --max-per-class 300
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

import typer
import yaml

from roomos.utils.logging import get_logger, setup_logging

log = get_logger("roomos.scripts.ingest_mpii_fiftyone")

REPO_ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = REPO_ROOT / "manifests" / "label_mapping.yaml"
BASE_IMAGES = Path(__file__).resolve().parents[1] / "data" / "base_images"
MPII_LOCAL = REPO_ROOT / "data" / "raw" / "mpii_human_pose_hf"

ROOMOS_CLASSES = ("work", "gaming", "sleep", "relaxing", "away")
CONFIDENCE_OK = frozenset({"high", "medium"})

app = typer.Typer(add_completion=False)


def _load_mapping() -> dict[str, Any]:
    with MAPPING_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _map_activity(activity: str, mapping: dict[str, Any]) -> Optional[Tuple[str, str]]:
    ds = mapping.get("datasets", {}).get("mpii_human_pose_hf", {})
    text = (activity or "").strip()
    if not text:
        return None
    lower = text.lower()
    for pat in ds.get("discard_patterns", []):
        if pat.lower() in lower:
            return None
    for rule in ds.get("keyword_rules", []):
        for pat in rule.get("patterns", []):
            if pat.lower() in lower:
                target = rule["target"]
                conf = rule.get("confidence", "medium")
                if target in ("uncertain", "discard") or conf not in CONFIDENCE_OK:
                    return None
                return target, conf
    return None


def _activity_name(sample) -> str:
    act = getattr(sample, "activity", None)
    if act is None:
        return ""
    if hasattr(act, "label"):
        return str(act.label or "")
    if hasattr(act, "labels") and act.labels:
        return str(act.labels[0] or "")
    return str(act)


def _safe_name(label: str, sample_id: str) -> str:
    clean = re.sub(r"[^\w\-]+", "_", str(sample_id))[:72]
    return f"mpii_{clean}.jpg"


@app.command()
def main(
    max_per_class: int = typer.Option(300, "--max-per-class"),
    max_samples: int = typer.Option(
        0,
        "--max-samples",
        help="Cap MPII samples scanned (0 = all).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    setup_logging()
    mapping = _load_mapping()
    counts: Dict[str, int] = {c: 0 for c in ROOMOS_CLASSES}
    seen: Set[str] = set()
    skipped = 0
    scanned = 0

    try:
        import fiftyone as fo
        import fiftyone.utils.huggingface as fouh
    except ImportError as e:
        raise typer.BadParameter(
            "fiftyone not installed. Run: npm run python -- -m pip install -r requirements-data.txt"
        ) from e

    log.info("Loading MPII from Hugging Face (uses local cache if present)...")
    kwargs: dict[str, Any] = {}
    if max_samples > 0:
        kwargs["max_samples"] = max_samples
    dataset = fouh.load_from_hub("Voxel51/MPII_Human_Pose_Dataset", **kwargs)

    for sample in dataset:
        scanned += 1
        activity = _activity_name(sample)
        hit = _map_activity(activity, mapping)
        if hit is None:
            skipped += 1
            continue
        roomos_label, _conf = hit
        if counts[roomos_label] >= max_per_class:
            continue
        src = Path(sample.filepath)
        if not src.is_file():
            skipped += 1
            continue
        out_name = _safe_name(roomos_label, sample.id)
        if out_name in seen:
            continue
        seen.add(out_name)
        dest = BASE_IMAGES / roomos_label / out_name
        if dry_run:
            counts[roomos_label] += 1
            continue
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        counts[roomos_label] += 1
        if sum(counts.values()) % 100 == 0 and sum(counts.values()) > 0:
            log.info("ingested so far: %s", counts)

    typer.echo(f"Scanned {scanned} MPII samples; skipped/unmapped {skipped}")
    typer.echo(f"Added per class: {counts}")
    totals = {}
    for label in ROOMOS_CLASSES:
        d = BASE_IMAGES / label
        totals[label] = len(list(d.glob("*.jpg"))) if d.is_dir() else 0
    typer.echo(f"Total jpg per class now: {totals}")


if __name__ == "__main__":
    app()
