"""Background training jobs for user-defined moods.

Builds a training set from on-device personal datasets (cached burst features
captured during live collection, re-extracted from frames when stale) merged
with the multi-room base features for builtin classes, trains XGBoost with a
dynamic class list from the mood registry, evaluates on a held-out split, and
only promotes ``data/models/latest`` when the eval gate passes (previous
bundle is kept at ``data/models/previous`` for rollback).
"""

from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..config import load_config
from ..model.compat import TrainServeCompatibilityError, verify_bundle_for_live
from ..model.train import train_model
from ..moods import registry as mood_registry
from ..utils.logging import get_logger
from . import personal_dataset as pds

log = get_logger("roomos.training.personal_trainer")

_BACKEND_DIR = Path(__file__).resolve().parents[2]

TRAIN_CONFIG_PATH = _BACKEND_DIR / "configs" / "train_personal.yaml"
INFERENCE_CONFIG_PATH = _BACKEND_DIR / "configs" / "inference.yaml"
MODELS_DIR = _BACKEND_DIR / "data" / "models"
BASE_FEATURES_PATH = _BACKEND_DIR / "data" / "features" / "multi_room_features.csv"

# Eval gate (kept deliberately forgiving for small personal datasets).
MIN_TEST_ACCURACY = 0.55
MIN_TEST_SAMPLES_FOR_GATE = 10
CLASS_IMBALANCE_WARN_RATIO = 10.0

