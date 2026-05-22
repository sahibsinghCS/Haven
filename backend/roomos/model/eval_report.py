"""Hackathon-friendly evaluation report under ``<bundle>/eval_report/``."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from ..utils.io import read_json, write_json
from ..utils.logging import get_logger
from ..utils.visualization import (
    save_class_distribution,
    save_confusion_matrix,
    save_feature_importance,
)

log = get_logger("roomos.model.eval_report")

REPORT_DIR_NAME = "eval_report"
LIMITATIONS = """
## Limitations (say this honestly to judges)

- **Offline bursts, not live video accuracy** — metrics are on held-out *training bursts*
  (5-frame feature rows), not a fresh continuous webcam session.
- **Small personal datasets** — with ~6–12 bursts per class, scores are directional, not
  benchmark-grade; confusion among similar poses (work vs relaxing) is expected.
- **Tabular XGBoost on CLIP+motion** — not end-to-end deep learning; performance depends on
  how well stills/videos match your real room at demo time.
- **No pose/posture in default personal config** — fine-grained sleep vs couch-relax may
  rely on scene + motion cues only.
- **Feedback memory is separate** — corrections on `/live` nudge similar bursts but do not
  change these offline metrics until you retrain.
""".strip()


def pick_eval_split(metrics: Mapping[str, Any]) -> Tuple[str, Dict[str, Any]]:
    for name in ("test", "val", "train"):
        if name in metrics and isinstance(metrics[name], dict):
            return name, dict(metrics[name])
    raise ValueError("No train/val/test split found in metrics.")


def per_class_table(per_class: Mapping[str, Any], classes: Sequence[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for label in classes:
        block = per_class.get(label)
        if not isinstance(block, dict):
            continue
        rows.append(
            {
                "class": label,
                "precision": round(float(block.get("precision", 0.0)), 3),
                "recall": round(float(block.get("recall", 0.0)), 3),
                "f1": round(float(block.get("f1-score", 0.0)), 3),
                "support": int(block.get("support", 0)),
            }
        )
    return rows


def top_confusion_pairs(
    cm: np.ndarray,
    classes: Sequence[str],
    *,
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    pairs: List[Tuple[int, float, str, str]] = []
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            if i == j:
                continue
            c = int(cm[i, j])
            if c > 0:
                pairs.append((c, c / max(1, cm[i].sum()), str(classes[i]), str(classes[j])))
    pairs.sort(reverse=True)
    out: List[Dict[str, Any]] = []
    for count, rate, true_l, pred_l in pairs[:top_n]:
        out.append(
            {
                "true": true_l,
                "predicted": pred_l,
                "count": count,
                "rate_of_true": round(rate, 3),
            }
        )
    return out


def judge_strengths_weaknesses(
    per_rows: List[Dict[str, Any]],
    confusion_pairs: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    strong: List[str] = []
    weak: List[str] = []
    for row in per_rows:
        label = row["class"]
        f1 = row["f1"]
        rec = row["recall"]
        prec = row["precision"]
        sup = row["support"]
        if sup < 2:
            weak.append(f"{label}: very few training bursts ({sup}) — metrics unstable")
        elif f1 >= 0.65 and rec >= 0.6:
            strong.append(f"{label}: F1={f1:.2f}, recall={rec:.2f} (n={sup})")
        elif rec < 0.45:
            weak.append(f"{label}: low recall {rec:.2f} — often missed when truly in this state")
        elif prec < 0.45:
            weak.append(f"{label}: low precision {prec:.2f} — other states confused as {label}")
        elif f1 < 0.5:
            weak.append(f"{label}: F1={f1:.2f} — expect live demo mistakes")

    for pair in confusion_pairs[:3]:
        weak.append(
            f"Often predicts {pair['predicted']} when truth is {pair['true']} "
            f"({pair['count']} bursts, {pair['rate_of_true']:.0%} of true {pair['true']})"
        )
    return {"strong": strong[:6], "weak": weak[:8]}


def feature_group_summary(
    importances: np.ndarray,
    feature_names: Sequence[str],
) -> Dict[str, float]:
    groups = {"clip": 0.0, "pose": 0.0, "motion": 0.0, "posture": 0.0, "other": 0.0}
    for name, val in zip(feature_names, importances):
        v = float(val)
        if name.startswith("clip_sim__"):
            groups["clip"] += v
        elif name.startswith("motion_"):
            groups["motion"] += v
        elif name.startswith("pose_"):
            groups["pose"] += v
        elif name.startswith("posture_"):
            groups["posture"] += v
        else:
            groups["other"] += v
    total = sum(groups.values()) or 1.0
    return {k: round(v / total, 3) for k, v in groups.items()}


def write_eval_report(
    bundle_dir: str | Path,
    split_metrics: Dict[str, Any],
    *,
    split_name: str,
    classes: Sequence[str],
    training_summary: Optional[Dict[str, Any]] = None,
    booster=None,
    feature_columns: Optional[Sequence[str]] = None,
    full_metrics: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write ``eval_report/`` artifacts for judges and Q&A."""
    bundle = Path(bundle_dir)
    out = bundle / REPORT_DIR_NAME
    out.mkdir(parents=True, exist_ok=True)

    cm = np.array(split_metrics["confusion_matrix"], dtype=int)
    per_class = split_metrics.get("per_class", {})
    rows = per_class_table(per_class, classes)
    conf_pairs = top_confusion_pairs(cm, classes)
    sw = judge_strengths_weaknesses(rows, conf_pairs)

    class_counts = {}
    n_total = int(split_metrics.get("n_samples", 0))
    if training_summary:
        class_counts = dict(training_summary.get("class_counts", {}))
        n_total = int(training_summary.get("n_rows_total", n_total))

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bundle_dir": str(bundle.resolve()),
        "eval_split": split_name,
        "n_eval_samples": int(split_metrics.get("n_samples", 0)),
        "accuracy": round(float(split_metrics.get("accuracy", 0.0)), 4),
        "macro_f1": round(float(split_metrics.get("macro_f1", 0.0)), 4),
        "weighted_f1": round(float(split_metrics.get("weighted_f1", 0.0)), 4),
        "per_class": rows,
        "top_confusions": conf_pairs,
        "strengths": sw["strong"],
        "weaknesses": sw["weak"],
        "training_class_counts": class_counts,
        "training_rows_total": n_total,
    }

    write_json(out / "metrics_summary.json", summary)
    if full_metrics is not None:
        write_json(out / "metrics_all_splits.json", full_metrics)

    try:
        save_confusion_matrix(
            cm,
            classes,
            out / "confusion_matrix_normalized.png",
            title=f"Confusion matrix — {split_name} (row-normalized)",
            normalize=True,
        )
        save_confusion_matrix(
            cm,
            classes,
            out / "confusion_matrix_counts.png",
            title=f"Confusion matrix — {split_name} (counts)",
            normalize=False,
        )
    except Exception as e:
        log.warning("Could not save confusion matrix plots: %s", e)

    if class_counts:
        try:
            save_class_distribution(
                class_counts,
                out / "class_distribution.png",
                title="Training bursts per class",
            )
        except Exception as e:
            log.warning("Could not save class distribution plot: %s", e)
        write_json(out / "class_distribution.json", class_counts)

    feat_groups: Dict[str, float] = {}
    if booster is not None and feature_columns:
        try:
            imp = np.asarray(booster.feature_importances_, dtype=float)
            save_feature_importance(
                imp,
                feature_columns,
                out / "feature_importance_top30.png",
                top_k=30,
                title="Top XGBoost features (gain)",
            )
            feat_groups = feature_group_summary(imp, feature_columns)
            write_json(out / "feature_importance_groups.json", feat_groups)
        except Exception as e:
            log.warning("Could not save feature importance: %s", e)

    _write_report_md(out / "REPORT.md", summary, feat_groups)
    write_json(out / "limitations.json", {"markdown": LIMITATIONS})
    (out / "LIMITATIONS.md").write_text(LIMITATIONS + "\n", encoding="utf-8")

    log.info("Evaluation report -> %s", out)
    return out


