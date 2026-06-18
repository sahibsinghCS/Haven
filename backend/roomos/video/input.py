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
from typing import Any, Callable, Iterator, List, Optional, Sequence, Tuple, Union

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


# Hypervisor / link-local prefixes — not where phones usually live; skipping
# them avoids doubling scan time when VirtualBox/WSL adapters are present.
_IGNORED_LAN_PREFIXES = frozenset({"192.168.56.", "169.254."})


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
        if prefix in _IGNORED_LAN_PREFIXES and prefix != preferred_prefix:
            continue
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


def _droidcam_scan_ports(
    preferred_port: Optional[int] = None,
) -> List[int]:
    ports: List[int] = []
    for p in (preferred_port, *_DROIDCAM_DEFAULT_PORTS):
        if p and int(p) not in ports:
            ports.append(int(p))
    return ports


def _droidcam_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/video"


_DISCOVERY_CACHE_TTL_SEC = 30.0
_discovery_cond = threading.Condition()
_discovery_cache: dict[tuple, tuple[float, List[str]]] = {}
_discovery_scanning: set[tuple] = set()


def clear_droidcam_discovery_cache() -> None:
    """Drop cached LAN scan results (tests / forced refresh)."""
    with _discovery_cond:
        _discovery_cache.clear()
        _discovery_scanning.clear()
        _discovery_cond.notify_all()


def discover_all_droidcam_urls(
    *,
    preferred_port: Optional[int] = None,
    preferred_prefix: Optional[str] = None,
    connect_timeout: float = 0.3,
    max_workers: int = 200,
    refresh: bool = False,
    pinned_hosts: Optional[Sequence[str]] = None,
) -> List[str]:
    """Scan localhost + LAN for **all** reachable DroidCam HTTP feeds.

    Each phone runs its own server (unique IP). Multi-room ``droidcam:auto``
    rooms each claim the next unassigned URL from this list.

    Results are cached briefly and concurrent callers share a single in-flight
    scan so the API stays responsive when the UI lists cameras repeatedly.

    Pass ``refresh=True`` to bypass the cache (UI Rescan). ``pinned_hosts`` are
    probed before the /24 sweep so known phones are found quickly.
    """
    if refresh:
        clear_droidcam_discovery_cache()
    pin_key = tuple(pinned_hosts or ())
    key = (preferred_port, preferred_prefix, round(connect_timeout, 3), max_workers, pin_key)
    with _discovery_cond:
        entry = _discovery_cache.get(key)
        if entry and time.monotonic() - entry[0] < _DISCOVERY_CACHE_TTL_SEC:
            return list(entry[1])
        while key in _discovery_scanning:
            _discovery_cond.wait(timeout=90.0)
            entry = _discovery_cache.get(key)
            if entry and time.monotonic() - entry[0] < _DISCOVERY_CACHE_TTL_SEC:
                return list(entry[1])
        _discovery_scanning.add(key)

    try:
        urls = _discover_all_droidcam_urls_uncached(
            preferred_port=preferred_port,
            preferred_prefix=preferred_prefix,
            connect_timeout=connect_timeout,
            max_workers=max_workers,
            pinned_hosts=pinned_hosts,
        )
    finally:
        with _discovery_cond:
            _discovery_cache[key] = (time.monotonic(), list(urls))
            _discovery_scanning.discard(key)
            _discovery_cond.notify_all()
    return urls


