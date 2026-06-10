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

import contextlib
import logging
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, List, Optional, Tuple, Union

import numpy as np

from ..utils.logging import get_logger
from .frame_preprocess import preprocess_frame

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


@contextlib.contextmanager
def _quiet_opencv():
    """Hide benign OpenCV WARN spam when probing missing webcam indices."""
    import cv2

    logging_mod = getattr(getattr(cv2, "utils", None), "logging", None)
    if logging_mod is None:
        yield
        return
    prev = logging_mod.getLogLevel()
    logging_mod.setLogLevel(logging_mod.LOG_LEVEL_ERROR)
    try:
        yield
    finally:
        logging_mod.setLogLevel(prev)


def _windows_video_device_names() -> List[str]:
    if not sys.platform.startswith("win"):
        return []
    return [n for n in _list_windows_dshow_names() if "audio" not in n.lower()]


def _effective_probe_max_index(max_index: int) -> int:
    """Do not probe webcam indices that cannot exist (reduces DSHOW noise on Windows)."""
    max_index = max(0, int(max_index))
    if sys.platform.startswith("win"):
        names = _windows_video_device_names()
        if names:
            return min(max_index, len(names) - 1)
        return min(max_index, 2)
    return max_index


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


def _is_remote_video_source(source: VideoSourceLike) -> bool:
    """True for HTTP/RTSP URLs and droidcam:auto (not local webcam indices)."""
    if isinstance(source, int):
        return False
    s = str(source)
    if s.isdigit():
        return False
    if s == "droidcam:auto":
        return True
    return "://" in s


def _mjpeg_connect_error(url: str, exc: BaseException) -> RuntimeError:
    return RuntimeError(
        f"Could not connect to MJPEG camera at {url}: {exc}. "
        "If this is DroidCam, open the DroidCam app on your phone and the PC client, "
        "then confirm live video works in DroidCam. "
        "Or pick a different camera: npm run probe:cameras"
    )


def _droidcam_busy_error(url: str) -> RuntimeError:
    return RuntimeError(
        f"DroidCam at {url} is busy (another app is using the feed). "
        "Quit the DroidCam Windows client (File -> Exit) and any other app using the "
        "phone camera, then reload /live. Or pick the DroidCam virtual webcam in the "
        "camera menu: npm run probe:cameras"
    )


def _mjpeg_not_stream_error(url: str, content_type: str) -> RuntimeError:
    return RuntimeError(
        f"Expected an MJPEG video stream at {url} but got {content_type or 'non-video'} "
        "content. If this is DroidCam, confirm the phone app is connected and the URL "
        "shows live video in a browser. Or run: npm run probe:cameras"
    )


def _should_fallback_to_webcam(source: VideoSourceLike) -> bool:
    """Never silently fall back to a local webcam for network/DroidCam sources.

    Falling back to a dark integrated webcam looks like a broken flash-then-black
    feed. Surface the DroidCam error instead so the user can free the stream.
    """
    return False


def _local_ipv4s() -> List[str]:
    """Best-effort list of this machine's IPv4 addresses across all NICs."""
    import socket

    ips: set[str] = set()
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    # The hostname trick can miss the active interface; ask the OS which local
    # address it would use to reach a few common gateways/the internet.
    for dest in ("192.168.1.1", "8.8.8.8", "1.1.1.1"):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((dest, 80))
            ips.add(s.getsockname()[0])
        except OSError:
            pass
        finally:
            try:
                s.close()
            except Exception:
                pass
    return [ip for ip in ips if ip and not ip.startswith("127.")]


def _lan_subnets(preferred_prefix: Optional[str] = None) -> List[str]:
    """Unique ``a.b.c.`` /24 prefixes for every local IPv4 interface.

    If ``preferred_prefix`` is given (e.g. the subnet of a previously-working
    DroidCam URL) it is scanned first so the common "phone got a new DHCP lease
    on the same Wi-Fi" case resolves almost instantly.
    """
    prefixes: List[str] = []
    seen: set[str] = set()
    for ip in _local_ipv4s():
        parts = ip.split(".")
        if len(parts) != 4:
            continue
        prefix = ".".join(parts[:3]) + "."
        if prefix not in seen:
            seen.add(prefix)
            prefixes.append(prefix)
    if preferred_prefix and preferred_prefix in prefixes:
        prefixes.remove(preferred_prefix)
        prefixes.insert(0, preferred_prefix)
    elif preferred_prefix and preferred_prefix not in seen:
        prefixes.insert(0, preferred_prefix)
    return prefixes


