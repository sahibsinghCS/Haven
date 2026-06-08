"""Process-wide application state.

We keep the long-running ML engine + a single broadcast hub here so any HTTP
route or WebSocket can read the latest snapshot without coupling to startup
order.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any, Literal, Optional, Set, Union

import numpy as np

from roomos.config import Config, load_config
from roomos.demo.readiness import format_missing_model_help, resolve_bundle_dir
from roomos.inference.live_pipeline import LiveInferenceEngine, LiveSnapshot, build_engine
from roomos.model.compat import TrainServeCompatibilityError, gate_live_engine_start
from roomos.model.registry import MODEL_ARTIFACT_FILES
from roomos.utils.logging import get_logger
from roomos.video.input import list_available_cameras

from .config import settings
from .feedback_events import FeedbackEventHub
from .preferences_events import PreferencesEventHub

log = get_logger("roomos.app.state")

LiveMode = Literal["off", "live"]

VideoSourceLike = Union[int, str]

_CAMERA_PREFS_PATH = Path(__file__).resolve().parents[2] / "data" / "camera_selection.json"


def describe_video_source(cfg: Config) -> str:
    """Human-readable label for the OpenCV source the inference engine uses."""
    source = cfg.video.source
    if isinstance(source, int) or (isinstance(source, str) and str(source).isdigit()):
        return f"Webcam index {int(source)} (RoomOS / OpenCV)"
    s = str(source)
    if s == "droidcam:auto":
        return "DroidCam auto-detect (RoomOS / OpenCV)"
    if s.startswith("http://") or s.startswith("https://"):
        return f"Network camera {s}"
    if s.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
        return f"Video file {s}"
    return f"Source {s}"


def _load_camera_prefs() -> tuple[Optional[VideoSourceLike], Optional[str]]:
    if not _CAMERA_PREFS_PATH.is_file():
        return None, None
    try:
        data = json.loads(_CAMERA_PREFS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("Could not read %s: %s", _CAMERA_PREFS_PATH, e)
        return None, None
    source = data.get("source")
    if isinstance(source, str) and source.isdigit():
        source = int(source)
    backend = data.get("backend")
    return source, str(backend) if backend else None


def _save_camera_prefs(source: VideoSourceLike, backend: str) -> None:
    _CAMERA_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": source, "backend": backend}
    _CAMERA_PREFS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class PreviewHub:
    """Latest JPEG frame from the inference camera (thread-safe).

    Also tracks the mean luma of the most-recent frame and how many frames have
    been seen, so the API can warn the UI when the camera is producing
    near-black frames (a classic Windows MSMF symptom).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jpeg: Optional[bytes] = None
        self._mean_luma: Optional[float] = None
        self._frames_seen: int = 0

    @property
    def available(self) -> bool:
        with self._lock:
            return self._jpeg is not None

    @property
    def mean_luma(self) -> Optional[float]:
        with self._lock:
            return self._mean_luma

    @property
    def frames_seen(self) -> int:
        with self._lock:
            return self._frames_seen

    def latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._jpeg

    def push_from_thread(self, jpeg: bytes, mean_luma: Optional[float] = None) -> None:
        with self._lock:
            self._jpeg = jpeg
            if mean_luma is not None:
                self._mean_luma = float(mean_luma)
            self._frames_seen += 1

    def clear(self) -> None:
        with self._lock:
            self._jpeg = None
            self._mean_luma = None
            self._frames_seen = 0


class SnapshotHub:
    """Async-aware fan-out of LiveSnapshot updates."""

    def __init__(self) -> None:
        self._latest: Optional[LiveSnapshot] = None
        self._subscribers: Set[asyncio.Queue] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = asyncio.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def latest(self) -> Optional[LiveSnapshot]:
        return self._latest

    def push_from_thread(self, snap: LiveSnapshot) -> None:
        self._latest = snap
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._fanout, snap)

    def _fanout(self, snap: LiveSnapshot) -> None:
        for q in list(self._subscribers):
            try:
                while not q.empty():
                    q.get_nowait()
                q.put_nowait(snap)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(snap)
                except Exception:
                    pass

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1)
        self._subscribers.add(q)
        if self._latest is not None:
            try:
                q.put_nowait(self._latest)
            except asyncio.QueueFull:
                pass
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)


