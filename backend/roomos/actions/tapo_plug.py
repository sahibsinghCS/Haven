"""Direct TP-Link Tapo smart plug control (P100/P110/P110M, KLAP protocol).

Primary driver is ``python-kasa`` (robust KLAP/AES auto-negotiation, explicit
P110M support). It is far more reliable than the Rust ``tapo`` crate, which
surfaces a misleading "challenge mismatch" message for what are often transient
connectivity problems (the plug sleeps and drops off Wi-Fi between commands).

Reliability features:
- Retries each connect a few times to wake a sleeping plug.
- If the saved IP is stale/unreachable (common after a DHCP lease change), falls
  back to a broadcast LAN discovery and matches the plug by device id / alias /
  type, then uses the address it is actually on.
- Falls back to the ``tapo`` crate only if python-kasa is unavailable.
- Returns the host it actually reached so callers can heal a stale saved IP.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Tuple

from ..utils.logging import get_logger

log = get_logger("roomos.actions.tapo")

_PLUG_HANDLERS = ("p110", "p115", "p105", "p100")


def _friendly_tapo_error(exc: BaseException, *, host: str) -> str:
    msg = str(exc).strip()
    lower = msg.lower()
    is_timeout = (
        "timeout" in lower
        or "timed out" in lower
        or "timedout" in lower
        or "unreachable" in lower
        or "connect error" in lower
        or "10060" in lower
        or "10061" in lower
    )
    is_auth = (
        not is_timeout
        and ("challenge" in lower or "authentication" in lower or "credential" in lower or "403" in lower)
    )
    if is_auth:
        return (
            f"Tapo rejected the login handshake at {host}. "
            "This often happens even when your Tapo email and password are correct.\n\n"
            "Try in order:\n"
            "1. Tapo app → Me → Tapo Lab (or Voice Assistant / Third-Party Services) → "
            "Third-Party Compatibility → ON. Toggle OFF, wait 10 seconds, turn ON again.\n"
            "2. Close the Tapo desktop app on this PC (only one local controller at a time).\n"
            "3. Confirm the plug IP in Tapo → your plug → Settings → Device Info.\n"
            "4. Still failing? Unplug every other TP-Link/Tapo device, factory-reset this plug, "
            "enable Third-Party Compatibility, then add only this plug in the Tapo app "
            "(a known Tapo bug uses incompatible credentials when other devices are on the network)."
        )
    if is_timeout:
        return (
            f"Could not reach the Tapo plug at {host}. The plug may be asleep, on a different "
            "Wi‑Fi/IP, or powered down.\n\n"
            "Try in order:\n"
            "1. Confirm the plug shows online in the Tapo app and note its current IP "
            "(Tapo → your plug → Settings → Device Info). DHCP can change it.\n"
            "2. Make sure this PC and the plug are on the same Wi‑Fi/LAN (2.4 GHz network).\n"
            "3. Reserve a static IP for the plug in your router so it stops moving.\n"
            "4. Re-run Connect — the first packet wakes the plug and the retry usually succeeds."
        )
    return msg or repr(exc)


def resolve_tapo_credentials(config: Dict[str, Any]) -> Tuple[str, str]:
    email = str(
        config.get("tapoEmail")
        or config.get("tapo_email")
        or config.get("username")
        or ""
    ).strip()
    password = str(
        config.get("tapoPassword")
        or config.get("tapo_password")
        or config.get("password")
        or ""
    ).strip()
    return email, password


def _broadcast_for(host: str) -> Optional[str]:
    """Directed /24 broadcast for the plug's subnet (helps on multi-NIC Windows)."""
    parts = host.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return ".".join(parts[:3] + ["255"])
    return None


async def _safe_disconnect(device: Any) -> None:
    disconnect = getattr(device, "disconnect", None)
    if disconnect is None:
        return
    try:
        result = disconnect()
        if asyncio.iscoroutine(result):
            await result
    except Exception:
        pass


def _device_summary(device: Any, fallback_host: str) -> Dict[str, Any]:
    host = str(getattr(device, "host", None) or fallback_host)
    model = getattr(device, "model", None)
    alias = getattr(device, "alias", None)
    power_w: float | None = None
    try:
        from kasa import Module

        energy = device.modules.get(Module.Energy)
        if energy is not None:
            value = getattr(energy, "current_consumption", None)
            if value is not None:
                power_w = float(value)
    except Exception:
        pass
    return {
        "host": host,
        "device": alias or model or host,
        "model": model,
        "alias": alias,
        "current_power_w": power_w,
    }


