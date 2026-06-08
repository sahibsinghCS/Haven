"""Second-pass dataset cleaning via out-of-fold (OOF) cross-validation.

The first pass (``scripts/clean_dataset.py``) scored each image with the model
that was *trained on those same labels*, so it agreed with label noise it had
memorized. This script removes that blind spot using the standard
confident-learning trick:

1. Extract the CLIP+motion still-burst feature row for every image (cached to
   parquet so reruns are instant).
2. Run K-fold cross-validation grouped by source image. For each fold we train
   a fresh XGBoost (same hyperparameters as ``train_multi_room.yaml``) on the
   other folds and predict the held-out fold. Every image therefore gets a
   probability vector from a model that **never saw it**.
3. Flag an image when its out-of-fold top class disagrees with the folder it
   lives in (balanced rule: winning class beats the folder label by >= margin).

Flagged images are quarantined to ``<images-dir>/_rejected/<label>/`` (same
place the first pass used) and recorded in ``clean_report_cv.csv``. Use
``--mode delete`` to hard-delete or ``--dry-run`` to preview.

Run from ``backend/``::

    python scripts/clean_dataset_cv.py --dry-run
    python scripts/clean_dataset_cv.py
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import csv
import json
import shutil
import time
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
import pandas as pd
import typer

from roomos.config import load_config
from roomos.dataset.builder import FeatureExtractionPipeline
from roomos.features import FrameBurst, FrameRecord
from roomos.model.registry import align_features, load_model_bundle
from roomos.utils.logging import get_logger, setup_logging

DEFAULT_CONFIG = Path("configs/inference.yaml")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

log = get_logger("roomos.scripts.clean_dataset_cv")

app = typer.Typer(
    add_completion=False,
    help="Out-of-fold (cross-validated) second pass to catch remaining mislabeled images.",
)


def _discover_images(label_dir: Path) -> List[Path]:
    return sorted(
        p
        for p in label_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def _source_id(label: str, image: Path) -> str:
    """label/<stem> with any ``_aug<tag>`` suffix stripped (group augmentations)."""
    import re

    stem = re.sub(r"_aug[a-z]+$", "", image.stem, flags=re.IGNORECASE)
    return f"{label}/{stem}"


def _still_row(pipe: FeatureExtractionPipeline, image, label: str, frame_count: int) -> dict:
    pipe.reset_motion()
    base = pipe.frame_to_record(image_bgr=image, frame_index=0, timestamp=0.0, source=label)
    pipe.reset_motion()
    records: List[FrameRecord] = [base]
    for i in range(1, frame_count):
        records.append(
            FrameRecord(
                timestamp=float(i),
                frame_index=i,
                source=label,
                clip_embedding=base.clip_embedding,
                clip_prompt_sim=base.clip_prompt_sim,
                pose_landmarks=base.pose_landmarks,
                pose_visibility=base.pose_visibility,
                pose_present=base.pose_present,
                pose_mean_visibility=base.pose_mean_visibility,
                pose_bbox=base.pose_bbox,
                motion_mean=0.0,
                motion_std=0.0,
                motion_max=0.0,
                motion_grid=base.motion_grid,
                posture=dict(base.posture or {}),
            )
        )
    burst = FrameBurst(
        start_time=0.0, end_time=float(frame_count - 1), source=label, frames=records, burst_index=0
    )
    return pipe.fusion.fuse(burst).as_dict()


def _quarantine_path(reject_dir: Path, label: str, src: Path) -> Path:
    dest_dir = reject_dir / label
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        stem, suffix = src.stem, src.suffix
        i = 1
        while dest.exists():
            dest = dest_dir / f"{stem}__dup{i}{suffix}"
            i += 1
    return dest


def _build_feature_frame(
    cfg, images_root: Path, classes: List[str], limit: int
) -> pd.DataFrame:
    frame_count = int(cfg.burst.frame_count)
    rows: List[dict] = []
    started = time.time()
    seen = 0
    pipe = FeatureExtractionPipeline(cfg)
    with pipe:
        for label in classes:
            images = _discover_images(images_root / label)
            if limit > 0:
                images = images[:limit]
            for img_path in images:
                image = cv2.imread(str(img_path))
                if image is None:
                    log.warning("Unreadable image, skipping: %s", img_path)
                    continue
                feats = _still_row(pipe, image, label, frame_count)
                feats["__file"] = str(img_path)
                feats["__label"] = label
                feats["__source"] = _source_id(label, img_path)
                rows.append(feats)
                seen += 1
                if seen % 200 == 0:
                    rate = seen / max(1e-6, time.time() - started)
                    log.info("  extracted %d features (%s) | %.1f img/s", seen, label, rate)
    log.info("Extracted %d feature rows in %.1fs", len(rows), time.time() - started)
    return pd.DataFrame(rows)


def _oof_probabilities(
    df: pd.DataFrame, feature_columns: List[str], classes: List[str], xgb_hp: dict, n_splits: int, seed: int
) -> np.ndarray:
    from sklearn.utils.class_weight import compute_sample_weight
    from xgboost import XGBClassifier

    try:
        from sklearn.model_selection import StratifiedGroupKFold

        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    except Exception:  # pragma: no cover - older sklearn
        from sklearn.model_selection import GroupKFold

        splitter = GroupKFold(n_splits=n_splits)
        log.warning("StratifiedGroupKFold unavailable; falling back to GroupKFold.")

    X = align_features(df, feature_columns)
    y = np.array([classes.index(str(v)) for v in df["__label"]], dtype=np.int32)
    groups = df["__source"].to_numpy()

    hp = dict(xgb_hp)
    hp.pop("early_stopping_rounds", None)  # no eval_set per fold
    n_jobs = hp.pop("n_jobs", 0) or -1

    oof = np.zeros((len(df), len(classes)), dtype=np.float32)
    for fold, (tr_idx, te_idx) in enumerate(splitter.split(X, y, groups), start=1):
        sw = compute_sample_weight("balanced", y[tr_idx])
        clf = XGBClassifier(**hp, n_jobs=n_jobs, random_state=seed)
        clf.fit(X[tr_idx], y[tr_idx], sample_weight=sw)
        oof[te_idx] = clf.predict_proba(X[te_idx]).astype(np.float32)
        log.info("  fold %d/%d: train=%d test=%d", fold, n_splits, len(tr_idx), len(te_idx))
    return oof


@app.command()
def main(
    images_dir: Path = typer.Option(Path("data/base_images"), "--images-dir"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    model_dir: Path = typer.Option(Path("data/models/latest"), "--model-dir"),
    features_cache: Path = typer.Option(
        Path("data/features/base_images_oof_features.pkl"), "--features-cache"
    ),
    from_features: bool = typer.Option(
        False, "--from-features", help="Reuse cached features (skip CLIP extraction)."
    ),
    mode: str = typer.Option("quarantine", "--mode", help="quarantine | delete"),
    balanced_margin: float = typer.Option(
        0.15, "--balanced-margin",
        help="Flag when the winning class beats the folder label by >= this OOF prob gap.",
    ),
    n_splits: int = typer.Option(5, "--n-splits"),
    reject_dirname: str = typer.Option("_rejected", "--reject-dirname"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    limit: int = typer.Option(0, "--limit", help="Max images per class (0 = all)."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)
    if mode not in {"quarantine", "delete"}:
        raise typer.BadParameter("mode must be 'quarantine' or 'delete'")

    cfg = load_config(config)
    images_root = images_dir if images_dir.is_absolute() else cfg.resolve_path(images_dir)
    if not images_root.is_dir():
        raise typer.BadParameter(f"images-dir not found: {images_root}")

    bundle_dir = model_dir if model_dir.is_absolute() else cfg.resolve_path(model_dir)
    model = load_model_bundle(bundle_dir)
    classes = list(model.classes)
    xgb_hp = dict(model.train_config.get("training", {}).get("xgboost", {}))
    seed = int(model.train_config.get("training", {}).get("random_state", 42))

    cache_path = features_cache if features_cache.is_absolute() else cfg.resolve_path(features_cache)

    started = time.time()
    if from_features and cache_path.is_file():
        log.info("Loading cached features: %s", cache_path)
        df = pd.read_pickle(cache_path)
        # Drop rows whose image no longer exists (already quarantined).
        exists = df["__file"].map(lambda p: Path(p).is_file())
        if not exists.all():
            log.info("Dropping %d cached rows whose image is gone.", int((~exists).sum()))
            df = df[exists].reset_index(drop=True)
    else:
        present = [c for c in classes if (images_root / c).is_dir()]
        df = _build_feature_frame(cfg, images_root, present, limit)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            df.to_pickle(cache_path)
            log.info("Cached features -> %s", cache_path)
        except Exception as e:  # pragma: no cover
            log.warning("Could not write feature cache (%s); continuing in-memory.", e)

    if df.empty:
        raise typer.Exit("No images to score.")

    log.info("Running %d-fold OOF on %d images...", n_splits, len(df))
    oof = _oof_probabilities(df, model.feature_columns, classes, xgb_hp, n_splits, seed)

    reject_dir = images_root / reject_dirname
    report_rows: List[dict] = []
    summary: Dict[str, dict] = {c: {"seen": 0, "flagged": 0} for c in classes}
    total_flagged = 0

    for i, (_, rec) in enumerate(df.iterrows()):
        label = str(rec["__label"])
        file_path = Path(str(rec["__file"]))
        probs = {c: float(oof[i, j]) for j, c in enumerate(classes)}
        ordered = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
        predicted, top_p = ordered[0]
        label_p = probs.get(label, 0.0)
        gap = top_p - label_p
        flag = predicted != label and gap >= balanced_margin

        summary[label]["seen"] += 1
        row = {
            "label": label,
            "file": str(file_path),
            "predicted": predicted,
            "label_prob": round(label_p, 4),
            "predicted_prob": round(top_p, 4),
            "flagged": flag,
            "reason": (f"OOF says '{predicted}' p={top_p:.2f} (+{gap:.2f} over '{label}')" if flag else "kept"),
            "action": "kept",
        }
        if flag:
            total_flagged += 1
            summary[label]["flagged"] += 1
            if dry_run:
                row["action"] = "would-flag"
            elif not file_path.is_file():
                row["action"] = "missing"
            elif mode == "delete":
                file_path.unlink(missing_ok=True)
                row["action"] = "deleted"
            else:
                dest = _quarantine_path(reject_dir, label, file_path)
                shutil.move(str(file_path), str(dest))
                row["action"] = "quarantined"
                row["moved_to"] = str(dest)
        report_rows.append(row)

    reject_dir.mkdir(parents=True, exist_ok=True)
    report_csv = reject_dir / "clean_report_cv.csv"
    fieldnames = [
        "label", "file", "predicted", "label_prob", "predicted_prob",
        "flagged", "reason", "action", "moved_to",
    ]
    with report_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in report_rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    summary_json = reject_dir / "clean_summary_cv.json"
    summary_json.write_text(
        json.dumps(
            {
                "method": "out-of-fold cross-validation",
                "images_dir": str(images_root),
                "model_dir": str(bundle_dir),
                "mode": mode,
                "dry_run": dry_run,
                "balanced_margin": balanced_margin,
                "n_splits": n_splits,
                "total_seen": int(len(df)),
                "total_flagged": total_flagged,
                "per_class": summary,
                "report_csv": str(report_csv),
                "elapsed_sec": round(time.time() - started, 1),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log.info("=" * 60)
    log.info("DONE in %.1fs | seen=%d flagged=%d", time.time() - started, len(df), total_flagged)
    for c in classes:
        s = summary[c]
        log.info("  %-9s seen=%-5s flagged=%-5s", c, s["seen"], s["flagged"])
    log.info("Report: %s", report_csv)


if __name__ == "__main__":
    app()
