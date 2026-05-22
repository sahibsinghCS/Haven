"""Generate or refresh ``<bundle>/eval_report/`` for hackathon Q&A."""

from __future__ import annotations

import _bootstrap  # noqa: F401
from pathlib import Path
from typing import Optional

import typer

from roomos.model.eval_report import generate_report_from_bundle
from roomos.utils.logging import setup_logging

app = typer.Typer(add_completion=False, help="Build judge-ready eval_report from a trained bundle.")


@app.command()
def main(
    bundle: Path = typer.Option(Path("data/models/latest"), "--bundle", "-b"),
    features: Optional[Path] = typer.Option(
        None,
        "--features",
        "-f",
        help="Optional features parquet to re-run holdout eval.",
    ),
    recompute: bool = typer.Option(
        False,
        "--recompute",
        help="Re-evaluate on --features instead of using metrics.json splits.",
    ),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    out = generate_report_from_bundle(bundle, features_path=features, recompute=recompute)
    typer.echo(f"Evaluation report written to {out}")
    typer.echo(f"Open: {out / 'REPORT.md'}")


if __name__ == "__main__":
    app()
