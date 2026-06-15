"""Live engine startup compatibility gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from roomos.config import load_config
from roomos.model.compat import (
    _train_config_from_bundle,
    assert_live_engine_compatible,
    build_compatibility_report,
    expected_feature_columns,
    format_compatibility_error,
    gate_live_engine_start,
)

_BACKEND = Path(__file__).resolve().parent.parent


def test_gate_passes_for_demo_bundle_if_present():
    bundle = _BACKEND / "data/models/latest"
    if not (bundle / "model.json").exists():
        pytest.skip("No trained bundle on disk — run npm run train:demo first")
    try:
        report = assert_live_engine_compatible(
            bundle,
            inference_config=_BACKEND / "configs/inference.yaml",
        )
    except Exception as exc:
        if "classes (order matters" in str(exc):
            pytest.skip(
                "Bundle label order predates config-order fix — re-run: npm run train:demo"
            )
        raise
    assert report.ok


def test_label_order_mismatch_detected(tmp_path):
    """Synthetic bundle with sklearn-style alphabetical order vs config order."""
    from roomos.model.registry import save_model_bundle
    from roomos.utils.io import write_json
    from xgboost import XGBClassifier

    infer = _BACKEND / "configs/inference.yaml"
    infer_cfg = load_config(infer)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    clf = XGBClassifier(
        objective="multi:softprob",
        num_class=5,
        n_estimators=2,
        max_depth=2,
        n_jobs=1,
    )
    X = [[0.0] * 4] * 10
    y = [0, 1, 2, 3, 4] * 2
    clf.fit(X, y)
    alpha_order = ["away", "gaming", "relaxing", "sleep", "work"]
    train_cfg = load_config(_BACKEND / "configs/train_personal.yaml")
    train_raw = train_cfg.to_dict()
    train_raw["labels"] = {"classes": alpha_order}
    save_model_bundle(
        bundle,
        clf=clf,
        classes=alpha_order,
        feature_columns=list(expected_feature_columns(load_config(infer))[:4]),
        train_config=train_raw,
        metrics={"train": {"accuracy": 1.0, "n_samples": 10}},
    )

    report = build_compatibility_report(bundle, inference_config=infer)
    assert not report.ok
    assert any(m.category == "labels" for m in report.mismatches)
    assert report.inference_classes == list(infer_cfg.labels.classes)


def test_gate_fails_on_pose_skew():
    bundle = _BACKEND / "data/models/latest"
    if not (bundle / "train_config.json").exists():
        pytest.skip("No bundle train_config.json")

    train_cfg, _ = _train_config_from_bundle(bundle)
    train_cfg.raw["features"]["enabled"]["pose"] = True

    report = build_compatibility_report(
        bundle,
        inference_config=_BACKEND / "configs/inference.yaml",
        train_config=train_cfg,
    )
    assert not report.ok
    assert any(m.category == "features" and "pose" in m.field for m in report.mismatches)

    msg = format_compatibility_error(report)
    assert "Feature modules" in msg
    assert "pose" in msg.lower()


def test_format_includes_fix_commands():
    report = build_compatibility_report(
        _BACKEND / "data/models/latest",
        inference_config=_BACKEND / "configs/inference.yaml",
    )
    if report.ok:
        pytest.skip("Bundle is compatible")
    msg = format_compatibility_error(report)
    assert "npm run train:demo" in msg


def test_registry_label_gate_requires_inference_eligible_overlap(tmp_path, monkeypatch):
    """With moods.json, gate fails when bundle matches no eligible active mood."""
    from roomos.moods import registry as mood_registry
    from roomos.model.compat import _registry_label_check

    moods_path = tmp_path / "moods.json"
    monkeypatch.setattr(mood_registry, "_cache", None)
    monkeypatch.setattr(mood_registry, "default_moods_path", lambda: moods_path)
    mood_registry.load_registry(moods_path)

    assert _registry_label_check(["sleep", "work", "relaxing", "away", "gaming"]) == []

    mood_registry.delete_mood("work", path=moods_path)
    mismatches = _registry_label_check(["work"])
    assert len(mismatches) == 1
    assert mismatches[0].category == "labels"
    assert "eligible" in mismatches[0].field


def test_gate_live_engine_start_resolves_paths():
    infer_cfg = load_config(_BACKEND / "configs/inference.yaml")
    bundle = _BACKEND / "data/models/latest"
    if not (bundle / "model.json").exists():
        pytest.skip("No bundle")
    try:
        report = gate_live_engine_start(
            infer_cfg,
            inference_config_path=_BACKEND / "configs/inference.yaml",
        )
    except Exception as exc:
        if "classes (order matters" in str(exc):
            pytest.skip("Stale bundle — npm run train:demo")
        raise
    assert report.bundle_dir
