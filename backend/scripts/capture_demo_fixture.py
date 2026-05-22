"""Append the latest live snapshot to a demo replay fixture (for curating demos)."""

from __future__ import annotations

import _bootstrap  # noqa: F401
import json
from datetime import datetime, timezone
from pathlib import Path

import typer

from roomos.utils.io import read_json, write_json

app = typer.Typer(add_completion=False)


@app.command()
def append(
    bundle: Path = typer.Option(Path("configs/demo_replay.json"), "--out", "-o"),
    snapshot: Path = typer.Option(
        None,
        "--snapshot",
        help="JSON file from GET /api/live/snapshot (default: read hub via API URL not supported here)",
    ),
    state: str = typer.Option(..., "--state", "-s"),
    hold_sec: float = typer.Option(6.0, "--hold"),
) -> None:
    """Add a manual step to the fixture (use after saving a snapshot JSON)."""
    path = bundle
    raw = read_json(path) if path.exists() else {"version": 1, "loop": True, "steps": []}
    steps = list(raw.get("steps") or [])
    dist = {state: 0.85}
    for other in ("sleep", "gaming", "work", "relaxing", "away"):
        if other != state:
            dist[other] = 0.03
    step = {
        "state": state,
        "hold_sec": hold_sec,
        "primary_confidence": 0.8,
        "distribution": dist,
        "rationale": [
            f"Captured step at {datetime.now(timezone.utc).isoformat()}",
            "Edit rationale bullets before judging.",
        ],
    }
    if snapshot and snapshot.exists():
        snap = read_json(snapshot)
        step["distribution"] = snap.get("distribution") or dist
        step["primary_confidence"] = snap.get("primaryConfidence", 0.8)
        step["rationale"] = snap.get("rationale") or step["rationale"]
        step["applied_scene"] = snap.get("appliedScene")
    steps.append(step)
    raw["steps"] = steps
    write_json(path, raw)
    typer.echo(f"Wrote {len(steps)} steps to {path}")


if __name__ == "__main__":
    app()
