"""One-command personal RoomOS training from labeled video folders.

Expected layout, from backend/:

    data/raw/work/*.mp4
    data/raw/gaming/*.mp4
    data/raw/sleep/*.mp4
    data/raw/relaxing/*.mp4
    data/raw/away/*.mp4

Each video is treated as one label for its full duration. For mixed videos or
partial labels, use label_windows.py instead.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import typer

from roomos.config import load_config
from roomos.dataset.builder import extract_bursts_from_video, save_features
from roomos.dataset.schemas import LabelSegment, save_label_segments
from roomos.model.train import train_model
from roomos.utils.logging import get_logger, setup_logging

app = typer.Typer(
    add_completion=False,
    help="Train a personal RoomOS model from data/raw/<label> video folders.",
)
log = get_logger("roomos.scripts.train_personal")

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


@app.command()
def main(
    raw_dir: Path = typer.Option(Path("data/raw"), "--raw-dir", help="Folder containing label subfolders."),
    features_out: Path = typer.Option(Path("data/features/personal_features.parquet"), "--features-out"),
    labels_out: Path = typer.Option(Path("data/labels/personal_labels.csv"), "--labels-out"),
    model_out: Path = typer.Option(Path("data/models/latest"), "--model-out"),
    config: Path = typer.Option(Path("configs/train.yaml"), "--config", "-c"),
    min_videos_per_class: int = typer.Option(3, "--min-videos-per-class"),
    log_level: str = typer.Option("INFO", "--log-level"),
    log_every: int = typer.Option(90, "--log-every"),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)
    classes = list(cfg.labels.classes)
    videos = _discover_videos(raw_dir, classes)
    _validate_coverage(videos, classes, min_videos_per_class)

    labels = _write_full_video_labels(videos, labels_out)
    all_rows: List[pd.DataFrame] = []
    for label, video in videos:
        source_id = _source_id(label, video)
        segs = [s for s in labels if s.source == source_id]
        log.info("Extracting %s from %s", label, video)
        df = extract_bursts_from_video(
            cfg,
            str(video),
            labels=segs,
            source_id=source_id,
            log_every=log_every,
        )
        all_rows.append(df)

    if not all_rows:
        raise typer.Exit("No videos processed.")

    full = pd.concat(all_rows, ignore_index=True)
    features_path = save_features(full, features_out)
    log.info("Saved %d labeled bursts -> %s", len(full), features_path)
    log.info("Class coverage:\n%s", full["label"].value_counts(dropna=False).to_string())

    result = train_model(full, cfg, output_dir=model_out)
    log.info("Training complete -> %s", result.bundle_dir)
    for split in ("train", "val", "test"):
        if split in result.metrics:
            m = result.metrics[split]
            log.info(
                "%-5s acc=%.3f macro_f1=%.3f weighted_f1=%.3f n=%d",
                split,
                m["accuracy"],
                m["macro_f1"],
                m["weighted_f1"],
                m["n_samples"],
            )


def _discover_videos(raw_dir: Path, classes: Iterable[str]) -> List[tuple[str, Path]]:
    out: List[tuple[str, Path]] = []
    for label in classes:
        label_dir = raw_dir / label
        if not label_dir.exists():
            continue
        for child in sorted(label_dir.iterdir()):
            if child.is_file() and child.suffix.lower() in VIDEO_EXTENSIONS:
                out.append((label, child))
    return out


def _validate_coverage(
    videos: List[tuple[str, Path]],
    classes: Iterable[str],
    min_videos_per_class: int,
) -> None:
    counts = {label: 0 for label in classes}
    for label, _ in videos:
        counts[label] = counts.get(label, 0) + 1
    missing = [label for label, count in counts.items() if count < min_videos_per_class]
    if missing:
        pretty = ", ".join(f"{label}={counts[label]}" for label in counts)
        raise typer.BadParameter(
            f"Need at least {min_videos_per_class} video(s) per class. Current: {pretty}"
        )


def _write_full_video_labels(videos: List[tuple[str, Path]], out: Path) -> List[LabelSegment]:
    labels: List[LabelSegment] = []
    for label, video in videos:
        labels.append(
            LabelSegment(
                source=_source_id(label, video),
                start_sec=0.0,
                end_sec=max(0.1, _video_duration_seconds(video)),
                label=label,
                notes="auto full-video label",
            )
        )
    save_label_segments(out, labels)
    return labels


def _video_duration_seconds(video: Path) -> float:
    import cv2

    cap = cv2.VideoCapture(str(video))
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        if fps > 0.0 and frames > 0.0:
            return frames / fps
    finally:
        cap.release()
    return 0.1


def _source_id(label: str, video: Path) -> str:
    return f"{label}/{video.name}"


if __name__ == "__main__":
    app()
