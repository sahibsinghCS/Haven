"""Add adult-in-bed sleep images to ``data/base_images/sleep/`` (additive only).

Downloads from Wikimedia Commons categories (see ``configs/base_image_sources.yaml``
sleep.wikimedia_categories) and **only keeps** images that pass a CLIP gate for
"person asleep in bed" vs floor/couch/baby prompts. Existing files in ``sleep/``
are never modified or removed.

Run from ``backend/``::

    python scripts/import_sleep_bed.py --target-add 200
    python scripts/import_sleep_bed.py --target-add 100 --dry-run
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import time
from pathlib import Path

import cv2
import typer

from roomos.config import load_config
from roomos.features.clip_extractor import ClipExtractor
from roomos.utils.logging import get_logger, setup_logging

from clean_sleep_bed import BED_BAD, BED_GOOD
from import_base_images import (
    _commons_category_files,
    _commons_file_info,
    _count_images,
    _download_url,
    _load_sources,
)
from roomos.utils.io import ensure_dir

DEFAULT_CONFIG = Path("configs/inference.yaml")
DEFAULT_SOURCES = Path("configs/base_image_sources.yaml")

log = get_logger("roomos.scripts.import_sleep_bed")

app = typer.Typer(add_completion=False, help="Import CLIP-filtered adult-in-bed sleep photos.")


def _clip_passes(
    extractor: ClipExtractor,
    image_bgr,
    *,
    n_good: int,
    margin: float,
    min_good: float,
) -> tuple[bool, float, float]:
    sims = extractor.extract(image_bgr).prompt_sim
    good = float(sims[:n_good].max()) if n_good else 0.0
    bad = float(sims[n_good:].max()) if len(sims) > n_good else 0.0
    ok = good >= min_good and bad < good - margin
    return ok, good, bad


@app.command()
def main(
    out_dir: Path = typer.Option(Path("data/base_images"), "--out-dir"),
    sources_config: Path = typer.Option(DEFAULT_SOURCES, "--sources-config"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    target_add: int = typer.Option(200, "--target-add", help="How many new images to add."),
    margin: float = typer.Option(0.02, "--margin", help="CLIP: bad must be below good by this."),
    min_good: float = typer.Option(0.20, "--min-good", help="CLIP: minimum best bed-prompt score."),
    sleep_sec: float = typer.Option(0.85, "--sleep-sec"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)
    root = out_dir if out_dir.is_absolute() else cfg.resolve_path(out_dir)
    sleep_dir = ensure_dir(root / "sleep")
    manifest_dir = ensure_dir(root / "_manifests")

    sources_path = sources_config if sources_config.is_absolute() else cfg.resolve_path(sources_config)
    all_cfg = _load_sources(sources_path)
    sleep_spec = all_cfg.get("sleep")
    if not sleep_spec:
        raise typer.BadParameter("No 'sleep' label in base_image_sources.yaml")

    categories = list(sleep_spec.get("wikimedia_categories", []))
    if not categories:
        raise typer.BadParameter("sleep has no wikimedia_categories")

    before = _count_images(sleep_dir)
    target = before + max(1, target_add)
    log.info(
        "sleep/ has %d images; adding up to %d (target %d) | categories=%d dry_run=%s",
        before,
        target_add,
        target,
        len(categories),
        dry_run,
    )

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

    added = 0
    tried = 0
    rejected_clip = 0

    with extractor:
        for category in categories:
            if added >= target_add:
                break
            need = target_add - added
            for page in _commons_category_files(category, limit=max(80, need * 4)):
                if added >= target_add:
                    break
                tried += 1
                info = _commons_file_info(page["title"])
                time.sleep(sleep_sec)
                url = info.get("url")
                if not url:
                    continue

                if dry_run:
                    log.info("[dry-run] would try %s", page.get("title", "")[:60])
                    continue

                item = _download_url(
                    label="sleep",
                    provider="wikimedia_bed",
                    url=str(url),
                    title=str(page.get("title", "")),
                    out_dir=root,
                    manifest_dir=manifest_dir,
                    license_name=str(info.get("license", "")),
                    license_url=str(info.get("license_url", "")),
                )
                if item is None:
                    continue

                image = cv2.imread(str(item.path))
                if image is None:
                    item.path.unlink(missing_ok=True)
                    continue

                ok, good, bad = _clip_passes(
                    extractor, image, n_good=n_good, margin=margin, min_good=min_good
                )
                if not ok:
                    rejected_clip += 1
                    item.path.unlink(missing_ok=True)
                    log.debug(
                        "CLIP reject %s good=%.3f bad=%.3f",
                        item.path.name,
                        good,
                        bad,
                    )
                    continue

                added += 1
                log.info(
                    "+%d/%d %s (good=%.3f bad=%.3f) from %s",
                    added,
                    target_add,
                    item.path.name,
                    good,
                    bad,
                    category,
                )

    after = _count_images(sleep_dir)
    log.info(
        "DONE | before=%d after=%d added=%d tried=%d clip_rejected=%d dry_run=%s",
        before,
        after,
        after - before,
        tried,
        rejected_clip,
        dry_run,
    )


if __name__ == "__main__":
    app()