def _looks_like_droidcam_http(host: str, port: int, timeout: float = 1.2) -> bool:
    """Quick check that ``host:port`` serves a DroidCam-style MJPEG stream."""
    import urllib.request

    url = f"http://{host}:{port}/video"
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
    except Exception:
        return False
    try:
        ct = str(resp.headers.get("Content-Type") or "").lower()
        if "multipart" in ct or "image" in ct:
            return True
        if "text/html" in ct:
            return False
        peek = resp.read(3)
        return peek[:2] == b"\xff\xd8"
    except Exception:
        return False
    finally:
        try:
            resp.close()
        except Exception:
            pass


def discover_droidcam_url(
    *,
    preferred_port: Optional[int] = None,
    preferred_prefix: Optional[str] = None,
    connect_timeout: float = 0.3,
    max_workers: int = 200,
) -> Optional[str]:
    """Scan localhost + the local network(s) for a live DroidCam MJPEG feed.

    Returns the first ``http://host:port/video`` that actually serves frames, or
    ``None``. Used by ``droidcam:auto`` and to auto-heal a saved DroidCam URL
    after the phone's IP changes.
    """
    import concurrent.futures

    ports: List[int] = []
    for p in (preferred_port, *_DROIDCAM_DEFAULT_PORTS):
        if p and int(p) not in ports:
            ports.append(int(p))

    # 1) Localhost first (USB / DroidCam client) — fast and avoids a LAN scan.
    # Do not open /video here: DroidCam allows only one HTTP client and a probe
    # would race with the real capture open immediately after discovery.
    for host in _DROIDCAM_DEFAULT_HOSTS:
        for port in ports:
            if _droidcam_port_open(host, port):
                url = f"http://{host}:{port}/video"
                log.info("DroidCam found at %s (localhost, port %d open)", url, port)
                return url

    # 2) Sweep each local /24 for open DroidCam ports, then verify the stream.
    subnets = _lan_subnets(preferred_prefix=preferred_prefix)
    if not subnets:
        return None

    tasks: List[Tuple[str, int]] = []
    for prefix in subnets:
        for octet in range(1, 255):
            host = f"{prefix}{octet}"
            for port in ports:
                tasks.append((host, port))

    def _probe(hp: Tuple[str, int]) -> Optional[Tuple[str, int]]:
        host, port = hp
        return hp if _droidcam_port_open(host, port, timeout_sec=connect_timeout) else None

    open_hosts: List[Tuple[str, int]] = []
    log.info(
        "Scanning %d host(s) across %d subnet(s) for DroidCam on ports %s…",
        len(tasks),
        len(subnets),
        ports,
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for res in pool.map(_probe, tasks):
            if res is not None:
                open_hosts.append(res)

    for host, port in open_hosts:
        url = f"http://{host}:{port}/video"
        log.info("DroidCam discovered at %s (LAN scan, port %d open)", url, port)
        return url
    return None


def _probe_droidcam() -> Optional[str]:
    """Return a working DroidCam URL (localhost then LAN), or None."""
    return discover_droidcam_url()


def _is_droidcam_url(value: str) -> bool:
    """True for ``http(s)://host:4747/video`` style DroidCam URLs."""
    import urllib.parse

    try:
        parsed = urllib.parse.urlparse(value)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.port in _DROIDCAM_DEFAULT_PORTS:
        return True
    return parsed.path.rstrip("/").endswith("/video")


def _url_host_port(value: str) -> Tuple[Optional[str], Optional[int]]:
    import urllib.parse

    try:
        parsed = urllib.parse.urlparse(value)
        return parsed.hostname, parsed.port
    except ValueError:
        return None, None


# Optional persistence hook so a successful rediscovery can be saved by the app
# layer (set via set_discovery_persist_hook) without coupling video<-app.
_discovery_persist_hook: Optional[Callable[[str], None]] = None


def set_discovery_persist_hook(fn: Optional[Callable[[str], None]]) -> None:
    global _discovery_persist_hook
    _discovery_persist_hook = fn


def _persist_discovered(url: str) -> None:
    if _discovery_persist_hook is None:
        return
    try:
        _discovery_persist_hook(url)
    except Exception as e:  # noqa: BLE001
        log.debug("discovery persist hook failed: %s", e)


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

    chain: List[Tuple[int, str]] = []
    seen: set[str] = set()
    if sys.platform.startswith("win"):
        # DSHOW opens most laptop webcams; MSMF is listed first in many configs but
        # often fails isOpened() on index 0 — try DSHOW before the configured primary.
        for name in ("CAP_DSHOW", primary[1], "CAP_MSMF", "CAP_ANY"):
            if name in seen:
                continue
            api = getattr(cv2, name, None)
            if api is None:
                continue
            chain.append((api, name))
            seen.add(name)
    else:
        chain.append(primary)
        seen.add(primary[1])
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
    if width and height:
        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        except Exception:
            pass
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass


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
            with _quiet_opencv():
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
        import urllib.error
        import urllib.request

        self.url = url
        try:
            self._resp = urllib.request.urlopen(url, timeout=10)
        except urllib.error.URLError as exc:
            raise _mjpeg_connect_error(url, exc) from exc
        content_type = str(self._resp.headers.get("Content-Type") or "").lower()
        peek = self._resp.read(1024)
        if "text/html" in content_type or peek.lstrip().startswith(b"<!"):
            body = peek.decode("utf-8", "replace").lower()
            self._resp.close()
            if "droidcam is busy" in body or "droidcam_busy" in body:
                raise _droidcam_busy_error(url)
            raise _mjpeg_not_stream_error(url, content_type or "text/html")
        self._buffer = peek
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
        while True:
            # Always jump to the *most recent* complete JPEG already buffered and
            # drop everything before it. If the consumer falls behind, frames pile
            # up in the socket/buffer; serving the oldest one (the previous
            # behaviour) made latency grow without bound. We decode only the
            # freshest frame and keep any trailing partial frame for next time.
            last_eoi = self._buffer.rfind(eoi)
            if last_eoi >= 0:
                last_soi = self._buffer.rfind(soi, 0, last_eoi)
                if last_soi >= 0:
                    jpg = self._buffer[last_soi : last_eoi + 2]
                    self._buffer = self._buffer[last_eoi + 2 :]
                    img = cv2.imdecode(
                        np.frombuffer(jpg, dtype=np.uint8),
                        cv2.IMREAD_COLOR,
                    )
                    if img is not None and img.size > 0:
                        return img
                    # Decode failed — keep pulling more bytes.
            if len(self._buffer) > 4_000_000:
                # Corrupt/never-terminated stream: avoid unbounded growth.
                self._buffer = b""
                return None
            chunk = self._resp.read(8192)
            if not chunk:
                return None
            self._buffer += chunk


def _open_mjpeg_http(
    url: str,
    *,
    max_attempts: int = 4,
    retry_delay_sec: float = 0.75,
) -> _MjpegHttpCapture:
    """Open DroidCam-style MJPEG over HTTP (stdlib). Retries when the feed is busy."""
    last_exc: Optional[BaseException] = None
    for attempt in range(1, max_attempts + 1):
        cap: Optional[_MjpegHttpCapture] = None
        try:
            cap = _MjpegHttpCapture(url)
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.release()
                raise RuntimeError(
                    f"Could not read MJPEG frames from {url}. "
                    "If DroidCam Client is open, the HTTP feed is often busy — quit the client "
                    "(File -> Exit) and retry, or use the virtual webcam: npm run probe:cameras "
                    "(on Windows try source=1 backend=msmf for 'DroidCam Video')."
                )
            log.info("Opened video source %r via mjpeg-http", url)
            return cap
        except RuntimeError as exc:
            last_exc = exc
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            msg = str(exc).lower()
            if "busy" in msg and attempt < max_attempts:
                log.warning(
                    "DroidCam busy at %s (attempt %d/%d) — retrying in %.1fs…",
                    url,
                    attempt,
                    max_attempts,
                    retry_delay_sec,
                )
                time.sleep(retry_delay_sec)
                continue
            raise
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"Could not open MJPEG stream at {url}")


