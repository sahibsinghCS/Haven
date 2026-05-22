"""Audit labeled image/video folders before training."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path

import typer

from roomos.config import load_config
from roomos.dataset.audit import audit_image_folders, audit_video_folders, format_audit_report
from roomos.utils.logging import setup_logging

app = typer.Typer(add_completion=False, help="Count bursts per class and balance warnings.")


def run_audit(
    images_dir: Path,
    raw_dir: Path,
    config: Path,
    min_bursts: int,
    target_bursts: int,
    stride: int,
) -> int:
    setup_logging(level="WARNING")
    cfg = load_config(config)
    classes = list(cfg.labels.classes)
    frame_count = int(cfg.burst.frame_count)

    image_stats = audit_image_folders(
        images_dir,
        classes,
        frame_count=frame_count,
        stride=stride,
        min_bursts_per_class=min_bursts,
        target_bursts_per_class=target_bursts,
    )
    typer.echo(format_audit_report(image_stats, min_bursts=min_bursts, target_bursts=target_bursts))

    video_stats = audit_video_folders(raw_dir, classes)
    if any(s.video_count for s in video_stats):
        typer.echo("")
        typer.echo("Videos (data/raw/<label>/*.mp4):")
        for s in video_stats:
            typer.echo(f"  {s.label:<10} {s.video_count} files")

    thin = [s.label for s in image_stats if not s.ok_for_min_bursts]
    return 1 if thin else 0


@app.command()
def main(
    images_dir: Path = typer.Option(Path("data/raw_images"), "--images-dir"),
    raw_dir: Path = typer.Option(Path("data/raw"), "--raw-dir"),
    config: Path = typer.Option(Path("configs/train_personal.yaml"), "--config", "-c"),
    min_bursts: int = typer.Option(6, "--min-bursts"),
    target_bursts: int = typer.Option(12, "--target-bursts", help="Hackathon 'good' target per class."),
    stride: int = typer.Option(5, "--stride"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    code = run_audit(images_dir, raw_dir, config, min_bursts, target_bursts, stride)
    if code:
        raise typer.Exit(code=code)


if __name__ == "__main__":
    app()
