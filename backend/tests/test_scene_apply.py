from unittest.mock import AsyncMock, patch

from roomos.devices.scene_apply import apply_preference_scene


@patch("roomos.devices.scene_apply.merge_runtime_integrations")
def test_preference_sync_dry_run(mock_merge):
    mock_merge.return_value = {
        "smart_plug": {"enabled": True, "brand": "tplink_kasa", "host": "10.0.0.1"},
        "thermostat": {"enabled": False, "brand": "none"},
        "lights": {"enabled": False, "brand": "none"},
    }
    record = apply_preference_scene(
        {"fanOn": True, "temperatureF": 68, "brightness": 10, "lightColorHex": "#112233"},
        dry_run=True,
        room_state="sleep",
    )
    assert record.get("dry_run") is True
    assert record.get("would_apply", {}).get("smart_plug") == "on"


@patch("roomos.devices.scene_apply.apply_smart_plug_state", new_callable=AsyncMock)
@patch("roomos.devices.scene_apply.merge_runtime_integrations")
def test_preference_sync_plug_on(mock_merge, mock_plug):
    mock_merge.return_value = {
        "smart_plug": {"enabled": True, "brand": "tplink_kasa", "host": "10.0.0.1"},
        "thermostat": {"enabled": False, "brand": "none"},
        "lights": {"enabled": False, "brand": "none"},
    }
    mock_plug.return_value = {"state": "on", "executed": True}
    record = apply_preference_scene(
        {"fanOn": True, "temperatureF": 72, "brightness": 50, "lightColorHex": "#fff"},
        dry_run=False,
        room_state="work",
    )
    assert record.get("executed") is True
    mock_plug.assert_awaited_once()