def _open_video_capture(
    source: Union[int, str],
    backend: Optional[VideoBackend],
    *,
    capture_width: Optional[int] = None,
    capture_height: Optional[int] = None,
    capture_fps: Optional[float] = None,
):
    """Open OpenCV capture, with HTTP MJPEG reader for DroidCam Wi-Fi URLs."""
    if isinstance(source, str) and "://" in source:
        # OpenCV often fails on DroidCam HTTP and a failed open can mark the feed
        # busy before our MJPEG reader runs — use the stdlib reader directly.
        if _is_droidcam_url(source):
            return _open_mjpeg_http(source), "mjpeg-http"
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
                "No DroidCam HTTP stream found on localhost or the local network. "
                "Start the DroidCam app on your phone (and the PC client for USB), "
                "connect to the same Wi-Fi as this PC, and confirm you see live "
                "video in DroidCam. Then reload /live. "
                "Or use DroidCam's virtual webcam and set video.source to that "
                "index (run: npm run probe:cameras)."
            )
        log.info("droidcam:auto -> %s", probed)
        return probed
    if _is_droidcam_url(s):
        # The phone's DHCP IP can change between sessions. If the saved URL is no
        # longer reachable, scan the LAN and auto-heal to wherever DroidCam is now
        # (so a stale http://<old-ip>:4747/video keeps working on any IP).
        host, port = _url_host_port(s)
        port = port or _DROIDCAM_DEFAULT_PORTS[0]
        if host and not _droidcam_port_open(host, int(port), timeout_sec=0.5):
            log.warning("DroidCam not reachable at %s — scanning the local network…", s)
            prefix = ".".join(host.split(".")[:3]) + "." if host.count(".") == 3 else None
            found = discover_droidcam_url(preferred_port=int(port), preferred_prefix=prefix)
            if found:
                log.info("DroidCam rediscovered at %s (was %s)", found, s)
                _persist_discovered(found)
                return found
            log.warning(
                "DroidCam LAN scan found nothing; trying the saved URL %s anyway.", s
            )
        return s
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


