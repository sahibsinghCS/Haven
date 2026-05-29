"""Unified RoomOS training entrypoint (hackathon-friendly).

Run from ``backend/`` or via npm scripts at repo root.

Examples::

    python scripts/train_roomos.py demo
    python scripts/train_roomos.py images --images-dir data/raw_images
    python scripts/train_roomos.py videos --raw-dir data/raw
    python scripts/train_roomos.py verify
    python scripts/train_roomos.py layout
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Train RoomOS models to data/models/latest (with live compatibility checks).",
)

DATA_LAYOUT = """
Hackathon collection: npm run data:init | data:capture-stills | data:audit
Full guide: docs/DATA-COLLECTION.md

Expected data layout (all under backend/data/, gitignored):

  Path A - still images (fastest personal bootstrap):
    data/raw_images/work/*.jpg
    data/raw_images/gaming/*.jpg
    data/raw_images/sleep/*.jpg
    data/raw_images/relaxing/*.jpg
    data/raw_images/away/*.jpg
    ->  npm run train:images

  Path A+ - your room weighted over generic multi-room (recommended for /live):
    ->  npm run train:my-room

  Path B - your room videos (best accuracy):
    data/raw/work/session01.mp4
    data/raw/gaming/...
    (one label folder per class, whole file = that label)
    ->  npm run train:videos

  Path C - no data yet (synthetic demo):
    ->  npm run train:demo

  Advanced - manual steps (same feature config required):
    1. capture:  python scripts/capture_video.py -o data/raw/work/take1.mp4 -d 60
    2. label:    python scripts/label_windows.py VIDEO -o data/labels/labels.csv
    3. extract:  python scripts/extract_features.py VIDEO -l labels.csv -c configs/train_personal.yaml
    4. train:    python scripts/train_model.py -c configs/train_personal.yaml -f features.parquet
    5. eval:     python scripts/evaluate_model.py -b data/models/latest -f features.parquet

Artifacts (always):
    data/models/latest/model.json
    data/models/latest/label_encoder.json
    data/models/latest/feature_columns.json
    data/models/latest/metrics.json

Live serving reads: configs/inference.yaml -> inference.model_dir (default: data/models/latest)
Train with configs/train_personal.yaml so features match inference.yaml.
"""


@app.command("layout")
def cmd_layout() -> None:
    """Print expected folder layout and artifact paths."""
    typer.echo(DATA_LAYOUT.strip())


@app.command("demo")
def cmd_demo(
    images_per_class: int = typer.Option(30, "--images-per-class"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Synthetic images → features → data/models/latest (no webcam/video needed)."""
    from scripts.bootstrap_demo_model import run_bootstrap_demo

    run_bootstrap_demo(images_per_class=images_per_class, log_level=log_level)


@app.command("my-room")
def cmd_my_room(
    images_dir: Path = typer.Option(Path("data/raw_images"), "--images-dir"),
    personal_only: bool = typer.Option(False, "--personal-only"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Train with your room at 12× weight vs subsampled multi-room prior."""
    from scripts.train_my_room import run_train_my_room

    run_train_my_room(
        images_dir=images_dir,
        personal_only=personal_only,
        log_level=log_level,
    )


@app.command("images")
def cmd_images(
    images_dir: Path = typer.Option(Path("data/raw_images"), "--images-dir"),
    model_out: Path = typer.Option(Path("data/models/latest"), "--model-out"),
    min_bursts_per_class: int = typer.Option(6, "--min-bursts-per-class"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Train from labeled still-image folders (see ``train_roomos.py layout``)."""
    from scripts.train_personal_images import main as images_main

    images_main(
        images_dir=images_dir,
        model_out=model_out,
        min_bursts_per_class=min_bursts_per_class,
        log_level=log_level,
    )


@app.command("videos")
def cmd_videos(
    raw_dir: Path = typer.Option(Path("data/raw"), "--raw-dir"),
    model_out: Path = typer.Option(Path("data/models/latest"), "--model-out"),
    min_videos_per_class: int = typer.Option(1, "--min-videos-per-class", help="Lower for tiny datasets."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Train from data/raw/<label>/*.mp4 folders (full-file labels)."""
    from scripts.train_personal_roomos import main as videos_main

    videos_main(
        raw_dir=raw_dir,
        model_out=model_out,
        min_videos_per_class=min_videos_per_class,
        log_level=log_level,
    )


@app.command("report")
def cmd_report(
    bundle: Path = typer.Option(Path("data/models/latest"), "--bundle", "-b"),
    features: Optional[Path] = typer.Option(None, "--features", "-f"),
    recompute: bool = typer.Option(False, "--recompute"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Generate eval_report/ (metrics, CM, per-class, limitations) for judges."""
    from roomos.model.eval_report import generate_report_from_bundle
    from roomos.utils.logging import setup_logging

    setup_logging(level=log_level)
    out = generate_report_from_bundle(bundle, features_path=features, recompute=recompute)
    typer.echo(f"Evaluation report written to {out}")
    typer.echo(f"Open: {out / 'REPORT.md'}")


@app.command("verify")
def cmd_verify(
    bundle: Path = typer.Option(Path("data/models/latest"), "--bundle", "-b"),
    inference_config: Path = typer.Option(Path("configs/inference.yaml"), "--inference-config", "-c"),
) -> None:
    """Check bundle feature schema matches live inference config."""
    from scripts.verify_bundle import main as verify_main

    verify_main(bundle=bundle, inference_config=inference_config)


if __name__ == "__main__":
    app()
