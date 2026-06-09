"""Integrations document v1 → v2 migration."""

from app.integrations_service import normalize_integrations_document


def test_v1_single_slots_migrate_to_arrays():
    v1 = {
        "schemaVersion": 1,
        "updatedAt": "2020-01-01T00:00:00Z",
        "devices": {
            "smartPlug": {
                "enabled": True,
                "connected": True,
                "brand": "tapo",
                "host": "192.168.1.10",
                "label": "Fan plug",
            },
            "lights": {
                "enabled": False,
                "connected": False,
                "brand": "none",
                "notes": "",
            },
            "thermostat": {
                "enabled": False,
                "connected": False,
                "brand": "none",
                "notes": "",
            },
        },
    }
    out = normalize_integrations_document(v1)
    assert out["schemaVersion"] == 2
    assert len(out["devices"]["smartPlugs"]) == 1
    assert out["devices"]["smartPlugs"][0]["label"] == "Fan plug"
    assert out["devices"]["smartPlugs"][0]["id"]
    assert len(out["devices"]["lights"]) == 1
    assert out["devices"]["lights"][0]["brand"] == "none"
    assert len(out["devices"]["thermostats"]) == 1


def test_v2_arrays_preserved():
    doc = {
        "schemaVersion": 2,
        "updatedAt": "2020-01-01T00:00:00Z",
        "devices": {
            "smartPlugs": [
                {
                    "id": "plug-a",
                    "enabled": True,
                    "connected": True,
                    "brand": "tapo",
                    "host": "192.168.1.20",
                    "label": "Lamp",
                }
            ],
            "lights": [],
            "thermostats": [],
        },
    }
    out = normalize_integrations_document(doc)
    assert out["devices"]["smartPlugs"][0]["id"] == "plug-a"
    assert out["devices"]["smartPlugs"][0]["host"] == "192.168.1.20"
