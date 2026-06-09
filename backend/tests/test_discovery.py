"""Discovery orchestration tests (merge/dedup + graceful protocol failures)."""

from __future__ import annotations

import asyncio

import pytest

from roomos.devices import discovery


def test_local_broadcasts_are_dotted_quads():
    bcasts = discovery.local_broadcasts()
    assert bcasts
    for b in bcasts:
        assert b.count(".") == 3


def test_rec_shape():
    rec = discovery._rec("smart_plug", "tapo", "192.168.1.37", model="P110M", name="fan", protocol="kasa")
    assert rec == {
        "category": "smart_plug",
        "brand": "tapo",
        "host": "192.168.1.37",
        "model": "P110M",
        "name": "fan",
        "protocol": "kasa",
    }


def _patch_all_empty(monkeypatch):
    async def _empty(*a, **k):
        return []

    for name in (
        "_discover_kasa",
        "_discover_wiz",
        "_discover_yeelight",
        "_discover_hue",
        "_discover_wemo",
        "_discover_lifx",
        "_discover_govee",
        "_discover_mdns",
    ):
        monkeypatch.setattr(discovery, name, _empty)


def test_discover_all_dedup_and_sort(monkeypatch):
    _patch_all_empty(monkeypatch)

    async def _kasa(*a, **k):
        return [discovery._rec("smart_plug", "tapo", "192.168.1.37", model="P110M", name="fan")]

    async def _wiz(*a, **k):
        return [
            # Same host+category as kasa but no model -> kasa entry should win.
            discovery._rec("lights", "wiz", "192.168.1.50", name="WiZ"),
            discovery._rec("lights", "wiz", "192.168.1.50", name="dupe"),
        ]

    monkeypatch.setattr(discovery, "_discover_kasa", _kasa)
    monkeypatch.setattr(discovery, "_discover_wiz", _wiz)

    devices = asyncio.run(discovery.discover_all(timeout=1.0))
    # One plug + one (deduped) wiz light.
    assert len(devices) == 2
    hosts = {(d["host"], d["category"]) for d in devices}
    assert ("192.168.1.37", "smart_plug") in hosts
    assert ("192.168.1.50", "lights") in hosts
    # Sorted by (category, host): lights before smart_plug.
    assert devices[0]["category"] == "lights"


def test_discover_all_survives_one_broken_protocol(monkeypatch):
    _patch_all_empty(monkeypatch)

    async def _kasa(*a, **k):
        return [discovery._rec("smart_plug", "tapo", "192.168.1.37", model="P110M")]

    async def _boom(*a, **k):
        raise RuntimeError("protocol exploded")

    monkeypatch.setattr(discovery, "_discover_kasa", _kasa)
    monkeypatch.setattr(discovery, "_discover_wiz", _boom)

    devices = asyncio.run(discovery.discover_all(timeout=1.0))
    assert len(devices) == 1
    assert devices[0]["host"] == "192.168.1.37"


def test_safe_timeout_returns_empty():
    async def _hang():
        await asyncio.sleep(5)
        return [discovery._rec("lights", "wiz", "x")]

    out = asyncio.run(discovery._safe(_hang(), timeout=0.1, label="hang"))
    assert out == []
