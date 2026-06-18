"""Unit tests for multi-room presence orchestration."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from roomos.inference.live_pipeline import LiveSnapshot
from roomos.rooms.models import RoomCamera, RoomDocument, RoomRecord
from roomos.rooms.orchestrator import (
    GRACE_MOTION_THRESHOLD,
    PresenceOrchestrator,
    _motion_score,
    _resume_mood_from_snapshot,
    _snap_confident_ml_presence,
    _snap_suggests_presence,
)
from roomos.rooms.store import RoomsStore


@pytest.fixture
def rooms_path(tmp_path: Path) -> Path:
    room_id = "room-a"
    doc = RoomDocument(
        rooms=[
            RoomRecord(
                id=room_id,
                name="Lounge",
                enabled=True,
                camera=RoomCamera(source=0, backend="dshow"),
                device_ids=["lights-1"],
            ),
            RoomRecord(
                id="room-b",
                name="Bedroom",
                enabled=True,
                camera=RoomCamera(source=1, backend="dshow"),
                device_ids=["lights-2"],
            ),
        ],
        active_room_id=room_id,
    )
    path = tmp_path / "rooms.json"
    path.write_text(json.dumps(doc.to_dict()), encoding="utf-8")
    return path


def test_rooms_store_migration_assigns_devices(tmp_path: Path) -> None:
    cam_path = tmp_path / "camera_selection.json"
    cam_path.write_text(json.dumps({"source": 0, "backend": "dshow"}), encoding="utf-8")
    store_path = tmp_path / "rooms.json"

    with patch("roomos.rooms.store._CAMERA_PREFS_PATH", cam_path):
        with patch("roomos.rooms.store._ROOMS_PATH", store_path):
            with patch("roomos.rooms.store._all_connected_device_ids", return_value=["plug-1"]):
                store = RoomsStore(path=store_path)
    assert len(store.list_rooms()) == 1
    assert store.list_rooms()[0].device_ids == ["plug-1"]


def test_motion_score_detects_change() -> None:
    a = np.zeros((120, 120, 3), dtype=np.uint8)
    b = a.copy()
    b[:, :] = 255
    assert _motion_score(a, b) >= GRACE_MOTION_THRESHOLD


def test_rooms_store_rejects_duplicate_camera(rooms_path: Path) -> None:
    url = "http://192.168.1.10:4747/video"
    with patch("roomos.rooms.store._reconcile_webcam_zero_with_prefs", return_value=False):
        store = RoomsStore(path=rooms_path)
        store.add_room(name="Office", source=url, backend="auto")
        with pytest.raises(ValueError, match="already assigned"):
            store.add_room(name="Hall", source=url, backend="auto")
        store.add_room(
            name="Porch",
            source="http://192.168.1.11:4747/video",
            backend="auto",
        )
        store.add_room(name="Garage", source="droidcam:auto", backend="auto")
    assert len(store.list_rooms()) == 5


def test_rooms_store_allows_multiple_droidcam_auto(tmp_path: Path) -> None:
    rooms_path = tmp_path / "rooms.json"
    rooms_path.write_text(
        json.dumps(
            {
                "rooms": [],
                "activeRoomId": None,
                "orchestrator": {
                    "mode": "away",
                    "graceStartedAt": None,
                    "graceDurationSec": 60,
                },
            }
        ),
        encoding="utf-8",
    )
    store = RoomsStore(path=rooms_path)
    store.add_room(name="Phone A", source="droidcam:auto", backend="auto")
    store.add_room(name="Phone B", source="droidcam:auto", backend="auto")
    auto_rooms = [r for r in store.list_rooms() if r.camera.source == "droidcam:auto"]
    assert len(auto_rooms) == 2


def test_orchestrator_enters_grace_on_away(rooms_path: Path) -> None:
    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(mode="active")
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch.set_inference_room("room-a")

    snap = LiveSnapshot(primary_state="away", primary_confidence=0.9)
    with patch.object(orch, "_apply_active_room_mood") as apply_mood:
        with patch.object(orch, "_apply_grace_origin_away_devices") as origin_away:
            with patch.object(orch, "_apply_walkway_lights") as walkway:
                with patch.object(orch, "_turn_off_non_active_devices") as turn_off:
                    with patch.object(orch, "_start_grace_scanner") as grace_scan:
                        orch.handle_snapshot("room-a", snap)
                        orch.handle_snapshot("room-a", snap)
                        orch.handle_snapshot("room-a", snap)
    assert store.document().orchestrator.mode == "grace"
    apply_mood.assert_not_called()
    origin_away.assert_called_once_with("room-a")
    walkway.assert_called_once_with(exclude_room_id="room-a")
    turn_off.assert_not_called()
    grace_scan.assert_called_once_with("room-a")


def test_stop_grace_scanner_does_not_join_current_thread(rooms_path: Path) -> None:
    store = RoomsStore(path=rooms_path)
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch._grace_thread = threading.current_thread()
    orch._grace_stop.clear()
    orch._stop_grace_scanner()
    assert orch._grace_thread is None
    assert orch._grace_stop.is_set()


def test_orchestrator_applies_mood_for_active_room(rooms_path: Path) -> None:
    store = RoomsStore(path=rooms_path)
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    store.update_orchestrator(mode="active")
    orch.set_inference_room("room-a")

    snap = LiveSnapshot(primary_state="work", primary_confidence=0.8)
    with patch.object(orch, "_apply_active_room_mood") as apply_mood:
        orch.handle_snapshot("room-a", snap)
    apply_mood.assert_called_once_with("room-a", "work")


def test_resume_from_grace_on_same_room_presence(rooms_path: Path) -> None:
    from roomos.devices.action_arbiter import ActionSource

    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(mode="grace", grace_started_at="2026-01-01T00:00:00+00:00")
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch.set_inference_room("room-a")
    orch._last_mood_by_room["room-a"] = "relaxing"

    snap = LiveSnapshot(primary_state="work", primary_confidence=0.85)
    with patch.object(orch, "_stop_grace_scanner") as stop_scan:
        with patch.object(orch, "_apply_active_room_mood") as apply_mood:
            orch.handle_snapshot("room-a", snap)
            orch.handle_snapshot("room-a", snap)

    stop_scan.assert_called_once()
    apply_mood.assert_called_once_with(
        "room-a",
        "work",
        action_source=ActionSource.ORCHESTRATOR_RESUME,
    )
    assert store.document().orchestrator.mode == "active"
    assert store.document().orchestrator.grace_started_at is None


def test_resume_from_grace_via_burst_probs_while_smoothed_away(rooms_path: Path) -> None:
    from roomos.devices.action_arbiter import ActionSource

    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(mode="grace", grace_started_at="2026-01-01T00:00:00+00:00")
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch.set_inference_room("room-a")
    orch._last_mood_by_room["room-a"] = "work"

    snap = LiveSnapshot(
        primary_state="away",
        primary_confidence=0.7,
        model_probs={"away": 0.3, "work": 0.55, "relaxing": 0.15},
    )
    assert _snap_suggests_presence(snap)

    with patch.object(orch, "_stop_grace_scanner"):
        with patch.object(orch, "_apply_active_room_mood") as apply_mood:
            orch.handle_snapshot("room-a", snap)
            orch.handle_snapshot("room-a", snap)

    apply_mood.assert_called_once_with(
        "room-a",
        "work",
        action_source=ActionSource.ORCHESTRATOR_RESUME,
    )
    assert store.document().orchestrator.mode == "active"


def test_snap_suggests_presence_via_smoothed_distribution() -> None:
    snap = LiveSnapshot(
        primary_state="away",
        primary_confidence=0.7,
        model_probs={"away": 0.4, "work": 0.35, "relaxing": 0.25},
        distribution={"away": 0.32, "work": 0.45, "relaxing": 0.23},
    )
    assert _snap_suggests_presence(snap)
    assert _resume_mood_from_snapshot(snap, fallback="work") == "work"


def _prime_active_empty(
    orch: PresenceOrchestrator, room_id: str, *, count: int = 3
) -> None:
    away_snap = LiveSnapshot(primary_state="away", primary_confidence=0.85)
    for _ in range(count):
        orch.handle_snapshot(room_id, away_snap)


def test_grace_promotes_other_room_on_ml_presence(rooms_path: Path) -> None:
    from roomos.devices.action_arbiter import ActionSource

    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(
        mode="grace",
        grace_started_at="2026-01-01T00:00:00+00:00",
    )
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch.set_inference_rooms({"room-a", "room-b"})
    orch._last_label_by_room["room-a"] = "away"
    _prime_active_empty(orch, "room-a")

    snap = LiveSnapshot(primary_state="work", primary_confidence=0.9)
    with patch.object(orch, "_stop_grace_scanner"):
        with patch.object(orch, "_apply_active_room_mood") as apply_mood:
            with patch.object(orch, "_turn_off_non_active_devices"):
                for _ in range(3):
                    orch.handle_snapshot("room-b", snap)

    assert store.document().active_room_id == "room-b"
    assert store.document().orchestrator.mode == "active"
    apply_mood.assert_called_once_with(
        "room-b",
        "work",
        action_source=ActionSource.ORCHESTRATOR_RESUME,
    )


def test_single_away_burst_does_not_enter_grace(rooms_path: Path) -> None:
    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(mode="active")
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    snap = LiveSnapshot(primary_state="away", primary_confidence=0.9)
    with patch.object(orch, "_enter_grace") as enter_grace:
        orch.handle_snapshot("room-a", snap)
        orch.handle_snapshot("room-a", snap)
    enter_grace.assert_not_called()
    assert store.document().orchestrator.mode == "active"


def test_work_after_away_reapplies_same_mood_in_active_mode(rooms_path: Path) -> None:
    from roomos.devices.action_arbiter import ActionSource

    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(mode="active")
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch.set_inference_room("room-a")
    orch._last_mood_by_room["room-a"] = "work"

    away_snap = LiveSnapshot(primary_state="away", primary_confidence=0.9)
    with patch.object(orch, "_apply_walkway_lights"):
        with patch.object(orch, "_start_grace_scanner"):
            for _ in range(3):
                orch.handle_snapshot("room-a", away_snap)
    assert orch._pending_mood_restore.get("room-a") == "work"

    store.update_orchestrator(mode="active", grace_started_at=None)
    work_snap = LiveSnapshot(primary_state="work", primary_confidence=0.95)
    with patch.object(orch, "_apply_active_room_mood") as apply_mood:
        orch.handle_snapshot("room-a", work_snap)

    apply_mood.assert_called_once_with(
        "room-a",
        "work",
        action_source=ActionSource.ORCHESTRATOR_RESUME,
    )


def test_grace_global_away_requires_all_rooms_away(rooms_path: Path) -> None:
    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(
        mode="grace",
        grace_started_at="2026-01-01T00:00:00+00:00",
    )
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch._last_label_by_room["room-a"] = "away"
    orch._last_label_by_room["room-b"] = "work"
    assert not orch._all_enabled_rooms_away()

    orch._last_label_by_room["room-b"] = "away"
    assert orch._all_enabled_rooms_away()


def test_grace_scanner_waits_until_all_rooms_away(rooms_path: Path) -> None:
    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(mode="grace", grace_started_at="2026-01-01T00:00:00+00:00")
    store.update_orchestrator(grace_duration_sec=0)
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch._last_label_by_room["room-a"] = "away"
    orch._last_label_by_room["room-b"] = "work"

    with patch.object(orch, "_enter_global_away") as enter_away:
        orch._start_grace_scanner("room-a")
        orch._grace_thread.join(timeout=5.0)
    enter_away.assert_not_called()

    orch._last_label_by_room["room-b"] = "away"
    with patch.object(orch, "_enter_global_away") as enter_away:
        orch._start_grace_scanner("room-a")
        orch._grace_thread.join(timeout=5.0)
    enter_away.assert_called_once()


def test_main_leave_grace_bedroom_promote_turns_off_main(rooms_path: Path) -> None:
    """Main → grace (lights stay) → bedroom presence → active bedroom, main devices off."""
    from roomos.devices.action_arbiter import ActionSource

    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(mode="active")
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch.set_inference_rooms({"room-a", "room-b"})
    orch._last_mood_by_room["room-a"] = "work"

    away_snap = LiveSnapshot(primary_state="away", primary_confidence=0.9)
    with patch.object(orch, "_apply_walkway_lights"):
        with patch.object(orch, "_start_grace_scanner"):
            with patch.object(orch, "_notify_mode_changed"):
                for _ in range(3):
                    orch.handle_snapshot("room-a", away_snap)
    assert store.document().orchestrator.mode == "grace"

    bedroom_snap = LiveSnapshot(primary_state="relaxing", primary_confidence=0.9)
    with patch.object(orch, "_stop_grace_scanner"):
        with patch.object(orch, "_apply_active_room_mood") as apply_mood:
            with patch.object(orch, "_turn_off_non_active_devices") as turn_off:
                _prime_active_empty(orch, "room-a")
                for _ in range(3):
                    orch.handle_snapshot("room-b", bedroom_snap)

    assert store.document().active_room_id == "room-b"
    assert store.document().orchestrator.mode == "active"
    apply_mood.assert_called_once_with(
        "room-b",
        "relaxing",
        action_source=ActionSource.ORCHESTRATOR_RESUME,
    )
    turn_off.assert_called_once_with("room-b")


def test_return_to_main_from_bedroom_promotes_main(rooms_path: Path) -> None:
    """Bedroom active → grace → main presence promotes main and turns off bedroom."""
    from roomos.devices.action_arbiter import ActionSource

    store = RoomsStore(path=rooms_path)
    store.set_active_room_id("room-b")
    store.update_orchestrator(
        mode="grace",
        grace_started_at="2026-01-01T00:00:00+00:00",
    )
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch.set_inference_rooms({"room-a", "room-b"})
    orch._last_mood_by_room["room-a"] = "work"
    orch._last_label_by_room["room-b"] = "away"
    _prime_active_empty(orch, "room-b")

    main_snap = LiveSnapshot(primary_state="work", primary_confidence=0.9)
    with patch.object(orch, "_stop_grace_scanner"):
        with patch.object(orch, "_apply_active_room_mood") as apply_mood:
            with patch.object(orch, "_turn_off_non_active_devices") as turn_off:
                for _ in range(3):
                    orch.handle_snapshot("room-a", main_snap)

    assert store.document().active_room_id == "room-a"
    assert store.document().orchestrator.mode == "active"
    apply_mood.assert_called_once_with(
        "room-a",
        "work",
        action_source=ActionSource.ORCHESTRATOR_RESUME,
    )
    turn_off.assert_called_once_with("room-a")


def test_cross_room_promote_not_blocked_by_origin_burst_when_committed_away(
    rooms_path: Path,
) -> None:
    """Burst noise on an away-labelled origin must not block bedroom promote."""
    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(
        mode="grace",
        grace_started_at="2026-01-01T00:00:00+00:00",
    )
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch._grace_origin_room_id = "room-a"
    _prime_active_empty(orch, "room-a")

    origin_snap = LiveSnapshot(
        primary_state="away",
        primary_confidence=0.6,
        model_probs={"away": 0.3, "work": 0.55, "relaxing": 0.15},
    )
    orch.handle_snapshot("room-a", origin_snap)

    other_snap = LiveSnapshot(primary_state="work", primary_confidence=0.9)
    with patch.object(orch, "_promote_room") as promote:
        for _ in range(3):
            orch.handle_snapshot("room-b", other_snap)
    promote.assert_called_once()


def test_active_mode_handoff_when_origin_empty(rooms_path: Path) -> None:
    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(mode="active")
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch.set_inference_rooms({"room-a", "room-b"})
    orch._active_empty_streak["room-a"] = 3
    orch._last_label_by_room["room-a"] = "away"

    bedroom_snap = LiveSnapshot(primary_state="relaxing", primary_confidence=0.9)
    with patch.object(orch, "_promote_room") as promote:
        for _ in range(3):
            orch.handle_snapshot("room-b", bedroom_snap)
        promote.assert_not_called()
        orch.handle_snapshot("room-b", bedroom_snap)
    promote.assert_called_once()


def test_cross_room_promote_blocked_while_active_room_occupied(rooms_path: Path) -> None:
    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(
        mode="grace",
        grace_started_at="2026-01-01T00:00:00+00:00",
    )
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch._last_label_by_room["room-a"] = "work"

    snap = LiveSnapshot(primary_state="relaxing", primary_confidence=0.9)
    with patch.object(orch, "_promote_room") as promote:
        for _ in range(6):
            orch.handle_snapshot("room-b", snap)
    promote.assert_not_called()


def test_snap_confident_presence_uses_smoothed_label_confidence() -> None:
    snap = LiveSnapshot(
        primary_state="work",
        primary_confidence=0.001,
        model_probs={"work": 0.001, "away": 0.8},
        distribution={"work": 0.52, "away": 0.3},
    )
    assert _snap_confident_ml_presence(snap)


def test_grace_main_burst_noise_does_not_reset_bedroom_streak(
    rooms_path: Path,
) -> None:
    """Empty-chair burst on origin must not zero the bedroom promote streak."""
    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(
        mode="grace",
        grace_started_at="2026-01-01T00:00:00+00:00",
    )
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch._grace_origin_room_id = "room-a"
    _prime_active_empty(orch, "room-a")

    main_noise = LiveSnapshot(
        primary_state="away",
        primary_confidence=0.8,
        model_probs={"away": 0.55, "work": 0.25, "relaxing": 0.2},
    )
    bedroom_snap = LiveSnapshot(
        primary_state="work",
        primary_confidence=0.55,
        distribution={"work": 0.55, "away": 0.2},
    )

    with patch.object(orch, "_promote_room") as promote:
        orch.handle_snapshot("room-b", bedroom_snap)
        orch.handle_snapshot("room-a", main_noise)
        orch.handle_snapshot("room-b", bedroom_snap)
        orch.handle_snapshot("room-a", main_noise)
        orch.handle_snapshot("room-b", bedroom_snap)
    promote.assert_called_once()


def test_away_label_with_burst_presence_does_not_enter_grace(rooms_path: Path) -> None:
    store = RoomsStore(path=rooms_path)
    store.update_orchestrator(mode="active")
    orch = PresenceOrchestrator(store, config_path="configs/inference.yaml")
    orch.set_inference_room("room-a")

    snap = LiveSnapshot(
        primary_state="away",
        primary_confidence=0.7,
        model_probs={"away": 0.3, "work": 0.55, "relaxing": 0.15},
    )
    with patch.object(orch, "_enter_grace") as enter_grace:
        for _ in range(4):
            orch.handle_snapshot("room-a", snap)
    enter_grace.assert_not_called()
