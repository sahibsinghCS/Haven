"""Tests for the prediction smoother."""

from __future__ import annotations

from roomos.inference.smoothing import PredictionSmoother, smoothing_confirm_bursts


def _smoother(**overrides):
    base = dict(
        classes=["work", "sleep", "gaming"],
        unknown_label="unknown",
        min_confidence=0.5,
        ema_alpha=1.0,
        confirm_bursts=2,
        cooldown_sec=0.0,
    )
    base.update(overrides)
    return PredictionSmoother(**base)


def test_unknown_below_confidence():
    s = _smoother()
    out = s.update({"work": 0.34, "sleep": 0.33, "gaming": 0.33}, now=0.0)
    assert out.label == "unknown"


def test_requires_consecutive_confirmations():
    s = _smoother()
    out1 = s.update({"work": 0.9, "sleep": 0.05, "gaming": 0.05}, now=0.0)
    assert out1.label == "unknown"
    out2 = s.update({"work": 0.9, "sleep": 0.05, "gaming": 0.05}, now=0.1)
    assert out2.label == "work"
    assert out2.switched


def test_cooldown_blocks_immediate_switch():
    s = _smoother(cooldown_sec=10.0, confirm_bursts=1)
    s.update({"work": 0.9, "sleep": 0.05, "gaming": 0.05}, now=0.0)
    out = s.update({"sleep": 0.9, "work": 0.05, "gaming": 0.05}, now=1.0)
    assert out.label == "work", "cooldown should prevent switching"


def test_input_renormalized_to_known_classes():
    s = _smoother(confirm_bursts=1)
    out = s.update({"work": 0.9, "junk": 0.5}, now=0.0)
    assert out.label == "work"
    assert "junk" not in out.smoothed_probs


def test_smoothing_confirm_bursts_prefers_new_key():
    assert smoothing_confirm_bursts({"confirm_bursts": 5, "confirm_windows": 1}) == 5


def test_smoothing_confirm_bursts_legacy_windows():
    assert smoothing_confirm_bursts({"confirm_windows": 3}) == 3
