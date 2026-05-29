"""Tests for the inference-time occupancy gate.

Covers the four scenarios the user reports:

1. Empty couch / empty desk → gate fires, ``away`` becomes the top class.
2. Person clearly in scene → gate stays silent, original probs untouched.
3. Pose features disabled (Windows DroidCam default) → CLIP-only path still
   detects empty rooms.
4. High-motion empty match (someone walking through) → gate stays silent.
"""

from __future__ import annotations

import pytest

from roomos.inference.occupancy import (
    OccupancyDecision,
    OccupancyGate,
    _slugify_prompt,
    build_gate_from_config,
)


_PERSON_PROMPTS = [
    "a person sitting at a desk working on a computer",
    "a person typing at a laptop",
    "a person reading a book on a couch",
]
_EMPTY_PROMPT = "an empty room with no people"
_EMPTY_COUCH = "an empty living room couch"
_UNOCCUPIED_DESK = "an unoccupied office desk with a monitor and keyboard"


def _empty_feature_row(
    *,
    empty_sim: float,
    person_sim: float,
    motion: float,
    pose: float | None = None,
    couch_sim: float | None = None,
    desk_sim: float | None = None,
):
    """Build a fake fused-burst feature row resembling what FeatureFusion emits.

    Only the keys the gate consults are populated; everything else defaults
    to 0.0 if the gate reads it.
    """
    row: dict[str, float] = {
        f"clip_sim__{_slugify_prompt(_EMPTY_PROMPT)}_mean": float(empty_sim),
        "motion_mean_mean": float(motion),
    }
    for p in _PERSON_PROMPTS:
        row[f"clip_sim__{_slugify_prompt(p)}_mean"] = float(person_sim)
    if couch_sim is not None:
        row[f"clip_sim__{_slugify_prompt(_EMPTY_COUCH)}_mean"] = float(couch_sim)
    if desk_sim is not None:
        row[f"clip_sim__{_slugify_prompt(_UNOCCUPIED_DESK)}_mean"] = float(desk_sim)
    if pose is not None:
        row["pose_present_ratio"] = float(pose)
    return row


def _gate(**overrides) -> OccupancyGate:
    base = dict(
        person_prompts=list(_PERSON_PROMPTS),
        empty_prompts=[_EMPTY_PROMPT],
        scene_empty_prompts=[_EMPTY_COUCH, _UNOCCUPIED_DESK],
        empty_margin=0.015,
        scene_empty_margin=0.008,
        motion_max_for_empty=0.02,
        away_floor_prob=0.78,
        activity_prob_cap=0.12,
        person_absence_clip_max=0.24,
        enabled=True,
        pose_enabled=False,
    )
    base.update(overrides)
    return OccupancyGate(**base)


# --- detect() ------------------------------------------------------------


def test_motion_present_vetoes_empty():
    row = _empty_feature_row(empty_sim=0.30, person_sim=0.18, motion=0.025)
    gate = _gate(motion_min_for_person=0.012)

    decision = gate.detect(row)

    assert not decision.empty
    assert decision.reason == "motion_present"


def test_empty_couch_clip_only_fires_gate():
    # CLIP says "empty room" wins clearly, motion is low, no pose.
    row = _empty_feature_row(empty_sim=0.27, person_sim=0.21, motion=0.004)
    gate = _gate()

    decision = gate.detect(row)

    assert decision.empty is True
    assert decision.reason == "empty_clip"
    assert decision.person_score == pytest.approx(0.21)
    assert decision.empty_score == pytest.approx(0.27)


def test_person_visible_does_not_fire_gate():
    # User on couch with laptop: person prompts dominate.
    row = _empty_feature_row(empty_sim=0.18, person_sim=0.28, motion=0.03)
    gate = _gate()

    decision = gate.detect(row)

    assert decision.empty is False
    assert decision.reason in ("person_visible", "motion_present")


def test_empty_couch_scene_prompt_fires_without_generic_margin():
    """Empty couch can beat weak 'person at desk' CLIP — classic false Work case."""
    row = _empty_feature_row(
        empty_sim=0.21,
        person_sim=0.23,
        motion=0.004,
        couch_sim=0.27,
    )
    gate = _gate()

    decision = gate.detect(row)

    assert decision.empty is True
    assert decision.reason in ("empty_scene", "empty_clip")


def test_soft_empty_caps_false_work():
    row = _empty_feature_row(empty_sim=0.223, person_sim=0.22, motion=0.01)
    gate = _gate()
    decision = gate.detect(row)
    assert decision.soft_empty is True
    raw = {"work": 0.62, "relaxing": 0.18, "sleep": 0.05, "gaming": 0.05, "away": 0.10}
    adjusted = gate.apply(raw, decision)
    assert adjusted["work"] <= 0.13
    assert adjusted["away"] >= 0.55
    assert max(adjusted, key=adjusted.get) == "away"


