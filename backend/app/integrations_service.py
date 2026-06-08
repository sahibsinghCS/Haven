"""Load/save device integration settings for the Settings UI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roomos.utils.logging import get_logger

from .integrations_settings_store import default_integrations_document, integrations_store_path
from .persistence import load_json_document, save_json_document

log = get_logger("roomos.integrations.service")

_REQUIRED_DEVICE_KEYS = ("smartPlug", "lights", "thermostat")

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
    return out


def normalize_integrations_document(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict):
        raise ValueError("Document must be an object")
    out = default_integrations_document()
    devices_in = doc.get("devices")
    if isinstance(devices_in, dict):
        for key in _REQUIRED_DEVICE_KEYS:
            block = devices_in.get(key)
            if isinstance(block, dict):
                out["devices"][key] = _coerce_device_block(key, block, out["devices"][key])
    out["schemaVersion"] = int(doc.get("schemaVersion", 1) or 1)
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
