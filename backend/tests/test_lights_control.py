"""Light control routing + graceful-error tests.

We can only physically verify the Tapo plug, so these tests lock in that every
light brand either routes to its driver or fails with a clear, actionable
message -- never a crash or a hang.
"""

from __future__ import annotations

import pytest

from roomos.devices.lights_control import (
    _hex_to_rgb,
    _rgb_to_xy,
    apply_lights_scene,
)

SCENE = {"brightness": 60, "lightColorHex": "#FF8800"}


def test_disabled_is_skipped():
    out = apply_lights_scene({"enabled": False}, SCENE)
    assert out["skipped"] is True
    assert out["reason"] == "lights_disabled"


def test_no_brand_is_skipped():
    out = apply_lights_scene({"enabled": True, "brand": "none"}, SCENE)
    assert out["reason"] == "no_lights_brand"


def test_unknown_brand_is_pending_not_crash():
    out = apply_lights_scene({"enabled": True, "brand": "zigbee_xyz"}, SCENE)
    assert out["executed"] is False
    assert out["reason"] == "lights_brand_pending"
    assert out["would_apply"]["brightness"] == 60


@pytest.mark.parametrize(
    "brand",
    ["lifx", "wiz", "yeelight", "kasa_light", "philips_hue", "nanoleaf", "govee"],
)
def test_host_required_brands_raise_clear_error(brand):
    # Missing host must produce an actionable error, not a hang or a crash.
    with pytest.raises(ValueError) as exc:
        apply_lights_scene({"enabled": True, "brand": brand}, SCENE)
    msg = str(exc.value).lower()
    assert "ip" in msg or "lan" in msg or "scan" in msg


def test_tuya_requires_credentials():
    with pytest.raises(ValueError) as exc:
        apply_lights_scene({"enabled": True, "brand": "tuya"}, SCENE)
    assert "device id" in str(exc.value).lower()


def test_hex_to_rgb():
    assert _hex_to_rgb("#FF8800") == (255, 136, 0)
    assert _hex_to_rgb("bad") == (255, 255, 255)


def test_rgb_to_xy_in_gamut():
    x, y = _rgb_to_xy(255, 136, 0)
    assert 0.0 <= x <= 1.0
    assert 0.0 <= y <= 1.0
    # Pure white falls back to the D65 white point.
    assert _rgb_to_xy(0, 0, 0) == (0.3127, 0.3290)
