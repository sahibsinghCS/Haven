"""When room state changes, push the preference scene to plugs, thermostat, and lights."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, FrozenSet, Optional

from ..integrations.device_bridge import (
    lights_runtime_config,
    load_ui_device_settings,
    merge_runtime_integrations,
    plug_runtime_config,
    thermostat_runtime_config,
)
from ..utils.logging import get_logger
from .lights_control import apply_lights_scene
from .smart_plug import apply_smart_plug_state
from .thermostat import apply_thermostat_setpoints

log = get_logger("roomos.devices.scene_apply")


def _device_array(devices: Dict[str, Any], key: str, legacy_key: str) -> list[dict[str, Any]]:
    items = devices.get(key)
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    legacy = devices.get(legacy_key)
    if isinstance(legacy, dict):
        return [legacy]
    return []


def _scene_devices_map(scene: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    devices_in = scene.get("devices")
    if isinstance(devices_in, dict):
        return {str(k): dict(v) if isinstance(v, dict) else {} for k, v in devices_in.items()}
    return {}


def _legacy_scene_values(scene: Dict[str, Any]) -> tuple[bool, int, str, str]:
    fan_on = bool(scene.get("fanOn", False))
    temp_f = int(scene.get("temperatureF", 72))
    brightness = int(scene.get("brightness", 30))
    color = str(scene.get("lightColorHex", "#2A2A2A"))
    return fan_on, temp_f, brightness, color


def _ui_devices_map() -> Dict[str, Any]:
    ui = load_ui_device_settings()
    devices = ui.get("devices")
    return devices if isinstance(devices, dict) else {}


def _device_id_categories(ui_devices: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for plug in _device_array(ui_devices, "smartPlugs", "smartPlug"):
        device_id = str(plug.get("id") or "").strip()
        if device_id:
            out[device_id] = "smartPlugs"
    for lights in _device_array(ui_devices, "lights", "lights"):
        device_id = str(lights.get("id") or "").strip()
        if device_id:
            out[device_id] = "lights"
    for thermo in _device_array(ui_devices, "thermostats", "thermostat"):
        device_id = str(thermo.get("id") or "").strip()
        if device_id:
            out[device_id] = "thermostats"
    return out


def connected_device_categories() -> FrozenSet[str]:
    """Device categories that are connected + enabled in Settings."""
    cats: set[str] = set()
    ui_devices = _ui_devices_map()
    for plug in _device_array(ui_devices, "smartPlugs", "smartPlug"):
        if plug.get("connected") and plug.get("enabled"):
            cats.add("smartPlugs")
            break
    for lights in _device_array(ui_devices, "lights", "lights"):
        if lights.get("connected") and lights.get("enabled"):
            cats.add("lights")
            break
    for thermo in _device_array(ui_devices, "thermostats", "thermostat"):
        if (
            thermo.get("connected")
            and thermo.get("enabled")
            and thermo.get("brand") not in ("none", "")
        ):
            cats.add("thermostats")
            break
    return frozenset(cats)


def scene_to_display_targets(
    scene: Dict[str, Any],
    *,
    connected: Optional[FrozenSet[str]] = None,
) -> Dict[str, Any]:
    """Flatten v2 per-device scene for live UI display (connected categories only)."""
    if connected is None:
        connected = connected_device_categories()

    devices_map = _scene_devices_map(scene)
    id_to_cat = _device_id_categories(_ui_devices_map())

    fan_on: Optional[bool] = None
    temp_f: Optional[int] = None
    brightness: Optional[int] = None
    color: Optional[str] = None

    if devices_map:
        for device_id, target in devices_map.items():
            category = id_to_cat.get(device_id)
            if category not in connected:
                continue
            if category == "smartPlugs" and "fanOn" in target:
                fan_on = bool(target.get("fanOn"))
            if category == "thermostats" and "temperatureF" in target:
                temp_f = int(target.get("temperatureF", temp_f or 72))
            if category == "lights":
                if "brightness" in target:
                    brightness = int(target.get("brightness", brightness or 30))
                if "lightColorHex" in target:
                    color = str(target.get("lightColorHex", color or "#2A2A2A"))
    else:
        legacy_fan, legacy_temp, legacy_brightness, legacy_color = _legacy_scene_values(scene)
        if "smartPlugs" in connected:
            fan_on = legacy_fan
        if "thermostats" in connected:
            temp_f = legacy_temp
        if "lights" in connected:
            brightness = legacy_brightness
            color = legacy_color

    out: Dict[str, Any] = {}
    if fan_on is not None:
        out["fanOn"] = fan_on
    if temp_f is not None:
        out["temperatureF"] = temp_f
    if brightness is not None:
        out["brightness"] = brightness
    if color is not None:
        out["lightColorHex"] = color
    return out


def _device_ready(device: dict[str, Any], *, category: str) -> bool:
    if not device.get("connected") or not device.get("enabled"):
        return False
    if category == "thermostats" and device.get("brand") in ("none", ""):
        return False
    return True


def has_controllable_devices() -> bool:
    """True when Settings has at least one connected + enabled device to drive."""
    return bool(connected_device_categories())


def resolve_apply_scene_for_mood(room_state: str) -> Dict[str, Any]:
    """Hydrated v2 preference scene for ``room_state`` (saved prefs or mood defaults)."""
    from app.preferences_service import load_preferences
    from ..preferences.document import (
        ROOM_STATE_ORDER,
        _LEGACY_MOOD_DEFAULTS,
        _connected_device_ids_by_category,
        _migrate_scene_to_v2,
        active_preset_preferences,
    )

    scenes = active_preset_preferences(load_preferences())
    if room_state in scenes:
        return scenes[room_state]
    try:
        from ..moods.registry import active_mood_ids

        valid_moods = set(active_mood_ids())
    except Exception:
        valid_moods = set(ROOM_STATE_ORDER)
    if room_state in valid_moods:
        legacy = _LEGACY_MOOD_DEFAULTS.get(room_state, _LEGACY_MOOD_DEFAULTS["work"])
        return _migrate_scene_to_v2(
            legacy,
            _connected_device_ids_by_category(),
            state=room_state,
        )
    return {}


def preference_sync_dry_run(actions_dry_run: bool) -> bool:
    """Preferences → device control is live when Settings devices exist, even if action rules are dry-run."""
    if not actions_dry_run:
        return False
    return not has_controllable_devices()


def _target_for_device(
    device_id: str,
    scene: Dict[str, Any],
    *,
    category: str,
) -> Dict[str, Any]:
    devices_map = _scene_devices_map(scene)
    if device_id in devices_map:
        return devices_map[device_id]
    fan_on, temp_f, brightness, color = _legacy_scene_values(scene)
    if category == "smartPlugs":
        return {"fanOn": fan_on}
    if category == "lights":
        return {"brightness": brightness, "lightColorHex": color}
    if category == "thermostats":
        return {"temperatureF": temp_f}
    return {}


async def apply_preference_scene_async(
    scene: Dict[str, Any],
    *,
    dry_run: bool = True,
    integrations: Optional[Dict[str, Any]] = None,
    room_state: str = "",
) -> Dict[str, Any]:
    """Apply per-device fan / temperature / lights from the active preset for ``room_state``."""
    merged = merge_runtime_integrations(dict(integrations or {}))
    ui = load_ui_device_settings()
    ui_devices = ui.get("devices") if isinstance(ui.get("devices"), dict) else {}

    record: Dict[str, Any] = {
        "rule": "preference_sync",
        "activity": room_state,
        "action_type": "preference_sync",
        "dry_run": dry_run,
        "scene": scene_to_display_targets(scene),
        "results": {},
    }

    if dry_run:
        would: Dict[str, Any] = {}
        for plug in _device_array(ui_devices, "smartPlugs", "smartPlug"):
            if not _device_ready(plug, category="smartPlugs"):
                continue
            device_id = str(plug.get("id") or "")
            target = _target_for_device(device_id, scene, category="smartPlugs")
            key = device_id or plug.get("label") or "smart_plug"
            would[f"smart_plug:{key}"] = "on" if target.get("fanOn") else "off"
        for lights in _device_array(ui_devices, "lights", "lights"):
            if not _device_ready(lights, category="lights"):
                continue
            device_id = str(lights.get("id") or "")
            target = _target_for_device(device_id, scene, category="lights")
            key = device_id or lights.get("label") or "lights"
            would[f"lights:{key}"] = {
                "brightness": int(target.get("brightness", 30)),
                "color": str(target.get("lightColorHex", "#2A2A2A")),
            }
        for thermo in _device_array(ui_devices, "thermostats", "thermostat"):
            if not _device_ready(thermo, category="thermostats"):
                continue
            device_id = str(thermo.get("id") or "")
            target = _target_for_device(device_id, scene, category="thermostats")
            key = device_id or thermo.get("notes") or "thermostat"
            would[f"thermostat:{key}"] = int(target.get("temperatureF", 72))
        record["executed"] = False
        record["skipped"] = True
        record["reason"] = "dry_run"
        record["would_apply"] = would
        log.info("[preference_sync] DRY-RUN state=%s would=%s", room_state, list(would.keys()))
        return record

    any_enabled = False
    results: Dict[str, Any] = {}
    errors: list[str] = []

    for plug in _device_array(ui_devices, "smartPlugs", "smartPlug"):
        if not _device_ready(plug, category="smartPlugs"):
            continue
        any_enabled = True
        device_id = str(plug.get("id") or "")
        cfg = plug_runtime_config(plug)
        target = _target_for_device(device_id, scene, category="smartPlugs")
        fan_on = bool(target.get("fanOn", False))
        result_key = f"smart_plug:{device_id or cfg.get('host', 'plug')}"
        try:
            results[result_key] = await apply_smart_plug_state(cfg, "on" if fan_on else "off")
        except Exception as e:
            errors.append(f"{result_key}: {e}")
            results[result_key] = {"executed": False, "error": str(e)}

    for thermo in _device_array(ui_devices, "thermostats", "thermostat"):
        if not _device_ready(thermo, category="thermostats"):
            continue
        any_enabled = True
        device_id = str(thermo.get("id") or "")
        cfg = thermostat_runtime_config(thermo)
        target = _target_for_device(device_id, scene, category="thermostats")
        temp_f = float(target.get("temperatureF", 72))
        result_key = f"thermostat:{device_id or cfg.get('notes', 'thermostat')}"
        try:
            results[result_key] = await apply_thermostat_setpoints(
                cfg,
                heat_f=temp_f,
                cool_f=temp_f + 2.0,
            )
        except Exception as e:
            errors.append(f"{result_key}: {e}")
            results[result_key] = {"executed": False, "error": str(e)}

    for lights in _device_array(ui_devices, "lights", "lights"):
        if not _device_ready(lights, category="lights"):
            continue
        any_enabled = True
        device_id = str(lights.get("id") or "")
        cfg = lights_runtime_config(lights)
        target = _target_for_device(device_id, scene, category="lights")
        scene_payload = {
            "brightness": int(target.get("brightness", 30)),
            "lightColorHex": str(target.get("lightColorHex", "#2A2A2A")),
        }
        result_key = f"lights:{device_id or cfg.get('label', 'lights')}"
        try:
            results[result_key] = apply_lights_scene(cfg, scene_payload)
        except Exception as e:
            errors.append(f"{result_key}: {e}")
            results[result_key] = {"executed": False, "error": str(e)}

    record["results"] = results
    record["executed"] = bool(results) and not errors
    if errors:
        record["errors"] = errors
    if not any_enabled:
        record["executed"] = False
        record["skipped"] = True
        record["reason"] = "no_devices_enabled"
    else:
        log.info("[preference_sync] state=%s — applied %s", room_state, list(results.keys()))

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
    for key, val in results.items():
        if isinstance(val, dict) and val.get("executed") is False:
            parts.append(f"{key}: failed")
        else:
            parts.append(str(key))
    return "preference sync → " + ", ".join(parts) if parts else "preference sync"
