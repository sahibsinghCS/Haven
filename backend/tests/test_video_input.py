"""Video input helpers (MJPEG fallback, remote source detection)."""

from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from roomos.video.input import (
    _MjpegHttpCapture,
    _is_remote_video_source,
    _mjpeg_connect_error,
    _should_fallback_to_webcam,
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
