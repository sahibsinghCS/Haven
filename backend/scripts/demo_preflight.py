"""CLI: demo readiness (venv-independent when run via npm run preflight:py)."""

from __future__ import annotations

import _bootstrap  # noqa: F401
import json
import sys

import typer

from roomos.demo.readiness import bundle_readiness, format_missing_model_help, resolve_bundle_dir

app = typer.Typer(add_completion=False, help="Check model bundle before live demo.")


@app.command()
def main(
    bundle: str = typer.Option("", "--bundle", "-b", help="Override bundle directory."),
) -> None:
    bundle_dir = resolve_bundle_dir() if not bundle else bundle
    report = bundle_readiness(bundle_dir)
    typer.echo(json.dumps(report, indent=2))
    if not report["ready"]:
        typer.secho(format_missing_model_help(bundle_dir=bundle_dir), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
