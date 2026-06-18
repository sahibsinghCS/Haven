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
from typing import Any, Callable, Literal, NamedTuple, Optional, Set, Tuple, Union

import numpy as np

from roomos.config import Config, load_config
from roomos.demo.readiness import format_missing_model_help, resolve_bundle_dir
from roomos.inference.live_pipeline import LiveInferenceEngine, LiveSnapshot, build_engine
from roomos.personalization import TransitionJournal
from roomos.model.compat import TrainServeCompatibilityError, gate_live_engine_start
from roomos.model.registry import MODEL_ARTIFACT_FILES
from roomos.utils.logging import get_logger
from roomos.rooms.models import RoomRecord
from roomos.rooms.orchestrator import PresenceOrchestrator
from roomos.rooms.preview_manager import RoomPreviewManager
from roomos.rooms.store import RoomsStore
from roomos.video.input import (
    _is_remote_video_source,
    collect_claimed_droidcam_urls,
    is_auto_video_source,
    is_phone_stream_url,
    list_all_cameras_for_ui,
    list_available_cameras,
    resolve_video_source,
    set_discovery_persist_hook,
    user_camera_error,
    validate_camera_source,
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


class _PreviewEncodeJob(NamedTuple):
    room_id: Optional[str]
    frame: np.ndarray
    max_width: int
    jpeg_quality: int
    push_main_preview: bool


class _AsyncPreviewEncoder:
    """Resize + JPEG encode off the capture thread to keep preview frames fresh."""

    def __init__(self) -> None:
        self._queue: "queue.Queue[Optional[_PreviewEncodeJob]]" = queue.Queue(maxsize=4)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
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
        room_id: Optional[str],
        max_width: int,
        jpeg_quality: int,
        push_main_preview: bool = False,
    ) -> None:
        self.ensure_running()
        job = _PreviewEncodeJob(
            room_id=room_id,
            frame=image_bgr.copy(),
            max_width=max_width,
            jpeg_quality=jpeg_quality,
            push_main_preview=push_main_preview,
        )
        try:
            self._queue.put_nowait(job)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(job)
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
            hook = self._side_hook
            self._encode_and_push(item)
            if hook is not None:
                try:
                    hook(item.frame)
                except Exception as e:
                    log.debug("preview side hook failed: %s", e)

    def _encode_and_push(self, job: _PreviewEncodeJob) -> None:
        preview = self._preview
        if preview is None:
            return
        try:
            import cv2
        except ImportError:
            return
        frame = job.frame
        h, w = frame.shape[:2]
        max_w = int(job.max_width)
        if max_w > 0 and w > max_w:
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
        quality = max(50, min(100, int(job.jpeg_quality)))
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            return
        jpeg_bytes = buf.tobytes()
        if job.room_id and self._room_previews is not None:
            self._room_previews.hub.push(job.room_id, jpeg_bytes, mean_luma=mean_luma)
        if job.push_main_preview and preview is not None:
            preview.push_from_thread(jpeg_bytes, mean_luma=mean_luma)


