"""Print ready-to-run capture commands for each room class (copy/paste)."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path

import typer

from roomos.config import load_config

app = typer.Typer(add_completion=False)


@app.command()
def main(
    raw_dir: Path = typer.Option(Path("data/raw"), "--raw-dir"),
    duration: float = typer.Option(75.0, "--duration", "-d"),
    source: str = typer.Option("0", "--source", "-s"),
) -> None:
    cfg = load_config()
    classes = list(cfg.labels.classes)
    typer.echo("# Record one clip per class (whole file = that label)")
    typer.echo(f"# Webcam/source: {source}  duration: {duration}s\n")
    for label in classes:
        out = raw_dir / label / f"{label}_01.mp4"
        typer.echo(
            f"npm run capture -- -o {out.as_posix()} -s {source} -d {duration}"
        )
    typer.echo("\n# Then: npm run train:videos")


if __name__ == "__main__":
    app()
