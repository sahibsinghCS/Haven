"""API auth middleware behavior."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def _auth_required_settings(mock_settings):
    mock_settings.haven_require_auth = True
    mock_settings.haven_room_id_default = "default"


@patch("app.main.auth_configured", return_value=True)
@patch("app.main.settings")
def test_health_open_when_auth_required(mock_settings, _mock_auth_configured):
    _auth_required_settings(mock_settings)
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200


@patch("app.main.auth_configured", return_value=True)
@patch("app.main.settings")
def test_integrations_401_without_token(mock_settings, _mock_auth_configured):
    _auth_required_settings(mock_settings)
    client = TestClient(app)
    response = client.get("/api/integrations")
    assert response.status_code == 401
    assert "Sign in required" in response.json()["detail"]


@patch("app.main.verify_access_token")
@patch("app.main.auth_configured", return_value=True)
@patch("app.main.settings")
def test_integrations_allowed_with_valid_token(
    mock_settings,
    _mock_auth_configured,
    mock_verify,
):
    _auth_required_settings(mock_settings)
    mock_verify.return_value = {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "user@example.com",
    }
    client = TestClient(app)
    response = client.get(
        "/api/integrations",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
