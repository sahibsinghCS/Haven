"""Persistent Tapo/Kasa connection manager (the Home Assistant model).

Problem this solves: opening a fresh ``python-kasa`` connection for every on/off
means a full KLAP handshake each time. Doing that rapidly (retry loops + repeated
UI clicks) trips the plug's local-auth throttle, which then returns the misleading
"Device response did not match our challenge" error until it cools down.

Home Assistant avoids this by discovering a device once, holding a single
long-lived connection, reusing it for every command, and serializing access.
This module does the same:

- A process-wide singleton owns one asyncio event loop on a daemon thread.
- Device connections are cached per ``(host, email)`` and reused.
- An ``asyncio.Lock`` per device serializes commands/handshakes (safe: one loop).
- Fresh connects use a single ``discover_single`` attempt (no handshake storm),
  rate-limited by a small per-host cooldown.
- Reused connections make on/off near-instant (no re-handshake).
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Dict, Optional, Tuple

from ..utils.logging import get_logger

log = get_logger("roomos.actions.tapo.manager")

# Minimum gap between *fresh* KLAP handshakes to the same host. Reused
# connections are exempt (they do not handshake), so steady-state on/off is fast.
_MIN_HANDSHAKE_INTERVAL = 1.0


def _broadcast_for(host: str) -> Optional[str]:
    """Directed /24 broadcast for the plug's subnet (helps on multi-NIC Windows)."""
    parts = host.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return ".".join(parts[:3] + ["255"])
    return None


def _looks_like_plug(device: Any) -> bool:
    try:
        from kasa import DeviceType

        if getattr(device, "device_type", None) in (DeviceType.Plug, DeviceType.Strip):
            return True
    except Exception:
        pass
    model = str(getattr(device, "model", "") or "").upper()
    return model.startswith("P1") or "PLUG" in model


def _device_summary(device: Any, fallback_host: str) -> Dict[str, Any]:
    host = str(getattr(device, "host", None) or fallback_host)
    model = getattr(device, "model", None)
    alias = getattr(device, "alias", None)
    is_on = getattr(device, "is_on", None)
    power_w: Optional[float] = None
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
        "is_on": is_on,
        "current_power_w": power_w,
    }


