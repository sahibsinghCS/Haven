"""Tests for state-transition journal + relabel → feedback memory."""

from __future__ import annotations

import numpy as np
import pytest

from roomos.personalization import FeedbackReinforcementModel, TransitionJournal


def test_record_and_list_transition(tmp_path):
    journal = TransitionJournal(root_dir=tmp_path / "transitions", max_entries=50)
    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    t = journal.record_switch(
        from_label="relaxing",
        to_label="sleep",
        confidence=0.71,
        sequence=3,
        features={"feat_a": 1.0, "feat_b": 0.0},
        raw_probs={"sleep": 0.6, "relaxing": 0.2},
        screenshots_bgr=[frame, frame],
    )
    assert t.from_label == "relaxing"
    assert t.to_label == "sleep"
    assert t.screenshot_count == 2

    listed = journal.list_transitions(limit=10)
    assert len(listed) == 1
    assert listed[0].id == t.id
    assert listed[0].corrected_label is None

    path = journal.screenshot_path(t.id, 1)
    assert path is not None and path.is_file()


def test_relabel_wires_feedback_memory(tmp_path):
    feedback_dir = tmp_path / "feedback"
    journal = TransitionJournal(root_dir=tmp_path / "transitions")
    feedback = FeedbackReinforcementModel(
        root_dir=feedback_dir,
        classes=["work", "sleep", "relaxing"],
        feature_columns=["feat_a", "feat_b"],
        similarity_floor=0.3,
        influence=0.8,
    )
    frame = np.full((32, 32, 3), 128, dtype=np.uint8)
    rec = journal.record_switch(
        from_label="unknown",
        to_label="sleep",
        confidence=0.8,
        sequence=1,
        features={"feat_a": 1.0, "feat_b": 0.0},
        raw_probs={"sleep": 0.8, "relaxing": 0.1},
        screenshots_bgr=[frame],
    )
    row = journal.get_record(rec.id)
    assert row is not None
    shots = journal.load_screenshots_bgr(rec.id)
    correction = feedback.record_correction(
        predicted_label="sleep",
        corrected_label="relaxing",
        confidence=0.8,
        features=row["features"],
        screenshots_bgr=shots,
    )
    journal.mark_corrected(rec.id, corrected_label="relaxing", correction_id=correction.id)

    listed = journal.list_transitions(uncorrected_only=True)
    assert len(listed) == 0

    adjusted, info = feedback.adjust_probabilities(
        {"feat_a": 1.0, "feat_b": 0.0},
        {"sleep": 0.8, "relaxing": 0.1},
    )
    assert info["applied"] is True
    assert adjusted["relaxing"] > 0.1


def test_clear_all_transitions(tmp_path):
    journal = TransitionJournal(root_dir=tmp_path / "transitions", max_entries=50)
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    journal.record_switch(
        from_label="work",
        to_label="away",
        confidence=0.5,
        sequence=1,
        features={"a": 1.0},
        raw_probs={"work": 0.4, "away": 0.5},
        screenshots_bgr=[frame],
    )
    removed = journal.clear_all()
    assert removed == 1
    assert journal.count == 0
    assert journal.list_transitions(limit=10) == []
