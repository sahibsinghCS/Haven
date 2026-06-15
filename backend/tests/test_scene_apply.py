from unittest.mock import AsyncMock, patch

from roomos.devices.scene_apply import (
    apply_preference_scene,
    invalidate_connected_device_categories_cache,
    preference_sync_dry_run,
    resolve_apply_scene_for_mood,
    scene_to_display_targets,
)


@patch("roomos.devices.scene_apply.load_ui_device_settings")
@patch("roomos.devices.scene_apply.merge_runtime_integrations")
def test_preference_sync_dry_run(mock_merge, mock_ui):
    mock_ui.return_value = {
        "devices": {
            "smartPlugs": [
                {
                    "id": "plug-1",
                    "enabled": True,
                    "connected": True,
                    "brand": "tplink_kasa",
                    "host": "10.0.0.1",
                    "label": "Fan",
                }
            ],
            "lights": [],
            "thermostats": [],
        }
    }
    mock_merge.return_value = {}
    record = apply_preference_scene(
        {"devices": {"plug-1": {"fanOn": True}}},
        dry_run=True,
        room_state="sleep",
    )
    assert record.get("dry_run") is True
    assert "smart_plug:plug-1" in record.get("would_apply", {})


@patch("roomos.devices.scene_apply.gateway_apply_plug", new_callable=AsyncMock)
@patch("roomos.devices.scene_apply.load_ui_device_settings")
@patch("roomos.devices.scene_apply.merge_runtime_integrations")
def test_preference_sync_plug_on(mock_merge, mock_ui, mock_plug):
    mock_ui.return_value = {
        "devices": {
            "smartPlugs": [
                {
                    "id": "plug-1",
                    "enabled": True,
                    "connected": True,
                    "brand": "tplink_kasa",
                    "host": "10.0.0.1",
                    "label": "Fan",
                }
            ],
            "lights": [],
            "thermostats": [],
        }
    }
    mock_merge.return_value = {}
    mock_plug.return_value = {
        "state": "on",
        "executed": True,
        "arbiter": {"allowed": True, "reason": "allowed"},
    }
    record = apply_preference_scene(
        {"devices": {"plug-1": {"fanOn": True}}},
        dry_run=False,
        room_state="work",
    )
    assert record.get("executed") is True
    mock_plug.assert_awaited_once()


@patch("roomos.devices.scene_apply.load_ui_device_settings")
def test_preference_sync_dry_run_overridden_when_devices_enabled(mock_ui):
    mock_ui.return_value = {
        "devices": {
            "smartPlugs": [{"id": "plug-1", "enabled": True, "connected": True}],
            "lights": [],
            "thermostats": [],
        }
    }
    assert preference_sync_dry_run(True) is False
    assert preference_sync_dry_run(False) is False


@patch("roomos.devices.scene_apply.load_ui_device_settings")
def test_preference_sync_stays_dry_run_without_devices(mock_ui):
    invalidate_connected_device_categories_cache()
    mock_ui.return_value = {"devices": {"smartPlugs": [], "lights": [], "thermostats": []}}
    assert preference_sync_dry_run(True) is True


@patch("roomos.devices.scene_apply.load_ui_device_settings")
def test_scene_to_display_targets_only_connected_categories(mock_ui):
    mock_ui.return_value = {
        "devices": {
            "smartPlugs": [
                {"id": "plug-1", "connected": True, "enabled": True, "label": "Fan"},
            ],
            "lights": [],
            "thermostats": [],
        }
    }
    scene = {
        "devices": {
            "plug-1": {"fanOn": True},
            "lights-1": {"brightness": 80, "lightColorHex": "#FFFFFF"},
            "thermo-1": {"temperatureF": 68},
        }
    }
    out = scene_to_display_targets(scene, connected=frozenset({"smartPlugs"}))
    assert out == {"fanOn": True}
    assert "brightness" not in out
    assert "temperatureF" not in out


@patch("roomos.devices.scene_apply.gateway_apply_plug", new_callable=AsyncMock)
@patch("roomos.devices.scene_apply.load_ui_device_settings")
@patch("roomos.devices.scene_apply.merge_runtime_integrations")
def test_preference_sync_skips_disconnected_plug(mock_merge, mock_ui, mock_plug):
    mock_ui.return_value = {
        "devices": {
            "smartPlugs": [
                {
                    "id": "plug-1",
                    "enabled": True,
                    "connected": False,
                    "brand": "tapo",
                    "host": "10.0.0.1",
                }
            ],
            "lights": [],
            "thermostats": [],
        }
    }
    mock_merge.return_value = {}
    record = apply_preference_scene(
        {"devices": {"plug-1": {"fanOn": True}}},
        dry_run=False,
        room_state="relaxing",
    )
    mock_plug.assert_not_awaited()
    assert record.get("reason") == "no_devices_enabled"


@patch("roomos.devices.scene_apply.load_ui_device_settings")
def test_scene_for_device_subset_inherits_stale_plug_target(mock_ui):
    mock_ui.return_value = {
        "devices": {
            "smartPlugs": [
                {"id": "plug-live", "connected": True, "enabled": True},
            ],
            "lights": [],
            "thermostats": [],
        }
    }
    from roomos.devices.scene_apply import _scene_for_device_subset

    scene = {"devices": {"plug-stale": {"fanOn": True}}}
    subset = _scene_for_device_subset(scene, frozenset(["plug-live"]))
    assert subset["devices"]["plug-live"]["fanOn"] is True


@patch("roomos.devices.scene_apply.load_ui_device_settings")
def test_target_for_device_inherits_from_other_plug(mock_ui):
    mock_ui.return_value = {
        "devices": {
            "smartPlugs": [
                {"id": "plug-live", "connected": True, "enabled": True},
                {"id": "plug-stale", "connected": True, "enabled": True},
            ],
            "lights": [],
            "thermostats": [],
        }
    }
    from roomos.devices.scene_apply import _target_for_device

    scene = {"devices": {"plug-stale": {"fanOn": True}}}
    target = _target_for_device("plug-live", scene, category="smartPlugs")
    assert target["fanOn"] is True


@patch("roomos.preferences.document._connected_device_ids_by_category")
@patch("app.preferences_service.load_preferences")
def test_resolve_apply_scene_differs_by_mood(mock_load_prefs, mock_ids):
    mock_ids.return_value = {"smartPlugs": ["plug-1"], "lights": [], "thermostats": []}
    mock_load_prefs.return_value = {
        "presets": [
            {
                "id": "preset_basic",
                "isDefault": True,
                "preferences": {
                    "work": {"devices": {"plug-1": {"fanOn": False}}},
                    "relaxing": {"devices": {"plug-1": {"fanOn": True}}},
                    "sleep": {"devices": {}},
                    "away": {"devices": {}},
                },
            }
        ],
        "activePresetId": "preset_basic",
    }
    work = resolve_apply_scene_for_mood("work")
    relaxing = resolve_apply_scene_for_mood("relaxing")
    assert work["devices"]["plug-1"]["fanOn"] is False
    assert relaxing["devices"]["plug-1"]["fanOn"] is True
