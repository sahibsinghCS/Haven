"""Aggregate mood dwell time and highlights from on-device inference logs."""

from __future__ import annotations

import statistics
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, Optional
from zoneinfo import ZoneInfo

from ..config import load_config
from ..utils.io import read_jsonl
from ..utils.logging import get_logger

log = get_logger("roomos.rhythm")

RhythmRange = Literal["day", "week", "month"]

# Gap longer than this starts a new dwell segment (camera off, away from desk, etc.).
_MAX_GAP_SEC = 15 * 60
# Tail credit for the final prediction in a contiguous run.
_TAIL_SEC = 10.0
# Low-confidence threshold (matches smoothing min_confidence ballpark).
_LOW_CONFIDENCE = 0.45
# Deep work block minimum duration.
_DEEP_WORK_MIN_SEC = 45 * 60
# Rough $/automation for display estimates when real metering is unavailable.
_SAVINGS_PER_SLEEP_ACTION_USD = 0.08
_SAVINGS_PER_AWAY_ACTION_USD = 0.05
_SAVINGS_PER_DIM_USD = 0.03


@dataclass(frozen=True)
class _PredictionRow:
    at: datetime
    label: str
    confidence: float
    switched: bool


_prediction_cache_lock = threading.Lock()
_prediction_cache: dict[str, tuple[float, list[_PredictionRow]]] = {}


def clear_rhythm_caches() -> None:
    """Drop in-memory prediction caches (tests / hot reload)."""
    with _prediction_cache_lock:
        _prediction_cache.clear()


def _parse_prediction_record(record: dict[str, Any]) -> Optional[_PredictionRow]:
    at = _parse_ts(str(record.get("t") or ""))
    if at is None:
        return None
    label = str(record.get("label") or "").strip()
    if not label:
        return None
    return _PredictionRow(
        at=at,
        label=label,
        confidence=float(record.get("confidence") or 0.0),
        switched=bool(record.get("switched")),
    )


def _all_predictions(path: Path) -> list[_PredictionRow]:
    """Load and cache all prediction rows; invalidated when the log file mtime changes."""
    if not path.is_file():
        return []
    key = str(path.resolve())
    mtime = path.stat().st_mtime
    with _prediction_cache_lock:
        cached = _prediction_cache.get(key)
        if cached is not None and cached[0] == mtime:
            return cached[1]

    rows: list[_PredictionRow] = []
    for record in read_jsonl(path):
        row = _parse_prediction_record(record)
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda r: r.at)

    with _prediction_cache_lock:
        _prediction_cache[key] = (mtime, rows)
    return rows


def _rows_in_range(rows: list[_PredictionRow], start: datetime, end: datetime) -> list[_PredictionRow]:
    return [r for r in rows if start <= r.at <= end]


