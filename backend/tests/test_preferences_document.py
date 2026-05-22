"""Active preset resolution for live scene application."""

from __future__ import annotations

import pytest

from roomos.preferences.document import (
    PreferenceValidationError,
    active_preset_preferences,
    normalize_preference_document,
    resolve_active_preset_id,
)


def _sample_doc():
    return {
        "schemaVersion": 1,
        "presets": [
            {
                "id": "preset_basic",
                "name": "Basic",
                "isDefault": True,
                "preferences": {
                    "work": {
                        "lightColorHex": "#FFFFFF",
                        "brightness": 10,
                        "fanOn": False,
                        "temperatureF": 70,
                    },
                    "sleep": {
                        "lightColorHex": "#000001",
                        "brightness": 1,
                        "fanOn": True,
                        "temperatureF": 68,
                    },
                    "gaming": {
                        "lightColorHex": "#000002",
                        "brightness": 2,
                        "fanOn": True,
                        "temperatureF": 69,
                    },
                    "relaxing": {
                        "lightColorHex": "#000003",
                        "brightness": 3,
                        "fanOn": False,
                        "temperatureF": 71,
                    },
                    "away": {
                        "lightColorHex": "#000004",
                        "brightness": 0,
                        "fanOn": False,
                        "temperatureF": 72,
                    },
                },
            },
            {
                "id": "preset_custom",
                "name": "Custom",
                "isDefault": False,
                "preferences": {
                    "work": {
                        "lightColorHex": "#AABBCC",
                        "brightness": 99,
                        "fanOn": True,
                        "temperatureF": 75,
                    },
                    "sleep": {
                        "lightColorHex": "#000001",
                        "brightness": 1,
                        "fanOn": True,
                        "temperatureF": 68,
                    },
                    "gaming": {
                        "lightColorHex": "#000002",
                        "brightness": 2,
                        "fanOn": True,
                        "temperatureF": 69,
                    },
                    "relaxing": {
                        "lightColorHex": "#000003",
                        "brightness": 3,
                        "fanOn": False,
                        "temperatureF": 71,
                    },
                    "away": {
                        "lightColorHex": "#000004",
                        "brightness": 0,
                        "fanOn": False,
                        "temperatureF": 72,
                    },
                },
            },
        ],
    }


def test_resolve_active_preset_id_explicit():
    doc = _sample_doc()
    doc["activePresetId"] = "preset_custom"
    assert resolve_active_preset_id(doc) == "preset_custom"


def test_resolve_active_preset_id_falls_back_to_is_default():
    doc = _sample_doc()
    assert resolve_active_preset_id(doc) == "preset_basic"


def test_active_preset_preferences_uses_active_not_default():
    doc = _sample_doc()
    doc["activePresetId"] = "preset_custom"
    scenes = active_preset_preferences(doc)
    assert scenes["work"]["brightness"] == 99
    assert scenes["work"]["lightColorHex"] == "#AABBCC"


def test_normalize_fills_missing_active_preset_id():
    doc = _sample_doc()
    out = normalize_preference_document(doc)
    assert out["activePresetId"] == "preset_basic"


def test_normalize_rejects_empty_presets():
    with pytest.raises(PreferenceValidationError):
        normalize_preference_document({"presets": []})
