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
