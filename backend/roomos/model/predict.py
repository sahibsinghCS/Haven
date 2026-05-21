"""Prediction helpers used by both the eval CLI and the live pipeline."""

from __future__ import annotations

from typing import Dict, Mapping

import numpy as np

from .registry import ActivityModel, align_features


def predict_proba_row(model: ActivityModel, row: Mapping[str, float] | dict) -> Dict[str, float]:
    """Predict class probabilities for a single feature row (dict-like)."""
    X = align_features(dict(row), model.feature_columns)
    proba = model.booster.predict_proba(X)[0]
    return {cls: float(p) for cls, p in zip(model.classes, proba)}


def predict_proba_batch(model: ActivityModel, df) -> np.ndarray:
    """Predict (n, n_classes) probability matrix for a dataframe."""
    X = align_features(df, model.feature_columns)
    return model.booster.predict_proba(X)
