"""Record a video from a webcam / RTSP source to disk for later labeling."""

from __future__ import annotations

import _bootstrap  # noqa: F401  -- side-effect import
import time
from pathlib import Path
from typing import Optional

import typer

from roomos.config import load_config
from roomos.utils.logging import get_logger, setup_logging
from roomos.video import open_video_source

app = typer.Typer(add_completion=False, help="Capture raw video to disk.")
log = get_logger("roomos.scripts.capture")


@app.command()
def main(
    out: Path = typer.Option(..., "--out", "-o", help="Output .mp4 path."),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Override config video source."),
    duration: float = typer.Option(30.0, "--duration", "-d", help="Recording length in seconds."),
    fps: float = typer.Option(15.0, "--fps", help="Output video FPS (sampled frame rate)."),
    width: int = typer.Option(960, "--width", help="Resize width (preserves aspect)."),
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", "-c"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)
    src = source if source is not None else cfg.video.source
    if isinstance(src, str) and src.isdigit():
        src = int(src)

    out.parent.mkdir(parents=True, exist_ok=True)

    import cv2

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer: Optional[cv2.VideoWriter] = None
    started = time.monotonic()
    log.info("Recording %.1fs from %s -> %s", duration, src, out)

    with open_video_source(src, sample_fps=fps, resize_width=width, read_timeout_sec=5.0) as fs:
        for sf in fs:
            if writer is None:
                h, w = sf.image.shape[:2]
                writer = cv2.VideoWriter(str(out), fourcc, fps, (w, h))
            writer.write(sf.image)
            if (time.monotonic() - started) >= duration:
                break

    if writer is not None:
        writer.release()
    log.info("Saved %s", out)


if __name__ == "__main__":
    app()
