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
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, List, Optional, Tuple, Union

import numpy as np

from ..utils.logging import get_logger

log = get_logger("roomos.video")

VideoSourceLike = Union[int, str, Path]

# Backend hint accepted by FrameSource / open_video_source.
#   "auto"  – pick a sensible default per OS (Windows: DSHOW, others: any)
#   "any"   – let OpenCV choose (cv2.CAP_ANY)
#   "dshow" – DirectShow (Windows webcams). Required on Windows for many webcams
#             otherwise OpenCV returns black/garbage frames or hangs.
#   "msmf"  – Media Foundation (Windows). Often slower to open but more stable
#             with some integrated cameras.
#   "v4l2"  – Video4Linux2 (Linux)
#   "avfoundation" – AVFoundation (macOS)
VideoBackend = str

_BACKEND_ALIASES = {
    "auto": None,  # resolved later based on platform + source type
    "any": "CAP_ANY",
    "dshow": "CAP_DSHOW",
    "msmf": "CAP_MSMF",
    "v4l2": "CAP_V4L2",
    "avfoundation": "CAP_AVFOUNDATION",
}


@dataclass
class SampledFrame:
    """A single decoded frame plus metadata."""

    index: int                # monotonic frame counter since stream open
    timestamp: float          # seconds since stream open (monotonic clock)
    image: np.ndarray         # BGR (HxWx3) image in OpenCV layout
    source: str               # human-readable source identifier


# --- droidcam helpers ------------------------------------------------------

# DroidCam default HTTP port is 4747. 8080 is often another local service on
# Windows (socket open but not an MJPEG feed) — do not pick it from TCP alone.
_DROIDCAM_DEFAULT_PORTS = (4747, 4848)
_DROIDCAM_DEFAULT_HOSTS = ("127.0.0.1", "localhost")


def _droidcam_port_open(host: str, port: int, timeout_sec: float = 0.25) -> bool:
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout_sec)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def _opencv_can_read_url(url: str, timeout_sec: float = 4.0) -> bool:
    """Try opening ``url`` with OpenCV without blocking the caller for minutes."""
    import concurrent.futures

    def _try() -> bool:
        import cv2

        cap = cv2.VideoCapture(url)
        try:
            if not cap.isOpened():
                return False
            for _ in range(5):
                ok, frame = cap.read()
                if ok and frame is not None and frame.size > 0:
                    return True
                time.sleep(0.05)
            return False
        finally:
            try:
                cap.release()
            except Exception:
                pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_try)
        try:
            return bool(fut.result(timeout=timeout_sec))
        except concurrent.futures.TimeoutError:
            log.warning("DroidCam OpenCV probe timed out after %.1fs: %s", timeout_sec, url)
            return False


def _probe_droidcam() -> Optional[str]:
    """Return the first DroidCam URL OpenCV can actually decode, or None."""
    for host in _DROIDCAM_DEFAULT_HOSTS:
        for port in _DROIDCAM_DEFAULT_PORTS:
            if not _droidcam_port_open(host, port):
                continue
            url = f"http://{host}:{port}/video"
            if _opencv_can_read_url(url):
                log.info("droidcam:auto verified stream at %s", url)
                return url
    return None


# --- backend resolution ----------------------------------------------------


def _resolve_backend(backend: Optional[VideoBackend], source: Union[int, str]) -> Tuple[int, str]:
    """Translate a backend hint into a cv2 capture API id + ordered fallbacks.

    Returns ``(primary_api, primary_name)``; callers iterate
    :func:`_backend_chain` for retries.
    """
    import cv2

    hint = (backend or "auto").strip().lower()
    if hint not in _BACKEND_ALIASES:
        log.warning("Unknown video.backend=%r; falling back to 'auto'.", backend)
        hint = "auto"

    if hint == "auto":
        # URL / RTSP / file: default OpenCV behavior is fine.
        if isinstance(source, str) and not source.isdigit():
            return getattr(cv2, "CAP_ANY", 0), "CAP_ANY"
        # Webcam index. Windows webcams are notoriously broken with the default
        # MSMF path under newer OpenCV builds (returns black frames on many
        # integrated cams). DirectShow is the right default.
        if sys.platform.startswith("win"):
            return getattr(cv2, "CAP_DSHOW", 700), "CAP_DSHOW"
        if sys.platform == "darwin":
            return getattr(cv2, "CAP_AVFOUNDATION", 1200), "CAP_AVFOUNDATION"
        return getattr(cv2, "CAP_ANY", 0), "CAP_ANY"

    name = _BACKEND_ALIASES[hint] or "CAP_ANY"
    return getattr(cv2, name, 0), name


