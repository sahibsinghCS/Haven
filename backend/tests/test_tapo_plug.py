"""Tapo plug helper tests."""

from __future__ import annotations

from roomos.actions.tapo_plug import _friendly_tapo_error


def test_friendly_tapo_error_challenge():
    msg = _friendly_tapo_error(
        RuntimeError(
            "Device response did not match our challenge on ip 192.168.1.37, "
            "check that your e-mail and password (both case-sensitive) are correct."
        ),
        host="192.168.1.37",
    )
    assert "192.168.1.37" in msg
    assert "Third-Party Compatibility" in msg
    assert "factory-reset" in msg.lower() or "factory-reset" in msg
