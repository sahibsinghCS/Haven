"""Evaluate a saved model bundle on a features dataframe."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path
from typing import Optional

import typer

from roomos.config import load_config
from roomos.dataset.builder import load_features, merge_labels_into_features
from roomos.dataset.schemas import load_label_segments
from roomos.model.evaluate import evaluate_model
from roomos.model.registry import load_model_bundle
from roomos.utils.logging import get_logger, setup_logging

app = typer.Typer(add_completion=False, help="Evaluate a trained model bundle.")
log = get_logger("roomos.scripts.eval")


@app.command()
def main(
    bundle: Path = typer.Option(..., "--bundle", "-b", exists=True, file_okay=False, help="Model bundle dir."),
    features: Path = typer.Option(..., "--features", "-f"),
    labels: Optional[Path] = typer.Option(None, "--labels", "-l"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Where to write eval artifacts."),
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", "-c"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    load_config(config)  # validates the path even though we don't use it for eval

    df = load_features(features)
    if labels is not None or "label" not in df.columns:
        seg_path = labels or Path("data/labels/labels.csv")
        log.info("Merging labels from %s", seg_path)
        segs = load_label_segments(seg_path)
        df = merge_labels_into_features(df, segs)

    model = load_model_bundle(bundle)
    log.info("Loaded model bundle %s (classes=%s)", bundle, model.classes)
    report_root = Path(out) if out else Path(bundle)
    metrics = evaluate_model(model, df, output_dir=report_root)
    log.info(
        "acc=%.3f  macro_f1=%.3f  weighted_f1=%.3f  n=%d",
        metrics["accuracy"], metrics["macro_f1"], metrics["weighted_f1"], metrics["n_samples"],
    )


if __name__ == "__main__":
    app()
