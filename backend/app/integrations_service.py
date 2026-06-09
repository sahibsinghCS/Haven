"""Load/save device integration settings for the Settings UI."""

from __future__ import annotations

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


def load_integrations() -> dict[str, Any]:
    return load_json_document(
        "integrations",
        default_fn=default_integrations_document,
        normalize_fn=normalize_integrations_document,
        local_filename="integrations.json",
    )


def save_integrations(doc: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_integrations_document(doc)
    normalized["updatedAt"] = datetime.now(timezone.utc).isoformat()

    def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
        out = normalize_integrations_document(payload)
        out["updatedAt"] = datetime.now(timezone.utc).isoformat()
        return out

    return save_json_document(
        "integrations",
        normalized,
        normalize_fn=_finalize,
        local_filename="integrations.json",
    )


def legacy_integrations_store_path():
    """Tests / migrations that expect a single file path."""
    return integrations_store_path()