async def _kasa_connect_host(host: str, creds: Any, per_try_timeout: float) -> Any:
    """Connect to a Tapo/Kasa device at ``host`` via python-kasa (single attempt)."""
    from kasa import Discover

    device = await asyncio.wait_for(
        Discover.discover_single(host, credentials=creds),
        timeout=per_try_timeout,
    )
    await asyncio.wait_for(device.update(), timeout=per_try_timeout)
    return device


async def _kasa_connect_host_explicit(host: str, creds: Any, per_try_timeout: float) -> Any:
    """Explicit KLAP connect (the combination proven to work on P110M firmware 1.3.x)."""
    from kasa import Device
    from kasa.deviceconfig import (
        DeviceConfig,
        DeviceConnectionParameters,
        DeviceEncryptionType,
        DeviceFamily,
    )

    conn = DeviceConnectionParameters(
        device_family=DeviceFamily.SmartTapoPlug,
        encryption_type=DeviceEncryptionType.Klap,
        https=False,
        login_version=2,
    )
    cfg = DeviceConfig(host=host, credentials=creds, connection_type=conn)
    device = await asyncio.wait_for(Device.connect(config=cfg), timeout=per_try_timeout)
    await asyncio.wait_for(device.update(), timeout=per_try_timeout)
    return device


async def _kasa_open(host: str, creds: Any, *, attempts: int, per_try_timeout: float) -> Any:
    """Try to reach ``host`` with retries (each retry helps wake a sleeping plug)."""
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        for connector in (_kasa_connect_host, _kasa_connect_host_explicit):
            try:
                return await connector(host, creds, per_try_timeout)
            except Exception as e:  # noqa: BLE001
                last_exc = e
                log.debug("kasa %s(%s) attempt %d failed: %s", connector.__name__, host, attempt, e)
        if attempt < attempts:
            await asyncio.sleep(0.7)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"Could not connect to Tapo plug at {host}")


def _looks_like_plug(device: Any) -> bool:
    try:
        from kasa import DeviceType

        if getattr(device, "device_type", None) in (DeviceType.Plug, DeviceType.Strip):
            return True
    except Exception:
        pass
    model = str(getattr(device, "model", "") or "").upper()
    return model.startswith("P1") or "PLUG" in model


async def _kasa_discover_plug(
    creds: Any,
    *,
    broadcast: Optional[str],
    label: str,
    device_id: str,
    discovery_timeout: float,
) -> Optional[Any]:
    """Broadcast-discover Tapo/Kasa devices and return the best-matching plug."""
    from kasa import Discover

    kwargs: Dict[str, Any] = {"credentials": creds, "discovery_timeout": discovery_timeout}
    if broadcast:
        kwargs["target"] = broadcast
    try:
        found = await Discover.discover(**kwargs)
    except Exception as e:  # noqa: BLE001
        log.debug("kasa broadcast discovery failed: %s", e)
        return None
    if not found:
        return None

    plugs: list[Any] = []
    for device in found.values():
        try:
            await device.update()
        except Exception:
            continue
        if _looks_like_plug(device):
            plugs.append(device)

    if not plugs:
        return None

    want_label = (label or "").strip().lower()
    want_id = (device_id or "").strip().lower()
    for device in plugs:
        if want_id and str(getattr(device, "device_id", "") or "").lower() == want_id:
            return device
    if want_label:
        for device in plugs:
            if str(getattr(device, "alias", "") or "").strip().lower() == want_label:
                return device
    return plugs[0]


async def _apply_via_tapo_crate(
    host: str, normalized: str, email: str, password: str, timeout_sec: float
) -> Dict[str, Any]:
    """Last-resort fallback using the Rust ``tapo`` crate."""
    from tapo import ApiClient

    async def _open_plug(client: Any) -> tuple[Any, str]:
        last_exc: Exception | None = None
        for handler_name in _PLUG_HANDLERS:
            handler = getattr(client, handler_name, None)
            if handler is None:
                continue
            try:
                return await handler(host), handler_name.upper()
            except Exception as e:  # noqa: BLE001
                last_exc = e
                log.debug("Tapo crate %s(%s) failed: %s", handler_name, host, e)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No Tapo plug handler available in tapo package")

    async def _control() -> Dict[str, Any]:
        client = ApiClient(email, password)
        device, handler_label = await _open_plug(client)
        if normalized == "on":
            await device.on()
        else:
            await device.off()
        model = handler_label
        power_w: float | None = None
        try:
            info = await device.get_device_info()
            model = str(getattr(info, "model", None) or getattr(info, "device_model", None) or model)
        except Exception:
            pass
        try:
            usage = await device.get_energy_usage()
            if usage is not None:
                power_w = float(getattr(usage, "current_power", None) or 0)
        except Exception:
            pass
        return {
            "host": host,
            "state": normalized,
            "device": model,
            "model": model,
            "current_power_w": power_w,
            "driver_backend": "tapo-crate",
        }

    return await asyncio.wait_for(_control(), timeout=float(timeout_sec))


