"""Per-label training weights."""

from __future__ import annotations

import numpy as np
import pandas as pd

from roomos.model.train import _apply_label_row_weights, _apply_row_weights


def test_label_row_weights_boost_work():
    train_df = pd.DataFrame(
        {
            "label": ["work", "work", "gaming", "gaming"],
            "row_weight": [1.0, 1.0, 1.0, 1.0],
        }
    )
    sw = np.ones(4, dtype=np.float32)
    out = _apply_label_row_weights(
        sw,
        train_df,
        {"label_row_weights": {"work": 2.0, "gaming": 1.0}},
    )
    assert out is not None
    assert out[0] > out[2]


def test_row_weight_ignored_when_label_row_weights_configured():
    """Avoid squaring work boost via row_weight column + label_row_weights."""
    train_df = pd.DataFrame(
        {
            "label": ["work", "gaming"],
            "row_weight": [1.7, 1.0],
        }
    )
    sw = np.array([1.0, 1.0], dtype=np.float32)
    cfg = {
        "use_row_weights": True,
        "label_row_weights": {"work": 2.0},
    }
    out = _apply_row_weights(sw, train_df, cfg)
    assert out is not None
    assert out[0] == 2.0
    assert out[1] == 1.0
