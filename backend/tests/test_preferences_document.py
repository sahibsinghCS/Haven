"""Active preset resolution for live scene application."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from roomos.preferences.document import (
    PreferenceValidationError,
    active_preset_preferences,
    normalize_preference_document,
    resolve_active_preset_id,
)


def _sample_doc():
    return {
        "schemaVersion": 2,
        "presets": [
            {
                "id": "preset_basic",
                "name": "Basic",
                "isDefault": True,
                "preferences": {
                    "work": {
                        "devices": {
                            "lights-1": {
                                "lightColorHex": "#FFFFFF",
                                "brightness": 10,
                            }
                        }
                    },
                    "sleep": {"devices": {}},
                    "relaxing": {"devices": {}},
                    "away": {"devices": {}},
                },
            },
            {
                "id": "preset_custom",
                "name": "Custom",
                "isDefault": False,
                "preferences": {
                    "work": {
                        "devices": {
                            "lights-1": {
                                "lightColorHex": "#AABBCC",
                                "brightness": 99,
                            },
                            "plug-1": {"fanOn": True},
                        }
                    },
                    "sleep": {"devices": {}},
                    "relaxing": {"devices": {}},
                    "away": {"devices": {}},
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
    work = scenes["work"]["devices"]
    assert work["lights-1"]["brightness"] == 99
    assert work["lights-1"]["lightColorHex"] == "#AABBCC"


def test_normalize_fills_missing_active_preset_id():
    doc = _sample_doc()
    out = normalize_preference_document(doc)
    assert out["activePresetId"] == "preset_basic"
    assert out["schemaVersion"] == 2


def test_normalize_rejects_empty_presets():
    with pytest.raises(PreferenceValidationError):
        normalize_preference_document({"presets": []})


@patch("roomos.preferences.document._connected_device_ids_by_category")
def test_active_preset_preferences_hydrates_empty_device_maps(mock_ids):
    mock_ids.return_value = {"smartPlugs": ["plug-1"], "lights": [], "thermostats": []}
    doc = {
        "schemaVersion": 2,
        "activePresetId": "preset_basic",
        "presets": [
            {
                "id": "preset_basic",
                "name": "Basic",
                "isDefault": True,
                "preferences": {
                    "sleep": {"devices": {}},
                    "work": {"devices": {}},
                    "relaxing": {"devices": {"plug-1": {"fanOn": True}}},
                    "away": {"devices": {}},
                },
            }
        ],
    }
    scenes = active_preset_preferences(doc)
    assert scenes["relaxing"]["devices"]["plug-1"]["fanOn"] is True
    assert scenes["work"]["devices"]["plug-1"]["fanOn"] is False
    assert scenes["sleep"]["devices"]["plug-1"]["fanOn"] is True
