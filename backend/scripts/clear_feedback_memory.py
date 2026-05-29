#!/usr/bin/env python3
"""Remove live feedback memory, transition journal, and screenshot evidence."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import typer

import _bootstrap  # noqa: F401

from roomos.config import load_config

app = typer.Typer(add_completion=False)


def _empty_feedback(path: Path) -> None:
    meta: dict = {"classes": [], "featureColumns": []}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                meta["classes"] = list(data.get("classes") or [])
                meta["featureColumns"] = list(data.get("featureColumns") or [])
        except Exception:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "classes": meta["classes"],
                "featureColumns": meta["featureColumns"],
                "examples": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _clear_dir(root: Path) -> int:
    removed = 0
    if not root.exists():
        return 0
    for child in root.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
        else:
            child.unlink(missing_ok=True)
            removed += 1
    return removed


@app.command()
def main(
    config: Path = typer.Option(Path("configs/inference.yaml"), "--config", "-c"),
) -> None:
    cfg = load_config(config)
    infer = cfg.get("inference", {}) or {}
    fb_dir = cfg.resolve_path(Path(infer.get("feedback", {}).get("dir", "data/feedback")))
    tr_dir = cfg.resolve_path(Path(infer.get("transitions", {}).get("dir", "data/transitions")))

    examples_path = fb_dir / "feedback_examples.json"
    _empty_feedback(examples_path)
    (fb_dir / "feedback_events.jsonl").write_text("", encoding="utf-8")
    fb_shots = fb_dir / "screenshots"
    if fb_shots.exists():
        shutil.rmtree(fb_shots, ignore_errors=True)

    tr_index = tr_dir / "transitions_index.json"
    tr_dir.mkdir(parents=True, exist_ok=True)
    tr_index.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "transitions": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (tr_dir / "transitions.jsonl").write_text("", encoding="utf-8")
    tr_shots = tr_dir / "screenshots"
    if tr_shots.exists():
        shutil.rmtree(tr_shots, ignore_errors=True)

    typer.echo(
        json.dumps(
            {
                "ok": True,
                "feedback_dir": str(fb_dir),
                "transitions_dir": str(tr_dir),
                "feedback_examples": str(examples_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
