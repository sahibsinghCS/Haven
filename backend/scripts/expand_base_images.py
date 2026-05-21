"""Expand labeled still-image folders with simple offline augmentations.

Used when public API rate limits block bulk downloads. Augmented files are
suffix-tagged (``_aug*``) so re-runs are idempotent.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path

import cv2
import numpy as np
import typer

from roomos.utils.logging import get_logger, setup_logging

app = typer.Typer(add_completion=False, help="Augment data/base_images/<label>/ in place.")
log = get_logger("roomos.scripts.expand_base_images")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _variants(image_bgr: np.ndarray) -> list[tuple[str, np.ndarray]]:
    out: list[tuple[str, np.ndarray]] = []
    h, w = image_bgr.shape[:2]
    if h < 32 or w < 32:
        return out
    out.append(("hflip", cv2.flip(image_bgr, 1)))
    bright = np.clip(image_bgr.astype(np.int16) + 28, 0, 255).astype(np.uint8)
    out.append(("bright", bright))
    dim = np.clip(image_bgr.astype(np.int16) - 28, 0, 255).astype(np.uint8)
    out.append(("dim", dim))
    small = cv2.resize(image_bgr, (max(32, w // 2), max(32, h // 2)), interpolation=cv2.INTER_AREA)
    out.append(("zoom", cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)))
    return out


@app.command()
def main(
    images_root: Path = typer.Option(Path("data/base_images"), "--images-root"),
    target_per_class: int = typer.Option(80, "--target-per-class"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    if not images_root.exists():
        raise typer.BadParameter(f"Missing folder: {images_root}")

    for label_dir in sorted(images_root.iterdir()):
        if not label_dir.is_dir() or label_dir.name.startswith("_"):
            continue
        originals = [
            p
            for p in sorted(label_dir.iterdir())
            if p.is_file()
            and p.suffix.lower() in IMAGE_EXTENSIONS
            and "_aug" not in p.stem
        ]
        if not originals:
            log.warning("No originals in %s", label_dir)
            continue
        created = 0
        idx = 0
        while _count(label_dir) < target_per_class and idx < target_per_class * 20:
            src = originals[idx % len(originals)]
            idx += 1
            image = cv2.imread(str(src))
            if image is None:
                continue
            for tag, variant in _variants(image):
                dest = label_dir / f"{src.stem}_aug{tag}{src.suffix.lower()}"
                if dest.exists():
                    continue
                if cv2.imwrite(str(dest), variant):
                    created += 1
                if _count(label_dir) >= target_per_class:
                    break
        log.info("%s: %d images (%d augmented this run)", label_dir.name, _count(label_dir), created)


def _count(label_dir: Path) -> int:
    return sum(
        1
        for p in label_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


if __name__ == "__main__":
    app()
