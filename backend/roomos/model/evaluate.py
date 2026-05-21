"""Standalone evaluation pass against a saved bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..utils.io import write_json
from ..utils.logging import get_logger
from ..utils.visualization import save_confusion_matrix
from .registry import ActivityModel, align_features

log = get_logger("roomos.model.evaluate")


def evaluate_model(
    model: ActivityModel,
    df: pd.DataFrame,
    *,
    output_dir: Optional[Path] = None,
) -> Dict[str, object]:
    if "label" not in df.columns:
        raise ValueError("Dataframe is missing 'label' column.")

    df = df[df["label"].notna()].copy()
    if df.empty:
        raise ValueError("No labeled rows for evaluation.")

    # Encode labels into the trained class space; warn (and drop) on unseen.
    valid = df["label"].astype(str).isin(model.classes)
    if (~valid).any():
        unseen = sorted(df.loc[~valid, "label"].astype(str).unique().tolist())
        log.warning("Dropping %d rows with unseen labels: %s", int((~valid).sum()), unseen)
        df = df[valid].copy()

    y = np.array([model.classes.index(str(v)) for v in df["label"]], dtype=np.int32)
    X = align_features(df, model.feature_columns)
    pred = model.booster.predict(X)

    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
    )

    metrics = {
        "accuracy": float(accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y, pred, average="weighted", zero_division=0)),
        "per_class": classification_report(
            y,
            pred,
            labels=list(range(len(model.classes))),
            target_names=model.classes,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(
            y, pred, labels=list(range(len(model.classes)))
        ).tolist(),
        "n_samples": int(len(y)),
        "bundle_dir": str(model.bundle_dir),
    }

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        write_json(out / "eval_metrics.json", metrics)
        cm = np.array(metrics["confusion_matrix"], dtype=int)
        save_confusion_matrix(cm, model.classes, out / "eval_confusion_matrix.png",
                              title="Evaluation confusion matrix (normalized)")
        log.info("Evaluation artifacts -> %s", out)

    return metrics
