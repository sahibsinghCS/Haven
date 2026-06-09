"""PreferenceDocument normalization — single source of truth for active preset."""

from __future__ import annotations

from typing import Any, Dict, List

# Must match web/src/types/roomos.ts PREFERENCE_MOOD_ORDER
_UI_STATE_ORDER = ("sleep", "work", "relaxing", "away")
ROOM_STATE_ORDER: tuple[str, ...] = _UI_STATE_ORDER

_LEGACY_MOOD_DEFAULTS: dict[str, dict[str, Any]] = {
    "sleep": {"lightColorHex": "#1E2A4A", "brightness": 8, "fanOn": True, "temperatureF": 68},
    "work": {"lightColorHex": "#E8F4FF", "brightness": 72, "fanOn": False, "temperatureF": 72},
    "relaxing": {"lightColorHex": "#2FB8A8", "brightness": 42, "fanOn": False, "temperatureF": 73},
    "away": {"lightColorHex": "#2A2A2A", "brightness": 0, "fanOn": False, "temperatureF": 76},
}


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


def _connected_device_ids_by_category() -> dict[str, list[str]]:
    try:
        from app.integrations_service import load_integrations

        doc = load_integrations()
    except Exception:
        return {"smartPlugs": [], "lights": [], "thermostats": []}

    devices = doc.get("devices")
    if not isinstance(devices, dict):
        return {"smartPlugs": [], "lights": [], "thermostats": []}

    out: dict[str, list[str]] = {"smartPlugs": [], "lights": [], "thermostats": []}
    for key in out:
        items = devices.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("connected") and item.get("enabled"):
                if key == "thermostats" and item.get("brand") in ("none", "", None):
                    continue
                device_id = str(item.get("id") or "").strip()
                if device_id:
                    out[key].append(device_id)
    return out


def _legacy_fields_for_scene(scene: dict[str, Any], state: str | None) -> dict[str, Any]:
    """Merge v1 root fields with per-mood defaults when hydrating empty v2 device maps."""
    base = dict(_LEGACY_MOOD_DEFAULTS.get(state or "", _LEGACY_MOOD_DEFAULTS["work"]))
    for key in ("fanOn", "brightness", "lightColorHex", "temperatureF"):
        if key in scene:
            base[key] = scene[key]
    return base


def _migrate_scene_to_v2(
    scene: dict[str, Any],
    ids_by_cat: dict[str, list[str]],
    *,
    state: str | None = None,
) -> dict[str, Any]:
    devices_in = scene.get("devices")
    devices: dict[str, dict[str, Any]] = (
        dict(devices_in) if isinstance(devices_in, dict) else {}
    )
    legacy = _legacy_fields_for_scene(scene, state)

    for plug_id in ids_by_cat.get("smartPlugs", []):
        if plug_id not in devices:
            devices[plug_id] = {"fanOn": bool(legacy.get("fanOn", False))}
    for lights_id in ids_by_cat.get("lights", []):
        if lights_id not in devices:
            devices[lights_id] = {
                "brightness": int(legacy.get("brightness", 30)),
                "lightColorHex": str(legacy.get("lightColorHex", "#2A2A2A")),
            }
    for thermo_id in ids_by_cat.get("thermostats", []):
        if thermo_id not in devices:
            devices[thermo_id] = {"temperatureF": int(legacy.get("temperatureF", 72))}
    return {"devices": devices}


def _normalize_preferences_matrix(prefs: dict[str, Any]) -> dict[str, Any]:
    ids_by_cat = _connected_device_ids_by_category()
    out: dict[str, Any] = {}
    for state in _UI_STATE_ORDER:
        scene = prefs.get(state)
        if isinstance(scene, dict):
            out[state] = _migrate_scene_to_v2(scene, ids_by_cat, state=state)
        else:
            legacy = _LEGACY_MOOD_DEFAULTS.get(state, _LEGACY_MOOD_DEFAULTS["work"])
            out[state] = _migrate_scene_to_v2(legacy, ids_by_cat, state=state)
    return out


def normalize_preference_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Validate and fill ``activePresetId`` (canonical active preset for live inference)."""
    if not isinstance(doc, dict):
        raise PreferenceValidationError("Document must be an object.")
    if "presets" not in doc:
        raise PreferenceValidationError("Document must include 'presets'.")

    out = dict(doc)
    presets = out.get("presets")
    if isinstance(presets, list):
        normalized_presets: list[dict[str, Any]] = []
        for preset in presets:
            if not isinstance(preset, dict):
                continue
            p = dict(preset)
            prefs = p.get("preferences")
            if isinstance(prefs, dict):
                p["preferences"] = _normalize_preferences_matrix(prefs)
            normalized_presets.append(p)
        out["presets"] = normalized_presets

    out["activePresetId"] = resolve_active_preset_id(out)
    out["schemaVersion"] = 2
    return out


def active_preset_preferences(doc: dict[str, Any]) -> dict[str, dict[str, object]]:
    """Per-state scene targets from the active preset matrix (v2 devices map)."""
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

    ids_by_cat = _connected_device_ids_by_category()
    out: dict[str, dict[str, object]] = {}
    for state in _UI_STATE_ORDER:
        scene = prefs.get(state)
        if not isinstance(scene, dict):
            continue
        out[state] = _migrate_scene_to_v2(scene, ids_by_cat, state=state)
    return out
