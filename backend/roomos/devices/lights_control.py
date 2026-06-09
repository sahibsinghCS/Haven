"""Apply preference brightness/color to configured lights.

Local-first, multi-brand light control. Each brand has a best-effort driver
that maps a scene (brightness 0-100 + hex color) to power/brightness/color.
Every driver lazy-imports its dependency and raises a *clear, actionable*
error rather than crashing when a library is missing or a device needs a
pairing step (Hue link button, Nanoleaf power-button token, Govee LAN mode).

Only the Tuya path and the shared python-kasa manager are exercised against
real-ish hardware here; the rest are implemented to spec and verified by
routing/unit tests. They fail with guidance instead of hanging.
"""

from __future__ import annotations

import asyncio
import json
import socket
from typing import Any, Dict, Tuple

from ..utils.logging import get_logger

log = get_logger("roomos.devices.lights")


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = str(hex_color or "#FFFFFF").strip().lstrip("#")
    if len(h) == 6:
        try:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except ValueError:
            pass
    return 255, 255, 255


def _run_async(coro: Any) -> Any:
    """Run an async driver from the synchronous endpoint context."""
    return asyncio.run(coro)


# --------------------------------------------------------------------------
# router
# --------------------------------------------------------------------------
def apply_lights_scene(config: Dict[str, Any], scene: Dict[str, Any]) -> Dict[str, Any]:
    if not config.get("enabled"):
        return {"executed": False, "skipped": True, "reason": "lights_disabled"}

    brand = str(config.get("brand") or "none").strip().lower()
    brightness = max(0, min(100, int(scene.get("brightness", 30))))
    hex_color = str(scene.get("lightColorHex", "#FFFFFF"))
    power_on = brightness > 0

    if brand in ("none", ""):
        return {"executed": False, "skipped": True, "reason": "no_lights_brand"}

    driver = _DRIVERS.get(brand)
    if driver is None:
        return {
            "executed": False,
            "skipped": True,
            "reason": "lights_brand_pending",
            "brand": brand,
            "would_apply": {"power_on": power_on, "brightness": brightness, "color": hex_color},
        }

    result = driver(config, power_on=power_on, brightness=brightness, hex_color=hex_color)
    result.setdefault("brand", brand)
    result.setdefault("brightness", brightness)
    result.setdefault("color", hex_color)
    result.setdefault("power_on", power_on)
    result.setdefault("executed", True)
    return result


# --------------------------------------------------------------------------
# Tuya / Smart Life (existing)
# --------------------------------------------------------------------------
def _apply_tuya_light(config, *, power_on, brightness, hex_color) -> Dict[str, Any]:
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

    try:
        import tinytuya
    except ImportError as e:
        raise ValueError("Tuya support is not installed. From the backend folder: pip install tinytuya") from e

    bulb = tinytuya.BulbDevice(dev_id, host, local_key, version=version)
    if not power_on:
        bulb.turn_off()
    else:
        bulb.turn_on()
        try:
            scaled = max(10, min(1000, int(brightness * 10)))
            bulb.set_brightness(scaled)
        except Exception as e:  # noqa: BLE001
            log.debug("Tuya set_brightness failed (%s); power state still set.", e)
    return {"driver": "tuya"}


# --------------------------------------------------------------------------
# TP-Link Kasa / Tapo bulbs & strips (shared persistent manager)
# --------------------------------------------------------------------------
def _apply_kasa_light(config, *, power_on, brightness, hex_color) -> Dict[str, Any]:
    host = str(config.get("host") or "").strip()
    if not host:
        raise ValueError("Kasa/Tapo bulb needs a host IP. Run 'Scan my network' to fill it in.")
    email = str(config.get("tapoEmail") or config.get("username") or "").strip()
    password = str(config.get("tapoPassword") or config.get("password") or "").strip()
    r, g, b = _hex_to_rgb(hex_color)

    try:
        from ..actions.tapo_manager import get_tapo_manager
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Kasa light manager unavailable: {e}") from e

    async def _op(device: Any) -> Dict[str, Any]:
        if not power_on:
            await device.turn_off()
            return {"driver": "kasa_light"}
        await device.turn_on()
        await _kasa_set_light(device, brightness=brightness, rgb=(r, g, b))
        try:
            await device.update()
        except Exception:
            pass
        return {"driver": "kasa_light"}

    mgr = get_tapo_manager()
    return mgr.run(
        host,
        _op,
        email=email,
        password=password,
        timeout_sec=12.0,
        label=str(config.get("notes") or "Kasa light"),
        allow_discovery=True,
    )


