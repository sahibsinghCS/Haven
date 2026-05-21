"""Train an XGBoost activity classifier from a features dataframe."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path
from typing import Optional

import typer

from roomos.config import load_config
from roomos.dataset.builder import load_features
from roomos.dataset.schemas import load_label_segments
from roomos.model.train import train_model
from roomos.utils.logging import get_logger, setup_logging

app = typer.Typer(add_completion=False, help="Train the XGBoost activity classifier.")
log = get_logger("roomos.scripts.train")


@app.command()
def main(
    config: Path = typer.Option(Path("configs/train.yaml"), "--config", "-c"),
    features: Optional[Path] = typer.Option(None, "--features", "-f", help="Override features path."),
    labels: Optional[Path] = typer.Option(None, "--labels", "-l", help="Optional labels CSV to merge."),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Override model output dir."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)

    feats_path = features or Path(cfg.training.features_path)
    log.info("Loading features from %s", feats_path)
    df = load_features(feats_path)

    if "label" not in df.columns or df["label"].isna().all():
        lbls_path = labels or Path(cfg.training.labels_path)
        log.info("Merging labels from %s", lbls_path)
        from roomos.dataset.builder import merge_labels_into_features

        segs = load_label_segments(lbls_path)
        df = merge_labels_into_features(df, segs)

    result = train_model(df, cfg, output_dir=out)
    log.info("Training complete -> %s", result.bundle_dir)
    metrics = result.metrics
    for split in ("train", "val", "test"):
        if split in metrics:
            m = metrics[split]
            log.info(
                "  %-5s  acc=%.3f  macro_f1=%.3f  weighted_f1=%.3f  n=%d",
                split,
                m["accuracy"],
                m["macro_f1"],
                m["weighted_f1"],
                m["n_samples"],
            )


if __name__ == "__main__":
    app()
