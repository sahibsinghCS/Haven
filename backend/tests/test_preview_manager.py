"""Room preview threads must not open the inference room's camera feed."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from roomos.rooms.models import RoomCamera, RoomRecord
from roomos.rooms.preview_manager import RoomPreviewManager


def test_sync_rooms_skips_inference_room_preview() -> None:
    room = RoomRecord(
        id="room-live",
        name="Lounge",
        enabled=True,
        camera=RoomCamera(source="http://192.168.1.18:4747/video", backend="auto"),
        device_ids=[],
    )
    mgr = RoomPreviewManager(config_path="configs/inference.yaml")
    mgr.set_inference_room("room-live")

    with patch("roomos.rooms.preview_manager._RoomCaptureThread") as thread_cls:
        thread_cls.return_value = MagicMock()
        mgr.sync_rooms([room])

    thread_cls.assert_not_called()
    assert mgr._threads == {}


def test_sync_rooms_stops_existing_inference_room_preview() -> None:
    room = RoomRecord(
        id="room-live",
        name="Lounge",
        enabled=True,
        camera=RoomCamera(source="http://192.168.1.18:4747/video", backend="auto"),
        device_ids=[],
    )
    mgr = RoomPreviewManager(config_path="configs/inference.yaml")
    stale = MagicMock()
    mgr._threads["room-live"] = stale

    mgr.set_inference_room("room-live")
    mgr.sync_rooms([room])

    stale.stop.assert_called_once_with(clear_hub=False)
    assert "room-live" not in mgr._threads


def test_shared_encoder_pushes_to_hub() -> None:
    import numpy as np

    from roomos.rooms.preview_manager import RoomPreviewHub, _SharedRoomPreviewEncoder

    hub = RoomPreviewHub()
    enc = _SharedRoomPreviewEncoder(hub)
    enc.configure(max_width=320, jpeg_quality=80)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    enc.enqueue("room-a", frame)
    deadline = __import__("time").monotonic() + 2.0
    while __import__("time").monotonic() < deadline:
        if hub.latest_jpeg("room-a") is not None:
            break
        __import__("time").sleep(0.05)
    enc.stop()
    assert hub.latest_jpeg("room-a") is not None
