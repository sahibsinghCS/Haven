#!/usr/bin/env python3
"""Probe a Tapo plug on the LAN (P100/P110/P110M/P115)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import _bootstrap  # noqa: F401  (adds backend/ to sys.path on import)

from roomos.actions.tapo_plug import apply_tapo_state  # noqa: E402


async def _test_host(host: str, state: str, email: str, password: str) -> None:
    print(f"Tapo {host} -> {state} ...")
    result = await apply_tapo_state(host, state, email=email, password=password)
    print(f"OK: {result}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Tapo plugs for RoomOS / HAVEN")
    parser.add_argument("--host", default=os.environ.get("TAPO_PLUG_HOST", ""), help="Plug LAN IP")
    parser.add_argument("--email", default=os.environ.get("TAPO_EMAIL", ""), help="Tapo account email")
    parser.add_argument(
        "--password",
        default=os.environ.get("TAPO_PASSWORD", ""),
        help="Tapo account password",
    )
    parser.add_argument("--on", dest="turn_on", action="store_true", help="Turn plug on")
    parser.add_argument("--off", dest="turn_off", action="store_true", help="Turn plug off")
    args = parser.parse_args()

    host = str(args.host or "").strip()
    email = str(args.email or "").strip()
    password = str(args.password or "").strip()
    if not host:
        parser.error("Set --host or TAPO_PLUG_HOST")
    if not email or not password:
        parser.error("Set --email/--password or TAPO_EMAIL/TAPO_PASSWORD")

    if args.turn_on:
        asyncio.run(_test_host(host, "on", email, password))
        return 0
    if args.turn_off:
        asyncio.run(_test_host(host, "off", email, password))
        return 0

    parser.error("Use --on or --off to test the plug")
    return 1


if __name__ == "__main__":
    sys.exit(main())
