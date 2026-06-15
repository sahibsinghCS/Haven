"""Process-wide application state.

We keep the long-running ML engine + a single broadcast hub here so any HTTP
route or WebSocket can read the latest snapshot without coupling to startup
order.
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Set, Tuple, Union

import numpy as np

from roomos.config import Config, load_config
from roomos.demo.readiness import format_missing_model_help, resolve_bundle_dir
from roomos.inference.live_pipeline import LiveInferenceEngine, LiveSnapshot, build_engine
from roomos.personalization import TransitionJournal
from roomos.model.compat import TrainServeCompatibilityError, gate_live_engine_start
from roomos.model.registry import MODEL_ARTIFACT_FILES
from roomos.utils.logging import get_logger
from roomos.rooms.orchestrator import PresenceOrchestrator
from roomos.rooms.preview_manager import RoomPreviewManager
from roomos.rooms.store import RoomsStore
from roomos.video.input import (
    collect_claimed_droidcam_urls,
    is_auto_video_source,
    is_phone_stream_url,
    list_all_cameras_for_ui,
    list_available_cameras,
    resolve_video_source,
    set_discovery_persist_hook,
    user_camera_error,
)

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
        return f"Webcam {int(source)}"
    s = str(source)
    if is_auto_video_source(s):
        return "Phone camera"
    if s.startswith(("http://", "https://", "rtsp://")):
        if is_phone_stream_url(s):
            return "Phone camera"
        return "Network camera"
    if s.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
        return f"Video file {s}"
    return f"Source {s}"


def _sanitize_camera_error(message: Optional[str]) -> Optional[str]:
    """Map internal capture failures to generic user-facing copy."""
    if not message:
        return message
    lower = message.lower()
    if "droidcam" in lower and "busy" in lower:
        return message
    camera_markers = (
        "camera",
        "video source",
        "videocapture",
        "mjpeg",
        "webcam",
        "droidcam",
        "could not open",
        "no frames",
    )
    if any(m in lower for m in camera_markers):
        return user_camera_error()
    return message


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
        self._cond = threading.Condition()
        self._jpeg: Optional[bytes] = None
        self._mean_luma: Optional[float] = None
        self._frames_seen: int = 0
        self._generation: int = 0

    @property
    def available(self) -> bool:
        with self._cond:
            return self._jpeg is not None

    @property
    def mean_luma(self) -> Optional[float]:
        with self._cond:
            return self._mean_luma

    @property
    def frames_seen(self) -> int:
        with self._cond:
            return self._frames_seen

    def latest_jpeg(self) -> Optional[bytes]:
        with self._cond:
            return self._jpeg

    def push_from_thread(self, jpeg: bytes, mean_luma: Optional[float] = None) -> None:
        with self._cond:
            self._jpeg = jpeg
            if mean_luma is not None:
                self._mean_luma = float(mean_luma)
            self._frames_seen += 1
            self._generation += 1
            self._cond.notify_all()

    def clear(self) -> None:
        with self._cond:
            self._jpeg = None
            self._mean_luma = None
            self._frames_seen = 0

    def wait_for_new_frame(
        self,
        after_generation: int,
        *,
        timeout: float = 1.0,
    ) -> Tuple[Optional[bytes], int]:
        """Block until a frame newer than *after_generation* arrives (or timeout)."""
        deadline = time.monotonic() + max(0.01, float(timeout))
        with self._cond:
            while True:
                if self._jpeg is not None and self._generation > after_generation:
                    return self._jpeg, self._generation
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return self._jpeg, self._generation
                self._cond.wait(timeout=min(0.05, remaining))


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


class _AsyncPreviewEncoder:
    """Resize + JPEG encode off the capture thread to keep preview frames fresh."""

    def __init__(self) -> None:
        self._queue: "queue.Queue[Optional[np.ndarray]]" = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._max_width = 1280
        self._jpeg_quality = 88
        self._inference_room_id: Optional[str] = None
        self._preview: Optional[PreviewHub] = None
        self._room_previews: Optional[RoomPreviewManager] = None
        self._side_hook: Optional[Callable[[np.ndarray], None]] = None

    def bind(
        self,
        *,
        preview: PreviewHub,
        room_previews: RoomPreviewManager,
    ) -> None:
        self._preview = preview
        self._room_previews = room_previews

    def set_side_hook(self, hook: Optional[Callable[[np.ndarray], None]]) -> None:
        """Optional hook (e.g. transition evidence) — runs on the encode worker."""
        self._side_hook = hook

    def ensure_running(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._worker,
            name="preview-encode",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
        thread = self._thread
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=2.0)
        self._thread = None

    def enqueue(
        self,
        image_bgr: np.ndarray,
        *,
        max_width: int,
        jpeg_quality: int,
        inference_room_id: Optional[str],
    ) -> None:
        self._max_width = max_width
        self._jpeg_quality = jpeg_quality
        self._inference_room_id = inference_room_id
        self.ensure_running()
        frame = image_bgr.copy()
        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(frame)
            except queue.Full:
                pass

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if item is None:
                break
            work = item
            hook = self._side_hook
            if hook is not None:
                try:
                    hook(work)
                except Exception as e:
                    log.debug("preview side hook failed: %s", e)
            self._encode_and_push(work)

    def _encode_and_push(self, image_bgr: np.ndarray) -> None:
        preview = self._preview
        if preview is None:
            return
        try:
            import cv2
        except ImportError:
            return
        frame = image_bgr
        h, w = frame.shape[:2]
        max_w = int(self._max_width)
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
        quality = max(50, min(100, int(self._jpeg_quality)))
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            return
        jpeg_bytes = buf.tobytes()
        preview.push_from_thread(jpeg_bytes, mean_luma=mean_luma)
        room_id = self._inference_room_id
        if room_id and self._room_previews is not None:
            self._room_previews.hub.push(room_id, jpeg_bytes, mean_luma=mean_luma)


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
        self._preview_encoder = _AsyncPreviewEncoder()
        self.rooms_store: RoomsStore = RoomsStore()
        self.room_previews: RoomPreviewManager = RoomPreviewManager(
            config_path=settings.roomos_config,
        )
        self.orchestrator: PresenceOrchestrator = PresenceOrchestrator(
            self.rooms_store,
            config_path=settings.roomos_config,
            preview_manager=self.room_previews,
            restart_engine=self.restart_engine_for_room,
            stop_engine=self._orchestrator_stop_engine,
        )
        self._inference_room_id: Optional[str] = None
        active_room = self.rooms_store.document().active_room_id
        active = (
            self.rooms_store.get_room(active_room)
            if active_room
            else None
        )
        if active is not None:
            self.video_source_override = active.camera.source
            self.video_backend_override = active.camera.backend
        else:
            saved_source, saved_backend = _load_camera_prefs()
            self.video_source_override = saved_source
            self.video_backend_override = saved_backend
        self.camera_setup_required: bool = False
        # Persist a DroidCam URL auto-discovered after the phone's IP changed, so
        # subsequent restarts connect instantly instead of re-scanning the LAN.
        set_discovery_persist_hook(self._on_droidcam_rediscovered)
        self._preview_encoder.bind(
            preview=self.preview,
            room_previews=self.room_previews,
        )

    def preview_mjpeg_fps(self) -> float:
        try:
            cfg = load_config(settings.roomos_config)
            video_cfg = cfg.video or {}
            preview_cfg = video_cfg.get("preview", {}) or {}
            return max(
                1.0,
                float(
                    preview_cfg.get("max_fps", video_cfg.get("preview_max_fps", 30))
                ),
            )
        except Exception:
            return 30.0

    def room_preview_mjpeg_fps(self) -> float:
        try:
            cfg = load_config(settings.roomos_config)
            video_cfg = cfg.video or {}
            room_cfg = video_cfg.get("room_preview", {}) or {}
            return max(
                0.5,
                float(room_cfg.get("max_fps", 1.5)),
            )
        except Exception:
            return 1.5

    def transition_journal(self) -> Optional[TransitionJournal]:
        """Disk-backed switch history — available even when live inference is off."""
        if self.engine is not None:
            journal = getattr(self.engine, "_transition_journal", None)
            if journal is not None:
                return journal
        cfg = load_config(settings.roomos_config)
        infer_cfg = dict(cfg.get("inference", {}) or {})
        transitions_cfg = dict(infer_cfg.get("transitions", {}) or {})
        if not bool(transitions_cfg.get("enabled", True)):
            return None
        transitions_dir = Path(transitions_cfg.get("dir", "data/transitions"))
        if not transitions_dir.is_absolute():
            transitions_dir = cfg.resolve_path(transitions_dir)
        return TransitionJournal(
            root_dir=transitions_dir,
            max_entries=int(transitions_cfg.get("max_entries", 200)),
        )

    def _on_droidcam_rediscovered(self, url: str) -> None:
        self.video_source_override = url
        try:
            _save_camera_prefs(url, self.video_backend_override or "auto")
            active_id = self.rooms_store.active_room_id()
            if active_id:
                self.rooms_store.update_room(
                    active_id,
                    source=url,
                    backend=self.video_backend_override or "auto",
                )
            log.info("Saved rediscovered DroidCam URL to camera selection: %s", url)
        except OSError as e:
            log.debug("Could not persist rediscovered camera URL: %s", e)

    def _orchestrator_stop_engine(self) -> None:
        self.stop_engine()

    def restart_engine_for_room(self, room_id: str) -> None:
        try:
            source, backend = self.orchestrator.camera_for_room(room_id)
        except ValueError:
            return
        self._inference_room_id = room_id
        self.orchestrator.set_inference_room(room_id)
        self.video_source_override = source
        self.video_backend_override = backend
        self.rooms_store.set_active_room_id(room_id)
        if self.live_mode == "live":
            self._stop_engine()
            self._start_live()
        else:
            self.orchestrator.sync_previews()

    def rooms_status(self) -> dict[str, Any]:
        return self.orchestrator.status_payload()

    def room_preview_jpeg(self, room_id: str) -> Optional[bytes]:
        if (
            self._inference_room_id == room_id
            and self.preview.available
        ):
            data = self.preview.latest_jpeg()
            if data is not None:
                return data
        return self.room_previews.hub.latest_jpeg(room_id)

    def _on_engine_snapshot(self, snap: LiveSnapshot) -> None:
        room_id = self._inference_room_id
        if room_id:
            snap.room_id = room_id
            snap.orchestrator_mode = self.orchestrator.mode
            snap.active_room_id = self.orchestrator.active_room_id
            self.orchestrator.handle_snapshot(room_id, snap)
        self.hub.push_from_thread(snap)

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

    def _droidcam_exclude_for_room(self, room_id: Optional[str]) -> set[str]:
        if not room_id:
            return set()
        return collect_claimed_droidcam_urls(
            self.rooms_store.list_rooms(),
            skip_room_id=room_id,
        )

    def _apply_video_overrides(self, cfg: Config) -> Config:
        source, backend = self._effective_video_config(cfg)
        exclude = self._droidcam_exclude_for_room(self._inference_room_id)
        resolved = resolve_video_source(
            source, backend=backend, exclude_urls=exclude
        )
        # NOTE: ``cfg.video`` returns a *fresh copy* on every attribute access
        # (Config.__getattr__ -> _wrap -> new _AttrDict), so assigning to
        # ``cfg.video.source`` would mutate a throwaway and never reach the
        # engine. Write straight into the backing dict so build_engine sees it.
        video = cfg.raw.setdefault("video", {})
        if resolved.unresolved:
            video["source"] = source
            video["backend"] = backend
        else:
            video["source"] = resolved.source
            video["backend"] = resolved.backend
        return cfg

    def _assigned_camera_sources(self, *, skip_room_id: Optional[str] = None) -> set[str]:
        """Picker entries already taken by other rooms (not ``droidcam:auto``)."""
        exclude: set[str] = set(collect_claimed_droidcam_urls(
            self.rooms_store.list_rooms(),
            skip_room_id=skip_room_id,
        ))
        for room in self.rooms_store.list_rooms():
            if skip_room_id and room.id == skip_room_id:
                continue
            src = room.camera.source
            if isinstance(src, int) or (isinstance(src, str) and str(src).isdigit()):
                exclude.add(str(src))
            elif isinstance(src, str) and not is_auto_video_source(src):
                exclude.add(str(src))
        return exclude

    def list_cameras(
        self,
        *,
        max_index: int = 6,
        exclude_room_id: Optional[str] = None,
        for_new_room: bool = False,
    ) -> dict[str, Any]:
        exclude = (
            self._assigned_camera_sources(skip_room_id=exclude_room_id)
            if for_new_room or exclude_room_id
            else set()
        )
        cameras = list_all_cameras_for_ui(
            max_index=max_index,
            exclude_sources=exclude,
            include_droidcam_scan=True,
        )
        cfg = load_config(settings.roomos_config)
        current_source, current_backend = self._effective_video_config(cfg)
        resolved = resolve_video_source(current_source, backend=current_backend)
        current_label = (
            "Not connected"
            if resolved.unresolved
            else describe_video_source(self._apply_video_overrides(cfg))
        )
        effective_source = resolved.source if not resolved.unresolved else current_source
        for cam in cameras:
            if cam.get("source") == effective_source:
                current_label = str(cam.get("label") or current_label)
                break
            if (
                isinstance(effective_source, str)
                and cam.get("source") == effective_source
            ):
                current_label = str(cam.get("label") or current_label)
                break
        return {
            "cameras": cameras,
            "current": {
                "source": effective_source,
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
        pending_setup = self.camera_setup_required
        self.video_source_override = source
        self.video_backend_override = backend_hint
        self.camera_setup_required = False
        _save_camera_prefs(source, backend_hint)
        active_id = self.rooms_store.active_room_id()
        if active_id:
            try:
                self.rooms_store.update_room(
                    active_id, source=source, backend=backend_hint
                )
            except ValueError:
                pass
        log.info("Video source set to %r (backend=%s)", source, backend_hint)
        was_live = self.live_mode == "live" and self.is_running
        if was_live or pending_setup:
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
        self._preview_encoder.enqueue(
            image_bgr,
            max_width=max_width,
            jpeg_quality=jpeg_quality,
            inference_room_id=self._inference_room_id,
        )

    def _stop_engine(self) -> None:
        if self.engine is not None and self.engine.is_running():
            self.engine.stop()
        self._preview_encoder.stop()
        self._preview_encoder.set_side_hook(None)
        self.engine = None
        self.live_mode = "off"
        self.preview.clear()
        self._inference_room_id = None

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
        self.camera_setup_required = False
        return self._start_live()

    def _start_live(self) -> dict:
        try:
            doc = self.rooms_store.document()
            enabled = doc.enabled_rooms()
            if not enabled:
                self.camera_setup_required = True
                return {
                    "status": "camera_setup_required",
                    "live_mode": "off",
                    "camera_setup_required": True,
                    "detail": "Add at least one enabled room with a camera.",
                }
            active_id = doc.active_room_id
            if active_id is None or doc.room_by_id(active_id) is None:
                active_id = enabled[0].id
                self.rooms_store.set_active_room_id(active_id)
            active_room = doc.room_by_id(active_id)
            if active_room is not None:
                self.video_source_override = active_room.camera.source
                self.video_backend_override = active_room.camera.backend
                self._inference_room_id = active_id

            cfg = load_config(settings.roomos_config)
            raw_source, raw_backend = self._effective_video_config(cfg)
            exclude = self._droidcam_exclude_for_room(self._inference_room_id)
            resolved = resolve_video_source(
                raw_source, backend=raw_backend, exclude_urls=exclude
            )
            if resolved.unresolved:
                self.camera_setup_required = True
                self.live_mode = "off"
                self.engine = None
                self.engine_error = None
                self.inference_source = None
                log.info("No camera resolved for %r — waiting for user setup", raw_source)
                return {
                    "status": "camera_setup_required",
                    "live_mode": "off",
                    "camera_setup_required": True,
                }

            self.camera_setup_required = False
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

            def _preview_side_hook(frame_bgr: np.ndarray) -> None:
                engine.push_evidence_from_preview(frame_bgr)

            engine = build_engine(
                cfg,
                actions_config_path=settings.roomos_actions_config,
                on_snapshot=self._on_engine_snapshot,
                on_preview_frame=_preview_frame,
            )
            engine.orchestrator_managed = True
            engine.inference_room_id = self._inference_room_id
            # Gallery preview threads may already hold DroidCam HTTP while live is off.
            self.orchestrator.set_inference_room(self._inference_room_id)
            self.room_previews.stop_all()
            engine.start_background()
            self.engine = engine
            self._preview_encoder.set_side_hook(_preview_side_hook)
            self.live_mode = "live"
            self.orchestrator.on_live_started()
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
        self.orchestrator.on_live_stopped()
        self._stop_engine()
        self.camera_setup_required = False
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
        reported_error = _sanitize_camera_error(run_error or self.engine_error)

        boot_phase = "off"
        if self.camera_setup_required:
            boot_phase = "camera_setup"
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

        rooms_status = self.orchestrator.status_payload()

        device_actions: list = []
        try:
            from roomos.devices.action_arbiter import get_arbiter

            device_actions = get_arbiter().recent_decisions(limit=15)
        except Exception:
            pass

        return {
            "engine_running": self.is_running,
            "live_mode": self.live_mode,
            "camera_setup_required": self.camera_setup_required,
            "orchestratorMode": rooms_status.get("orchestratorMode"),
            "activeRoomId": rooms_status.get("activeRoomId"),
            "rooms": rooms_status.get("rooms"),
            "graceDurationSec": rooms_status.get("graceDurationSec"),
            "graceRemainingSec": rooms_status.get("graceRemainingSec"),
            "inferenceRoomId": self._inference_room_id,
            "deviceActions": device_actions,
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
