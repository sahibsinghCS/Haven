"""Bootstrap a demo RoomOS model without labeled videos.

Generates distinct synthetic stills per class, extracts CLIP+motion features
(matching ``configs/bootstrap_still.yaml`` / live inference), and writes
``data/models/latest/``. First run downloads OpenCLIP weights (~400MB).

From repo root::

    npm run bootstrap:demo

Or from ``backend/``::

    python scripts/bootstrap_demo_model.py
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path
from typing import Iterable, List

import cv2
import numpy as np
import pandas as pd
import typer

from roomos.config import load_config
from roomos.dataset.builder import FeatureExtractionPipeline, save_features
from roomos.features import FrameBurst
from roomos.model.train import train_model
from roomos.training.finalize import finalize_training, log_training_metrics
from roomos.utils.logging import get_logger, setup_logging

DEFAULT_INFERENCE_CONFIG = Path("configs/inference.yaml")

app = typer.Typer(
    add_completion=False,
    help="Train data/models/latest from synthetic demo images (hackathon bootstrap).",
)
log = get_logger("roomos.scripts.bootstrap_demo_model")

# Distinct BGR palettes per UI class — enough for motion/CLIP to separate weakly.
_CLASS_STYLES: dict[str, tuple[tuple[int, int, int], int]] = {
    "work": ((235, 245, 252), 18),
    "sleep": ((28, 36, 72), 6),
    "gaming": ((120, 48, 200), 42),
    "relaxing": ((48, 168, 140), 22),
    "away": ((72, 72, 76), 4),
}


def _write_demo_images(out_dir: Path, classes: Iterable[str], images_per_class: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for label in classes:
        label_dir = out_dir / label
        label_dir.mkdir(parents=True, exist_ok=True)
        base_bgr, noise = _CLASS_STYLES.get(label, ((128, 128, 128), 20))
        rng = np.random.default_rng(hash(label) % (2**32))
        for i in range(images_per_class):
            h, w = 360, 480
            frame = np.full((h, w, 3), base_bgr, dtype=np.uint8)
            # Class-specific structure so motion grids differ burst-to-burst.
            if label == "work":
                cv2.rectangle(frame, (40, 80), (w - 40, h - 120), (200, 210, 255), -1)
                cv2.line(frame, (60, 100), (w - 60, 100), (80, 120, 200), 3)
            elif label == "gaming":
                cv2.circle(frame, (w // 2, h // 2), 90 + (i % 12), (180, 80, 255), 3)
            elif label == "sleep":
                frame = (frame * 0.55).astype(np.uint8)
            elif label == "relaxing":
                cv2.ellipse(frame, (w // 2, h // 2 + 20), (140, 70), 0, 0, 360, (80, 200, 160), -1)
            elif label == "away":
                pass  # flat empty room tone
            jitter = rng.integers(-noise, noise + 1, frame.shape, dtype=np.int16)
            frame = np.clip(frame.astype(np.int16) + jitter, 0, 255).astype(np.uint8)
            path = label_dir / f"demo_{i:04d}.jpg"
            if not path.exists():
                cv2.imwrite(str(path), frame)


def _extract_burst(
    pipe: FeatureExtractionPipeline,
    images: List[Path],
    label: str,
    burst_index: int,
) -> dict:
    source_id = f"{label}/demo_burst_{burst_index:05d}"
    records = []
    pipe.reset_motion()
    for i, image_path in enumerate(images):
        image = cv2.imread(str(image_path))
        if image is None:
            raise RuntimeError(f"Could not read image: {image_path}")
        records.append(
            pipe.frame_to_record(
                image_bgr=image,
                frame_index=i,
                timestamp=float(i),
                source=source_id,
            )
        )
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
    row["notes"] = "bootstrap demo burst"
    return row


def _groups(images: List[Path], frame_count: int, stride: int) -> Iterable[List[Path]]:
    for start in range(0, max(0, len(images) - frame_count + 1), stride):
        group = images[start : start + frame_count]
        if len(group) == frame_count:
            yield group


def run_bootstrap_demo(
    *,
    images_dir: Path = Path("data/demo_bootstrap"),
    features_out: Path = Path("data/features/bootstrap_demo_features.parquet"),
    model_out: Path = Path("data/models/latest"),
    config: Path = Path("configs/bootstrap_demo.yaml"),
    images_per_class: int = 30,
    stride: int = 5,
    log_level: str = "INFO",
) -> Path:
    """Train ``data/models/latest`` from synthetic demo images. Returns bundle dir."""
    setup_logging(level=log_level)
    cfg = load_config(config)
    classes = list(cfg.labels.classes)
    n_frames = int(cfg.burst.frame_count)
    if n_frames < 1:
        raise typer.BadParameter("burst.frame_count must be >= 1")

    log.info("Writing synthetic demo images -> %s", images_dir)
    _write_demo_images(images_dir, classes, images_per_class)

    images_by_class = {
        label: sorted((images_dir / label).glob("demo_*.jpg")) for label in classes
    }
    rows: List[dict] = []
    with FeatureExtractionPipeline(cfg) as pipe:
        for label in classes:
            images = images_by_class[label]
            for burst_index, group in enumerate(_groups(images, n_frames, stride)):
                rows.append(_extract_burst(pipe, group, label, burst_index))

    if not rows:
        raise typer.Exit("No bursts extracted — check images_per_class and stride.")

    df = pd.DataFrame(rows)
    counts = df["label"].value_counts()
    min_per_class = 4
    thin = [label for label in classes if int(counts.get(label, 0)) < min_per_class]
    if thin:
        raise typer.BadParameter(
            f"Need at least {min_per_class} bursts per class (try --images-per-class 30). "
            f"Thin classes: {', '.join(f'{l}={counts.get(l, 0)}' for l in thin)}"
        )
    features_path = save_features(df, features_out)
    log.info("Saved %d demo bursts -> %s", len(df), features_path)
    log.info("Class coverage:\n%s", df["label"].value_counts(dropna=False).to_string())

    result = train_model(df, cfg, output_dir=model_out)
    log_training_metrics(result)
    finalize_training(result, cfg, inference_config=DEFAULT_INFERENCE_CONFIG)
    typer.echo(f"Demo model written to {result.bundle_dir}")
    return Path(result.bundle_dir)


@app.command()
def main(
    images_dir: Path = typer.Option(Path("data/demo_bootstrap"), "--images-dir"),
    features_out: Path = typer.Option(
        Path("data/features/bootstrap_demo_features.parquet"),
        "--features-out",
    ),
    model_out: Path = typer.Option(Path("data/models/latest"), "--model-out"),
    config: Path = typer.Option(Path("configs/bootstrap_demo.yaml"), "--config", "-c"),
    images_per_class: int = typer.Option(30, "--images-per-class", min=20),
    stride: int = typer.Option(5, "--stride"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    run_bootstrap_demo(
        images_dir=images_dir,
        features_out=features_out,
        model_out=model_out,
        config=config,
        images_per_class=images_per_class,
        stride=stride,
        log_level=log_level,
    )


if __name__ == "__main__":
    app()
