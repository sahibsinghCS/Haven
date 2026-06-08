"""Live inference: repeated burst capture -> XGBoost -> smoothing -> actions."""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Deque, Dict, List, Mapping, Optional

import numpy as np

from ..actions.engine import ActionEngine
from ..config import Config, load_actions_config
from ..dataset.builder import FeatureExtractionPipeline
from ..features import BurstAggregator, FrameBurst
from ..model.predict import predict_proba_row
from ..model.registry import ActivityModel, load_model_bundle
from ..personalization import (
    FeedbackCorrection,
    FeedbackReinforcementModel,
    StateTransition,
    TransitionJournal,
)
from ..preferences.document import active_preset_preferences
from ..utils.io import append_jsonl, read_json
from ..utils.logging import get_logger
from ..video import open_video_source
from .activity_hints import ActivityHintGate, build_activity_hints_from_config
from .occupancy import OccupancyDecision, OccupancyGate, build_gate_from_config
from .overlays import draw_overlay
from .smoothing import PredictionSmoother, SmoothedPrediction, smoothing_confirm_bursts

log = get_logger("roomos.inference.live")


# Frontend taxonomy (must match web/src/types/roomos.ts ROOM_STATE_ORDER).
_UI_STATE_ORDER: tuple[str, ...] = ("sleep", "gaming", "work", "relaxing", "away")
_ACTIVITY_LABELS: tuple[str, ...] = ("work", "gaming", "sleep", "relaxing")


@dataclass
class LiveSnapshot:
    schema_version: int = 1
    captured_at: str = ""
    primary_state: str = "unknown"
    primary_confidence: float = 0.0
    distribution: Dict[str, float] = field(default_factory=dict)
    rationale: List[str] = field(default_factory=list)
    applied_scene: Dict[str, object] = field(default_factory=dict)
    confidence_history: List[Dict[str, object]] = field(default_factory=list)
    personalization: Dict[str, object] = field(default_factory=dict)
    model_probs: Dict[str, float] = field(default_factory=dict)
    sequence: int = 0
    last_automation: Dict[str, object] = field(default_factory=dict)
    automation_mode: str = "dry_run"  # dry_run | live | off
    data_source: str = "roomos-ml"  # roomos-ml | demo-replay

    def to_frontend_dict(self) -> dict:
        dist = _normalize_ui_distribution(self.distribution)
        return {
            "schemaVersion": int(self.schema_version),
            "sequence": int(self.sequence),
            "capturedAt": self.captured_at,
            "stream": {
                "streamUrl": None,
                "posterUrl": None,
                "aspectLabel": "16/9",
            },
            "primaryState": self.primary_state,
            "primaryConfidence": float(self.primary_confidence),
            "distribution": dist,
            "modelDistribution": _normalize_ui_distribution(self.model_probs),
            "rationale": list(self.rationale),
            "appliedScene": dict(self.applied_scene),
            "confidenceHistory": list(self.confidence_history),
            "personalization": dict(self.personalization),
            "lastAutomation": dict(self.last_automation),
            "automationMode": self.automation_mode,
            "dataSource": self.data_source,
        }


def _live_presence_fixup(
    probs: Dict[str, float],
    features: Mapping[str, float],
) -> Dict[str, float]:
    """Webcam + desk: demote false Away when motion and an activity class are competitive."""
    motion = float(features.get("motion_mean_mean", 0.0) or 0.0)
    if motion < 0.004:
        return probs
    activities = {c: float(probs.get(c, 0.0)) for c in _ACTIVITY_LABELS}
    best = max(activities, key=activities.get)
    best_p = activities[best]
    away_p = float(probs.get("away", 0.0))
    work_p = float(probs.get("work", 0.0))

    if away_p <= best_p:
        return probs

    # Person at desk: Away barely beats Work — trust motion + work/activity.
    if best_p >= 0.18 and motion >= 0.005:
        adjusted = dict(probs)
        adjusted["away"] = min(away_p, best_p * 0.55)
        adjusted[best] = max(best_p, away_p * 0.72)
        return _normalize_ui_distribution(adjusted)

    if work_p >= 0.22 and away_p - work_p < 0.35 and motion >= 0.005:
        adjusted = dict(probs)
        adjusted["work"] = max(work_p, away_p * 0.7)
        adjusted["away"] = min(away_p, work_p * 0.9)
        return _normalize_ui_distribution(adjusted)

    return probs


def _bootstrap_live_fixup(
    probs: Dict[str, float],
    features: Mapping[str, float],
) -> Dict[str, float]:
    """Extra demotion for synthetic bootstrap weights."""
    out = _live_presence_fixup(probs, features)
    if out is not probs:
        return out
    motion = float(features.get("motion_mean_mean", 0.0) or 0.0)
    if motion < 0.005:
        return probs
    activities = {c: float(probs.get(c, 0.0)) for c in _ACTIVITY_LABELS}
    best = max(activities, key=activities.get)
    best_p = activities[best]
    away_p = float(probs.get("away", 0.0))
    if best_p < 0.12 or away_p <= best_p:
        return probs
    adjusted = dict(probs)
    adjusted["away"] = min(away_p, best_p * 0.4)
    adjusted[best] = max(best_p, away_p * 0.75)
    return _normalize_ui_distribution(adjusted)


def _normalize_ui_distribution(raw: Dict[str, float]) -> Dict[str, float]:
    """Ensure all five UI states exist and probabilities sum to ~1."""
    vals = {k: max(0.0, float(raw.get(k, 0.0))) for k in _UI_STATE_ORDER}
    total = sum(vals.values())
    if total <= 1e-9:
        uniform = 1.0 / len(_UI_STATE_ORDER)
        return {k: uniform for k in _UI_STATE_ORDER}
    return {k: vals[k] / total for k in _UI_STATE_ORDER}


SnapshotCallback = Callable[[LiveSnapshot], None]


