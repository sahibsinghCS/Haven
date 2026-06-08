"""Device integration settings API."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..integrations_service import load_integrations, save_integrations
from roomos.utils.logging import get_logger

log = get_logger("roomos.api.integrations")

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class PlugTestBody(BaseModel):
    host: str = Field(default="", description="Plug LAN IP (optional if saved in Settings)")
    state: str = Field(default="on", description="on or off")
    brand: str = Field(default="", description="Override brand from saved settings")


class ThermostatTestBody(BaseModel):
    heat_f: float | None = Field(default=None, description="Heat setpoint °F")
    cool_f: float | None = Field(default=None, description="Cool setpoint °F")


class LightsTestBody(BaseModel):
    brightness: int | None = Field(default=50, description="0–100")
    light_color_hex: str = Field(default="#E8F4FF", description="Target color")


def _smart_plug_config_from_request(body: PlugTestBody | None = None) -> dict[str, Any]:
    from roomos.integrations.device_bridge import plug_runtime_config

    doc = load_integrations()
    plug = doc.get("devices", {}).get("smartPlug", {})
    if not isinstance(plug, dict):
        plug = {}
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
    thermo = doc.get("devices", {}).get("thermostat", {})
    if not isinstance(thermo, dict):
        thermo = {}
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


def _lights_config_from_request() -> dict[str, Any]:
    from roomos.integrations.device_bridge import lights_runtime_config

    doc = load_integrations()
    lights = doc.get("devices", {}).get("lights", {})
    if not isinstance(lights, dict):
        lights = {}
    cfg = lights_runtime_config(lights)
    cfg["enabled"] = True
    return cfg


def _maybe_heal_plug_host(cfg: dict[str, Any], result: dict[str, Any]) -> None:
    """If discovery found the plug at a new IP, persist it so it stops drifting."""
    new_host = str(result.get("host") or "").strip()
    old_host = str(cfg.get("host") or "").strip()
    if not new_host or new_host == old_host:
        return
    try:
        doc = load_integrations()
        plug = doc.get("devices", {}).get("smartPlug")
        if isinstance(plug, dict):
            plug["host"] = new_host
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


@router.post("/smart-plug/test")
def test_smart_plug(body: PlugTestBody) -> dict[str, Any]:
    state = (body.state or "on").strip().lower()
    if state not in ("on", "off"):
        raise HTTPException(status_code=400, detail="state must be 'on' or 'off'")
    cfg = _smart_plug_config_from_request(body)
    try:
        from roomos.devices.smart_plug import apply_smart_plug_state

        result = asyncio.run(apply_smart_plug_state(cfg, state))
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
        from roomos.devices.thermostat import apply_thermostat_setpoints

        result = asyncio.run(
            apply_thermostat_setpoints(
                cfg,
                heat_f=float(heat) if heat is not None else None,
                cool_f=float(cool) if cool is not None else None,
            )
        )
        return {"ok": True, **result}
    except Exception as e:
        log.warning("Thermostat test failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/lights/test")
def test_lights(body: LightsTestBody) -> dict[str, Any]:
    cfg = _lights_config_from_request()
    brightness = 50 if body.brightness is None else max(0, min(100, int(body.brightness)))
    scene = {"brightness": brightness, "lightColorHex": body.light_color_hex or "#E8F4FF"}
    try:
        from roomos.devices.lights_control import apply_lights_scene

        result = apply_lights_scene(cfg, scene)
        return {"ok": True, **result}
    except Exception as e:
        log.warning("Lights test failed: %s", e)
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
