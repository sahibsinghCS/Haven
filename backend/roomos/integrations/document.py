"""Integrations document helpers — v2 arrays with stable device ids."""

from __future__ import annotations

import uuid
from typing import Any

_V2_ARRAY_KEYS = ("smartPlugs", "lights", "thermostats")
_LEGACY_KEY_MAP = {
    "smartPlugs": "smartPlug",
    "lights": "lights",
    "thermostats": "thermostat",
}


def new_device_id() -> str:
    return str(uuid.uuid4())


def find_device_by_id(doc: dict[str, Any], device_id: str) -> tuple[str, dict[str, Any]] | None:
    devices = doc.get("devices")
    if not isinstance(devices, dict):
        return None
    for key in _V2_ARRAY_KEYS:
        items = devices.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and str(item.get("id") or "") == device_id:
                return key, item
    return None


def iter_connected_devices(doc: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    devices = doc.get("devices")
    if not isinstance(devices, dict):
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for key in _V2_ARRAY_KEYS:
        items = devices.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("connected") and item.get("enabled"):
                out.append((key, item))
    return out
