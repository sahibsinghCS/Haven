"""Automatically retrain XGBoost when enough live corrections accumulate."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from ..config import Config, load_config
from ..dataset.builder import load_features
from ..model.train import train_model
from ..training.correction_dataset import build_correction_dataframe, merge_base_and_corrections
from ..training.finalize import finalize_training
from ..utils.logging import get_logger

log = get_logger("roomos.training.auto_retrain")


class CorrectionAutoRetrainer:
    """Background retrains ``data/models/latest`` from corrections + prior features."""

    def __init__(
        self,
        config: Config,
        *,
        on_complete: Optional[Callable[[Path], None]] = None,
    ) -> None:
        infer = config.get("inference", {}) or {}
        ar = dict(infer.get("auto_retrain", {}) or {})
        self._enabled = bool(ar.get("enabled", True))
        self._min_corrections = max(1, int(ar.get("min_corrections", 5)))
        self._min_interval_sec = max(30.0, float(ar.get("min_interval_sec", 90)))
        self._correction_weight = float(ar.get("correction_row_weight", 1.0))
        self._confirmation_weight = float(ar.get("confirmation_row_weight", 1.0))
        self._base_weight = float(ar.get("base_row_weight", 1.0))
        self._max_correction_rows = max(10, int(ar.get("max_correction_rows", 80)))
        self._max_correction_weight_fraction = float(
            ar.get("max_correction_weight_fraction", 0.12)
        )
        self._min_test_accuracy = float(ar.get("min_test_accuracy", 0.0))

        self._config = config
        self._train_config_path = Path(
            ar.get("train_config", "configs/train_multi_room.yaml")
        )
        if not self._train_config_path.is_absolute():
            self._train_config_path = config.resolve_path(self._train_config_path)

        default_features = "data/features/multi_room_features.csv"
        if "training" in config:
            default_features = str(
                config.training.get("features_path", default_features)
            )
        features_path = Path(ar.get("base_features_path", default_features))
        if not features_path.is_absolute():
            features_path = config.resolve_path(features_path)
        self._base_features_path = features_path

        infer_fb = dict(infer.get("feedback", {}) or {})
        fb_dir = Path(infer_fb.get("dir", "data/feedback"))
        if not fb_dir.is_absolute():
            fb_dir = config.resolve_path(fb_dir)
        self._feedback_dir = fb_dir

        tr = dict(infer.get("transitions", {}) or {})
        tr_dir = Path(tr.get("dir", "data/transitions"))
        if not tr_dir.is_absolute():
            tr_dir = config.resolve_path(tr_dir)
        self._transitions_dir = tr_dir

        model_dir = Path(infer.get("model_dir", "data/models/latest"))
        if not model_dir.is_absolute():
            model_dir = config.resolve_path(model_dir)
        self._model_dir = model_dir

        self._feature_columns: list[str] = list(ar.get("feature_columns") or [])
        self._on_complete = on_complete

        self._lock = threading.Lock()
        self._running = False
        self._last_run_at = 0.0
        self._corrections_since_run = 0
        self._last_result: Optional[dict] = None
        self._pending_rerun = False
        self._live_snapshot_min_interval = max(
            5.0, float(ar.get("live_snapshot_min_interval_sec", 10))
        )
        self._live_snapshot_instant = bool(ar.get("live_snapshot_instant", True))

    @property
    def enabled(self) -> bool:
        return self._enabled

    def status(self) -> dict:
        stored = 0
        fb_path = self._feedback_dir / "feedback_examples.json"
        if fb_path.is_file():
            try:
                from ..utils.io import read_json

                data = read_json(fb_path)
                ex = data.get("examples", []) if isinstance(data, dict) else []
                stored = len(ex) if isinstance(ex, list) else 0
            except Exception:
                stored = 0
        with self._lock:
            return {
                "enabled": self._enabled,
                "running": self._running,
                "corrections_since_last_run": self._corrections_since_run,
                "stored_corrections": stored,
                "min_corrections": self._min_corrections,
                "min_interval_sec": self._min_interval_sec,
                "last_run_at": self._last_run_at or None,
                "last_result": self._last_result,
            }

    def notify_correction(self) -> None:
        """Burst-based corrections (e.g. transition review) — batch threshold."""
        if not self._enabled:
            return
        should_start = False
        with self._lock:
            self._corrections_since_run += 1
            if (
                not self._running
                and self._corrections_since_run >= self._min_corrections
                and (time.time() - self._last_run_at) >= self._min_interval_sec
            ):
                self._running = True
                should_start = True
        if should_start:
            threading.Thread(
                target=self._run_locked,
                kwargs={"min_rows": self._min_corrections},
                daemon=True,
                name="roomos-auto-retrain",
            ).start()

    def notify_live_snapshot(self) -> None:
        """Live /live tap — retrain from the snapshot row (debounced, min 1 row)."""
        if not self._enabled or not self._live_snapshot_instant:
            self.notify_correction()
            return
        should_start = False
        with self._lock:
            if self._running:
                self._pending_rerun = True
                return
            elapsed = time.time() - self._last_run_at
            if self._last_run_at > 0 and elapsed < self._live_snapshot_min_interval:
                self._pending_rerun = True
                return
            self._running = True
            should_start = True
        if should_start:
            threading.Thread(
                target=self._run_locked,
                kwargs={"min_rows": 1},
                daemon=True,
                name="roomos-auto-retrain-snapshot",
            ).start()

    def _run_locked(self, *, min_rows: Optional[int] = None) -> None:
        try:
            result_summary = self._retrain(min_rows=min_rows)
            with self._lock:
                self._last_result = result_summary
                if result_summary.get("ok"):
                    self._last_run_at = time.time()
                    self._corrections_since_run = 0
        except Exception as e:
            log.exception("Auto-retrain failed: %s", e)
            with self._lock:
                self._last_result = {"ok": False, "error": str(e)}
        finally:
            rerun = False
            with self._lock:
                self._running = False
                if self._pending_rerun:
                    self._pending_rerun = False
                    rerun = True
            if rerun and self._live_snapshot_instant:
                self.notify_live_snapshot()

    def _retrain(self, *, min_rows: Optional[int] = None) -> dict:
        threshold = self._min_corrections if min_rows is None else max(1, int(min_rows))
        train_cfg = load_config(self._train_config_path)
        feature_cols = self._feature_columns
        if not feature_cols:
            from ..model.registry import load_model_bundle

            bundle = load_model_bundle(self._model_dir)
            feature_cols = list(bundle.feature_columns)

        correction_df = build_correction_dataframe(
            feedback_dir=self._feedback_dir,
            transitions_dir=self._transitions_dir,
            feature_columns=feature_cols,
            correction_row_weight=self._correction_weight,
            confirmation_row_weight=self._confirmation_weight,
            max_correction_rows=self._max_correction_rows,
        )
        n_corr = len(correction_df)
        if n_corr < threshold:
            log.info("Auto-retrain skipped: only %d correction rows (need %d)", n_corr, threshold)
            return {"ok": False, "reason": "not_enough_correction_rows", "correction_rows": n_corr}

        base_df = load_features(self._base_features_path)
        if base_df.empty:
            log.warning("Base features missing at %s — training on corrections only", self._base_features_path)

        combined = merge_base_and_corrections(
            base_df,
            correction_df,
            base_row_weight=self._base_weight,
            max_correction_weight_fraction=self._max_correction_weight_fraction,
        )
        log.info(
            "Auto-retrain: %d base rows + %d correction rows -> %s",
            len(base_df),
            n_corr,
            self._model_dir,
        )

        result = train_model(combined, train_cfg, output_dir=self._model_dir)
        test_acc = float(result.metrics.get("test", {}).get("accuracy", 0.0))
        if self._min_test_accuracy > 0 and test_acc < self._min_test_accuracy:
            log.warning(
                "Auto-retrain test acc %.3f below floor %.3f — bundle still written",
                test_acc,
                self._min_test_accuracy,
            )

        finalize_training(
            result,
            train_cfg,
            inference_config=Path("configs/inference.yaml"),
            skip_verify=False,
        )

        if self._on_complete:
            try:
                self._on_complete(self._model_dir)
            except Exception as e:
                log.warning("Post-retrain callback failed: %s", e)

        return {
            "ok": True,
            "correction_rows": n_corr,
            "base_rows": len(base_df),
            "total_rows": len(combined),
            "test_accuracy": test_acc,
            "bundle_dir": str(self._model_dir),
        }