class AppState:
    def __init__(self) -> None:
        self._room_engines: dict[str, LiveInferenceEngine] = {}
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
            on_active_room_changed=self._on_orchestrator_active_room_changed,
            on_mode_changed=self._on_orchestrator_mode_changed,
        )
        self._inference_room_id: Optional[str] = None
        self._preview_max_w: int = 1280
        self._preview_quality: int = 88
        self._last_ml_rooms: set[str] = set()
        self._snapshot_lock = threading.RLock()
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
        self._usb_probe_cache: Optional[list[dict[str, Any]]] = None
        # Persist a DroidCam URL auto-discovered after the phone's IP changed, so
        # subsequent restarts connect instantly instead of re-scanning the LAN.
        set_discovery_persist_hook(self._on_droidcam_rediscovered)
        self._preview_encoder.bind(
            preview=self.preview,
            room_previews=self.room_previews,
        )

    @property
    def engine(self) -> Optional[LiveInferenceEngine]:
        """Primary engine for the active room (feedback, transitions, status)."""
        active_id = self.orchestrator.active_room_id or self._inference_room_id
        if active_id and active_id in self._room_engines:
            return self._room_engines[active_id]
        if self._room_engines:
            return next(iter(self._room_engines.values()))
        return None

    def _on_orchestrator_active_room_changed(self, room_id: str) -> None:
        self._inference_room_id = room_id
        active = self.rooms_store.get_room(room_id)
        if active is not None:
            self.video_source_override = active.camera.source
            self.video_backend_override = active.camera.backend
            self.inference_source = describe_video_source(
                self._apply_video_overrides_for_room(
                    load_config(settings.roomos_config),
                    active,
                )
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

    def _on_orchestrator_mode_changed(self, mode: str) -> None:
        if self.live_mode != "live":
            return
        self._ensure_room_engines()

    def _handoff_preview_to_ml(
        self,
        room: RoomRecord,
        *,
        preview_max_w: int,
        preview_quality: int,
    ) -> Optional[LiveInferenceEngine]:
        """Release the preview HTTP client so ML can open the same DroidCam URL."""
        room_id = room.id
        if room_id in self._room_engines:
            return self._room_engines[room_id]
        had_preview = self.room_previews.has_preview_thread(room_id)
        if had_preview:
            self.room_previews.stop_room(room_id, clear_hub=False)
        eng = self._start_room_engine(
            room,
            preview_max_w=preview_max_w,
            preview_quality=preview_quality,
        )
        if eng is None and had_preview:
            log.warning(
                "ML handoff failed for room %s — restoring preview thread",
                room.name,
            )
            self.room_previews.sync_rooms(self.rooms_store.document().rooms)
        return eng

    def _ensure_room_engines(self) -> None:
        """Keep ML on every enabled room while live — never tear down on mode/focus switches."""
        if self.live_mode != "live":
            self.orchestrator.sync_previews()
            return

        doc = self.rooms_store.document()
        enabled = doc.enabled_rooms()
        active_id = doc.active_room_id or self._inference_room_id
        preview_max_w = getattr(self, "_preview_max_w", 1280)
        preview_quality = getattr(self, "_preview_quality", 88)
        enabled_ids = {room.id for room in enabled}
        prev_ml = set(self._last_ml_rooms)
        engines_changed = False

        for rid in list(self._room_engines.keys()):
            if rid not in enabled_ids:
                self._stop_room_engine(rid)
                engines_changed = True

        for room in enabled:
            existing = self._room_engines.get(room.id)
            if existing is not None and not existing.is_running():
                log.warning(
                    "Room %s engine stopped unexpectedly — restarting",
                    room.name,
                )
                self._room_engines.pop(room.id, None)
                engines_changed = True
            if room.id not in self._room_engines:
                if self._handoff_preview_to_ml(
                    room,
                    preview_max_w=preview_max_w,
                    preview_quality=preview_quality,
                ):
                    engines_changed = True

        ml_rooms = set(self._room_engines.keys())
        self._last_ml_rooms = ml_rooms
        self.orchestrator.set_inference_rooms(ml_rooms)
        self.room_previews.set_inference_rooms(ml_rooms)
        if active_id:
            self.orchestrator.set_inference_room(active_id)
        if engines_changed or ml_rooms != prev_ml:
            self.room_previews.sync_rooms(doc.rooms)

    def _sync_ml_scope(self, mode: Optional[str] = None) -> None:
        """Backward-compatible alias — mode no longer stops per-room engines."""
        _ = mode
        self._ensure_room_engines()

    def restart_engine_for_room(self, room_id: str) -> None:
        """Switch UI focus / active room without stopping any camera feeds."""
        try:
            self.orchestrator.camera_for_room(room_id)
        except ValueError:
            return
        self.rooms_store.set_active_room_id(room_id)
        self._on_orchestrator_active_room_changed(room_id)
        self.orchestrator.set_inference_room(room_id)

    def sync_room_engines(self) -> None:
        """Start/stop per-room engines when the room list changes during live mode."""
        if self.live_mode != "live":
            self.orchestrator.sync_previews()
            return
        enabled = {r.id: r for r in self.rooms_store.document().enabled_rooms()}
        for rid in list(self._room_engines.keys()):
            if rid not in enabled:
                self._stop_room_engine(rid)
        self._ensure_room_engines()
        for room in enabled.values():
            if room.id in self._room_engines:
                self._restart_room_engine_if_camera_changed(room)

    def rooms_status(self) -> dict[str, Any]:
        return self.orchestrator.status_payload()

    def room_preview_jpeg(self, room_id: str) -> Optional[bytes]:
        data = self.room_previews.hub.latest_jpeg(room_id)
        if data is not None:
            return data
        if (
            self.orchestrator.active_room_id == room_id
            and self.preview.available
        ):
            return self.preview.latest_jpeg()
        return None

    def _on_engine_snapshot(self, room_id: str, snap: LiveSnapshot) -> None:
        with self._snapshot_lock:
            snap.room_id = room_id
            self.orchestrator.handle_snapshot(room_id, snap)
            snap.orchestrator_mode = self.orchestrator.mode
            snap.active_room_id = self.orchestrator.active_room_id
            if room_id == self.orchestrator.active_room_id:
                self.hub.push_from_thread(snap)

    @property
    def is_running(self) -> bool:
        return bool(self._room_engines) and any(
            eng.is_running() for eng in self._room_engines.values()
        )

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

    def _apply_video_overrides_for_room(self, cfg: Config, room: RoomRecord) -> Config:
        source = room.camera.source
        backend = room.camera.backend
        exclude = self._droidcam_exclude_for_room(room.id)
        resolved = resolve_video_source(
            source, backend=backend, exclude_urls=exclude
        )
        video = cfg.raw.setdefault("video", {})
        if resolved.unresolved:
            video["source"] = source
            video["backend"] = backend
        else:
            video["source"] = resolved.source
            video["backend"] = resolved.backend
        return cfg

    def _apply_video_overrides(self, cfg: Config) -> Config:
        active_id = self._inference_room_id or self.rooms_store.active_room_id()
        room = self.rooms_store.get_room(active_id) if active_id else None
        if room is None:
            source, backend = self._effective_video_config(cfg)
            exclude = self._droidcam_exclude_for_room(active_id)
            resolved = resolve_video_source(
                source, backend=backend, exclude_urls=exclude
            )
            video = cfg.raw.setdefault("video", {})
            if resolved.unresolved:
                video["source"] = source
                video["backend"] = backend
            else:
                video["source"] = resolved.source
                video["backend"] = resolved.backend
            return cfg
        return self._apply_video_overrides_for_room(cfg, room)

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

    def _known_phone_hosts(self, cfg: Config) -> list[str]:
        raw = cfg.video.get("known_phone_hosts") or []
        if not isinstance(raw, list):
            return []
        return [str(h).strip() for h in raw if str(h).strip()]

    def _skip_usb_probe_for_listing(self, cfg: Config) -> bool:
        """Avoid opening USB webcams while a network stream is actively inferring."""
        if not self.is_running or self.live_mode != "live":
            return False
        source, _ = self._effective_video_config(cfg)
        return _is_remote_video_source(source)

    def list_cameras(
        self,
        *,
        max_index: int = 6,
        exclude_room_id: Optional[str] = None,
        for_new_room: bool = False,
        refresh: bool = False,
    ) -> dict[str, Any]:
        cfg = load_config(settings.roomos_config)
        exclude = (
            self._assigned_camera_sources(skip_room_id=exclude_room_id)
            if for_new_room or exclude_room_id
            else set()
        )
        skip_usb = self._skip_usb_probe_for_listing(cfg)
        if not skip_usb:
            self._usb_probe_cache = list_available_cameras(max_index=max_index)
        cameras = list_all_cameras_for_ui(
            max_index=max_index,
            exclude_sources=exclude,
            include_droidcam_scan=True,
            skip_usb_probe=skip_usb,
            cached_usb_cameras=self._usb_probe_cache,
            droidcam_refresh=refresh,
            pinned_hosts=self._known_phone_hosts(cfg),
            include_onvif_scan=refresh,
        )
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

        discovered_phones = [
            c for c in cameras if c.get("kind") in ("droidcam", "droidcam_auto")
        ]
        assigned = exclude & {
            str(c.get("source"))
            for c in discovered_phones
            if c.get("kind") == "droidcam"
        }
        available_phones = [
            c for c in discovered_phones if c.get("kind") == "droidcam" and c.get("available")
        ]
        onvif_found = [c for c in cameras if c.get("kind") == "onvif"]

        return {
            "cameras": cameras,
            "current": {
                "source": effective_source,
                "backend": current_backend,
                "label": current_label,
            },
            "scan": {
                "phonesFound": len([c for c in cameras if c.get("kind") == "droidcam"]),
                "phonesAvailable": len(available_phones),
                "phonesAssigned": len(assigned),
                "onvifFound": len(onvif_found),
                "usbProbeSkipped": skip_usb,
                "refreshed": refresh,
            },
            "discoveredWifi": [
                {
                    "host": str(c.get("host") or ""),
                    "label": str(c.get("label") or ""),
                    "protocol": "onvif",
                }
                for c in onvif_found
                if c.get("host")
            ],
        }

    def validate_camera(self, source: VideoSourceLike) -> dict[str, Any]:
        return validate_camera_source(source)

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
        if was_live:
            self.sync_room_engines()
            cfg = load_config(settings.roomos_config)
            self.inference_source = describe_video_source(self._apply_video_overrides(cfg))
            return {
                "status": "updated",
                "source": source,
                "backend": backend_hint,
                "inference_source": self.inference_source,
                "engine_restarted": True,
            }
        if pending_setup:
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
        room_id: str,
        image_bgr: np.ndarray,
        *,
        max_width: int = 1280,
        jpeg_quality: int = 88,
    ) -> None:
        active_id = self.orchestrator.active_room_id or self._inference_room_id
        self._preview_encoder.enqueue(
            image_bgr,
            room_id=room_id,
            max_width=max_width,
            jpeg_quality=jpeg_quality,
            push_main_preview=(room_id == active_id),
        )

    def _preview_side_hook(self, frame_bgr: np.ndarray) -> None:
        eng = self.engine
        if eng is not None:
            eng.push_evidence_from_preview(frame_bgr)

    def _stop_room_engine(self, room_id: str) -> None:
        eng = self._room_engines.pop(room_id, None)
        if eng is not None and eng.is_running():
            eng.stop()

    def _restart_room_engine_if_camera_changed(self, room: RoomRecord) -> None:
        eng = self._room_engines.get(room.id)
        if eng is None:
            return
        cfg = load_config(settings.roomos_config)
        applied = self._apply_video_overrides_for_room(cfg, room)
        current_src = applied.raw.get("video", {}).get("source")
        current_bkd = applied.raw.get("video", {}).get("backend")
        eng_video = eng.config.raw.get("video", {})
        if (
            eng_video.get("source") == current_src
            and eng_video.get("backend") == current_bkd
        ):
            return
        self._stop_room_engine(room.id)
        video_cfg = cfg.video
        preview_cfg = video_cfg.get("preview", {}) or {}
        preview_max_w = int(
            preview_cfg.get("max_width", video_cfg.get("preview_max_width", 1280))
        )
        preview_quality = int(
            preview_cfg.get("jpeg_quality", video_cfg.get("preview_jpeg_quality", 88))
        )
        self._start_room_engine(
            room,
            preview_max_w=preview_max_w,
            preview_quality=preview_quality,
        )

    def _start_room_engine(
        self,
        room: RoomRecord,
        *,
        preview_max_w: int,
        preview_quality: int,
    ) -> Optional[LiveInferenceEngine]:
        if room.id in self._room_engines:
            return self._room_engines[room.id]

        cfg = load_config(settings.roomos_config)
        room_cfg = self._apply_video_overrides_for_room(cfg, room)
        resolved = resolve_video_source(
            room.camera.source,
            backend=room.camera.backend,
            exclude_urls=self._droidcam_exclude_for_room(room.id),
        )
        if resolved.unresolved:
            log.warning(
                "Skipping room %s — camera %r not resolved",
                room.name,
                room.camera.source,
            )
            return None

        room_id = room.id

        def _on_snapshot(snap: LiveSnapshot) -> None:
            self._on_engine_snapshot(room_id, snap)

        def _on_preview(image_bgr: np.ndarray) -> None:
            self._push_preview_frame(
                room_id,
                image_bgr,
                max_width=preview_max_w,
                jpeg_quality=preview_quality,
            )

        engine = build_engine(
            room_cfg,
            actions_config_path=None,
            on_snapshot=_on_snapshot,
            on_preview_frame=_on_preview,
        )
        engine.orchestrator_managed = True
        engine.inference_room_id = room_id
        engine.start_background()
        self._room_engines[room_id] = engine
        log.info("Started inference engine for room %s (%s)", room.name, room_id[:8])
        return engine

    def _stop_engine(self) -> None:
        for rid in list(self._room_engines.keys()):
            self._stop_room_engine(rid)
        self.room_previews.stop_all(clear_hub=False)
        self._preview_encoder.stop()
        self._preview_encoder.set_side_hook(None)
        self.live_mode = "off"
        self.preview.clear()
        self.room_previews.hub.clear_all()
        self._inference_room_id = None
        self._last_ml_rooms = set()
        self.orchestrator.set_inference_rooms(set())

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
            self._on_orchestrator_active_room_changed(active_id)

            cfg = load_config(settings.roomos_config)
            bundle_dir = resolve_bundle_dir(cfg)
            missing = [n for n in MODEL_ARTIFACT_FILES if not (bundle_dir / n).exists()]
            if missing:
                self.engine_compat_report = None
                self.engine_error = format_missing_model_help(bundle_dir=bundle_dir)
                log.error(self.engine_error)
                return {"status": "error", "error": self.engine_error, "live_mode": "off"}

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
            self._preview_max_w = preview_max_w
            self._preview_quality = preview_quality

            # Release low-FPS preview threads before ML opens each DroidCam URL.
            for room in enabled:
                self.room_previews.stop_room(room.id, clear_hub=False)

            started_rooms: list[str] = []
            for room in enabled:
                if self._handoff_preview_to_ml(
                    room,
                    preview_max_w=preview_max_w,
                    preview_quality=preview_quality,
                ):
                    started_rooms.append(room.id)

            if not started_rooms:
                self.camera_setup_required = True
                self.live_mode = "off"
                self.engine_error = None
                self.inference_source = None
                log.info("No room cameras resolved — waiting for user setup")
                return {
                    "status": "camera_setup_required",
                    "live_mode": "off",
                    "camera_setup_required": True,
                }

            self.camera_setup_required = False
            ml_started = set(self._room_engines.keys())
            self._last_ml_rooms = ml_started
            self.orchestrator.set_inference_rooms(ml_started)
            self.orchestrator.set_inference_room(active_id)
            self.room_previews.set_inference_rooms(set(self._room_engines.keys()))
            self.room_previews.sync_rooms(doc.rooms)
            self._preview_encoder.set_side_hook(self._preview_side_hook)
            self.live_mode = "live"
            self.orchestrator.on_live_started()
            self.engine_error = None
            active_room = doc.room_by_id(active_id)
            if active_room is not None:
                self.inference_source = describe_video_source(
                    self._apply_video_overrides_for_room(cfg, active_room)
                )
            src, bkd = self._effective_video_config(cfg)
            return {
                "status": "started",
                "live_mode": "live",
                "config": settings.roomos_config,
                "inference_source": self.inference_source,
                "data_source": "roomos-ml",
                "video_source": src,
                "video_backend": bkd,
                "rooms_started": started_rooms,
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

        run_error = None
        if self.live_mode == "live" and self._room_engines:
            for eng in self._room_engines.values():
                err = getattr(eng, "_run_error", None)
                if err:
                    run_error = err
                    break
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
