"""Per-room engine lifecycle: cameras must stay connected across mode switches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.state import AppState


def _fake_live_state(*, engine_ids: list[str]) -> SimpleNamespace:
    """Minimal stand-in for AppState._ensure_room_engines."""
    stopped: list[str] = []
    handoffs: list[str] = []

    state = SimpleNamespace(
        live_mode="live",
        _room_engines={},
        _preview_max_w=1280,
        _preview_quality=88,
        _inference_room_id=engine_ids[0] if engine_ids else None,
        _last_ml_rooms=set(),
        stopped=stopped,
        handoffs=handoffs,
    )
    for rid in engine_ids:
        eng = MagicMock(name=rid)
        eng.is_running = MagicMock(return_value=True)
        state._room_engines[rid] = eng

    room_a = SimpleNamespace(id="room-a", name="Main", enabled=True)
    room_b = SimpleNamespace(id="room-b", name="Bedroom", enabled=True)
    doc = SimpleNamespace(
        enabled_rooms=lambda: [room_a, room_b],
        rooms=[room_a, room_b],
        active_room_id="room-a",
        room_by_id=lambda rid: room_a if rid == "room-a" else room_b,
    )
    state.rooms_store = SimpleNamespace(document=lambda: doc)

    orch = MagicMock()
    state.orchestrator = orch

    previews = MagicMock()
    state.room_previews = previews

    def stop_engine(rid: str) -> None:
        stopped.append(rid)
        state._room_engines.pop(rid, None)

    def handoff(room, **kwargs) -> MagicMock:
        handoffs.append(room.id)
        eng = MagicMock(name=f"eng-{room.id}")
        eng.is_running = MagicMock(return_value=True)
        state._room_engines[room.id] = eng
        return eng

    state._stop_room_engine = stop_engine
    state._handoff_preview_to_ml = handoff

    return state


def test_ensure_room_engines_keeps_all_engines_on_active_mode() -> None:
    state = _fake_live_state(engine_ids=["room-a", "room-b"])
    AppState._ensure_room_engines(state)  # type: ignore[arg-type]
    assert set(state._room_engines.keys()) == {"room-a", "room-b"}
    assert state.stopped == []
    state.orchestrator.set_inference_rooms.assert_called_once_with(
        {"room-a", "room-b"}
    )


def test_ensure_room_engines_does_not_stop_when_simulating_grace_to_active() -> None:
    state = _fake_live_state(engine_ids=["room-a", "room-b"])
    AppState._ensure_room_engines(state)  # type: ignore[arg-type]
    AppState._ensure_room_engines(state)  # type: ignore[arg-type]
    assert state.stopped == []
    assert len(state._room_engines) == 2


def test_ensure_room_engines_starts_missing_room_only() -> None:
    state = _fake_live_state(engine_ids=["room-a"])
    AppState._ensure_room_engines(state)  # type: ignore[arg-type]
    assert state.handoffs == ["room-b"]
    assert "room-b" in state._room_engines
    assert state.stopped == []


def test_ensure_room_engines_removes_disabled_room() -> None:
    state = _fake_live_state(engine_ids=["room-a", "room-b"])
    state.rooms_store.document().enabled_rooms = lambda: [
        SimpleNamespace(id="room-a", name="Main", enabled=True)
    ]
    AppState._ensure_room_engines(state)  # type: ignore[arg-type]
    assert state.stopped == ["room-b"]
    assert set(state._room_engines.keys()) == {"room-a"}


def test_ensure_room_engines_skips_sync_when_unchanged() -> None:
    state = _fake_live_state(engine_ids=["room-a", "room-b"])
    state.room_previews.sync_rooms = MagicMock()
    AppState._ensure_room_engines(state)  # type: ignore[arg-type]
    state.room_previews.sync_rooms.assert_called_once()
    state.room_previews.sync_rooms.reset_mock()
    AppState._ensure_room_engines(state)  # type: ignore[arg-type]
    state.room_previews.sync_rooms.assert_not_called()


def test_restart_engine_for_room_does_not_call_ensure() -> None:
    with patch.object(AppState, "_ensure_room_engines") as ensure:
        state = AppState.__new__(AppState)
        state.live_mode = "live"
        state.rooms_store = MagicMock()
        state.orchestrator = MagicMock()
        state.orchestrator.camera_for_room = MagicMock()
        state._on_orchestrator_active_room_changed = MagicMock()
        AppState.restart_engine_for_room(state, "room-b")
        ensure.assert_not_called()


@pytest.mark.parametrize("orch_mode", ["grace", "away", "active"])
def test_mode_changed_hook_calls_ensure(orch_mode: str) -> None:
    with patch.object(AppState, "_ensure_room_engines") as ensure:
        state = AppState.__new__(AppState)
        state.live_mode = "live"
        AppState._on_orchestrator_mode_changed(state, orch_mode)
        ensure.assert_called_once()
