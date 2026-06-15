"""Load/save device integration settings for the Settings UI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from roomos.integrations.document import new_device_id
from roomos.utils.logging import get_logger

from .integrations_settings_store import (
    _default_lights,
    _default_smart_plug,
    _default_thermostat,
    default_integrations_document,
    integrations_store_path,
)
from .persistence import load_json_document, save_json_document

log = get_logger("roomos.integrations.service")

_integrations_merge_cache: tuple[str, dict[str, Any]] = ("", {})

_LEGACY_SINGLE_KEYS = ("smartPlug", "lights", "thermostat")
_V2_ARRAY_KEYS = ("smartPlugs", "lights", "thermostats")
_LEGACY_KEY_MAP = {
    "smartPlugs": "smartPlug",
    "lights": "lights",
    "thermostats": "thermostat",
}

_LEGACY_PROVIDER_TO_BRAND: dict[str, dict[str, str]] = {
    "smartPlug": {"kasa": "tplink_kasa", "tuya": "tuya", "other": "other_plug"},
    "lights": {
        "none": "none",
        "kasa": "kasa_light",
        "home_assistant": "other_lights",
        "matter": "matter",
        "other": "other_lights",
    },
    "thermostat": {
        "none": "none",
        "home_assistant": "other_thermostat",
        "matter": "other_thermostat",
        "other": "other_thermostat",
    },
}


def _coerce_device_block(key: str, block: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    out = {**defaults, **block}
    legacy_map = _LEGACY_PROVIDER_TO_BRAND.get(key, {})
    brand = out.get("brand") or out.get("provider")
    if isinstance(brand, str) and brand in legacy_map:
        brand = legacy_map[brand]
    if key == "smartPlug" and brand == "other":
        brand = "other_plug"
    if isinstance(brand, str):
        out["brand"] = brand
    out.pop("provider", None)
    out.pop("id", None)
    return out


def _normalize_device_array(
    category_key: str,
    items_in: Any,
    legacy_block: Any,
    defaults_single: dict[str, Any],
) -> list[dict[str, Any]]:
    legacy_key = _LEGACY_KEY_MAP[category_key]
    out: list[dict[str, Any]] = []

    if isinstance(items_in, list):
        for item in items_in:
            if not isinstance(item, dict):
                continue
            block = _coerce_device_block(legacy_key, item, defaults_single)
            device_id = str(item.get("id") or "").strip() or new_device_id()
            out.append({"id": device_id, **block})
    elif isinstance(legacy_block, dict):
        block = _coerce_device_block(legacy_key, legacy_block, defaults_single)
        device_id = str(legacy_block.get("id") or "").strip() or new_device_id()
        out.append({"id": device_id, **block})

    return out


def normalize_integrations_document(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict):
        raise ValueError("Document must be an object")
    out = default_integrations_document()
    devices_in = doc.get("devices")
    if isinstance(devices_in, dict):
        out["devices"] = {
            "smartPlugs": _normalize_device_array(
                "smartPlugs",
                devices_in.get("smartPlugs"),
                devices_in.get("smartPlug"),
                _default_smart_plug(),
            ),
            "lights": _normalize_device_array(
                "lights",
                devices_in.get("lights") if isinstance(devices_in.get("lights"), list) else None,
                devices_in.get("lights") if isinstance(devices_in.get("lights"), dict) else None,
                _default_lights(),
            ),
            "thermostats": _normalize_device_array(
                "thermostats",
                devices_in.get("thermostats"),
                devices_in.get("thermostat"),
                _default_thermostat(),
            ),
        }
    out["schemaVersion"] = 2
    out["updatedAt"] = str(doc.get("updatedAt") or out["updatedAt"])
    return out


def _device_entry_score(item: dict[str, Any]) -> int:
    score = 0
    if item.get("connected"):
        score += 2
    if item.get("enabled"):
        score += 2
    device_id = str(item.get("id") or "").strip()
    if device_id and device_id != "plug-runtime":
        score += 4
    if str(item.get("tapoEmail") or item.get("username") or "").strip() and str(
        item.get("tapoPassword") or item.get("password") or ""
    ).strip():
        score += 8
    if str(item.get("host") or "").strip():
        score += 1
    return score


def _merge_device_lists(*lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for items in lists:
        for item in items:
            if not isinstance(item, dict):
                continue
            device_id = str(item.get("id") or "").strip()
            if not device_id:
                continue
            prev = by_id.get(device_id)
            if prev is None or _device_entry_score(item) > _device_entry_score(prev):
                by_id[device_id] = dict(item)
    return list(by_id.values())


def _prune_stub_smart_plugs(plugs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop the dev ``plug-runtime`` stub when a real Tapo/Kasa plug is configured."""
    real = [
        plug
        for plug in plugs
        if str(plug.get("id") or "") != "plug-runtime"
        and plug.get("connected")
        and plug.get("enabled")
        and _device_entry_score(plug) >= 10
    ]
    if real:
        return real
    return plugs


