"""Lightweight per-room preview capture (gallery tiles, grace occupancy scan)."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

import numpy as np

from ..config import load_config
from ..utils.logging import get_logger
from ..video.input import (
    collect_claimed_droidcam_urls,
    open_video_source,
    resolve_video_source,
)
from .models import RoomRecord

log = get_logger("roomos.rooms.preview")


@dataclass(frozen=True)
class RoomPreviewSettings:
    fps: float = 1.5
    max_width: int = 960
    jpeg_quality: int = 78


def load_room_preview_settings(config_path: str) -> RoomPreviewSettings:
    cfg = load_config(config_path)
    video_cfg = cfg.video or {}
    room_cfg = dict(video_cfg.get("room_preview", {}) or {})
    return RoomPreviewSettings(
        fps=max(0.5, float(room_cfg.get("max_fps", 1.5))),
        max_width=int(room_cfg.get("max_width", 960)),
        jpeg_quality=int(room_cfg.get("jpeg_quality", 78)),
    )


class RoomPreviewHub:
    """Thread-safe latest JPEG per room id."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._jpeg: Dict[str, bytes] = {}
        self._mean_luma: Dict[str, float] = {}
        self._frames_seen: Dict[str, int] = {}
        self._generation: Dict[str, int] = {}

    def push(self, room_id: str, jpeg: bytes, *, mean_luma: Optional[float] = None) -> None:
        with self._cond:
            self._jpeg[room_id] = jpeg
            if mean_luma is not None:
                self._mean_luma[room_id] = float(mean_luma)
            self._frames_seen[room_id] = self._frames_seen.get(room_id, 0) + 1
            self._generation[room_id] = self._generation.get(room_id, 0) + 1
            self._cond.notify_all()

    def latest_jpeg(self, room_id: str) -> Optional[bytes]:
        with self._cond:
            return self._jpeg.get(room_id)

    def mean_luma(self, room_id: str) -> Optional[float]:
        with self._cond:
            return self._mean_luma.get(room_id)

    def clear_room(self, room_id: str) -> None:
        with self._cond:
            self._jpeg.pop(room_id, None)
            self._mean_luma.pop(room_id, None)
            self._frames_seen.pop(room_id, None)
            self._generation.pop(room_id, None)
            self._cond.notify_all()

    def clear_all(self) -> None:
        with self._cond:
            self._jpeg.clear()
            self._mean_luma.clear()
            self._frames_seen.clear()
            self._generation.clear()
            self._cond.notify_all()

    def wait_for_new_frame(
        self,
        room_id: str,
        after_generation: int,
        *,
        timeout: float = 1.0,
    ) -> Tuple[Optional[bytes], int]:
        deadline = time.monotonic() + max(0.01, float(timeout))
        with self._cond:
            while True:
                gen = self._generation.get(room_id, 0)
                jpeg = self._jpeg.get(room_id)
                if jpeg is not None and gen > after_generation:
                    return jpeg, gen
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return jpeg, gen
                self._cond.wait(timeout=min(0.1, remaining))


@dataclass
class _RoomEncodeJob:
    room_id: str
    image: np.ndarray


