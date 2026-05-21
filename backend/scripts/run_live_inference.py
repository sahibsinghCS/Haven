"""Run real-time inference (CLI mode, no FastAPI)."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path
from typing import Optional

import typer

from roomos.config import load_config
from roomos.inference.live_pipeline import build_engine
from roomos.utils.logging import get_logger, setup_logging

app = typer.Typer(
    add_completion=False,
    help="Live inference: repeated burst sampling, XGBoost, smoothing (terminal / OpenCV).",
)
log = get_logger("roomos.scripts.live")


@app.command()
def main(
    config: Path = typer.Option(Path("configs/inference.yaml"), "--config", "-c"),
    actions_config: Optional[Path] = typer.Option(Path("configs/actions.yaml"), "--actions"),
    show: bool = typer.Option(False, "--show", help="Show an OpenCV preview window."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)
    if show:
        cfg.raw.setdefault("inference", {})["show_window"] = True

    def _print_snap(snap):
        log.info(
            "snap %-9s %5.1f%%  %s",
            snap.primary_state,
            snap.primary_confidence * 100,
            ", ".join(f"{k}={v:.2f}" for k, v in snap.distribution.items()),
        )

    engine = build_engine(cfg, actions_config_path=str(actions_config) if actions_config else None,
                          on_snapshot=_print_snap)
    try:
        engine.run()
    except KeyboardInterrupt:
        log.info("Interrupted; shutting down.")
    finally:
        engine.stop()


if __name__ == "__main__":
    app()