async def _kasa_set_light(device: Any, *, brightness: int, rgb: Tuple[int, int, int]) -> None:
    """Set brightness/color across python-kasa IOT and SMART light variants."""
    import colorsys

    r, g, b = rgb
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    hue = int(h * 360)
    sat = int(s * 100)

    # Try the modern modules API first (SMART/Tapo + newer kasa).
    try:
        from kasa import Module

        light = device.modules.get(Module.Light) if hasattr(device, "modules") else None
        if light is not None:
            if getattr(light, "is_color", False) and (r, g, b) != (255, 255, 255):
                await light.set_hsv(hue, sat, max(1, brightness))
            elif getattr(light, "is_dimmable", True):
                await light.set_brightness(max(1, brightness))
            return
    except Exception as e:  # noqa: BLE001
        log.debug("kasa modules light path failed (%s); trying legacy", e)

    # Legacy IOT bulb API.
    try:
        if getattr(device, "is_color", False) and (r, g, b) != (255, 255, 255):
            await device.set_hsv(hue, sat, max(1, brightness))
        elif getattr(device, "is_dimmable", False):
            await device.set_brightness(max(1, brightness))
    except Exception as e:  # noqa: BLE001
        log.debug("kasa legacy light path failed: %s", e)


# --------------------------------------------------------------------------
# WiZ (pywizlight, UDP)
# --------------------------------------------------------------------------
def _apply_wiz(config, *, power_on, brightness, hex_color) -> Dict[str, Any]:
    host = str(config.get("host") or "").strip()
    if not host:
        raise ValueError("WiZ bulb needs a host IP. Run 'Scan my network' to fill it in.")
    try:
        from pywizlight import PilotBuilder, wizlight
    except ImportError as e:
        raise ValueError("WiZ support is not installed. From the backend folder: pip install pywizlight") from e

    r, g, b = _hex_to_rgb(hex_color)

    async def _go() -> None:
        light = wizlight(host)
        try:
            if not power_on:
                await light.turn_off()
            else:
                await light.turn_on(PilotBuilder(rgb=(r, g, b), brightness=max(1, int(brightness * 255 / 100))))
        finally:
            try:
                await light.async_close()
            except Exception:
                pass

    _run_async(_go())
    return {"driver": "wiz"}


# --------------------------------------------------------------------------
# Yeelight (LAN, sync lib)
# --------------------------------------------------------------------------
def _apply_yeelight(config, *, power_on, brightness, hex_color) -> Dict[str, Any]:
    host = str(config.get("host") or "").strip()
    if not host:
        raise ValueError("Yeelight needs a host IP. Enable LAN Control in the Yeelight app, then scan.")
    try:
        import yeelight
    except ImportError as e:
        raise ValueError("Yeelight support is not installed. From the backend folder: pip install yeelight") from e

    r, g, b = _hex_to_rgb(hex_color)
    bulb = yeelight.Bulb(host, auto_on=power_on)
    if not power_on:
        bulb.turn_off()
    else:
        bulb.turn_on()
        try:
            bulb.set_brightness(max(1, brightness))
            if (r, g, b) != (255, 255, 255):
                bulb.set_rgb(r, g, b)
        except Exception as e:  # noqa: BLE001
            log.debug("Yeelight color/brightness failed (%s); power set.", e)
    return {"driver": "yeelight"}


# --------------------------------------------------------------------------
# LIFX (LAN UDP protocol, no extra runtime control dep needed)
# --------------------------------------------------------------------------
def _apply_lifx(config, *, power_on, brightness, hex_color) -> Dict[str, Any]:
    host = str(config.get("host") or "").strip()
    if not host:
        raise ValueError("LIFX bulb needs a host IP. Run 'Scan my network' to fill it in.")
    import colorsys
    import struct

    r, g, b = _hex_to_rgb(hex_color)
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    hue16 = int(h * 65535)
    sat16 = int(s * 65535)
    bri16 = int(max(1, brightness) / 100 * 65535) if power_on else 0
    kelvin = 3500

    def _frame(pkt_type: int, payload: bytes) -> bytes:
        size = 36 + len(payload)
        # frame header (size, protocol=1024, addressable+tagged, source)
        frame = struct.pack("<HHI", size, 0x3400, 0)
        # frame address (target 8 bytes, reserved 6, flags res_required, sequence)
        frame_addr = struct.pack("<8sHHBB", b"\x00" * 8, 0, 0, 0x01, 0)
        # protocol header (reserved, type, reserved)
        proto = struct.pack("<QHH", 0, pkt_type, 0)
        return frame + frame_addr + proto + payload

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(2.0)
        # SetPower (117): level uint16, duration uint32
        set_power = struct.pack("<HI", 65535 if power_on else 0, 400)
        sock.sendto(_frame(117, set_power), (host, 56700))
        if power_on:
            # SetColor (102): reserved uint8, HSBK (4x uint16), duration uint32
            set_color = struct.pack("<BHHHHI", 0, hue16, sat16, bri16, kelvin, 400)
            sock.sendto(_frame(102, set_color), (host, 56700))
    finally:
        sock.close()
    return {"driver": "lifx"}