class _SharedRoomPreviewEncoder:
    """One background worker encodes gallery frames from all room capture threads."""

    def __init__(self, hub: RoomPreviewHub) -> None:
        self._hub = hub
        self._queue: "queue.Queue[Optional[_RoomEncodeJob]]" = queue.Queue(maxsize=8)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._max_width = 960
        self._jpeg_quality = 78

    def configure(self, *, max_width: int, jpeg_quality: int) -> None:
        self._max_width = max_width
        self._jpeg_quality = jpeg_quality

    def ensure_running(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._worker,
            name="room-preview-encode",
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

    def enqueue(self, room_id: str, image_bgr: np.ndarray) -> None:
        self.ensure_running()
        job = _RoomEncodeJob(room_id=room_id, image=image_bgr)
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
            self._encode_and_push(item.room_id, item.image.copy())

    def _encode_and_push(self, room_id: str, image_bgr: np.ndarray) -> None:
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
        if ok:
            self._hub.push(room_id, buf.tobytes(), mean_luma=mean_luma)


class _RoomCaptureThread:
    def __init__(
        self,
        room: RoomRecord,
        hub: RoomPreviewHub,
        encoder: _SharedRoomPreviewEncoder,
        *,
        config_path: str,
        settings: Optional[RoomPreviewSettings] = None,
        skip_room_ids: Optional[Callable[[], set[str]]] = None,
        all_rooms_fn: Optional[Callable[[], list[RoomRecord]]] = None,
    ) -> None:
        self._room = room
        self._hub = hub
        self._encoder = encoder
        self._config_path = config_path
        self._settings = settings or load_room_preview_settings(config_path)
        self._fps = self._settings.fps
        self._skip_room_ids = skip_room_ids or (lambda: set())
        self._all_rooms_fn = all_rooms_fn or (lambda: [])
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._latest_bgr: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()

    @property
    def room_id(self) -> str:
        return self._room.id

    def latest_bgr(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            if self._latest_bgr is None:
                return None
            return self._latest_bgr.copy()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"room-preview-{self._room.id[:8]}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=4.0)
        self._thread = None
        self._hub.clear_room(self._room.id)

    def _run(self) -> None:
        # Live inference owns this room's feed (DroidCam HTTP allows one client).
        while not self._stop.is_set() and self._room.id in self._skip_room_ids():
            time.sleep(0.25)
        if self._stop.is_set():
            return

        exclude = collect_claimed_droidcam_urls(
            self._all_rooms_fn(),
            skip_room_id=self._room.id,
        )
        resolved = resolve_video_source(
            self._room.camera.source,
            backend=self._room.camera.backend,
            exclude_urls=exclude,
        )
        if resolved.unresolved:
            log.debug("Preview skip unresolved camera for room %s", self._room.name)
            return

        interval = 1.0 / self._fps
        try:
            with open_video_source(
                resolved.source,
                sample_fps=self._fps,
                backend=resolved.backend,
            ) as source:
                for frame in source:
                    if self._stop.is_set():
                        break
                    if self._room.id in self._skip_room_ids():
                        time.sleep(interval)
                        continue
                    img = frame.image
                    with self._frame_lock:
                        self._latest_bgr = img
                    self._encoder.enqueue(self._room.id, img)
                    time.sleep(interval)
        except Exception as e:
            log.warning("Room preview %s failed: %s", self._room.name, e)


class RoomPreviewManager:
    """Manages preview capture threads for enabled rooms."""

    def __init__(self, *, config_path: str, hub: Optional[RoomPreviewHub] = None) -> None:
        self._config_path = config_path
        self.hub = hub or RoomPreviewHub()
        self._settings = load_room_preview_settings(config_path)
        self._encoder = _SharedRoomPreviewEncoder(self.hub)
        self._encoder.configure(
            max_width=self._settings.max_width,
            jpeg_quality=self._settings.jpeg_quality,
        )
        self._threads: Dict[str, _RoomCaptureThread] = {}
        self._lock = threading.Lock()
        self._inference_room_id: Optional[str] = None
        self._rooms: list[RoomRecord] = []

    def set_inference_room(self, room_id: Optional[str]) -> None:
        with self._lock:
            self._inference_room_id = room_id

    def _skip_ids(self) -> set[str]:
        if self._inference_room_id:
            return {self._inference_room_id}
        return set()

    def sync_rooms(self, rooms: list[RoomRecord]) -> None:
        self._settings = load_room_preview_settings(self._config_path)
        self._encoder.configure(
            max_width=self._settings.max_width,
            jpeg_quality=self._settings.jpeg_quality,
        )
        self._rooms = list(rooms)
        enabled = {r.id: r for r in rooms if r.enabled}
        all_rooms_fn = lambda: self._rooms  # noqa: E731
        with self._lock:
            inference_id = self._inference_room_id
            if inference_id:
                stale = self._threads.pop(inference_id, None)
                if stale is not None:
                    stale.stop()

            for rid in list(self._threads.keys()):
                if rid not in enabled:
                    self._threads.pop(rid).stop()
            for room in enabled.values():
                if room.id == inference_id:
                    continue
                existing = self._threads.get(room.id)
                if existing is None:
                    t = _RoomCaptureThread(
                        room,
                        self.hub,
                        self._encoder,
                        config_path=self._config_path,
                        settings=self._settings,
                        skip_room_ids=self._skip_ids,
                        all_rooms_fn=all_rooms_fn,
                    )
                    self._threads[room.id] = t
                    t.start()
                else:
                    prev = existing._room.camera
                    cur = room.camera
                    if prev.source != cur.source or prev.backend != cur.backend:
                        existing.stop()
                        t = _RoomCaptureThread(
                            room,
                            self.hub,
                            self._encoder,
                            config_path=self._config_path,
                            settings=self._settings,
                            skip_room_ids=self._skip_ids,
                            all_rooms_fn=all_rooms_fn,
                        )
                        self._threads[room.id] = t
                        t.start()
                    else:
                        existing._room = room

    def stop_all(self) -> None:
        with self._lock:
            for t in list(self._threads.values()):
                t.stop()
            self._threads.clear()
        self._encoder.stop()
        self.hub.clear_all()

    def latest_bgr(self, room_id: str) -> Optional[np.ndarray]:
        with self._lock:
            t = self._threads.get(room_id)
        if t is None:
            return None
        return t.latest_bgr()
