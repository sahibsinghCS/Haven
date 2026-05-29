#!/usr/bin/env python3
"""Copy mapped samples from repo-root ``data/raw`` into ``data/base_images/<label>/``.

Bridges external datasets into ``scripts/train_multi_room.py``. Only copies
samples with explicit high/medium-confidence mappings (never silent uncertain→class).

Usage::

    python scripts/ingest_external_datasets.py --max-per-class 200 --datasets all
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import re
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import cv2
import typer
import yaml

from roomos.utils.logging import get_logger, setup_logging

log = get_logger("roomos.scripts.ingest_external_datasets")

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW = REPO_ROOT / "data" / "raw"
MAPPING_PATH = REPO_ROOT / "manifests" / "label_mapping.yaml"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
BASE_IMAGES = BACKEND_ROOT / "data" / "base_images"

ROOMOS_CLASSES = ("work", "gaming", "sleep", "relaxing", "away")
CONFIDENCE_OK = frozenset({"high", "medium"})
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# MIT Indoor 67 categories → (roomos_label, confidence). Longest names first at runtime.
_SCENE_RULES: List[Tuple[str, str, str]] = [
    ("fastfood_restaurant", "relaxing", "low"),
    ("children_room", "relaxing", "low"),
    ("childrenroom", "relaxing", "low"),
    ("meeting_room", "work", "low"),
    ("meetingroom", "work", "low"),
    ("operating_room", "away", "medium"),
    ("operatingroom", "away", "medium"),
    ("inside_subway", "away", "medium"),
    ("insidesubway", "away", "medium"),
    ("inside_bus", "away", "medium"),
    ("insidebus", "away", "medium"),
    ("waitingroom", "away", "medium"),
    ("waiting_room", "away", "medium"),
    ("winecellar", "away", "low"),
    ("computerroom", "work", "medium"),
    ("livingroom", "relaxing", "medium"),
    ("dining_room", "relaxing", "low"),
    ("diningroom", "relaxing", "low"),
    ("gameroom", "gaming", "medium"),
    ("tvroom", "relaxing", "medium"),
    ("staircase", "away", "medium"),
    ("corridor", "away", "medium"),
    ("classroom", "work", "low"),
    ("bedroom", "sleep", "low"),
    ("bathroom", "away", "low"),
    ("kitchen", "relaxing", "low"),
    ("library", "work", "low"),
    ("elevator", "away", "medium"),
    ("warehouse", "away", "medium"),
    ("locker_room", "away", "medium"),
    ("lockerroom", "away", "medium"),
    ("garage", "away", "medium"),
    ("lobby", "away", "medium"),
    ("office", "work", "medium"),
    ("nursery", "sleep", "low"),
]

app = typer.Typer(add_completion=False)


def _load_mapping() -> dict[str, Any]:
    with MAPPING_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _map_action_label(action: str, mapping: dict[str, Any], dataset_id: str) -> Optional[Tuple[str, str]]:
    ds = mapping.get("datasets", {}).get(dataset_id, {})
    norm = action.strip().lower()
    for rule in ds.get("rules", []):
        match = str(rule.get("match", "")).strip().lower()
        if norm == match or match in norm:
            target = rule["target"]
            conf = rule.get("confidence", "medium")
            if target in ("uncertain", "discard"):
                return None
            if conf not in CONFIDENCE_OK:
                return None
            return target, conf
    return None


def _apply_keyword_rules(text: str, mapping: dict[str, Any], dataset_id: str) -> Optional[Tuple[str, str]]:
    ds = mapping.get("datasets", {}).get(dataset_id, {})
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


def _match_scene_from_stem(stem: str) -> Optional[Tuple[str, str]]:
    normalized = re.sub(r"[^a-z0-9]+", "", stem.lower())
    for cat, target, conf in sorted(_SCENE_RULES, key=lambda x: -len(x[0])):
        cat_norm = re.sub(r"[^a-z0-9]+", "", cat.lower())
        if cat_norm and cat_norm in normalized:
            if conf not in CONFIDENCE_OK:
                return None
            return target, conf
    return None


def _indoor_video_roots() -> List[Path]:
    base = RAW / "indoor_action_dataset"
    roots = [base / "IndoorActionDataset-video", base]
    return [r for r in roots if r.is_dir()]


def _normalize_action(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _label_from_path(path: Path) -> str:
    parent = _normalize_action(path.parent.name)
    known = {
        "no-action",
        "no action",
        "watching tv",
        "eating",
        "cleaning",
        "walking",
        "sitting down",
        "standing up",
        "lying on the floor",
        "falling down",
        "blowing nose or sneezing",
        "blowing nose",
    }
    if parent in known or any(k in parent for k in known):
        if parent == "no action":
            return "no-action"
        if "blowing nose" in parent:
            return "blowing nose or sneezing"
        return parent
    return "unknown"


def _iter_indoor_clips() -> Iterable[Tuple[Path, str]]:
    for root in _indoor_video_roots():
        for split in ("train", "validation", "test"):
            split_dir = root / split
            if not split_dir.is_dir():
                continue
            for path in split_dir.rglob("*.mp4"):
                yield path, split


def _copy_image(src: Path, dest: Path, dry_run: bool) -> bool:
    if dest.exists():
        return False
    if dry_run:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in IMAGE_EXTENSIONS:
        shutil.copy2(src, dest)
        return True
    return False


def _extract_video_frame(video: Path, dest: Path, dry_run: bool) -> bool:
    if dest.exists():
        return False
    if dry_run:
        return True
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return False
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, n // 2))
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dest), frame)
    return True


def _safe_name(prefix: str, label: str, stem: str) -> str:
    clean = re.sub(r"[^\w\-]+", "_", stem)[:72]
    return f"{prefix}_{clean}.jpg"


def ingest_indoor_action(
    *,
    max_per_class: int,
    mapping: dict[str, Any],
    dry_run: bool,
    counts: Dict[str, int],
) -> None:
    seen: Set[str] = set()
    for video, split in _iter_indoor_clips():
        action = _label_from_path(video)
        hit = _map_action_label(action, mapping, "indoor_action_dataset")
        if hit is None:
            continue
        roomos_label, _ = hit
        if counts[roomos_label] >= max_per_class:
            continue
        out_name = _safe_name(f"indoor_{split}", roomos_label, video.stem)
        if out_name in seen:
            continue
        seen.add(out_name)
        dest = BASE_IMAGES / roomos_label / out_name
        if _extract_video_frame(video, dest, dry_run):
            counts[roomos_label] += 1


def ingest_indoor_scene(
    *,
    max_per_class: int,
    dry_run: bool,
    counts: Dict[str, int],
) -> None:
    root = RAW / "indoor_scene_recognition_hf"
    if not root.is_dir():
        log.warning("missing %s", root)
        return
    seen: Set[str] = set()
    for src in root.rglob("*.jpg"):
        if ".cache" in src.parts:
            continue
        hit = _match_scene_from_stem(src.stem)
        if hit is None:
            continue
        roomos_label, _ = hit
        if counts[roomos_label] >= max_per_class:
            continue
        out_name = _safe_name("scene", roomos_label, src.stem)
        if out_name in seen:
            continue
        seen.add(out_name)
        dest = BASE_IMAGES / roomos_label / out_name
        if _copy_image(src, dest, dry_run):
            counts[roomos_label] += 1


def ingest_mpii(
    *,
    max_per_class: int,
    mapping: dict[str, Any],
    dry_run: bool,
    counts: Dict[str, int],
) -> None:
    root = RAW / "mpii_human_pose_hf"
    if not root.is_dir():
        log.warning("missing %s (download may still be in progress)", root)
        return
    seen: Set[str] = set()
    for src in root.rglob("*"):
        if not src.is_file() or src.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if ".cache" in src.parts:
            continue
        # Activity may appear in path segments or filename
        text = " ".join(src.parts[-4:])
        hit = _apply_keyword_rules(text, mapping, "mpii_human_pose_hf")
        if hit is None:
            continue
        roomos_label, _ = hit
        if counts[roomos_label] >= max_per_class:
            continue
        out_name = _safe_name("mpii", roomos_label, src.stem)
        if out_name in seen:
            continue
        seen.add(out_name)
        dest = BASE_IMAGES / roomos_label / out_name
        if _copy_image(src, dest, dry_run):
            counts[roomos_label] += 1


@app.command()
def main(
    max_per_class: int = typer.Option(
        200,
        "--max-per-class",
        help="Max NEW images to add per RoomOS label from external sources.",
    ),
    datasets: str = typer.Option(
        "all",
        "--datasets",
        help="Comma-separated ids or 'all' (indoor_action, indoor_scene, mpii).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    setup_logging()
    mapping = _load_mapping()
    if datasets.strip().lower() == "all":
        ids = ["indoor_action_dataset", "indoor_scene_recognition_hf", "mpii_human_pose_hf"]
    else:
        ids = [d.strip() for d in datasets.split(",") if d.strip()]

    # Per-source caps (additive on top of existing base_images).
    added: Dict[str, int] = {c: 0 for c in ROOMOS_CLASSES}

    for ds_id in ids:
        source_added: Dict[str, int] = {c: 0 for c in ROOMOS_CLASSES}
        if ds_id == "indoor_action_dataset":
            ingest_indoor_action(
                max_per_class=max_per_class, mapping=mapping, dry_run=dry_run, counts=source_added
            )
        elif ds_id == "indoor_scene_recognition_hf":
            ingest_indoor_scene(max_per_class=max_per_class, dry_run=dry_run, counts=source_added)
        elif ds_id == "mpii_human_pose_hf":
            ingest_mpii(
                max_per_class=max_per_class, mapping=mapping, dry_run=dry_run, counts=source_added
            )
        else:
            log.warning("unknown dataset id %s", ds_id)
            continue
        for k in ROOMOS_CLASSES:
            added[k] += source_added[k]
        log.info("%s added %s", ds_id, source_added)

    typer.echo(f"New images added per class: {added}")
    typer.echo(f"Sorted into: {BASE_IMAGES}")
    totals = {}
    for label in ROOMOS_CLASSES:
        d = BASE_IMAGES / label
        totals[label] = (
            len([p for p in d.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS])
            if d.is_dir()
            else 0
        )
    typer.echo(f"Total images per class now: {totals}")
    if totals.get("gaming", 0) < 100:
        typer.echo(
            "Gaming is still thin in public data — add local stills: npm run data:capture-stills",
            err=True,
        )


if __name__ == "__main__":
    app()