# --------------------------------------------------------------------------
# Philips Hue (local bridge REST + link-button key minting)
# --------------------------------------------------------------------------
def _apply_hue(config, *, power_on, brightness, hex_color) -> Dict[str, Any]:
    import httpx

    host = str(config.get("host") or config.get("hueBridgeIp") or "").strip()
    if not host:
        raise ValueError("Philips Hue needs the bridge IP. Run 'Scan my network' to find it.")
    app_key = str(config.get("hueAppKey") or "").strip()
    minted = False

    base = f"http://{host}/api"
    with httpx.Client(timeout=6.0) as client:
        if not app_key:
            resp = client.post(base, json={"devicetype": "haven_roomos#server"})
            data = resp.json()
            entry = data[0] if isinstance(data, list) and data else {}
            if "success" in entry:
                app_key = entry["success"]["username"]
                minted = True
            else:
                raise ValueError(
                    "Press the round link button on the Hue bridge, then click Connect again "
                    "within 30 seconds so HAVEN can pair."
                )

        r, g, b = _hex_to_rgb(hex_color)
        x, y = _rgb_to_xy(r, g, b)
        action: Dict[str, Any] = {"on": bool(power_on)}
        if power_on:
            action["bri"] = max(1, int(brightness * 254 / 100))
            if (r, g, b) != (255, 255, 255):
                action["xy"] = [x, y]
        # Group 0 = all lights on the bridge.
        client.put(f"{base}/{app_key}/groups/0/action", json=action)

    result: Dict[str, Any] = {"driver": "hue"}
    if minted:
        result["hueAppKey"] = app_key
        result["note"] = "Paired with Hue bridge. Save settings to keep the key."
    return result


def _rgb_to_xy(r: int, g: int, b: int) -> Tuple[float, float]:
    def _g(c: float) -> float:
        c = c / 255.0
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92

    rg, gg, bg = _g(r), _g(g), _g(b)
    X = rg * 0.4124 + gg * 0.3576 + bg * 0.1805
    Y = rg * 0.2126 + gg * 0.7152 + bg * 0.0722
    Z = rg * 0.0193 + gg * 0.1192 + bg * 0.9505
    total = X + Y + Z
    if total == 0:
        return 0.3127, 0.3290
    return round(X / total, 4), round(Y / total, 4)


# --------------------------------------------------------------------------
# Nanoleaf (token via power-button hold)
# --------------------------------------------------------------------------
def _apply_nanoleaf(config, *, power_on, brightness, hex_color) -> Dict[str, Any]:
    host = str(config.get("host") or "").strip()
    if not host:
        raise ValueError("Nanoleaf needs a host IP. Run 'Scan my network' to find it.")
    token = str(config.get("nanoleafToken") or "").strip()
    try:
        from nanoleafapi import Nanoleaf
    except ImportError as e:
        raise ValueError("Nanoleaf support is not installed. From the backend folder: pip install nanoleafapi") from e

    if not token:
        raise ValueError(
            "Hold the Nanoleaf power button for ~5-7 seconds until the LEDs flash, "
            "then click Connect again so HAVEN can mint an access token."
        )

    r, g, b = _hex_to_rgb(hex_color)
    nl = Nanoleaf(host, token)
    if not power_on:
        nl.power_off()
    else:
        nl.power_on()
        try:
            nl.set_brightness(max(1, brightness))
            if (r, g, b) != (255, 255, 255):
                nl.set_color((r, g, b))
        except Exception as e:  # noqa: BLE001
            log.debug("Nanoleaf brightness/color failed (%s); power set.", e)
    return {"driver": "nanoleaf"}


# --------------------------------------------------------------------------
# Govee LAN API (UDP control on :4003)
# --------------------------------------------------------------------------
def _apply_govee(config, *, power_on, brightness, hex_color) -> Dict[str, Any]:
    host = str(config.get("host") or "").strip()
    if not host:
        raise ValueError(
            "Govee LAN control needs the device IP. In the Govee Home app enable "
            "'LAN Control' for the device, then run 'Scan my network'."
        )
    r, g, b = _hex_to_rgb(hex_color)

    def _send(obj: Dict[str, Any]) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(2.0)
            sock.sendto(json.dumps(obj).encode(), (host, 4003))
        finally:
            sock.close()

    _send({"msg": {"cmd": "turn", "data": {"value": 1 if power_on else 0}}})
    if power_on:
        _send({"msg": {"cmd": "brightness", "data": {"value": max(1, brightness)}}})
        if (r, g, b) != (255, 255, 255):
            _send({"msg": {"cmd": "colorwc", "data": {"color": {"r": r, "g": g, "b": b}, "colorTemInKelvin": 0}}})
    return {"driver": "govee"}


_DRIVERS = {
    "tuya": _apply_tuya_light,
    "kasa_light": _apply_kasa_light,
    "tplink_kasa": _apply_kasa_light,
    "tapo": _apply_kasa_light,
    "wiz": _apply_wiz,
    "yeelight": _apply_yeelight,
    "lifx": _apply_lifx,
    "philips_hue": _apply_hue,
    "hue": _apply_hue,
    "nanoleaf": _apply_nanoleaf,
    "govee": _apply_govee,
}