PHASES = (
    "queued",
    "extracting_features",
    "training",
    "validating",
    "promoting",
    "reloading",
    "done",
    "error",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PersonalTrainingError(RuntimeError):
    pass


class PersonalTrainingJobManager:
    """One training job at a time; status persisted for HTTP polling."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: Dict[str, dict] = {}
        self._running_job_id: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

    # --- public API ------------------------------------------------------

    def start_job(
        self,
        mood_id: str,
        *,
        on_promoted: Optional[Callable[[], None]] = None,
        datasets_root: Optional[Path] = None,
        jobs_root: Optional[Path] = None,
        moods_path: Optional[Path] = None,
        base_features_path: Optional[Path] = None,
        models_dir: Optional[Path] = None,
    ) -> dict:
        with self._lock:
            if self._running_job_id is not None:
                running = self._jobs.get(self._running_job_id)
                if running and running.get("phase") not in ("done", "error"):
                    raise PersonalTrainingError(
                        "A training job is already running. Wait for it to finish."
                    )
            ds_root = Path(datasets_root) if datasets_root else mood_registry.datasets_root()
            mood = mood_registry.get_mood(mood_id, path=moods_path)
            if mood is None:
                raise PersonalTrainingError(f"Unknown mood: {mood_id!r}")
            counts = pds.dataset_counts(ds_root, mood_id)
            if (
                counts["burstCount"] < pds.MIN_BURSTS_TO_TRAIN
                or counts["frameCount"] < pds.MIN_FRAMES_TO_TRAIN
            ):
                raise PersonalTrainingError(
                    f"Need more data for '{mood['displayName']}': have "
                    f"{counts['burstCount']} bursts / {counts['frameCount']} frames, "
                    f"need at least {pds.MIN_BURSTS_TO_TRAIN} bursts and "
                    f"{pds.MIN_FRAMES_TO_TRAIN} frames. Keep collecting on Live."
                )

            job_id = f"train_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
            job = {
                "id": job_id,
                "moodId": mood_id,
                "phase": "queued",
                "progress": 0.0,
                "startedAt": _now_iso(),
                "finishedAt": None,
                "ok": None,
                "error": None,
                "warnings": [],
                "result": None,
            }
            self._jobs[job_id] = job
            self._running_job_id = job_id
            jroot = Path(jobs_root) if jobs_root else mood_registry.training_jobs_root()
            self._persist(job, jroot)

            self._thread = threading.Thread(
                target=self._run_guarded,
                args=(
                    job_id,
                    ds_root,
                    jroot,
                    moods_path,
                    Path(base_features_path) if base_features_path else BASE_FEATURES_PATH,
                    Path(models_dir) if models_dir else MODELS_DIR,
                    on_promoted,
                ),
                name="roomos-personal-train",
                daemon=True,
            )
            self._thread.start()
            return dict(job)

    def get_job(self, job_id: str, jobs_root: Optional[Path] = None) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                return dict(job)
        jroot = Path(jobs_root) if jobs_root else mood_registry.training_jobs_root()
        path = jroot / f"{job_id}.json"
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return None

    def is_running(self) -> bool:
        with self._lock:
            if self._running_job_id is None:
                return False
            job = self._jobs.get(self._running_job_id)
            return bool(job and job.get("phase") not in ("done", "error"))

    # --- job execution ----------------------------------------------------

    def _persist(self, job: dict, jobs_root: Path) -> None:
        try:
            jobs_root.mkdir(parents=True, exist_ok=True)
            (jobs_root / f"{job['id']}.json").write_text(
                json.dumps(job, indent=2), encoding="utf-8"
            )
        except OSError as e:
            log.debug("Could not persist training job: %s", e)

    def _update(
        self, job: dict, jobs_root: Path, *, phase: Optional[str] = None, **fields: Any
    ) -> None:
        with self._lock:
            if phase is not None:
                job["phase"] = phase
            job.update(fields)
            self._persist(job, jobs_root)

    def _run_guarded(
        self,
        job_id: str,
        datasets_root: Path,
        jobs_root: Path,
        moods_path: Optional[Path],
        base_features_path: Path,
        models_dir: Path,
        on_promoted: Optional[Callable[[], None]],
    ) -> None:
        job = self._jobs[job_id]
        try:
            self._run(
                job,
                datasets_root,
                jobs_root,
                moods_path,
                base_features_path,
                models_dir,
                on_promoted,
            )
        except Exception as e:
            log.exception("Personal training job failed: %s", e)
            self._update(
                job,
                jobs_root,
                phase="error",
                ok=False,
                error=str(e),
                finishedAt=_now_iso(),
            )
            try:
                mood_registry.update_mood_ml(
                    job["moodId"], path=moods_path, status="error"
                )
            except Exception:
                pass
        finally:
            with self._lock:
                if self._running_job_id == job_id:
                    self._running_job_id = None

    def _run(
        self,
        job: dict,
        datasets_root: Path,
        jobs_root: Path,
        moods_path: Optional[Path],
        base_features_path: Path,
        models_dir: Path,
        on_promoted: Optional[Callable[[], None]],
    ) -> None:
        import pandas as pd

        cfg = load_config(TRAIN_CONFIG_PATH)

        # 1) Resolve dynamic class list: every ML-enabled mood that has either
        #    personal data on disk or base (multi-room) coverage.
        self._update(job, jobs_root, phase="extracting_features", progress=0.05)
        candidates = mood_registry.ml_class_candidates(path=moods_path)
        personal_counts = {
            m: pds.dataset_counts(datasets_root, m) for m in candidates
        }
        base_df = None
        base_labels: set[str] = set()
        if base_features_path.is_file():
            try:
                base_df = pd.read_csv(base_features_path)
                base_labels = set(base_df["label"].astype(str).unique())
            except Exception as e:
                log.warning("Could not load base features (%s); personal-only.", e)
                base_df = None

        classes: List[str] = []
        for mood_id in candidates:
            has_personal = personal_counts[mood_id]["burstCount"] >= pds.MIN_BURSTS_TO_TRAIN
            has_base = mood_id in base_labels
            if has_personal or has_base:
                classes.append(mood_id)
        if job["moodId"] not in classes:
            raise PersonalTrainingError(
                f"Mood '{job['moodId']}' has too little data to train."
            )
        if len(classes) < 2:
            raise PersonalTrainingError(
                "Need at least two moods with training data. Collect data for "
                "another mood (or restore a builtin) first."
            )

        # 2) Personal rows: cached features, re-extracted only when stale.
        personal_rows = self._personal_rows(cfg, datasets_root, classes, job, jobs_root)
        n_personal_by_class: Dict[str, int] = {}
        for row in personal_rows:
            n_personal_by_class[row["label"]] = n_personal_by_class.get(row["label"], 0) + 1
        warnings: List[str] = []
        if n_personal_by_class:
            lo = min(n_personal_by_class.values())
            hi = max(n_personal_by_class.values())
            if lo > 0 and hi / max(1, lo) >= CLASS_IMBALANCE_WARN_RATIO:
                warnings.append(
                    "Class balance: one mood has "
                    f"{hi} bursts vs another's {lo} (>{CLASS_IMBALANCE_WARN_RATIO:.0f}x). "
                    "Consider collecting more for the smaller mood."
                )

        frames = []
        if personal_rows:
            frames.append(pd.DataFrame(personal_rows))
        if base_df is not None:
            base_keep = base_df[base_df["label"].astype(str).isin(classes)].copy()
            if len(base_keep):
                if "row_weight" not in base_keep.columns:
                    base_keep["row_weight"] = 1.0
                base_keep["row_weight"] = base_keep["row_weight"].fillna(1.0)
                if "dataset" not in base_keep.columns:
                    base_keep["dataset"] = "multi_room_base"
                frames.append(base_keep)
        if not frames:
            raise PersonalTrainingError("No training rows available.")
        df = pd.concat(frames, ignore_index=True, sort=False)

        # 3) Train into a candidate bundle with the dynamic class list.
        self._update(job, jobs_root, phase="training", progress=0.45, warnings=warnings)
        cfg.raw.setdefault("labels", {})["classes"] = list(classes)
        split = cfg.raw.setdefault("training", {}).setdefault("split", {})
        split.setdefault("strategy", "by_source")
        split["test_size"] = max(0.2, float(split.get("test_size", 0.2)))
        candidate_dir = models_dir / f"candidate_{job['id']}"
        if candidate_dir.exists():
            shutil.rmtree(candidate_dir, ignore_errors=True)
        result = train_model(df, cfg, output_dir=candidate_dir)

        # 4) Eval gate before promotion.
        self._update(job, jobs_root, phase="validating", progress=0.8)
        eval_split = result.metrics.get("test") or result.metrics.get("val") or {}
        accuracy = float(eval_split.get("accuracy", 0.0))
        n_eval = int(eval_split.get("n_samples", 0))
        per_class = {
            cls: {
                "precision": float(stats.get("precision", 0.0)),
                "recall": float(stats.get("recall", 0.0)),
                "f1": float(stats.get("f1-score", 0.0)),
                "support": int(stats.get("support", 0)),
            }
            for cls, stats in (eval_split.get("per_class") or {}).items()
            if cls in classes
        }
        if n_eval >= MIN_TEST_SAMPLES_FOR_GATE and accuracy < MIN_TEST_ACCURACY:
            shutil.rmtree(candidate_dir, ignore_errors=True)
            raise PersonalTrainingError(
                f"Held-out accuracy {accuracy:.0%} is below the "
                f"{MIN_TEST_ACCURACY:.0%} safety gate — model NOT deployed. "
                "Collect more (or more varied) data and retrain."
            )
        if n_eval < MIN_TEST_SAMPLES_FOR_GATE:
            warnings.append(
                f"Small held-out set ({n_eval} bursts) — accuracy gate skipped."
            )

        # 5) Promote: keep rollback bundle, then swap latest.
        self._update(job, jobs_root, phase="promoting", progress=0.88, warnings=warnings)
        latest = models_dir / "latest"
        previous = models_dir / "previous"
        if latest.exists():
            shutil.rmtree(previous, ignore_errors=True)
            shutil.copytree(latest, previous)
            shutil.rmtree(latest, ignore_errors=True)
        shutil.copytree(candidate_dir, latest)
        shutil.rmtree(candidate_dir, ignore_errors=True)

        try:
            report = verify_bundle_for_live(latest, inference_config=INFERENCE_CONFIG_PATH)
            from ..utils.io import write_json

            write_json(
                latest / "live_compat.json",
                {"verified_at_train": True, "inference_config": str(INFERENCE_CONFIG_PATH), **report},
            )
        except TrainServeCompatibilityError as e:
            # Roll back: the new bundle would brick the live engine.
            shutil.rmtree(latest, ignore_errors=True)
            if previous.exists():
                shutil.copytree(previous, latest)
            raise PersonalTrainingError(
                f"New model failed the live compatibility gate; rolled back. {e}"
            ) from e

        # 6) Registry bookkeeping + privacy cleanup.
        trained_at = _now_iso()
        for mood_id in classes:
            counts = personal_counts.get(mood_id, {"burstCount": 0, "frameCount": 0})
            try:
                mood_registry.update_mood_ml(
                    mood_id,
                    path=moods_path,
                    status="ready",
                    lastTrainedAt=trained_at,
                    burstCount=counts["burstCount"],
                    frameCount=counts["frameCount"],
                )
            except mood_registry.MoodValidationError:
                pass  # mood deleted mid-train
        cleared = 0
        for mood_id, counts in personal_counts.items():
            if counts["burstCount"] > 0:
                cleared += pds.clear_raw_frames(datasets_root, mood_id)

        # 7) Hot-reload the live engine.
        self._update(job, jobs_root, phase="reloading", progress=0.95)
        if on_promoted is not None:
            try:
                on_promoted()
            except Exception as e:
                warnings.append(f"Model deployed but live reload failed: {e}")

        self._update(
            job,
            jobs_root,
            phase="done",
            progress=1.0,
            ok=True,
            finishedAt=_now_iso(),
            warnings=warnings,
            result={
                "classes": classes,
                "accuracy": accuracy,
                "macroF1": float(eval_split.get("macro_f1", 0.0)),
                "nEvalSamples": n_eval,
                "perClass": per_class,
                "personalBurstsByClass": n_personal_by_class,
                "clearedFrames": cleared,
                "bundleDir": str(latest),
            },
        )
        log.info(
            "Personal training done: classes=%s acc=%.3f (n=%d)",
            classes,
            accuracy,
            n_eval,
        )

    # --- dataset -> rows ---------------------------------------------------

    def _personal_rows(
        self,
        cfg,
        datasets_root: Path,
        classes: List[str],
        job: dict,
        jobs_root: Path,
    ) -> List[dict]:
        rows: List[dict] = []
        train_cfg = cfg.get("training", {}) or {}
        use_weights = bool(train_cfg.get("use_row_weights", True))
        weight = float(train_cfg.get("default_row_weight", 12.0))

        pipe = None  # lazy — only loaded when a burst must be re-extracted
        try:
            for mood_id in classes:
                mood_dir = pds.mood_dataset_dir(datasets_root, mood_id)
                if not mood_dir.is_dir():
                    continue
                cached: Dict[str, dict] = {}
                fdir = pds.features_dir(datasets_root, mood_id)
                if fdir.is_dir():
                    for f in sorted(fdir.glob("*.json")):
                        try:
                            cached[f.stem] = json.loads(f.read_text(encoding="utf-8"))
                        except (OSError, json.JSONDecodeError):
                            continue

                bursts_root = mood_dir / "bursts"
                disk_bursts = (
                    {d.name for d in bursts_root.iterdir() if d.is_dir()}
                    if bursts_root.is_dir()
                    else set()
                )
                all_burst_ids = sorted(set(cached) | disk_bursts)
                for burst_id in all_burst_ids:
                    payload = cached.get(burst_id)
                    frame_files = (
                        sorted((bursts_root / burst_id).glob("frame_*.jpg"))
                        if burst_id in disk_bursts
                        else []
                    )
                    use_cache = payload is not None and (
                        not frame_files or int(payload.get("nFrames", -1)) == len(frame_files)
                    )
                    if use_cache:
                        features = dict(payload.get("features") or {})
                        metadata = dict(payload.get("metadata") or {})
                    elif len(frame_files) >= pds.MIN_FRAMES_PER_BURST:
                        if pipe is None:
                            from ..dataset.builder import FeatureExtractionPipeline

                            pipe = FeatureExtractionPipeline(cfg)
                            pipe.load()
                        features, metadata = self._extract_burst(
                            pipe, frame_files, mood_id, burst_id
                        )
                        if features is None:
                            continue
                    else:
                        continue
                    row = dict(metadata)
                    row.update(features)
                    row["label"] = mood_id
                    row["source"] = f"personal/{mood_id}/{burst_id}"
                    row["notes"] = "personal mood collection"
                    if use_weights:
                        row["row_weight"] = weight
                        row["dataset"] = "personal_room"
                    rows.append(row)
        finally:
            if pipe is not None:
                try:
                    pipe.close()
                except Exception:
                    pass
        return rows

    def _extract_burst(self, pipe, frame_files: List[Path], mood_id: str, burst_id: str):
        import cv2

        from ..features import FrameBurst

        records = []
        pipe.reset_motion()
        source_id = f"personal/{mood_id}/{burst_id}"
        for i, fp in enumerate(frame_files):
            image = cv2.imread(str(fp))
            if image is None:
                continue
            records.append(
                pipe.frame_to_record(
                    image_bgr=image,
                    frame_index=i,
                    timestamp=float(i),
                    source=source_id,
                )
            )
        if len(records) < pds.MIN_FRAMES_PER_BURST:
            return None, None
        burst = FrameBurst(
            start_time=0.0,
            end_time=float(len(records) - 1),
            source=source_id,
            frames=records,
            burst_index=0,
        )
        fused = pipe.fusion.fuse(burst)
        return dict(fused.as_dict()), dict(fused.metadata)


# Process-wide singleton used by the moods API.
personal_training_jobs = PersonalTrainingJobManager()
