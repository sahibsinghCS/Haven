"""Evaluation report helpers."""

import numpy as np

from roomos.model.eval_report import (
    judge_strengths_weaknesses,
    per_class_table,
    top_confusion_pairs,
)


def test_per_class_table():
    per = {
        "work": {"precision": 0.8, "recall": 0.7, "f1-score": 0.75, "support": 10},
        "sleep": {"precision": 0.6, "recall": 0.4, "f1-score": 0.48, "support": 5},
    }
    rows = per_class_table(per, ["work", "sleep"])
    assert rows[0]["class"] == "work"
    assert rows[0]["f1"] == 0.75


def test_top_confusion_pairs():
    cm = np.array([[8, 2, 0], [1, 7, 0], [0, 1, 9]], dtype=int)
    pairs = top_confusion_pairs(cm, ["work", "sleep", "away"])
    assert pairs[0]["true"] in ("work", "sleep", "away")


def test_judge_strengths_weaknesses():
    rows = per_class_table(
        {
            "work": {"precision": 0.9, "recall": 0.8, "f1-score": 0.85, "support": 12},
            "gaming": {"precision": 0.4, "recall": 0.3, "f1-score": 0.35, "support": 8},
        },
        ["work", "gaming"],
    )
    sw = judge_strengths_weaknesses(rows, [])
    assert any("work" in s for s in sw["strong"])
