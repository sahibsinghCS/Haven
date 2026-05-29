"""Plotting helpers used by the training/evaluation report."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np


def save_confusion_matrix(
    cm: np.ndarray,
    class_names: Sequence[str],
    out_path: str | Path,
    title: str = "Confusion matrix (normalized)",
    *,
    normalize: bool = True,
) -> Path:
    """Render and save a confusion matrix as PNG. Imports matplotlib lazily."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    cm = np.asarray(cm, dtype=float)
    if normalize:
        row_sums = cm.sum(axis=1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            plot = np.divide(cm, row_sums, where=row_sums > 0)
        plot = np.nan_to_num(plot)
        fmt = ".2f"
    else:
        plot = np.rint(cm)
        fmt = ".0f"

    fig, ax = plt.subplots(figsize=(1.2 + 0.9 * len(class_names), 1.0 + 0.8 * len(class_names)))
    sns.heatmap(
        plot,
        annot=True,
        fmt=fmt,
        xticklabels=list(class_names),
        yticklabels=list(class_names),
        cmap="viridis",
        cbar=True,
        ax=ax,
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def save_feature_importance(
    importances: np.ndarray,
    feature_names: Sequence[str],
    out_path: str | Path,
    top_k: int = 30,
    title: str = "Top feature importances",
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    importances = np.asarray(importances, dtype=float)
    feature_names = list(feature_names)
    order = np.argsort(importances)[::-1]
    order = order[:top_k]
    names = [feature_names[i] for i in order]
    vals = importances[order]

    fig, ax = plt.subplots(figsize=(8, max(3.0, 0.28 * len(order))))
    ax.barh(range(len(order))[::-1], vals[::-1])
    ax.set_yticks(range(len(order))[::-1])
    ax.set_yticklabels(names[::-1])
    ax.set_xlabel("Importance (gain)")
    ax.set_title(title)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def save_class_distribution(
    class_counts: dict[str, int] | dict[str, float],
    out_path: str | Path,
    title: str = "Training samples per class",
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = list(class_counts.keys())
    values = [float(class_counts[k]) for k in labels]
    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.1), 4))
    ax.bar(labels, values, color="#2dd4bf", edgecolor="#0f766e")
    ax.set_ylabel("Labeled bursts")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=25)
    for i, v in enumerate(values):
        ax.text(i, v, f"{int(v)}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