def _discover_all_droidcam_urls_uncached(
    *,
    preferred_port: Optional[int] = None,
    preferred_prefix: Optional[str] = None,
    connect_timeout: float = 0.3,
    max_workers: int = 200,
    pinned_hosts: Optional[Sequence[str]] = None,
) -> List[str]:
    import concurrent.futures

    ports = _droidcam_scan_ports(preferred_port)
    found: List[str] = []
    seen_hosts: set[str] = set()

    for raw_host in pinned_hosts or ():
        host = str(raw_host).strip()
        if not host or host in seen_hosts:
            continue
        for port in ports:
            if _droidcam_port_open(host, port, timeout_sec=connect_timeout):
                url = _droidcam_url(host, port)
                if url not in found:
                    found.append(url)
                    seen_hosts.add(host)
                    log.info("DroidCam found at %s (pinned host)", url)
                break

    for host in _DROIDCAM_DEFAULT_HOSTS:
        for port in ports:
            if _droidcam_port_open(host, port):
                url = _droidcam_url(host, port)
                if url not in found:
                    found.append(url)
                    log.info("DroidCam found at %s (localhost)", url)

    subnets = _lan_subnets(preferred_prefix=preferred_prefix)
    if not subnets:
        return found

    tasks: List[Tuple[str, int]] = []
    for prefix in subnets:
        for octet in range(1, 255):
            host = f"{prefix}{octet}"
            if host in ("127.0.0.1", "localhost") or host in seen_hosts:
                continue
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

    for host, port in sorted(open_hosts, key=lambda hp: (hp[0], hp[1])):
        if host in seen_hosts:
            continue
        seen_hosts.add(host)
        url = _droidcam_url(host, port)
        if url not in found:
            found.append(url)
            log.info("DroidCam discovered at %s (LAN)", url)
    return found


