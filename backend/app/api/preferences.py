"""Preferences persistence — matches PreferenceDocument in the frontend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from roomos.preferences.document import PreferenceValidationError, normalize_preference_document
from roomos.utils.logging import get_logger

from ..preferences_service import load_preferences, save_preferences

log = get_logger("roomos.api.preferences")
router = APIRouter(prefix="/api/preferences", tags=["preferences"])


def _store_path():
    # We resolve lazily so tests can monkeypatch via env vars / configs.
    from roomos.config import load_config
    from ..core.config import settings

    cfg = load_config(settings.roomos_config)
    return cfg.resolve_path("data/preferences.json")


_DEFAULT_DOC = {
    "schemaVersion": 1,
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "presets": [
        {
            "id": "preset_basic",
            "name": "Basic Preference",
            "description": "Balanced defaults for day-to-night transitions.",
            "isDefault": True,
            "preferences": {
                "sleep":    {"lightColorHex": "#1E2A4A", "brightness": 8,  "fanOn": True,  "temperatureF": 68},
                "gaming":   {"lightColorHex": "#6D4AFF", "brightness": 80, "fanOn": True,  "temperatureF": 70},
                "work":     {"lightColorHex": "#E8F4FF", "brightness": 72, "fanOn": False, "temperatureF": 72},
                "relaxing": {"lightColorHex": "#2FB8A8", "brightness": 42, "fanOn": False, "temperatureF": 73},
                "away":     {"lightColorHex": "#2A2A2A", "brightness": 0,  "fanOn": False, "temperatureF": 76},
            },
        },
        {
            "id": "preset_custom",
            "name": "Custom",
            "description": "Your personal mix. Adjust any mood, then save.",
            "isDefault": False,
            "preferences": {
                "sleep":    {"lightColorHex": "#0F172A", "brightness": 4,  "fanOn": True,  "temperatureF": 67},
                "gaming":   {"lightColorHex": "#7C3AED", "brightness": 88, "fanOn": True,  "temperatureF": 69},
                "work":     {"lightColorHex": "#D7F9FF", "brightness": 85, "fanOn": False, "temperatureF": 71},
                "relaxing": {"lightColorHex": "#14B8A6", "brightness": 35, "fanOn": False, "temperatureF": 74},
                "away":     {"lightColorHex": "#18181B", "brightness": 0,  "fanOn": False, "temperatureF": 78},
            },
        },
    ],
    "activePresetId": "preset_basic",
}


@router.get("")
def get_preferences() -> dict[str, Any]:
    return load_preferences()


@router.put("")
def put_preferences(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict) or "presets" not in doc:
        raise HTTPException(status_code=400, detail="Body must be a PreferenceDocument with 'presets'.")
    try:
        normalize_preference_document(doc)
    except PreferenceValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return save_preferences(doc)
