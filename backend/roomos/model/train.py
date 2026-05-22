"""XGBoost training pipeline."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import Config
from ..dataset.schemas import FEATURE_META_COLUMNS
from ..utils.io import write_json
from ..utils.logging import get_logger
from ..utils.visualization import save_confusion_matrix, save_feature_importance
from .eval_report import write_eval_report
from .registry import save_model_bundle

log = get_logger("roomos.model.train")


@dataclass
class TrainResult:
    bundle_dir: Path
    metrics: Dict[str, Any]
    classes: List[str]
    feature_columns: List[str]


# --- helpers ---------------------------------------------------------------


def _select_feature_columns(df: pd.DataFrame) -> List[str]:
    drop = set(FEATURE_META_COLUMNS) | {"label", "notes"}
    cols = [c for c in df.columns if c not in drop]
    if not cols:
        raise ValueError("Dataframe has no feature columns after dropping metadata/label.")
    return cols


def _split_by_source(
    df: pd.DataFrame, val_size: float, test_size: float, seed: int
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Group-aware split — keeps all burst rows from one video on one side.

    Falls back to a simple random split when there is only one source.
    """
    rng = np.random.default_rng(seed)
    sources = df["source"].dropna().unique().tolist()
    if len(sources) <= 1:
        log.warning(
            "Only %d unique source(s); falling back to random row split.",
            len(sources),
        )
        return _split_random(df, val_size, test_size, seed)

    rng.shuffle(sources)
    n = len(sources)
    n_test = max(1, int(round(n * test_size)))
    n_val = max(1, int(round(n * val_size)))
    n_train = max(1, n - n_test - n_val)
    if n_train < 1:
        n_train = 1
        n_val = max(1, n - n_train - n_test)

    train_src = set(sources[:n_train])
    val_src = set(sources[n_train:n_train + n_val])
    test_src = set(sources[n_train + n_val:])

    return (
        df[df["source"].isin(train_src)].copy(),
        df[df["source"].isin(val_src)].copy(),
        df[df["source"].isin(test_src)].copy(),
    )