def _backend_chain(backend: Optional[VideoBackend], source: Union[int, str]) -> List[Tuple[int, str]]:
    """Primary + sensible fallbacks for opening a webcam.

    Only webcam indices get a chain — URLs / files always use the primary
    resolved backend.
    """
    import cv2

    primary = _resolve_backend(backend, source)
    if not isinstance(source, int):
        # Network MJPEG (DroidCam). On Windows CAP_ANY often fails; try FFmpeg first.
        import cv2

        chain: List[Tuple[int, str]] = []
        seen: set[str] = set()
        for name in ("CAP_FFMPEG", "CAP_ANY"):
            api = getattr(cv2, name, None)
            if api is None or name in seen:
                continue
            chain.append((api, name))
            seen.add(name)
        return chain if chain else [primary]

    chain: List[Tuple[int, str]] = [primary]
    seen = {primary[1]}
    if sys.platform.startswith("win"):
        for name in ("CAP_DSHOW", "CAP_MSMF", "CAP_ANY"):
            if name in seen:
                continue
            api = getattr(cv2, name, None)
            if api is None:
                continue
            chain.append((api, name))
            seen.add(name)
    else:
        for name in ("CAP_V4L2", "CAP_AVFOUNDATION", "CAP_ANY"):
            if name in seen:
                continue
            api = getattr(cv2, name, None)
            if api is None:
                continue
            chain.append((api, name))
            seen.add(name)
    return chain


def _apply_capture_format(
    cap,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
    fps: Optional[float] = None,
) -> None:
    """Best-effort negotiation with the device driver (may be ignored)."""
    import cv2

    if width and width > 0:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
    if height and height > 0:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
    if fps and fps > 0:
        cap.set(cv2.CAP_PROP_FPS, float(fps))


def _open_capture(
    source: Union[int, str],
    backend: Optional[VideoBackend],
    *,
    capture_width: Optional[int] = None,
    capture_height: Optional[int] = None,
    capture_fps: Optional[float] = None,
):
    """Open a cv2.VideoCapture trying the platform-appropriate backend chain.

    Returns ``(cap, backend_name)`` on success. Raises ``RuntimeError`` if all
    backends fail to produce a readable first frame.
    """
    import cv2

    chain = _backend_chain(backend, source)
    last_err: Optional[str] = None
    for api, name in chain:
        try:
            cap = cv2.VideoCapture(source, api) if api else cv2.VideoCapture(source)
        except Exception as e:
            last_err = f"{name}: open raised {e!r}"
            continue
        if not cap.isOpened():
            last_err = f"{name}: VideoCapture.isOpened() == False"
            try:
                cap.release()
            except Exception:
                pass
            continue
        if isinstance(source, int):
            _apply_capture_format(
                cap,
                width=capture_width,
                height=capture_height,
                fps=capture_fps,
            )
        # Read one warm-up frame: many Windows webcams claim isOpened()==True
        # but only return None until DSHOW negotiates a format. Try a few times.
        ok = False
        for _ in range(5):
            ok, _frame = cap.read()
            if ok and _frame is not None:
                break
            time.sleep(0.05)
        if not ok:
            last_err = f"{name}: opened but no frames after warm-up"
            try:
                cap.release()
            except Exception:
                pass
            continue
        log.info("Opened video source %r via %s", source, name)
        return cap, name

    raise RuntimeError(
        f"Could not open video source {source!r} with any backend "
        f"(tried {[n for _, n in chain]}). Last error: {last_err}"
    )


class _MjpegHttpCapture:
    """VideoCapture-like reader for DroidCam-style MJPEG over HTTP (stdlib)."""

    def __init__(self, url: str) -> None:
        import urllib.request

        self.url = url
        self._resp = urllib.request.urlopen(url, timeout=10)
        self._buffer = b""
        self._opened = True

    def isOpened(self) -> bool:
        return self._opened

    def read(self):
        import cv2

        frame = self._read_jpeg_frame()
        if frame is None:
            return False, None
        return True, frame

    def release(self) -> None:
        self._opened = False
        try:
            self._resp.close()
        except Exception:
            pass

    def _read_jpeg_frame(self) -> Optional[np.ndarray]:
        import cv2

        soi = b"\xff\xd8"
        eoi = b"\xff\xd9"
        while len(self._buffer) < 2_000_000:
            start = self._buffer.find(soi)
            if start >= 0:
                end = self._buffer.find(eoi, start + 2)
                if end >= 0:
                    jpg = self._buffer[start : end + 2]
                    self._buffer = self._buffer[end + 2 :]
                    img = cv2.imdecode(
                        np.frombuffer(jpg, dtype=np.uint8),
                        cv2.IMREAD_COLOR,
                    )
                    if img is not None and img.size > 0:
                        return img
            chunk = self._resp.read(8192)
            if not chunk:
                return None
            self._buffer += chunk
        return None


