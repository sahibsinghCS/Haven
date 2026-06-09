"""Merge Settings UI (integrations.json) into the action engine integration block."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

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
    brand = str(plug.get("brand") or plug.get("provider") or "tapo")
    tapo_email = str(plug.get("tapoEmail") or plug.get("username") or "").strip()
    tapo_password = str(plug.get("tapoPassword") or plug.get("password") or "").strip()
    if tapo_email and tapo_password:
        brand = "tapo"
    host = str(plug.get("host") or "").strip()
    enabled = bool(plug.get("enabled"))
    cfg: Dict[str, Any] = {
        "id": str(plug.get("id") or ""),
        "enabled": enabled,
        "brand": brand,
        "host": host,
        "label": str(plug.get("label") or ""),
        "timeout_sec": float(plug.get("timeout_sec", 12.0)),
        "tapoEmail": tapo_email,
        "tapoPassword": tapo_password,
        "username": tapo_email,
        "password": tapo_password,
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
        "id": str(thermo.get("id") or ""),
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
    out: Dict[str, Any] = {str(k): v for k, v in lights.items()}
    out.update(
        {
            "id": str(lights.get("id") or ""),
            "enabled": bool(lights.get("enabled")),
            "brand": str(lights.get("brand") or "none"),
            "host": str(lights.get("host") or ""),
            "notes": str(lights.get("notes") or ""),
            "tuyaDeviceId": str(lights.get("tuyaDeviceId") or ""),
            "tuyaLocalKey": str(lights.get("tuyaLocalKey") or ""),
            "tuyaVersion": lights.get("tuyaVersion") or "3.3",
        }
    )
    return out


def _device_array(devices: Dict[str, Any], key: str, legacy_key: str) -> List[Dict[str, Any]]:
    items = devices.get(key)
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    legacy = devices.get(legacy_key)
    if isinstance(legacy, dict):
        return [legacy]
    return []


def merge_runtime_integrations(yaml_integrations: Dict[str, Any]) -> Dict[str, Any]:
    """Overlay UI-saved devices onto actions.yaml integrations."""
    out = dict(yaml_integrations or {})
    ui = load_ui_device_settings()
    devices = ui.get("devices")
    if not isinstance(devices, dict):
        return out

    smart_plugs = _device_array(devices, "smartPlugs", "smartPlug")
    plug_cfgs = [plug_runtime_config(p) for p in smart_plugs]
    out["smart_plugs"] = plug_cfgs

    lights_list = _device_array(devices, "lights", "lights")
    lights_cfgs = [lights_runtime_config(l) for l in lights_list]
    out["lights_list"] = lights_cfgs

    thermostats = _device_array(devices, "thermostats", "thermostat")
    thermo_cfgs = [thermostat_runtime_config(t) for t in thermostats]
    out["thermostats"] = thermo_cfgs

    # Backward-compatible single slots for legacy action handlers
    first_plug = next((p for p in plug_cfgs if p.get("enabled")), plug_cfgs[0] if plug_cfgs else None)
    if isinstance(first_plug, dict):
        out["smart_plug"] = first_plug
        brand = first_plug.get("brand", "")
        if brand in ("tplink_kasa", "tapo", "kasa"):
            kasa = dict(out.get("kasa") or {})
            kasa["enabled"] = first_plug.get("enabled", False) or kasa.get("enabled", False)
            if first_plug.get("host"):
                kasa["host"] = first_plug["host"]
            if first_plug.get("username"):
                kasa["username"] = first_plug["username"]
            if first_plug.get("password"):
                kasa["password"] = first_plug["password"]
            out["kasa"] = kasa

    first_thermo = next((t for t in thermo_cfgs if t.get("enabled")), thermo_cfgs[0] if thermo_cfgs else None)
    if isinstance(first_thermo, dict):
        out["thermostat"] = first_thermo

    first_lights = next((l for l in lights_cfgs if l.get("enabled")), lights_cfgs[0] if lights_cfgs else None)
    if isinstance(first_lights, dict):
        out["lights"] = first_lights

    return out