async def apply_tapo_state(
    host: str,
    state: str,
    *,
    email: str = "",
    password: str = "",
    timeout_sec: float = 12.0,
    label: str = "",
    device_id: str = "",
    allow_discovery: bool = True,
) -> Dict[str, Any]:
    """Turn a Tapo plug on or off (local LAN, KLAP auth).

    Returns a dict including ``host`` — the address actually reached, which may
    differ from ``host`` if the plug moved and was found via discovery.
    """
    normalized = str(state or "").strip().lower()
    if normalized not in ("on", "off"):
        raise ValueError(f"tapo state must be 'on' or 'off', got {state!r}")

    host = str(host or "").strip()
    if not host:
        raise ValueError("Plug IP address is required for Tapo.")

    if not email or not password:
        raise ValueError(
            "Tapo plugs need the same email and password you use in the Tapo app. "
            "On newer firmware, also enable Me → Voice Assistant → Third-Party Compatibility."
        )

    try:
        from kasa import Credentials
    except ImportError:
        log.warning("python-kasa not installed; using tapo crate fallback only")
        try:
            return await _apply_via_tapo_crate(host, normalized, email, password, timeout_sec)
        except Exception as e:  # noqa: BLE001
            raise ValueError(_friendly_tapo_error(e, host=host)) from e

    creds = Credentials(email, password)
    per_try_timeout = max(4.0, float(timeout_sec) / 2.0)

    device: Any = None
    resolved_host = host
    rediscovered = False
    connect_exc: Exception | None = None

    # 1) Direct connect to the saved IP (with retries to wake a sleeping plug).
    try:
        device = await _kasa_open(host, creds, attempts=3, per_try_timeout=per_try_timeout)
    except Exception as e:  # noqa: BLE001
        connect_exc = e
        log.info("Tapo direct connect to %s failed (%s); trying LAN discovery", host, e)

    # 2) Saved IP unreachable → discover the plug on the LAN by credentials.
    if device is None and allow_discovery:
        discovered = await _kasa_discover_plug(
            creds,
            broadcast=_broadcast_for(host),
            label=label,
            device_id=device_id,
            discovery_timeout=max(6.0, per_try_timeout),
        )
        if discovered is not None:
            device = discovered
            resolved_host = str(getattr(device, "host", None) or host)
            rediscovered = resolved_host != host
            log.info("Tapo plug found via discovery at %s (saved IP was %s)", resolved_host, host)

    # 3) python-kasa exhausted → try the tapo crate at the saved IP.
    if device is None:
        try:
            result = await _apply_via_tapo_crate(host, normalized, email, password, timeout_sec)
            return result
        except Exception:  # noqa: BLE001
            base = connect_exc if connect_exc is not None else RuntimeError("Tapo connect failed")
            raise ValueError(_friendly_tapo_error(base, host=host)) from base

    # 4) Control the device we connected to.
    try:
        if normalized == "on":
            await asyncio.wait_for(device.turn_on(), timeout=per_try_timeout)
        else:
            await asyncio.wait_for(device.turn_off(), timeout=per_try_timeout)
        try:
            await asyncio.wait_for(device.update(), timeout=per_try_timeout)
        except Exception:
            pass
        summary = _device_summary(device, resolved_host)
    except Exception as e:  # noqa: BLE001
        raise ValueError(_friendly_tapo_error(e, host=resolved_host)) from e
    finally:
        await _safe_disconnect(device)

    summary.update(
        {
            "state": normalized,
            "driver_backend": "python-kasa",
            "rediscovered": rediscovered,
            "requested_host": host,
        }
    )
    return summary


async def discover_tapo_plugs(
    email: str,
    password: str,
    *,
    broadcast: Optional[str] = None,
    discovery_timeout: float = 8.0,
) -> list[Dict[str, Any]]:
    """List Tapo/Kasa plugs on the LAN (for diagnostics / IP self-heal)."""
    from kasa import Credentials, Discover

    creds = Credentials(email, password)
    kwargs: Dict[str, Any] = {"credentials": creds, "discovery_timeout": discovery_timeout}
    if broadcast:
        kwargs["target"] = broadcast
    found = await Discover.discover(**kwargs)
    out: list[Dict[str, Any]] = []
    for ip, device in found.items():
        try:
            await device.update()
        except Exception:
            pass
        out.append(
            {
                "host": ip,
                "model": getattr(device, "model", None),
                "alias": getattr(device, "alias", None),
                "device_id": getattr(device, "device_id", None),
                "is_on": getattr(device, "is_on", None),
                "is_plug": _looks_like_plug(device),
            }
        )
    return out
