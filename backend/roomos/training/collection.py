"""Live mood-collection sessions.

While a session is active the live engine keeps doing normal inference, and
every processed burst is ALSO persisted (frames + fused features) into the
mood's on-device dataset. Frames come straight from the engine's decoded BGR
frames — we never open a second camera client (DroidCam allows only one).
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from ..utils.logging import get_logger
from . import personal_dataset as pds

log = get_logger("roomos.training.collection")

# Data-quality gates for captured bursts.
MIN_MEAN_LUMA = 14.0          # skip near-black bursts
MIN_BLUR_SCORE = 6.0          # Laplacian variance; lower = very blurry
DUPLICATE_DIFF_THRESHOLD = 1.5  # mean |diff| on a 16x16 gray thumb; lower = duplicate


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CollectionSession:
    mood_id: str
    duration_sec: float
    datasets_root: Path
    room_ids: list[str] = field(default_factory=list)  # empty = all rooms
    started_monotonic: float = field(default_factory=time.monotonic)
    started_at: str = field(default_factory=_now_iso)
    bursts_saved: int = 0
    frames_saved: int = 0
    bursts_skipped_dark: int = 0
    bursts_skipped_blur: int = 0
    bursts_skipped_duplicate: int = 0
    active: bool = True
    stop_reason: Optional[str] = None  # "timer" | "user"
    finished_at: Optional[str] = None

    @property
    def elapsed_sec(self) -> float:
        return time.monotonic() - self.started_monotonic

    @property
    def remaining_sec(self) -> float:
        return max(0.0, self.duration_sec - self.elapsed_sec)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "moodId": self.mood_id,
            "active": self.active,
            "startedAt": self.started_at,
            "durationSec": self.duration_sec,
            "elapsedSec": round(self.elapsed_sec, 1),
            "remainingSec": round(self.remaining_sec, 1),
            "burstsSaved": self.bursts_saved,
            "framesSaved": self.frames_saved,
            "skipped": {
                "dark": self.bursts_skipped_dark,
                "blurry": self.bursts_skipped_blur,
                "duplicate": self.bursts_skipped_duplicate,
            },
            "stopReason": self.stop_reason,
            "finishedAt": self.finished_at,
            "roomIds": list(self.room_ids),
        }


def _gray_stats(image_bgr: np.ndarray) -> tuple[float, float, np.ndarray]:
    """(mean_luma, blur_score, 16x16 thumb) for quality + duplicate checks."""
    import cv2

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    mean_luma = float(gray.mean())
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    thumb = cv2.resize(gray, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32)
    return mean_luma, blur, thumb


class MoodCollectionManager:
    """Singleton bridging the live engine thread and the moods API."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._session: Optional[CollectionSession] = None
        self._queue: "queue.Queue[Optional[tuple]]" = queue.Queue(maxsize=8)
        self._writer: Optional[threading.Thread] = None
        self._last_thumb: Optional[np.ndarray] = None

    # --- session lifecycle (API thread) --------------------------------

    def start(
        self,
        mood_id: str,
        duration_sec: float,
        datasets_root: Path,
        *,
        room_ids: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            if self._session is not None and self._session.active:
                raise RuntimeError(
                    f"A collection session for '{self._session.mood_id}' is already active."
                )
            duration = float(duration_sec)
            if not (10.0 <= duration <= 3600.0):
                raise ValueError("durationSec must be between 10 and 3600 seconds.")
            normalized_rooms = [str(r).strip() for r in (room_ids or []) if str(r).strip()]
            self._session = CollectionSession(
                mood_id=mood_id,
                duration_sec=duration,
                datasets_root=Path(datasets_root),
                room_ids=normalized_rooms,
            )
            self._last_thumb = None
            self._ensure_writer()
            log.info(
                "Mood collection started: mood=%s duration=%.0fs", mood_id, duration
            )
            return self._session.to_dict()

    def stop(self, *, reason: str = "user") -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._session is None:
                return None
            if self._session.active:
                self._session.active = False
                self._session.stop_reason = reason
                self._session.finished_at = _now_iso()
                log.info(
                    "Mood collection stopped (%s): mood=%s bursts=%d frames=%d",
                    reason,
                    self._session.mood_id,
                    self._session.bursts_saved,
                    self._session.frames_saved,
                )
            return self._session.to_dict()

    def clear(self) -> None:
        with self._lock:
            self._session = None

    def status(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._session is None:
                return None
            self._check_timer_locked()
            return self._session.to_dict()

    def is_active(self) -> bool:
        with self._lock:
            if self._session is None or not self._session.active:
                return False
            self._check_timer_locked()
            return self._session.active

    def active_mood_id(self) -> Optional[str]:
        with self._lock:
            if self._session is not None and self._session.active:
                return self._session.mood_id
            return None

    def _check_timer_locked(self) -> None:
        s = self._session
        if s is not None and s.active and s.elapsed_sec >= s.duration_sec:
            s.active = False
            s.stop_reason = "timer"
            s.finished_at = _now_iso()
            log.info(
                "Mood collection timer elapsed: mood=%s bursts=%d frames=%d",
                s.mood_id,
                s.bursts_saved,
                s.frames_saved,
            )

    # --- burst intake (engine ML thread) --------------------------------

    def handle_burst(
        self, burst: Any, fused: Any, *, room_id: Optional[str] = None
    ) -> None:
        """Called by the live engine after every processed burst. Never raises."""
        try:
            with self._lock:
                if not self.is_active():
                    return
                session = self._session
            assert session is not None
            if session.room_ids and room_id and room_id not in session.room_ids:
                return

            frames = [
                f.image_bgr
                for f in getattr(burst, "frames", [])
                if getattr(f, "image_bgr", None) is not None
            ]
            if len(frames) < pds.MIN_FRAMES_PER_BURST:
                return

            mid = frames[len(frames) // 2]
            mean_luma, blur, thumb = _gray_stats(mid)
            with self._lock:
                if mean_luma < MIN_MEAN_LUMA:
                    session.bursts_skipped_dark += 1
                    return
                if blur < MIN_BLUR_SCORE:
                    session.bursts_skipped_blur += 1
                    return
                if (
                    self._last_thumb is not None
                    and self._last_thumb.shape == thumb.shape
                    and float(np.abs(self._last_thumb - thumb).mean())
                    < DUPLICATE_DIFF_THRESHOLD
                ):
                    session.bursts_skipped_duplicate += 1
                    return
                self._last_thumb = thumb

            burst_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
            item = (
                session,
                burst_id,
                [f.copy() for f in frames],
                dict(fused.as_dict()),
                dict(getattr(fused, "metadata", {}) or {}),
                mean_luma,
                blur,
            )
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                log.warning("Collection writer backlog full; dropping burst.")
        except Exception as e:  # never break the inference loop
            log.warning("Mood collection burst intake failed: %s", e)

    # --- background writer ----------------------------------------------

    def _ensure_writer(self) -> None:
        if self._writer is not None and self._writer.is_alive():
            return
        self._writer = threading.Thread(
            target=self._writer_loop, name="roomos-mood-collect", daemon=True
        )
        self._writer.start()

    def _writer_loop(self) -> None:
        import cv2

        while True:
            try:
                item = self._queue.get(timeout=2.0)
            except queue.Empty:
                with self._lock:
                    idle = self._session is None or not self._session.active
                if idle and self._queue.empty():
                    continue
                continue
            if item is None:
                break
            session, burst_id, frames, features, metadata, mean_luma, blur = item
            try:
                bdir = pds.burst_dir(session.datasets_root, session.mood_id, burst_id)
                bdir.mkdir(parents=True, exist_ok=True)
                saved = 0
                for i, frame in enumerate(frames, start=1):
                    ok, buf = cv2.imencode(
                        ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88]
                    )
                    if ok:
                        (bdir / f"frame_{i:02d}.jpg").write_bytes(buf.tobytes())
                        saved += 1
                if saved < pds.MIN_FRAMES_PER_BURST:
                    continue
                pds.write_feature_cache(
                    session.datasets_root,
                    session.mood_id,
                    burst_id,
                    features=features,
                    metadata=metadata,
                    n_frames=saved,
                )
                meta: Dict[str, Any] = {
                    "burstId": burst_id,
                    "capturedAt": _now_iso(),
                    "meanLuma": round(mean_luma, 2),
                    "blurScore": round(blur, 2),
                    "frameCount": saved,
                }
                if room_id:
                    meta["roomId"] = room_id
                pds.append_burst_metadata(
                    session.datasets_root,
                    session.mood_id,
                    meta,
                )
                with self._lock:
                    session.bursts_saved += 1
                    session.frames_saved += saved
            except Exception as e:
                log.warning("Failed to persist collection burst: %s", e)


# Process-wide singleton used by the engine hook and the moods API.
mood_collection = MoodCollectionManager()
