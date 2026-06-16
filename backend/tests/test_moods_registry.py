"""Mood registry CRUD, migration, and live-label helpers."""

from __future__ import annotations

import json

import pytest

from roomos.inference.live_pipeline import _mask_inactive_labels
from roomos.moods import registry as mood_registry
from roomos.moods.registry import MoodValidationError
from roomos.training.collection import mood_collection


@pytest.fixture
def moods_env(tmp_path, monkeypatch):
    """Isolated moods.json + personal_datasets under tmp_path."""
    moods_path = tmp_path / "moods.json"
    datasets = tmp_path / "personal_datasets"
    datasets.mkdir()
    monkeypatch.setattr(mood_registry, "_cache", None)
    monkeypatch.setattr(mood_registry, "default_moods_path", lambda: moods_path)
    monkeypatch.setattr(mood_registry, "datasets_root", lambda: datasets)
    mood_collection.clear()
    yield moods_path, datasets
    mood_collection.clear()


def test_migrate_creates_four_builtins(moods_env):
    moods_path, _ = moods_env
    doc = mood_registry.load_registry(moods_path)
    ids = [m["id"] for m in doc["moods"]]
    assert ids == ["sleep", "work", "relaxing", "away"]
    assert doc["consent"]["accepted"] is False


def test_create_custom_mood(moods_env):
    moods_path, _ = moods_env
    mood_registry.load_registry(moods_path)
    mood = mood_registry.create_mood(name="Reading", path=moods_path)
    assert mood["kind"] == "custom"
    assert mood["displayName"] == "Reading"
    assert mood["id"].startswith("reading")
    doc = mood_registry.load_registry(moods_path)
    assert any(m["id"] == mood["id"] for m in doc["moods"])


def test_restore_deleted_builtin(moods_env):
    moods_path, _ = moods_env
    mood_registry.load_registry(moods_path)
    mood_registry.delete_mood("away", path=moods_path)
    assert "away" not in mood_registry.active_mood_ids(moods_path)
    restored = mood_registry.create_mood(builtin_key="away", path=moods_path)
    assert restored["kind"] == "builtin"
    assert restored["id"] == "away"


def test_cannot_delete_last_mood(moods_env):
    moods_path, _ = moods_env
    mood_registry.load_registry(moods_path)
    for mid in ["sleep", "work", "relaxing"]:
        mood_registry.delete_mood(mid, path=moods_path)
    with pytest.raises(MoodValidationError):
        mood_registry.delete_mood("away", path=moods_path)


def test_gaming_not_in_registry(moods_env):
    moods_path, _ = moods_env
    doc = mood_registry.load_registry(moods_path)
    ids = {m["id"] for m in doc["moods"]}
    assert "gaming" not in ids
    bundle = {"sleep", "work", "relaxing", "away"}
    allowed = mood_registry.allowed_live_labels(moods_path, bundle_classes=bundle)
    assert "gaming" not in allowed
    assert "unknown" in allowed


def test_inference_eligible_requires_bundle_class(moods_env):
    moods_path, _ = moods_env
    mood_registry.load_registry(moods_path)
    custom = mood_registry.create_mood(name="Reading", path=moods_path)
    eligible = mood_registry.inference_eligible_labels(
        moods_path, bundle_classes={"sleep", "work", "relaxing", "away"}
    )
    assert custom["id"] not in eligible
    assert "sleep" in eligible


def test_lifecycle_custom_untrained(moods_env):
    moods_path, _ = moods_env
    mood_registry.load_registry(moods_path)
    custom = mood_registry.create_mood(name="Yoga", path=moods_path)
    enriched = mood_registry.enrich_mood(
        custom, bundle_classes={"sleep", "work", "relaxing", "away"}
    )
    assert enriched["lifecycle"] == "custom_untrained"
    assert enriched["inferenceEligible"] is False
    assert enriched["inBundle"] is False


