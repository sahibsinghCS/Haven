#!/usr/bin/env python3
"""Verify persistent-connection reuse + measure on/off latency."""

from __future__ import annotations

import asyncio
import os
import time

import _bootstrap  # noqa: F401

from roomos.actions.tapo_plug import apply_tapo_state

HOST = os.environ.get("TAPO_PLUG_HOST", "192.168.1.37").strip()
EMAIL = os.environ.get("TAPO_EMAIL", "").strip()
PASSWORD = os.environ.get("TAPO_PASSWORD", "").strip()


async def main() -> int:
    seq = ["on", "off", "on", "off", "on", "off"]
    for i, state in enumerate(seq, 1):
        t0 = time.monotonic()
        result = await apply_tapo_state(HOST, state, email=EMAIL, password=PASSWORD)
        dt = (time.monotonic() - t0) * 1000
        print(
            f"#{i} {state:3} -> {dt:7.0f} ms  "
            f"reused={result.get('reused')}  is_on={result.get('is_on')}  "
            f"backend={result.get('driver_backend')}  host={result.get('host')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
