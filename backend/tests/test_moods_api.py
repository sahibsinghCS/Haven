"""HTTP API for moods, collection, bursts, and training consent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.state import state
from app.main import app
from roomos.moods import registry as mood_registry
from roomos.training import personal_dataset as pds
from roomos.training.collection import mood_collection


@pytest.fixture
def moods_client(tmp_path, monkeypatch):
    moods_path = tmp_path / "moods.json"
    datasets = tmp_path / "personal_datasets"
    jobs = tmp_path / "personal_training_jobs"
    datasets.mkdir()
    jobs.mkdir()
    monkeypatch.setattr(mood_registry, "_cache", None)
    monkeypatch.setattr(mood_registry, "default_moods_path", lambda: moods_path)
    monkeypatch.setattr(mood_registry, "datasets_root", lambda: datasets)
    monkeypatch.setattr(mood_registry, "training_jobs_root", lambda: jobs)
    mood_registry.load_registry(moods_path)
    mood_collection.clear()
    client = TestClient(app)
    yield client, moods_path, datasets
    mood_collection.clear()
    state.live_mode = "off"
    state.engine = None


def test_list_moods(moods_client):
    client, _, _ = moods_client
    res = client.get("/api/moods")
    assert res.status_code == 200
    body = res.json()
    assert len(body["moods"]) == 4
    assert "restorableBuiltins" in body


def test_create_and_delete_custom_mood(moods_client):
    client, moods_path, _ = moods_client
    create = client.post("/api/moods", json={"name": "Yoga"})
    assert create.status_code == 201
    mood_id = create.json()["mood"]["id"]

    listed = client.get("/api/moods")
    assert any(m["id"] == mood_id for m in listed.json()["moods"])

    deleted = client.delete(f"/api/moods/{mood_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == mood_id
    assert mood_id not in mood_registry.active_mood_ids(moods_path)


def test_collection_requires_consent(moods_client):
    client, _, _ = moods_client
    state.live_mode = "live"
    mock_engine = MagicMock()
    mock_engine.is_running.return_value = True
    state.engine = mock_engine

    res = client.post(
        "/api/moods/sleep/collection/start",
        json={"durationSec": 60},
    )
    assert res.status_code == 409
    assert "consent" in res.json()["detail"].lower()


def test_collection_start_stop(moods_client):
    client, moods_path, datasets = moods_client
    mood_registry.set_consent(True, path=moods_path)
    state.live_mode = "live"
    mock_engine = MagicMock()
    mock_engine.is_running.return_value = True
    state.engine = mock_engine

    start = client.post(
        "/api/moods/sleep/collection/start",
        json={"durationSec": 120},
    )
    assert start.status_code == 200
    session = start.json()["session"]
    assert session["active"] is True
    assert session["moodId"] == "sleep"

    status = client.get("/api/moods/sleep/collection/status")
    assert status.status_code == 200
    assert status.json()["session"]["active"] is True

    stop = client.post("/api/moods/sleep/collection/stop")
    assert stop.status_code == 200
    assert stop.json()["session"]["active"] is False


def test_burst_list_and_delete(moods_client):
    client, moods_path, datasets = moods_client
    mood_id = "sleep"
    burst_id = "test_burst_01"
    bdir = pds.burst_dir(datasets, mood_id, burst_id)
    bdir.mkdir(parents=True)
    (bdir / "frame_01.jpg").write_bytes(b"\xff\xd8\xff")
    (bdir / "frame_02.jpg").write_bytes(b"\xff\xd8\xff")
    (bdir / "frame_03.jpg").write_bytes(b"\xff\xd8\xff")
    pds.append_burst_metadata(
        datasets,
        mood_id,
        {"burstId": burst_id, "frameCount": 3, "meanLuma": 50.0},
    )

    listed = client.get(f"/api/moods/{mood_id}/bursts")
    assert listed.status_code == 200
    bursts = listed.json()["bursts"]
    assert any(b["id"] == burst_id for b in bursts)

    deleted = client.delete(f"/api/moods/{mood_id}/bursts/{burst_id}")
    assert deleted.status_code == 200
    assert not bdir.exists()


def test_training_consent_endpoint(moods_client):
    client, moods_path, _ = moods_client
    res = client.post("/api/training/consent", json={"accepted": True})
    assert res.status_code == 200
    assert res.json()["consent"]["accepted"] is True
    doc = mood_registry.load_registry(moods_path)
    assert doc["consent"]["accepted"] is True


@patch("app.api.moods.personal_training_jobs")
def test_train_enqueues_job(mock_jobs, moods_client):
    client, moods_path, datasets = moods_client
    mock_jobs.is_running.return_value = False
    mock_jobs.start_job.return_value = {
        "id": "job-1",
        "moodId": "sleep",
        "phase": "queued",
        "progress": 0,
        "startedAt": "2026-01-01T00:00:00+00:00",
        "warnings": [],
    }

    res = client.post("/api/moods/sleep/train")
    assert res.status_code == 202
    assert res.json()["job"]["id"] == "job-1"
    mock_jobs.start_job.assert_called_once()
