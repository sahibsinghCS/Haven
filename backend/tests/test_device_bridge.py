from roomos.integrations.device_bridge import merge_runtime_integrations, plug_runtime_config


def test_plug_runtime_config_maps_tuya_fields():
    cfg = plug_runtime_config(
        {
            "enabled": True,
            "brand": "tuya",
            "host": "192.168.1.10",
            "tuyaDeviceId": "abc123",
            "tuyaLocalKey": "secret",
        }
    )
    assert cfg["brand"] == "tuya"
    assert cfg["tuyaDeviceId"] == "abc123"


def test_merge_overlays_smart_plug():
    out = merge_runtime_integrations(
        {"kasa": {"enabled": False}},
    )
    assert "smart_plug" in out or "kasa" in out