def test_low_motion_alone_does_not_fire_without_clip_margin():
    # Person sitting very still: low motion but person CLIP signal still wins.
    row = _empty_feature_row(empty_sim=0.21, person_sim=0.22, motion=0.003)
    gate = _gate()

    decision = gate.detect(row)

    assert decision.empty is False


def test_walk_through_high_motion_blocks_gate():
    # CLIP looks empty for a moment but motion is high (someone walking by).
    row = _empty_feature_row(empty_sim=0.30, person_sim=0.20, motion=0.08)
    gate = _gate()

    decision = gate.detect(row)

    assert decision.empty is False


def test_disabled_gate_never_fires():
    row = _empty_feature_row(empty_sim=0.30, person_sim=0.10, motion=0.001)
    gate = _gate(enabled=False)

    decision = gate.detect(row)

    assert decision.empty is False
    assert decision.reason == "disabled"


def test_pose_signal_takes_priority_when_enabled():
    # Pose says no person and motion is low → empty even without CLIP margin.
    row = _empty_feature_row(empty_sim=0.20, person_sim=0.21, motion=0.005, pose=0.0)
    gate = _gate(pose_enabled=True)

    decision = gate.detect(row)

    assert decision.empty is True
    assert decision.reason == "empty_pose"


# --- apply() -------------------------------------------------------------


def test_apply_lifts_away_above_floor_for_empty_decision():
    gate = _gate(away_floor_prob=0.78)
    raw_probs = {"work": 0.6, "relaxing": 0.2, "sleep": 0.05, "gaming": 0.1, "away": 0.05}
    decision = OccupancyDecision(
        empty=True,
        person_score=0.2,
        empty_score=0.27,
        motion=0.004,
        pose_present_ratio=None,
        reason="empty_clip",
    )

    adjusted = gate.apply(raw_probs, decision)

    assert sum(adjusted.values()) == pytest.approx(1.0, abs=1e-6)
    assert adjusted["away"] >= 0.78 - 1e-6
    assert adjusted["work"] < raw_probs["work"]
    assert max(adjusted, key=adjusted.get) == "away"


def test_apply_is_noop_when_not_empty():
    gate = _gate()
    raw_probs = {"work": 0.7, "away": 0.1, "relaxing": 0.2}
    decision = OccupancyDecision(
        empty=False,
        person_score=0.30,
        empty_score=0.18,
        motion=0.03,
        pose_present_ratio=None,
        reason="person_visible",
    )

    adjusted = gate.apply(raw_probs, decision)

    assert max(adjusted, key=adjusted.get) == "work"
    # Should still be normalized.
    assert sum(adjusted.values()) == pytest.approx(sum(raw_probs.values()), abs=1e-6)


def test_apply_preserves_away_already_above_floor():
    gate = _gate(away_floor_prob=0.5)
    raw_probs = {"work": 0.1, "away": 0.85, "relaxing": 0.05}
    decision = OccupancyDecision(
        empty=True,
        person_score=0.0,
        empty_score=0.3,
        motion=0.0,
        pose_present_ratio=None,
        reason="empty_clip",
    )

    adjusted = gate.apply(raw_probs, decision)

    assert adjusted["away"] == pytest.approx(0.85, abs=1e-6)
    assert sum(adjusted.values()) == pytest.approx(1.0, abs=1e-6)


# --- build_gate_from_config ---------------------------------------------


def test_build_gate_from_config_uses_defaults_when_missing():
    gate = build_gate_from_config(
        occupancy_cfg=None,
        away_label="away",
        unknown_label="unknown",
        pose_enabled=False,
    )

    assert gate.enabled is True
    assert gate.away_label == "away"
    assert gate.pose_enabled is False
    # Some person prompts should have been seeded so the gate is functional.
    assert len(gate.person_prompts) > 0
    assert len(gate.empty_prompts) > 0


def test_build_gate_from_config_overrides_apply():
    gate = build_gate_from_config(
        occupancy_cfg={
            "enabled": True,
            "empty_margin": 0.05,
            "motion_max_for_empty": 0.001,
            "away_floor_prob": 0.9,
        },
        away_label="away",
        unknown_label="unknown",
        pose_enabled=True,
    )

    assert gate.empty_margin == pytest.approx(0.05)
    assert gate.motion_max_for_empty == pytest.approx(0.001)
    assert gate.away_floor_prob == pytest.approx(0.9)
    assert gate.pose_enabled is True
