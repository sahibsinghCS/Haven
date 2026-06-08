"""When room state changes, push the preference scene to plugs, thermostat, and lights."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from ..integrations.device_bridge import merge_runtime_integrations
from ..utils.logging import get_logger
from .lights_control import apply_lights_scene
from .smart_plug import apply_smart_plug_state
from .thermostat import apply_thermostat_setpoints

log = get_logger("roomos.devices.scene_apply")


def _scene_values(scene: Dict[str, Any]) -> tuple[bool, int, str]:
    fan_on = bool(scene.get("fanOn", False))
    temp_f = int(scene.get("temperatureF", 72))
    brightness = int(scene.get("brightness", 30))
    color = str(scene.get("lightColorHex", "#2A2A2A"))
    return fan_on, temp_f, brightness, color


async def apply_preference_scene_async(
    scene: Dict[str, Any],
    *,
    dry_run: bool = True,
    integrations: Optional[Dict[str, Any]] = None,
    room_state: str = "",
) -> Dict[str, Any]:
    """Apply fan / temperature / lights from the active preset for ``room_state``."""
    fan_on, temp_f, brightness, color = _scene_values(scene)
    merged = merge_runtime_integrations(dict(integrations or {}))

    record: Dict[str, Any] = {
        "rule": "preference_sync",
        "activity": room_state,
        "action_type": "preference_sync",
        "dry_run": dry_run,
        "scene": {
            "fanOn": fan_on,
            "temperatureF": temp_f,
            "brightness": brightness,
            "lightColorHex": color,
        },
        "results": {},
    }

    if dry_run:
        record["executed"] = False
        record["skipped"] = True
        record["reason"] = "dry_run"
        record["would_apply"] = {
            "smart_plug": "on" if fan_on else "off",
            "thermostat_f": temp_f,
            "lights": {"brightness": brightness, "color": color},
        }
        log.info(
            "[preference_sync] DRY-RUN state=%s fan=%s temp=%sF lights=%s%%",
            room_state,
            fan_on,
            temp_f,
            brightness,
        )
        return record

    any_enabled = False
    results: Dict[str, Any] = {}
    errors: list[str] = []

    plug = merged.get("smart_plug") or {}
    if isinstance(plug, dict) and plug.get("enabled"):
        any_enabled = True
        try:
            results["smart_plug"] = await apply_smart_plug_state(
                plug,
                "on" if fan_on else "off",
            )
        except Exception as e:
            errors.append(f"plug: {e}")
            results["smart_plug"] = {"executed": False, "error": str(e)}

    thermo = merged.get("thermostat") or {}
    if isinstance(thermo, dict) and thermo.get("enabled") and thermo.get("brand") not in ("none", ""):
        any_enabled = True
        try:
            results["thermostat"] = await apply_thermostat_setpoints(
                thermo,
                heat_f=float(temp_f),
                cool_f=float(temp_f) + 2.0,
            )
        except Exception as e:
            errors.append(f"thermostat: {e}")
            results["thermostat"] = {"executed": False, "error": str(e)}

    lights = merged.get("lights") or {}
    if isinstance(lights, dict) and lights.get("enabled"):
        any_enabled = True
        try:
            results["lights"] = apply_lights_scene(
                lights,
                {"brightness": brightness, "lightColorHex": color, "fanOn": fan_on},
            )
        except Exception as e:
            errors.append(f"lights: {e}")
            results["lights"] = {"executed": False, "error": str(e)}

    record["results"] = results
    record["executed"] = bool(results) and not errors
    if errors:
        record["errors"] = errors
    if not any_enabled:
        record["executed"] = False
        record["skipped"] = True
        record["reason"] = "no_devices_enabled"
    else:
        log.info(
            "[preference_sync] state=%s fan=%s temp=%sF — applied %s",
            room_state,
            fan_on,
            temp_f,
            list(results.keys()),
        )

    return record


def apply_preference_scene(
    scene: Dict[str, Any],
    *,
    dry_run: bool = True,
    integrations: Optional[Dict[str, Any]] = None,
    room_state: str = "",
) -> Dict[str, Any]:
    return asyncio.run(
        apply_preference_scene_async(
            scene,
            dry_run=dry_run,
            integrations=integrations,
            room_state=room_state,
        )
    )


def automation_summary(record: Dict[str, Any]) -> str:
    if record.get("dry_run"):
        return "preference sync (dry-run)"
    results = record.get("results") or {}
    parts = []
    plug = results.get("smart_plug") or {}
    if plug.get("state"):
        parts.append(f"plug {plug.get('state')}")
    thermo = results.get("thermostat") or {}
    if thermo.get("heat_setpoint_f") is not None:
        parts.append(f"heat {thermo.get('heat_setpoint_f')}°F")
    lights = results.get("lights") or {}
    if lights.get("executed"):
        parts.append("lights updated")
    return " · ".join(parts) if parts else "preference sync"
