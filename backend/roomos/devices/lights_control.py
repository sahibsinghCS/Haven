"""Apply preference brightness/color to configured lights."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..utils.logging import get_logger

log = get_logger("roomos.devices.lights")


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = str(hex_color or "#FFFFFF").strip().lstrip("#")
    if len(h) == 6:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 255, 255, 255


def apply_lights_scene(config: Dict[str, Any], scene: Dict[str, Any]) -> Dict[str, Any]:
    if not config.get("enabled"):
        return {"executed": False, "skipped": True, "reason": "lights_disabled"}

    brand = str(config.get("brand") or "none").strip().lower()
    brightness = max(0, min(100, int(scene.get("brightness", 30))))
    hex_color = str(scene.get("lightColorHex", "#FFFFFF"))
    power_on = brightness > 0

    if brand in ("none", ""):
        return {"executed": False, "skipped": True, "reason": "no_lights_brand"}

    if brand == "tuya":
        return _apply_tuya_light(config, power_on=power_on, brightness=brightness, hex_color=hex_color)

    # Other brands: record intent until dedicated drivers are added
    return {
        "executed": False,
        "skipped": True,
        "reason": "lights_brand_pending",
        "brand": brand,
        "would_apply": {"power_on": power_on, "brightness": brightness, "color": hex_color},
    }


def _apply_tuya_light(
    config: Dict[str, Any],
    *,
    power_on: bool,
    brightness: int,
    hex_color: str,
) -> Dict[str, Any]:
    import tinytuya

    dev_id = str(config.get("tuyaDeviceId") or "").strip()
    local_key = str(config.get("tuyaLocalKey") or "").strip()
    host = str(config.get("host") or "Auto").strip() or "Auto"
    version_raw = config.get("tuyaVersion") or "3.3"
    try:
        version = float(version_raw)
    except (TypeError, ValueError):
        version = 3.3

    if not dev_id or not local_key:
        raise ValueError("Tuya lights need Device ID and Local Key (same as Smart Life wizard).")

    bulb = tinytuya.BulbDevice(dev_id, host, local_key, version=version)
    if not power_on:
        bulb.turn_off()
    else:
        bulb.turn_on()
        # Many Tuya bulbs: brightness 10–1000 on DPS 3, mode on 2
        try:
            scaled = max(10, min(1000, int(brightness * 10)))
            bulb.set_brightness(scaled)
        except Exception as e:
            log.debug("Tuya set_brightness failed (%s); power state still set.", e)

    return {
        "executed": True,
        "driver": "tuya",
        "brand": "tuya",
        "brightness": brightness,
        "color": hex_color,
        "power_on": power_on,
    }
