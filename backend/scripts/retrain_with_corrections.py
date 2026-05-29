#!/usr/bin/env python3
"""Immediately retrain XGBoost using multi-room features + all live corrections."""

from __future__ import annotations

import _bootstrap  # noqa: F401

import json
from pathlib import Path

import typer

from roomos.config import load_config
from roomos.model.registry import load_model_bundle
from roomos.training.auto_retrain import CorrectionAutoRetrainer
from roomos.utils.logging import setup_logging

app = typer.Typer(add_completion=False)


@app.command()
def main(
    config: Path = typer.Option(Path("configs/inference.yaml"), "--config", "-c"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)
    infer = cfg.get("inference", {}) or {}
    model_dir = Path(infer.get("model_dir", "data/models/latest"))
    if not model_dir.is_absolute():
        model_dir = cfg.resolve_path(model_dir)
    bundle = load_model_bundle(model_dir)
    retrainer = CorrectionAutoRetrainer(cfg)
    retrainer._feature_columns = list(bundle.feature_columns)
    summary = retrainer._retrain()
    typer.echo(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