class LiveInferenceEngine:
    def __init__(
        self,
        config: Config,
        *,
        model: Optional[ActivityModel] = None,
        actions: Optional[ActionEngine] = None,
        on_snapshot: Optional[SnapshotCallback] = None,
        on_frame: Optional[Callable[[np.ndarray, SmoothedPrediction], None]] = None,
        on_preview_frame: Optional[Callable[[np.ndarray], None]] = None,
    ) -> None:
        self.config = config
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        infer_cfg = config.get("inference", {}) or {}
        model_dir = Path(infer_cfg.get("model_dir", "data/models/latest"))
        if not model_dir.is_absolute():
            model_dir = config.resolve_path(model_dir)
        self._model_dir = model_dir
        self._model = model or load_model_bundle(model_dir)
        self._actions = actions
        self._on_snapshot = on_snapshot
        self._on_frame = on_frame
        self._on_preview_frame = on_preview_frame

        feat_cfg = (config.get("features", {}) or {}).get("enabled", {}) or {}
        self._pose_enabled = bool(feat_cfg.get("pose", True))

        # Cheap occupancy gate — vetoes false-positive activity labels on
        # empty scenes (couch with no person, etc.). See inference/occupancy.py.
        unknown_label_for_gate = str(config.labels.get("unknown_class", "unknown"))
        clip_prompts = (
            (config.get("features", {}) or {}).get("clip", {}) or {}
        ).get("prompts") or []
        self._occupancy_gate: OccupancyGate = build_gate_from_config(
            occupancy_cfg=infer_cfg.get("occupancy"),
            away_label="away",
            unknown_label=unknown_label_for_gate,
            pose_enabled=self._pose_enabled,
            clip_prompts=list(clip_prompts) if clip_prompts else None,
        )
        self._activity_hints: ActivityHintGate = build_activity_hints_from_config(
            infer_cfg.get("activity_hints"),
        )

        # Boot phase exposed via state.status_payload so the UI can show
        # specific copy ("Loading models", "Camera up — first burst pending",
        # "Streaming") instead of an indefinite spinner.
        self._boot_phase: str = "starting"  # starting | opening_camera | warming_up | streaming
        self._preview_fit: str = "cover"
        self._preview_frame_shape: Optional[tuple[int, ...]] = None
        self._capture_size: Optional[tuple[int, int]] = None
        self._first_frame_at: Optional[float] = None
        self._first_burst_at: Optional[float] = None

        # Bootstrap model heuristic — looks at the config that produced the
        # bundle (we tag it in `_source_config` during finalize). UI shows a
        # banner so demos make clear it's a synthetic-stills model.
        self._is_bootstrap_model = _looks_like_bootstrap_bundle(self._model)
        lf_cfg = dict(infer_cfg.get("live_presence_fixup", {}) or {})
        self._live_presence_fixup_enabled = bool(lf_cfg.get("enabled", False))

        if self._is_bootstrap_model:
            self._occupancy_gate.enabled = False
            log.warning(
                "Loaded bootstrap demo model — occupancy gate disabled. "
                "Run `npm run train:multi-room` and restart for real webcam accuracy."
            )

        smooth_cfg = config.smoothing
        unknown_label = str(config.labels.get("unknown_class", "unknown"))
        self._smoother = PredictionSmoother(
            classes=list(self._model.classes),
            unknown_label=unknown_label,
            min_confidence=float(smooth_cfg.min_confidence),
            ema_alpha=float(smooth_cfg.prob_ema_alpha),
            confirm_bursts=smoothing_confirm_bursts(smooth_cfg),
            cooldown_sec=float(smooth_cfg.cooldown_sec),
        )

        history_len = int(infer_cfg.get("snapshot_history", 60))
        self._history: Deque[Dict[str, object]] = deque(maxlen=history_len)
        self._ui_classes = list(_UI_STATE_ORDER)
        prefs_path = infer_cfg.get("preferences_path", "data/preferences.json")
        self._preferences_path = (
            Path(prefs_path)
            if Path(prefs_path).is_absolute()
            else config.resolve_path(Path(prefs_path))
        )
        self._preferences_cache: tuple[float, dict[str, dict[str, object]]] = (0.0, {})

        self._log_predictions = bool(infer_cfg.get("log_predictions", True))
        self._pred_log_path = Path(infer_cfg.get("predictions_log", "data/logs/predictions.jsonl"))
        if not self._pred_log_path.is_absolute():
            self._pred_log_path = config.resolve_path(self._pred_log_path)

        self._overlay = bool(infer_cfg.get("overlay", True))
        self._show_window = bool(infer_cfg.get("show_window", False))
        self._snapshot_seq = 0

        feedback_cfg = dict(infer_cfg.get("feedback", {}) or {})
        feedback_dir = Path(feedback_cfg.get("dir", "data/feedback"))
        if not feedback_dir.is_absolute():
            feedback_dir = config.resolve_path(feedback_dir)
        self._feedback_enabled = bool(feedback_cfg.get("enabled", True))
        influence = float(feedback_cfg.get("influence", 0.35))
        if _is_personal_room_bundle(self._model):
            boost = float(feedback_cfg.get("personal_room_influence_boost", 1.2))
            influence = min(1.0, influence * boost)
        self._feedback_model = (
            FeedbackReinforcementModel(
                root_dir=feedback_dir,
                classes=list(self._model.classes),
                feature_columns=list(self._model.feature_columns),
                influence=influence,
                similarity_floor=float(feedback_cfg.get("similarity_floor", 0.72)),
                nearest_k=int(feedback_cfg.get("nearest_k", 8)),
                max_examples=int(feedback_cfg.get("max_examples", 500)),
                penalty_factor=float(feedback_cfg.get("penalty_factor", 0.45)),
                personalization_blend=float(
                    feedback_cfg.get("personalization_blend", 1.0)
                ),
            )
            if self._feedback_enabled
            else None
        )
        self._evidence_lock = threading.RLock()
        self._latest_evidence: Optional[dict] = None
        self._recent_screenshots: Deque[np.ndarray] = deque(maxlen=5)
        self._frame_lock = threading.RLock()
        self._latest_live_frame_bgr: Optional[np.ndarray] = None
        self._latest_snapshot: Optional[LiveSnapshot] = None
        self._pipe_lock = threading.RLock()
        self._feedback_pipe: Optional[FeatureExtractionPipeline] = None
        self._run_error: Optional[str] = None

        transitions_cfg = dict(infer_cfg.get("transitions", {}) or {})
        self._transitions_enabled = bool(transitions_cfg.get("enabled", True))
        transitions_dir = Path(transitions_cfg.get("dir", "data/transitions"))
        if not transitions_dir.is_absolute():
            transitions_dir = config.resolve_path(transitions_dir)
        self._transition_journal: Optional[TransitionJournal] = (
            TransitionJournal(
                root_dir=transitions_dir,
                max_entries=int(transitions_cfg.get("max_entries", 200)),
            )
            if self._transitions_enabled
            else None
        )

        self._auto_retrainer = None
        ar_cfg = dict(infer_cfg.get("auto_retrain", {}) or {})
        if bool(ar_cfg.get("enabled", True)):
            from ..training.auto_retrain import CorrectionAutoRetrainer

            self._auto_retrainer = CorrectionAutoRetrainer(
                config,
                on_complete=lambda _p: self.reload_model_bundle(),
            )
            self._auto_retrainer._feature_columns = list(self._model.feature_columns)
        self._previous_displayed_label: str = unknown_label

    def start_background(self) -> None:
        if self._thread and self._thread.is_alive():
            log.warning("Live engine already running; ignoring start_background().")
            return
        self._stop_event.clear()
        self._run_error = None
        self._thread = threading.Thread(target=self._run_guarded, name="roomos-live", daemon=True)
        self._thread.start()
        log.info("Live engine started in background thread.")

    def _run_guarded(self) -> None:
        try:
            self.run()
        except Exception as e:
            self._run_error = str(e)
            log.exception("Live inference thread failed: %s", e)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        self._thread = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # --- status surface used by app.core.state.status_payload ----------

    @property
    def boot_phase(self) -> str:
        """starting | opening_camera | warming_up | streaming."""
        return self._boot_phase

    @property
    def is_bootstrap_model(self) -> bool:
        return self._is_bootstrap_model

    @property
    def model_kind(self) -> str:
        if self._is_bootstrap_model:
            return "bootstrap"
        return _trained_model_kind(self._model.train_config or {})

    @property
    def pose_enabled(self) -> bool:
        return self._pose_enabled

    def run(self) -> None:
        cfg = self.config
        video_cfg = cfg.video
        bcfg = cfg.burst

        pipe = FeatureExtractionPipeline(cfg)
        pipe.load()

        agg = BurstAggregator(
            duration_seconds=float(bcfg.duration_seconds),
            stride_seconds=float(bcfg.stride_seconds),
            frame_count=int(bcfg.frame_count),
            sampling_strategy=str(bcfg.sampling_strategy),
            min_collected_frames=int(bcfg.min_collected_frames),
        )

        import os

        env_source = os.environ.get("ROOMOS_VIDEO_SOURCE")
        env_backend = os.environ.get("ROOMOS_VIDEO_BACKEND")
        source = video_cfg.source if env_source is None else env_source
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        sid = f"live::{source}"
        # video_cfg is an _AttrDict (also a real dict) so .get is safe.
        backend_hint = env_backend or str(video_cfg.get("backend", "auto") or "auto")
        log.info(
            "Live inference (burst): source=%s backend=%s frames/burst=%d duration=%.2fs stride=%.2fs",
            source,
            backend_hint,
            int(bcfg.frame_count),
            float(bcfg.duration_seconds),
            float(bcfg.stride_seconds),
        )

        last_pred: Optional[SmoothedPrediction] = None
        self._boot_phase = "opening_camera"

        preview_cfg = video_cfg.get("preview", {}) or {}
        preview_fps = float(
            preview_cfg.get("max_fps", video_cfg.get("preview_max_fps", 20))
        )
        capture_width = video_cfg.get("capture_width")
        capture_height = video_cfg.get("capture_height")
        capture_fps = video_cfg.get("capture_fps")
        frame_preprocess = dict(video_cfg.get("frame_preprocess") or {})
        self._preview_fit = str(
            (preview_cfg.get("fit") or video_cfg.get("preview_fit") or "cover")
        ).strip().lower()

        with open_video_source(
            source,
            sample_fps=float(video_cfg.sample_fps),
            resize_width=int(video_cfg.resize_width),
            read_timeout_sec=float(video_cfg.read_timeout_sec),
            backend=backend_hint,
            preview_fps=preview_fps if self._on_preview_frame else None,
            preview_callback=self._on_preview_frame,
            capture_width=int(capture_width) if capture_width else None,
            capture_height=int(capture_height) if capture_height else None,
            capture_fps=float(capture_fps) if capture_fps else None,
            frame_preprocess=frame_preprocess if frame_preprocess.get("enabled", True) else None,
            fallback_to_webcam=True,
        ) as fs:
            self._capture_size = getattr(fs, "_capture_size", None)
            pipe.reset_motion()

            # Decouple heavy ML (per-frame CLIP + burst XGBoost) from the camera
            # read/preview loop. If inference ran inline, every burst would pause
            # cap.read() and starve the preview stream (stutters to ~15 FPS). A
            # bounded queue + worker thread keeps the capture loop tight so the
            # MJPEG preview stays at the full preview_fps.
            frame_q: "queue.Queue" = queue.Queue(maxsize=2)
            stop_sentinel = object()
            ml_state = {"last_pred": last_pred}

            def _process_burst(burst) -> None:
                fused = pipe.fusion.fuse(burst)
                feats = fused.as_dict()
                probs = predict_proba_row(self._model, feats)
                if self._live_presence_fixup_enabled:
                    if self._is_bootstrap_model:
                        probs = _bootstrap_live_fixup(probs, feats)
                    else:
                        probs = _live_presence_fixup(probs, feats)
                occupancy = self._occupancy_gate.detect(feats)
                if occupancy.empty:
                    probs = self._occupancy_gate.apply(probs, occupancy)
                elif occupancy.soft_empty:
                    probs = self._occupancy_gate.apply(probs, occupancy)
                if not occupancy.empty:
                    probs = self._activity_hints.apply(probs, feats)
                probs, personalization = self._personalize_probs(feats, probs)
                pred = self._smoother.update(probs)
                ml_state["last_pred"] = pred
                self._after_burst(
                    burst,
                    fused,
                    probs,
                    pred,
                    personalization,
                    occupancy=occupancy,
                )
                pipe.reset_motion()

            def _ml_worker() -> None:
                while True:
                    try:
                        item = frame_q.get(timeout=0.5)
                    except queue.Empty:
                        if self._stop_event.is_set():
                            break
                        continue
                    if item is stop_sentinel:
                        break
                    sf = item
                    try:
                        rec = pipe.frame_to_record(
                            image_bgr=sf.image,
                            frame_index=sf.index,
                            timestamp=sf.timestamp,
                            source=sid,
                        )
                        if self._feedback_model is not None:
                            rec.image_bgr = _feedback_screenshot(sf.image)
                            with self._evidence_lock:
                                self._recent_screenshots.append(rec.image_bgr)
                        with self._frame_lock:
                            self._latest_live_frame_bgr = _feedback_screenshot(sf.image)
                        for burst in agg.push(rec):
                            _process_burst(burst)

                        last_pred = ml_state["last_pred"]
                        if self._overlay and self._on_frame and last_pred is not None:
                            self._on_frame(sf.image, last_pred)
                        if self._show_window and last_pred is not None:
                            import cv2

                            annotated = draw_overlay(
                                sf.image,
                                label=last_pred.label,
                                confidence=last_pred.confidence,
                                probs=last_pred.smoothed_probs,
                                status=f"burst src={source} thr={self._smoother.min_confidence:.2f}",
                            )
                            cv2.imshow("roomos live", annotated)
                            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                                self._stop_event.set()
                    except Exception as e:
                        log.exception("ML worker frame failed: %s", e)

                try:
                    for burst in agg.flush():
                        _process_burst(burst)
                except Exception as e:
                    log.exception("ML worker flush failed: %s", e)

            worker = threading.Thread(
                target=_ml_worker, name="roomos-ml", daemon=True
            )
            worker.start()

            try:
                for sf in fs:
                    if self._stop_event.is_set():
                        break

                    if fs.last_frame_shape:
                        self._preview_frame_shape = tuple(fs.last_frame_shape)

                    if self._first_frame_at is None:
                        self._first_frame_at = time.monotonic()
                        if self._boot_phase in ("starting", "opening_camera"):
                            self._boot_phase = "warming_up"

                    # Hand the sampled frame to the ML worker without ever
                    # blocking the capture loop. If the worker is busy, drop the
                    # oldest queued frame so we always process the freshest one.
                    try:
                        frame_q.put_nowait(sf)
                    except queue.Full:
                        try:
                            frame_q.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            frame_q.put_nowait(sf)
                        except queue.Full:
                            pass
            finally:
                try:
                    frame_q.put_nowait(stop_sentinel)
                except queue.Full:
                    try:
                        frame_q.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        frame_q.put_nowait(stop_sentinel)
                    except queue.Full:
                        pass
                worker.join(timeout=10.0)

        try:
            pipe.close()
        except Exception:
            pass
        log.info("Live inference engine stopped.")

    def _after_burst(
        self,
        burst,
        fused,
        raw_probs: Dict[str, float],
        pred: SmoothedPrediction,
        personalization: dict,
        *,
        occupancy: Optional[OccupancyDecision] = None,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        hist_entry: Dict[str, object] = {"t": now_iso}
        for c in self._ui_classes:
            hist_entry[c] = float(pred.smoothed_probs.get(c, 0.0))
        self._history.append(hist_entry)

        self._snapshot_seq += 1
        if self._first_burst_at is None:
            self._first_burst_at = time.monotonic()
        self._boot_phase = "streaming"
        smoothed = {
            c: float(pred.smoothed_probs.get(c, 0.0)) for c in self._ui_classes
        }
        model_only = {c: float(raw_probs.get(c, 0.0)) for c in self._ui_classes}
        raw_primary_conf = float(model_only.get(pred.label, pred.confidence))
        last_automation: Dict[str, object] = {}
        automation_mode = "off"
        scene = self._scene_for(pred.label)
        actions_dry_run = True
        if self._actions is not None:
            actions_dry_run = bool(self._actions.dry_run)
            try:
                self._actions.on_prediction(
                    label=pred.label,
                    confidence=pred.confidence,
                    at=time.monotonic(),
                )
                if self._actions.last_automation:
                    last_automation = dict(self._actions.last_automation)
                automation_mode = "dry_run" if self._actions.dry_run else "live"
            except Exception as e:
                log.warning("Action engine raised: %s", e)

        if pred.switched and pred.label in self._ui_classes:
            try:
                from ..devices.scene_apply import (
                    apply_preference_scene_async,
                    automation_summary,
                )

                integrations = (
                    dict(self._actions.integrations)
                    if self._actions is not None
                    else {}
                )
                if not integrations and self._actions is None:
                    from ..integrations.device_bridge import merge_runtime_integrations

                    integrations = merge_runtime_integrations({})

                pref_record = asyncio.run(
                    apply_preference_scene_async(
                        scene,
                        dry_run=actions_dry_run,
                        integrations=integrations,
                        room_state=pred.label,
                    )
                )
                if pref_record.get("results") or pref_record.get("would_apply"):
                    last_automation = {
                        "rule": "preference_sync",
                        "activity": pred.label,
                        "action_type": "preference_sync",
                        "dry_run": actions_dry_run,
                        "result": pref_record,
                        "summary": automation_summary(pref_record),
                    }
                    if self._actions is not None:
                        self._actions.last_automation = last_automation
            except Exception as e:
                log.warning("Preference device sync failed: %s", e)

        snap = LiveSnapshot(
            captured_at=now_iso,
            sequence=self._snapshot_seq,
            primary_state=pred.label,
            primary_confidence=raw_primary_conf,
            distribution=smoothed,
            model_probs=model_only,
            rationale=self._rationale(
                fused, pred, raw_probs, personalization, occupancy
            ),
            applied_scene=scene,
            confidence_history=list(self._history),
            personalization=dict(personalization or {}),
            last_automation=last_automation,
            automation_mode=automation_mode,
        )

        with self._evidence_lock:
            self._latest_snapshot = snap

        self._remember_evidence(now_iso, burst, fused, snap, personalization)

        if pred.switched:
            self._record_state_switch(
                pred=pred,
                fused=fused,
                burst=burst,
                snap=snap,
                raw_probs=raw_probs,
                occupancy=occupancy,
            )
        self._previous_displayed_label = pred.label

        if self._log_predictions:
            try:
                append_jsonl(
                    self._pred_log_path,
                    {
                        "t": now_iso,
                        "label": pred.label,
                        "confidence": float(pred.confidence),
                        "raw_probs": raw_probs,
                        "smoothed_probs": pred.smoothed_probs,
                        "burst_start": fused.metadata.get("start_time"),
                        "burst_end": fused.metadata.get("end_time"),
                        "burst_index": fused.metadata.get("burst_index"),
                        "num_frames": fused.metadata.get("num_frames"),
                        "switched": bool(pred.switched),
                        "personalization": personalization,
                    },
                )
            except Exception as e:
                log.debug("Failed to log prediction: %s", e)

        if self._on_snapshot is not None:
            try:
                self._on_snapshot(snap)
            except Exception as e:
                log.warning("Snapshot callback raised: %s", e)

    def _personalize_probs(
        self,
        features: Dict[str, float],
        raw_probs: Dict[str, float],
    ) -> tuple[Dict[str, float], dict]:
        if self._feedback_model is None:
            return raw_probs, {
                "applied": False,
                "examples": 0,
                "memory_examples": 0,
                "nearest_similarity": 0.0,
            }
        try:
            return self._feedback_model.adjust_probabilities(features, raw_probs)
        except Exception as e:
            log.warning("Feedback personalization failed: %s", e)
            return raw_probs, {"applied": False, "error": str(e)}

    def _remember_evidence(self, now_iso: str, burst, fused, snap: LiveSnapshot, personalization: dict) -> None:
        screenshots = [
            f.image_bgr
            for f in getattr(burst, "frames", [])
            if getattr(f, "image_bgr", None) is not None
        ][:5]
        with self._evidence_lock:
            if len(screenshots) < 5:
                screenshots = list(self._recent_screenshots)
            self._latest_evidence = {
                "captured_at": now_iso,
                "features": fused.as_dict(),
                "metadata": dict(fused.metadata),
                "screenshots": screenshots,
                "snapshot": snap,
                "personalization": dict(personalization or {}),
            }

    def evidence_payload(self) -> dict:
        """Metadata for the live snapshot that /live feedback would persist."""
        with self._frame_lock:
            has_frame = self._latest_live_frame_bgr is not None
        if not has_frame:
            return {"available": False, "captureMode": "snapshot"}
        snap = None
        with self._evidence_lock:
            snap = self._latest_snapshot
        primary = ""
        confidence = 0.0
        if isinstance(snap, LiveSnapshot):
            primary = str(snap.primary_state)
            confidence = float(snap.primary_confidence)
        return {
            "available": True,
            "captureMode": "snapshot",
            "capturedAt": snap.captured_at if isinstance(snap, LiveSnapshot) else None,
            "primaryState": primary,
            "confidence": confidence,
            "frameCount": 1,
        }

    def evidence_frame_jpeg(self, frame_index: int) -> Optional[bytes]:
        """1-based JPEG for the live preview frame used by /live feedback."""
        if frame_index != 1:
            return None
        with self._frame_lock:
            frame = None if self._latest_live_frame_bgr is None else self._latest_live_frame_bgr.copy()
        if frame is None:
            return None
        try:
            import cv2

            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            if not ok:
                return None
            return buf.tobytes()
        except Exception as e:
            log.debug("Failed to encode live snapshot frame: %s", e)
            return None

    def feedback_correction_jpeg(self, correction_id: str) -> Optional[bytes]:
        """JPEG from a saved feedback correction folder."""
        if self._feedback_model is None:
            return None
        cid = str(correction_id or "").strip()
        if not cid or "/" in cid or "\\" in cid or ".." in cid:
            return None
        event_dir = self._feedback_model.screenshot_dir / cid
        if not event_dir.is_dir():
            return None
        for name in ("frame_01.jpg", "frame_02.jpg"):
            path = event_dir / name
            if path.is_file():
                try:
                    return path.read_bytes()
                except OSError as e:
                    log.debug("Could not read %s: %s", path, e)
        return None

    def _features_from_snapshot_frame(
        self, image_bgr: np.ndarray
    ) -> tuple[dict[str, float], list[np.ndarray]]:
        """Extract one fused feature row + evidence image from the current video frame."""
        shot = _feedback_screenshot(image_bgr)
        with self._pipe_lock:
            if self._feedback_pipe is None:
                self._feedback_pipe = FeatureExtractionPipeline(self.config)
                self._feedback_pipe.load()
            self._feedback_pipe.reset_motion()
            ts = time.time()
            rec = self._feedback_pipe.frame_to_record(
                image_bgr=image_bgr.copy(),
                frame_index=0,
                timestamp=ts,
                source="live_snapshot",
            )
            burst = FrameBurst(
                start_time=ts,
                end_time=ts,
                source="live_snapshot",
                frames=[rec],
                burst_index=0,
            )
            fused = self._feedback_pipe.fusion.fuse(burst)
        return fused.as_dict(), [shot]

    def record_feedback(
        self,
        *,
        corrected_label: str,
        notes: str = "",
        metadata: Optional[Mapping[str, object]] = None,
    ) -> dict:
        if self._feedback_model is None:
            raise RuntimeError("Feedback personalization is disabled.")

        with self._frame_lock:
            frame = None if self._latest_live_frame_bgr is None else self._latest_live_frame_bgr.copy()
        if frame is None:
            raise RuntimeError("No camera frame available yet — wait for the live preview.")

        with self._evidence_lock:
            snap = self._latest_snapshot
        if not isinstance(snap, LiveSnapshot):
            raise RuntimeError("No live snapshot available yet.")

        features, screenshots = self._features_from_snapshot_frame(frame)
        raw_probs = dict(snap.model_probs) if snap.model_probs else dict(snap.distribution)

        before_probs, before_info = self._feedback_model.adjust_probabilities(features, raw_probs)
        meta: Dict[str, object] = {
            "capture_mode": "snapshot",
            "captured_at": snap.captured_at,
            "personalization": dict(snap.personalization or {}),
        }
        if metadata:
            meta.update(dict(metadata))
        correction = self._feedback_model.record_correction(
            predicted_label=snap.primary_state,
            corrected_label=corrected_label,
            confidence=snap.primary_confidence,
            features=features,
            screenshots_bgr=screenshots,
            notes=notes,
            metadata=meta,
        )
        after_probs, after_info = self._feedback_model.adjust_probabilities(features, raw_probs)
        if correction.predicted_label == correction.corrected_label:
            log.info(
                "Recorded feedback confirmation %s: %s (memory=%d examples)",
                correction.id,
                correction.corrected_label,
                self._feedback_model.count,
            )
        else:
            log.info(
                "Recorded feedback correction %s: %s -> %s (memory=%d examples)",
                correction.id,
                correction.predicted_label,
                correction.corrected_label,
                self._feedback_model.count,
            )
        self._notify_live_snapshot_retrain()
        return {
            "correction": correction,
            "memory_examples": self._feedback_model.count,
            "capture_mode": "snapshot",
            "screenshot_count": len(screenshots),
            "probability_preview": {
                "before": {k: round(float(before_probs.get(k, 0.0)), 4) for k in self._ui_classes},
                "after": {k: round(float(after_probs.get(k, 0.0)), 4) for k in self._ui_classes},
                "corrected_label": corrected_label,
                "applied_after_save": bool(after_info.get("applied")),
                "nearest_similarity": float(after_info.get("nearest_similarity", 0.0)),
            },
            "storage": self._feedback_model.status_payload(),
        }

    def reload_model_bundle(self) -> None:
        """Hot-reload XGBoost after background auto-retrain."""
        self._model = load_model_bundle(self._model_dir)
        smooth_cfg = self.config.smoothing
        unknown_label = str(self.config.labels.get("unknown_class", "unknown"))
        self._smoother = PredictionSmoother(
            classes=list(self._model.classes),
            unknown_label=unknown_label,
            min_confidence=float(smooth_cfg.min_confidence),
            ema_alpha=float(smooth_cfg.prob_ema_alpha),
            confirm_bursts=smoothing_confirm_bursts(smooth_cfg),
            cooldown_sec=float(smooth_cfg.cooldown_sec),
        )
        if self._feedback_model is not None:
            self._feedback_model.feature_columns = list(self._model.feature_columns)
        if self._auto_retrainer is not None:
            self._auto_retrainer._feature_columns = list(self._model.feature_columns)
        log.info("Reloaded model bundle from %s", self._model_dir)

    def _notify_auto_retrain(self) -> None:
        if self._auto_retrainer is not None:
            self._auto_retrainer.notify_correction()

    def _notify_live_snapshot_retrain(self) -> None:
        if self._auto_retrainer is not None:
            self._auto_retrainer.notify_live_snapshot()

    def auto_retrain_status(self) -> dict:
        if self._auto_retrainer is None:
            return {"enabled": False}
        return self._auto_retrainer.status()

    def feedback_status(self) -> dict:
        if self._feedback_model is None:
            payload = {
                "enabled": False,
                "memory_examples": 0,
                "has_evidence": self._latest_evidence is not None,
            }
        else:
            payload = self._feedback_model.status_payload()
            payload["enabled"] = True
            payload["has_evidence"] = self._latest_evidence is not None
        payload["evidence"] = self.evidence_payload()
        if self._transition_journal is not None:
            payload["transitions"] = self._transition_journal.status_payload()
        else:
            payload["transitions"] = {"enabled": False, "total": 0, "pendingReview": 0}
        payload["autoRetrain"] = self.auto_retrain_status()
        return payload

    def list_transitions(
        self,
        *,
        limit: int = 40,
        uncorrected_only: bool = False,
    ) -> List[StateTransition]:
        if self._transition_journal is None:
            return []
        return self._transition_journal.list_transitions(
            limit=limit,
            uncorrected_only=uncorrected_only,
        )

    def transition_screenshot_path(self, transition_id: str, index: int) -> Optional[Path]:
        if self._transition_journal is None:
            return None
        return self._transition_journal.screenshot_path(transition_id, index)

    def record_transition_correction(
        self,
        *,
        transition_id: str,
        corrected_label: str,
        notes: str = "",
    ) -> dict:
        if self._feedback_model is None:
            raise RuntimeError("Feedback personalization is disabled.")
        if self._transition_journal is None:
            raise RuntimeError("Transition journal is disabled.")
        rec = self._transition_journal.get_record(transition_id)
        if not rec:
            raise ValueError(f"Unknown transition id: {transition_id!r}")

        predicted = str(rec.get("to_label", ""))
        if corrected_label not in self._model.classes:
            raise ValueError(f"Unknown corrected label: {corrected_label!r}")

        features = dict(rec.get("features", {}))
        raw_probs = dict(rec.get("raw_probs", {}))
        screenshots = self._transition_journal.load_screenshots_bgr(transition_id)

        before_probs, _ = self._feedback_model.adjust_probabilities(features, raw_probs)
        correction = self._feedback_model.record_correction(
            predicted_label=predicted,
            corrected_label=corrected_label,
            confidence=float(rec.get("confidence", 0.0)),
            features=features,
            screenshots_bgr=screenshots,
            notes=notes,
            metadata={
                "transition_id": transition_id,
                "from_label": rec.get("from_label"),
                "captured_at": rec.get("captured_at"),
            },
        )
        after_probs, after_info = self._feedback_model.adjust_probabilities(features, raw_probs)
        self._transition_journal.mark_corrected(
            transition_id,
            corrected_label=corrected_label,
            correction_id=correction.id,
            notes=notes,
        )
        log.info(
            "Transition %s relabeled: %s -> %s (memory=%d)",
            transition_id[:8],
            predicted,
            corrected_label,
            self._feedback_model.count,
        )
        self._notify_auto_retrain()
        return {
            "correction": correction,
            "transition_id": transition_id,
            "predicted_label": predicted,
            "from_label": rec.get("from_label"),
            "memory_examples": self._feedback_model.count,
            "probability_preview": {
                "before": {k: round(float(before_probs.get(k, 0.0)), 4) for k in self._ui_classes},
                "after": {k: round(float(after_probs.get(k, 0.0)), 4) for k in self._ui_classes},
                "corrected_label": corrected_label,
                "applied_after_save": bool(after_info.get("applied")),
                "nearest_similarity": float(after_info.get("nearest_similarity", 0.0)),
            },
            "storage": self._feedback_model.status_payload(),
        }

    def _record_state_switch(
        self,
        *,
        pred: SmoothedPrediction,
        fused,
        burst,
        snap: LiveSnapshot,
        raw_probs: Dict[str, float],
        occupancy: Optional[OccupancyDecision] = None,
    ) -> None:
        if self._transition_journal is None:
            return
        from_label = self._previous_displayed_label
        to_label = pred.label
        if from_label == to_label:
            return

        screenshots = [
            f.image_bgr
            for f in getattr(burst, "frames", [])
            if getattr(f, "image_bgr", None) is not None
        ][:5]
        if len(screenshots) < 1:
            with self._evidence_lock:
                screenshots = list(self._recent_screenshots)

        rationale = self._rationale(
            fused,
            pred,
            raw_probs,
            snap.personalization,
            occupancy,
        )
        try:
            self._transition_journal.record_switch(
                from_label=from_label,
                to_label=to_label,
                confidence=float(pred.confidence),
                sequence=int(snap.sequence),
                features=fused.as_dict(),
                raw_probs=raw_probs,
                screenshots_bgr=screenshots,
                rationale=rationale,
            )
        except Exception as e:
            log.warning("Failed to record state transition: %s", e)

    def _rationale(
        self,
        fused,
        pred: SmoothedPrediction,
        raw: Dict[str, float],
        personalization: dict,
        occupancy: Optional[OccupancyDecision] = None,
    ) -> List[str]:
        bullets: List[str] = []
        row = fused.as_dict()

        # Pose-based bullets are only meaningful when the pose feature group is
        # actually enabled in the inference config. Otherwise pose_present_ratio
        # is constantly 0 and we'd lie ("no person detected") every burst.
        if self._pose_enabled:
            person = row.get("pose_present_ratio", 0.0)
            if person <= 0.2:
                bullets.append("No clear person detected across the burst.")
            elif person >= 0.8:
                bullets.append("Person visible in most burst frames.")

        # Occupancy gate runs even without pose features (CLIP-based fallback),
        # so add an honest bullet when the gate fires or when CLIP strongly
        # leans "empty room".
        if occupancy is not None:
            if occupancy.empty:
                if occupancy.reason == "empty_pose":
                    bullets.append(
                        "Occupancy gate: no person detected (pose+low motion) — forcing 'away'."
                    )
                elif occupancy.reason in ("empty_clip", "empty_scene"):
                    bullets.append(
                        "Occupancy gate: no person in scene (empty couch/desk/room > person prompts, "
                        f"margin={occupancy.empty_score - occupancy.person_score:+.02f}) — not Work/Studying."
                    )
                else:
                    bullets.append("Occupancy gate: empty scene — forcing 'away'.")
            elif occupancy.soft_empty:
                bullets.append(
                    "Weak person signal — capping Work/Relaxing/Sleep; scene looks unoccupied."
                )
            elif (
                not self._pose_enabled
                and occupancy.empty_score > 0.0
                and (occupancy.empty_score - occupancy.person_score) >= 0.005
            ):
                bullets.append(
                    "CLIP leans slightly toward 'empty room' but gate threshold not met."
                )

        motion = row.get("motion_mean_mean", 0.0)
        if motion <= 0.005:
            bullets.append("Very little motion in the burst.")
        elif motion >= 0.05:
            bullets.append("High motion in the burst.")

        if self._pose_enabled:
            if row.get("posture_lying_ratio", 0.0) > 0.5:
                bullets.append("Posture skews toward lying down.")
            elif row.get("posture_sitting_ratio", 0.0) > 0.5:
                bullets.append("Posture skews toward sitting.")
            elif row.get("posture_standing_ratio", 0.0) > 0.5:
                bullets.append("Posture skews toward standing.")

        top_clip = None
        top_val = -1.0
        for k, v in row.items():
            if k.startswith("clip_sim__") and k.endswith("_mean"):
                if float(v) > top_val:
                    top_val = float(v)
                    top_clip = k
        if top_clip is not None and top_val > 0.18:
            slug = top_clip[len("clip_sim__"): -len("_mean")]
            bullets.append(f"Scene context most similar to '{slug.replace('_', ' ')}'.")

        if pred.label != "unknown":
            sorted_p = sorted(pred.smoothed_probs.items(), key=lambda kv: kv[1], reverse=True)
            if len(sorted_p) >= 2:
                margin = sorted_p[0][1] - sorted_p[1][1]
                if margin < 0.1:
                    bullets.append(
                        f"Close call vs '{sorted_p[1][0]}' (delta={margin:.2f})."
                    )

        mem = int(personalization.get("memory_examples", personalization.get("examples", 0)) or 0)
        if personalization.get("applied"):
            matches = int(personalization.get("matches", 0) or 0)
            boosted = personalization.get("boosted_label")
            sim = float(personalization.get("nearest_similarity", 0.0) or 0.0)
            if boosted:
                bullets.append(
                    f"Room memory ({mem} saved) nudged this burst toward '{boosted}' "
                    f"({matches} similar correction(s), sim={sim:.2f})."
                )
            else:
                bullets.append(
                    f"Room memory adjusted this read ({matches} similar correction(s) in {mem} saved)."
                )
        elif mem > 0:
            bullets.append(f"Room memory has {mem} saved correction(s); none similar enough to this burst yet.")

        return bullets[:5]

    def _scene_for(self, label: str) -> Dict[str, object]:
        defaults = {
            "work":     {"lightColorHex": "#E8F4FF", "brightness": 72, "fanOn": False, "temperatureF": 72},
            "sleep":    {"lightColorHex": "#1E2A4A", "brightness": 8,  "fanOn": True,  "temperatureF": 68},
            "gaming":   {"lightColorHex": "#6D4AFF", "brightness": 80, "fanOn": True,  "temperatureF": 70},
            "relaxing": {"lightColorHex": "#2FB8A8", "brightness": 42, "fanOn": False, "temperatureF": 73},
            "away":     {"lightColorHex": "#2A2A2A", "brightness": 0,  "fanOn": False, "temperatureF": 76},
        }
        if label not in defaults:
            return {"lightColorHex": "#222222", "brightness": 30, "fanOn": False, "temperatureF": 72}
        prefs = self._preference_scene_for(label)
        return prefs if prefs is not None else defaults[label]

    def _preference_scene_for(self, label: str) -> Optional[Dict[str, object]]:
        scenes = self._load_preference_scenes()
        return scenes.get(label)

    def _load_preference_scenes(self) -> dict[str, dict[str, object]]:
        path = self._preferences_path
        try:
            mtime = path.stat().st_mtime if path.exists() else 0.0
        except OSError:
            mtime = 0.0
        cached_mtime, cached = self._preferences_cache
        if mtime == cached_mtime and cached:
            return cached
        if not path.exists():
            self._preferences_cache = (mtime, {})
            return {}
        try:
            doc = read_json(path)
            out = active_preset_preferences(doc)
            self._preferences_cache = (mtime, out)
            return out
        except Exception as e:
            log.debug("Could not load preferences for scene: %s", e)
            self._preferences_cache = (mtime, {})
            return {}


def build_engine(
    config: Config,
    actions_config_path: Optional[str] = None,
    on_snapshot: Optional[SnapshotCallback] = None,
    on_preview_frame: Optional[Callable[[np.ndarray], None]] = None,
) -> LiveInferenceEngine:
    try:
        ac = load_actions_config(actions_config_path)
        actions = ActionEngine.from_config(ac)
    except FileNotFoundError:
        log.info("No actions config found; running without action engine.")
        actions = None
    return LiveInferenceEngine(
        config,
        actions=actions,
        on_snapshot=on_snapshot,
        on_preview_frame=on_preview_frame,
    )


def _trained_model_kind(train_config: dict) -> str:
    """``generic`` = multi-room cold-start; ``personal`` = user's room training."""
    try:
        source = str(train_config.get("_source_config", "")).lower()
        training = train_config.get("training", {}) or {}
        feats = str(training.get("features_path", "")).lower()
        if "train_my_room" in source or "my_room" in feats:
            return "personal"
        if "train_personal" in source or "personal" in feats:
            return "personal"
        if "train_multi_room" in source or "multi_room" in feats:
            return "generic"
        if "bootstrap" in source or "bootstrap" in feats:
            return "bootstrap"
    except Exception:
        pass
    return "trained"


def _is_personal_room_bundle(model: ActivityModel) -> bool:
    """True when the bundle was trained with personal-room row weighting."""
    try:
        source = str((model.train_config or {}).get("_source_config", "")).lower()
        if "train_my_room" in source:
            return True
        training = (model.train_config or {}).get("training", {}) or {}
        if bool(training.get("use_row_weights", False)):
            feats = str(training.get("features_path", "")).lower()
            if "my_room" in feats or "personal" in feats:
                return True
            if float(training.get("default_row_weight", 1.0)) > 1.0:
                return True
            if float(training.get("personal_row_weight", 1.0)) > 1.0:
                return True
    except Exception:
        return False
    return False


def _looks_like_bootstrap_bundle(model: ActivityModel) -> bool:
    """True if this bundle was produced by ``bootstrap_demo_model.py``.

    The bootstrap script writes a ``_source_config`` field with the path to
    ``configs/bootstrap_demo.yaml`` (or any file with ``bootstrap`` in its
    name). Users who run ``train:images`` / ``train:videos`` get a different
    source config so this flag flips off automatically.
    """
    try:
        source = str((model.train_config or {}).get("_source_config", "")).lower()
        if "bootstrap" in source:
            return True
        # Defensive: also flag features files that include "bootstrap".
        training = (model.train_config or {}).get("training", {}) or {}
        feats = str(training.get("features_path", "")).lower()
        if "bootstrap" in feats:
            return True
    except Exception:
        return False
    return False


def _feedback_screenshot(image_bgr: np.ndarray) -> np.ndarray:
    """Return a small evidence copy for user-reported corrections."""
    try:
        import cv2

        h, w = image_bgr.shape[:2]
        if w > 320:
            scale = 320.0 / float(w)
            return cv2.resize(
                image_bgr,
                (320, max(1, int(round(h * scale)))),
                interpolation=cv2.INTER_AREA,
            )
    except Exception:
        pass
    return image_bgr.copy()
