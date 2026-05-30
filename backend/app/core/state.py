"""Process-wide application state.

We keep the long-running ML engine + a single broadcast hub here so any HTTP
route or WebSocket can read the latest snapshot without coupling to startup
order.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Literal, Optional, Set

import numpy as np

from roomos.config import Config, load_config
from roomos.demo.replay import DATA_SOURCE, INFERENCE_SOURCE_LABEL, load_replay_engine
from roomos.demo.readiness import format_missing_model_help, resolve_bundle_dir
from roomos.inference.live_pipeline import LiveInferenceEngine, LiveSnapshot, build_engine
from roomos.model.compat import TrainServeCompatibilityError, gate_live_engine_start
from roomos.model.registry import MODEL_ARTIFACT_FILES
from roomos.utils.logging import get_logger

from .config import settings
from .feedback_events import FeedbackEventHub
from .preferences_events import PreferencesEventHub

log = get_logger("roomos.app.state")

LiveMode = Literal["off", "live", "replay"]


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
    """Async-aware fan-out of LiveSnapshot updates.

    The ML engine pushes synchronously from a background thread; we shuttle
    each update onto the asyncio loop so any number of WebSocket clients can
    subscribe via a queue.
    """

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
        """Called from the ML engine's background thread."""
        self._latest = snap
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._fanout, snap)

    def _fanout(self, snap: LiveSnapshot) -> None:
        """Push the newest snapshot; drop stale queued items (UI only needs latest)."""
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
        self.replay: Optional[object] = None  # DemoReplayEngine
        self.live_mode: LiveMode = "off"
        self.engine_error: Optional[str] = None
        self.engine_compat_report: Optional[dict] = None
        self.inference_source: Optional[str] = None
        self.hub: SnapshotHub = SnapshotHub()
        self.feedback_hub: FeedbackEventHub = FeedbackEventHub()
        self.preferences_hub: PreferencesEventHub = PreferencesEventHub()
        self.preview: PreviewHub = PreviewHub()

    @property
    def is_running(self) -> bool:
        if self.live_mode == "replay":
            return self.replay is not None and self.replay.is_running()
        return self.engine is not None and self.engine.is_running()

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
        max_w = max(320, int(max_width))
        if w > max_w:
            scale = max_w / float(w)
            frame = cv2.resize(
                frame,
                (max_w, max(1, int(round(h * scale)))),
                interpolation=cv2.INTER_LINEAR,
            )
        try:
            mean_luma = float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean())
        except Exception:
            mean_luma = None
        quality = max(50, min(100, int(jpeg_quality)))
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if ok:
            self.preview.push_from_thread(buf.tobytes(), mean_luma=mean_luma)

    def _push_preview_jpeg(self, jpeg: bytes) -> None:
        # Replay pushes pre-encoded JPEGs; luma decoding is unnecessary for the
        # synthetic frames, so mark them as well-lit so the UI doesn't warn.
        self.preview.push_from_thread(jpeg, mean_luma=128.0)

    def _stop_all_engines(self) -> None:
        if self.engine is not None and self.engine.is_running():
            self.engine.stop()
        if self.replay is not None and self.replay.is_running():
            self.replay.stop()
        self.engine = None
        self.replay = None
        self.live_mode = "off"
        self.preview.clear()

    def _resolve_start_mode(self, mode: Optional[str]) -> LiveMode:
        if mode in ("live", "replay"):
            return mode  # type: ignore[return-value]
        default = (settings.roomos_demo_mode or "off").strip().lower()
        if default in ("replay", "demo", "demo-replay"):
            return "replay"
        return "live"

    def start_engine(self, *, mode: Optional[str] = None) -> dict:
        target = self._resolve_start_mode(mode)
        if self.is_running and self.live_mode == target:
            return {
                "status": "already_running",
                "live_mode": self.live_mode,
                "inference_source": self.inference_source,
            }

        self._stop_all_engines()
        self.engine_error = None

        if target == "replay":
            return self._start_replay()
        return self._start_live()

    def _start_replay(self) -> dict:
        try:
            backend = Path(__file__).resolve().parents[2]
            fixture = settings.roomos_demo_fixture
            self.replay = load_replay_engine(
                fixture,
                on_snapshot=self.hub.push_from_thread,
                on_preview_jpeg=self._push_preview_jpeg,
                project_root=backend,
            )
            self.replay.start_background()
            self.live_mode = "replay"
            self.inference_source = INFERENCE_SOURCE_LABEL
            self.engine_compat_report = None
            return {
                "status": "started",
                "live_mode": "replay",
                "inference_source": self.inference_source,
                "demo_fixture": fixture,
                "data_source": DATA_SOURCE,
            }
        except Exception as e:
            self.engine_error = f"Demo replay failed: {e!r}"
            log.exception("Demo replay start failed")
            self._stop_all_engines()
            return {"status": "error", "error": self.engine_error, "live_mode": "off"}

    def _start_live(self) -> dict:
        try:
            cfg = load_config(settings.roomos_config)
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
            return {
                "status": "started",
                "live_mode": "live",
                "config": settings.roomos_config,
                "inference_source": self.inference_source,
                "data_source": "roomos-ml",
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
        """Switch between live camera inference and deterministic demo replay."""
        m = mode.strip().lower()
        if m in ("demo", "demo-replay", "replay"):
            return self.start_engine(mode="replay")
        if m == "live":
            return self.start_engine(mode="live")
        if m == "off":
            return self.stop_engine()
        return {"status": "error", "error": f"Unknown mode: {mode}"}

    def stop_engine(self) -> dict:
        if not self.is_running and self.live_mode == "off":
            return {"status": "not_running", "live_mode": "off"}
        prev = self.live_mode
        self._stop_all_engines()
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
        elif self.live_mode == "replay" and self.hub.latest is not None:
            snap = self.hub.latest
            automation = {
                "mode": snap.automation_mode,
                "dry_run": snap.automation_mode == "dry_run",
                "last": snap.last_automation,
            }

        latest = self.hub.latest

        run_error = (
            getattr(self.engine, "_run_error", None)
            if self.live_mode == "live" and self.engine is not None
            else None
        )
        reported_error = run_error or self.engine_error

        # Engine-derived hints for the UI's boot screen / dark-camera banner.
        boot_phase = "off"
        model_kind = "unknown"
        pose_enabled: Optional[bool] = None
        if self.live_mode == "replay":
            boot_phase = "streaming" if latest is not None else "warming_up"
            model_kind = "replay"
        elif self.live_mode == "live" and self.engine is not None:
            boot_phase = getattr(self.engine, "boot_phase", "starting")
            model_kind = getattr(self.engine, "model_kind", "unknown")
            pose_enabled = getattr(self.engine, "pose_enabled", None)

        preview_fit = "cover"
        preview_frame_shape = None
        capture_size = None
        if self.live_mode == "live" and self.engine is not None:
            preview_fit = getattr(self.engine, "_preview_fit", "cover") or "cover"
            shape = getattr(self.engine, "_preview_frame_shape", None)
            if shape and len(shape) >= 2:
                preview_frame_shape = [int(shape[1]), int(shape[0])]
            cap = getattr(self.engine, "_capture_size", None)
            if cap and len(cap) == 2:
                capture_size = [int(cap[0]), int(cap[1])]

        preview_mean_luma = self.preview.mean_luma
        # Anything below ~10/255 average brightness is effectively black on
        # consumer screens; expose a normalized flag so the UI doesn't have to
        # invent its own threshold.
        preview_dark = (
            preview_mean_luma is not None
            and self.preview.available
            and preview_mean_luma < 10.0
            and self.live_mode == "live"
        )

        return {
            "engine_running": self.is_running,
            "live_mode": self.live_mode,
            "demo_mode": self.live_mode == "replay",
            "demo_replay_active": self.live_mode == "replay",
            "engine_error": reported_error,
            "compat_ok": self.engine_compat_report.get("ok")
            if self.engine_compat_report
            else None,
            "compat_report": self.engine_compat_report,
            "has_snapshot": latest is not None,
            "inference_source": self.inference_source,
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
            "demo_fixture": settings.roomos_demo_fixture
            if self.live_mode == "replay"
            else None,
            "automation": automation,
        }


state = AppState()
