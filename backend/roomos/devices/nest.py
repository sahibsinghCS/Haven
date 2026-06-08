"""Google Nest thermostat via Device Access (SDM) API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

SDM_BASE = "https://smartdevicemanagement.googleapis.com/v1"


def _f_to_c(temp_f: float) -> float:
    return (float(temp_f) - 32.0) * 5.0 / 9.0


def nest_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    r = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=20.0,
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise ValueError(
            "Google did not return an access token. Check Nest client ID, secret, and refresh token."
        )
    return str(token)


def _nest_headers(access: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {access}"}


def list_nest_thermostats(project_id: str, access: str) -> List[Dict[str, Any]]:
    url = f"{SDM_BASE}/enterprises/{project_id}/devices"
    r = httpx.get(url, headers=_nest_headers(access), timeout=20.0)
    r.raise_for_status()
    devices = r.json().get("devices") or []
    out: List[Dict[str, Any]] = []
    for d in devices:
        if not isinstance(d, dict):
            continue
        traits = d.get("traits") or {}
        if "sdm.devices.traits.Temperature" in traits or "sdm.devices.traits.ThermostatMode" in traits:
            out.append(
                {
                    "id": d.get("name", "").split("/")[-1] if d.get("name") else "",
                    "name": d.get("name", "Nest thermostat"),
                    "raw_name": d.get("name"),
                }
            )
    return out


def _pick_thermostat(devices: List[Dict[str, Any]], device_id: str) -> str:
    if not devices:
        raise ValueError("No Nest thermostats found on this Google Device Access project.")
    if device_id:
        for d in devices:
            if d.get("id") == device_id or device_id in str(d.get("raw_name", "")):
                return str(d.get("raw_name") or f"enterprises/*/devices/{device_id}")
    raw = devices[0].get("raw_name")
    if not raw:
        raise ValueError("Could not resolve Nest device resource name.")
    return str(raw)


def _execute_command(
    device_name: str,
    access: str,
    command: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    r = httpx.post(
        f"{SDM_BASE}/{device_name}:executeCommand",
        headers={**_nest_headers(access), "Content-Type": "application/json"},
        json={"command": command, "params": params},
        timeout=20.0,
    )
    r.raise_for_status()
    return r.json()


def apply_nest_setpoints(
    config: Dict[str, Any],
    *,
    heat_f: Optional[float],
    cool_f: Optional[float],
) -> Dict[str, Any]:
    project_id = str(config.get("nestProjectId") or config.get("nest_project_id") or "").strip()
    client_id = str(config.get("nestClientId") or config.get("nest_client_id") or "").strip()
    client_secret = str(
        config.get("nestClientSecret") or config.get("nest_client_secret") or ""
    ).strip()
    refresh = str(config.get("nestRefreshToken") or config.get("nest_refresh_token") or "").strip()
    device_id = str(config.get("nestDeviceId") or config.get("deviceId") or "").strip()

    if not project_id:
        raise ValueError("Nest needs your Google Device Access project ID.")
    if not client_id or not client_secret or not refresh:
        raise ValueError(
            "Nest needs Google OAuth client ID, client secret, and refresh token "
            "(from Google Cloud + Device Access — see Settings instructions)."
        )

    access = nest_access_token(client_id, client_secret, refresh)
    thermostats = list_nest_thermostats(project_id, access)
    device_name = _pick_thermostat(thermostats, device_id)

    results: List[str] = []
    if heat_f is not None:
        _execute_command(
            device_name,
            access,
            "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
            {"heatCelsius": round(_f_to_c(heat_f), 1)},
        )
        results.append(f"heat {_f_to_c(heat_f):.1f}°C")
    if cool_f is not None:
        _execute_command(
            device_name,
            access,
            "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
            {"coolCelsius": round(_f_to_c(cool_f), 1)},
        )
        results.append(f"cool {_f_to_c(cool_f):.1f}°C")

    if not results:
        raise ValueError("No temperature setpoint to apply.")

    return {
        "driver": "nest",
        "brand": "nest",
        "device": device_name,
        "heat_setpoint_f": heat_f,
        "cool_setpoint_f": cool_f,
        "applied": results,
    }
