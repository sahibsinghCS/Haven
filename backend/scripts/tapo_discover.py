#!/usr/bin/env python3
"""Broadcast-discover all Kasa/Tapo devices on the LAN and print their IPs."""

from __future__ import annotations

import asyncio
import os
import sys

import _bootstrap  # noqa: F401

EMAIL = os.environ.get("TAPO_EMAIL", "").strip()
PASSWORD = os.environ.get("TAPO_PASSWORD", "").strip()


async def main() -> int:
    from kasa import Credentials, Discover

    creds = Credentials(EMAIL, PASSWORD) if EMAIL and PASSWORD else None
    print(f"Discovering Kasa/Tapo devices (timeout 10s)... creds={'set' if creds else 'none'}")
    found = await Discover.discover(credentials=creds, discovery_timeout=10)
    if not found:
        print("No devices found via broadcast discovery.")
        return 1
    for ip, dev in found.items():
        try:
            await dev.update()
            print(f"  {ip:16} model={getattr(dev,'model',None)!r:12} alias={getattr(dev,'alias',None)!r} on={getattr(dev,'is_on',None)}")
        except Exception as e:
            print(f"  {ip:16} (found, update failed: {type(e).__name__}: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
