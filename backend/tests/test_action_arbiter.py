"""Device action arbiter — precedence, cooldown, duplicate suppression."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from roomos.devices.action_arbiter import (
    ActionSource,
    DeviceActionArbiter,
    DeviceActionIntent,
    fingerprint_plug,
    reset_arbiter,
)
from roomos.devices.command_gateway import gateway_apply_plug
from roomos.devices.scene_apply import apply_all_devices_off_async, apply_preference_scene


@pytest.fixture(autouse=True)
def _clean_arbiter():
    reset_arbiter()
    yield
    reset_arbiter()


def test_duplicate_suppressed_within_cooldown():
    arbiter = DeviceActionArbiter()
    intent = DeviceActionIntent(
        source=ActionSource.PREFERENCE_SYNC,
        device_id="plug-1",
        category="smartPlugs",
        fingerprint=fingerprint_plug("plug-1", "on"),
    )
    first = arbiter.plan(intent)
    assert first.allowed is True
    arbiter.record_success(intent)

    second = arbiter.plan(intent)
    assert second.allowed is False
    assert second.reason == "duplicate_suppressed"


def test_resume_beats_recent_away_off():
    arbiter = DeviceActionArbiter()
    away = DeviceActionIntent(
        source=ActionSource.ORCHESTRATOR_AWAY,
        device_id="plug-1",
        category="smartPlugs",
        fingerprint=fingerprint_plug("plug-1", "off"),
    )
    resume = DeviceActionIntent(
        source=ActionSource.ORCHESTRATOR_RESUME,
        device_id="plug-1",
        category="smartPlugs",
        fingerprint=fingerprint_plug("plug-1", "on"),
    )
    arbiter.record_success(away)
    allowed = arbiter.plan(resume)
    assert allowed.allowed is True
    assert allowed.reason == "allowed"


def test_away_beats_recent_resume_on():
    """Brief grace resume must not block the next leave-home all-off."""
    arbiter = DeviceActionArbiter()
    resume = DeviceActionIntent(
        source=ActionSource.ORCHESTRATOR_RESUME,
        device_id="plug-1",
        category="smartPlugs",
        fingerprint=fingerprint_plug("plug-1", "on"),
    )
    away = DeviceActionIntent(
        source=ActionSource.ORCHESTRATOR_AWAY,
        device_id="plug-1",
        category="smartPlugs",
        fingerprint=fingerprint_plug("plug-1", "off"),
    )
    arbiter.record_success(resume)
    allowed = arbiter.plan(away)
    assert allowed.allowed is True
    assert allowed.reason == "allowed"


def test_higher_priority_blocks_lower_priority_conflict():
    arbiter = DeviceActionArbiter()
    away = DeviceActionIntent(
        source=ActionSource.ORCHESTRATOR_AWAY,
        device_id="plug-1",
        category="smartPlugs",
        fingerprint=fingerprint_plug("plug-1", "off"),
    )
    pref = DeviceActionIntent(
        source=ActionSource.PREFERENCE_SYNC,
        device_id="plug-1",
        category="smartPlugs",
        fingerprint=fingerprint_plug("plug-1", "on"),
    )
    assert arbiter.plan(away).allowed is True
    arbiter.record_success(away)

    blocked = arbiter.plan(pref)
    assert blocked.allowed is False
    assert blocked.reason == "preempted_by_higher_priority"


def test_manual_test_not_duplicate_suppressed():
    arbiter = DeviceActionArbiter()
    intent = DeviceActionIntent(
        source=ActionSource.MANUAL_TEST,
        device_id="plug-1",
        category="smartPlugs",
        fingerprint=fingerprint_plug("plug-1", "on"),
    )
    arbiter.record_success(intent)
    assert arbiter.plan(intent).allowed is True


@patch("roomos.devices.command_gateway.apply_smart_plug_state", new_callable=AsyncMock)
def test_gateway_skips_duplicate_live_commands(mock_apply):
    mock_apply.return_value = {"state": "on", "executed": True}
    cfg = {"id": "plug-1", "host": "10.0.0.1", "brand": "tplink_kasa"}

    r1 = asyncio.run(
        gateway_apply_plug(
            cfg,
            "on",
            source=ActionSource.PREFERENCE_SYNC,
            device_id="plug-1",
        )
    )
    r2 = asyncio.run(
        gateway_apply_plug(
            cfg,
            "on",
            source=ActionSource.PREFERENCE_SYNC,
            device_id="plug-1",
        )
    )
    assert r1.get("executed") is True
    assert r2.get("skipped") is True
    assert r2.get("reason") == "duplicate_suppressed"
    mock_apply.assert_awaited_once()


@patch("roomos.devices.command_gateway.apply_smart_plug_state", new_callable=AsyncMock)
@patch("roomos.devices.scene_apply.load_ui_device_settings")
@patch("roomos.devices.scene_apply.merge_runtime_integrations")
def test_scene_apply_records_suppressed_second_call(mock_merge, mock_ui, mock_apply):
    mock_ui.return_value = {
        "devices": {
            "smartPlugs": [
                {
                    "id": "plug-1",
                    "enabled": True,
                    "connected": True,
                    "brand": "tplink_kasa",
                    "host": "10.0.0.1",
                }
            ],
            "lights": [],
            "thermostats": [],
        }
    }
    mock_merge.return_value = {}
    mock_apply.return_value = {"state": "on", "executed": True}

    scene = {"devices": {"plug-1": {"fanOn": True}}}
    apply_preference_scene(scene, dry_run=False, room_state="work")
    record = apply_preference_scene(scene, dry_run=False, room_state="work")

    mock_apply.assert_awaited_once()
    assert record.get("suppressed") == ["smart_plug:plug-1"]


@patch("roomos.devices.command_gateway.apply_smart_plug_state", new_callable=AsyncMock)
@patch("roomos.devices.scene_apply.load_ui_device_settings")
@patch("roomos.devices.scene_apply.merge_runtime_integrations")
def test_away_off_blocks_preference_on(mock_merge, mock_ui, mock_apply):
    mock_ui.return_value = {
        "devices": {
            "smartPlugs": [
                {
                    "id": "plug-1",
                    "enabled": True,
                    "connected": True,
                    "brand": "tplink_kasa",
                    "host": "10.0.0.1",
                }
            ],
            "lights": [],
            "thermostats": [],
        }
    }
    mock_merge.return_value = {}
    mock_apply.return_value = {"state": "off", "executed": True}

    asyncio.run(apply_all_devices_off_async(["plug-1"], dry_run=False))
    record = apply_preference_scene(
        {"devices": {"plug-1": {"fanOn": True}}},
        dry_run=False,
        room_state="work",
    )

    mock_apply.assert_awaited_once()
    assert record["results"]["smart_plug:plug-1"].get("skipped") is True
    assert record["results"]["smart_plug:plug-1"].get("reason") == "preempted_by_higher_priority"
