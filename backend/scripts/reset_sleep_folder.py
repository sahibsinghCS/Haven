"""Wipe ``sleep/`` training folders so you can use only ``person_sleeping_bed_*.jpg``.

Does **not** restore from ``_rejected/sleep/``. Deletes:

* ``data/base_images/sleep/*``
* ``data/base_images/_rejected/sleep/*``
* optional ``data/raw_images/sleep/*``

Run from ``backend/``::

    python scripts/reset_sleep_folder.py
    python scripts/reset_sleep_folder.py --include-raw-images
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

from pathlib import Path

import typer

from roomos.utils.logging import get_logger, setup_logging

log = get_logger("roomos.scripts.reset_sleep_folder")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

app = typer.Typer(add_completion=False, help="Clear sleep folders (no restore from _rejected).")


def _delete_files_in(dir_path: Path) -> int:
    if not dir_path.is_dir():
        return 0
    n = 0
    for p in dir_path.iterdir():
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
            p.unlink(missing_ok=True)
            n += 1
    return n


@app.command()
def main(
    include_raw_images: bool = typer.Option(
        False,
        "--include-raw-images",
        help="Also clear data/raw_images/sleep/ (used by train:my-room).",
    ),
) -> None:
    setup_logging()
    root = Path("data")
    targets = [
        root / "base_images" / "sleep",
        root / "base_images" / "_rejected" / "sleep",
    ]
    if include_raw_images:
        targets.append(root / "raw_images" / "sleep")

    total = 0
    for d in targets:
        d.mkdir(parents=True, exist_ok=True)
        n = _delete_files_in(d)
        total += n
        log.info("Cleared %d files from %s", n, d.resolve())

    log.info("DONE | deleted %d files total", total)
    log.info(
        "Copy your person_sleeping_bed_000.jpg … person_sleeping_bed_107.jpg into:\n"
        "  %s\n"
        "For train:my-room also copy into:\n"
        "  %s",
        (root / "base_images" / "sleep").resolve(),
        (root / "raw_images" / "sleep").resolve(),
    )


if __name__ == "__main__":
    app()
