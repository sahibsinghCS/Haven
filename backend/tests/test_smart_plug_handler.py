from unittest.mock import patch

from roomos.actions.rules import ActionEvent, build_handler


def test_build_smart_plug_handler():
    h = build_handler(
        {"type": "smart_plug", "state": "on"},
        integrations={"smart_plug": {"enabled": True, "brand": "tplink_kasa", "host": "10.0.0.8"}},
    )
    assert h.type_name == "smart_plug"


@patch("roomos.actions.smart_plug.gateway_apply_plug")
def test_smart_plug_skipped_when_dry_run(mock_gateway):
    h = build_handler(
        {"type": "smart_plug", "state": "on"},
        integrations={"smart_plug": {"enabled": True, "brand": "shelly", "host": "10.0.0.9"}},
    )
    event = ActionEvent(
        rule_name="t",
        activity="sleep",
        confidence=0.9,
        at=0.0,
        iso_time="",
        action_type="smart_plug",
        payload={},
    )
    result = h.execute(event, dry_run=True)
    assert result.get("skipped") is True
    mock_gateway.assert_not_called()