class TapoConnectionManager:
    """Owns a background event loop and a cache of live python-kasa devices."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._start_lock = threading.Lock()
        self._devices: Dict[Tuple[str, str], Any] = {}
        self._key_locks: Dict[Tuple[str, str], asyncio.Lock] = {}
        self._last_handshake: Dict[str, float] = {}

    # -- background loop plumbing ------------------------------------------
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._start_lock:
            if self._loop is not None and self._loop.is_running():
                return self._loop
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=self._run_loop, args=(loop,), name="tapo-conn-loop", daemon=True
            )
            self._loop = loop
            self._thread = thread
            thread.start()
            return loop

    @staticmethod
    def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def _submit(self, coro: Any, timeout: float) -> Any:
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout)

    # -- helpers (run on the manager loop) ---------------------------------
    def _get_key_lock(self, key: Tuple[str, str]) -> asyncio.Lock:
        lock = self._key_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._key_locks[key] = lock
        return lock

    async def _safe_disconnect(self, device: Any) -> None:
        disconnect = getattr(device, "disconnect", None)
        if disconnect is None:
            return
        try:
            result = disconnect()
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            pass

    def _drop(self, *keys: Tuple[str, str]) -> Optional[Any]:
        device = None
        for key in keys:
            d = self._devices.pop(key, None)
            device = device or d
        return device

    async def _cooldown(self, host: str) -> None:
        last = self._last_handshake.get(host)
        if last is None:
            return
        elapsed = time.monotonic() - last
        if elapsed < _MIN_HANDSHAKE_INTERVAL:
            await asyncio.sleep(_MIN_HANDSHAKE_INTERVAL - elapsed)

    async def _connect_fresh(
        self,
        host: str,
        email: str,
        password: str,
        timeout: float,
        label: str,
        device_id: str,
        allow_discovery: bool,
    ) -> Tuple[Any, str, bool]:
        """Single discovery-first connect; broadcast fallback only on connectivity errors."""
        from kasa import Credentials, Discover
        from kasa.exceptions import AuthenticationError

        creds = Credentials(email, password) if (email and password) else None
        await self._cooldown(host)
        try:
            device = await asyncio.wait_for(
                Discover.discover_single(host, credentials=creds), timeout=timeout
            )
            await asyncio.wait_for(device.update(), timeout=timeout)
            self._last_handshake[host] = time.monotonic()
            return device, host, False
        except AuthenticationError:
            # Wrong creds OR (more often here) a temporary local-auth throttle.
            # Do NOT retry; retrying makes the throttle worse.
            self._last_handshake[host] = time.monotonic()
            raise
        except Exception as conn_exc:
            if not allow_discovery:
                raise
            log.info("Tapo direct connect to %s failed (%s); trying LAN discovery", host, conn_exc)
            found = await self._discover_plug(creds, host, label, device_id, timeout)
            if found is None:
                raise
            resolved_host = str(getattr(found, "host", None) or host)
            self._last_handshake[resolved_host] = time.monotonic()
            log.info("Tapo plug found via discovery at %s (saved IP was %s)", resolved_host, host)
            return found, resolved_host, resolved_host != host

    async def _discover_plug(
        self, creds: Any, host: str, label: str, device_id: str, timeout: float
    ) -> Optional[Any]:
        from kasa import Discover

        kwargs: Dict[str, Any] = {
            "credentials": creds,
            "discovery_timeout": max(6.0, timeout),
        }
        broadcast = _broadcast_for(host)
        if broadcast:
            kwargs["target"] = broadcast
        try:
            found = await Discover.discover(**kwargs)
        except Exception as e:  # noqa: BLE001
            log.debug("Tapo broadcast discovery failed: %s", e)
            return None
        if not found:
            return None
        plugs = []
        for device in found.values():
            try:
                await device.update()
            except Exception:
                continue
            if _looks_like_plug(device):
                plugs.append(device)
        if not plugs:
            return None
        want_id = (device_id or "").strip().lower()
        want_label = (label or "").strip().lower()
        for device in plugs:
            if want_id and str(getattr(device, "device_id", "") or "").lower() == want_id:
                return device
        if want_label:
            for device in plugs:
                if str(getattr(device, "alias", "") or "").strip().lower() == want_label:
                    return device
        return plugs[0]

    async def _set_state(self, device: Any, state: str, timeout: float) -> Dict[str, Any]:
        if state == "on":
            await asyncio.wait_for(device.turn_on(), timeout=timeout)
        else:
            await asyncio.wait_for(device.turn_off(), timeout=timeout)
        try:
            await asyncio.wait_for(device.update(), timeout=timeout)
        except Exception:
            pass
        return {"state": state}

    async def _read_state(self, device: Any, timeout: float) -> Dict[str, Any]:
        await asyncio.wait_for(device.update(), timeout=timeout)
        is_on = bool(getattr(device, "is_on", False))
        return {"state": "on" if is_on else "off", "is_on": is_on}

    async def _run(
        self,
        host: str,
        email: str,
        password: str,
        op: Any,
        timeout: float,
        label: str,
        device_id: str,
        allow_discovery: bool,
    ) -> Dict[str, Any]:
        """Run ``op(device) -> dict`` on a cached-or-fresh connection (serialized)."""
        from kasa.exceptions import AuthenticationError

        key = (host, email)
        lock = self._get_key_lock(key)
        async with lock:
            device = self._devices.get(key)
            resolved_host = host
            rediscovered = False

            if device is not None:
                # Reuse the live connection (fast path: no handshake).
                try:
                    extra = await op(device) or {}
                    summary = _device_summary(device, resolved_host)
                    summary.update(extra)
                    summary.update(rediscovered=False, requested_host=host, reused=True)
                    return summary
                except AuthenticationError:
                    await self._safe_disconnect(self._drop(key))
                    raise
                except Exception as e:  # noqa: BLE001
                    log.info("Kasa cached connection to %s stale (%s); reconnecting", host, e)
                    await self._safe_disconnect(self._drop(key))
                    device = None

            # Fresh connect (single handshake), then run the operation.
            device, resolved_host, rediscovered = await self._connect_fresh(
                host, email, password, timeout, label, device_id, allow_discovery
            )
            new_key = (resolved_host, email)
            self._devices[new_key] = device
            try:
                extra = await op(device) or {}
            except Exception:
                await self._safe_disconnect(self._drop(new_key, key))
                raise
            summary = _device_summary(device, resolved_host)
            summary.update(extra)
            summary.update(rediscovered=rediscovered, requested_host=host, reused=False)
            return summary

    # -- public sync entries ------------------------------------------------
    def apply_state(
        self,
        host: str,
        state: str,
        *,
        email: str,
        password: str,
        timeout_sec: float = 12.0,
        label: str = "",
        device_id: str = "",
        allow_discovery: bool = True,
    ) -> Dict[str, Any]:
        """Turn a plug on/off. Blocking call (safe from sync code / threads)."""
        timeout = float(timeout_sec)

        async def _op(device: Any) -> Dict[str, Any]:
            return await self._set_state(device, state, timeout)

        coro = self._run(host, email, password, _op, timeout, label, device_id, allow_discovery)
        return self._submit(coro, timeout=timeout + 25.0)

    def read_state(
        self,
        host: str,
        *,
        email: str,
        password: str,
        timeout_sec: float = 12.0,
        label: str = "",
        device_id: str = "",
        allow_discovery: bool = True,
    ) -> Dict[str, Any]:
        """Read on/off without changing the plug. Blocking call."""
        timeout = float(timeout_sec)

        async def _op(device: Any) -> Dict[str, Any]:
            return await self._read_state(device, timeout)

        coro = self._run(host, email, password, _op, timeout, label, device_id, allow_discovery)
        return self._submit(coro, timeout=timeout + 25.0)

    def run(
        self,
        host: str,
        op: Any,
        *,
        email: str,
        password: str,
        timeout_sec: float = 12.0,
        label: str = "",
        device_id: str = "",
        allow_discovery: bool = True,
    ) -> Dict[str, Any]:
        """Run an arbitrary ``async op(device) -> dict`` on a reused connection.

        Used by the lights driver for Kasa bulbs/strips so brightness/color
        changes reuse the same persistent, serialized connection as on/off.
        """
        timeout = float(timeout_sec)
        coro = self._run(host, email, password, op, timeout, label, device_id, allow_discovery)
        return self._submit(coro, timeout=timeout + 25.0)


_MANAGER: Optional[TapoConnectionManager] = None
_MANAGER_LOCK = threading.Lock()


def get_tapo_manager() -> TapoConnectionManager:
    global _MANAGER
    if _MANAGER is None:
        with _MANAGER_LOCK:
            if _MANAGER is None:
                _MANAGER = TapoConnectionManager()
    return _MANAGER
