"""Video input helpers (MJPEG fallback, remote source detection)."""

from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch  # noqa: F401 — patch used in tests below

import pytest

from roomos.video.input import (
    _MjpegHttpCapture,
    _is_remote_video_source,
    _mjpeg_connect_error,
    _should_fallback_to_webcam,
    resolve_video_source,
)


def test_is_remote_video_source() -> None:
    assert _is_remote_video_source(0) is False
    assert _is_remote_video_source("1") is False
    assert _is_remote_video_source("droidcam:auto") is True
    assert _is_remote_video_source("http://192.168.1.18:4747/video") is True


def test_mjpeg_connect_error_message() -> None:
    cause = urllib.error.URLError("connection refused")
    err = _mjpeg_connect_error("http://127.0.0.1:4747/video", cause)
    assert isinstance(err, RuntimeError)
    assert "DroidCam" in str(err)
    assert "127.0.0.1:4747" in str(err)


def test_should_not_fallback_to_webcam_for_remote_sources() -> None:
    assert _should_fallback_to_webcam("droidcam:auto") is False
    assert _should_fallback_to_webcam("http://192.168.1.18:4747/video") is False
    assert _should_fallback_to_webcam(0) is False
    assert _should_fallback_to_webcam("1") is False


def test_mjpeg_http_capture_droidcam_busy_html() -> None:
    html = b"<!doctype html><html><h5>DroidCam is Busy</h5></html>"
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "text/html; charset=UTF-8"}
    mock_resp.read.return_value = html

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="DroidCam at .+ is busy"):
            _MjpegHttpCapture("http://192.168.1.18:4747/video")


def test_mjpeg_http_capture_urlerror_becomes_runtime_error() -> None:
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        with pytest.raises(RuntimeError, match="Could not connect to MJPEG"):
            _MjpegHttpCapture("http://127.0.0.1:4747/video")


def test_resolve_droidcam_auto_unresolved() -> None:
    with patch("roomos.video.input._probe_droidcam", return_value=None):
        resolved = resolve_video_source("droidcam:auto")
    assert resolved.unresolved is True
    assert resolved.source is None


def test_open_video_capture_falls_back_to_virtual_webcam_when_http_busy() -> None:
    from roomos.video.input import _open_video_capture

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, __import__("numpy").zeros((480, 640, 3), dtype="uint8"))
    mock_cap.get.side_effect = lambda prop: {5: 640, 4: 480}.get(prop, 0)

    busy = RuntimeError("DroidCam at http://192.168.1.18:4747/video is busy")

    with patch("roomos.video.input._open_mjpeg_http", side_effect=busy):
        with patch(
            "roomos.video.input._open_droidcam_virtual_webcam",
            return_value=(mock_cap, "dshow"),
        ) as virtual:
            cap, backend = _open_video_capture(
                "http://192.168.1.18:4747/video",
                "auto",
            )
    virtual.assert_called_once()
    assert cap is mock_cap
    assert backend == "dshow"


def test_frame_source_fallback_to_webcam() -> None:
    from roomos.video.input import FrameSource

    fs = FrameSource(
        "http://192.168.1.18:4747/video",
        fallback_to_webcam=True,
    )
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, __import__("numpy").zeros((480, 640, 3), dtype="uint8"))
    mock_cap.get.side_effect = lambda prop: {5: 640, 4: 480}.get(prop, 0)

    with patch("roomos.video.input._open_video_capture", side_effect=[RuntimeError("offline"), (mock_cap, "dshow")]):
        with patch(
            "roomos.video.input.list_available_cameras",
            return_value=[{"source": 0, "backend": "dshow", "label": "Integrated Camera", "available": True}],
        ):
            with fs:
                assert fs.coerced_source == 0
                assert fs.backend == "dshow"


def test_frame_source_no_grabber_for_webcam_index() -> None:
    from roomos.video.input import FrameSource

    fs = FrameSource(0, sample_fps=6.0)
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, __import__("numpy").zeros((480, 640, 3), dtype="uint8"))
    mock_cap.get.side_effect = lambda prop: {5: 640, 4: 480}.get(prop, 0)

    with patch("roomos.video.input._open_video_capture", return_value=(mock_cap, "dshow")):
        fs.open()
    try:
        assert fs._grab_thread is None
        assert fs._grab_cond is None
    finally:
        fs.close()


def test_frame_source_starts_grabber_for_network_url() -> None:
    from roomos.video.input import FrameSource

    fs = FrameSource("http://192.168.1.18:4747/video", sample_fps=6.0)
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, __import__("numpy").zeros((480, 640, 3), dtype="uint8"))
    mock_cap.get.side_effect = lambda prop: {5: 640, 4: 480}.get(prop, 0)

    with patch("roomos.video.input._open_video_capture", return_value=(mock_cap, "mjpeg-http")):
        fs.open()
    try:
        assert fs._grab_thread is not None
        assert fs._grab_cond is not None
    finally:
        fs.close()


def test_preview_hub_wait_for_new_frame() -> None:
    from app.core.state import PreviewHub

    hub = PreviewHub()
    hub.push_from_thread(b"frame-1", mean_luma=128.0)
    jpeg, gen = hub.wait_for_new_frame(-1, timeout=0.1)
    assert jpeg == b"frame-1"
    assert gen == 1
    same, same_gen = hub.wait_for_new_frame(gen, timeout=0.05)
    assert same == b"frame-1"
    assert same_gen == 1
