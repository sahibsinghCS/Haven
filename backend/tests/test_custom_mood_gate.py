"""Custom mood live inference guardrails."""

from __future__ import annotations

from roomos.inference.custom_mood_gate import (
    CustomMoodGateConfig,
    CustomMoodTrainStats,
    apply_custom_mood_gate,
)


def test_demotes_weak_custom_top_label():
    probs = {"work": 0.22, "relaxing": 0.13, "jump_rope": 0.65}
    out = apply_custom_mood_gate(
        probs,
        {"motion_mean_mean": 0.002},
        custom_mood_ids={"jump_rope"},
        train_stats={
            "jump_rope": CustomMoodTrainStats(
                burst_count=12, motion_median=0.04, motion_p25=0.03
            )
        },
        cfg=CustomMoodGateConfig(),
    )
    assert out["jump_rope"] < 0.05
    assert out["work"] > out["jump_rope"]


def test_keeps_strong_active_custom_label():
    probs = {"work": 0.08, "relaxing": 0.05, "jump_rope": 0.87}
    out = apply_custom_mood_gate(
        probs,
        {"motion_mean_mean": 0.05},
        custom_mood_ids={"jump_rope"},
        train_stats={
            "jump_rope": CustomMoodTrainStats(
                burst_count=12, motion_median=0.04, motion_p25=0.03
            )
        },
        cfg=CustomMoodGateConfig(),
    )
    assert out["jump_rope"] > 0.8


def test_low_motion_custom_keeps_reading_when_confident():
    probs = {"work": 0.12, "reading": 0.82, "relaxing": 0.04}
    out = apply_custom_mood_gate(
        probs,
        {"motion_mean_mean": 0.002},
        custom_mood_ids={"reading"},
        train_stats={
            "reading": CustomMoodTrainStats(
                burst_count=25, motion_median=0.036, motion_p25=0.026
            )
        },
        cfg=CustomMoodGateConfig(),
    )
    assert out["reading"] > 0.75


def test_low_motion_custom_demotes_weak_reading_top_label():
    probs = {"work": 0.35, "reading": 0.55, "relaxing": 0.1}
    out = apply_custom_mood_gate(
        probs,
        {"motion_mean_mean": 0.002},
        custom_mood_ids={"reading"},
        train_stats={
            "reading": CustomMoodTrainStats(
                burst_count=25, motion_median=0.036, motion_p25=0.026
            )
        },
        cfg=CustomMoodGateConfig(),
    )
    assert out["reading"] < 0.05
    assert out["work"] > out["reading"]