def _probe_one_index(idx: int, bname: str, api: int, *, warm_reads: int) -> dict:
    """Try opening a single (index, backend) pair."""
    import cv2

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
        with _quiet_opencv():
            cap = cv2.VideoCapture(idx, api)
        if not cap.isOpened():
            entry["error"] = "isOpened() == False"
        else:
            best_luma = -1.0
            best_shape: Optional[Tuple[int, ...]] = None
            for _ in range(warm_reads):
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
    return entry


def probe_cameras(max_index: int = 4, *, exhaustive: bool = True) -> List[dict]:
    """Probe webcam indices 0..max_index across known backends.

    Returns a list of dicts ``{index, backend, ok, mean_luma, error}`` so the
    operator can pick a working camera/backend pair when the default goes
    black.

    When ``exhaustive`` is False (UI listing), only probe indices that likely
    exist and stop after the first working backend per index.
    """
    import cv2

    results: List[dict] = []
    if sys.platform.startswith("win"):
        backend_names = ("CAP_DSHOW", "CAP_MSMF", "CAP_ANY")
    elif sys.platform == "darwin":
        backend_names = ("CAP_AVFOUNDATION", "CAP_ANY")
    else:
        backend_names = ("CAP_V4L2", "CAP_ANY")

    dshow_names = _list_windows_dshow_names() if sys.platform.startswith("win") else []
    last_index = _effective_probe_max_index(max_index)
    warm_reads = 8 if exhaustive else 5

    for idx in range(last_index + 1):
        index_opened = False
        for bname in backend_names:
            api = getattr(cv2, bname, None)
            if api is None:
                continue
            entry = _probe_one_index(idx, bname, api, warm_reads=warm_reads)
            results.append(entry)
            if entry["ok"]:
                index_opened = True
                if not exhaustive:
                    break
        if not exhaustive and not index_opened and idx >= 1:
            # No device at this index — higher indices are unlikely on Windows.
            break

    if dshow_names:
        _attach_windows_device_hints(results, dshow_names)
    return results


def _backend_name_to_hint(bname: str) -> str:
    return bname.replace("CAP_", "").lower()


