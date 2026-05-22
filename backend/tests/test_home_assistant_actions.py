"""Home Assistant and webhook automation handlers."""

from __future__ import annotations

from unittest.mock import patch

from roomos.actions.home_assistant import HomeAssistantHandler
from roomos.actions.rules import ActionEvent, WebhookHandler


def _event(**kwargs) -> ActionEvent:
    defaults = dict(
        rule_name="test_rule",
        activity="work",
        confidence=0.9,
        at=0.0,
        iso_time="2026-01-01T00:00:00+00:00",
        action_type="home_assistant",
        payload={"type": "home_assistant"},
    )
    defaults.update(kwargs)
    return ActionEvent(**defaults)


def test_ha_skipped_when_dry_run():
    h = HomeAssistantHandler(
        mode="webhook",
        webhook_id="roomos_work",
        integration={"enabled": True, "base_url": "http://127.0.0.1:8123"},
    )
    r = h.execute(_event(), dry_run=True)
    assert r["executed"] is False
    assert r.get("skipped") is True
    assert r.get("reason") == "dry_run"


def test_ha_skipped_when_integration_disabled():
    h = HomeAssistantHandler(
        mode="webhook",
        webhook_id="roomos_work",
        integration={"enabled": False, "base_url": "http://127.0.0.1:8123"},
    )
    r = h.execute(_event(), dry_run=False)
    assert r["executed"] is False
    assert r.get("reason") == "integration_disabled"


@patch("roomos.actions.integrations.post_json", return_value={"status": 200, "ok": True})
def test_ha_webhook_fires_when_enabled(mock_post):
    h = HomeAssistantHandler(
        mode="webhook",
        webhook_id="roomos_work",
        integration={"enabled": True, "base_url": "http://127.0.0.1:8123"},
    )
    r = h.execute(_event(), dry_run=False)
    assert r["executed"] is True
    mock_post.assert_called_once()
    assert "roomos_work" in mock_post.call_args.kwargs["url"]


@patch("roomos.actions.integrations.post_json", return_value={"status": 200, "ok": True})
def test_webhook_fires_when_not_dry_run(mock_post):
    h = WebhookHandler(url="http://127.0.0.1:9999/roomos")
    r = h.execute(_event(action_type="webhook", payload={"type": "webhook"}), dry_run=False)
    assert r["executed"] is True
    mock_post.assert_called_once()
