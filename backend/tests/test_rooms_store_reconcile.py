"""Rooms store camera reconciliation with legacy camera_selection.json."""

from __future__ import annotations

import json
from pathlib import Path

from roomos.rooms.store import RoomsStore


def test_reconcile_webcam_zero_with_droidcam_prefs(tmp_path: Path) -> None:
    rooms_path = tmp_path / "rooms.json"
    prefs_path = tmp_path / "camera_selection.json"
    prefs_path.write_text(
        json.dumps(
            {"source": "http://192.168.1.18:4747/video", "backend": "auto"},
            indent=2,
        ),
        encoding="utf-8",
    )
    rooms_path.write_text(
        json.dumps(
            {
                "rooms": [
                    {
                        "id": "room-1",
                        "name": "Main",
                        "enabled": True,
                        "camera": {"source": 0, "backend": "auto"},
                        "deviceIds": [],
                    }
                ],
                "activeRoomId": "room-1",
                "orchestrator": {
                    "mode": "away",
                    "graceStartedAt": None,
                    "graceDurationSec": 60,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    import roomos.rooms.store as store_mod

    original = store_mod._CAMERA_PREFS_PATH
    store_mod._CAMERA_PREFS_PATH = prefs_path
    try:
        store = RoomsStore(path=rooms_path)
        room = store.get_room("room-1")
        assert room is not None
        assert room.camera.source == "http://192.168.1.18:4747/video"
        saved = json.loads(rooms_path.read_text(encoding="utf-8"))
        assert saved["rooms"][0]["camera"]["source"] == "http://192.168.1.18:4747/video"
    finally:
        store_mod._CAMERA_PREFS_PATH = original
