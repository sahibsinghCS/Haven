from unittest.mock import MagicMock, patch

import httpx
import pytest

from app import supabase_store as store


@pytest.fixture(autouse=True)
def _reset_schema_state():
    store._schema_probed = False
    store._schema_ready = False
    store._schema_hint_logged = False
    yield
    store._schema_probed = False
    store._schema_ready = False
    store._schema_hint_logged = False


def test_probe_missing_table_logs_once(monkeypatch):
    monkeypatch.setattr(store, "supabase_configured", lambda: True)

    response = MagicMock()
    response.status_code = 404
    response.json.return_value = {"code": "PGRST205", "message": "missing"}

    with patch("app.supabase_store.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = response

        assert store.probe_supabase_schema() is False
        assert store.probe_supabase_schema() is False
        assert client.get.call_count == 1


def test_load_room_document_skips_when_schema_missing(monkeypatch):
    monkeypatch.setattr(store, "supabase_configured", lambda: True)
    monkeypatch.setattr(store, "supabase_schema_ready", lambda: False)

    assert store.load_room_document("default", "integrations") is None


def test_load_room_document_raises_on_other_http_errors(monkeypatch):
    monkeypatch.setattr(store, "supabase_configured", lambda: True)
    monkeypatch.setattr(store, "supabase_schema_ready", lambda: True)

    request = httpx.Request("GET", "https://example.test/rest/v1/haven_room_data")
    response = httpx.Response(500, request=request)

    with patch("app.supabase_store.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = response

        with pytest.raises(httpx.HTTPStatusError):
            store.load_room_document("default", "integrations")
