"""Camera source resolution and user-facing labels."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.state import describe_video_source
from roomos.config import Config
from roomos.video.input import (
    ResolvedVideoSource,
    is_auto_video_source,
    is_phone_stream_url,
    resolve_video_source,
    user_camera_error,
)


def test_is_auto_video_source() -> None:
    assert is_auto_video_source("auto") is True
    assert is_auto_video_source("droidcam:auto") is True
    assert is_auto_video_source(0) is False
    assert is_auto_video_source("http://192.168.1.1:4747/video") is False


def test_resolve_auto_finds_phone_stream() -> None:
    with patch("roomos.video.input._probe_droidcam", return_value="http://192.168.1.5:4747/video"):
        resolved = resolve_video_source("auto")
    assert resolved.unresolved is False
    assert resolved.source == "http://192.168.1.5:4747/video"


def test_resolve_auto_unresolved_without_stream() -> None:
    with patch("roomos.video.input._probe_droidcam", return_value=None):
        resolved = resolve_video_source("auto", backend="dshow")
    assert resolved.unresolved is True
    assert resolved.source is None
    assert resolved.backend == "dshow"


def test_resolve_explicit_webcam_index() -> None:
    resolved = resolve_video_source(1, backend="dshow")
    assert resolved.unresolved is False
    assert resolved.source == 1
    assert resolved.backend == "dshow"


def test_is_phone_stream_url() -> None:
    assert is_phone_stream_url("http://192.168.1.18:4747/video") is True
    assert is_phone_stream_url("rtsp://cam.local/stream") is False


def test_user_camera_error_generic() -> None:
    msg = user_camera_error()
    assert "DroidCam" not in msg
    assert "camera" in msg.lower()


def test_describe_video_source_generic_labels() -> None:
    cfg = Config({"video": {"source": "auto"}})
    assert describe_video_source(cfg) == "Phone camera"

    cfg2 = Config({"video": {"source": "http://192.168.1.18:4747/video"}})
    assert describe_video_source(cfg2) == "Phone camera"

    cfg3 = Config({"video": {"source": 0}})
    assert describe_video_source(cfg3) == "Webcam 0"

    cfg4 = Config({"video": {"source": "rtsp://192.168.1.1/stream"}})
    assert describe_video_source(cfg4) == "Network camera"


def test_list_cameras_excludes_droidcam_auto_entry() -> None:
    from app.core.state import state

    with patch(
        "app.core.state.list_all_cameras_for_ui",
        return_value=[],
    ):
        with patch("app.core.state.resolve_video_source") as mock_resolve:
            mock_resolve.return_value = ResolvedVideoSource(
                source=None, backend="dshow", unresolved=True
            )
            payload = state.list_cameras(max_index=2)
    sources = [c.get("source") for c in payload["cameras"]]
    assert "droidcam:auto" not in sources


def test_discover_all_droidcam_urls_dedupes_hosts() -> None:
    from roomos.video.input import clear_droidcam_discovery_cache, discover_all_droidcam_urls

    clear_droidcam_discovery_cache()

    def fake_port_open(host: str, port: int, timeout_sec: float = 0.25) -> bool:
        return host in ("127.0.0.1", "192.168.1.10", "192.168.1.11") and port == 4747

    with patch("roomos.video.input._droidcam_port_open", side_effect=fake_port_open):
        with patch("roomos.video.input._lan_subnets", return_value=["192.168.1."]):
            urls = discover_all_droidcam_urls()
    assert "http://127.0.0.1:4747/video" in urls
    assert "http://192.168.1.10:4747/video" in urls
    assert "http://192.168.1.11:4747/video" in urls
    assert len(urls) == 3


def test_discover_all_droidcam_urls_single_flight() -> None:
    from roomos.video.input import clear_droidcam_discovery_cache, discover_all_droidcam_urls

    clear_droidcam_discovery_cache()
    scan_calls = 0

    def fake_uncached(**kwargs):
        nonlocal scan_calls
        scan_calls += 1
        return ["http://192.168.1.10:4747/video"]

    with patch(
        "roomos.video.input._discover_all_droidcam_urls_uncached",
        side_effect=fake_uncached,
    ):
        first = discover_all_droidcam_urls()
        second = discover_all_droidcam_urls()
    assert first == second
    assert scan_calls == 1


def test_list_droidcam_shows_auto_with_multiple_phones() -> None:
    from roomos.video.input import list_droidcam_network_cameras

    urls = [
        "http://192.168.1.10:4747/video",
        "http://192.168.1.11:4747/video",
    ]
    with patch("roomos.video.input.discover_all_droidcam_urls", return_value=urls):
        cams = list_droidcam_network_cameras()
    sources = [c["source"] for c in cams]
    assert "droidcam:auto" in sources
    assert urls[0] in sources
    assert urls[1] in sources


def test_resolve_auto_skips_claimed_phones() -> None:
    first = "http://192.168.1.10:4747/video"
    second = "http://192.168.1.11:4747/video"
    with patch(
        "roomos.video.input.discover_all_droidcam_urls",
        return_value=[first, second],
    ):
        resolved = resolve_video_source("droidcam:auto", exclude_urls={first})
    assert resolved.source == second


def test_collect_claimed_droidcam_urls_two_auto_rooms() -> None:
    from types import SimpleNamespace

    from roomos.video.input import collect_claimed_droidcam_urls

    urls = [
        "http://192.168.1.10:4747/video",
        "http://192.168.1.11:4747/video",
    ]

    def fake_discover(*, exclude_urls=None, **kwargs):
        exclude = exclude_urls or set()
        for url in urls:
            if url not in exclude:
                return url
        return None

    rooms = [
        SimpleNamespace(id="a", camera=SimpleNamespace(source="droidcam:auto")),
        SimpleNamespace(id="b", camera=SimpleNamespace(source="droidcam:auto")),
    ]
    with patch("roomos.video.input.discover_droidcam_url", side_effect=fake_discover):
        claimed_a = collect_claimed_droidcam_urls(rooms, skip_room_id="a")
        claimed_b = collect_claimed_droidcam_urls(rooms, skip_room_id="b")
    assert claimed_a == {urls[1]}
    assert claimed_b == {urls[0]}


def test_discover_pinned_hosts_first() -> None:
    from roomos.video.input import clear_droidcam_discovery_cache, discover_all_droidcam_urls

    clear_droidcam_discovery_cache()

    def fake_port_open(host: str, port: int, timeout_sec: float = 0.25) -> bool:
        return host == "192.168.1.10" and port == 4747

    with patch("roomos.video.input._droidcam_port_open", side_effect=fake_port_open):
        with patch("roomos.video.input._lan_subnets", return_value=[]):
            urls = discover_all_droidcam_urls(pinned_hosts=["192.168.1.10"])
    assert urls == ["http://192.168.1.10:4747/video"]


def test_discover_refresh_clears_cache() -> None:
    from roomos.video.input import clear_droidcam_discovery_cache, discover_all_droidcam_urls

    clear_droidcam_discovery_cache()
    scan_calls = 0

    def fake_uncached(**kwargs):
        nonlocal scan_calls
        scan_calls += 1
        return ["http://192.168.1.10:4747/video"]

    with patch(
        "roomos.video.input._discover_all_droidcam_urls_uncached",
        side_effect=fake_uncached,
    ):
        discover_all_droidcam_urls()
        discover_all_droidcam_urls(refresh=True)
    assert scan_calls == 2
