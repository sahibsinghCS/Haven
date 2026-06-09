"""Preference apply helpers (no network)."""

from unittest.mock import patch

from roomos.preferences.apply import PreferenceChangeSpec, apply_preference_changes
from roomos.preferences.document import resolve_active_preset_id

from tests.test_preferences_document import _sample_doc


@patch("roomos.preferences.apply._connected_device_ids_by_category")
def test_fan_lower_for_work(mock_ids):
    mock_ids.return_value = {"smartPlugs": ["plug-1"], "lights": [], "thermostats": []}
    doc = _sample_doc()
    doc["activePresetId"] = "preset_custom"
    spec = PreferenceChangeSpec(target_states=["work"], fan="off")
    result = apply_preference_changes(doc, spec, fallback_state="work")
    scenes = result.doc["presets"][1]["preferences"]["work"]["devices"]
    assert scenes["plug-1"]["fanOn"] is False
    assert any("fan" in c for c in result.changes)


@patch("roomos.preferences.apply._connected_device_ids_by_category")
def test_brightness_lower_uses_current_state_when_empty(mock_ids):
    mock_ids.return_value = {"smartPlugs": [], "lights": ["lights-1"], "thermostats": []}
    doc = _sample_doc()
    doc["presets"][0]["preferences"]["relaxing"] = {
        "devices": {"lights-1": {"brightness": 3, "lightColorHex": "#000003"}}
    }
    spec = PreferenceChangeSpec(brightness={"relative": "lower"})
    result = apply_preference_changes(doc, spec, fallback_state="relaxing")
    assert "relaxing" in result.target_states
    scenes = result.doc["presets"][0]["preferences"]["relaxing"]["devices"]
    assert scenes["lights-1"]["brightness"] < 3


@patch("roomos.preferences.apply._connected_device_ids_by_category")
def test_light_color_blue(mock_ids):
    mock_ids.return_value = {"smartPlugs": [], "lights": ["lights-1"], "thermostats": []}
    doc = _sample_doc()
    doc["presets"][0]["preferences"]["relaxing"] = {
        "devices": {"lights-1": {"brightness": 2, "lightColorHex": "#000002"}}
    }
    spec = PreferenceChangeSpec(target_states=["relaxing"], light_color={"name": "blue"})
    result = apply_preference_changes(doc, spec, fallback_state="relaxing")
    hx = result.doc["presets"][0]["preferences"]["relaxing"]["devices"]["lights-1"]["lightColorHex"]
    assert hx.upper() == "#3B82F6"
