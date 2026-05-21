"""Interactive labeling tool for recorded videos."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path
from typing import Optional

import typer

from roomos.config import load_config
from roomos.dataset.labeling import run_labeling_ui
from roomos.utils.logging import get_logger, setup_logging

app = typer.Typer(
    add_completion=False,
    help="Keyboard-driven labeling for time segments (aligned to burst rows in feature export).",
)
log = get_logger("roomos.scripts.label")


@app.command()
def main(
    video: Path = typer.Argument(..., exists=True, readable=True),
    out: Path = typer.Option(Path("data/labels/labels.csv"), "--out", "-o"),
    source_id: Optional[str] = typer.Option(None, "--source-id"),
    fps: float = typer.Option(20.0, "--fps", help="Playback fps."),
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", "-c"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)
    classes = list(cfg.labels.classes)
    run_labeling_ui(
        video,
        classes=classes,
        out_csv=out,
        source_id=source_id,
        playback_fps=fps,
    )


if __name__ == "__main__":
    app()
