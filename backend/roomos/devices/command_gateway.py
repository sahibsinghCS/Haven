"""Device command gateway — all writes go through the action arbiter."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .action_arbiter import (
    ActionSource,
    ArbiterDecision,
    DeviceActionIntent,
    fingerprint_lights,
    fingerprint_plug,
    fingerprint_thermostat,
    get_arbiter,
)
from .lights_control import apply_lights_scene
from .smart_plug import apply_smart_plug_state
from .thermostat import apply_thermostat_setpoints


def _arbiter_result(
    decision: ArbiterDecision,
    *,
    executed: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "executed": executed,
        "arbiter": decision.to_dict(),
    }
    if not decision.allowed:
        out["skipped"] = True
        out["reason"] = decision.reason
        out["explanation"] = decision.explanation
    if extra:
        out.update(extra)
    return out


async def gateway_apply_plug(
    config: Dict[str, Any],
    state: str,
    *,
    source: ActionSource,
    device_id: str,
    dry_run: bool = False,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply smart-plug state through the arbiter."""
    did = str(device_id or config.get("id") or config.get("deviceId") or config.get("host") or "plug")
    fp = fingerprint_plug(did, state)
    intent = DeviceActionIntent(
        source=source,
        device_id=did,
        category="smartPlugs",
        fingerprint=fp,
        dry_run=dry_run,
        context=dict(context or {}),
    )
    decision = get_arbiter().plan(intent)
    if not decision.allowed:
        return _arbiter_result(decision)

    if dry_run:
        return _arbiter_result(
            decision,
            executed=False,
            extra={"dry_run": True, "state": state, "would_apply": fp},
        )

    result = await apply_smart_plug_state(config, state)
    get_arbiter().record_success(intent)
    return _arbiter_result(decision, executed=True, extra=result)


async def gateway_apply_thermostat(
    config: Dict[str, Any],
    *,
    source: ActionSource,
    device_id: str,
    heat_f: Optional[float] = None,
    cool_f: Optional[float] = None,
    dry_run: bool = False,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    did = str(device_id or config.get("id") or config.get("deviceId") or "thermostat")
    fp = fingerprint_thermostat(did, heat_f, cool_f)
    intent = DeviceActionIntent(
        source=source,
        device_id=did,
        category="thermostats",
        fingerprint=fp,
        dry_run=dry_run,
        context=dict(context or {}),
    )
    decision = get_arbiter().plan(intent)
    if not decision.allowed:
        return _arbiter_result(decision)

    if dry_run:
        return _arbiter_result(
            decision,
            executed=False,
            extra={"dry_run": True, "heat_f": heat_f, "cool_f": cool_f, "would_apply": fp},
        )

    result = await apply_thermostat_setpoints(config, heat_f=heat_f, cool_f=cool_f)
    get_arbiter().record_success(intent)
    return _arbiter_result(decision, executed=True, extra=result)


def gateway_apply_lights(
    config: Dict[str, Any],
    scene: Dict[str, Any],
    *,
    source: ActionSource,
    device_id: str,
    dry_run: bool = False,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    did = str(device_id or config.get("id") or config.get("deviceId") or "lights")
    brightness = max(0, min(100, int(scene.get("brightness", 30))))
    hex_color = str(scene.get("lightColorHex", "#FFFFFF"))
    fp = fingerprint_lights(did, brightness, hex_color)
    intent = DeviceActionIntent(
        source=source,
        device_id=did,
        category="lights",
        fingerprint=fp,
        dry_run=dry_run,
        context=dict(context or {}),
    )
    decision = get_arbiter().plan(intent)
    if not decision.allowed:
        return _arbiter_result(decision)

    if dry_run:
        return _arbiter_result(
            decision,
            executed=False,
            extra={
                "dry_run": True,
                "brightness": brightness,
                "lightColorHex": hex_color,
                "would_apply": fp,
            },
        )

    result = apply_lights_scene(config, scene)
    executed = bool(result.get("executed", True)) and not result.get("skipped")
    if executed:
        get_arbiter().record_success(intent)
    return _arbiter_result(decision, executed=executed, extra=result)
