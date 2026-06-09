"""Direct TP-Link Tapo smart plug control (P100/P110/P110M, KLAP protocol).

Control goes through a persistent connection manager (see ``tapo_manager``) that
keeps one live ``python-kasa`` connection per plug and reuses it for every
command -- the same model Home Assistant uses. This makes on/off near-instant
and, critically, avoids re-running the KLAP handshake on every call. Repeated
handshakes (retry loops + rapid UI clicks) trip the plug's local-auth throttle,
which then returns the misleading "Device response did not match our challenge"
error even when the email/password are correct.

The Rust ``tapo`` crate is kept only as a fallback for when ``python-kasa`` is
not importable.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Tuple

from ..utils.logging import get_logger

log = get_logger("roomos.actions.tapo")

_PLUG_HANDLERS = ("p110", "p115", "p105", "p100")


def _friendly_tapo_error(exc: BaseException, *, host: str) -> str:
    msg = str(exc).strip()
    lower = msg.lower()
    is_timeout = (
        "timeout" in lower
        or "timed out" in lower
        or "unreachable" in lower
        or "connect error" in lower
        or "unable to query" in lower
        or "10060" in lower
        or "10061" in lower
    )
    is_auth = (
        not is_timeout
        and (
            "challenge" in lower
            or "did not match" in lower
            or "authentication" in lower
            or "credential" in lower
            or "403" in lower
        )
    )
    if is_auth:
        # On this firmware the same error appears both for wrong credentials AND
        # for a temporary local-auth throttle after several quick attempts.
        return (
            f"The Tapo plug at {host} refused the local login handshake.\n\n"
            "If it was working before, this is almost always a temporary lockout from "
            "trying too many times too quickly -- wait about 30-60 seconds, then click Connect "
            "ONCE and let it finish.\n\n"
            "If it keeps failing:\n"
            "1. Tapo app -> Me -> Tapo Lab (or Voice Assistant / Third-Party Services) -> "
            "Third-Party Compatibility -> ON. Toggle OFF, wait 10 seconds, turn ON again.\n"
            "2. Close the Tapo desktop app on this PC (only one local controller at a time).\n"
            "3. Confirm the plug IP in Tapo -> your plug -> Settings -> Device Info, and that "
            "the email/password match the Tapo app exactly (case-sensitive)."
        )
    if is_timeout:
        return (
            f"Could not reach the Tapo plug at {host}. The plug may be asleep, on a different "
            "Wi-Fi/IP, or powered down.\n\n"
            "Try in order:\n"
            "1. Confirm the plug shows online in the Tapo app and note its current IP "
            "(Tapo -> your plug -> Settings -> Device Info). DHCP can change it.\n"
            "2. Make sure this PC and the plug are on the same Wi-Fi/LAN (2.4 GHz network).\n"
            "3. Reserve a static IP for the plug in your router so it stops moving.\n"
            "4. Re-run Connect once -- the first packet wakes the plug and the retry usually succeeds."
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


async def _apply_via_tapo_crate(
    host: str, normalized: str, email: str, password: str, timeout_sec: float
) -> Dict[str, Any]:
    """Last-resort fallback using the Rust ``tapo`` crate (only if python-kasa is missing)."""
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
    """Turn a Tapo plug on or off (local LAN, KLAP auth) via the persistent manager.

    Returns a dict including ``host`` -- the address actually reached, which may
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
            "On newer firmware, also enable Me -> Voice Assistant -> Third-Party Compatibility."
        )

    try:
        from kasa import Credentials  # noqa: F401  (presence check)
    except ImportError:
        log.warning("python-kasa not installed; using tapo crate fallback only")
        try:
            return await _apply_via_tapo_crate(host, normalized, email, password, timeout_sec)
        except Exception as e:  # noqa: BLE001
            raise ValueError(_friendly_tapo_error(e, host=host)) from e

    from .tapo_manager import get_tapo_manager

    manager = get_tapo_manager()
    try:
        result = await asyncio.to_thread(
            manager.apply_state,
            host,
            normalized,
            email=email,
            password=password,
            timeout_sec=timeout_sec,
            label=label,
            device_id=device_id,
            allow_discovery=allow_discovery,
        )
    except Exception as e:  # noqa: BLE001
        raise ValueError(_friendly_tapo_error(e, host=host)) from e

    result.setdefault("driver_backend", "python-kasa")
    return result


async def discover_tapo_plugs(
    email: str,
    password: str,
    *,
    broadcast: str | None = None,
    discovery_timeout: float = 8.0,
) -> list[Dict[str, Any]]:
    """List Tapo/Kasa plugs on the LAN (for diagnostics / IP self-heal)."""
    from kasa import Credentials, Discover

    from .tapo_manager import _looks_like_plug

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
