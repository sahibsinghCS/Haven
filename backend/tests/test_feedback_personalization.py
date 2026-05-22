from __future__ import annotations

import numpy as np
import pytest

from roomos.personalization import FeedbackReinforcementModel


def test_feedback_correction_biases_similar_future_prediction(tmp_path):
    model = FeedbackReinforcementModel(
        root_dir=tmp_path,
        classes=["work", "relaxing"],
        feature_columns=["a", "b"],
        influence=0.5,
        similarity_floor=0.7,
    )
    model.record_correction(
        predicted_label="work",
        corrected_label="relaxing",
        confidence=0.82,
        features={"a": 1.0, "b": 0.0},
        screenshots_bgr=[np.zeros((8, 8, 3), dtype=np.uint8) for _ in range(5)],
    )

    adjusted, info = model.adjust_probabilities(
        {"a": 1.0, "b": 0.0},
        {"work": 0.8, "relaxing": 0.2},
    )

    assert info["applied"] is True
    assert info.get("memory_examples") == 1
    assert info.get("boosted_label") == "relaxing"
    assert adjusted["relaxing"] > 0.2
    assert adjusted["work"] < 0.8
    assert len(list((tmp_path / "screenshots").glob("*/frame_*.jpg"))) == 5
    assert (tmp_path / "feedback_examples.json").exists()
    assert (tmp_path / "feedback_events.jsonl").exists()


def test_feedback_ignores_dissimilar_examples(tmp_path):
    model = FeedbackReinforcementModel(
        root_dir=tmp_path,
        classes=["work", "relaxing"],
        feature_columns=["a", "b"],
        influence=0.5,
        similarity_floor=0.9,
    )
    model.record_correction(
        predicted_label="work",
        corrected_label="relaxing",
        confidence=0.82,
        features={"a": 1.0, "b": 0.0},
        screenshots_bgr=[],
    )

    adjusted, info = model.adjust_probabilities(
        {"a": 0.0, "b": 1.0},
        {"work": 0.8, "relaxing": 0.2},
    )

    assert info["applied"] is False
    assert adjusted == {"work": pytest.approx(0.8), "relaxing": pytest.approx(0.2)}
