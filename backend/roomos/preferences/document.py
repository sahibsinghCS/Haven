"""PreferenceDocument normalization — single source of truth for active preset."""

from __future__ import annotations

from typing import Any, Dict, List

# Must match web/src/types/roomos.ts ROOM_STATE_ORDER
_UI_STATE_ORDER = ("sleep", "gaming", "work", "relaxing", "away")


class PreferenceValidationError(ValueError):
    """Raised when a preference payload cannot be normalized."""


def _preset_ids(presets: List[Any]) -> List[str]:
    ids: List[str] = []
    for p in presets:
        if not isinstance(p, dict):
            raise PreferenceValidationError("Each preset must be an object.")
        pid = p.get("id")
        if not pid or not str(pid).strip():
            raise PreferenceValidationError("Each preset requires a non-empty 'id'.")
        ids.append(str(pid))
    return ids


def resolve_active_preset_id(doc: dict[str, Any]) -> str:
    """Return the preset id used for live scene application."""
    presets = doc.get("presets")
    if not isinstance(presets, list) or not presets:
        raise PreferenceValidationError("'presets' must be a non-empty list.")

    ids = _preset_ids(presets)
    active = doc.get("activePresetId")
    if active is not None and str(active) in ids:
        return str(active)

    for p in presets:
        if isinstance(p, dict) and p.get("isDefault"):
            return str(p["id"])
    return ids[0]


def normalize_preference_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Validate and fill ``activePresetId`` (canonical active preset for live inference)."""
    if not isinstance(doc, dict):
        raise PreferenceValidationError("Document must be an object.")
    if "presets" not in doc:
        raise PreferenceValidationError("Document must include 'presets'.")

    out = dict(doc)
    out["activePresetId"] = resolve_active_preset_id(out)
    out.setdefault("schemaVersion", 1)
    return out


def active_preset_preferences(doc: dict[str, Any]) -> dict[str, dict[str, object]]:
    """Per-state scene targets from the active preset matrix."""
    presets = doc.get("presets")
    if not isinstance(presets, list):
        return {}

    active_id = resolve_active_preset_id(doc)
    active = next((p for p in presets if isinstance(p, dict) and str(p.get("id")) == active_id), None)
    if not isinstance(active, dict):
        return {}

    prefs = active.get("preferences", {})
    if not isinstance(prefs, dict):
        return {}

    out: dict[str, dict[str, object]] = {}
    for state in _UI_STATE_ORDER:
        scene = prefs.get(state)
        if not isinstance(scene, dict):
            continue
        out[state] = {
            "lightColorHex": str(scene.get("lightColorHex", "#2A2A2A")),
            "brightness": int(scene.get("brightness", 30)),
            "fanOn": bool(scene.get("fanOn", False)),
            "temperatureF": int(scene.get("temperatureF", 72)),
        }
    return out