def _split_random(
    df: pd.DataFrame, val_size: float, test_size: float, seed: int
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from sklearn.model_selection import train_test_split

    rest, test = train_test_split(
        df,
        test_size=test_size,
        random_state=seed,
        stratify=df["label"] if df["label"].nunique() > 1 else None,
    )
    val_fraction = val_size / max(1e-6, (1.0 - test_size))
    train, val = train_test_split(
        rest,
        test_size=val_fraction,
        random_state=seed,
        stratify=rest["label"] if rest["label"].nunique() > 1 else None,
    )
    return train.copy(), val.copy(), test.copy()


def _compute_sample_weights(y: np.ndarray, mode: str) -> Optional[np.ndarray]:
    if mode == "none" or not mode:
        return None
    if mode != "balanced":
        log.warning("Unknown class_weighting=%r; using 'balanced'", mode)
    counts = Counter(int(v) for v in y)
    n_classes = len(counts)
    total = len(y)
    weights = {c: total / (n_classes * cnt) for c, cnt in counts.items()}
    return np.array([weights[int(v)] for v in y], dtype=np.float32)


# --- main entry ------------------------------------------------------------


def train_model(
    df: pd.DataFrame,
    config: Config,
    *,
    output_dir: Optional[Path] = None,
) -> TrainResult:
    """Train an XGBoost multiclass classifier on a fused-features dataframe."""
    if "label" not in df.columns:
        raise ValueError("Input dataframe is missing the required 'label' column.")
    train_cfg = config.training

    df = df.copy()
    n_before = len(df)
    df = df[df["label"].notna() & (df["label"].astype(str).str.len() > 0)]
    log.info("Dropped %d unlabeled rows (kept %d).", n_before - len(df), len(df))
    if df.empty:
        raise ValueError("No labeled rows available for training.")

    # Validate label space matches the configured taxonomy when possible.
    allowed = set(config.labels.classes) | {config.labels.get("unknown_class", "unknown")}
    bad = set(df["label"].unique()) - allowed
    if bad:
        log.warning(
            "Labels present in dataset but not in config.labels.classes: %s. "
            "They will be kept; consider updating configs/default.yaml.",
            sorted(bad),
        )

    feature_cols = _select_feature_columns(df)
    log.info("Using %d feature columns.", len(feature_cols))

    # Encode labels — class index order must match config.labels.classes (and live UI).
    present = sorted(set(df["label"].astype(str)))
    config_order = [c for c in config.labels.classes if c in present]
    extra = sorted(set(present) - set(config_order))
    classes = config_order + extra
    if not classes:
        raise ValueError("No label classes after encoding.")
    label_to_idx = {c: i for i, c in enumerate(classes)}
    df["_y"] = df["label"].astype(str).map(label_to_idx).astype(np.int32)
    log.info("Class counts:\n%s", df["label"].value_counts().to_string())

    # Split.
    seed = int(train_cfg.get("random_state", 42))
    val_size = float(train_cfg.split.get("val_size", 0.15))
    test_size = float(train_cfg.split.get("test_size", 0.15))
    strategy = str(train_cfg.split.get("strategy", "by_source"))
    if strategy == "by_source" and "source" in df.columns:
        train_df, val_df, test_df = _split_by_source(df, val_size, test_size, seed)
    else:
        train_df, val_df, test_df = _split_random(df, val_size, test_size, seed)

    log.info(
        "Split sizes — train=%d val=%d test=%d", len(train_df), len(val_df), len(test_df)
    )
    if len(train_df) == 0:
        raise ValueError("Training split is empty; check your dataset / split sizes.")

    X_train = train_df[feature_cols].astype(float).fillna(0.0).to_numpy(dtype=np.float32)
    y_train = train_df["_y"].to_numpy(dtype=np.int32)
    X_val = val_df[feature_cols].astype(float).fillna(0.0).to_numpy(dtype=np.float32) if len(val_df) else None
    y_val = val_df["_y"].to_numpy(dtype=np.int32) if len(val_df) else None
    X_test = test_df[feature_cols].astype(float).fillna(0.0).to_numpy(dtype=np.float32) if len(test_df) else None
    y_test = test_df["_y"].to_numpy(dtype=np.int32) if len(test_df) else None

    sw = _compute_sample_weights(y_train, str(train_cfg.get("class_weighting", "balanced")))

    # XGBoost.
    from xgboost import XGBClassifier

    hp = dict(train_cfg.xgboost)
    early = hp.pop("early_stopping_rounds", None)
    n_jobs = hp.pop("n_jobs", 0)
    if n_jobs in (0, None):
        n_jobs = -1

    # Multi-class objective is required when we have >2 classes.
    if len(classes) <= 2:
        hp["objective"] = "binary:logistic"
        hp["eval_metric"] = hp.get("eval_metric", "logloss")

    clf = XGBClassifier(
        **hp,
        n_jobs=n_jobs,
        random_state=seed,
        early_stopping_rounds=early,
    )

    fit_kwargs: dict = {}
    if X_val is not None and y_val is not None and len(y_val) > 0:
        fit_kwargs["eval_set"] = [(X_val, y_val)]
        fit_kwargs["verbose"] = False
    if sw is not None:
        fit_kwargs["sample_weight"] = sw

    log.info("Fitting XGBoost (%d trees, depth=%s)...", hp.get("n_estimators"), hp.get("max_depth"))
    clf.fit(X_train, y_train, **fit_kwargs)

    # Evaluate.
    metrics = _evaluate_splits(
        clf,
        classes=classes,
        train=(X_train, y_train),
        val=(X_val, y_val) if X_val is not None else None,
        test=(X_test, y_test) if X_test is not None else None,
    )

    # Persist.
    if output_dir is None:
        output_dir = Path(train_cfg.get("output_dir", "data/models/latest"))
    output_dir = Path(output_dir)
    train_cfg_dict = config.to_dict()
    if config.source_path is not None:
        train_cfg_dict["_source_config"] = str(config.source_path)
    save_model_bundle(
        output_dir,
        clf=clf,
        classes=classes,
        feature_columns=feature_cols,
        train_config=train_cfg_dict,
        metrics=metrics,
    )

    # Visualizations + summary report (optional plotting deps).
    cm = np.array(metrics["test"]["confusion_matrix"] if "test" in metrics else metrics["val"]["confusion_matrix"], dtype=int)
    try:
        save_confusion_matrix(cm, classes, output_dir / "confusion_matrix.png")
    except Exception as e:
        log.warning("Could not save confusion matrix plot: %s", e)
    try:
        importances = clf.feature_importances_
        save_feature_importance(importances, feature_cols, output_dir / "feature_importance.png")
    except Exception as e:
        log.warning("Could not save feature importances: %s", e)

    write_json(output_dir / "metrics.json", metrics)
    training_summary = {
        "n_rows_total": int(len(df)),
        "n_train": int(len(train_df)),
        "n_val": int(len(val_df)),
        "n_test": int(len(test_df)),
        "class_counts": df["label"].value_counts().to_dict(),
        "classes": classes,
        "n_features": len(feature_cols),
    }
    write_json(output_dir / "training_summary.json", training_summary)

    split_name = "test" if "test" in metrics else ("val" if "val" in metrics else "train")
    try:
        write_eval_report(
            output_dir,
            metrics[split_name],
            split_name=split_name,
            classes=classes,
            training_summary=training_summary,
            booster=clf,
            feature_columns=feature_cols,
            full_metrics=metrics,
        )
    except Exception as e:
        log.warning("Could not write eval_report: %s", e)

    return TrainResult(
        bundle_dir=output_dir,
        metrics=metrics,
        classes=classes,
        feature_columns=feature_cols,
    )


# --- eval ------------------------------------------------------------------


def _evaluate_splits(
    clf,
    *,
    classes: List[str],
    train: Tuple[np.ndarray, np.ndarray],
    val: Optional[Tuple[np.ndarray, np.ndarray]],
    test: Optional[Tuple[np.ndarray, np.ndarray]],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["train"] = _metrics_for(clf, *train, classes=classes)
    if val is not None and val[0] is not None and len(val[1]):
        out["val"] = _metrics_for(clf, *val, classes=classes)
    if test is not None and test[0] is not None and len(test[1]):
        out["test"] = _metrics_for(clf, *test, classes=classes)
    return out


def _metrics_for(clf, X: np.ndarray, y: np.ndarray, classes: List[str]) -> Dict[str, Any]:
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
    )

    pred = clf.predict(X)
    out = {
        "accuracy": float(accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y, pred, average="weighted", zero_division=0)),
        "per_class": classification_report(
            y,
            pred,
            labels=list(range(len(classes))),
            target_names=classes,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(y, pred, labels=list(range(len(classes)))).tolist(),
        "n_samples": int(len(y)),
    }
    return out
