"""Publish feedback events after a correction is saved."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .core.feedback_events import FeedbackEvent
from .core.state import state


def publish_feedback_result(
    result: Mapping[str, Any],
    *,
    source: str,
    notes: str = "",
) -> FeedbackEvent:
    correction = result["correction"]
    auto = {}
    if state.engine is not None:
        auto = state.engine.auto_retrain_status()
    event = FeedbackEvent(
        source=source,
        correction_id=str(correction.id),
        created_at=str(correction.created_at),
        predicted_label=str(correction.predicted_label),
        corrected_label=str(correction.corrected_label),
        confirmed=correction.predicted_label == correction.corrected_label,
        notes=str(notes or correction.notes or ""),
        screenshot_count=int(result.get("screenshot_count", len(correction.screenshot_paths))),
        memory_examples=int(result.get("memory_examples", 0)),
        auto_retrain_enabled=bool(auto.get("enabled")),
    )
    state.feedback_hub.publish_from_thread(event)
    return event
