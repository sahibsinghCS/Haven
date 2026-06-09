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


def _empty_matrix() -> dict[str, Any]:
    return {
        "sleep": {"devices": {}},
        "work": {"devices": {}},
        "relaxing": {"devices": {}},
        "away": {"devices": {}},
    }


DEFAULT_PREFERENCES_DOC: dict[str, Any] = {
    "schemaVersion": 2,
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "presets": [
        {
            "id": "preset_basic",
            "name": "Basic Preference",
            "description": "Balanced defaults for day-to-night transitions.",
            "isDefault": True,
            "preferences": _empty_matrix(),
        },
        {
            "id": "preset_custom",
            "name": "Custom",
            "description": "Your personal mix. Adjust any mood, then save.",
            "isDefault": False,
            "preferences": _empty_matrix(),
        },
    ],
    "activePresetId": "preset_basic",
}
