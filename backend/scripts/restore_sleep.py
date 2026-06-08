"""Restore ``data/base_images/sleep/`` from local backups (not git).

**Warning:** ``_rejected/sleep/`` holds images the cleaners flagged as wrong
(floor/baby/mislabeled). Do not use this if you only want ``person_sleeping_bed_*``
stills — use ``reset_sleep_folder.py`` instead.

``backend/data/`` is gitignored — git cannot recover these files.

This script:
1. Moves/copies everything from ``_rejected/sleep/`` back into ``sleep/``.
2. Optionally copies any paths listed in cleaning CSVs that still exist on disk.

Run from ``backend/``::

    python scripts/restore_sleep.py
    python scripts/restore_sleep.py --copy   # keep copies in _rejected
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import csv
import shutil
from pathlib import Path

import typer

from roomos.utils.logging import get_logger, setup_logging

log = get_logger("roomos.scripts.restore_sleep")

app = typer.Typer(add_completion=False, help="Restore sleep/ from _rejected and cleaning reports.")


def _unique_dest(dest_dir: Path, name: str) -> Path:
    dest = dest_dir / name
    if not dest.exists():
        return dest
    stem, suffix = Path(name).stem, Path(name).suffix
    i = 1
    while dest.exists():
        dest = dest_dir / f"{stem}__restored{i}{suffix}"
        i += 1
    return dest


@app.command()
def main(
    images_dir: Path = typer.Option(Path("data/base_images"), "--images-dir"),
    copy: bool = typer.Option(False, "--copy", help="Copy instead of move from _rejected."),
    from_reports: bool = typer.Option(True, "--from-reports", help="Also restore CSV moved_to paths."),
) -> None:
    setup_logging()
    root = Path(images_dir).resolve()
    sleep_dir = root / "sleep"
    reject_sleep = root / "_rejected" / "sleep"
    sleep_dir.mkdir(parents=True, exist_ok=True)

    restored = 0

    if reject_sleep.is_dir():
        for src in sorted(reject_sleep.iterdir()):
            if not src.is_file():
                continue
            dest = _unique_dest(sleep_dir, src.name)
            if copy:
                shutil.copy2(src, dest)
            else:
                shutil.move(str(src), str(dest))
            restored += 1
        log.info("From _rejected/sleep: %d files -> sleep/", restored)
    else:
        log.warning("No %s", reject_sleep)

    if from_reports:
        for csv_name in ("clean_report.csv", "clean_report_cv.csv", "clean_sleep_bed_report.csv"):
            report = root / "_rejected" / csv_name
            if not report.is_file():
                continue
            n = 0
            with report.open(encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("label") != "sleep":
                        continue
                    for key in ("moved_to", "file"):
                        p = row.get(key, "").strip()
                        if not p:
                            continue
                        src = Path(p)
                        if not src.is_file():
                            continue
                        if src.parent.resolve() == sleep_dir.resolve():
                            continue
                        dest = _unique_dest(sleep_dir, src.name)
                        if copy:
                            shutil.copy2(src, dest)
                        else:
                            shutil.move(str(src), str(dest))
                        n += 1
                        restored += 1
                        break
            if n:
                log.info("From %s: %d additional files", csv_name, n)

    total = sum(1 for p in sleep_dir.iterdir() if p.is_file())
    log.info("DONE | restored_this_run=%d | sleep/ now has %d files", restored, total)
    if total < 100:
        log.warning(
            "sleep/ is still small. Git cannot help (data is gitignored). "
            "Re-download with: npm run import:base-images -- --labels sleep --per-class 800 "
            "and/or npm run data:import-sleep-bed"
        )


if __name__ == "__main__":
    app()
