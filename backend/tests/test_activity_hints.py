"""Tests for CLIP-based work / gaming / relaxing disambiguation."""

from __future__ import annotations

from roomos.inference.activity_hints import (
    ActivityHintConfig,
    ActivityHintGate,
    _key,
)
from roomos.inference.occupancy import _slugify_prompt

_GAMING = "a large gaming monitor displaying a colourful video game"
_WORK = "a tidy work desk with a monitor and a notebook"
_COUCH = "a cozy sofa with throw pillows and a blanket"


def test_game_scene_nudges_work_over_relaxing():
    gate = ActivityHintGate(cfg=ActivityHintConfig(nudge_strength=0.3, min_margin=0.01))
    feats = {
        _key(_GAMING): 0.29,
        _key(_WORK): 0.20,
        _key(_COUCH): 0.18,
    }
    probs = {"work": 0.45, "relaxing": 0.35, "sleep": 0.1, "away": 0.1}
    out = gate.apply(probs, feats)
    assert out["work"] > out["relaxing"]


def test_relaxing_beats_work_on_couch_clip():
    gate = ActivityHintGate(cfg=ActivityHintConfig(nudge_strength=0.3, min_margin=0.01))
    feats = {
        _key(_COUCH): 0.28,
        _key(_WORK): 0.19,
        _key(_GAMING): 0.17,
    }
    probs = {"work": 0.5, "relaxing": 0.35, "sleep": 0.1, "away": 0.05}
    out = gate.apply(probs, feats)
    assert out["relaxing"] > out["work"]


def test_reading_beats_work_when_book_clip_strong_and_model_sees_reading():
    gate = ActivityHintGate(cfg=ActivityHintConfig(nudge_strength=0.3, min_margin=0.01))
    reading = "a person reading a book on a couch"
    feats = {
        _key(reading): 0.34,
        _key(_WORK): 0.16,
        _key("a student studying at a desk with laptop and textbooks"): 0.14,
    }
    probs = {"work": 0.48, "reading": 0.32, "relaxing": 0.1, "sleep": 0.05, "away": 0.05}
    out = gate.apply(probs, feats)
    assert out["reading"] > out["work"]


def test_reading_hint_skipped_when_model_does_not_see_reading():
    gate = ActivityHintGate(cfg=ActivityHintConfig(nudge_strength=0.3, min_margin=0.01))
    reading = "a person reading a book on a couch"
    feats = {
        _key(reading): 0.34,
        _key(_WORK): 0.16,
    }
    probs = {"work": 0.72, "reading": 0.05, "relaxing": 0.1, "sleep": 0.08, "away": 0.05}
    out = gate.apply(probs, feats)
    assert out["work"] > out["reading"]
