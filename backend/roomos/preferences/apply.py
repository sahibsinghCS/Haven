"""Apply Telegram / NL preference edits to the active preset matrix."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .document import PreferenceValidationError, _connected_device_ids_by_category, resolve_active_preset_id

_UI_STATES = ("sleep", "work", "relaxing", "away")

_NAMED_COLORS: dict[str, str] = {
    "red": "#EF4444",
    "orange": "#F97316",
    "amber": "#F59E0B",
    "yellow": "#EAB308",
    "green": "#22C55E",
    "teal": "#14B8A6",
    "cyan": "#06B6D4",
    "blue": "#3B82F6",
    "indigo": "#6366F1",
    "purple": "#8B5CF6",
    "pink": "#EC4899",
    "white": "#F8FAFC",
    "warm white": "#F5E6C8",
    "cool white": "#E8F4FF",
    "warm": "#F5D0A8",
    "cool": "#C8E8FF",
}


@dataclass
class PreferenceChangeSpec:
    target_states: List[str] = field(default_factory=list)
    fan: Optional[str] = None  # on | off | lower | higher
    brightness: Optional[dict[str, Any]] = None
    light_color: Optional[dict[str, Any]] = None
    temperature_f: Optional[dict[str, Any]] = None


@dataclass
class PreferenceApplyResult:
    doc: dict[str, Any]
    preset_name: str
    active_preset_id: str
    target_states: List[str]
    changes: List[str]


def _clamp_brightness(value: int) -> int:
    return max(0, min(100, int(value)))


def _clamp_temp(value: int) -> int:
    return max(60, min(82, int(value)))


def _normalize_hex(value: str) -> Optional[str]:
    s = str(value or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", s):
        return s.upper()
    if re.fullmatch(r"[0-9A-Fa-f]{6}", s):
        return f"#{s.upper()}"
    return None


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02X}{max(0, min(255, g)):02X}{max(0, min(255, b)):02X}"


def _shift_color(hex_color: str, *, warmer: bool) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    if warmer:
        r = min(255, r + 35)
        g = min(255, g + 18)
        b = max(0, b - 25)
    else:
        r = max(0, r - 20)
        g = max(0, g - 10)
        b = min(255, b + 35)
    return _rgb_to_hex(r, g, b)


def _resolve_brightness(current: int, spec: Optional[dict[str, Any]]) -> tuple[int, str]:
    if not spec:
        return current, ""
    if "absolute" in spec and spec["absolute"] is not None:
        v = _clamp_brightness(int(spec["absolute"]))
        return v, f"brightness → {v}%"
    rel = str(spec.get("relative", "")).lower()
    if rel in ("lower", "dim", "dimmer", "down"):
        v = _clamp_brightness(current - 25)
        return v, f"brightness → {v}% (lower)"
    if rel in ("higher", "brighter", "up", "bright"):
        v = _clamp_brightness(current + 25)
        return v, f"brightness → {v}% (higher)"
    if "delta" in spec and spec["delta"] is not None:
        v = _clamp_brightness(current + int(spec["delta"]))
        return v, f"brightness → {v}%"
    return current, ""


def _resolve_temperature(current: int, spec: Optional[dict[str, Any]]) -> tuple[int, str]:
    if not spec:
        return current, ""
    if "absolute" in spec and spec["absolute"] is not None:
        v = _clamp_temp(int(spec["absolute"]))
        return v, f"temperature → {v}°F"
    rel = str(spec.get("relative", "")).lower()
    if rel in ("lower", "cooler", "down", "cool"):
        v = _clamp_temp(current - 2)
        return v, f"temperature → {v}°F (cooler)"
    if rel in ("higher", "warmer", "up", "warm"):
        v = _clamp_temp(current + 2)
        return v, f"temperature → {v}°F (warmer)"
    if "delta" in spec and spec["delta"] is not None:
        v = _clamp_temp(current + int(spec["delta"]))
        return v, f"temperature → {v}°F"
    return current, ""


def _resolve_light_color(current: str, spec: Optional[dict[str, Any]]) -> tuple[str, str]:
    if not spec:
        return current, ""
    hx = spec.get("hex")
    if hx:
        norm = _normalize_hex(str(hx))
        if norm:
            return norm, f"light → {norm}"
    name = str(spec.get("name", "")).lower().strip()
    if name and name in _NAMED_COLORS:
        c = _NAMED_COLORS[name]
        return c, f"light → {name} ({c})"
    rel = str(spec.get("relative", "")).lower()
    if rel in ("warmer", "warm"):
        c = _shift_color(current, warmer=True)
        return c, f"light → warmer ({c})"
    if rel in ("cooler", "cool"):
        c = _shift_color(current, warmer=False)
        return c, f"light → cooler ({c})"
    return current, ""


def _resolve_fan(current: bool, fan: Optional[str]) -> tuple[bool, str]:
    if not fan:
        return current, ""
    key = str(fan).lower().strip()
    if key in ("on", "enable", "enabled", "high", "higher"):
        return True, "fan → on"
    if key in ("off", "disable", "disabled", "low", "lower"):
        return False, "fan → off"
    return current, ""


def _ensure_scene_devices(scene: dict[str, Any]) -> dict[str, dict[str, Any]]:
    devices_in = scene.get("devices")
    if isinstance(devices_in, dict):
        return devices_in
    scene["devices"] = {}
    return scene["devices"]


def _first_device_ids(ids_by_cat: dict[str, list[str]]) -> dict[str, Optional[str]]:
    return {
        "plug": ids_by_cat.get("smartPlugs", [None])[0] if ids_by_cat.get("smartPlugs") else None,
        "lights": ids_by_cat.get("lights", [None])[0] if ids_by_cat.get("lights") else None,
        "thermo": ids_by_cat.get("thermostats", [None])[0] if ids_by_cat.get("thermostats") else None,
    }


def _apply_to_scene(scene: dict[str, Any], spec: PreferenceChangeSpec) -> List[str]:
    lines: List[str] = []
    ids_by_cat = _connected_device_ids_by_category()
    first_ids = _first_device_ids(ids_by_cat)
    devices = _ensure_scene_devices(scene)

    if spec.fan:
        plug_ids = ids_by_cat.get("smartPlugs", [])
        for plug_id in plug_ids:
            target = dict(devices.get(plug_id) or {})
            fan_val, fan_line = _resolve_fan(bool(target.get("fanOn", False)), spec.fan)
            if fan_line:
                target["fanOn"] = fan_val
                devices[plug_id] = target
                lines.append(fan_line)
                break

    if spec.brightness or spec.light_color:
        lights_ids = ids_by_cat.get("lights", [])
        for lights_id in lights_ids:
            target = dict(devices.get(lights_id) or {})
            changed = False
            bright_val, bright_line = _resolve_brightness(int(target.get("brightness", 30)), spec.brightness)
            if bright_line:
                target["brightness"] = bright_val
                lines.append(bright_line)
                changed = True
            color_val, color_line = _resolve_light_color(
                str(target.get("lightColorHex", "#2A2A2A")),
                spec.light_color,
            )
            if color_line:
                target["lightColorHex"] = color_val
                lines.append(color_line)
                changed = True
            if changed:
                devices[lights_id] = target
                break

    if spec.temperature_f:
        thermo_ids = ids_by_cat.get("thermostats", [])
        for thermo_id in thermo_ids:
            target = dict(devices.get(thermo_id) or {})
            temp_val, temp_line = _resolve_temperature(int(target.get("temperatureF", 72)), spec.temperature_f)
            if temp_line:
                target["temperatureF"] = temp_val
                devices[thermo_id] = target
                lines.append(temp_line)
                break

    if not lines and not devices:
        # Legacy flat fallback when no connected devices
        legacy = {
            "lightColorHex": str(scene.get("lightColorHex", "#2A2A2A")),
            "brightness": int(scene.get("brightness", 30)),
            "fanOn": bool(scene.get("fanOn", False)),
            "temperatureF": int(scene.get("temperatureF", 72)),
        }
        fan_val, fan_line = _resolve_fan(legacy["fanOn"], spec.fan)
        if fan_line:
            legacy["fanOn"] = fan_val
            lines.append(fan_line)
        bright_val, bright_line = _resolve_brightness(legacy["brightness"], spec.brightness)
        if bright_line:
            legacy["brightness"] = bright_val
            lines.append(bright_line)
        color_val, color_line = _resolve_light_color(legacy["lightColorHex"], spec.light_color)
        if color_line:
            legacy["lightColorHex"] = color_val
            lines.append(color_line)
        temp_val, temp_line = _resolve_temperature(legacy["temperatureF"], spec.temperature_f)
        if temp_line:
            legacy["temperatureF"] = temp_val
            lines.append(temp_line)
        if first_ids["plug"] and legacy.get("fanOn") is not None:
            devices[str(first_ids["plug"])] = {"fanOn": legacy["fanOn"]}
        if first_ids["lights"]:
            devices[str(first_ids["lights"])] = {
                "brightness": legacy["brightness"],
                "lightColorHex": legacy["lightColorHex"],
            }
        if first_ids["thermo"]:
            devices[str(first_ids["thermo"])] = {"temperatureF": legacy["temperatureF"]}

    scene["devices"] = devices
    return lines


def apply_preference_changes(
    doc: dict[str, Any],
    spec: PreferenceChangeSpec,
    *,
    fallback_state: Optional[str] = None,
) -> PreferenceApplyResult:
    states = [s for s in spec.target_states if s in _UI_STATES]
    if not states:
        fb = str(fallback_state or "").strip()
        if fb in _UI_STATES:
            states = [fb]
        else:
            states = ["work"]

    presets = doc.get("presets")
    if not isinstance(presets, list) or not presets:
        raise PreferenceValidationError("No presets in document.")

    active_id = resolve_active_preset_id(doc)
    active = next((p for p in presets if isinstance(p, dict) and str(p.get("id")) == active_id), None)
    if not isinstance(active, dict):
        raise PreferenceValidationError(f"Active preset {active_id!r} not found.")

    prefs = active.get("preferences")
    if not isinstance(prefs, dict):
        raise PreferenceValidationError("Active preset has no preferences matrix.")

    all_changes: List[str] = []
    for state in states:
        scene = prefs.get(state)
        if not isinstance(scene, dict):
            scene = {"devices": {}}
            prefs[state] = scene
        lines = _apply_to_scene(scene, spec)
        for line in lines:
            all_changes.append(f"{state}: {line}")

    if not all_changes:
        raise PreferenceValidationError("No preference fields were changed — try being more specific.")

    preset_name = str(active.get("name", active_id))
    return PreferenceApplyResult(
        doc=doc,
        preset_name=preset_name,
        active_preset_id=active_id,
        target_states=states,
        changes=all_changes,
    )