def generate_report_from_bundle(
    bundle_dir: str | Path,
    *,
    features_path: Optional[Path] = None,
    recompute: bool = False,
) -> Path:
    """Build or refresh eval_report from bundle artifacts (+ optional features parquet)."""
    bundle = Path(bundle_dir)
    metrics_path = bundle / "metrics.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"No metrics.json in {bundle}")

    full_metrics = read_json(metrics_path)
    split_name, split_metrics = pick_eval_split(full_metrics)

    training_summary = None
    ts_path = bundle / "training_summary.json"
    if ts_path.exists():
        training_summary = read_json(ts_path)

    booster = None
    feature_columns: Optional[List[str]] = None

    if recompute and features_path is not None:
        from ..dataset.builder import load_features
        from .evaluate import evaluate_model
        from .registry import load_model_bundle

        model = load_model_bundle(bundle)
        df = load_features(features_path)
        split_metrics = evaluate_model(model, df)
        split_name = "holdout_features"
        booster = model.booster
        feature_columns = model.feature_columns
    else:
        from .registry import load_model_bundle

        try:
            model = load_model_bundle(bundle)
            booster = model.booster
            feature_columns = model.feature_columns
        except Exception as e:
            log.warning("Could not load model for feature importance: %s", e)

    return write_eval_report(
        bundle,
        split_metrics,
        split_name=split_name,
        classes=list(
            training_summary.get("classes", [])
            if training_summary
            else read_json(bundle / "label_encoder.json")["classes"]
        ),
        training_summary=training_summary,
        booster=booster,
        feature_columns=feature_columns,
        full_metrics=full_metrics,
    )


