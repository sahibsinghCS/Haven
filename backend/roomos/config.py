"""Central config loader.

YAML files in ``configs/`` are the source of truth. Files can ``extends:``
another YAML so we don't repeat shared sections. The loaded object is a thin
dataclass-ish wrapper that lets callers do attribute access *and* keeps a
dictionary view for serialization.
"""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml


# --- low-level YAML merge ---------------------------------------------------


def _deep_merge(base: dict[str, Any], over: Mapping[str, Any]) -> dict[str, Any]:
    """Recursive merge — values in ``over`` win, dicts merged, lists replaced."""
    out = deepcopy(base)
    for k, v in over.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, Mapping):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Top-level YAML in {path} must be a mapping, got {type(data).__name__}")
    return data


def _resolve_extends(path: Path, raw: dict[str, Any], _seen: set[Path]) -> dict[str, Any]:
    extends = raw.pop("extends", None)
    if extends is None:
        return raw
    parent_path = (path.parent / extends).resolve()
    if parent_path in _seen:
        raise ValueError(f"Cyclic 'extends' chain involving {parent_path}")
    _seen.add(parent_path)
    parent_raw = _load_yaml(parent_path)
    parent_resolved = _resolve_extends(parent_path, parent_raw, _seen)
    return _deep_merge(parent_resolved, raw)


# --- public config object ---------------------------------------------------


class _AttrDict(dict):
    """Dictionary that also supports attribute access (read-only-ish)."""

    __slots__ = ()

    def __getattr__(self, item: str) -> Any:  # type: ignore[override]
        try:
            v = self[item]
        except KeyError as e:
            raise AttributeError(item) from e
        return _wrap(v)

    def __setattr__(self, key: str, value: Any) -> None:  # type: ignore[override]
        self[key] = value


def _wrap(v: Any) -> Any:
    if isinstance(v, dict) and not isinstance(v, _AttrDict):
        return _AttrDict(v)
    return v


@dataclass
class Config:
    """Project config. Always created via :func:`load_config`."""

    raw: dict[str, Any] = field(default_factory=dict)
    source_path: Path | None = None
    project_root: Path | None = None

    # short attribute access ------------------------------------------------
    def __getattr__(self, item: str) -> Any:
        if item in {"raw", "source_path", "project_root"}:
            raise AttributeError(item)
        try:
            return _wrap(self.raw[item])
        except KeyError as e:
            raise AttributeError(item) from e

    def __contains__(self, item: object) -> bool:
        return item in self.raw

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def resolve_path(self, *parts: str | os.PathLike[str]) -> Path:
        """Resolve a path relative to the *project root* (the dir containing configs/)."""
        root = self.project_root or Path.cwd()
        p = Path(*parts)
        return p if p.is_absolute() else (root / p)

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.raw)


# --- loading ----------------------------------------------------------------


def _detect_project_root(config_path: Path) -> Path:
    """The directory containing the ``configs/`` folder is the project root."""
    p = config_path.resolve()
    for parent in [p.parent, *p.parents]:
        if (parent / "configs").is_dir():
            return parent
    return p.parent


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    """Load a YAML config (with ``extends:`` resolution).

    Defaults to ``configs/default.yaml`` relative to CWD, or to the path in
    ``ROOMOS_CONFIG`` if set.
    """
    if path is None:
        path = os.environ.get("ROOMOS_CONFIG", "configs/default.yaml")
    cfg_path = Path(path).resolve()
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")
    raw = _load_yaml(cfg_path)
    resolved = _resolve_extends(cfg_path, raw, {cfg_path})
    return Config(
        raw=resolved,
        source_path=cfg_path,
        project_root=_detect_project_root(cfg_path),
    )


def load_actions_config(path: str | os.PathLike[str] | None = None) -> Config:
    """Convenience for the actions config, which extends ``default.yaml``."""
    if path is None:
        path = os.environ.get("ROOMOS_ACTIONS_CONFIG", "configs/actions.yaml")
    return load_config(path)