def _open_mjpeg_http(url: str) -> _MjpegHttpCapture:
    """Fallback when OpenCV cannot open DroidCam HTTP URLs on Windows."""
    cap = _MjpegHttpCapture(url)
    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        raise RuntimeError(
            f"Could not read MJPEG frames from {url}. "
            "If DroidCam Client is open, the HTTP feed is often busy — quit the client "
            "(File → Exit) and retry, or use the virtual webcam: npm run probe:cameras "
            "(on Windows try source=1 backend=msmf for 'DroidCam Video')."
        )
    log.info("Opened video source %r via mjpeg-http (OpenCV fallback)", url)
    return cap


def _open_video_capture(
    source: Union[int, str],
    backend: Optional[VideoBackend],
    *,
    capture_width: Optional[int] = None,
    capture_height: Optional[int] = None,
    capture_fps: Optional[float] = None,
):
    """Open OpenCV capture, with HTTP MJPEG fallback for DroidCam Wi-Fi URLs."""
    if isinstance(source, str) and "://" in source:
        try:
            return _open_capture(
                source,
                backend,
                capture_width=capture_width,
                capture_height=capture_height,
                capture_fps=capture_fps,
            )
        except RuntimeError as exc:
            log.warning("OpenCV failed for %s: %s — trying HTTP MJPEG reader.", source, exc)
            return _open_mjpeg_http(source), "mjpeg-http"
    cap, active = _open_capture(
        source,
        backend,
        capture_width=capture_width,
        capture_height=capture_height,
        capture_fps=capture_fps,
    )
    return cap, active


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
                "No DroidCam HTTP stream found on 127.0.0.1:4747 or :4848. "
                "Start the DroidCam Windows client, connect your phone, and confirm "
                "you see live video there. Then set video.source to the exact URL "
                "from DroidCam (e.g. http://127.0.0.1:4747/video over USB, or "
                "http://<phone-ip>:4747/video on Wi-Fi). "
                "Or use DroidCam's virtual webcam and set video.source to that "
                "index (run: npm run probe:cameras)."
            )
        log.info("droidcam:auto -> %s", probed)
        return probed
    return s


def _list_windows_dshow_names() -> List[str]:
    """Best-effort DirectShow friendly names (requires ffmpeg on PATH)."""
    import re
    import shutil
    import subprocess

    if not sys.platform.startswith("win") or not shutil.which("ffmpeg"):
        return []
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "dshow", "-list_devices", "true", "-i", "dummy"],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    text = (proc.stderr or "") + (proc.stdout or "")
    names: List[str] = []
    for line in text.splitlines():
        m = re.search(r'"([^"]+)"\s+\(video\)', line)
        if m:
            names.append(m.group(1))
    return names


def probe_cameras(max_index: int = 4) -> List[dict]:
    """Probe webcam indices 0..max_index across known backends.

    Returns a list of dicts ``{index, backend, ok, mean_luma, error}`` so the
    operator can pick a working camera/backend pair when the default goes
    black. Intentionally side-effect free for shell use.

    On Windows, DroidCam often appears as index 1 with **CAP_MSMF** while index 0
    is the laptop webcam (DSHOW may open index 0 with black frames). We warm up
    several reads and keep the brightest frame so transient dark frames do not
    hide a working device.
    """
    import cv2

    results: List[dict] = []
    if sys.platform.startswith("win"):
        # MSMF first: DroidCam Virtual Output often fails DSHOW-by-index but works here.
        backend_names = ("CAP_MSMF", "CAP_DSHOW", "CAP_ANY")
    elif sys.platform == "darwin":
        backend_names = ("CAP_AVFOUNDATION", "CAP_ANY")
    else:
        backend_names = ("CAP_V4L2", "CAP_ANY")

    dshow_names = _list_windows_dshow_names() if sys.platform.startswith("win") else []

    for idx in range(max_index + 1):
        for bname in backend_names:
            api = getattr(cv2, bname, None)
            if api is None:
                continue
            entry: dict = {
                "index": idx,
                "backend": bname,
                "ok": False,
                "mean_luma": None,
                "error": None,
                "device_hint": None,
            }
            cap = None
            try:
                cap = cv2.VideoCapture(idx, api)
                if not cap.isOpened():
                    entry["error"] = "isOpened() == False"
                else:
                    best_luma = -1.0
                    best_shape: Optional[Tuple[int, ...]] = None
                    for _ in range(20):
                        ok, frame = cap.read()
                        if ok and frame is not None:
                            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                            luma = float(gray.mean())
                            if luma > best_luma:
                                best_luma = luma
                                best_shape = tuple(frame.shape)
                        time.sleep(0.05)
                    if best_shape is None:
                        entry["error"] = "opened but no frames"
                    else:
                        entry["ok"] = True
                        entry["mean_luma"] = best_luma
                        entry["frame_shape"] = list(best_shape)
            except Exception as e:  # noqa: BLE001
                entry["error"] = f"{type(e).__name__}: {e}"
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
            results.append(entry)

    if dshow_names:
        _attach_windows_device_hints(results, dshow_names)
    return results


