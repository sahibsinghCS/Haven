#!/usr/bin/env python3
"""Deep diagnostics for a Tapo/Kasa plug. Tries multiple drivers + protocols."""

from __future__ import annotations

import asyncio
import os
import sys
import traceback

import _bootstrap  # noqa: F401  (adds backend/ to sys.path on import)


HOST = os.environ.get("TAPO_PLUG_HOST", "192.168.1.37").strip()
EMAIL = os.environ.get("TAPO_EMAIL", "").strip()
PASSWORD = os.environ.get("TAPO_PASSWORD", "").strip()


def hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


async def try_tapo_lib() -> None:
    hr("1) tapo Rust library (current driver)")
    try:
        from tapo import ApiClient
    except Exception as e:
        print(f"  import failed: {e!r}")
        return
    client = ApiClient(EMAIL, PASSWORD)
    for name in ("p110", "p115", "p100", "p105"):
        handler = getattr(client, name, None)
        if handler is None:
            continue
        try:
            dev = await handler(HOST)
            info = await dev.get_device_info()
            print(f"  {name}() OK -> {info}")
            return
        except Exception as e:
            print(f"  {name}() -> {type(e).__name__}: {e}")


async def try_kasa() -> None:
    hr("2) python-kasa (Discover.discover_single, auto protocol)")
    from kasa import Credentials, Discover

    creds = Credentials(EMAIL, PASSWORD)
    try:
        dev = await Discover.discover_single(HOST, credentials=creds)
        await dev.update()
        print(f"  OK connected")
        print(f"  alias       : {getattr(dev, 'alias', None)}")
        print(f"  model       : {getattr(dev, 'model', None)}")
        print(f"  device_type : {getattr(dev, 'device_type', None)}")
        print(f"  is_on       : {getattr(dev, 'is_on', None)}")
        sysinfo = getattr(dev, "sys_info", None) or {}
        for k in ("obd_src", "fw_ver", "hw_ver", "type", "model", "device_id"):
            if isinstance(sysinfo, dict) and k in sysinfo:
                print(f"  sys_info[{k}] = {sysinfo[k]}")
    except Exception as e:
        print(f"  FAILED {type(e).__name__}: {e}")
        traceback.print_exc()


async def try_kasa_connect_variants() -> None:
    hr("3) python-kasa Device.connect with explicit connection configs")
    from kasa import Credentials, Device
    from kasa.deviceconfig import (
        DeviceConfig,
        DeviceConnectionParameters,
        DeviceEncryptionType,
        DeviceFamily,
    )

    creds = Credentials(EMAIL, PASSWORD)
    combos = [
        (DeviceFamily.SmartTapoPlug, DeviceEncryptionType.Klap, False),
        (DeviceFamily.SmartTapoPlug, DeviceEncryptionType.Klap, True),
        (DeviceFamily.SmartTapoPlug, DeviceEncryptionType.Aes, True),
        (DeviceFamily.IotSmartPlugSwitch, DeviceEncryptionType.Klap, False),
    ]
    for family, enc, https in combos:
        label = f"{family.value}/{enc.value}/https={https}"
        try:
            conn = DeviceConnectionParameters(
                device_family=family,
                encryption_type=enc,
                https=https,
                login_version=2,
            )
            cfg = DeviceConfig(host=HOST, credentials=creds, connection_type=conn)
            dev = await Device.connect(config=cfg)
            await dev.update()
            print(f"  {label} -> OK model={getattr(dev,'model',None)} on={getattr(dev,'is_on',None)}")
            await dev.disconnect()
            return
        except Exception as e:
            print(f"  {label} -> {type(e).__name__}: {e}")


async def main() -> int:
    print(f"host={HOST}  email={'set' if EMAIL else 'MISSING'}  password={'set' if PASSWORD else 'MISSING'}")
    if not EMAIL or not PASSWORD:
        print("Set TAPO_EMAIL / TAPO_PASSWORD env vars.")
        return 2
    await try_tapo_lib()
    await try_kasa()
    await try_kasa_connect_variants()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
