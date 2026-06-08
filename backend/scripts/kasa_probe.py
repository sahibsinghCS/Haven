#!/usr/bin/env python3
"""Discover Kasa plugs on the LAN and test on/off (for HS103 and similar)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from _bootstrap import bootstrap

bootstrap()

from roomos.actions.kasa import apply_kasa_state  # noqa: E402


async def _discover(timeout: float) -> None:
    from kasa import Discover

    print(f"Scanning for Kasa devices ({timeout:.0f}s)...")
    found = await Discover.discover(timeout=timeout)
    if not found:
        print("No devices found. Same Wi-Fi as the plug? Try --host <ip> from your router.")
        return
    for addr, dev in found.items():
        await dev.update()
        print(f"  {addr}  alias={dev.alias!r}  model={getattr(dev, 'model', '?')}")


async def _test_host(host: str, state: str, username: str, password: str) -> None:
    print(f"Setting {host} -> {state} ...")
    result = await apply_kasa_state(host, state, username=username, password=password)
    print(f"OK: {result}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Kasa plugs for RoomOS")
    parser.add_argument("--discover", action="store_true", help="Scan LAN for Kasa devices")
    parser.add_argument("--host", default=os.environ.get("KASA_PLUG_HOST", ""), help="Plug IP")
    parser.add_argument("--on", dest="turn_on", action="store_true", help="Turn plug on")
    parser.add_argument("--off", dest="turn_off", action="store_true", help="Turn plug off")
    parser.add_argument("--timeout", type=float, default=10.0, help="Discover timeout (sec)")
    args = parser.parse_args()

    user = os.environ.get("KASA_USERNAME", "")
    password = os.environ.get("KASA_PASSWORD", "")

    if args.discover:
        asyncio.run(_discover(args.timeout))
        return 0

    host = str(args.host or "").strip()
    if not host:
        parser.error("Set --host or KASA_PLUG_HOST, or use --discover")

    if args.turn_on:
        asyncio.run(_test_host(host, "on", user, password))
        return 0
    if args.turn_off:
        asyncio.run(_test_host(host, "off", user, password))
        return 0

    parser.error("Use --on or --off to test, or --discover to scan")
    return 1


if __name__ == "__main__":
    sys.exit(main())