class AppState:
    def __init__(self) -> None:
        self.engine: Optional[LiveInferenceEngine] = None
        self.live_mode: LiveMode = "off"
        self.engine_error: Optional[str] = None
        self.engine_compat_report: Optional[dict] = None
        self.inference_source: Optional[str] = None
        self.hub: SnapshotHub = SnapshotHub()
        self.feedback_hub: FeedbackEventHub = FeedbackEventHub()
        self.preferences_hub: PreferencesEventHub = PreferencesEventHub()
        self.preview: PreviewHub = PreviewHub()
        saved_source, saved_backend = _load_camera_prefs()
        self.video_source_override: Optional[VideoSourceLike] = saved_source
        self.video_backend_override: Optional[str] = saved_backend

    @property
    def is_running(self) -> bool:
        return self.engine is not None and self.engine.is_running()

    def _effective_video_config(self, cfg: Config) -> tuple[VideoSourceLike, str]:
        source = (
            self.video_source_override
            if self.video_source_override is not None
            else cfg.video.source
        )
        backend = (
            self.video_backend_override
            if self.video_backend_override is not None
            else str(cfg.video.get("backend", "auto") or "auto")
        )
        return source, backend

    def _apply_video_overrides(self, cfg: Config) -> Config:
        source, backend = self._effective_video_config(cfg)
        cfg.video.source = source
        cfg.video.backend = backend
        return cfg

    def list_cameras(self, *, max_index: int = 6) -> dict[str, Any]:
        cameras = list_available_cameras(max_index=max_index)
        cfg = load_config(settings.roomos_config)
        cfg = self._apply_video_overrides(cfg)
        current_source, current_backend = self._effective_video_config(cfg)
        current_label = describe_video_source(cfg)
        for cam in cameras:
            if cam.get("source") == current_source:
                current_label = str(cam.get("label") or current_label)
                break
        return {
            "cameras": cameras,
            "current": {
                "source": current_source,
                "backend": current_backend,
                "label": current_label,
            },
        }

    def set_video_source(
        self,
        source: VideoSourceLike,
        *,
        backend: Optional[str] = None,
    ) -> dict[str, Any]:
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        backend_hint = (backend or self.video_backend_override or "auto").strip().lower()
        self.video_source_override = source
        self.video_backend_override = backend_hint
        _save_camera_prefs(source, backend_hint)
        log.info("Video source set to %r (backend=%s)", source, backend_hint)
        was_live = self.live_mode == "live" and self.is_running
        if was_live:
            result = self.start_engine(mode="live")
            result["engine_restarted"] = True
            return result
        cfg = load_config(settings.roomos_config)
        self.inference_source = describe_video_source(self._apply_video_overrides(cfg))
        return {
            "status": "updated",
            "source": source,
            "backend": backend_hint,
            "inference_source": self.inference_source,
            "engine_restarted": False,
        }

    def _push_preview_frame(
        self,
        image_bgr: np.ndarray,
        *,
        max_width: int = 1280,
        jpeg_quality: int = 88,
    ) -> None:
        try:
            import cv2
        except ImportError:
            return
        frame = image_bgr
        h, w = frame.shape[:2]
        max_w = int(max_width)
        if max_w > 0 and w > max_w:
            scale = max_w / float(w)
            frame = cv2.resize(
                frame,
                (max_w, max(1, int(round(h * scale)))),
                interpolation=cv2.INTER_AREA,
            )
        try:
            mean_luma = float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean())
        except Exception:
            mean_luma = None
        quality = max(50, min(100, int(jpeg_quality)))
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if ok:
            self.preview.push_from_thread(buf.tobytes(), mean_luma=mean_luma)

    def _stop_engine(self) -> None:
        if self.engine is not None and self.engine.is_running():
            self.engine.stop()
        self.engine = None
        self.live_mode = "off"
        self.preview.clear()

    def start_engine(self, *, mode: Optional[str] = None) -> dict:
        target: LiveMode = "live"
        if mode == "off":
            return self.stop_engine()

        if self.is_running and self.live_mode == "live":
            return {
                "status": "already_running",
                "live_mode": self.live_mode,
                "inference_source": self.inference_source,
            }

        self._stop_engine()
        self.engine_error = None
        return self._start_live()

    def _start_live(self) -> dict:
        try:
            cfg = load_config(settings.roomos_config)
            cfg = self._apply_video_overrides(cfg)
            bundle_dir = resolve_bundle_dir(cfg)
            missing = [n for n in MODEL_ARTIFACT_FILES if not (bundle_dir / n).exists()]
            if missing:
                self.engine_compat_report = None
                self.engine_error = format_missing_model_help(bundle_dir=bundle_dir)
                log.error(self.engine_error)
                return {"status": "error", "error": self.engine_error, "live_mode": "off"}

            self.inference_source = describe_video_source(cfg)
            compat = gate_live_engine_start(
                cfg,
                inference_config_path=settings.roomos_config,
            )
            self.engine_compat_report = compat.to_dict()
            log.info(
                "Train/serve compatibility OK (bundle=%s, %d feature columns)",
                compat.bundle_dir,
                compat.n_bundle_columns,
            )
            video_cfg = cfg.video
            preview_cfg = video_cfg.get("preview", {}) or {}
            preview_max_w = int(
                preview_cfg.get("max_width", video_cfg.get("preview_max_width", 1280))
            )
            preview_quality = int(
                preview_cfg.get("jpeg_quality", video_cfg.get("preview_jpeg_quality", 88))
            )

            def _preview_frame(image_bgr: np.ndarray) -> None:
                self._push_preview_frame(
                    image_bgr,
                    max_width=preview_max_w,
                    jpeg_quality=preview_quality,
                )

            engine = build_engine(
                cfg,
                actions_config_path=settings.roomos_actions_config,
                on_snapshot=self.hub.push_from_thread,
                on_preview_frame=_preview_frame,
            )
            engine.start_background()
            self.engine = engine
            self.live_mode = "live"
            self.engine_error = None
            src, bkd = self._effective_video_config(cfg)
            return {
                "status": "started",
                "live_mode": "live",
                "config": settings.roomos_config,
                "inference_source": self.inference_source,
                "data_source": "roomos-ml",
                "video_source": src,
                "video_backend": bkd,
            }
        except TrainServeCompatibilityError as e:
            self.engine_compat_report = e.report.to_dict() if e.report else None
            self.engine_error = str(e)
            log.error("Train/serve compatibility gate failed:\n%s", self.engine_error)
            return {
                "status": "error",
                "error": self.engine_error,
                "compat": self.engine_compat_report,
                "live_mode": "off",
            }
        except FileNotFoundError as e:
            self.engine_compat_report = None
            self.engine_error = (
                f"Could not start engine: model bundle missing ({e}). "
                "Train a model first: npm run setup:model (from repo root)."
            )
            log.warning(self.engine_error)
            return {"status": "error", "error": self.engine_error, "live_mode": "off"}
        except Exception as e:
            self.engine_compat_report = None
            self.engine_error = f"Engine start failed: {e!r}"
            log.exception("Engine start failed")
            return {"status": "error", "error": self.engine_error, "live_mode": "off"}

    def set_live_mode(self, mode: str) -> dict:
        """Start or stop live camera inference."""
        m = mode.strip().lower()
        if m == "live":
            return self.start_engine(mode="live")
        if m == "off":
            return self.stop_engine()
        return {"status": "error", "error": f"Unknown mode: {mode}"}

    def stop_engine(self) -> dict:
        if not self.is_running and self.live_mode == "off":
            return {"status": "not_running", "live_mode": "off"}
        prev = self.live_mode
        self._stop_engine()
        return {"status": "stopped", "live_mode": "off", "previous_mode": prev}

    def status_payload(self) -> dict:
        automation: dict = {"mode": "off"}
        if self.live_mode == "live" and self.engine is not None:
            actions = getattr(self.engine, "_actions", None)
            if actions is not None:
                automation = {
                    "mode": "dry_run" if actions.dry_run else "live",
                    "dry_run": bool(actions.dry_run),
                    "last": actions.last_automation,
                    "ha_enabled": bool(
                        (actions.integrations.get("home_assistant") or {}).get("enabled")
                    ),
                }

        latest = self.hub.latest

        run_error = (
            getattr(self.engine, "_run_error", None)
            if self.live_mode == "live" and self.engine is not None
            else None
        )
        reported_error = run_error or self.engine_error

        boot_phase = "off"
        model_kind = "unknown"
        pose_enabled: Optional[bool] = None
        if self.live_mode == "live" and self.engine is not None:
            boot_phase = getattr(self.engine, "boot_phase", "starting")
            model_kind = getattr(self.engine, "model_kind", "unknown")
            pose_enabled = getattr(self.engine, "pose_enabled", None)

        preview_fit = "cover"
        preview_frame_shape = None
        capture_size = None
        video_source: Optional[VideoSourceLike] = None
        video_backend: Optional[str] = None
        if self.live_mode == "live" and self.engine is not None:
            preview_fit = getattr(self.engine, "_preview_fit", "cover") or "cover"
            shape = getattr(self.engine, "_preview_frame_shape", None)
            if shape and len(shape) >= 2:
                preview_frame_shape = [int(shape[1]), int(shape[0])]
            cap = getattr(self.engine, "_capture_size", None)
            if cap and len(cap) == 2:
                capture_size = [int(cap[0]), int(cap[1])]
            try:
                cfg = load_config(settings.roomos_config)
                video_source, video_backend = self._effective_video_config(cfg)
            except Exception:
                pass

        preview_mean_luma = self.preview.mean_luma
        preview_dark = (
            preview_mean_luma is not None
            and self.preview.available
            and preview_mean_luma < 10.0
            and self.live_mode == "live"
        )

        return {
            "engine_running": self.is_running,
            "live_mode": self.live_mode,
            "engine_error": reported_error,
            "compat_ok": self.engine_compat_report.get("ok")
            if self.engine_compat_report
            else None,
            "compat_report": self.engine_compat_report,
            "has_snapshot": latest is not None,
            "inference_source": self.inference_source,
            "video_source": video_source,
            "video_backend": video_backend,
            "preview_available": self.preview.available,
            "preview_is_inference_feed": self.live_mode == "live",
            "preview_mean_luma": preview_mean_luma,
            "preview_dark": preview_dark,
            "preview_frames_seen": self.preview.frames_seen,
            "preview_fit": preview_fit,
            "preview_frame_shape": preview_frame_shape,
            "capture_size": capture_size,
            "boot_phase": boot_phase,
            "model_kind": model_kind,
            "pose_enabled": pose_enabled,
            "data_source": latest.data_source if latest else None,
            "automation": automation,
        }


state = AppState()