def discover_droidcam_url(
    *,
    preferred_port: Optional[int] = None,
    preferred_prefix: Optional[str] = None,
    connect_timeout: float = 0.3,
    max_workers: int = 200,
    exclude_urls: Optional[set[str]] = None,
    refresh: bool = False,
    pinned_hosts: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Return the first DroidCam URL not already in *exclude_urls*."""
    exclude = exclude_urls or set()
    urls = discover_all_droidcam_urls(
        preferred_port=preferred_port,
        preferred_prefix=preferred_prefix,
        connect_timeout=connect_timeout,
        max_workers=max_workers,
        refresh=refresh,
        pinned_hosts=pinned_hosts,
    )
    for url in urls:
        if url not in exclude:
            return url
    return None


def _probe_droidcam(exclude_urls: Optional[set[str]] = None) -> Optional[str]:
    """Return a working DroidCam URL (localhost then LAN), or None."""
    return discover_droidcam_url(exclude_urls=exclude_urls)


def collect_claimed_droidcam_urls(
    rooms: Sequence[Any],
    *,
    skip_room_id: Optional[str] = None,
) -> set[str]:
    """DroidCam HTTP URLs already assigned to other rooms (stable by room id).

    Each ``droidcam:auto`` room claims the next free phone on the network so
    multiple rooms can all use auto-discover without colliding. Assignments are
    computed for *all* rooms in sorted id order, then URLs for rooms other than
    *skip_room_id* are returned.
    """
    used: set[str] = set()
    room_urls: dict[str, str] = {}
    ordered = sorted(rooms, key=lambda r: str(getattr(r, "id", "")))
    for room in ordered:
        rid = str(getattr(room, "id", ""))
        camera = getattr(room, "camera", None)
        src = getattr(camera, "source", None) if camera is not None else None
        if is_auto_video_source(src):
            url = discover_droidcam_url(exclude_urls=used)
            if url:
                used.add(url)
                room_urls[rid] = url
        elif isinstance(src, str) and is_phone_stream_url(src):
            used.add(src)
            room_urls[rid] = src
    if skip_room_id:
        return {url for rid, url in room_urls.items() if rid != skip_room_id}
    return used


@dataclass(frozen=True)
class ResolvedVideoSource:
    """Result of resolving ``video.source: auto`` to a concrete capture target."""

    source: Optional[Union[int, str]]
    backend: str
    unresolved: bool = False


def is_auto_video_source(source: VideoSourceLike) -> bool:
    """True when the config requests silent phone-stream discovery."""
    if isinstance(source, int):
        return False
    return str(source).strip().lower() in ("auto", "droidcam:auto")


def is_phone_stream_url(value: str) -> bool:
    """True for HTTP MJPEG phone streams (including saved discovery URLs)."""
    return _is_droidcam_url(value)


def user_camera_error(detail: Optional[str] = None) -> str:
    """Generic camera error for API/UI — no vendor-specific wording."""
    base = (
        "Could not open camera. Choose a device below or close other apps using the webcam."
    )
    if detail:
        return f"{base} ({detail})"
    return base


def resolve_video_source(
    source: VideoSourceLike,
    *,
    backend: str = "auto",
    exclude_urls: Optional[set[str]] = None,
) -> ResolvedVideoSource:
    """Resolve ``auto`` / ``droidcam:auto`` to a concrete OpenCV source.

    Pass *exclude_urls* (phones already used by other rooms) so each auto room
    binds a distinct DroidCam feed. Does not fall back to a local webcam when
    auto-discovery fails.
    """
    if isinstance(source, str):
        sl = source.strip().lower()
        if sl in ("auto", "droidcam:auto"):
            url = _probe_droidcam(exclude_urls=exclude_urls)
            if url:
                log.info("Resolved %r -> %s", source, url)
                return ResolvedVideoSource(source=url, backend="auto")
            log.info("Resolved %r: no phone stream found (camera setup required)", source)
            return ResolvedVideoSource(source=None, backend=backend, unresolved=True)
        if source.isdigit():
            return ResolvedVideoSource(source=int(source), backend=backend)
    return ResolvedVideoSource(source=source, backend=backend)


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


# Max bytes we let the MJPEG parse buffer grow to before discarding stale data.
# A backlog this large only happens on a corrupt/never-terminated stream or a
# huge frame; we keep the tail (newest partial frame) and drop the rest.
_MJPEG_MAX_BUFFER = 16_000_000
# Per-read chunk size. Large so a single read can swallow several queued frames
# (draining the socket backlog) instead of trickling 8 KB at a time.
_MJPEG_READ_CHUNK = 262_144


class _MjpegHttpCapture:
    """VideoCapture-like reader for DroidCam-style MJPEG over HTTP (stdlib).

    Latency control: DroidCam pushes frames continuously. If the consumer
    (JPEG decode + ML pipeline) can't keep up, frames pile up in the OS socket
    receive buffer and Python's buffered HTTP reader. To keep latency bounded we
    drain *everything* currently waiting on the socket before decoding, then only
    decode the single freshest complete JPEG and discard the backlog without
    decoding the intermediate frames.
    """

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

        # Underlying buffered socket reader. Used for non-blocking draining via
        # ``select`` so we can skip stale frames. Falls back to plain blocking
        # reads if anything here is unavailable (e.g. a mocked response).
        self._fp = getattr(self._resp, "fp", None)
        self._fileno: Optional[int] = None
        if self._fp is not None and hasattr(self._fp, "read1"):
            try:
                self._fileno = self._fp.fileno()
            except Exception:
                self._fileno = None

    def isOpened(self) -> bool:
        return self._opened

    def read(self):
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

    def _read_chunk(self, size: int) -> bytes:
        """Read up to ``size`` bytes, returning as soon as *any* data is ready.

        ``read1`` avoids the blocking-until-full behaviour of ``read`` so a
        partially-arrived frame doesn't stall us, which keeps latency low.
        """
        if self._fp is not None and hasattr(self._fp, "read1"):
            return self._fp.read1(size)
        return self._resp.read(size)

    def _drain_available(self) -> None:
        """Pull all bytes currently waiting on the socket (non-blocking).

        This is what bounds latency: any frames queued behind the freshest one
        are appended to the buffer here so the parser can skip straight to the
        newest complete JPEG instead of decoding the backlog frame by frame.
        """
        if self._fileno is None:
            return
        import select

        while True:
            try:
                readable, _, _ = select.select([self._fileno], [], [], 0.0)
            except (OSError, ValueError):
                # Socket/select unusable on this platform — stop draining and
                # fall back to plain blocking reads for the rest of the session.
                self._fileno = None
                return
            if not readable:
                return
            try:
                chunk = self._read_chunk(_MJPEG_READ_CHUNK)
            except (OSError, ValueError):
                return
            if not chunk:
                return
            self._buffer += chunk
            if len(self._buffer) > _MJPEG_MAX_BUFFER:
                self._trim_buffer_to_latest()
                return

    def _trim_buffer_to_latest(self) -> None:
        """Drop everything before the last JPEG start marker (cap memory)."""
        soi = b"\xff\xd8"
        keep = self._buffer.rfind(soi)
        if keep > 0:
            self._buffer = self._buffer[keep:]
        elif keep < 0:
            self._buffer = self._buffer[-_MJPEG_READ_CHUNK:]

    def _read_jpeg_frame(self) -> Optional[np.ndarray]:
        import cv2

        soi = b"\xff\xd8"
        eoi = b"\xff\xd9"
        while True:
            # Swallow any backlog sitting on the socket so we decode the freshest
            # frame, not a stale one. Without this, a consumer that falls behind
            # makes latency grow without bound.
            self._drain_available()

            # Jump to the *most recent* complete JPEG and drop everything before
            # it, keeping any trailing partial frame for next time.
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
            if len(self._buffer) > _MJPEG_MAX_BUFFER:
                # Corrupt/never-terminated stream: avoid unbounded growth.
                self._trim_buffer_to_latest()
            # Nothing complete buffered yet — block briefly for more data.
            chunk = self._read_chunk(_MJPEG_READ_CHUNK)
            if not chunk:
                return None
            self._buffer += chunk


def _open_droidcam_virtual_webcam(
    *,
    capture_width: Optional[int] = None,
    capture_height: Optional[int] = None,
    capture_fps: Optional[float] = None,
) -> Optional[tuple[Any, str]]:
    """Open DroidCam's Windows virtual webcam when the Wi-Fi HTTP feed is busy."""
    candidates: list[tuple[Union[int, str], str]] = []
    for cam in list_available_cameras(max_index=6):
        label = str(cam.get("label") or "").lower()
        hint = str(cam.get("device_hint") or "").lower()
        if "droidcam" not in label and "droidcam" not in hint:
            continue
        src = cam.get("source")
        if src is None:
            continue
        backend = str(cam.get("backend") or "dshow")
        candidates.append((src, backend))

    if sys.platform.startswith("win"):
        for idx in (1, 0, 2, 3):
            for backend in ("msmf", "dshow"):
                pair = (idx, backend)
                if pair not in candidates:
                    candidates.append(pair)

    seen: set[tuple[str, str]] = set()
    for src, backend in candidates:
        key = (str(src), backend)
        if key in seen:
            continue
        seen.add(key)
        try:
            cap, active = _open_capture(
                src,
                backend,
                capture_width=capture_width,
                capture_height=capture_height,
                capture_fps=capture_fps,
            )
            log.info(
                "Opened DroidCam virtual webcam %r via %s (HTTP feed was busy)",
                src,
                active,
            )
            return cap, active
        except RuntimeError:
            continue
    return None


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
            try:
                return _open_mjpeg_http(source), "mjpeg-http"
            except RuntimeError as exc:
                if "busy" in str(exc).lower():
                    virtual = _open_droidcam_virtual_webcam(
                        capture_width=capture_width,
                        capture_height=capture_height,
                        capture_fps=capture_fps,
                    )
                    if virtual is not None:
                        return virtual
                raise
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


def _droidcam_list_label(url: str) -> str:
    try:
        from urllib.parse import urlparse

        parsed = urlparse(str(url))
        host = parsed.hostname or "phone"
        if host in ("127.0.0.1", "localhost"):
            return "DroidCam (this PC)"
        return f"DroidCam · {host}"
    except Exception:
        return "DroidCam (phone)"


def list_droidcam_network_cameras(
    *,
    exclude_sources: Optional[set[str]] = None,
    scan: bool = True,
    refresh: bool = False,
    pinned_hosts: Optional[Sequence[str]] = None,
) -> List[dict]:
    """Network DroidCam feeds for the camera picker (one entry per phone)."""
    exclude = exclude_sources or set()
    out: List[dict] = []
    if scan:
        try:
            urls = discover_all_droidcam_urls(
                refresh=refresh,
                pinned_hosts=pinned_hosts,
            )
        except Exception as e:
            log.warning("DroidCam LAN scan failed: %s", e)
            urls = []
    else:
        urls = []

    for idx, url in enumerate(urls):
        if url in exclude:
            continue
        out.append(
            {
                "index": 1000 + idx,
                "source": url,
                "backend": "auto",
                "label": _droidcam_list_label(url),
                "available": True,
                "mean_luma": None,
                "frame_shape": None,
                "kind": "droidcam",
            }
        )

    # Auto-discover assigns the next free phone per room (see collect_claimed_droidcam_urls).
    if "droidcam:auto" not in exclude:
        out.insert(
            0,
            {
                "index": 999,
                "source": "droidcam:auto",
                "backend": "auto",
                "label": "Phone camera (auto-discover)",
                "available": True,
                "mean_luma": None,
                "frame_shape": None,
                "kind": "droidcam_auto",
            },
        )
    return out


def list_onvif_discovered_cameras(
    *,
    exclude_hosts: Optional[set[str]] = None,
    scan: bool = True,
) -> List[dict]:
    """ONVIF cameras found via WS-Discovery (host only — user supplies RTSP creds)."""
    exclude = exclude_hosts or set()
    out: List[dict] = []
    if not scan:
        return out
    try:
        from .onvif_discovery import discover_onvif_hosts

        hosts = discover_onvif_hosts()
    except Exception as e:
        log.warning("ONVIF discovery failed: %s", e)
        hosts = []

    for idx, host in enumerate(hosts):
        if host in exclude:
            continue
        out.append(
            {
                "index": 2000 + idx,
                "source": f"rtsp://{host}:554/",
                "backend": "auto",
                "label": f"ONVIF camera · {host}",
                "available": False,
                "mean_luma": None,
                "frame_shape": None,
                "kind": "onvif",
                "host": host,
                "needsCredentials": True,
            }
        )
    return out


def list_all_cameras_for_ui(
    *,
    max_index: int = 4,
    exclude_sources: Optional[set[str]] = None,
    include_droidcam_scan: bool = True,
    skip_usb_probe: bool = False,
    cached_usb_cameras: Optional[List[dict]] = None,
    droidcam_refresh: bool = False,
    pinned_hosts: Optional[Sequence[str]] = None,
    include_onvif_scan: bool = False,
) -> List[dict]:
    """USB/webcam indices plus discovered DroidCam HTTP streams and ONVIF hosts."""
    if skip_usb_probe and cached_usb_cameras is not None:
        local = list(cached_usb_cameras)
    else:
        local = list_available_cameras(max_index=max_index)
    exclude = exclude_sources or set()
    filtered_local = [c for c in local if str(c.get("source")) not in exclude]
    network = list_droidcam_network_cameras(
        exclude_sources=exclude,
        scan=include_droidcam_scan,
        refresh=droidcam_refresh,
        pinned_hosts=pinned_hosts,
    )
    onvif_exclude = {
        str(c.get("host") or "")
        for c in network
        if c.get("host")
    }
    for src in exclude:
        if isinstance(src, str) and src.startswith("rtsp://"):
            try:
                from urllib.parse import urlparse

                host = urlparse(src).hostname
                if host:
                    onvif_exclude.add(host)
            except Exception:
                pass
    onvif = list_onvif_discovered_cameras(
        exclude_hosts=onvif_exclude,
        scan=include_onvif_scan and include_droidcam_scan,
    )
    return filtered_local + network + onvif


def validate_camera_source(source: VideoSourceLike) -> dict[str, Any]:
    """Lightweight reachability check without holding an OpenCV capture open."""
    if isinstance(source, int) or (isinstance(source, str) and str(source).isdigit()):
        return {
            "ok": True,
            "kind": "usb",
            "message": "Webcam index — connect to verify the feed.",
        }
    s = str(source).strip()
    if is_auto_video_source(s):
        url = discover_droidcam_url(refresh=True)
        if url:
            return {
                "ok": True,
                "kind": "droidcam_auto",
                "resolved": url,
                "message": f"Phone stream found at {url}",
            }
        return {
            "ok": False,
            "kind": "droidcam_auto",
            "message": "No phone stream found on the network. Open DroidCam on the phone and rescan.",
        }
    if s.startswith(("http://", "https://")):
        host, port = _url_host_port(s)
        if host and port and not _droidcam_port_open(host, port, timeout_sec=1.0):
            return {
                "ok": False,
                "kind": "http",
                "message": f"Cannot reach {host}:{port}. Check Wi‑Fi and that the camera app is running.",
            }
        import urllib.error
        import urllib.request

        try:
            resp = urllib.request.urlopen(s, timeout=4.0)
        except urllib.error.URLError as exc:
            return {"ok": False, "kind": "http", "message": str(exc)}
        try:
            peek = resp.read(512)
            ct = str(resp.headers.get("Content-Type") or "").lower()
            body = peek.decode("utf-8", "replace").lower()
            if "droidcam is busy" in body or "droidcam_busy" in body:
                return {
                    "ok": False,
                    "kind": "http",
                    "message": "Camera is busy — another app is using the feed.",
                }
            if "text/html" in ct and peek.lstrip().startswith(b"<!"):
                return {
                    "ok": False,
                    "kind": "http",
                    "message": "Host responded but did not return a video stream.",
                }
            return {"ok": True, "kind": "http", "message": "Stream reachable."}
        finally:
            try:
                resp.close()
            except Exception:
                pass
    if s.startswith("rtsp://"):
        host, port = _url_host_port(s)
        if host:
            port_num = port or 554
            if _droidcam_port_open(host, port_num, timeout_sec=1.0):
                return {
                    "ok": True,
                    "kind": "rtsp",
                    "message": "RTSP host is reachable — connect to verify the stream.",
                }
        return {
            "ok": False,
            "kind": "rtsp",
            "message": "Cannot reach RTSP host. Check IP, port, and credentials.",
        }
    return {"ok": False, "kind": "unknown", "message": "Unsupported camera source."}


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
        self._preview_from_grabber: bool = False
        self._preview_grabber_lock = threading.Lock()

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

        # Network streams and local webcams both buffer in the driver; drain in a
        # background thread so preview always sees the freshest frame.
        self._preview_from_grabber = bool(
            self.preview_callback is not None
            and self._preview_period is not None
            and self.is_live()
        )
        if self.is_live():
            self._start_grabber()

    def _maybe_emit_preview(self, frame: np.ndarray, *, now_rel: float) -> None:
        if (
            self.preview_callback is None
            or self._preview_period is None
            or now_rel < self._next_preview_emit_at
        ):
            return
        self._next_preview_emit_at = now_rel + self._preview_period
        out = frame
        if self.frame_preprocess:
            out = preprocess_frame(frame, self.frame_preprocess)
        try:
            self.preview_callback(out)
        except Exception as e:
            log.debug("preview_callback failed: %s", e)

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
            now_rel = time.monotonic() - self._opened_at
            with self._preview_grabber_lock:
                if self._preview_from_grabber:
                    self._maybe_emit_preview(frame, now_rel=now_rel)
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

            preview_due = (
                not self._preview_from_grabber
                and self.preview_callback is not None
                and self._preview_period is not None
                and now_rel >= self._next_preview_emit_at
            )
            sample_due = now_rel >= self._next_emit_at

            if not preview_due and not sample_due:
                if self._grab_cond is not None:
                    continue
                if self.is_live() and self._grab_cond is None and self._cap is not None:
                    try:
                        self._cap.read()
                    except Exception:
                        pass
                continue

            # Latency control: network streams use the background grabber; local
            # webcams use CAP_PROP_BUFFERSIZE=1 and discard reads above when idle.

            if self.frame_preprocess:
                frame = preprocess_frame(frame, self.frame_preprocess)
            self._last_frame_shape = tuple(frame.shape)

            if (
                not self._preview_from_grabber
                and self.preview_callback is not None
                and self._preview_period is not None
                and preview_due
            ):
                self._next_preview_emit_at = now_rel + self._preview_period
                try:
                    self.preview_callback(frame)
                except Exception as e:
                    log.debug("preview_callback failed: %s", e)

            # Sample-rate gating: only emit if enough wall-time has passed.
            if not sample_due:
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
