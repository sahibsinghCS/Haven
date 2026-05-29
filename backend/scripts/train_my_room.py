"""Train RoomOS with YOUR room dominating the dataset.

Combines:

* **Personal** — ``data/raw_images/<label>/`` from ``npm run data:capture-stills``
  (your bed, desk, couch layout). Each row gets ``row_weight = personal_row_weight``
  (default **12×**).
* **Multi-room** (optional) — pre-built ``multi_room_features.parquet`` from
  generic photos. Subsampled and ``row_weight = 1×`` so they regularize without
  overriding your space.

Use when live demo should follow *your* room, not a random internet bedroom.

From repo root::

    npm run data:capture-stills
    npm run train:my-room
    npm run demo
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path
from typing import List, Optional

import pandas as pd
import typer

from roomos.config import load_config
from roomos.dataset.builder import load_features
from roomos.model.train import train_model
from roomos.scripts.train_personal_images import (
    IMAGE_EXTENSIONS,
    _discover_images,
    _extract_image_burst,
    _groups,
    _validate_coverage,
)
from roomos.dataset.builder import FeatureExtractionPipeline, save_features
from roomos.training.finalize import finalize_training, log_training_metrics
from roomos.utils.logging import get_logger, setup_logging

DEFAULT_CONFIG = Path("configs/train_my_room.yaml")
DEFAULT_INFERENCE = Path("configs/inference.yaml")

app = typer.Typer(
    add_completion=False,
    help="Train with your room weighted higher than generic multi-room data.",
)
log = get_logger("roomos.scripts.train_my_room")


def _extract_personal_df(
    cfg,
    images_dir: Path,
    *,
    personal_weight: float,
    frame_count: int,
    stride: int,
    min_bursts_per_class: int,
) -> pd.DataFrame:
    classes = list(cfg.labels.classes)
    images_by_class = _discover_images(images_dir, classes)
    _validate_coverage(images_by_class, frame_count, stride, min_bursts_per_class)

    rows: List[dict] = []
    with FeatureExtractionPipeline(cfg) as pipe:
        for label in classes:
            for burst_index, group in enumerate(
                _groups(images_by_class[label], frame_count, stride)
            ):
                row = _extract_image_burst(pipe, group, label, burst_index)
                row["source"] = f"myroom/{label}/burst_{burst_index:05d}"
                row["dataset"] = "personal_room"
                row["row_weight"] = float(personal_weight)
                row["notes"] = "personal room still"
                rows.append(row)
    if not rows:
        raise typer.BadParameter("No personal bursts extracted from raw_images.")
    return pd.DataFrame(rows)


def _load_multi_room_df(
    path: Path,
    *,
    multi_weight: float,
    max_fraction: float,
    personal_df: pd.DataFrame,
    seed: int,
) -> pd.DataFrame:
    if not path.exists():
        alt = path.with_suffix(".csv")
        if alt.exists():
            path = alt
        else:
            log.warning("Multi-room features not found at %s — training personal only.", path)
            return pd.DataFrame()

    multi = load_features(path)
    if multi.empty or "label" not in multi.columns:
        log.warning("Multi-room features empty — skipping.")
        return pd.DataFrame()

    multi = multi.copy()
    multi["dataset"] = "multi_room"
    multi["row_weight"] = float(multi_weight)

    n_personal = len(personal_df)
    max_multi = max(0, int(round(n_personal * max_fraction)))
    if max_multi <= 0:
        return pd.DataFrame()

    rng = __import__("numpy").random.default_rng(seed)
    parts: List[pd.DataFrame] = []
    per_class_cap = max(1, max_multi // max(1, multi["label"].nunique()))

    for label in multi["label"].unique():
        part = multi[multi["label"] == label]
        if len(part) <= per_class_cap:
            parts.append(part)
        else:
            idx = rng.choice(len(part), size=per_class_cap, replace=False)
            parts.append(part.iloc[idx])

    out = pd.concat(parts, ignore_index=True)
    if len(out) > max_multi:
        idx = rng.choice(len(out), size=max_multi, replace=False)
        out = out.iloc[idx]
    log.info(
        "Multi-room prior: %d rows (cap %.0f%% of %d personal rows, weight=%.1f)",
        len(out),
        max_fraction * 100,
        n_personal,
        multi_weight,
    )
    return out


def run_train_my_room(
    *,
    images_dir: Path = Path("data/raw_images"),
    config: Path = DEFAULT_CONFIG,
    inference_config: Path = DEFAULT_INFERENCE,
    model_out: Path = Path("data/models/latest"),
    features_out: Path = Path("data/features/my_room_features.parquet"),
    personal_only: Optional[bool] = None,
    personal_weight: Optional[float] = None,
    multi_weight: Optional[float] = None,
    min_bursts_per_class: int = 6,
    stride: int = 5,
    log_level: str = "INFO",
) -> Path:
    setup_logging(level=log_level)
    cfg = load_config(config)
    train_cfg = cfg.training

    pw = float(personal_weight if personal_weight is not None else train_cfg.get("personal_row_weight", 12.0))
    mw = float(multi_weight if multi_weight is not None else train_cfg.get("multi_room_row_weight", 1.0))
    only_personal = bool(
        personal_only
        if personal_only is not None
        else train_cfg.get("personal_only", False)
    )
    max_frac = float(train_cfg.get("multi_room_max_fraction", 0.22))
    seed = int(train_cfg.get("random_state", 42))
    n_frames = int(cfg.burst.frame_count)

    personal_df = _extract_personal_df(
        cfg,
        images_dir,
        personal_weight=pw,
        frame_count=n_frames,
        stride=stride,
        min_bursts_per_class=min_bursts_per_class,
    )
    log.info("Personal room bursts: %d (weight=%.1f each)", len(personal_df), pw)
    log.info("Personal class counts:\n%s", personal_df["label"].value_counts().to_string())

    if only_personal:
        combined = personal_df
    else:
        multi_path = Path(train_cfg.get("multi_room_features_path", "data/features/multi_room_features.parquet"))
        if not multi_path.is_absolute():
            multi_path = cfg.resolve_path(multi_path)
        multi_df = _load_multi_room_df(
            multi_path,
            multi_weight=mw,
            personal_df=personal_df,
            max_fraction=max_frac,
            seed=seed,
        )
        combined = pd.concat([personal_df, multi_df], ignore_index=True)

    if combined.empty:
        raise typer.BadParameter("No training rows after merge.")

    w_personal = float(combined.loc[combined["dataset"] == "personal_room", "row_weight"].sum())
    w_multi = float(combined.loc[combined["dataset"] == "multi_room", "row_weight"].sum())
    log.info(
        "Combined train pool: %d rows — effective weight personal=%.0f multi=%.0f (ratio %.1f:1)",
        len(combined),
        w_personal,
        w_multi,
        w_personal / max(w_multi, 1e-6),
    )

    features_path = save_features(combined, features_out)
    log.info("Saved features -> %s", features_path)

    result = train_model(combined, cfg, output_dir=model_out)
    log_training_metrics(result)
    finalize_training(result, cfg, inference_config=inference_config)
    return Path(result.bundle_dir)


@app.command()
def main(
    images_dir: Path = typer.Option(Path("data/raw_images"), "--images-dir"),
    features_out: Path = typer.Option(Path("data/features/my_room_features.parquet"), "--features-out"),
    model_out: Path = typer.Option(Path("data/models/latest"), "--model-out"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    inference_config: Path = typer.Option(DEFAULT_INFERENCE, "--inference-config"),
    personal_only: bool = typer.Option(
        False,
        "--personal-only",
        help="Train only on your captures; ignore generic multi-room parquet.",
    ),
    personal_weight: float = typer.Option(0, "--personal-weight", help="0 = use config (default 12)."),
    multi_weight: float = typer.Option(0, "--multi-weight", help="0 = use config (default 1)."),
    min_bursts_per_class: int = typer.Option(6, "--min-bursts-per-class"),
    stride: int = typer.Option(5, "--stride"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    run_train_my_room(
        images_dir=images_dir,
        config=config,
        inference_config=inference_config,
        model_out=model_out,
        features_out=features_out,
        personal_only=personal_only,
        personal_weight=personal_weight if personal_weight > 0 else None,
        multi_weight=multi_weight if multi_weight > 0 else None,
        min_bursts_per_class=min_bursts_per_class,
        stride=stride,
        log_level=log_level,
    )


if __name__ == "__main__":
    app()
