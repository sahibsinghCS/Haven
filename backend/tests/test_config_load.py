"""Tests for YAML config loading + extends resolution."""

from __future__ import annotations

from pathlib import Path

from roomos.config import load_config


def test_default_config_loads():
    cfg = load_config(Path(__file__).parent.parent / "configs" / "default.yaml")
    assert "sleep" in cfg.labels.classes
    assert float(cfg.burst.duration_seconds) > 0
    assert int(cfg.burst.frame_count) >= 1


def test_inference_extends_default():
    cfg = load_config(Path(__file__).parent.parent / "configs" / "inference.yaml")
    assert float(cfg.burst.duration_seconds) > 0
    assert "model_dir" in cfg.raw["inference"]


def test_actions_extends_default():
    cfg = load_config(Path(__file__).parent.parent / "configs" / "actions.yaml")
    assert "rules" in cfg.raw["actions"]
    assert cfg.raw["actions"]["dry_run"] is True