def test_lifecycle_ready_when_in_bundle(moods_env):
    moods_path, _ = moods_env
    mood = mood_registry.get_mood("work", moods_path)
    enriched = mood_registry.enrich_mood(
        mood, bundle_classes={"sleep", "work", "relaxing", "away"}
    )
    assert enriched["lifecycle"] == "ready"
    assert enriched["inferenceEligible"] is True


def test_deleted_builtin_lifecycle():
    mood = {"id": "away", "kind": "builtin", "ml": {"enabled": True, "status": "ready"}}
    assert (
        mood_registry.compute_lifecycle(mood, deleted_builtin=True) == "builtin_deleted"
    )


def test_deleted_mood_excluded_from_ml_candidates(moods_env):
    moods_path, _ = moods_env
    mood_registry.load_registry(moods_path)
    mood_registry.delete_mood("work", path=moods_path)
    classes = mood_registry.ml_class_candidates(moods_path)
    assert "work" not in classes
    assert "sleep" in classes


def test_resolve_personal_training_classes_excludes_gaming(moods_env):
    moods_path, _ = moods_env
    mood_registry.load_registry(moods_path)
    custom = mood_registry.create_mood(name="Jump Rope", path=moods_path)
    base_labels = {"sleep", "work", "relaxing", "away", "gaming"}
    candidates = mood_registry.ml_class_candidates(moods_path)
    classes = mood_registry.resolve_personal_training_classes(
        candidates=candidates,
        personal_burst_counts={custom["id"]: 10, "sleep": 0, "work": 0},
        base_labels=base_labels,
        min_bursts_to_train=3,
        trigger_mood_id=custom["id"],
    )
    assert "gaming" not in classes
    assert custom["id"] in classes
    assert "sleep" in classes


def test_resolve_personal_training_classes_drops_orphan_custom(moods_env):
    moods_path, _ = moods_env
    mood_registry.load_registry(moods_path)
    base_labels = {"sleep", "work", "relaxing", "away", "gaming"}
    candidates = mood_registry.ml_class_candidates(moods_path)
    classes = mood_registry.resolve_personal_training_classes(
        candidates=candidates,
        personal_burst_counts={m: 0 for m in candidates},
        base_labels=base_labels,
        min_bursts_to_train=3,
        trigger_mood_id="sleep",
    )
    assert "jump_rope" not in classes
    assert "gaming" not in classes


def test_correction_allowed_labels_includes_custom_not_in_bundle(moods_env):
    moods_path, _ = moods_env
    mood_registry.load_registry(moods_path)
    custom = mood_registry.create_mood(name="Jump Rope", path=moods_path)
    allowed = mood_registry.correction_allowed_labels(moods_path)
    assert custom["id"] in allowed
    assert "gaming" not in allowed


def test_mask_inactive_labels_zeros_deleted():
    probs = {"sleep": 0.1, "work": 0.7, "relaxing": 0.1, "away": 0.1}
    allowed = {"sleep", "relaxing", "away", "unknown"}
    masked = _mask_inactive_labels(probs, allowed)
    assert masked["work"] == 0.0
    assert abs(sum(masked.values()) - 1.0) < 1e-6
    assert masked["sleep"] > 0


def test_mask_all_mass_on_deleted_falls_back_uniform():
    probs = {"work": 1.0, "sleep": 0.0, "relaxing": 0.0}
    allowed = {"sleep", "relaxing", "away"}
    masked = _mask_inactive_labels(probs, allowed)
    assert masked["work"] == 0.0
    assert masked["sleep"] == 0.5
    assert masked["relaxing"] == 0.5
    assert abs(sum(masked.values()) - 1.0) < 1e-6


def test_set_consent_persists(moods_env):
    moods_path, _ = moods_env
    mood_registry.load_registry(moods_path)
    doc = mood_registry.set_consent(True, path=moods_path)
    assert doc["consent"]["accepted"] is True
    assert doc["consent"]["acceptedAt"] is not None
    reloaded = json.loads(moods_path.read_text(encoding="utf-8"))
    assert reloaded["consent"]["accepted"] is True