def list_available_cameras(max_index: int = 4) -> List[dict]:
    """Summarize probe results into one entry per webcam index for the UI.

    Each item: ``index``, ``source``, ``backend``, ``label``, ``available``,
    ``mean_luma`` (optional).
    """
    raw = probe_cameras(max_index=max_index, exhaustive=False)
    video_names = _windows_video_device_names()

    best_per_index: dict[int, dict] = {}
    for row in raw:
        if not row.get("ok"):
            continue
        idx = int(row["index"])
        prev = best_per_index.get(idx)
        luma = float(row.get("mean_luma") or 0)
        if prev is None or luma > float(prev.get("mean_luma") or 0):
            best_per_index[idx] = row

    cameras: List[dict] = []
    for idx in range(max_index + 1):
        if idx in best_per_index:
            row = best_per_index[idx]
            hint = row.get("device_hint")
            if not hint and idx < len(video_names):
                hint = video_names[idx]
            cameras.append(
                {
                    "index": idx,
                    "source": idx,
                    "backend": _backend_name_to_hint(str(row["backend"])),
                    "label": str(hint or f"Camera {idx}"),
                    "available": True,
                    "mean_luma": row.get("mean_luma"),
                    "frame_shape": row.get("frame_shape"),
                }
            )
        elif idx < len(video_names):
            cameras.append(
                {
                    "index": idx,
                    "source": idx,
                    "backend": "dshow",
                    "label": video_names[idx],
                    "available": False,
                    "mean_luma": None,
                    "frame_shape": None,
                }
            )

    cameras.sort(key=lambda c: int(c["index"]))
    return cameras


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
    frame_preprocess : dict | None
        Letterbox strip / aspect crop (see ``frame_preprocess.preprocess_frame``).
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
        frame_preprocess: Optional[dict] = None,
        fallback_to_webcam: bool = False,
    ) -> None:
        self.requested_source = source
        self.fallback_to_webcam = bool(fallback_to_webcam)
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
        self.frame_preprocess = dict(frame_preprocess) if frame_preprocess else None

        self._cap = None
        self._capture_size: Optional[tuple[int, int]] = None
        self._last_frame_shape: Optional[tuple[int, ...]] = None
        self._opened_at = 0.0
        self._next_emit_at = 0.0
        self._next_preview_emit_at = 0.0
        self._sample_period = 1.0 / self.sample_fps
        self._preview_period = (
            1.0 / self.preview_fps if self.preview_fps and self.preview_fps > 0 else None
        )
        self._frame_index = 0
        self._active_backend: Optional[str] = None

        # Low-latency grabber: for network streams (DroidCam/HTTP/RTSP) a
        # background thread continuously drains the capture so we always process
        # the freshest frame instead of a growing backlog. Set up in open().
        self._grab_thread: Optional[threading.Thread] = None
        self._grab_stop: Optional[threading.Event] = None
        self._grab_cond: Optional[threading.Condition] = None
        self._latest_grab: Optional[np.ndarray] = None
        self._grab_frame_id: int = 0
        self._grab_consumed_id: int = 0
        self._grab_dead: bool = False

    @property
    def last_frame_shape(self) -> Optional[tuple[int, ...]]:
        return self._last_frame_shape

    @property
    def capture_size(self) -> Optional[tuple[int, int]]:
        return self._capture_size

    # --- context manager -----------------------------------------------

    def __enter__(self) -> "FrameSource":
        try:
            self.open()
        except Exception as primary_exc:
            if not self.fallback_to_webcam or not _is_remote_video_source(self.requested_source):
                raise
            cameras = [c for c in list_available_cameras(max_index=6) if c.get("available")]
            if not cameras:
                raise primary_exc
            fallback = cameras[0]
            log.warning(
                "Could not open %r (%s). Falling back to local webcam %r (index %s).",
                self.requested_source,
                primary_exc,
                fallback.get("label"),
                fallback.get("source"),
            )
            self.requested_source = fallback["source"]
            self.coerced_source = _coerce_source(fallback["source"])
            self.backend = fallback.get("backend") or self.backend
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
        try:
            import cv2

            self._capture_size = (
                int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
            )
            log.info(
                "Capture negotiated: %dx%d (backend=%s)",
                self._capture_size[0],
                self._capture_size[1],
                active,
            )
        except Exception:
            self._capture_size = None
        self._opened_at = time.monotonic()
        self._next_emit_at = 0.0
        self._next_preview_emit_at = 0.0
        self._frame_index = 0

        # Only network streams suffer from buffer-accumulation latency. Local
        # webcams use CAP_PROP_BUFFERSIZE=1 and are read in lock-step, so leave
        # them on the simple sequential path.
        if isinstance(self.coerced_source, str) and "://" in self.coerced_source:
            self._start_grabber()

    def _start_grabber(self) -> None:
        """Continuously read the capture in the background, keeping only the
        latest frame. Drains the network buffer so latency stays bounded even if
        the ML pipeline / preview encoding can't keep up with the source FPS."""
        self._grab_stop = threading.Event()
        self._grab_cond = threading.Condition()
        self._latest_grab = None
        self._grab_frame_id = 0
        self._grab_consumed_id = 0
        self._grab_dead = False
        self._grab_thread = threading.Thread(
            target=self._grab_loop,
            args=(self._cap,),
            name="roomos-grab",
            daemon=True,
        )
        self._grab_thread.start()

    def _grab_loop(self, cap) -> None:
        consecutive_failures = 0
        assert self._grab_cond is not None and self._grab_stop is not None
        while not self._grab_stop.is_set():
            try:
                ok, frame = cap.read()
            except Exception as e:  # noqa: BLE001
                log.debug("grabber read raised: %s", e)
                ok, frame = False, None
            if not ok or frame is None:
                consecutive_failures += 1
                # Surface a sustained outage so the iterator's read_timeout fires.
                if consecutive_failures * 0.02 > self.read_timeout_sec:
                    with self._grab_cond:
                        self._grab_dead = True
                        self._grab_cond.notify_all()
                    return
                if self._grab_stop.wait(0.02):
                    return
                continue
            consecutive_failures = 0
            with self._grab_cond:
                self._latest_grab = frame
                self._grab_frame_id += 1
                self._grab_cond.notify_all()

    def _read_source_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Return ``(ok, frame)`` from the grabber (network) or directly (file/webcam)."""
        if self._grab_cond is None:
            return self._cap.read()
        deadline = time.monotonic() + self.read_timeout_sec
        with self._grab_cond:
            while True:
                if (
                    self._grab_frame_id != self._grab_consumed_id
                    and self._latest_grab is not None
                ):
                    self._grab_consumed_id = self._grab_frame_id
                    return True, self._latest_grab
                if self._grab_dead:
                    return False, None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False, None
                self._grab_cond.wait(timeout=min(0.1, remaining))

    def close(self) -> None:
        if self._grab_stop is not None:
            self._grab_stop.set()
            if self._grab_cond is not None:
                with self._grab_cond:
                    self._grab_cond.notify_all()
        thread = self._grab_thread
        thread_alive = False
        if thread is not None:
            thread.join(timeout=3.0)
            thread_alive = thread.is_alive()
            self._grab_thread = None
        self._grab_cond = None
        self._grab_stop = None
        self._latest_grab = None
        if self._cap is not None:
            if thread_alive:
                # Grabber is still blocked inside cap.read(); releasing now could
                # crash OpenCV. Drop our reference and let the daemon thread free
                # the capture when its blocking read returns.
                log.warning("Grabber thread still running on close; deferring capture release.")
            else:
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
            ok, frame = self._read_source_frame()
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

            # Latency control: local webcams use CAP_PROP_BUFFERSIZE=1; network
            # streams are drained by the background grabber (see _start_grabber),
            # which hands us only the freshest frame so a slow ML/preview loop
            # can't build up a growing backlog of stale frames.

            if self.frame_preprocess:
                frame = preprocess_frame(frame, self.frame_preprocess)
            self._last_frame_shape = tuple(frame.shape)

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
    frame_preprocess: Optional[dict] = None,
    fallback_to_webcam: bool = False,
) -> FrameSource:
    """Functional convenience wrapper — does not open the device yet."""
    return FrameSource(
        source=source,
        sample_fps=sample_fps,
        resize_width=resize_width,
        read_timeout_sec=read_timeout_sec,
        log_every=log_every,
        backend=backend,
        fallback_to_webcam=fallback_to_webcam,
        preview_fps=preview_fps,
        preview_callback=preview_callback,
        capture_width=capture_width,
        capture_height=capture_height,
        capture_fps=capture_fps,
        frame_preprocess=frame_preprocess,
    )