def _attach_windows_device_hints(results: List[dict], dshow_names: List[str]) -> None:
    """Guess friendly names — ffmpeg list order often differs from OpenCV index order."""
    video_names = [n for n in dshow_names if "audio" not in n.lower()]
    droid = next((n for n in video_names if "droidcam" in n.lower()), None)
    integrated = next(
        (n for n in video_names if "integrated" in n.lower() or "facetime" in n.lower()),
        None,
    )
    if not droid and not integrated:
        return

    best_per_index: dict[int, dict] = {}
    for row in results:
        if not row.get("ok"):
            continue
        idx = int(row["index"])
        prev = best_per_index.get(idx)
        if prev is None or (row.get("mean_luma") or 0) > (prev.get("mean_luma") or 0):
            best_per_index[idx] = row

    if not best_per_index:
        return

    ranked = sorted(
        best_per_index.items(),
        key=lambda item: item[1].get("mean_luma") or 0,
        reverse=True,
    )
    brightest_idx = ranked[0][0]
    dimmest_idx = ranked[-1][0] if len(ranked) > 1 else None

    for row in results:
        if not row.get("ok"):
            continue
        idx = int(row["index"])
        if droid and idx == brightest_idx and (row.get("mean_luma") or 0) >= 12:
            row["device_hint"] = droid
        elif integrated and dimmest_idx is not None and idx == dimmest_idx:
            row["device_hint"] = integrated


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
    preview_fps : float | None
        If set with ``preview_callback``, emit full-resolution frames at this
        rate (independent of ``sample_fps`` / ML resize).
    preview_callback : callable | None
        Called with the camera frame *before* ``resize_width`` downscale.
    capture_width, capture_height, capture_fps : optional
        Passed to the driver on open (webcam indices only).
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
        backend: Optional[VideoBackend] = "auto",
        preview_fps: Optional[float] = None,
        preview_callback: Optional[Callable[[np.ndarray], None]] = None,
        capture_width: Optional[int] = None,
        capture_height: Optional[int] = None,
        capture_fps: Optional[float] = None,
    ) -> None:
        self.requested_source = source
        self.coerced_source = _coerce_source(source)
        self.sample_fps = max(0.1, float(sample_fps))
        self.resize_width = resize_width
        self.read_timeout_sec = float(read_timeout_sec)
        self.log_every = int(log_every)
        self.backend = backend
        self.preview_fps = float(preview_fps) if preview_fps else None
        self.preview_callback = preview_callback
        self.capture_width = capture_width
        self.capture_height = capture_height
        self.capture_fps = capture_fps

        self._cap = None
        self._opened_at = 0.0
        self._next_emit_at = 0.0
        self._next_preview_emit_at = 0.0
        self._sample_period = 1.0 / self.sample_fps
        self._preview_period = (
            1.0 / self.preview_fps if self.preview_fps and self.preview_fps > 0 else None
        )
        self._frame_index = 0
        self._active_backend: Optional[str] = None

    # --- context manager -----------------------------------------------

    def __enter__(self) -> "FrameSource":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # --- core API ------------------------------------------------------

    def open(self) -> None:
        log.info("Opening video source: %s (backend hint=%s)", self.coerced_source, self.backend)
        cap, active = _open_video_capture(
            self.coerced_source,
            self.backend,
            capture_width=self.capture_width,
            capture_height=self.capture_height,
            capture_fps=self.capture_fps,
        )
        self._cap = cap
        self._active_backend = active
        self._opened_at = time.monotonic()
        self._next_emit_at = 0.0
        self._next_preview_emit_at = 0.0
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

            if (
                self.preview_callback is not None
                and self._preview_period is not None
                and now_rel >= self._next_preview_emit_at
            ):
                self._next_preview_emit_at = now_rel + self._preview_period
                try:
                    self.preview_callback(frame)
                except Exception as e:
                    log.debug("preview_callback failed: %s", e)

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
    backend: Optional[VideoBackend] = "auto",
    preview_fps: Optional[float] = None,
    preview_callback: Optional[callable] = None,
    capture_width: Optional[int] = None,
    capture_height: Optional[int] = None,
    capture_fps: Optional[float] = None,
) -> FrameSource:
    """Functional convenience wrapper — does not open the device yet."""
    return FrameSource(
        source=source,
        sample_fps=sample_fps,
        resize_width=resize_width,
        read_timeout_sec=read_timeout_sec,
        log_every=log_every,
        backend=backend,
        preview_fps=preview_fps,
        preview_callback=preview_callback,
        capture_width=capture_width,
        capture_height=capture_height,
        capture_fps=capture_fps,
    )
