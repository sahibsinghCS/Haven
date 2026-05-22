"""Shared post-training steps (verify + operator hints)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import Config
from ..model.compat import (
    TrainServeCompatibilityError,
    print_training_success,
    verify_bundle_for_live,
)
from ..model.train import TrainResult
from ..utils.logging import get_logger

log = get_logger("roomos.training.finalize")

DEFAULT_INFERENCE_CONFIG = Path("configs/inference.yaml")


def log_training_metrics(result: TrainResult) -> None:
    log.info("Training complete -> %s", result.bundle_dir)
    for split in ("train", "val", "test"):
        if split in result.metrics:
            m = result.metrics[split]
            log.info(
                "%-5s acc=%.3f macro_f1=%.3f weighted_f1=%.3f n=%d",
                split,
                m["accuracy"],
                m["macro_f1"],
                m["weighted_f1"],
                m["n_samples"],
            )


def finalize_training(
    result: TrainResult,
    train_cfg: Config,
    *,
    inference_config: Path = DEFAULT_INFERENCE_CONFIG,
    skip_verify: bool = False,
) -> None:
    """Verify train/serve compatibility and print next-step commands."""
    if not skip_verify:
        try:
            report = verify_bundle_for_live(
                result.bundle_dir,
                inference_config=inference_config,
                train_config=train_cfg,
            )
            from ..utils.io import write_json

            write_json(
                Path(result.bundle_dir) / "live_compat.json",
                {
                    "verified_at_train": True,
                    "inference_config": str(inference_config),
                    **report,
                },
            )
            log.info(
                "Train/serve compatibility OK (%d feature columns)",
                report["n_bundle_columns"],
            )
        except TrainServeCompatibilityError:
            log.exception("Compatibility check failed")
            raise
    try:
        from ..model.eval_report import generate_report_from_bundle

        generate_report_from_bundle(result.bundle_dir, recompute=False)
    except Exception as e:
        log.warning("Could not refresh eval_report: %s", e)

    print_training_success(result.bundle_dir, inference_config=str(inference_config))
