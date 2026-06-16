"""Rhythm analytics HTTP routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from roomos.rhythm import build_rhythm_summary, build_rhythm_summaries

router = APIRouter(prefix="/api/rhythm", tags=["rhythm"])

RhythmRangeParam = Literal["day", "week", "month"]


@router.get("/summary")
def rhythm_summary(
    range: RhythmRangeParam = Query("week", alias="range"),
    tz: str = Query("UTC", min_length=1, max_length=64),
) -> dict:
    """Aggregate mood dwell time and lifestyle highlights from local inference logs."""
    return build_rhythm_summary(range, tz_name=tz)


@router.get("/summaries")
def rhythm_summaries(
    tz: str = Query("UTC", min_length=1, max_length=64),
) -> dict[str, dict]:
    """Day, week, and month summaries in one response (single log read)."""
    return build_rhythm_summaries(tz_name=tz)