def _parse_ts(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _range_bounds(
    range_key: RhythmRange,
    *,
    now: datetime,
    tz: ZoneInfo,
) -> tuple[datetime, datetime, datetime, datetime]:
    """Return (start, end, prev_start, prev_end) as timezone-aware UTC."""
    local_now = now.astimezone(tz)
    local_end = local_now
    if range_key == "day":
        local_start = datetime.combine(local_now.date(), time.min, tzinfo=tz)
        prev_end = local_start
        prev_start = local_start - timedelta(days=1)
    elif range_key == "week":
        # Monday-start week
        weekday = local_now.weekday()
        local_start = datetime.combine(
            local_now.date() - timedelta(days=weekday), time.min, tzinfo=tz
        )
        span = local_end - local_start
        prev_end = local_start
        prev_start = local_start - span
    else:
        local_start = datetime.combine(local_now.date().replace(day=1), time.min, tzinfo=tz)
        span = local_end - local_start
        prev_end = local_start
        prev_start = local_start - span

    def _to_utc(dt: datetime) -> datetime:
        return dt.astimezone(timezone.utc)

    return _to_utc(local_start), _to_utc(local_end), _to_utc(prev_start), _to_utc(prev_end)


def _load_predictions(path: Path, start: datetime, end: datetime) -> list[_PredictionRow]:
    return _rows_in_range(_all_predictions(path), start, end)


def _accumulate_dwell(rows: list[_PredictionRow]) -> tuple[dict[str, float], float, list[float]]:
    """Return per-mood seconds, total seconds, confidence samples."""
    by_mood: dict[str, float] = defaultdict(float)
    confidences: list[float] = []
    if not rows:
        return dict(by_mood), 0.0, confidences

    for i, row in enumerate(rows):
        confidences.append(row.confidence)
        if i + 1 < len(rows):
            nxt = rows[i + 1]
            gap = (nxt.at - row.at).total_seconds()
            if gap <= 0:
                continue
            if gap > _MAX_GAP_SEC:
                by_mood[row.label] += _TAIL_SEC
            else:
                by_mood[row.label] += gap
        else:
            by_mood[row.label] += _TAIL_SEC

    total = sum(by_mood.values())
    return dict(by_mood), total, confidences


def _sleep_starts_local(rows: list[_PredictionRow], tz: ZoneInfo) -> list[time]:
    """First sustained sleep block per local calendar day (>= 20 min)."""
    by_day: dict[date, list[_PredictionRow]] = defaultdict(list)
    for row in rows:
        if row.label != "sleep":
            continue
        by_day[row.at.astimezone(tz).date()].append(row)

    starts: list[time] = []
    min_block = 20 * 60
    for day_rows in by_day.values():
        day_rows.sort(key=lambda r: r.at)
        block_start: Optional[datetime] = None
        block_label: Optional[str] = None
        for i, row in enumerate(day_rows):
            if block_start is None:
                block_start = row.at
                block_label = row.label
                continue
            gap = (row.at - day_rows[i - 1].at).total_seconds() if i > 0 else 0
            if gap > _MAX_GAP_SEC:
                duration = (day_rows[i - 1].at - block_start).total_seconds() + _TAIL_SEC
                if block_label == "sleep" and duration >= min_block:
                    starts.append(block_start.astimezone(tz).timetz().replace(tzinfo=None))
                block_start = row.at
                block_label = row.label
        if block_start and block_label == "sleep":
            duration = (day_rows[-1].at - block_start).total_seconds() + _TAIL_SEC
            if duration >= min_block:
                starts.append(block_start.astimezone(tz).timetz().replace(tzinfo=None))
    return starts


def _median_time(times: list[time]) -> Optional[str]:
    if not times:
        return None
    minutes = sorted(t.hour * 60 + t.minute for t in times)
    mid = minutes[len(minutes) // 2]
    return f"{mid // 60:02d}:{mid % 60:02d}"


def _sleep_consistency(times: list[time]) -> Optional[str]:
    if len(times) < 3:
        return None
    minutes = [t.hour * 60 + t.minute for t in times]
    stdev = statistics.pstdev(minutes)
    if stdev <= 25:
        return "steady"
    if stdev <= 55:
        return "mixed"
    return "variable"


def _deep_work_stats(rows: list[_PredictionRow]) -> tuple[int, float]:
    """Count work blocks >= 45 min and total minutes in those blocks."""
    if not rows:
        return 0, 0.0
    blocks = 0
    total_sec = 0.0
    block_start: Optional[datetime] = None
    prev_at: Optional[datetime] = None
    for row in rows:
        if row.label != "work":
            if block_start and prev_at:
                dur = (prev_at - block_start).total_seconds() + _TAIL_SEC
                if dur >= _DEEP_WORK_MIN_SEC:
                    blocks += 1
                    total_sec += dur
            block_start = None
            prev_at = row.at
            continue
        if block_start is None:
            block_start = row.at
        elif prev_at and (row.at - prev_at).total_seconds() > _MAX_GAP_SEC:
            dur = (prev_at - block_start).total_seconds() + _TAIL_SEC
            if dur >= _DEEP_WORK_MIN_SEC:
                blocks += 1
                total_sec += dur
            block_start = row.at
        prev_at = row.at
    if block_start and prev_at:
        dur = (prev_at - block_start).total_seconds() + _TAIL_SEC
        if dur >= _DEEP_WORK_MIN_SEC:
            blocks += 1
            total_sec += dur
    return blocks, total_sec / 60.0


def _wind_down_minutes(rows: list[_PredictionRow]) -> Optional[float]:
    """Relaxing → sleep within 3h before first sleep block of the day."""
    if not rows:
        return None
    gaps: list[float] = []
    i = 0
    while i < len(rows):
        if rows[i].label != "sleep":
            i += 1
            continue
        sleep_start = rows[i].at
        j = i - 1
        last_relax: Optional[datetime] = None
        while j >= 0:
            gap_back = (rows[j + 1].at - rows[j].at).total_seconds()
            if gap_back > _MAX_GAP_SEC:
                break
            if rows[j].label == "relaxing":
                last_relax = rows[j].at
            elif rows[j].label in ("work", "away"):
                break
            j -= 1
        if last_relax:
            delta = (sleep_start - last_relax).total_seconds() / 60.0
            if 0 < delta <= 180:
                gaps.append(delta)
        i += 1
    if not gaps:
        return None
    return round(statistics.mean(gaps), 1)


def _estimate_savings(actions_path: Path, start: datetime, end: datetime) -> tuple[float, int, bool]:
    if not actions_path.is_file():
        return 0.0, 0, True
    total = 0.0
    count = 0
    any_dry = False
    for record in read_jsonl(actions_path):
        at = _parse_ts(str(record.get("t") or ""))
        if at is None or at < start or at > end:
            continue
        activity = str(record.get("activity") or "")
        dry = bool(record.get("dry_run"))
        result = record.get("result") or {}
        executed = bool(result.get("executed"))
        if dry:
            any_dry = True
        if not executed and not dry:
            continue
        count += 1
        rule = str(record.get("rule") or "")
        if activity == "sleep" or "sleep" in rule:
            total += _SAVINGS_PER_SLEEP_ACTION_USD
        elif activity == "away":
            total += _SAVINGS_PER_AWAY_ACTION_USD
        elif "dim" in rule:
            total += _SAVINGS_PER_DIM_USD
        else:
            total += 0.02
    return round(total, 2), count, any_dry


def _daily_breakdown(
    rows: list[_PredictionRow],
    tz: ZoneInfo,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Per-local-day mood seconds for stacked charts."""
    if not rows:
        return []
    by_day: dict[date, list[_PredictionRow]] = defaultdict(list)
    for row in rows:
        by_day[row.at.astimezone(tz).date()].append(row)

    out: list[dict[str, Any]] = []
    cur = start.astimezone(tz).date()
    end_date = end.astimezone(tz).date()
    while cur <= end_date:
        day_rows = by_day.get(cur, [])
        moods, total, _ = _accumulate_dwell(day_rows)
        out.append(
            {
                "date": cur.isoformat(),
                "totalSec": round(total, 1),
                "moods": {k: round(v, 1) for k, v in sorted(moods.items())},
            }
        )
        cur += timedelta(days=1)
    return out


def _mood_labels() -> dict[str, str]:
    labels: dict[str, str] = {}
    try:
        from ..moods.registry import load_registry

        doc = load_registry()
        for mood in doc.get("moods") or []:
            if isinstance(mood, dict):
                mid = str(mood.get("id") or "")
                if mid:
                    labels[mid] = str(mood.get("displayName") or mid)
    except Exception as exc:
        log.debug("Could not load mood labels: %s", exc)
    return labels


def _format_moods(
    by_mood: Mapping[str, float],
    total: float,
    labels: Mapping[str, str],
) -> list[dict[str, Any]]:
    items = sorted(by_mood.items(), key=lambda kv: kv[1], reverse=True)
    result: list[dict[str, Any]] = []
    for mood_id, seconds in items:
        pct = (seconds / total * 100.0) if total > 0 else 0.0
        result.append(
            {
                "id": mood_id,
                "label": labels.get(mood_id) or mood_id.replace("_", " ").title(),
                "seconds": round(seconds, 1),
                "percent": round(pct, 1),
            }
        )
    return result


def build_rhythm_summaries(
    *,
    now: Optional[datetime] = None,
    tz_name: str = "UTC",
    predictions_path: Optional[Path] = None,
    actions_path: Optional[Path] = None,
) -> dict[RhythmRange, dict[str, Any]]:
    """Build day/week/month summaries with a single predictions log read."""
    ranges: tuple[RhythmRange, ...] = ("day", "week", "month")
    return {
        range_key: build_rhythm_summary(
            range_key,
            now=now,
            tz_name=tz_name,
            predictions_path=predictions_path,
            actions_path=actions_path,
        )
        for range_key in ranges
    }


def build_rhythm_summary(
    range_key: RhythmRange,
    *,
    now: Optional[datetime] = None,
    tz_name: str = "UTC",
    predictions_path: Optional[Path] = None,
    actions_path: Optional[Path] = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    cfg = load_config()
    pred_path = predictions_path
    if pred_path is None:
        infer = cfg.get("inference", {}) or {}
        raw = Path(str(infer.get("predictions_log", "data/logs/predictions.jsonl")))
        pred_path = raw if raw.is_absolute() else cfg.resolve_path(raw)

    act_path = actions_path
    if act_path is None:
        actions_cfg = cfg.get("actions", {}) or {}
        raw_act = Path(str(actions_cfg.get("events_log", "data/events/actions.jsonl")))
        act_path = raw_act if raw_act.is_absolute() else cfg.resolve_path(raw_act)

    start, end, prev_start, prev_end = _range_bounds(range_key, now=now, tz=tz)
    labels = _mood_labels()

    all_rows = _all_predictions(pred_path)
    rows = _rows_in_range(all_rows, start, end)
    prev_rows = _rows_in_range(all_rows, prev_start, prev_end)

    by_mood, total_sec, confidences = _accumulate_dwell(rows)
    prev_by_mood, prev_total, _ = _accumulate_dwell(prev_rows)

    mood_switches = sum(1 for r in rows if r.switched)
    sleep_starts = _sleep_starts_local(rows, tz)
    deep_blocks, deep_minutes = _deep_work_stats(rows)
    away_sec = by_mood.get("away", 0.0)
    savings_usd, automations, savings_dry = _estimate_savings(act_path, start, end)
    uncertain_pct = (
        round(sum(1 for c in confidences if c < _LOW_CONFIDENCE) / len(confidences) * 100.0, 1)
        if confidences
        else None
    )
    avg_conf = round(statistics.mean(confidences), 3) if confidences else None

    mood_deltas: dict[str, float] = {}
    all_ids = set(by_mood) | set(prev_by_mood)
    for mood_id in all_ids:
        mood_deltas[mood_id] = round(by_mood.get(mood_id, 0.0) - prev_by_mood.get(mood_id, 0.0), 1)

    coverage = (
        "No live inference in this period. Open Live with the camera on to build your rhythm."
        if total_sec <= 0
        else None
    )

    return {
        "range": range_key,
        "rangeStart": start.isoformat(),
        "rangeEnd": end.isoformat(),
        "timezone": str(tz),
        "totalTrackedSec": round(total_sec, 1),
        "coverageNote": coverage,
        "moods": _format_moods(by_mood, total_sec, labels),
        "highlights": {
            "moodSwitches": mood_switches,
            "usualSleepStart": _median_time(sleep_starts),
            "sleepStartSamples": len(sleep_starts),
            "sleepConsistency": _sleep_consistency(sleep_starts),
            "windDownMinutes": _wind_down_minutes(rows),
            "deepWorkBlocks": deep_blocks,
            "deepWorkMinutes": round(deep_minutes, 1),
            "awayHours": round(away_sec / 3600.0, 2),
            "estimatedSavingsUsd": savings_usd,
            "savingsIsEstimate": True,
            "savingsIncludesDryRun": savings_dry,
            "automationsRun": automations,
            "avgConfidence": avg_conf,
            "uncertainPercent": uncertain_pct,
        },
        "dailyBreakdown": _daily_breakdown(rows, tz, start, end) if range_key != "day" else [],
        "comparison": {
            "previousTotalSec": round(prev_total, 1),
            "moodDeltaSec": mood_deltas,
        },
        "sources": {
            "predictionsLog": str(pred_path),
            "actionsLog": str(act_path),
        },
    }
