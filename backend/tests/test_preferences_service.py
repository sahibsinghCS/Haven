"""Preferences save should re-apply devices for the current live mood."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.core.state import state
from app.preferences_service import sync_preferences_to_devices
from roomos.inference.live_pipeline import LiveSnapshot


@patch("roomos.devices.scene_apply.apply_preference_scene")
@patch("roomos.devices.scene_apply.resolve_apply_scene_for_mood")
@patch("roomos.devices.scene_apply.has_controllable_devices", return_value=True)
@patch("roomos.integrations.device_bridge.merge_runtime_integrations", return_value={})
def test_sync_preferences_uses_current_live_mood(
    mock_merge,
    mock_has_devices,
    mock_resolve_scene,
    mock_apply_scene,
):
    mock_resolve_scene.return_value = {"devices": {"plug-1": {"fanOn": True}}}
    mock_apply_scene.return_value = {"executed": True}

    state.hub._latest = LiveSnapshot(primary_state="work")

    record = sync_preferences_to_devices()

    assert record is not None
    mock_resolve_scene.assert_called_once_with("work")
    mock_apply_scene.assert_called_once()
    assert mock_apply_scene.call_args.kwargs["room_state"] == "work"


@patch("roomos.devices.scene_apply.apply_preference_scene")
@patch("roomos.devices.scene_apply.has_controllable_devices", return_value=True)
def test_sync_preferences_skips_unknown_mood(mock_has_devices, mock_apply_scene):
    state.hub._latest = LiveSnapshot(primary_state="unknown")

    record = sync_preferences_to_devices()

    assert record is None
    mock_apply_scene.assert_not_called()


@patch("roomos.devices.scene_apply.apply_preference_scene")
@patch("roomos.devices.scene_apply.resolve_apply_scene_for_mood")
@patch("roomos.devices.scene_apply.has_controllable_devices", return_value=True)
@patch("roomos.integrations.device_bridge.merge_runtime_integrations", return_value={})
def test_sync_preferences_honors_explicit_room_state(
    mock_merge,
    mock_has_devices,
    mock_resolve_scene,
    mock_apply_scene,
):
    mock_resolve_scene.return_value = {"devices": {"plug-1": {"fanOn": False}}}
    state.hub._latest = LiveSnapshot(primary_state="relaxing")

    sync_preferences_to_devices(room_state="work")

    mock_resolve_scene.assert_called_once_with("work")
