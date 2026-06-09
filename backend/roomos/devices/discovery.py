"""Home-Assistant-style local network discovery for smart devices.

Runs many discovery protocols concurrently and returns a single, de-duplicated
list of devices the user can one-tap add. Every protocol is best-effort: a
missing optional dependency or a protocol-level failure is swallowed so the rest
of the scan still completes.

Unified record shape::

    {
      "category": "smart_plug" | "lights",
      "brand":    "<ui brand id>",   # matches the Connections dropdowns
      "host":     "192.168.1.50",
      "model":    "P110M" | None,
      "name":     "fan" | None,
      "protocol": "kasa" | "wiz" | ...,
    }
"""

from __future__ import annotations

import asyncio
import json
import socket
import time
from typing import Any, Dict, List, Optional

from ..utils.logging import get_logger

log = get_logger("roomos.devices.discovery")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def local_broadcasts() -> List[str]:
    """Directed /24 broadcast address(es) for this host's IPv4 networks."""
    out: List[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127.") or ip.startswith("169.254."):
                continue
            parts = ip.split(".")
            if len(parts) == 4:
                bcast = ".".join(parts[:3] + ["255"])
                if bcast not in out:
                    out.append(bcast)
    except Exception:
        pass
    # Prefer common home subnets first; keep VirtualBox-style nets last.
    out.sort(key=lambda b: (b.startswith("192.168.56."), b))
    return out or ["255.255.255.255"]


def _rec(category: str, brand: str, host: str, *, model=None, name=None, protocol="") -> Dict[str, Any]:
    return {
        "category": category,
        "brand": brand,
        "host": str(host or "").strip(),
        "model": model,
        "name": name,
        "protocol": protocol,
    }


async def _safe(coro, *, timeout: float, label: str = "") -> List[Dict[str, Any]]:
    """Run a discovery coroutine with a hard timeout; never raise.

    Critical: some protocols use sync libraries via ``asyncio.to_thread`` that
    cannot be cancelled. A hard ``wait_for`` keeps one slow/hung protocol from
    blocking the whole scan -- we just drop its results and move on.
    """
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        return result or []
    except asyncio.TimeoutError:
        log.debug("discovery protocol %s timed out", label)
        return []
    except Exception as e:  # noqa: BLE001
        log.debug("discovery protocol %s failed: %s", label, e)
        return []


# --------------------------------------------------------------------------
# python-kasa (TP-Link Kasa + Tapo plugs, switches, bulbs, strips)
# --------------------------------------------------------------------------
async def _discover_kasa(email: str, password: str, timeout: float) -> List[Dict[str, Any]]:
    from kasa import Credentials, Discover, DeviceType

    creds = Credentials(email, password) if (email and password) else None
    found: Dict[str, Any] = {}
    for bcast in local_broadcasts():
        try:
            part = await Discover.discover(
                target=bcast, credentials=creds, discovery_timeout=max(4.0, timeout)
            )
            found.update(part)
        except Exception as e:  # noqa: BLE001
            log.debug("kasa discover on %s failed: %s", bcast, e)

    out: List[Dict[str, Any]] = []
    for ip, device in found.items():
        try:
            await device.update()
        except Exception:
            pass
        model = getattr(device, "model", None)
        name = getattr(device, "alias", None)
        dtype = getattr(device, "device_type", None)
        # Discovery only reads metadata; close the session so it does not leak.
        try:
            disc = getattr(device, "disconnect", None)
            if disc is not None:
                res = disc()
                if asyncio.iscoroutine(res):
                    await res
        except Exception:
            pass
        is_light = dtype in (
            getattr(DeviceType, "Bulb", None),
            getattr(DeviceType, "LightStrip", None),
            getattr(DeviceType, "Dimmer", None),
        )
        # Smart (Tapo) vs legacy Iot (Kasa) family.
        family = ""
        try:
            family = str(device.config.connection_type.device_family.value)
        except Exception:
            sysinfo = getattr(device, "sys_info", None) or {}
            family = str(sysinfo.get("type", "")) if isinstance(sysinfo, dict) else ""
        is_smart = "SMART" in family.upper()

        if is_light:
            out.append(_rec("lights", "kasa_light", ip, model=model, name=name, protocol="kasa"))
        else:
            brand = "tapo" if is_smart else "tplink_kasa"
            out.append(_rec("smart_plug", brand, ip, model=model, name=name, protocol="kasa"))
    return out


# --------------------------------------------------------------------------
# WiZ bulbs (pywizlight, UDP)
# --------------------------------------------------------------------------
async def _discover_wiz(timeout: float) -> List[Dict[str, Any]]:
    from pywizlight import discovery as wiz_discovery

    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for bcast in local_broadcasts():
        try:
            bulbs = await wiz_discovery.discover_lights(broadcast_space=bcast, wait_time=min(5, timeout))
        except TypeError:
            bulbs = await wiz_discovery.discover_lights(broadcast_space=bcast)
        except Exception as e:  # noqa: BLE001
            log.debug("wiz discover on %s failed: %s", bcast, e)
            continue
        for b in bulbs or []:
            ip = getattr(b, "ip", None)
            if ip and ip not in seen:
                seen.add(ip)
                out.append(_rec("lights", "wiz", ip, name="WiZ light", protocol="wiz"))
    return out


# --------------------------------------------------------------------------
# Yeelight (LAN SSDP-style multicast; sync lib run in a thread)
# --------------------------------------------------------------------------
async def _discover_yeelight(timeout: float) -> List[Dict[str, Any]]:
    import yeelight

    def _scan() -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for b in yeelight.discover_bulbs(timeout=2) or []:
            ip = b.get("ip")
            caps = b.get("capabilities", {}) or {}
            if ip:
                out.append(
                    _rec(
                        "lights",
                        "yeelight",
                        ip,
                        model=caps.get("model"),
                        name=caps.get("name") or "Yeelight",
                        protocol="yeelight",
                    )
                )
        return out

    return await asyncio.to_thread(_scan)


# --------------------------------------------------------------------------
# Philips Hue bridges (cloud N-UPnP discovery endpoint)
# --------------------------------------------------------------------------
async def _discover_hue(timeout: float) -> List[Dict[str, Any]]:
    import httpx

    out: List[Dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=min(6.0, timeout)) as client:
            r = await client.get("https://discovery.meethue.com/")
            r.raise_for_status()
            for bridge in r.json() or []:
                ip = bridge.get("internalipaddress")
                if ip:
                    out.append(
                        _rec("lights", "philips_hue", ip, name="Hue bridge", protocol="hue-nupnp")
                    )
    except Exception as e:  # noqa: BLE001
        log.debug("hue n-upnp discovery failed: %s", e)
    return out


# --------------------------------------------------------------------------
# Wemo plugs/switches (pywemo, SSDP; sync lib run in a thread)
# --------------------------------------------------------------------------
def _ssdp_search(search_target: str, timeout: float) -> List[str]:
    """Bounded SSDP M-SEARCH; returns the IPs of responders' LOCATION headers."""
    deadline = time.monotonic() + min(4.0, timeout)
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 2\r\n"
        f"ST: {search_target}\r\n\r\n"
    ).encode()
    ips: List[str] = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(min(3.0, timeout))
        sock.sendto(msg, ("239.255.255.250", 1900))
        seen: set[str] = set()
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                break
            except Exception:
                break
            ip = addr[0]
            if ip not in seen:
                seen.add(ip)
                ips.append(ip)
    finally:
        sock.close()
    return ips


