"""Preference apply helpers (no network)."""

from roomos.preferences.apply import PreferenceChangeSpec, apply_preference_changes
from roomos.preferences.document import resolve_active_preset_id

from tests.test_preferences_document import _sample_doc


def test_fan_lower_for_work():
    doc = _sample_doc()
    doc["activePresetId"] = "preset_custom"
    spec = PreferenceChangeSpec(target_states=["work"], fan="off")
    result = apply_preference_changes(doc, spec, fallback_state="work")
    scenes = result.doc["presets"][1]["preferences"]["work"]
    assert scenes["fanOn"] is False
    assert any("fan" in c for c in result.changes)


def test_brightness_lower_uses_current_state_when_empty():
    doc = _sample_doc()
    spec = PreferenceChangeSpec(brightness={"relative": "lower"})
    result = apply_preference_changes(doc, spec, fallback_state="relaxing")
    assert "relaxing" in result.target_states
    scenes = result.doc["presets"][0]["preferences"]["relaxing"]
    assert scenes["brightness"] < 3


def test_light_color_blue():
    doc = _sample_doc()
    spec = PreferenceChangeSpec(target_states=["gaming"], light_color={"name": "blue"})
    result = apply_preference_changes(doc, spec, fallback_state="gaming")
    hx = result.doc["presets"][0]["preferences"]["gaming"]["lightColorHex"]
    assert hx.upper() == "#3B82F6"