def integrations_revision_key() -> str:
    """Cheap change detector for integrations on disk (avoids re-merge every burst)."""
    from .persistence import _local_candidate_paths

    parts: list[str] = []
    for path in _local_candidate_paths("integrations.json"):
        if not path.is_file():
            continue
        try:
            parts.append(f"{path}:{path.stat().st_mtime_ns}")
        except OSError:
            continue
    return "|".join(sorted(parts))


def invalidate_integrations_cache() -> None:
    global _integrations_merge_cache
    _integrations_merge_cache = ("", {})
    try:
        from roomos.devices.scene_apply import invalidate_connected_device_categories_cache

        invalidate_connected_device_categories_cache()
    except Exception:
        pass


def _merge_local_integration_backups(doc: dict[str, Any]) -> dict[str, Any]:
    """Merge device rows from every on-disk integrations copy (canonical, room, user)."""
    from .persistence import _local_candidate_paths

    arrays: dict[str, list[list[dict[str, Any]]]] = {key: [] for key in _V2_ARRAY_KEYS}
    devices = doc.get("devices")
    if isinstance(devices, dict):
        for key in _V2_ARRAY_KEYS:
            items = devices.get(key)
            if isinstance(items, list):
                arrays[key].append([item for item in items if isinstance(item, dict)])

    for path in _local_candidate_paths("integrations.json"):
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.debug("Could not read integrations backup %s: %s", path, e)
            continue
        if not isinstance(raw, dict):
            continue
        backup_devices = raw.get("devices")
        if not isinstance(backup_devices, dict):
            continue
        for key in _V2_ARRAY_KEYS:
            items = backup_devices.get(key)
            if isinstance(items, list):
                arrays[key].append([item for item in items if isinstance(item, dict)])

    out = dict(doc)
    out_devices = dict(devices) if isinstance(devices, dict) else {}
    for key in _V2_ARRAY_KEYS:
        merged = _merge_device_lists(*arrays[key])
        if key == "smartPlugs":
            merged = _prune_stub_smart_plugs(merged)
        if merged:
            out_devices[key] = merged
    out["devices"] = out_devices
    return normalize_integrations_document(out)


def load_integrations() -> dict[str, Any]:
    global _integrations_merge_cache
    revision = integrations_revision_key()
    if revision and revision == _integrations_merge_cache[0] and _integrations_merge_cache[1]:
        return _integrations_merge_cache[1]
    doc = load_json_document(
        "integrations",
        default_fn=default_integrations_document,
        normalize_fn=normalize_integrations_document,
        local_filename="integrations.json",
    )
    merged = _merge_local_integration_backups(doc)
    _integrations_merge_cache = (revision, merged)
    return merged


def save_integrations(doc: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_integrations_document(doc)
    normalized["updatedAt"] = datetime.now(timezone.utc).isoformat()

    def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
        out = normalize_integrations_document(payload)
        out["updatedAt"] = datetime.now(timezone.utc).isoformat()
        return out

    saved = save_json_document(
        "integrations",
        normalized,
        normalize_fn=_finalize,
        local_filename="integrations.json",
    )
    invalidate_integrations_cache()
    return saved


def legacy_integrations_store_path():
    """Tests / migrations that expect a single file path."""
    return integrations_store_path()
