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
    # The challenge error is most often a temporary local-auth lockout from too
    # many quick attempts, so the message must steer the user to wait and retry.
    assert "wait" in msg.lower()


def test_friendly_tapo_error_is_ascii():
    # The Windows console logger uses cp1252; non-ASCII (e.g. arrows) crashes it.
    msg = _friendly_tapo_error(
        RuntimeError("Device response did not match our challenge"),
        host="192.168.1.37",
    )
    msg.encode("cp1252")  # must not raise


def test_friendly_tapo_error_timeout():
    msg = _friendly_tapo_error(
        RuntimeError("Unable to query the device: 192.168.1.37: TimeoutError()"),
        host="192.168.1.37",
    )
    assert "192.168.1.37" in msg
    assert "reach" in msg.lower()
