"""Train RoomOS from labeled still-image folders.

Expected layout, from backend/:

    data/raw_images/work/*.jpg
    data/raw_images/gaming/*.jpg
    data/raw_images/sleep/*.jpg
    data/raw_images/relaxing/*.jpg
    data/raw_images/away/*.jpg

Sorted images are grouped into 5-frame bursts by default. Each burst becomes
one training row, matching the live pipeline's 5-frame memory span.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import typer

from roomos.config import load_config
from roomos.dataset.builder import FeatureExtractionPipeline, save_features
from roomos.features import FrameBurst
from roomos.model.train import train_model
from roomos.training.finalize import finalize_training, log_training_metrics
from roomos.utils.logging import get_logger, setup_logging

DEFAULT_TRAIN_CONFIG = Path("configs/train_personal.yaml")
DEFAULT_INFERENCE_CONFIG = Path("configs/inference.yaml")

app = typer.Typer(
    add_completion=False,
    help="Train a personal RoomOS model from data/raw_images/<label> still images.",
)
log = get_logger("roomos.scripts.train_personal_images")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@app.command()
def main(
    images_dir: Path = typer.Option(Path("data/raw_images"), "--images-dir"),
    features_out: Path = typer.Option(Path("data/features/personal_image_features.parquet"), "--features-out"),
    model_out: Path = typer.Option(Path("data/models/latest"), "--model-out"),
    config: Path = typer.Option(
        DEFAULT_TRAIN_CONFIG,
        "--config",
        "-c",
        help="Use configs/train_personal.yaml (matches live inference).",
    ),
    inference_config: Path = typer.Option(
        DEFAULT_INFERENCE_CONFIG,
        "--inference-config",
        help="Live config to verify against after training.",
    ),
    skip_verify: bool = typer.Option(False, "--skip-verify", help="Skip train/serve compatibility check."),
    frame_count: int = typer.Option(0, "--frame-count", help="0 means use config burst.frame_count."),
    stride: int = typer.Option(5, "--stride", help="Image step between consecutive bursts."),
    min_bursts_per_class: int = typer.Option(6, "--min-bursts-per-class"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)
    classes = list(cfg.labels.classes)
    n_frames = int(frame_count or cfg.burst.frame_count)
    if n_frames < 1:
        raise typer.BadParameter("frame_count must be >= 1")
    if stride < 1:
        raise typer.BadParameter("stride must be >= 1")

    images_by_class = _discover_images(images_dir, classes)
    _validate_coverage(images_by_class, n_frames, stride, min_bursts_per_class)

    rows: List[dict] = []
    with FeatureExtractionPipeline(cfg) as pipe:
        for label in classes:
            images = images_by_class.get(label, [])
            for burst_index, group in enumerate(_groups(images, n_frames, stride)):
                row = _extract_image_burst(pipe, group, label, burst_index)
                train_cfg = cfg.training
                if bool(train_cfg.get("use_row_weights", False)):
                    row["row_weight"] = float(train_cfg.get("default_row_weight", 12.0))
                    row["dataset"] = "personal_room"
                    row["source"] = f"myroom/{label}/burst_{burst_index:05d}"
                rows.append(row)

    if not rows:
        raise typer.Exit("No image bursts processed.")

    df = pd.DataFrame(rows)
    features_path = save_features(df, features_out)
    log.info("Saved %d labeled image bursts -> %s", len(df), features_path)
    log.info("Class coverage:\n%s", df["label"].value_counts(dropna=False).to_string())

    result = train_model(df, cfg, output_dir=model_out)
    log_training_metrics(result)
    finalize_training(
        result,
        cfg,
        inference_config=inference_config,
        skip_verify=skip_verify,
    )


def _extract_image_burst(
    pipe: FeatureExtractionPipeline,
    group: List[Path],
    label: str,
    burst_index: int,
) -> dict:
    import cv2

    source_id = f"{label}/burst_{burst_index:05d}"
    records = []
    pipe.reset_motion()
    for i, image_path in enumerate(group):
        image = cv2.imread(str(image_path))
        if image is None:
            raise RuntimeError(f"Could not read image: {image_path}")
        rec = pipe.frame_to_record(
            image_bgr=image,
            frame_index=i,
            timestamp=float(i),
            source=source_id,
        )
        records.append(rec)

    burst = FrameBurst(
        start_time=0.0,
        end_time=float(len(records) - 1),
        source=source_id,
        frames=records,
        burst_index=burst_index,
    )
    fused = pipe.fusion.fuse(burst)
    row = dict(fused.metadata)
    row.update(fused.as_dict())
    row["label"] = label
    row["notes"] = "image burst"
    return row


def _discover_images(images_dir: Path, classes: Iterable[str]) -> dict[str, List[Path]]:
    out: dict[str, List[Path]] = {}
    for label in classes:
        label_dir = images_dir / label
        images: List[Path] = []
        if label_dir.exists():
            images = [
                child
                for child in sorted(label_dir.iterdir())
                if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS
            ]
        out[label] = images
    return out


def _groups(images: List[Path], frame_count: int, stride: int) -> Iterable[List[Path]]:
    for start in range(0, max(0, len(images) - frame_count + 1), stride):
        group = images[start : start + frame_count]
        if len(group) == frame_count:
            yield group


def _validate_coverage(
    images_by_class: dict[str, List[Path]],
    frame_count: int,
    stride: int,
    min_bursts_per_class: int,
) -> None:
    counts = {
        label: sum(1 for _ in _groups(images, frame_count, stride))
        for label, images in images_by_class.items()
    }
    missing = [label for label, count in counts.items() if count < min_bursts_per_class]
    if missing:
        pretty = ", ".join(f"{label}={counts[label]} bursts" for label in counts)
        needed_images = frame_count + (min_bursts_per_class - 1) * stride
        raise typer.BadParameter(
            "Not enough image bursts. "
            f"Need at least {min_bursts_per_class} bursts per class "
            f"(about {needed_images} images/class with this stride). Current: {pretty}. "
            "Capture more: npm run data:capture-stills (from repo root)."
        )


if __name__ == "__main__":
    app()
