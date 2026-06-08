"""Source high-quality *adult-in-bed* sleep images from the Pexels API.

Pexels photos are free to use (Pexels License: commercial OK, no attribution
required) which keeps the dataset license-safe. This script:

1. Searches Pexels for several "person sleeping in bed" style queries.
2. Downloads candidates and runs the same adult-in-bed CLIP gate used by
   ``clean_sleep_bed.py`` (good = asleep in a bedroom bed; bad = floor / couch /
   baby / outdoors) **plus** extra "awake in bed" negatives so that
   awake-in-bed (which is RoomOS ``relaxing``) is rejected, not labeled sleep.
3. De-duplicates by Pexels photo id and by content hash.
4. Writes keepers as ``person_sleeping_bed_NNN.jpg`` into BOTH
   ``data/base_images/sleep/`` and ``data/raw_images/sleep/`` (numbering
   continues past any existing ``person_sleeping_bed_*`` files).
5. Writes a manifest CSV: filename, source, license, description (+ pexels id,
   photographer, url, clip scores).

Run from ``backend/``::

    python scripts/import_sleep_pexels.py --target 200 --pexels-key <KEY>
    PEXELS_API_KEY=<KEY> python scripts/import_sleep_pexels.py --target 200 --dry-run
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import typer

from roomos.config import load_config
from roomos.features.clip_extractor import ClipExtractor
from roomos.utils.io import ensure_dir
from roomos.utils.logging import get_logger, setup_logging

from clean_sleep_bed import BED_BAD, BED_GOOD

# Make logging safe on Windows consoles (photographer names contain unicode).
try:  # pragma: no cover - environment dependent
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

DEFAULT_CONFIG = Path("configs/inference.yaml")
PEXELS_SEARCH = "https://api.pexels.com/v1/search"
PEXELS_LICENSE = "Pexels License (free to use, commercial OK, attribution not required)"
NAME_PREFIX = "person_sleeping_bed"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

log = get_logger("roomos.scripts.import_sleep_pexels")

# Extra negatives. Pexels "sleep" searches are dominated by empty-bed product
# shots, people making the bed, morning-coffee-in-bed, and awake-in-bed (which
# is RoomOS "relaxing"). These push all of that OUT of the sleep class.
AWAKE_BAD = [
    # awake in bed -> relaxing, not sleep
    "a person awake in bed looking at a smartphone",
    "a person sitting up awake in bed reading a book",
    "a person awake and smiling in bed",
    "a person awake watching television in bed",
    "a person sitting upright on the bed awake",
    # empty beds -> away, not sleep
    "an empty unmade bed with no person",
    "an empty neatly made bed in a bedroom",
    "a close-up of bedding and sheets with no person",
    "a made bed with decorative pillows and no person",
    # bed chores / staging -> not sleep
    "a person making the bed",
    "a person arranging pillows on a bed",
    "hands smoothing a bedsheet",
    "folded laundry and towels on a bed",
    "a cup of coffee on a bed in the morning",
    # studio / not a bedroom
    "a person wrapped in a blanket standing in a studio",
    "a person sitting wrapped in a blanket against a white wall",
]

# Queries chosen to bias toward asleep people in real bedrooms (avoid terms like
# "bedding"/"morning"/"made bed" that surface product/chore stock).
DEFAULT_QUERIES = [
    "person sleeping in bed",
    "man sleeping in bed",
    "woman sleeping in bed",
    "person asleep eyes closed pillow",
    "person sleeping on side bed",
    "person sleeping under blanket night",
    "person fast asleep in bed",
    "tired person sleeping pillow",
    "person napping in bed",
    "couple sleeping in bed",
    "man asleep bed night",
    "woman asleep bed pillow",
    "bedroom interior person sleeping in bed",
    "wide bedroom person asleep in bed",
    "person sleeping hotel room bed",
    "person sleeping dorm bunk bed",
    "elderly person sleeping in bed",
    "young adult sleeping bedroom bed",
    "person sleeping peacefully bedroom",
    "sleeping in bed cozy bedroom",
]

app = typer.Typer(add_completion=False, help="Import Pexels adult-in-bed sleep photos (CLIP-gated).")


def _ascii(text: str) -> str:
    return (text or "").encode("ascii", "replace").decode("ascii")


def _existing_max_index(*dirs: Path) -> int:
    pat = re.compile(rf"^{re.escape(NAME_PREFIX)}_(\d+)\b")
    best = -1
    for d in dirs:
        if not d.is_dir():
            continue
        for p in d.iterdir():
            m = pat.match(p.stem)
            if m:
                best = max(best, int(m.group(1)))
    return best


def _pexels_search(key: str, query: str, page: int, per_page: int) -> dict:
    params = urllib.parse.urlencode(
        {"query": query, "per_page": per_page, "page": page, "size": "large"}
    )
    req = urllib.request.Request(
        f"{PEXELS_SEARCH}?{params}",
        headers={"Authorization": key, "User-Agent": "RoomOS-data/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, timeout: float = 30.0) -> Optional[bytes]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RoomOS-data/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:  # pragma: no cover - network
        log.debug("download failed %s (%s)", url[:80], e)
        return None


def _decode_bgr(data: bytes) -> Optional[np.ndarray]:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _clip_scores(
    extractor: ClipExtractor, image_bgr: np.ndarray, n_good: int
) -> Tuple[float, float, int]:
    sims = extractor.extract(image_bgr).prompt_sim
    good = float(sims[:n_good].max()) if n_good else 0.0
    bad = float(sims[n_good:].max()) if len(sims) > n_good else 0.0
    bad_idx = int(sims[n_good:].argmax()) if len(sims) > n_good else 0
    return good, bad, bad_idx


@app.command()
def main(
    pexels_key: str = typer.Option(
        "", "--pexels-key", help="Pexels API key (or set PEXELS_API_KEY env var)."
    ),
    target: int = typer.Option(200, "--target", help="How many gated keepers to collect."),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    out_dir: Path = typer.Option(Path("data/base_images"), "--out-dir"),
    raw_dir: Path = typer.Option(Path("data/raw_images"), "--raw-dir"),
    per_page: int = typer.Option(80, "--per-page", help="Pexels page size (max 80)."),
    max_pages: int = typer.Option(8, "--max-pages", help="Max pages per query."),
    min_short_side: int = typer.Option(480, "--min-short-side"),
    margin: float = typer.Option(0.02, "--margin", help="CLIP: bad must be below good by this."),
    min_good: float = typer.Option(0.20, "--min-good", help="CLIP: minimum best good-prompt score."),
    sleep_sec: float = typer.Option(0.4, "--sleep-sec", help="Delay between API/page calls."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Search + gate, but write nothing."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    key = pexels_key.strip() or os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        raise typer.BadParameter("Provide --pexels-key or set PEXELS_API_KEY.")

    cfg = load_config(config)
    base_root = out_dir if out_dir.is_absolute() else cfg.resolve_path(out_dir)
    raw_root = raw_dir if raw_dir.is_absolute() else cfg.resolve_path(raw_dir)
    sleep_base = ensure_dir(base_root / "sleep")
    sleep_raw = ensure_dir(raw_root / "sleep")
    manifest_dir = ensure_dir(base_root / "_manifests")
    manifest_csv = manifest_dir / "sleep_manifest.csv"
    legacy_pexels_csv = manifest_dir / "sleep_pexels_manifest.csv"

    prompts = BED_GOOD + BED_BAD + AWAKE_BAD
    n_good = len(BED_GOOD)
    bad_prompts = BED_BAD + AWAKE_BAD

    clip_cfg = dict(cfg.features.get("clip", {}))
    extractor = ClipExtractor(
        model_name=str(clip_cfg.get("model_name", "ViT-B-32")),
        pretrained=str(clip_cfg.get("pretrained", "laion2b_s34b_b79k")),
        device=str(clip_cfg.get("device", "auto")),
        prompts=prompts,
        keep_embedding=False,
    )

    start_index = _existing_max_index(sleep_base, sleep_raw) + 1
    next_index = start_index

    seen_ids: set[int] = set()
    seen_hashes: set[str] = set()
    # Seed seen Pexels ids from the manifest. The manifest records EVERY photo
    # that ever passed the gate (including ones later curated out), so this
    # prevents reruns from re-adding duplicates *or* previously-removed junk.
    # (Hash-seeding from disk fails because saved files are re-encoded JPEGs
    # whose bytes differ from the freshly downloaded originals.)
    def _seed_ids_from_csv(path: Path) -> int:
        n = 0
        if not path.exists():
            return 0
        with path.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                prov = (row.get("provider") or "pexels").strip().lower()
                if prov not in ("", "pexels"):
                    continue
                sid = row.get("source_id") or row.get("pexels_id") or ""
                try:
                    pid = int(sid)
                except ValueError:
                    continue
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    n += 1
        return n

    try:
        seeded = _seed_ids_from_csv(manifest_csv) + _seed_ids_from_csv(legacy_pexels_csv)
        log.info("Seeded %d Pexels ids from manifest(s) to skip (total %d).", seeded, len(seen_ids))
    except Exception as e:  # pragma: no cover
        log.warning("Could not read manifest for id-seed (%s).", e)

    manifest_rows: List[Dict[str, object]] = []

    kept = 0
    tried = 0
    rej_clip = 0
    rej_small = 0
    rej_dup = 0

    log.info(
        "Pexels sleep import | target=%d start_index=%03d queries=%d dry_run=%s",
        target,
        start_index,
        len(DEFAULT_QUERIES),
        dry_run,
    )

    with extractor:
        for query in DEFAULT_QUERIES:
            if kept >= target:
                break
            for page in range(1, max_pages + 1):
                if kept >= target:
                    break
                try:
                    payload = _pexels_search(key, query, page, per_page)
                except Exception as e:
                    log.warning("search failed q=%r page=%d (%s)", query, page, e)
                    break
                photos = payload.get("photos", [])
                if not photos:
                    break
                time.sleep(sleep_sec)

                for photo in photos:
                    if kept >= target:
                        break
                    pid = int(photo.get("id", 0))
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    tried += 1

                    src = photo.get("src", {})
                    url = src.get("large2x") or src.get("large") or src.get("original")
                    if not url:
                        continue

                    data = _download(url)
                    if not data:
                        continue
                    digest = hashlib.md5(data).hexdigest()
                    if digest in seen_hashes:
                        rej_dup += 1
                        continue

                    image = _decode_bgr(data)
                    if image is None:
                        continue
                    h, w = image.shape[:2]
                    if min(h, w) < min_short_side:
                        rej_small += 1
                        continue

                    good, bad, bad_idx = _clip_scores(extractor, image, n_good)
                    ok = good >= min_good and bad < good - margin
                    if not ok:
                        rej_clip += 1
                        continue

                    seen_hashes.add(digest)
                    fname = f"{NAME_PREFIX}_{next_index:03d}.jpg"
                    alt = _ascii(str(photo.get("alt", "")))[:140]
                    if not dry_run:
                        ok_write, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                        if not ok_write:
                            continue
                        (sleep_base / fname).write_bytes(buf.tobytes())
                        (sleep_raw / fname).write_bytes(buf.tobytes())

                    manifest_rows.append(
                        {
                            "filename": fname,
                            "source": f"Pexels (id={pid}, photographer={_ascii(str(photo.get('photographer','')))})",
                            "license": PEXELS_LICENSE,
                            "description": alt or "person sleeping in a bedroom bed",
                            "provider": "pexels",
                            "source_id": str(pid),
                            "source_url": photo.get("url", ""),
                        }
                    )
                    next_index += 1
                    kept += 1
                    if kept % 10 == 0 or kept <= 5:
                        log.info(
                            "+%d/%d %s (good=%.3f bad=%.3f) q=%r",
                            kept,
                            target,
                            fname,
                            good,
                            bad,
                            query,
                        )

    if manifest_rows and not dry_run:
        write_header = not manifest_csv.exists()
        fieldnames = ["filename", "source", "license", "description", "provider", "source_id", "source_url"]
        with manifest_csv.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerows(manifest_rows)

    log.info("=" * 64)
    log.info(
        "DONE | kept=%d tried=%d clip_rejected=%d too_small=%d dup=%d dry_run=%s",
        kept,
        tried,
        rej_clip,
        rej_small,
        rej_dup,
        dry_run,
    )
    log.info(
        "Wrote %s -> %s and %s",
        f"{NAME_PREFIX}_{start_index:03d}..{NAME_PREFIX}_{next_index-1:03d}.jpg" if kept else "(nothing)",
        sleep_base,
        sleep_raw,
    )
    if not dry_run and manifest_rows:
        log.info("Manifest: %s (+%d rows)", manifest_csv, len(manifest_rows))


if __name__ == "__main__":
    app()
