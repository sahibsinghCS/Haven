"""On-disk model bundle: XGBoost classifier + label encoder + feature schema.

A "bundle" is a directory with these files:

* ``model.json``           — XGBoost native serialization
* ``label_encoder.json``   — list of class labels in encoder order
* ``feature_columns.json`` — ordered feature column names
* ``train_config.json``    — config used at training time (for reproducibility)
* ``metrics.json``         — last evaluation metrics (optional)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

import numpy as np

from ..utils.io import ensure_dir, read_json, write_json
from ..utils.logging import get_logger

log = get_logger("roomos.model.registry")

MODEL_ARTIFACT_FILES = (
    "model.json",
    "label_encoder.json",
    "feature_columns.json",
    "train_config.json",
)


@dataclass
class ActivityModel:
    """Loaded model bundle ready for inference."""

    booster: Any                  # xgboost.XGBClassifier instance
    classes: List[str]            # label-index -> label string
    feature_columns: List[str]
    train_config: dict
    bundle_dir: Path

    @property
    def num_classes(self) -> int:
        return len(self.classes)

    def class_to_index(self, c: str) -> Optional[int]:
        try:
            return self.classes.index(c)
        except ValueError:
            return None


def save_model_bundle(
    bundle_dir: str | Path,
    *,
    clf: Any,
    classes: List[str],
    feature_columns: List[str],
    train_config: dict,
    metrics: Optional[dict] = None,
) -> Path:
    out = ensure_dir(bundle_dir)
    clf.save_model(str(out / "model.json"))
    write_json(out / "label_encoder.json", {"classes": list(classes)})
    write_json(out / "feature_columns.json", {"columns": list(feature_columns)})
    write_json(out / "train_config.json", train_config)
    if metrics is not None:
        write_json(out / "metrics.json", metrics)
    log.info("Saved model bundle -> %s", out)
    return out


def load_model_bundle(bundle_dir: str | Path) -> ActivityModel:
    bundle = Path(bundle_dir)
    for name in MODEL_ARTIFACT_FILES:
        if not (bundle / name).exists():
            raise FileNotFoundError(
                f"Bundle {bundle} is missing required artifact: {name}"
            )

    from xgboost import XGBClassifier  # lazy

    # XGBoost 2.x requires an estimator type before loading native JSON saved
    # via ``save_model`` (see xgboost sklearn ``_get_type``).
    clf = XGBClassifier()
    clf._estimator_type = "classifier"
    clf.load_model(str(bundle / "model.json"))

    label_data = read_json(bundle / "label_encoder.json")
    classes = list(label_data["classes"])
    cols = list(read_json(bundle / "feature_columns.json")["columns"])
    cfg = read_json(bundle / "train_config.json")
    return ActivityModel(
        booster=clf,
        classes=classes,
        feature_columns=cols,
        train_config=cfg,
        bundle_dir=bundle,
    )


def align_features(
    row_or_df,
    feature_columns: List[str],
    fill: float = 0.0,
) -> np.ndarray:
    """Reorder/fill a row or dataframe to match the trained feature schema.

    Returns a 2D float32 array suitable for ``predict_proba``.
    """
    import pandas as pd

    if isinstance(row_or_df, pd.Series):
        df = row_or_df.to_frame().T
    elif isinstance(row_or_df, pd.DataFrame):
        df = row_or_df
    elif isinstance(row_or_df, dict):
        df = pd.DataFrame([row_or_df])
    else:
        raise TypeError(f"Unsupported input type: {type(row_or_df)}")

    out = pd.DataFrame(index=df.index, columns=feature_columns, dtype=float)
    common = [c for c in feature_columns if c in df.columns]
    out.loc[:, common] = df[common].astype(float).values
    out.fillna(fill, inplace=True)
    return out.to_numpy(dtype=np.float32, copy=True)
