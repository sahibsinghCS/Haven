from app.persistence import load_json_document, save_json_document
from app.integrations_service import default_integrations_document, normalize_integrations_document
from app.room_context import clear_user, set_room_id


def test_local_integrations_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("ROOMOS_CONFIG", "configs/inference.yaml")
    set_room_id("test-room")

    def _default():
        return default_integrations_document()

    doc = _default()
    doc["devices"]["smartPlugs"] = [
        {
            "id": "plug-1",
            "enabled": False,
            "connected": False,
            "brand": "tapo",
            "host": "",
            "label": "Cloud Room Plug",
        }
    ]

    saved = save_json_document(
        "integrations",
        doc,
        normalize_fn=normalize_integrations_document,
        local_filename="integrations.json",
    )
    assert saved["devices"]["smartPlugs"][0]["label"] == "Cloud Room Plug"

    loaded = load_json_document(
        "integrations",
        default_fn=_default,
        normalize_fn=normalize_integrations_document,
        local_filename="integrations.json",
    )
    assert loaded["devices"]["smartPlugs"][0]["label"] == "Cloud Room Plug"


def test_runtime_load_uses_canonical_mirror_without_user_context(tmp_path, monkeypatch):
    monkeypatch.setenv("ROOMOS_CONFIG", "configs/inference.yaml")
    set_room_id("test-room")
    clear_user()

    def _default():
        return default_integrations_document()

    doc = _default()
    doc["devices"]["smartPlugs"] = [
        {
            "id": "plug-runtime",
            "enabled": True,
            "connected": True,
            "brand": "tapo",
            "host": "192.168.1.10",
            "label": "Runtime Fan",
        }
    ]

    save_json_document(
        "integrations",
        doc,
        normalize_fn=normalize_integrations_document,
        local_filename="integrations.json",
    )

    loaded = load_json_document(
        "integrations",
        default_fn=_default,
        normalize_fn=normalize_integrations_document,
        local_filename="integrations.json",
    )
    plug = loaded["devices"]["smartPlugs"][0]
    assert plug["label"] == "Runtime Fan"
    assert plug["connected"] is True