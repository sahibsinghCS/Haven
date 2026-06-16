"""Review API reads disk-backed transitions without a running engine."""

from __future__ import annotations

import numpy as np

from app.core.state import state
from roomos.personalization import TransitionJournal


def test_list_transitions_without_engine(monkeypatch, tmp_path):
    journal_dir = tmp_path / "transitions"
    journal = TransitionJournal(root_dir=journal_dir, max_entries=50)
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    journal.record_switch(
        from_label="work",
        to_label="relaxing",
        confidence=0.8,
        sequence=1,
        features={"a": 1.0},
        raw_probs={"work": 0.2, "relaxing": 0.7},
        screenshots_bgr=[frame],
    )

    monkeypatch.setattr(state, "engine", None)

    def _journal():
        return journal

    monkeypatch.setattr(state, "transition_journal", _journal)

    from app.api.live import list_transitions

    payload = list_transitions(limit=10, uncorrected_only=False)
    assert payload["enabled"] is True
    assert len(payload["transitions"]) == 1
    assert payload["transitions"][0]["fromLabel"] == "work"
    assert payload["transitions"][0]["toLabel"] == "relaxing"


def test_clear_transitions_without_engine(monkeypatch, tmp_path):
    journal_dir = tmp_path / "transitions"
    journal = TransitionJournal(root_dir=journal_dir, max_entries=50)
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    journal.record_switch(
        from_label="work",
        to_label="relaxing",
        confidence=0.8,
        sequence=1,
        features={"a": 1.0},
        raw_probs={"work": 0.2, "relaxing": 0.7},
        screenshots_bgr=[frame],
    )

    monkeypatch.setattr(state, "engine", None)
    monkeypatch.setattr(state, "transition_journal", lambda: journal)

    from app.api.live import clear_transitions, list_transitions

    cleared = clear_transitions()
    assert cleared["status"] == "cleared"
    assert cleared["removed"] == 1
    assert cleared["total"] == 0

    payload = list_transitions(limit=10, uncorrected_only=False)
    assert payload["transitions"] == []
