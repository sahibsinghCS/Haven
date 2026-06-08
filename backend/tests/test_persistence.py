from app.persistence import load_json_document, save_json_document
from app.integrations_service import default_integrations_document, normalize_integrations_document
from app.room_context import set_room_id


def test_local_integrations_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("ROOMOS_CONFIG", "configs/inference.yaml")
    set_room_id("test-room")

    def _default():
        return default_integrations_document()

    doc = _default()
    doc["devices"]["smartPlug"]["label"] = "Cloud Room Plug"

    saved = save_json_document(
        "integrations",
        doc,
        normalize_fn=normalize_integrations_document,
        local_filename="integrations.json",
    )
    assert saved["devices"]["smartPlug"]["label"] == "Cloud Room Plug"

    loaded = load_json_document(
        "integrations",
        default_fn=_default,
        normalize_fn=normalize_integrations_document,
        local_filename="integrations.json",
    )
    assert loaded["devices"]["smartPlug"]["label"] == "Cloud Room Plug"
