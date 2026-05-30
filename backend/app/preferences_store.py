"""Preferences JSON path and default document — shared without API layer imports."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def preferences_store_path() -> Path:
    from roomos.config import load_config

    from .core.config import settings

    cfg = load_config(settings.roomos_config)
    return cfg.resolve_path("data/preferences.json")


DEFAULT_PREFERENCES_DOC: dict[str, Any] = {
    "schemaVersion": 1,
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "presets": [
        {
            "id": "preset_basic",
            "name": "Basic Preference",
            "description": "Balanced defaults for day-to-night transitions.",
            "isDefault": True,
            "preferences": {
                "sleep": {"lightColorHex": "#1E2A4A", "brightness": 8, "fanOn": True, "temperatureF": 68},
                "gaming": {"lightColorHex": "#6D4AFF", "brightness": 80, "fanOn": True, "temperatureF": 70},
                "work": {"lightColorHex": "#E8F4FF", "brightness": 72, "fanOn": False, "temperatureF": 72},
                "relaxing": {"lightColorHex": "#2FB8A8", "brightness": 42, "fanOn": False, "temperatureF": 73},
                "away": {"lightColorHex": "#2A2A2A", "brightness": 0, "fanOn": False, "temperatureF": 76},
            },
        },
        {
            "id": "preset_custom",
            "name": "Custom",
            "description": "Your personal mix. Adjust any mood, then save.",
            "isDefault": False,
            "preferences": {
                "sleep": {"lightColorHex": "#0F172A", "brightness": 4, "fanOn": True, "temperatureF": 67},
                "gaming": {"lightColorHex": "#7C3AED", "brightness": 88, "fanOn": True, "temperatureF": 69},
                "work": {"lightColorHex": "#D7F9FF", "brightness": 85, "fanOn": False, "temperatureF": 71},
                "relaxing": {"lightColorHex": "#14B8A6", "brightness": 35, "fanOn": False, "temperatureF": 74},
                "away": {"lightColorHex": "#18181B", "brightness": 0, "fanOn": False, "temperatureF": 78},
            },
        },
    ],
    "activePresetId": "preset_basic",
}
