"""Multi-brand thermostat control (cloud APIs)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from ..utils.logging import get_logger

log = get_logger("roomos.devices.thermostat")

HONEYWELL_BRANDS = frozenset({"honeywell_tcc", "honeywell_home"})


def _brand(config: Dict[str, Any]) -> str:
    return str(config.get("brand") or config.get("provider") or "none").strip().lower()


def _credentials(config: Dict[str, Any]) -> tuple[str, str]:
    user = str(config.get("username") or config.get("honeywellUsername") or "").strip()
    password = str(config.get("password") or config.get("honeywellPassword") or "").strip()
    return user, password


def _iter_honeywell_devices(client: Any) -> List[Any]:
    devices: List[Any] = []
    for location in client.locations_by_id.values():
        for device in location.devices_by_id.values():
            devices.append(device)
    return devices


def _pick_honeywell_device(client: Any, config: Dict[str, Any]) -> Any:
    devices = _iter_honeywell_devices(client)
    if not devices:
        raise ValueError("No Honeywell thermostats found on this account.")

    device_id = str(config.get("deviceId") or config.get("honeywellDeviceId") or "").strip()
    if device_id:
        found = client.get_device(device_id)
        if found:
            return found

    name_hint = str(config.get("label") or config.get("notes") or "").strip().lower()
    if name_hint:
        for d in devices:
            if name_hint in (getattr(d, "name", "") or "").lower():
                return d

    default = client.default_device
    return default if default is not None else devices[0]


def _apply_honeywell(
    config: Dict[str, Any],
    *,
    heat_f: Optional[float],
    cool_f: Optional[float],
) -> Dict[str, Any]:
    import somecomfort

    username, password = _credentials(config)
    if not username or not password:
        raise ValueError("Enter the same username and password you use in the Honeywell Home app.")

    client = somecomfort.SomeComfort(username, password)
    device = _pick_honeywell_device(client, config)

    if heat_f is not None:
        device.setpoint_heat = float(heat_f)
    if cool_f is not None:
        device.setpoint_cool = float(cool_f)

    return {
        "driver": "honeywell",
        "brand": _brand(config),
        "device": getattr(device, "name", "thermostat"),
        "device_id": getattr(device, "deviceid", None),
        "current_temperature_f": device.current_temperature,
        "heat_setpoint_f": heat_f,
        "cool_setpoint_f": cool_f,
    }


def _ecobee_token(api_key: str, refresh_token: str) -> str:
    import httpx

    r = httpx.post(
        "https://api.ecobee.com/token",
        params={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": api_key,
        },
        timeout=15.0,
    )
    r.raise_for_status()
    data = r.json()
    token = data.get("access_token")
    if not token:
        raise ValueError("Ecobee did not return an access token — check API key and refresh token.")
    return str(token)


def _apply_ecobee(
    config: Dict[str, Any],
    *,
    heat_f: Optional[float],
    cool_f: Optional[float],
) -> Dict[str, Any]:
    import httpx

    api_key = str(config.get("ecobeeApiKey") or config.get("ecobee_api_key") or "").strip()
    refresh = str(config.get("ecobeeRefreshToken") or config.get("ecobee_refresh_token") or "").strip()
    if not api_key or not refresh:
        raise ValueError(
            "Ecobee needs an API key and refresh token from developer.ecobee.com "
            "(register an app, authorize once, paste the refresh token here)."
        )

    access = _ecobee_token(api_key, refresh)
    selection = str(config.get("ecobeeThermostatId") or config.get("deviceId") or "").strip()
    if not selection:
        selection = "registered"

    params: Dict[str, Any] = {"holdType": "indefinite"}
    if heat_f is not None:
        params["heatHoldTemp"] = int(round(float(heat_f) * 10))
    if cool_f is not None:
        params["coolHoldTemp"] = int(round(float(cool_f) * 10))
    if not params.get("heatHoldTemp") and not params.get("coolHoldTemp"):
        functions = [{"type": "resumeProgram", "params": {}}]
    else:
        functions = [{"type": "setHold", "params": params}]

    body = {"selection": {"selectionType": "thermostats", "selectionMatch": selection}, "functions": functions}
    r = httpx.post(
        "https://api.ecobee.com/1/thermostat",
        params={"format": "json"},
        headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
        json=body,
        timeout=15.0,
    )
    r.raise_for_status()
    return {
        "driver": "ecobee",
        "brand": "ecobee",
        "heat_setpoint_f": heat_f,
        "cool_setpoint_f": cool_f,
        "status": r.json().get("status", {}).get("code"),
    }


def list_thermostat_devices(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    brand = _brand(config)
    if brand in HONEYWELL_BRANDS:
        import somecomfort

        username, password = _credentials(config)
        client = somecomfort.SomeComfort(username, password)
        out = []
        for d in _iter_honeywell_devices(client):
            out.append(
                {
                    "id": getattr(d, "deviceid", None),
                    "name": getattr(d, "name", "Thermostat"),
                    "current_f": d.current_temperature,
                }
            )
        return out
    if brand == "ecobee":
        return [{"id": "registered", "name": "Default thermostat on Ecobee account"}]
    if brand == "nest":
        from .nest import list_nest_thermostats, nest_access_token

        project_id = str(config.get("nestProjectId") or "").strip()
        client_id = str(config.get("nestClientId") or "").strip()
        client_secret = str(config.get("nestClientSecret") or "").strip()
        refresh = str(config.get("nestRefreshToken") or "").strip()
        access = nest_access_token(client_id, client_secret, refresh)
        return list_nest_thermostats(project_id, access)
    return []


async def apply_thermostat_setpoints(
    config: Dict[str, Any],
    *,
    heat_f: Optional[float] = None,
    cool_f: Optional[float] = None,
) -> Dict[str, Any]:
    cfg = dict(config or {})
    brand = _brand(cfg)

    if brand in ("none", ""):
        raise ValueError("Choose a thermostat brand in Settings.")

    if brand in HONEYWELL_BRANDS:
        return await asyncio.to_thread(_apply_honeywell, cfg, heat_f=heat_f, cool_f=cool_f)
    if brand == "ecobee":
        return await asyncio.to_thread(_apply_ecobee, cfg, heat_f=heat_f, cool_f=cool_f)
    if brand == "nest":
        from .nest import apply_nest_setpoints

        return await asyncio.to_thread(apply_nest_setpoints, cfg, heat_f=heat_f, cool_f=cool_f)
    if brand in ("amazon", "sensi", "tuya"):
        raise ValueError(
            f"{brand} thermostats are not supported for direct control yet. "
            "Use Nest, Honeywell Home, or Ecobee."
        )
    if brand == "other_thermostat":
        user, password = _credentials(cfg)
        if user and password:
            return await asyncio.to_thread(
                _apply_honeywell,
                {**cfg, "brand": "honeywell_home"},
                heat_f=heat_f,
                cool_f=cool_f,
            )
        raise ValueError("Enter Honeywell-style username/password, or pick your thermostat brand.")

    raise ValueError(f"Unsupported thermostat brand: {brand}")
