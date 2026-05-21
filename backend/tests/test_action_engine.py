"""Tests for the rule engine."""

from __future__ import annotations

from roomos.actions.engine import ActionEngine
from roomos.actions.rules import LogHandler
from roomos.config import Config


def _engine() -> ActionEngine:
    cfg = Config(
        raw={
            "actions": {
                "dry_run": True,
                "events_log": None,
                "default_min_confidence": 0.5,
                "default_sustain_windows": 2,
                "default_cooldown_sec": 5.0,
                "rules": [
                    {
                        "name": "focus",
                        "when": {"activity": "work", "min_confidence": 0.6, "sustain_windows": 2},
                        "action": {"type": "log", "message": "focus"},
                        "cooldown_sec": 10.0,
                    },
                ],
            }
        }
    )
    return ActionEngine.from_config(cfg)


def test_rule_requires_sustain_windows():
    eng = _engine()
    assert eng.on_prediction(label="work", confidence=0.9, at=0.0) == []
    fired = eng.on_prediction(label="work", confidence=0.9, at=0.5)
    assert len(fired) == 1
    assert fired[0]["rule"] == "focus"


def test_rule_respects_cooldown():
    eng = _engine()
    # Fire once.
    eng.on_prediction(label="work", confidence=0.9, at=0.0)
    eng.on_prediction(label="work", confidence=0.9, at=0.5)
    # Within cooldown — should not refire.
    assert eng.on_prediction(label="work", confidence=0.9, at=1.0) == []
    # After cooldown — should be eligible to refire (still needs sustain).
    eng.on_prediction(label="work", confidence=0.9, at=11.0)
    fired = eng.on_prediction(label="work", confidence=0.9, at=11.5)
    assert len(fired) == 1


def test_rule_resets_when_activity_changes():
    eng = _engine()
    eng.on_prediction(label="work", confidence=0.9, at=0.0)
    eng.on_prediction(label="relaxing", confidence=0.9, at=0.5)
    # The next "work" should restart the sustain counter.
    assert eng.on_prediction(label="work", confidence=0.9, at=1.0) == []


def test_low_confidence_does_not_fire():
    eng = _engine()
    eng.on_prediction(label="work", confidence=0.3, at=0.0)
    assert eng.on_prediction(label="work", confidence=0.3, at=0.5) == []


def test_log_handler_returns_executed():
    h = LogHandler(message="ok")
    from roomos.actions.rules import ActionEvent

    ev = ActionEvent(
        rule_name="r", activity="work", confidence=0.9, at=0.0, iso_time="2026-01-01T00:00:00",
        action_type="log", payload={"type": "log"},
    )
    result = h.execute(ev, dry_run=True)
    assert result["executed"] is True
