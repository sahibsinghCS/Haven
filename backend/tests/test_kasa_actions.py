"""Kasa plug action handler tests."""

from __future__ import annotations

from unittest.mock import patch

from roomos.actions.kasa import KasaHandler, resolve_kasa_host
from roomos.actions.rules import ActionEvent, build_handler


def _event(**kwargs) -> ActionEvent:
    defaults = dict(
        rule_name="sleep_fan_kasa",
        activity="sleep",
        confidence=0.9,
        at=0.0,
        iso_time="2026-01-01T00:00:00+00:00",
        action_type="kasa",
        payload={"type": "kasa", "state": "on"},
    )
    defaults.update(kwargs)
    return ActionEvent(**defaults)


def test_resolve_host_from_env(monkeypatch):
    monkeypatch.setenv("KASA_PLUG_HOST", "192.168.1.99")
    assert resolve_kasa_host({"host_env": "KASA_PLUG_HOST"}) == "192.168.1.99"


def test_build_kasa_handler():
    h = build_handler(
        {"type": "kasa", "state": "on"},
        integrations={"kasa": {"enabled": True, "host": "10.0.0.5"}},
    )
    assert h.type_name == "kasa"


def test_kasa_skipped_when_dry_run():
    h = KasaHandler(state="on", integration={"enabled": True, "host": "192.168.1.50"})
    r = h.execute(_event(), dry_run=True)
    assert r["executed"] is False
    assert r.get("reason") == "dry_run"


def test_kasa_skipped_when_integration_disabled():
    h = KasaHandler(state="on", integration={"enabled": False, "host": "192.168.1.50"})
    r = h.execute(_event(), dry_run=False)
    assert r["executed"] is False
    assert r.get("reason") == "integration_disabled"


@patch(
    "roomos.actions.kasa.asyncio.run",
    return_value={"host": "192.168.1.50", "state": "on", "device": "Fan"},
)
def test_kasa_turns_on_when_enabled(mock_run):
    h = KasaHandler(state="on", integration={"enabled": True, "host": "192.168.1.50"})
    r = h.execute(_event(), dry_run=False)
    assert r["executed"] is True
    assert r["state"] == "on"
    mock_run.assert_called_once()
