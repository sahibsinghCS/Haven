"""Smoke test that the shipped bundle in ``data/models/latest`` meets a
minimum held-out accuracy bar.

This is intentionally lenient (skipped when the bundle has not been trained
on a real eval split) — the goal is to catch regressions where someone
re-runs ``bootstrap_demo`` and accidentally ships a 5-row synthetic-stills
bundle into ``data/models/latest``.

Configured threshold (test accuracy) lives in this file:

* ``REQUIRED_ACCURACY`` — minimum acceptable accuracy on the bundle's held-out
  ``test`` split as recorded in ``training_summary.json`` /
  ``eval_report/metrics_summary.json``.
* ``REQUIRED_SAMPLES`` — minimum number of test samples; below this the
  accuracy number is noisy enough that we skip the assertion.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Cold-start product bar: generic multi-room model on unseen rooms (see docs/COLD-START.md).
COLD_START_MIN_ACCURACY = 0.60
COLD_START_MIN_MACRO_F1 = 0.60
COLD_START_MIN_MEAN_RECALL = 0.60
COLD_START_MIN_WORK_RECALL = 0.52
# Stricter bar for release notes / aspirational CI (optional future gate).
RELEASE_TARGET_ACCURACY = 0.80
REQUIRED_SAMPLES = 50

_BUNDLE_DIR = Path(__file__).resolve().parents[1] / "data" / "models" / "latest"
_METRICS_PATH = _BUNDLE_DIR / "eval_report" / "metrics_summary.json"


def _load_metrics() -> dict | None:
    if not _METRICS_PATH.exists():
        return None
    try:
        return json.loads(_METRICS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def test_bundle_meets_minimum_accuracy():
    metrics = _load_metrics()
    if metrics is None:
        pytest.skip(
            f"No eval report at {_METRICS_PATH}; run `npm run train:multi-room` "
            "to produce the model bundle that this test enforces."
        )

    n = int(metrics.get("n_eval_samples", 0) or 0)
    if n < REQUIRED_SAMPLES:
        pytest.skip(
            f"Eval split too small to enforce accuracy bar "
            f"(n={n}, need >= {REQUIRED_SAMPLES})."
        )

    accuracy = float(metrics.get("accuracy", 0.0) or 0.0)
    macro_f1 = float(metrics.get("macro_f1", 0.0) or 0.0)
    split = metrics.get("eval_split", "test")
    assert accuracy >= COLD_START_MIN_ACCURACY, (
        f"Bundle {_BUNDLE_DIR} {split} accuracy {accuracy:.3f} is below the "
        f"cold-start minimum {COLD_START_MIN_ACCURACY:.2f}. See docs/COLD-START.md."
    )
    assert macro_f1 >= COLD_START_MIN_MACRO_F1, (
        f"Bundle {_BUNDLE_DIR} macro F1 {macro_f1:.3f} is below cold-start "
        f"minimum {COLD_START_MIN_MACRO_F1:.2f}."
    )


def test_bundle_mean_per_class_recall_meets_cold_start():
    """Average recall across the five states should meet the ~60% cold-start goal."""
    metrics = _load_metrics()
    if metrics is None:
        pytest.skip(f"No eval report at {_METRICS_PATH}.")

    n = int(metrics.get("n_eval_samples", 0) or 0)
    if n < REQUIRED_SAMPLES:
        pytest.skip("Eval split too small.")

    per_class = metrics.get("per_class") or []
    recalls = [
        float(item.get("recall", 0.0))
        for item in per_class
        if isinstance(item, dict) and int(item.get("support", 0)) >= 5
    ]
    if len(recalls) < 5:
        pytest.skip("Per-class metrics incomplete.")
    mean_recall = sum(recalls) / len(recalls)
    assert mean_recall >= COLD_START_MIN_MEAN_RECALL, (
        f"Mean per-class recall {mean_recall:.3f} is below cold-start target "
        f"{COLD_START_MIN_MEAN_RECALL:.2f}. recalls={recalls}"
    )


def test_bundle_work_recall_meets_cold_start():
    metrics = _load_metrics()
    if metrics is None:
        pytest.skip(f"No eval report at {_METRICS_PATH}.")

    per_class = metrics.get("per_class") or []
    work_dict = next(
        (
            x
            for x in per_class
            if isinstance(x, dict)
            and str(x.get("class", x.get("label", ""))) == "work"
        ),
        None,
    )
    if work_dict is None:
        pytest.skip("No work metrics in eval report.")
    work_rec = float(work_dict.get("recall", 0.0))
    if int(work_dict.get("support", 0)) < 5:
        pytest.skip("Too few work test samples.")
    assert work_rec >= COLD_START_MIN_WORK_RECALL, (
        f"Work recall {work_rec:.3f} below cold-start target {COLD_START_MIN_WORK_RECALL:.2f}. "
        "Run npm run train:multi-room-v3."
    )


def test_bundle_has_balanced_per_class_recall():
    """No single class may collapse to < 40% recall on the eval split — that
    catches "the model is just predicting one class" regressions even when
    overall accuracy looks healthy."""
    metrics = _load_metrics()
    if metrics is None:
        pytest.skip(f"No eval report at {_METRICS_PATH}.")

    n = int(metrics.get("n_eval_samples", 0) or 0)
    if n < REQUIRED_SAMPLES:
        pytest.skip("Eval split too small to enforce per-class recall.")

    per_class = metrics.get("per_class") or []
    weak = [
        item
        for item in per_class
        if isinstance(item, dict)
        and float(item.get("recall", 0.0)) < 0.40
        and int(item.get("support", 0)) >= 5
        and str(item.get("class", item.get("label", ""))) != "work"
    ]
    assert not weak, (
        f"Per-class recall collapse: {weak}. The model is ignoring at least "
        "one class — re-balance the dataset (more images for those classes "
        "in data/base_images/) or revisit class_weighting in the train config."
    )
