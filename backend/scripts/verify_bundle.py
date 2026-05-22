"""Verify a trained bundle works with live inference (feature schema match)."""

from __future__ import annotations

import _bootstrap  # noqa: F401
import json
from pathlib import Path

import typer

from roomos.model.compat import TrainServeCompatibilityError, verify_bundle_for_live
from roomos.utils.logging import setup_logging

app = typer.Typer(add_completion=False, help="Check model bundle vs configs/inference.yaml")


@app.command()
def main(
    bundle: Path = typer.Option(Path("data/models/latest"), "--bundle", "-b", help="Model bundle directory."),
    inference_config: Path = typer.Option(
        Path("configs/inference.yaml"),
        "--inference-config",
        "-c",
        help="Config used by the live FastAPI engine.",
    ),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    try:
        report = verify_bundle_for_live(bundle, inference_config=inference_config)
    except TrainServeCompatibilityError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho("Train/serve compatibility: OK", fg=typer.colors.GREEN)
    typer.echo(json.dumps(report, indent=2))


if __name__ == "__main__":
    app()
