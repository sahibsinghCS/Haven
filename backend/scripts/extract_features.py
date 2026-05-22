"""Extract burst-level fused features from one or many videos."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path
from typing import List, Optional

import pandas as pd
import typer

from roomos.config import load_config
from roomos.dataset.builder import extract_bursts_from_video, save_features
from roomos.dataset.schemas import load_label_segments
from roomos.utils.logging import get_logger, setup_logging

app = typer.Typer(
    add_completion=False,
    help="Extract burst-level features (short multi-frame units) from videos.",
)
log = get_logger("roomos.scripts.extract")


@app.command()
def main(
    inputs: List[Path] = typer.Argument(..., help="Video files to process."),
    out: Path = typer.Option(Path("data/features/features.parquet"), "--out", "-o"),
    labels: Optional[Path] = typer.Option(None, "--labels", "-l", help="Optional labels CSV."),
    config: Path = typer.Option(
        Path("configs/train_personal.yaml"),
        "--config",
        "-c",
        help="Must match the config used for training and live inference.",
    ),
    log_level: str = typer.Option("INFO", "--log-level"),
    log_every: int = typer.Option(60, "--log-every", help="Heartbeat log frequency (frames)."),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)
    segs = load_label_segments(labels) if labels else []

    all_rows: List[pd.DataFrame] = []
    for video in inputs:
        if not video.exists():
            log.warning("Skipping missing file: %s", video)
            continue
        log.info("Extracting burst features from %s", video)
        df = extract_bursts_from_video(
            cfg, str(video), labels=segs, source_id=video.name, log_every=log_every
        )
        log.info("  -> %d bursts", len(df))
        all_rows.append(df)

    if not all_rows:
        raise typer.Exit("No videos processed.")

    full = pd.concat(all_rows, ignore_index=True)
    out_path = save_features(full, out)
    log.info("Saved %d total rows -> %s", len(full), out_path)
    if "label" in full.columns:
        log.info("Label coverage:\n%s", full["label"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    app()
