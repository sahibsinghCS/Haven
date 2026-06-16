"""Rhythm summary aggregation tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from roomos.rhythm.summary import build_rhythm_summary, clear_rhythm_caches


def _write_predictions(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def test_build_rhythm_summary_day_dwell(tmp_path):
    clear_rhythm_caches()
    pred = tmp_path / "predictions.jsonl"
    base = datetime(2026, 6, 15, 20, 0, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(6):
        rows.append(
            {
                "t": (base.replace(minute=i * 2)).isoformat(),
                "label": "work",
                "confidence": 0.8,
                "switched": i == 0,
            }
        )
    for i in range(4):
        rows.append(
            {
                "t": (base.replace(minute=12 + i * 2)).isoformat(),
                "label": "sleep",
                "confidence": 0.75,
                "switched": i == 0,
            }
        )
    _write_predictions(pred, rows)

    summary = build_rhythm_summary(
        "day",
        now=base.replace(hour=23),
        tz_name="UTC",
        predictions_path=pred,
        actions_path=tmp_path / "missing.jsonl",
    )

    assert summary["totalTrackedSec"] > 0
    assert len(summary["moods"]) >= 2
    ids = {m["id"] for m in summary["moods"]}
    assert "work" in ids
    assert "sleep" in ids
    assert summary["highlights"]["moodSwitches"] >= 1


def test_build_rhythm_summary_empty(tmp_path):
    clear_rhythm_caches()
    pred = tmp_path / "predictions.jsonl"
    _write_predictions(pred, [])
    summary = build_rhythm_summary(
        "week",
        now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        predictions_path=pred,
        actions_path=tmp_path / "missing.jsonl",
    )
    assert summary["totalTrackedSec"] == 0
    assert summary["coverageNote"] is not None
