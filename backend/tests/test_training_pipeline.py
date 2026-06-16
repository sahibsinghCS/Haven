"""Smoke test for the training pipeline on synthetic data."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

xgboost = pytest.importorskip("xgboost")
sklearn = pytest.importorskip("sklearn")

from roomos.config import Config
from roomos.model.predict import predict_proba_row
from roomos.model.registry import load_model_bundle
from roomos.model.train import train_model


def _fake_dataset(n_per_class: int = 40, n_features: int = 12, seed: int = 0):
    rng = np.random.default_rng(seed)
    classes = ["work", "sleep", "relaxing", "away"]
    rows = []
    for ci, cls in enumerate(classes):
        for j in range(n_per_class):
            # Each class gets its own "signature" — feature `ci` is high.
            base = rng.normal(0.0, 0.2, n_features).astype(np.float32)
            base[ci] += 3.0
            row = {"source": f"vid_{cls}_{j // 8}", "start_time": j * 1.0, "end_time": j * 1.0 + 3.0, "num_frames": 18}
            for k in range(n_features):
                row[f"feat_{k:02d}"] = float(base[k])
            row["label"] = cls
            rows.append(row)
    return pd.DataFrame(rows)


def _train_config(tmp_path) -> Config:
    cfg = Config(
        raw={
            "labels": {"classes": ["work", "sleep", "relaxing", "away"], "unknown_class": "unknown"},
            "training": {
                "output_dir": str(tmp_path / "bundle"),
                "random_state": 7,
                "split": {"strategy": "by_source", "val_size": 0.2, "test_size": 0.2},
                "class_weighting": "balanced",
                "xgboost": {
                    "objective": "multi:softprob",
                    "eval_metric": "mlogloss",
                    "n_estimators": 60,
                    "max_depth": 4,
                    "learning_rate": 0.2,
                    "subsample": 1.0,
                    "colsample_bytree": 1.0,
                    "min_child_weight": 1,
                    "reg_lambda": 1.0,
                    "tree_method": "hist",
                    "n_jobs": 1,
                },
            },
        }
    )
    return cfg


def test_training_smoke(tmp_path):
    df = _fake_dataset()
    cfg = _train_config(tmp_path)
    result = train_model(df, cfg)
    assert result.bundle_dir.exists()
    assert (result.bundle_dir / "model.json").exists()
    assert (result.bundle_dir / "label_encoder.json").exists()
    assert (result.bundle_dir / "feature_columns.json").exists()
    # Should at least beat random on this engineered task.
    test_or_val = result.metrics.get("test") or result.metrics.get("val") or result.metrics["train"]
    assert test_or_val["accuracy"] > 0.5


def test_apply_row_weights_multiplies_sample_weight():
    from roomos.model.train import _apply_row_weights, _compute_sample_weights

    y = np.array([0, 0, 1, 1], dtype=np.int32)
    train_df = pd.DataFrame({"row_weight": [12.0, 12.0, 1.0, 1.0]})
    sw = _compute_sample_weights(y, "balanced")
    out = _apply_row_weights(sw, train_df, {"use_row_weights": True})
    assert out is not None
    assert out[0] > out[2]
    assert float(out[:2].sum()) > float(out[2:].sum())


def test_equal_total_class_weights_with_row_weights():
    from roomos.model.train import _compute_train_sample_weights

    train_df = pd.DataFrame(
        {
            "label": ["jump_rope"] * 20 + ["work"] * 5,
            "row_weight": [12.0] * 20 + [12.0] * 5,
        }
    )
    y = np.zeros(len(train_df), dtype=np.int32)
    y[20:] = 1
    sw = _compute_train_sample_weights(
        train_df,
        y,
        {"class_weighting": "balanced", "use_row_weights": True},
    )
    assert sw is not None
    jump_total = float(sw[:20].sum())
    work_total = float(sw[20:].sum())
    assert jump_total == pytest.approx(work_total, rel=1e-5)
    # More bursts in jump_rope -> lower per-burst weight.
    assert sw[0] < sw[20]


def test_equal_total_class_weights_custom_mood_fraction():
    from roomos.model.train import _compute_train_sample_weights

    train_df = pd.DataFrame(
        {
            "label": ["reading"] * 24 + ["work"] * 586,
            "row_weight": [2.0] * 24 + [1.0] * 586,
        }
    )
    y = np.zeros(len(train_df), dtype=np.int32)
    y[24:] = 1
    sw = _compute_train_sample_weights(
        train_df,
        y,
        {
            "class_weighting": "balanced",
            "use_row_weights": True,
            "custom_mood_labels": ["reading"],
            "custom_mood_class_weight_fraction": 0.35,
        },
    )
    assert sw is not None
    reading_total = float(sw[:24].sum())
    work_total = float(sw[24:].sum())
    assert reading_total < work_total
    assert reading_total == pytest.approx(work_total * 0.35, rel=1e-4)


def test_equal_total_class_weights_personal_vs_base():
    from roomos.model.train import _compute_train_sample_weights

    train_df = pd.DataFrame(
        {
            "label": ["jump_rope"] * 10 + ["work"] * 50,
            "row_weight": [12.0] * 10 + [1.0] * 50,
        }
    )
    y = np.zeros(len(train_df), dtype=np.int32)
    y[10:] = 1
    sw = _compute_train_sample_weights(
        train_df,
        y,
        {"class_weighting": "balanced", "use_row_weights": True},
    )
    assert sw is not None
    assert float(sw[:10].sum()) == pytest.approx(float(sw[10:].sum()), rel=1e-5)


def test_bundle_roundtrip(tmp_path):
    df = _fake_dataset()
    cfg = _train_config(tmp_path)
    result = train_model(df, cfg)

    model = load_model_bundle(result.bundle_dir)
    assert model.classes == ["work", "sleep", "relaxing", "away"]
    assert model.feature_columns == result.feature_columns

    # Predict using only some of the features (others should default to 0).
    feat = {n: 0.0 for n in result.feature_columns}
    # Push "work" signal (feature index 0 = "feat_00").
    feat["feat_00"] = 5.0
    probs = predict_proba_row(model, feat)
    assert abs(sum(probs.values()) - 1.0) < 1e-4
    assert max(probs, key=probs.get) == "work"
