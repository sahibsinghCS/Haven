"""Preferences persistence — matches PreferenceDocument in the frontend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from roomos.utils.io import read_json, write_json
from roomos.utils.logging import get_logger

from ..core.state import state  # noqa: F401  (kept for symmetry / future use)

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
    ],
}


@router.get("")
def get_preferences() -> dict[str, Any]:
    p = _store_path()
    if not p.exists():
        return _DEFAULT_DOC
    try:
        return read_json(p)
    except Exception as e:
        log.warning("Preferences read failed (%s); returning defaults.", e)
        return _DEFAULT_DOC


@router.put("")
def put_preferences(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict) or "presets" not in doc:
        raise HTTPException(status_code=400, detail="Body must be a PreferenceDocument with 'presets'.")
    doc = dict(doc)
    doc["updatedAt"] = datetime.now(timezone.utc).isoformat()
    doc.setdefault("schemaVersion", 1)
    p = _store_path()
    write_json(p, doc)
    return doc
