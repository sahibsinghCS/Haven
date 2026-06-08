"""Keep only *adult-in-bed* sleep training images; quarantine the rest.

Public datasets often dump floor naps, couch sleep, and babies into ``sleep/``.
This script scores each image in ``data/base_images/sleep/`` with targeted CLIP
prompts and moves poor matches to ``_rejected/sleep/``.

Run from ``backend/``::

    python scripts/clean_sleep_bed.py --dry-run
    python scripts/clean_sleep_bed.py
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import csv
import json
import shutil
import time
from pathlib import Path
from typing import List

import cv2
import typer

from roomos.config import load_config
from roomos.features.clip_extractor import ClipExtractor
from roomos.utils.logging import get_logger, setup_logging

DEFAULT_CONFIG = Path("configs/inference.yaml")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

log = get_logger("roomos.scripts.clean_sleep_bed")

# What we want RoomOS "sleep" to mean at inference time.
BED_GOOD = [
    "an adult person sleeping in a bed under blankets",
    "a person lying asleep in a bedroom bed on a mattress",
    "a person curled up asleep under blankets in bed",
    "an adult sleeping in a double bed in a bedroom",
    "a person asleep lying on their side in bed",
]

# Common junk in scraped ``sleep/`` folders.
BED_BAD = [
    "a baby sleeping in a crib",
    "an infant sleeping in a nursery",
    "a newborn baby asleep",
    "a toddler sleeping on the floor",
    "a person sleeping on the floor",
    "a person sleeping on the ground outdoors",
    "a person napping on a couch in the living room",
    "a person sleeping sitting up in a chair",
    "a dog sleeping on the floor",
]

app = typer.Typer(add_completion=False, help="Filter sleep/ to adult-in-bed images only.")


def _discover(label_dir: Path) -> List[Path]:
    return sorted(
        p for p in label_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def _quarantine(reject_dir: Path, src: Path) -> Path:
    reject_dir.mkdir(parents=True, exist_ok=True)
    dest = reject_dir / src.name
    if dest.exists():
        stem, suffix = src.stem, src.suffix
        i = 1
        while dest.exists():
            dest = reject_dir / f"{stem}__dup{i}{suffix}"
            i += 1
    return dest


@app.command()
def main(
    images_dir: Path = typer.Option(Path("data/base_images"), "--images-dir"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    reject_dirname: str = typer.Option("_rejected", "--reject-dirname"),
    margin: float = typer.Option(
        0.02,
        "--margin",
        help="Flag when max(bad) >= max(good) - margin (CLIP cosines are close).",
    ),
    min_good: float = typer.Option(
        0.20,
        "--min-good",
        help="Also flag when best bed prompt score is below this (weak bed signal).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
    limit: int = typer.Option(0, "--limit"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)
    root = images_dir if images_dir.is_absolute() else cfg.resolve_path(images_dir)
    sleep_dir = root / "sleep"
    if not sleep_dir.is_dir():
        raise typer.BadParameter(f"Missing {sleep_dir}")

    reject_dir = root / reject_dirname / "sleep"
    prompts = BED_GOOD + BED_BAD
    n_good = len(BED_GOOD)

    clip_cfg = dict(cfg.features.get("clip", {}))
    extractor = ClipExtractor(
        model_name=str(clip_cfg.get("model_name", "ViT-B-32")),
        pretrained=str(clip_cfg.get("pretrained", "laion2b_s34b_b79k")),
        device=str(clip_cfg.get("device", "auto")),
        prompts=prompts,
        keep_embedding=False,
    )

    images = _discover(sleep_dir)
    if limit > 0:
        images = images[:limit]

    rows: list[dict] = []
    flagged = 0
    started = time.time()

    with extractor:
        for i, path in enumerate(images, 1):
            image = cv2.imread(str(path))
            if image is None:
                log.warning("Unreadable: %s", path)
                continue
            sims = extractor.extract(image).prompt_sim
            good = float(sims[:n_good].max()) if n_good else 0.0
            bad = float(sims[n_good:].max()) if len(sims) > n_good else 0.0
            best_bad_idx = int(sims[n_good:].argmax()) if len(sims) > n_good else 0
            best_bad = BED_BAD[best_bad_idx] if best_bad_idx < len(BED_BAD) else ""

            flag = bad >= good - margin or good < min_good
            reason = []
            if bad >= good - margin:
                reason.append(f"bad>={good - margin:.3f} (bad={bad:.3f} good={good:.3f})")
            if good < min_good:
                reason.append(f"weak bed signal (good={good:.3f} < {min_good})")
            if best_bad and flag:
                reason.append(f"top bad: {best_bad[:50]}")

            row = {
                "file": str(path),
                "good_score": round(good, 4),
                "bad_score": round(bad, 4),
                "flagged": flag,
                "reason": "; ".join(reason) or "kept",
                "action": "kept",
            }
            if flag:
                flagged += 1
                if dry_run:
                    row["action"] = "would-quarantine"
                else:
                    dest = _quarantine(reject_dir, path)
                    shutil.move(str(path), str(dest))
                    row["action"] = "quarantined"
                    row["moved_to"] = str(dest)
            rows.append(row)

            if i % 50 == 0:
                log.info("...%d/%d (%d flagged)", i, len(images), flagged)

    report = reject_dir.parent / "clean_sleep_bed_report.csv"
    reject_dir.parent.mkdir(parents=True, exist_ok=True)
    with report.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["file", "good_score", "bad_score", "flagged", "reason", "action", "moved_to"]
        )
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})

    summary = {
        "sleep_dir": str(sleep_dir),
        "seen": len(rows),
        "flagged": flagged,
        "kept": len(rows) - flagged,
        "dry_run": dry_run,
        "margin": margin,
        "min_good": min_good,
        "report_csv": str(report),
        "elapsed_sec": round(time.time() - started, 1),
    }
    (reject_dir.parent / "clean_sleep_bed_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    log.info("DONE | seen=%d flagged=%d kept=%d | report=%s", len(rows), flagged, len(rows) - flagged, report)


if __name__ == "__main__":
    app()