async def _discover_wemo(timeout: float) -> List[Dict[str, Any]]:
    def _scan() -> List[Dict[str, Any]]:
        ips = _ssdp_search("urn:Belkin:device:**", timeout)
        return [_rec("smart_plug", "wemo", ip, name="Wemo", protocol="ssdp") for ip in ips]

    return await asyncio.to_thread(_scan)


# --------------------------------------------------------------------------
# LIFX bulbs (aiolifx UDP discovery)
# --------------------------------------------------------------------------
async def _discover_lifx(timeout: float) -> List[Dict[str, Any]]:
    import aiolifx

    loop = asyncio.get_running_loop()
    found: Dict[str, Any] = {}

    class _Collector:
        def register(self, device: Any) -> None:
            ip = getattr(device, "ip_addr", None)
            if ip:
                found[ip] = device

        def unregister(self, device: Any) -> None:  # noqa: D401
            pass

    scanner = aiolifx.LifxDiscovery(loop, _Collector())
    try:
        scanner.start()
        await asyncio.sleep(min(5.0, timeout))
    finally:
        try:
            scanner.cleanup()
        except Exception:
            pass

    out: List[Dict[str, Any]] = []
    for ip in found:
        out.append(_rec("lights", "lifx", ip, name="LIFX light", protocol="lifx"))
    return out


