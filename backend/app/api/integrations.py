"""Device integration settings API."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from roomos.integrations.document import find_device_by_id

from ..integrations_service import load_integrations, save_integrations
from roomos.utils.logging import get_logger

log = get_logger("roomos.api.integrations")

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class PlugTestBody(BaseModel):
    device_id: str = Field(default="", description="Saved plug instance id")
    host: str = Field(default="", description="Plug LAN IP (optional if saved in Settings)")
    state: str = Field(default="on", description="on or off")
    brand: str = Field(default="", description="Override brand from saved settings")


class ThermostatTestBody(BaseModel):
    device_id: str = Field(default="", description="Saved thermostat instance id")
    heat_f: float | None = Field(default=None, description="Heat setpoint °F")
    cool_f: float | None = Field(default=None, description="Cool setpoint °F")


class LightsTestBody(BaseModel):
    device_id: str = Field(default="", description="Saved lights instance id")
    brightness: int | None = Field(default=50, description="0–100")
    light_color_hex: str = Field(default="#E8F4FF", description="Target color")


class DiscoverBody(BaseModel):
    timeout: float = Field(default=8.0, ge=2.0, le=20.0, description="Scan seconds per protocol")


def _resolve_plug_from_doc(doc: dict[str, Any], device_id: str) -> dict[str, Any]:
    if device_id:
        found = find_device_by_id(doc, device_id)
        if found and found[0] == "smartPlugs":
            return found[1]
    plugs = doc.get("devices", {}).get("smartPlugs")
    if isinstance(plugs, list) and plugs:
        first = plugs[0]
        if isinstance(first, dict):
            return first
    legacy = doc.get("devices", {}).get("smartPlug")
    return legacy if isinstance(legacy, dict) else {}


def _resolve_lights_from_doc(doc: dict[str, Any], device_id: str) -> dict[str, Any]:
    if device_id:
        found = find_device_by_id(doc, device_id)
        if found and found[0] == "lights":
            return found[1]
    items = doc.get("devices", {}).get("lights")
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict):
            return first
    if isinstance(items, dict):
        return items
    return {}


def _resolve_thermostat_from_doc(doc: dict[str, Any], device_id: str) -> dict[str, Any]:
    if device_id:
        found = find_device_by_id(doc, device_id)
        if found and found[0] == "thermostats":
            return found[1]
    items = doc.get("devices", {}).get("thermostats")
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict):
            return first
    legacy = doc.get("devices", {}).get("thermostat")
    return legacy if isinstance(legacy, dict) else {}


def _smart_plug_config_from_request(body: PlugTestBody | None = None) -> dict[str, Any]:
    from roomos.integrations.device_bridge import plug_runtime_config

    doc = load_integrations()
    device_id = str(body.device_id or "").strip() if body else ""
    plug = _resolve_plug_from_doc(doc, device_id)
    cfg = plug_runtime_config(plug)
    if body:
        if body.host.strip():
            cfg["host"] = body.host.strip()
        if body.brand.strip():
            cfg["brand"] = body.brand.strip()
    cfg["enabled"] = True
    return cfg


def _thermostat_config_from_request(body: ThermostatTestBody | None = None) -> dict[str, Any]:
    from roomos.integrations.device_bridge import thermostat_runtime_config

    doc = load_integrations()
    device_id = str(body.device_id or "").strip() if body else ""
    thermo = _resolve_thermostat_from_doc(doc, device_id)
    cfg = thermostat_runtime_config(thermo)
    cfg["enabled"] = True
    if body:
        if body.heat_f is not None:
            cfg["targetHeatF"] = body.heat_f
        if body.cool_f is not None:
            cfg["targetCoolF"] = body.cool_f
    if cfg.get("targetHeatF") is None and cfg.get("targetCoolF") is None:
        cfg["targetHeatF"] = 70.0
    return cfg


def _lights_config_from_request(body: LightsTestBody | None = None) -> dict[str, Any]:
    from roomos.integrations.device_bridge import lights_runtime_config

    doc = load_integrations()
    device_id = str(body.device_id or "").strip() if body else ""
    lights = _resolve_lights_from_doc(doc, device_id)
    cfg = lights_runtime_config(lights)
    cfg["enabled"] = True
    return cfg


def _maybe_heal_plug_host(cfg: dict[str, Any], result: dict[str, Any]) -> None:
    """If discovery found the plug at a new IP, persist it so it stops drifting."""
    new_host = str(result.get("host") or "").strip()
    old_host = str(cfg.get("host") or "").strip()
    device_id = str(cfg.get("id") or "").strip()
    if not new_host or new_host == old_host:
        return
    try:
        doc = load_integrations()
        devices = doc.get("devices", {})
        if not isinstance(devices, dict):
            return
        plugs = devices.get("smartPlugs")
        if isinstance(plugs, list) and device_id:
            for plug in plugs:
                if isinstance(plug, dict) and str(plug.get("id") or "") == device_id:
                    plug["host"] = new_host
                    save_integrations(doc)
                    log.info("Healed smart plug host: %s -> %s", old_host or "(unset)", new_host)
                    return
        legacy = devices.get("smartPlug")
        if isinstance(legacy, dict):
            legacy["host"] = new_host
            save_integrations(doc)
            log.info("Healed smart plug host: %s -> %s", old_host or "(unset)", new_host)
    except Exception as e:
        log.warning("Could not persist healed plug host: %s", e)


@router.get("")
def get_integrations() -> dict[str, Any]:
    return load_integrations()


@router.put("")
def put_integrations(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict) or "devices" not in doc:
        raise HTTPException(status_code=400, detail="Body must include 'devices'.")
    try:
        return save_integrations(doc)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/smart-plug/status")
def smart_plug_status(device_id: str = "") -> dict[str, Any]:
    """Read current on/off state without toggling the plug."""
    cfg = _smart_plug_config_from_request(PlugTestBody(device_id=device_id))
    try:
        from roomos.devices.smart_plug import read_smart_plug_state

        result = asyncio.run(read_smart_plug_state(cfg))
        state = str(result.get("state") or ("on" if result.get("is_on") else "off"))
        if state not in ("on", "off"):
            state = "off"
        _maybe_heal_plug_host(cfg, result)
        return {"ok": True, "state": state, **result}
    except Exception as e:
        log.warning("Smart plug status read failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/device-actions")
def device_action_log(limit: int = 20) -> dict[str, Any]:
    """Recent device command arbiter decisions (for Settings / debug UI)."""
    from roomos.devices.action_arbiter import get_arbiter

    items = get_arbiter().recent_decisions(limit=max(1, min(100, int(limit))))
    return {"ok": True, "decisions": items}


@router.post("/smart-plug/test")
def test_smart_plug(body: PlugTestBody) -> dict[str, Any]:
    state = (body.state or "on").strip().lower()
    if state not in ("on", "off"):
        raise HTTPException(status_code=400, detail="state must be 'on' or 'off'")
    cfg = _smart_plug_config_from_request(body)
    try:
        from roomos.devices.action_arbiter import ActionSource
        from roomos.devices.command_gateway import gateway_apply_plug

        device_id = str(body.device_id or cfg.get("id") or cfg.get("host") or "plug")
        result = asyncio.run(
            gateway_apply_plug(
                cfg,
                state,
                source=ActionSource.MANUAL_TEST,
                device_id=device_id,
                dry_run=False,
                context={"endpoint": "smart-plug/test"},
            )
        )
        _maybe_heal_plug_host(cfg, result)
        return {"ok": True, **result}
    except Exception as e:
        log.warning("Smart plug test failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/kasa/test")
def test_kasa_plug(body: PlugTestBody) -> dict[str, Any]:
    if not body.brand.strip():
        body = body.model_copy(update={"brand": "tplink_kasa"})
    return test_smart_plug(body)


@router.post("/thermostat/test")
def test_thermostat(body: ThermostatTestBody) -> dict[str, Any]:
    cfg = _thermostat_config_from_request(body)
    heat = body.heat_f if body.heat_f is not None else cfg.get("targetHeatF")
    cool = body.cool_f if body.cool_f is not None else cfg.get("targetCoolF")
    try:
        from roomos.devices.action_arbiter import ActionSource
        from roomos.devices.command_gateway import gateway_apply_thermostat

        device_id = str(body.device_id or cfg.get("id") or "thermostat")
        result = asyncio.run(
            gateway_apply_thermostat(
                cfg,
                source=ActionSource.MANUAL_TEST,
                device_id=device_id,
                heat_f=float(heat) if heat is not None else None,
                cool_f=float(cool) if cool is not None else None,
                dry_run=False,
                context={"endpoint": "thermostat/test"},
            )
        )
        return {"ok": True, **result}
    except Exception as e:
        log.warning("Thermostat test failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/lights/test")
def test_lights(body: LightsTestBody) -> dict[str, Any]:
    cfg = _lights_config_from_request(body)
    brightness = 50 if body.brightness is None else max(0, min(100, int(body.brightness)))
    scene = {"brightness": brightness, "lightColorHex": body.light_color_hex or "#E8F4FF"}
    try:
        from roomos.devices.action_arbiter import ActionSource
        from roomos.devices.command_gateway import gateway_apply_lights

        device_id = str(body.device_id or cfg.get("id") or "lights")
        result = gateway_apply_lights(
            cfg,
            scene,
            source=ActionSource.MANUAL_TEST,
            device_id=device_id,
            dry_run=False,
            context={"endpoint": "lights/test"},
        )
        return {"ok": True, **result}
    except Exception as e:
        log.warning("Lights test failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/discover")
def discover_devices_api(body: DiscoverBody | None = None) -> dict[str, Any]:
    """Home-Assistant-style network scan. Seeds Kasa/Tapo creds from saved settings."""
    timeout = float(body.timeout) if body else 8.0

    email = ""
    password = ""
    try:
        doc = load_integrations()
        devices = doc.get("devices", {})
        if isinstance(devices, dict):
            plugs = devices.get("smartPlugs")
            plug: dict[str, Any] | None = None
            if isinstance(plugs, list):
                for item in plugs:
                    if isinstance(item, dict) and (item.get("tapoEmail") or item.get("tapoPassword")):
                        plug = item
                        break
                if plug is None and plugs and isinstance(plugs[0], dict):
                    plug = plugs[0]
            elif isinstance(devices.get("smartPlug"), dict):
                plug = devices["smartPlug"]
            if isinstance(plug, dict):
                email = str(plug.get("tapoEmail") or plug.get("username") or "").strip()
                password = str(plug.get("tapoPassword") or plug.get("password") or "").strip()
    except Exception:
        pass

    try:
        from roomos.devices.discovery import discover_all

        devices = asyncio.run(
            discover_all(timeout=timeout, kasa_email=email, kasa_password=password)
        )
        return {"ok": True, "devices": devices}
    except Exception as e:
        log.warning("Device discovery failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/thermostat/devices")
def list_thermostat_devices_api() -> dict[str, Any]:
    cfg = _thermostat_config_from_request()
    try:
        from roomos.devices.thermostat import list_thermostat_devices

        devices = list_thermostat_devices(cfg)
        return {"ok": True, "devices": devices}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
