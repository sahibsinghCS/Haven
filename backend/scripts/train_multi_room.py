"""Train RoomOS on a *multi-room* still-image dataset.

The default ``train:images`` workflow assumes the user has captured short
sequences of frames of **their own room** for each activity. For demo
robustness we also want a model that has seen many different rooms — couches,
desks, beds, gaming setups — so that the live classifier does not collapse to
"work" the moment it sees any indoor scene.

This script processes ``data/base_images/<label>/*.jpg`` (populated by
``scripts/import_base_images.py`` from Open Images v7 / Wikimedia / Zenodo)
into one feature row per image:

* Each image becomes a **single-image burst** of ``frame_count`` identical
  copies. This is intentional: still images carry no motion, and a static
  zero-motion burst is the cleanest training signal for a stills dataset.
  Live inference still works because the live pipeline produces non-zero
  motion features that the model has simply never relied on at train time.

* Each burst's ``source`` is the **original image stem** with any ``_aug*``
  suffix stripped. The ``by_source`` split therefore groups every
  augmentation of one original photo onto the same side of train/val/test
  (no per-augmentation leakage).

After training we run the standard ``finalize_training`` hook so the bundle
is verified against ``configs/inference.yaml`` and an eval report is written.

Usage::

    cd backend
    .\\.venv\\Scripts\\python.exe scripts/train_multi_room.py

    # or to force a higher quality bar:
    .\\.venv\\Scripts\\python.exe scripts/train_multi_room.py \\
        --min-test-accuracy 0.80 --frame-count 5
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import re
from pathlib import Path
from typing import Iterable, List

import cv2
import pandas as pd
import typer

from roomos.config import load_config
from roomos.dataset.builder import FeatureExtractionPipeline, load_features, save_features
from roomos.features import FrameBurst, FrameRecord
from roomos.model.train import train_model
from roomos.training.finalize import finalize_training, log_training_metrics
from roomos.utils.logging import get_logger, setup_logging

DEFAULT_TRAIN_CONFIG = Path("configs/train_multi_room.yaml")
DEFAULT_INFERENCE_CONFIG = Path("configs/inference.yaml")

app = typer.Typer(
    add_completion=False,
    help="Train data/models/latest on a multi-room still-image dataset.",
)
log = get_logger("roomos.scripts.train_multi_room")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Strips any ``_aug<tag>`` suffix produced by scripts/expand_base_images.py.
_AUG_SUFFIX = re.compile(r"_aug[a-z]+$", flags=re.IGNORECASE)


def _source_id_for(label: str, image: Path) -> str:
    """Map ``open_images_v7_<id>_augbright.jpg`` → ``<label>/open_images_v7_<id>``."""
    stem = image.stem
    base = _AUG_SUFFIX.sub("", stem)
    return f"{label}/{base}"


def _discover_images(images_dir: Path, classes: Iterable[str]) -> dict[str, List[Path]]:
    out: dict[str, List[Path]] = {}
    for label in classes:
        label_dir = images_dir / label
        if not label_dir.exists():
            out[label] = []
            continue
        out[label] = sorted(
            p
            for p in label_dir.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )
    return out


def _extract_still_burst(
    pipe: FeatureExtractionPipeline,
    image_path: Path,
    label: str,
    frame_count: int,
    burst_index: int,
) -> dict:
    """Build a feature row from one image by replicating it ``frame_count`` times.

    Performance: a naive implementation would call ``frame_to_record`` once
    per replicated frame, paying for ``frame_count`` CLIP forward passes on
    the **same** image. Since CLIP is deterministic on identical input we
    compute the features once and copy them across the N FrameRecords. Motion
    of N identical frames is exactly zero by definition, so we skip the
    motion extractor entirely and let the fusion layer summarise the
    all-zero state.
    """
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Could not read image: {image_path}")

    source_id = _source_id_for(label, image_path)

    pipe.reset_motion()
    base = pipe.frame_to_record(
        image_bgr=image,
        frame_index=0,
        timestamp=0.0,
        source=source_id,
    )
    pipe.reset_motion()  # discard the motion baseline so siblings start clean

    records: List[FrameRecord] = [base]
    for i in range(1, frame_count):
        records.append(
            FrameRecord(
                timestamp=float(i),
                frame_index=i,
                source=source_id,
                clip_embedding=base.clip_embedding,
                clip_prompt_sim=base.clip_prompt_sim,
                pose_landmarks=base.pose_landmarks,
                pose_visibility=base.pose_visibility,
                pose_present=base.pose_present,
                pose_mean_visibility=base.pose_mean_visibility,
                pose_bbox=base.pose_bbox,
                motion_mean=0.0,
                motion_std=0.0,
                motion_max=0.0,
                motion_grid=base.motion_grid,
                posture=dict(base.posture or {}),
            )
        )

    burst = FrameBurst(
        start_time=0.0,
        end_time=float(frame_count - 1),
        source=source_id,
        frames=records,
        burst_index=burst_index,
    )
    fused = pipe.fusion.fuse(burst)
    row = dict(fused.metadata)
    row.update(fused.as_dict())
    row["label"] = label
    row["notes"] = f"multi_room still: {image_path.name}"
    row["row_weight"] = 1.0
    return row


@app.command()
def main(
    images_dir: Path = typer.Option(Path("data/base_images"), "--images-dir"),
    features_out: Path = typer.Option(
        Path("data/features/multi_room_features.parquet"),
        "--features-out",
    ),
    model_out: Path = typer.Option(Path("data/models/latest"), "--model-out"),
    config: Path = typer.Option(
        DEFAULT_TRAIN_CONFIG,
        "--config",
        "-c",
        help="Train config (extends train.yaml, matches inference.yaml feature flags).",
    ),
    inference_config: Path = typer.Option(
        DEFAULT_INFERENCE_CONFIG, "--inference-config"
    ),
    frame_count: int = typer.Option(
        0,
        "--frame-count",
        help="Frames per burst (0 = use config burst.frame_count). Each frame = same image.",
    ),
    min_images_per_class: int = typer.Option(20, "--min-images-per-class"),
    min_test_accuracy: float = typer.Option(
        0.0,
        "--min-test-accuracy",
        help="If >0, raise typer.Exit(1) when held-out test accuracy is below this.",
    ),
    skip_verify: bool = typer.Option(False, "--skip-verify"),
    from_features: bool = typer.Option(
        False,
        "--from-features",
        help="Skip CLIP extraction; train from --features-out if it already exists.",
    ),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)
    classes = list(cfg.labels.classes)
    n_frames = int(frame_count or cfg.burst.frame_count)
    if n_frames < 1:
        raise typer.BadParameter("frame_count must be >= 1")

    if from_features and features_out.exists():
        log.info("Loading existing features from %s (skip extraction)", features_out)
        df = load_features(features_out)
        features_path = features_out
    else:
        images_by_class = _discover_images(images_dir, classes)
        counts = {label: len(paths) for label, paths in images_by_class.items()}
        thin = {label: count for label, count in counts.items() if count < min_images_per_class}
        if thin:
            raise typer.BadParameter(
                f"Need at least {min_images_per_class} images per class. "
                f"Thin: {thin}. Run scripts/import_base_images.py and/or expand_base_images.py."
            )
        log.info("Image counts per class: %s", counts)

        rows: List[dict] = []
        burst_index = 0
        with FeatureExtractionPipeline(cfg) as pipe:
            for label in classes:
                for image_path in images_by_class[label]:
                    row = _extract_still_burst(pipe, image_path, label, n_frames, burst_index)
                    rows.append(row)
                    burst_index += 1
                    if burst_index % 50 == 0:
                        log.info("Fused %d bursts so far...", burst_index)

        if not rows:
            raise typer.Exit("No bursts produced.")

        df = pd.DataFrame(rows)
        features_path = save_features(df, features_out)
    log.info(
        "Saved %d multi-room bursts (one per image) -> %s",
        len(df),
        features_path,
    )
    log.info("Class coverage:\n%s", df["label"].value_counts(dropna=False).to_string())
    unique_sources = df["source"].nunique()
    log.info(
        "Unique source clusters (after _aug stripping): %d "
        "— by_source split groups all variants of one photo together.",
        unique_sources,
    )

    result = train_model(df, cfg, output_dir=model_out)
    log_training_metrics(result)

    test_acc = float(result.metrics.get("test", {}).get("accuracy", 0.0))
    val_acc = float(result.metrics.get("val", {}).get("accuracy", 0.0))
    log.info(
        "Held-out accuracy — test=%.3f val=%.3f (min required = %.3f)",
        test_acc,
        val_acc,
        min_test_accuracy,
    )

    finalize_training(
        result,
        cfg,
        inference_config=inference_config,
        skip_verify=skip_verify,
    )

    train_acc = float(result.metrics.get("train", {}).get("accuracy", 0.0))
    gap = train_acc - test_acc
    max_gap = float(cfg.training.get("max_train_test_acc_gap", 0.0) or 0.0)
    if max_gap > 0 and gap > max_gap:
        log.warning(
            "Train-test accuracy gap %.3f exceeds %.3f (train=%.3f test=%.3f) — "
            "model may be overfitting; consider more regularization or data.",
            gap,
            max_gap,
            train_acc,
            test_acc,
        )
    work_per = (result.metrics.get("test", {}) or {}).get("per_class", {})
    if isinstance(work_per, dict) and "work" in work_per:
        work_rec = float(work_per["work"].get("recall", 0.0))
        log.info("Test recall for work: %.3f", work_rec)

    if min_test_accuracy > 0.0 and test_acc < min_test_accuracy:
        log.error(
            "Test accuracy %.3f is below required %.3f — bundle was written but flagged.",
            test_acc,
            min_test_accuracy,
        )
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