# --------------------------------------------------------------------------
# Govee LAN API (UDP multicast scan; only LAN-enabled models respond)
# --------------------------------------------------------------------------
async def _discover_govee(timeout: float) -> List[Dict[str, Any]]:
    def _scan() -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.settimeout(min(4.0, timeout))
            msg = json.dumps({"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}}).encode()
            sock.sendto(msg, ("239.255.255.250", 4001))
            try:
                sock.bind(("", 4002))
            except Exception:
                pass
            deadline = time.monotonic() + min(4.0, timeout)
            seen: set[str] = set()
            while time.monotonic() < deadline:
                try:
                    data, addr = sock.recvfrom(2048)
                except socket.timeout:
                    break
                except Exception:
                    break
                ip = addr[0]
                if ip in seen:
                    continue
                seen.add(ip)
                model = None
                try:
                    payload = json.loads(data.decode("utf-8", "ignore"))
                    model = payload.get("msg", {}).get("data", {}).get("sku")
                except Exception:
                    pass
                out.append(_rec("lights", "govee", ip, model=model, name="Govee light", protocol="govee"))
        finally:
            sock.close()
        return out

    return await asyncio.to_thread(_scan)


# --------------------------------------------------------------------------
# mDNS / zeroconf (Shelly, Nanoleaf, and generic Hue fallback)
# --------------------------------------------------------------------------
_MDNS_TYPES = {
    "_shelly._tcp.local.": ("smart_plug", "shelly"),
    "_nanoleafapi._tcp.local.": ("lights", "nanoleaf"),
    "_hue._tcp.local.": ("lights", "philips_hue"),
}


async def _discover_mdns(timeout: float) -> List[Dict[str, Any]]:
    def _scan() -> List[Dict[str, Any]]:
        from zeroconf import ServiceBrowser, Zeroconf

        found: List[Dict[str, Any]] = []

        class _Listener:
            def __init__(self, category: str, brand: str) -> None:
                self.category = category
                self.brand = brand

            def add_service(self, zc: Any, type_: str, name: str) -> None:
                try:
                    info = zc.get_service_info(type_, name, timeout=2500)
                except Exception:
                    return
                if not info:
                    return
                addrs = []
                try:
                    addrs = info.parsed_addresses()
                except Exception:
                    pass
                if addrs:
                    found.append(
                        _rec(
                            self.category,
                            self.brand,
                            addrs[0],
                            name=name.split(".")[0],
                            protocol="mdns",
                        )
                    )

            def update_service(self, *args: Any) -> None:
                pass

            def remove_service(self, *args: Any) -> None:
                pass

        zc = Zeroconf()
        try:
            browsers = [
                ServiceBrowser(zc, stype, _Listener(cat, brand))
                for stype, (cat, brand) in _MDNS_TYPES.items()
            ]
            time.sleep(min(5.0, timeout))
            del browsers
        finally:
            try:
                zc.close()
            except Exception:
                pass
        return found

    return await asyncio.to_thread(_scan)


# --------------------------------------------------------------------------
# orchestrator
# --------------------------------------------------------------------------
async def discover_all(
    *,
    timeout: float = 8.0,
    kasa_email: str = "",
    kasa_password: str = "",
) -> List[Dict[str, Any]]:
    """Run all discovery protocols concurrently and return a deduped device list."""
    # Kasa loops over each subnet broadcast, so give it more wall-clock.
    kasa_budget = 2 * timeout + 8.0
    other_budget = timeout + 5.0
    results = await asyncio.gather(
        _safe(_discover_kasa(kasa_email, kasa_password, timeout), timeout=kasa_budget, label="kasa"),
        _safe(_discover_wiz(timeout), timeout=other_budget, label="wiz"),
        _safe(_discover_yeelight(timeout), timeout=other_budget, label="yeelight"),
        _safe(_discover_hue(timeout), timeout=other_budget, label="hue"),
        _safe(_discover_wemo(timeout), timeout=other_budget, label="wemo"),
        _safe(_discover_lifx(timeout), timeout=other_budget, label="lifx"),
        _safe(_discover_govee(timeout), timeout=other_budget, label="govee"),
        _safe(_discover_mdns(timeout), timeout=other_budget, label="mdns"),
    )

    merged: Dict[tuple, Dict[str, Any]] = {}
    for group in results:
        for rec in group:
            host = rec.get("host")
            if not host:
                continue
            key = (host, rec.get("category"))
            # Prefer a credentialed/richer source if we already have this host.
            existing = merged.get(key)
            if existing is None or (not existing.get("model") and rec.get("model")):
                merged[key] = rec
    devices = list(merged.values())
    devices.sort(key=lambda d: (d.get("category", ""), d.get("host", "")))
    return devices


def discover_all_sync(**kwargs: Any) -> List[Dict[str, Any]]:
    return asyncio.run(discover_all(**kwargs))
