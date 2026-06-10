"""On-device per-mood training datasets (frames + cached burst features).

Layout under ``data/personal_datasets/<moodId>/``:

* ``bursts/<burstId>/frame_01.jpg ...``  — raw review frames (deleted after train)
* ``features/<burstId>.json``            — fused feature row cached at capture time
* ``bursts.jsonl``                        — append-only capture metadata

Everything stays on this machine; nothing is uploaded.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.io import append_jsonl
from ..utils.logging import get_logger

log = get_logger("roomos.training.personal_dataset")

# A burst needs at least this many frames to stay usable for training.
MIN_FRAMES_PER_BURST = 3
# Minimum data before a mood can be trained (configurable via API payloads).
MIN_BURSTS_TO_TRAIN = 3
MIN_FRAMES_TO_TRAIN = 15


def _safe_id(value: str) -> str:
    v = str(value or "").strip()
    if not v or "/" in v or "\\" in v or ".." in v:
        raise ValueError(f"Invalid identifier: {value!r}")
    return v


def mood_dataset_dir(root: Path, mood_id: str) -> Path:
    return Path(root) / _safe_id(mood_id)


def burst_dir(root: Path, mood_id: str, burst_id: str) -> Path:
    return mood_dataset_dir(root, mood_id) / "bursts" / _safe_id(burst_id)


def features_dir(root: Path, mood_id: str) -> Path:
    return mood_dataset_dir(root, mood_id) / "features"


def frame_path(root: Path, mood_id: str, burst_id: str, frame_name: str) -> Path:
    name = _safe_id(frame_name)
    if not name.lower().endswith(".jpg"):
        raise ValueError(f"Invalid frame name: {frame_name!r}")
    return burst_dir(root, mood_id, burst_id) / name


def append_burst_metadata(root: Path, mood_id: str, record: Dict[str, Any]) -> None:
    append_jsonl(mood_dataset_dir(root, mood_id) / "bursts.jsonl", record)


def write_feature_cache(
    root: Path,
    mood_id: str,
    burst_id: str,
    *,
    features: Dict[str, float],
    metadata: Dict[str, Any],
    n_frames: int,
) -> None:
    fdir = features_dir(root, mood_id)
    fdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "burstId": burst_id,
        "nFrames": int(n_frames),
        "metadata": metadata,
        "features": {k: float(v) for k, v in features.items()},
    }
    (fdir / f"{_safe_id(burst_id)}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def list_bursts(root: Path, mood_id: str) -> List[Dict[str, Any]]:
    """Bursts for the review UI, newest first."""
    bursts_root = mood_dataset_dir(root, mood_id) / "bursts"
    meta_by_id: Dict[str, Dict[str, Any]] = {}
    meta_file = mood_dataset_dir(root, mood_id) / "bursts.jsonl"
    if meta_file.is_file():
        try:
            for line in meta_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if isinstance(rec, dict) and rec.get("burstId"):
                    meta_by_id[str(rec["burstId"])] = rec
        except (OSError, json.JSONDecodeError) as e:
            log.debug("Could not parse bursts.jsonl for %s: %s", mood_id, e)

    out: List[Dict[str, Any]] = []
    if not bursts_root.is_dir():
        return out
    for d in sorted(bursts_root.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        frames = sorted(f.name for f in d.glob("frame_*.jpg"))
        if not frames:
            continue
        meta = meta_by_id.get(d.name, {})
        out.append(
            {
                "id": d.name,
                "frames": frames,
                "frameCount": len(frames),
                "capturedAt": meta.get("capturedAt"),
                "meanLuma": meta.get("meanLuma"),
                "blurScore": meta.get("blurScore"),
            }
        )
    return out


def dataset_counts(root: Path, mood_id: str) -> Dict[str, int]:
    """Bursts usable for training: on-disk frames OR cached features."""
    burst_frames: Dict[str, int] = {}
    bursts_root = mood_dataset_dir(root, mood_id) / "bursts"
    if bursts_root.is_dir():
        for d in bursts_root.iterdir():
            if d.is_dir():
                n = len(list(d.glob("frame_*.jpg")))
                if n >= MIN_FRAMES_PER_BURST:
                    burst_frames[d.name] = n
    fdir = features_dir(root, mood_id)
    if fdir.is_dir():
        for f in fdir.glob("*.json"):
            bid = f.stem
            if bid not in burst_frames:
                try:
                    payload = json.loads(f.read_text(encoding="utf-8"))
                    burst_frames[bid] = int(payload.get("nFrames", 0))
                except (OSError, json.JSONDecodeError, ValueError):
                    continue
    return {
        "burstCount": len(burst_frames),
        "frameCount": sum(burst_frames.values()),
    }


def delete_burst(root: Path, mood_id: str, burst_id: str) -> bool:
    removed = False
    bdir = burst_dir(root, mood_id, burst_id)
    if bdir.is_dir():
        shutil.rmtree(bdir, ignore_errors=True)
        removed = True
    fpath = features_dir(root, mood_id) / f"{_safe_id(burst_id)}.json"
    if fpath.is_file():
        fpath.unlink(missing_ok=True)
        removed = True
    return removed


def delete_frame(root: Path, mood_id: str, burst_id: str, frame_name: str) -> bool:
    """Delete one frame. Invalidates the burst's cached features; if too few
    frames remain the whole burst is dropped."""
    fpath = frame_path(root, mood_id, burst_id, frame_name)
    if not fpath.is_file():
        return False
    fpath.unlink()
    cache = features_dir(root, mood_id) / f"{_safe_id(burst_id)}.json"
    cache.unlink(missing_ok=True)
    remaining = list(burst_dir(root, mood_id, burst_id).glob("frame_*.jpg"))
    if len(remaining) < MIN_FRAMES_PER_BURST:
        delete_burst(root, mood_id, burst_id)
    return True


def clear_raw_frames(root: Path, mood_id: str) -> int:
    """Post-training privacy cleanup: delete raw JPEGs, keep cached features."""
    bursts_root = mood_dataset_dir(root, mood_id) / "bursts"
    if not bursts_root.is_dir():
        return 0
    removed = 0
    for d in list(bursts_root.iterdir()):
        if d.is_dir():
            removed += len(list(d.glob("frame_*.jpg")))
            shutil.rmtree(d, ignore_errors=True)
    return removed


def moods_with_data(root: Path) -> List[str]:
    p = Path(root)
    if not p.is_dir():
        return []
    out = []
    for d in sorted(p.iterdir()):
        if d.is_dir() and dataset_counts(p, d.name)["burstCount"] > 0:
            out.append(d.name)
    return out
