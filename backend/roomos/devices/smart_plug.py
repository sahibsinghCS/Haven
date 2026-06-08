"""Multi-brand smart plug control on the local network (and Meross cloud)."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Optional

from ..utils.logging import get_logger

log = get_logger("roomos.devices.smart_plug")

KASA_FAMILY = frozenset({"tplink_kasa", "kasa"})
TAPO_BRANDS = frozenset({"tapo"})


def _normalize_state(state: str) -> str:
    normalized = str(state or "").strip().lower()
    if normalized not in ("on", "off"):
        raise ValueError(f"plug state must be 'on' or 'off', got {state!r}")
    return normalized


def _plug_config(config: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    return config


def _brand(config: Dict[str, Any]) -> str:
    return str(config.get("brand") or config.get("provider") or "tplink_kasa").strip().lower()


def _host(config: Dict[str, Any]) -> str:
    return str(config.get("host") or "").strip()


async def _apply_tapo(config: Dict[str, Any], state: str) -> Dict[str, Any]:
    from ..actions.tapo_plug import apply_tapo_state, resolve_tapo_credentials

    host = _host(config)
    if not host:
        raise ValueError("Plug IP address is required for TP-Link Tapo.")
    email, password = resolve_tapo_credentials(config)
    timeout = float(config.get("timeout_sec", 12.0))
    label = str(config.get("label") or "").strip()
    device_id = str(config.get("deviceId") or config.get("device_id") or "").strip()
    result = await apply_tapo_state(
        host,
        state,
        email=email,
        password=password,
        timeout_sec=timeout,
        label=label,
        device_id=device_id,
    )
    return {"driver": "tapo", "brand": "tapo", **result}


async def _apply_kasa_family(config: Dict[str, Any], state: str) -> Dict[str, Any]:
    from ..actions.kasa import apply_kasa_state, resolve_kasa_credentials

    host = _host(config)
    if not host:
        raise ValueError("Plug IP address is required for TP-Link Kasa.")
    username, password = resolve_kasa_credentials(config)
    timeout = float(config.get("timeout_sec", 12.0))
    result = await apply_kasa_state(
        host,
        state,
        username=username,
        password=password,
        timeout_sec=timeout,
    )
    return {"driver": "kasa", "brand": _brand(config), **result}


def _apply_shelly(config: Dict[str, Any], state: str) -> Dict[str, Any]:
    import httpx

    host = _host(config)
    if not host:
        raise ValueError("Plug IP address is required for Shelly.")
    turn = "on" if state == "on" else "off"
    gen = str(config.get("shellyGen") or config.get("shelly_gen") or "1").strip()
    timeout = float(config.get("timeout_sec", 10.0))

    if gen == "2" or gen.startswith("2"):
        url = f"http://{host}/rpc/Switch.Set"
        body = {"id": 0, "on": state == "on"}
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=body)
            r.raise_for_status()
    else:
        url = f"http://{host}/relay/0"
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url, params={"turn": turn})
            r.raise_for_status()

    return {"driver": "shelly", "brand": "shelly", "host": host, "state": state}


def _apply_tuya(config: Dict[str, Any], state: str) -> Dict[str, Any]:
    import tinytuya

    host = _host(config)
    dev_id = str(config.get("tuyaDeviceId") or config.get("tuya_device_id") or "").strip()
    local_key = str(config.get("tuyaLocalKey") or config.get("tuya_local_key") or "").strip()
    version_raw = config.get("tuyaVersion") or config.get("tuya_version") or "3.3"
    try:
        version = float(version_raw)
    except (TypeError, ValueError):
        version = 3.3

    if not dev_id or not local_key:
        raise ValueError(
            "Tuya / Smart Life plugs need Device ID and Local Key "
            "(run: python -m tinytuya wizard)."
        )
    if not host:
        host = "Auto"

    device = tinytuya.OutletDevice(dev_id, host, local_key, version=version)
    if state == "on":
        payload = device.turn_on()
    else:
        payload = device.turn_off()

    return {
        "driver": "tuya",
        "brand": _brand(config),
        "host": host,
        "state": state,
        "device": dev_id,
        "response": payload,
    }


def _apply_wemo(config: Dict[str, Any], state: str) -> Dict[str, Any]:
    import pywemo

    host = _host(config)
    if not host:
        raise ValueError("Plug IP address is required for Wemo.")
    url = pywemo.setup_url(host)
    device = pywemo.discovery.device_from_url(url)
    if state == "on":
        device.on()
    else:
        device.off()
    return {
        "driver": "wemo",
        "brand": "wemo",
        "host": host,
        "state": state,
        "device": getattr(device, "name", host),
    }


async def _apply_meross(config: Dict[str, Any], state: str) -> Dict[str, Any]:
    email = str(config.get("merossEmail") or config.get("meross_email") or "").strip()
    password = str(config.get("merossPassword") or config.get("meross_password") or "").strip()
    device_name = str(config.get("label") or config.get("deviceName") or "").strip().lower()
    if not email or not password:
        raise ValueError("Meross plugs need the same email and password as the Meross app.")

    try:
        from meross_iot.http_api import MerossHttpClient
        from meross_iot.manager import MerossManager
    except ImportError as e:
        raise ValueError("Meross support is not installed. Run: pip install meross-iot") from e

    http_api = await MerossHttpClient.from_user_password(email=email, password=password)
    manager = MerossManager(http_client=http_api)
    await manager.async_init()
    await manager.async_device_discovery()
    plugs = []
    for dev in manager.find_devices():
        dtype = str(getattr(dev, "type", "") or "").lower()
        if dtype.startswith("mss") or "plug" in dtype:
            plugs.append(dev)
    if not plugs:
        await manager.async_close()
        raise ValueError("No Meross plugs found on this account.")

    target = plugs[0]
    if device_name:
        for p in plugs:
            name = (getattr(p, "name", None) or "").lower()
            if device_name in name:
                target = p
                break

    if state == "on":
        await target.async_turn_on()
    else:
        await target.async_turn_off()
    name = getattr(target, "name", "meross plug")
    await manager.async_close()
    return {"driver": "meross", "brand": "meross", "state": state, "device": name}


def _resolve_driver(brand: str, config: Dict[str, Any]) -> str:
    if brand in TAPO_BRANDS:
        return "tapo"
    if brand in KASA_FAMILY:
        return "kasa"
    if brand == "shelly":
        return "shelly"
    if brand == "tuya":
        return "tuya"
    if brand == "wemo":
        return "wemo"
    if brand == "meross":
        return "meross"
    if brand == "other_plug":
        if str(config.get("tuyaDeviceId") or config.get("tuya_device_id") or "").strip():
            return "tuya"
        if _host(config):
            return "kasa_probe"
        raise ValueError(
            "For generic plugs, enter Tuya Device ID + Local Key, or pick your brand from the list."
        )
    if brand in ("wyze", "amazon"):
        raise ValueError(
            f"{brand} plugs use the manufacturer cloud and cannot be tested over local IP yet. "
            "Try TP-Link Kasa, Shelly, Tuya/Smart Life, or Meross."
        )
    raise ValueError(f"Unsupported plug brand: {brand}")


async def apply_smart_plug_state(config: Dict[str, Any], state: str) -> Dict[str, Any]:
    """Turn a smart plug on/off using the brand saved in Settings."""
    cfg = _plug_config(config)
    normalized = _normalize_state(state)
    brand = _brand(cfg)
    driver = _resolve_driver(brand, cfg)

    if driver == "tapo":
        return await _apply_tapo(cfg, normalized)
    if driver == "kasa":
        return await _apply_kasa_family(cfg, normalized)
    if driver == "shelly":
        return await asyncio.to_thread(_apply_shelly, cfg, normalized)
    if driver == "tuya":
        return await asyncio.to_thread(_apply_tuya, cfg, normalized)
    if driver == "wemo":
        return await asyncio.to_thread(_apply_wemo, cfg, normalized)
    if driver == "meross":
        return await _apply_meross(cfg, normalized)
    if driver == "kasa_probe":
        return await _apply_kasa_family({**cfg, "brand": "tplink_kasa"}, normalized)

    raise ValueError(f"No driver for brand {brand!r}")


def apply_smart_plug_state_sync(config: Dict[str, Any], state: str) -> Dict[str, Any]:
    return asyncio.run(apply_smart_plug_state(config, state))