def _write_report_md(path: Path, summary: Dict[str, Any], feat_groups: Dict[str, float]) -> None:
    lines = [
        "# RoomOS model evaluation (hackathon report)",
        "",
        f"Generated: {summary.get('generated_at', '')}",
        f"Bundle: `{summary.get('bundle_dir', '')}`",
        f"Eval split: **{summary.get('eval_split', '')}** ({summary.get('n_eval_samples', 0)} labeled bursts)",
        "",
        "## Headline metrics",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| Accuracy | {summary.get('accuracy', 0):.1%} |",
        f"| Macro F1 | {summary.get('macro_f1', 0):.1%} |",
        f"| Weighted F1 | {summary.get('weighted_f1', 0):.1%} |",
        "",
        "## Per-class (precision / recall / F1)",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|-------|----------:|-------:|---:|--------:|",
    ]
    for row in summary.get("per_class", []):
        lines.append(
            f"| {row['class']} | {row['precision']:.2f} | {row['recall']:.2f} "
            f"| {row['f1']:.2f} | {row['support']} |"
        )
    lines.extend(["", "## Training data distribution", ""])
    counts = summary.get("training_class_counts", {})
    if counts:
        for label, n in counts.items():
            lines.append(f"- **{label}**: {n} bursts")
        lines.append(f"- **Total rows**: {summary.get('training_rows_total', '?')}")
    else:
        lines.append("- (Run training again to write `training_summary.json`)")

    lines.extend(["", "## Strong vs weak (for live demo)", "", "### Likely strong", ""])
    for s in summary.get("strengths", []) or ["(none flagged)"]:
        lines.append(f"- {s}")
    lines.extend(["", "### Watch out live", ""])
    for w in summary.get("weaknesses", []) or ["(none flagged)"]:
        lines.append(f"- {w}")

    if summary.get("top_confusions"):
        lines.extend(["", "## Top confusions (true → predicted)", ""])
        for p in summary["top_confusions"]:
            lines.append(
                f"- {p['true']} → {p['predicted']}: {p['count']} bursts ({p['rate_of_true']:.0%} of true {p['true']})"
            )

    if feat_groups:
        lines.extend(
            [
                "",
                "## Feature signal (XGBoost gain share)",
                "",
                f"- CLIP scene: {feat_groups.get('clip', 0):.0%}",
                f"- Motion: {feat_groups.get('motion', 0):.0%}",
                f"- Pose: {feat_groups.get('pose', 0):.0%}",
                f"- Posture: {feat_groups.get('posture', 0):.0%}",
            ]
        )

    lines.extend(["", "## Files in this folder", ""])
    lines.extend(
        [
            "- `confusion_matrix_normalized.png` — read for judge slide",
            "- `confusion_matrix_counts.png` — raw burst counts",
            "- `class_distribution.png` — training balance",
            "- `feature_importance_top30.png` — what the model uses",
            "- `metrics_summary.json` — machine-readable",
            "- `LIMITATIONS.md` — honest caveats",
        ]
    )
    lines.extend(["", LIMITATIONS])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
