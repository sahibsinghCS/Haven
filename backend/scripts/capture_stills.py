"""Rapid still-image capture into data/raw_images/<label>/ (hackathon path).

Press SPACE to save a frame, N for next class, Q to quit.
Uses the same webcam as live inference (configs/default.yaml video.source).

Example::

    npm run data:capture-stills
    npm run data:capture-stills -- --class work --count 40
"""

from __future__ import annotations

import _bootstrap  # noqa: F401
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer

from roomos.config import load_config
from roomos.utils.logging import get_logger, setup_logging
from roomos.video import open_video_source

app = typer.Typer(add_completion=False, help="Capture labeled stills for train:images.")
log = get_logger("roomos.scripts.capture_stills")

# Recommended display names for the five demo classes
CLASS_HINTS = {
    "work": "Desk / laptop / studying — keyboard visible, screen glow",
    "sleep": "In bed or lying down — lights low, horizontal posture",
    "gaming": "Controller or intense screen time — gaming posture",
    "relaxing": "Couch / reading / casual — not desk, not asleep",
    "away": "Empty room or you out of frame — lights may be on/off",
}


@app.command()
def main(
    out_dir: Path = typer.Option(Path("data/raw_images"), "--out-dir"),
    config: Path = typer.Option(Path("configs/default.yaml"), "--config", "-c"),
    class_name: Optional[str] = typer.Option(
        None,
        "--class",
        help="Capture one class only (work, sleep, gaming, relaxing, away).",
    ),
    count: int = typer.Option(40, "--count", help="Target stills for this session (per class if rotating)."),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Webcam index or path override."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    cfg = load_config(config)
    classes = list(cfg.labels.classes)
    if class_name:
        if class_name not in classes:
            raise typer.BadParameter(f"--class must be one of: {', '.join(classes)}")
        session_classes = [class_name]
    else:
        session_classes = classes

    src = source if source is not None else cfg.video.source
    if isinstance(src, str) and src.isdigit():
        src = int(src)

    import cv2

    typer.echo("")
    typer.echo("RoomOS still capture")
    typer.echo("  SPACE = save frame   N = next class   Q = quit")
    typer.echo(f"  Output: {out_dir.resolve()}/<label>/")
    typer.echo("")

    with open_video_source(
        src,
        sample_fps=float(cfg.video.sample_fps),
        resize_width=int(cfg.video.resize_width),
        read_timeout_sec=float(cfg.video.read_timeout_sec),
    ) as fs:
        for label in session_classes:
            label_dir = out_dir / label
            label_dir.mkdir(parents=True, exist_ok=True)
            existing = len(list(label_dir.glob("*.jpg"))) + len(list(label_dir.glob("*.png")))
            saved = 0
            target = count

            hint = CLASS_HINTS.get(label, label)
            typer.echo(f"=== {label.upper()} ({existing} already on disk) ===")
            typer.echo(f"    {hint}")
            typer.echo(f"    Save {target} frames (SPACE), then press N for next class.")
            typer.echo("")

            window = f"RoomOS capture — {label}"
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)

            for sf in fs:
                frame = sf.image.copy()
                overlay = _draw_overlay(frame, label, saved, target, existing + saved)
                cv2.imshow(window, overlay)
                key = cv2.waitKey(1) & 0xFF

                if key in (ord("q"), ord("Q"), 27):
                    cv2.destroyWindow(window)
                    typer.echo("Stopped by user.")
                    raise typer.Exit(0)

                if key in (ord("n"), ord("N")) and saved > 0:
                    break

                if key == ord(" "):
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
                    path = label_dir / f"shot_{stamp}.jpg"
                    cv2.imwrite(str(path), sf.image, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
                    saved += 1
                    log.info("Saved %s (%d/%d)", path.name, saved, target)
                    if saved >= target:
                        typer.echo(f"  Reached {target} for {label}. Press N for next class or Q to quit.")
                        key2 = cv2.waitKey(0) & 0xFF
                        if key2 in (ord("n"), ord("N")):
                            break
                        if key2 in (ord("q"), ord("Q"), 27):
                            cv2.destroyWindow(window)
                            raise typer.Exit(0)

            cv2.destroyWindow(window)
            typer.echo(f"  Done {label}: +{saved} images -> {label_dir}")
            typer.echo("")

    typer.echo("Run: npm run data:audit   then   npm run train:images")


def _draw_overlay(frame, label: str, saved: int, target: int, total: int):
    import cv2

    out = frame.copy()
    h, w = out.shape[:2]
    cv2.rectangle(out, (0, 0), (w, 72), (0, 0, 0), -1)
    cv2.putText(
        out,
        f"{label}  session {saved}/{target}  total~{total}",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (240, 240, 240),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        out,
        "SPACE save | N next class | Q quit",
        (12, 56),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (180, 220, 200),
        1,
        cv2.LINE_AA,
    )
    return out


if __name__ == "__main__":
    app()
