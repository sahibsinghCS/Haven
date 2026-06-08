"""Multi-brand smart plug routing tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from roomos.devices.smart_plug import apply_smart_plug_state


def test_tapo_routes_to_native_driver():
    import asyncio

    with patch("roomos.devices.smart_plug._apply_tapo", new_callable=AsyncMock) as mock:
        mock.return_value = {"driver": "tapo", "state": "on"}
        result = asyncio.run(
            apply_smart_plug_state(
                {"brand": "tapo", "host": "192.168.1.50", "tapoEmail": "a@b.com", "tapoPassword": "x"},
                "on",
            )
        )
        mock.assert_awaited_once()
        assert result["driver"] == "tapo"


def test_kasa_family_routes_to_kasa():
    import asyncio

    with patch("roomos.devices.smart_plug._apply_kasa_family", new_callable=AsyncMock) as mock:
        mock.return_value = {"driver": "kasa", "state": "on"}
        result = asyncio.run(
            apply_smart_plug_state({"brand": "tplink_kasa", "host": "10.0.0.2"}, "on")
        )
        mock.assert_awaited_once()
        assert result["state"] == "on"


def test_tuya_requires_credentials():
    import asyncio

    with pytest.raises(ValueError, match="Device ID"):
        asyncio.run(apply_smart_plug_state({"brand": "tuya", "host": "10.0.0.3"}, "on"))


def test_shelly_calls_http():
    import asyncio

    with patch("roomos.devices.smart_plug._apply_shelly") as mock:
        mock.return_value = {"driver": "shelly", "state": "on"}
        result = asyncio.run(
            apply_smart_plug_state({"brand": "shelly", "host": "10.0.0.4"}, "on")
        )
        mock.assert_called_once()
        assert result["driver"] == "shelly"
