"""Merge Settings UI (integrations.json) into the action engine integration block."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ..utils.logging import get_logger

log = get_logger("roomos.integrations.device_bridge")


def _integrations_json_path() -> Path:
    try:
        from app.integrations_settings_store import integrations_store_path

        return integrations_store_path()
    except Exception:
        return Path("data/integrations.json")


def load_ui_device_settings() -> Dict[str, Any]:
    try:
        from app.integrations_service import load_integrations

        return load_integrations()
    except Exception:
        pass
    path = _integrations_json_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception as e:
        log.debug("Could not read %s: %s", path, e)
        return {}


def plug_runtime_config(plug: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(plug, dict):
        return {}
    brand = str(plug.get("brand") or plug.get("provider") or "tplink_kasa")
    host = str(plug.get("host") or "").strip()
    enabled = bool(plug.get("enabled"))
    cfg: Dict[str, Any] = {
        "enabled": enabled,
        "brand": brand,
        "host": host,
        "label": str(plug.get("label") or ""),
        "timeout_sec": float(plug.get("timeout_sec", 12.0)),
        "tuyaDeviceId": str(plug.get("tuyaDeviceId") or ""),
        "tuyaLocalKey": str(plug.get("tuyaLocalKey") or ""),
        "tuyaVersion": plug.get("tuyaVersion") or "3.3",
        "merossEmail": str(plug.get("merossEmail") or ""),
        "merossPassword": str(plug.get("merossPassword") or ""),
        "shellyGen": str(plug.get("shellyGen") or "1"),
    }
    return cfg


def thermostat_runtime_config(thermo: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(thermo, dict):
        return {}
    return {
        "enabled": bool(thermo.get("enabled")),
        "brand": str(thermo.get("brand") or thermo.get("provider") or "none"),
        "label": str(thermo.get("label") or ""),
        "notes": str(thermo.get("notes") or ""),
        "username": str(thermo.get("username") or thermo.get("honeywellUsername") or ""),
        "password": str(thermo.get("password") or thermo.get("honeywellPassword") or ""),
        "deviceId": str(thermo.get("deviceId") or thermo.get("honeywellDeviceId") or ""),
        "ecobeeApiKey": str(thermo.get("ecobeeApiKey") or ""),
        "ecobeeRefreshToken": str(thermo.get("ecobeeRefreshToken") or ""),
        "ecobeeThermostatId": str(thermo.get("ecobeeThermostatId") or ""),
        "targetHeatF": thermo.get("targetHeatF"),
        "targetCoolF": thermo.get("targetCoolF"),
        "nestProjectId": str(thermo.get("nestProjectId") or ""),
        "nestClientId": str(thermo.get("nestClientId") or ""),
        "nestClientSecret": str(thermo.get("nestClientSecret") or ""),
        "nestRefreshToken": str(thermo.get("nestRefreshToken") or ""),
        "nestDeviceId": str(thermo.get("nestDeviceId") or ""),
    }


def lights_runtime_config(lights: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(lights, dict):
        return {}
    return {
        "enabled": bool(lights.get("enabled")),
        "brand": str(lights.get("brand") or "none"),
        "host": str(lights.get("host") or ""),
        "notes": str(lights.get("notes") or ""),
        "tuyaDeviceId": str(lights.get("tuyaDeviceId") or ""),
        "tuyaLocalKey": str(lights.get("tuyaLocalKey") or ""),
        "tuyaVersion": lights.get("tuyaVersion") or "3.3",
    }


def merge_runtime_integrations(yaml_integrations: Dict[str, Any]) -> Dict[str, Any]:
    """Overlay UI-saved devices onto actions.yaml integrations."""
    out = dict(yaml_integrations or {})
    ui = load_ui_device_settings()
    devices = ui.get("devices")
    if not isinstance(devices, dict):
        return out

    plug = devices.get("smartPlug")
    if isinstance(plug, dict):
        plug_cfg = plug_runtime_config(plug)
        out["smart_plug"] = plug_cfg
        brand = plug_cfg.get("brand", "")
        if brand in ("tplink_kasa", "tapo", "kasa"):
            kasa = dict(out.get("kasa") or {})
            kasa["enabled"] = plug_cfg.get("enabled", False) or kasa.get("enabled", False)
            if plug_cfg.get("host"):
                kasa["host"] = plug_cfg["host"]
            out["kasa"] = kasa

    thermo = devices.get("thermostat")
    if isinstance(thermo, dict):
        out["thermostat"] = thermostat_runtime_config(thermo)

    lights = devices.get("lights")
    if isinstance(lights, dict):
        out["lights"] = lights_runtime_config(lights)

    return out
