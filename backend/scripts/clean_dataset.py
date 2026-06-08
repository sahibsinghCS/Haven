"""Flag and quarantine mislabeled images in ``data/base_images/<label>/``.

The labeled still-image dataset is noisy: e.g. some photos in ``sleep/`` show a
person who is clearly awake, and some ``away/`` photos contain a person. This
script scores every image with the **already-trained XGBoost model** in
``data/models/latest`` using the exact same feature pipeline the model was
trained on (CLIP + motion still-burst, see ``scripts/train_multi_room.py``):

* Each image becomes a zero-motion 5-frame still burst -> one fused feature row.
* ``model.predict_proba`` gives calibrated probabilities over the five classes.
* If the model's top class disagrees with the folder the image lives in, the
  image is flagged (subject to the chosen ``--strictness``).

We use the trained model rather than raw CLIP prompt argmax on purpose: raw
CLIP cosine similarities are not comparable across prompts (e.g. "an empty room
with no people" scores high on almost any indoor scene), so prompt argmax
mislabels nearly everything. The model works in a calibrated space.

By default flagged images are **quarantined** (moved to
``<images-dir>/_rejected/<label>/``) rather than deleted, and a CSV + JSON
report is written so the decision is auditable and fully reversible. Pass
``--mode delete`` to hard-delete instead, or ``--dry-run`` to only write the
report without touching any files.

Run from ``backend/``::

    python scripts/clean_dataset.py --dry-run            # preview only
    python scripts/clean_dataset.py                      # quarantine, balanced
    python scripts/clean_dataset.py --strictness conservative
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
import typer

from roomos.config import load_config
from roomos.dataset.builder import FeatureExtractionPipeline
from roomos.features import FrameBurst, FrameRecord
from roomos.model.predict import predict_proba_row
from roomos.model.registry import load_model_bundle
from roomos.utils.logging import get_logger, setup_logging

DEFAULT_CONFIG = Path("configs/inference.yaml")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

log = get_logger("roomos.scripts.clean_dataset")

app = typer.Typer(
    add_completion=False,
    help="Flag/quarantine images that don't match their activity folder using the trained model.",
)


def _discover_images(label_dir: Path) -> List[Path]:
    return sorted(
        p
        for p in label_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def _still_row(
    pipe: FeatureExtractionPipeline, image, label: str, frame_count: int
) -> dict:
    """Build the same zero-motion still-burst feature row used at train time."""
    pipe.reset_motion()
    base = pipe.frame_to_record(
        image_bgr=image, frame_index=0, timestamp=0.0, source=label
    )
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
        start_time=0.0,
        end_time=float(frame_count - 1),
        source=label,
        frames=records,
        burst_index=0,
    )
    fused = pipe.fusion.fuse(burst)
    return fused.as_dict()


def _should_flag(
    label: str,
    probs: Dict[str, float],
    strictness: str,
    balanced_margin: float,
    conservative_conf: float,
    strict_low_conf: float,
) -> tuple[bool, str, str]:
    """Return (flag?, predicted_label, reason)."""
    ordered = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    predicted, top_p = ordered[0]
    label_p = probs.get(label, 0.0)

    if predicted != label:
        gap = top_p - label_p
        if strictness == "conservative":
            if top_p >= conservative_conf:
                return True, predicted, f"model says '{predicted}' p={top_p:.2f} (vs '{label}' {label_p:.2f})"
            return False, predicted, f"disagrees but low conf p={top_p:.2f}, kept (conservative)"
        if strictness == "balanced":
            if gap >= balanced_margin:
                return True, predicted, f"model says '{predicted}' p={top_p:.2f} (+{gap:.2f} over '{label}')"
            return False, predicted, f"near-tie (gap {gap:.2f}), kept (balanced)"
        # strict: any disagreement
        return True, predicted, f"model top is '{predicted}' p={top_p:.2f} (vs '{label}' {label_p:.2f})"

    if strictness == "strict" and label_p < strict_low_conf:
        return True, predicted, f"correct label but low conf ({label_p:.2f} < {strict_low_conf:.2f})"

    return False, predicted, "kept"


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


@app.command()
def main(
    images_dir: Path = typer.Option(Path("data/base_images"), "--images-dir"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c"),
    model_dir: Path = typer.Option(
        Path("data/models/latest"), "--model-dir", help="Trained bundle to score with."
    ),
    mode: str = typer.Option("quarantine", "--mode", help="quarantine | delete"),
    strictness: str = typer.Option(
        "balanced", "--strictness", help="conservative | balanced | strict"
    ),
    labels_only: str = typer.Option(
        "",
        "--labels",
        help="Comma-separated subset of classes to clean (e.g. sleep). Default: all present.",
    ),
    reject_dirname: str = typer.Option("_rejected", "--reject-dirname"),
    balanced_margin: float = typer.Option(
        0.15, "--balanced-margin",
        help="Balanced: flag only if the winning class beats the folder label by >= this prob gap.",
    ),
    conservative_conf: float = typer.Option(
        0.65, "--conservative-conf",
        help="Conservative: flag only if the disagreeing class has prob >= this.",
    ),
    strict_low_conf: float = typer.Option(
        0.30, "--strict-low-conf",
        help="Strict: also flag images whose own label prob is below this.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Score + report only; move/delete nothing."),
    limit: int = typer.Option(0, "--limit", help="Max images per class (0 = all). For testing."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(level=log_level)

    if mode not in {"quarantine", "delete"}:
        raise typer.BadParameter("mode must be 'quarantine' or 'delete'")
    if strictness not in {"conservative", "balanced", "strict"}:
        raise typer.BadParameter("strictness must be conservative|balanced|strict")

    cfg = load_config(config)
    images_root = images_dir if images_dir.is_absolute() else cfg.resolve_path(images_dir)
    if not images_root.is_dir():
        raise typer.BadParameter(f"images-dir not found: {images_root}")

    bundle_dir = model_dir if model_dir.is_absolute() else cfg.resolve_path(model_dir)
    model = load_model_bundle(bundle_dir)
    log.info("Loaded model bundle %s | classes=%s", bundle_dir, model.classes)

    classes = [c for c in cfg.labels.classes if (images_root / c).is_dir()]
    if labels_only.strip():
        wanted = {x.strip() for x in labels_only.split(",") if x.strip()}
        unknown = wanted - set(classes)
        if unknown:
            raise typer.BadParameter(f"Unknown --labels {sorted(unknown)}. Present: {classes}")
        classes = [c for c in classes if c in wanted]
    frame_count = int(cfg.burst.frame_count)

    reject_dir = images_root / reject_dirname
    report_rows: List[dict] = []
    summary: Dict[str, dict] = {}

    log.info(
        "Cleaning %s | mode=%s strictness=%s dry_run=%s classes=%s",
        images_root, mode, strictness, dry_run, classes,
    )

    started = time.time()
    total_seen = 0
    total_flagged = 0

    pipe = FeatureExtractionPipeline(cfg)
    with pipe:
        for label in classes:
            label_dir = images_root / label
            images = _discover_images(label_dir)
            if limit > 0:
                images = images[:limit]

            seen = 0
            flagged = 0
            for img_path in images:
                image = cv2.imread(str(img_path))
                if image is None:
                    log.warning("Unreadable image, skipping: %s", img_path)
                    continue
                seen += 1
                total_seen += 1

                row = _still_row(pipe, image, label, frame_count)
                probs = predict_proba_row(model, row)
                flag, predicted, reason = _should_flag(
                    label, probs, strictness,
                    balanced_margin, conservative_conf, strict_low_conf,
                )

                record = {
                    "label": label,
                    "file": str(img_path),
                    "predicted": predicted,
                    "label_prob": round(probs.get(label, 0.0), 4),
                    "predicted_prob": round(probs.get(predicted, 0.0), 4),
                    "flagged": flag,
                    "reason": reason,
                    "action": "kept",
                }

                if flag:
                    flagged += 1
                    total_flagged += 1
                    if dry_run:
                        record["action"] = "would-flag"
                    elif mode == "delete":
                        img_path.unlink(missing_ok=True)
                        record["action"] = "deleted"
                    else:
                        dest = _quarantine_path(reject_dir, label, img_path)
                        shutil.move(str(img_path), str(dest))
                        record["action"] = "quarantined"
                        record["moved_to"] = str(dest)

                report_rows.append(record)

                if total_seen % 100 == 0:
                    rate = total_seen / max(1e-6, time.time() - started)
                    log.info(
                        "...%d images (%s: %d/%d flagged) | %.1f img/s",
                        total_seen, label, flagged, seen, rate,
                    )

            kept = seen - flagged
            summary[label] = {"seen": seen, "flagged": flagged, "kept": kept}
            log.info("[%s] seen=%d flagged=%d kept=%d", label, seen, flagged, kept)

    reject_dir.mkdir(parents=True, exist_ok=True)
    report_csv = reject_dir / "clean_report.csv"
    fieldnames = [
        "label", "file", "predicted", "label_prob", "predicted_prob",
        "flagged", "reason", "action", "moved_to",
    ]
    with report_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in report_rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    summary_json = reject_dir / "clean_summary.json"
    summary_payload = {
        "images_dir": str(images_root),
        "config": str(cfg.source_path),
        "model_dir": str(bundle_dir),
        "mode": mode,
        "strictness": strictness,
        "dry_run": dry_run,
        "balanced_margin": balanced_margin,
        "conservative_conf": conservative_conf,
        "strict_low_conf": strict_low_conf,
        "total_seen": total_seen,
        "total_flagged": total_flagged,
        "per_class": summary,
        "report_csv": str(report_csv),
        "elapsed_sec": round(time.time() - started, 1),
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    log.info("=" * 60)
    log.info("DONE in %.1fs | seen=%d flagged=%d", time.time() - started, total_seen, total_flagged)
    for label in classes:
        s = summary.get(label, {})
        log.info("  %-9s seen=%-5s flagged=%-5s kept=%-5s",
                 label, s.get("seen", 0), s.get("flagged", 0), s.get("kept", 0))
    log.info("Report: %s", report_csv)
    log.info("Summary: %s", summary_json)


if __name__ == "__main__":
    app()
