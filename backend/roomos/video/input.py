"""Video input.

A thin wrapper around ``cv2.VideoCapture`` that:

* accepts ints (webcam index), strings (file path / RTSP URL),
  and the convenience prefix ``droidcam:auto`` which probes a few common
  DroidCam HTTP ports;
* exposes an iterator over :class:`SampledFrame` objects with monotonic
  timestamps so downstream code doesn't need to know whether the source is
  live or a file;
* fails gracefully — no frame? we log, sleep briefly, and try again.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Union

import numpy as np

from ..utils.logging import get_logger

log = get_logger("roomos.video")

VideoSourceLike = Union[int, str, Path]


@dataclass
class SampledFrame:
    """A single decoded frame plus metadata."""

    index: int                # monotonic frame counter since stream open
    timestamp: float          # seconds since stream open (monotonic clock)
    image: np.ndarray         # BGR (HxWx3) image in OpenCV layout
    source: str               # human-readable source identifier


# --- droidcam helpers ------------------------------------------------------

_DROIDCAM_DEFAULT_PORTS = (4747, 4848, 8080)
_DROIDCAM_DEFAULT_HOSTS = ("127.0.0.1", "localhost")


def _probe_droidcam() -> Optional[str]:
    """Return the first DroidCam URL that responds, or None."""
    import socket

    for host in _DROIDCAM_DEFAULT_HOSTS:
        for port in _DROIDCAM_DEFAULT_PORTS:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            try:
                s.connect((host, port))
                s.close()
                return f"http://{host}:{port}/video"
            except OSError:
                continue
    return None


# --- main class ------------------------------------------------------------


def _coerce_source(source: VideoSourceLike) -> Union[int, str]:
    """Normalize 'source' into a value cv2.VideoCapture understands."""
    if isinstance(source, int):
        return source
    s = str(source)
    if s.isdigit():
        return int(s)
    if s == "droidcam:auto":
        probed = _probe_droidcam()
        if probed is None:
            raise RuntimeError(
                "No DroidCam HTTP endpoint detected on common ports. "
                "Pass a full URL (e.g. http://192.168.x.x:4747/video) instead."
            )
        log.info("droidcam:auto -> %s", probed)
        return probed
    return s


class FrameSource:
    """Iterable, sampled view of any cv2-readable video source.

    Parameters
    ----------
    source : int | str | Path
        Webcam index, file path, RTSP URL, or ``"droidcam:auto"``.
    sample_fps : float
        Target processing rate. We *drop* frames if the source runs faster
        than this; we don't try to keep up if it runs slower.
    resize_width : int | None
        If set, frames are resized to this width preserving aspect ratio.
    read_timeout_sec : float
        Considered "dead" if no successful frame within this window.
    log_every : int
        Emit a heartbeat log every N processed frames (live debugging).
    """

    def __init__(
        self,
        source: VideoSourceLike,
        sample_fps: float = 6.0,
        resize_width: Optional[int] = None,
        read_timeout_sec: float = 5.0,
        log_every: int = 0,
    ) -> None:
        self.requested_source = source
        self.coerced_source = _coerce_source(source)
        self.sample_fps = max(0.1, float(sample_fps))
        self.resize_width = resize_width
        self.read_timeout_sec = float(read_timeout_sec)
        self.log_every = int(log_every)

        self._cap = None
        self._opened_at = 0.0
        self._next_emit_at = 0.0
        self._sample_period = 1.0 / self.sample_fps
        self._frame_index = 0

    # --- context manager -----------------------------------------------

    def __enter__(self) -> "FrameSource":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # --- core API ------------------------------------------------------

    def open(self) -> None:
        import cv2

        log.info("Opening video source: %s", self.coerced_source)
        cap = cv2.VideoCapture(self.coerced_source)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video source: {self.coerced_source!r}")
        self._cap = cap
        self._opened_at = time.monotonic()
        self._next_emit_at = 0.0
        self._frame_index = 0

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def is_live(self) -> bool:
        """File sources are not live; ints and URLs are."""
        return not isinstance(self.coerced_source, str) or "://" in self.coerced_source

    # --- iteration -----------------------------------------------------

    def __iter__(self) -> Iterator[SampledFrame]:
        if self._cap is None:
            self.open()
        assert self._cap is not None

        import cv2

        last_ok = time.monotonic()
        consecutive_failures = 0
        while True:
            ok, frame = self._cap.read()
            now_rel = time.monotonic() - self._opened_at

            if not ok or frame is None:
                consecutive_failures += 1
                if (time.monotonic() - last_ok) > self.read_timeout_sec:
                    # For files, EOF is normal. For live, give up.
                    if self.is_live():
                        log.warning("Video read timeout (%.1fs). Stopping iterator.", self.read_timeout_sec)
                    else:
                        log.info("End of video reached after %d failures.", consecutive_failures)
                    return
                time.sleep(0.02)
                continue

            consecutive_failures = 0
            last_ok = time.monotonic()

            # Sample-rate gating: only emit if enough wall-time has passed.
            if now_rel < self._next_emit_at:
                continue
            self._next_emit_at = now_rel + self._sample_period

            if self.resize_width and frame.shape[1] > self.resize_width:
                scale = self.resize_width / float(frame.shape[1])
                new_size = (self.resize_width, max(1, int(round(frame.shape[0] * scale))))
                frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)

            sf = SampledFrame(
                index=self._frame_index,
                timestamp=now_rel,
                image=frame,
                source=str(self.requested_source),
            )
            self._frame_index += 1

            if self.log_every and (self._frame_index % self.log_every == 0):
                log.info(
                    "frame=%d t=%.2fs shape=%s fps_target=%.1f",
                    sf.index,
                    sf.timestamp,
                    tuple(sf.image.shape),
                    self.sample_fps,
                )

            yield sf


def open_video_source(
    source: VideoSourceLike,
    *,
    sample_fps: float = 6.0,
    resize_width: Optional[int] = None,
    read_timeout_sec: float = 5.0,
    log_every: int = 0,
) -> FrameSource:
    """Functional convenience wrapper — does not open the device yet."""
    return FrameSource(
        source=source,
        sample_fps=sample_fps,
        resize_width=resize_width,
        read_timeout_sec=read_timeout_sec,
        log_every=log_every,
    )
