"""Train/serve feature configuration compatibility."""

from __future__ import annotations

from pathlib import Path

import pytest

from roomos.config import load_config
from roomos.model.compat import compare_feature_configs, expected_feature_columns

_BACKEND = Path(__file__).resolve().parent.parent


def test_train_personal_matches_inference_config():
    train_cfg = load_config(_BACKEND / "configs/train_personal.yaml")
    infer_cfg = load_config(_BACKEND / "configs/inference.yaml")
    issues = compare_feature_configs(train_cfg, infer_cfg)
    assert issues == [], f"Expected no mismatches, got: {issues}"


def test_expected_feature_columns_stable():
    cfg = load_config(_BACKEND / "configs/inference.yaml")
    cols_a = expected_feature_columns(cfg)
    cols_b = expected_feature_columns(cfg)
    assert cols_a == cols_b
    assert len(cols_a) > 20


def test_compare_detects_pose_mismatch():
    train_cfg = load_config(_BACKEND / "configs/train_personal.yaml")
    infer_cfg = load_config(_BACKEND / "configs/inference.yaml")
    # Simulate training with pose enabled
    train_cfg.raw["features"]["enabled"]["pose"] = True
    issues = compare_feature_configs(train_cfg, infer_cfg)
    assert any("pose" in i for i in issues)
