"""Device integration settings — UI connections (smart plug, lights, thermostat)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def integrations_store_path() -> Path:
    from roomos.config import load_config

    from .core.config import settings

    cfg = load_config(settings.roomos_config)
    return cfg.resolve_path("data/integrations.json")


def _default_smart_plug() -> dict[str, Any]:
    return {
        "enabled": False,
        "connected": False,
        "brand": "tapo",
        "host": "",
        "label": "Desk plug",
        "tapoEmail": "",
        "tapoPassword": "",
    }


def _default_lights() -> dict[str, Any]:
    return {
        "enabled": False,
        "connected": False,
        "brand": "none",
        "notes": "",
    }


def _default_thermostat() -> dict[str, Any]:
    return {
        "enabled": False,
        "connected": False,
        "brand": "none",
        "notes": "",
    }


def default_smart_plug_device() -> dict[str, Any]:
    from roomos.integrations.document import new_device_id

    return {"id": new_device_id(), **_default_smart_plug()}


def default_lights_device() -> dict[str, Any]:
    from roomos.integrations.document import new_device_id

    return {"id": new_device_id(), **_default_lights()}


def default_thermostat_device() -> dict[str, Any]:
    from roomos.integrations.document import new_device_id

    return {"id": new_device_id(), **_default_thermostat()}


def default_integrations_document() -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schemaVersion": 2,
        "updatedAt": now,
        "devices": {
            "smartPlugs": [],
            "lights": [],
            "thermostats": [],
        },
    }
