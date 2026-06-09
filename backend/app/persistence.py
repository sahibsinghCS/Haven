"""Load/save JSON documents: Supabase per-user when signed in, else per-room/local."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from roomos.utils.logging import get_logger

from .room_context import get_room_id, get_user_id, is_authenticated, storage_slug
from .supabase_store import DocumentKind, load_room_document, load_user_document
from .supabase_store import save_room_document, save_user_document
from .supabase_store import supabase_configured

log = get_logger("roomos.persistence")

LoadFn = Callable[[], dict[str, Any]]


def _data_root() -> Path:
    from roomos.config import load_config

    from .core.config import settings

    cfg = load_config(settings.roomos_config)
    return cfg.resolve_path("data")


def _local_path(filename: str) -> Path:
    return _data_root() / storage_slug() / filename


def _canonical_local_path(filename: str) -> Path:
    """Runtime mirror for background threads (live engine) without auth context."""
    return _data_root() / filename


def _newest_user_local_path(filename: str) -> Path | None:
    users_dir = _data_root() / "users"
    if not users_dir.is_dir():
        return None
    candidates: list[tuple[float, Path]] = []
    for user_dir in users_dir.iterdir():
        if not user_dir.is_dir():
            continue
        path = user_dir / filename
        if not path.is_file():
            continue
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _local_candidate_paths(filename: str) -> list[Path]:
    paths: list[Path] = [_canonical_local_path(filename), _local_path(filename)]
    user_path = _newest_user_local_path(filename)
    if user_path is not None:
        paths.append(user_path)
    # De-dupe while preserving order.
    seen: set[Path] = set()
    out: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


def _load_local_candidates(
    filename: str,
    default_fn: LoadFn,
) -> dict[str, Any] | None:
    """Load the freshest on-disk copy (canonical, room, or per-user backup)."""
    ranked: list[tuple[float, Path]] = []
    for path in _local_candidate_paths(filename):
        if not path.is_file():
            continue
        try:
            ranked.append((path.stat().st_mtime, path))
        except OSError:
            continue
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    for _mtime, path in ranked:
        raw = _load_local(path, default_fn)
        if raw != default_fn():
            return raw
    return None


def _load_local(path: Path, default_fn: LoadFn) -> dict[str, Any]:
    if not path.exists():
        return default_fn()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception as e:
        log.warning("Local read failed %s: %s", path, e)
    return default_fn()


def _save_local(path: Path, doc: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return doc


def load_json_document(
    kind: DocumentKind,
    *,
    default_fn: LoadFn,
    normalize_fn: Callable[[dict[str, Any]], dict[str, Any]],
    local_filename: str,
) -> dict[str, Any]:
    uid = get_user_id()
    if supabase_configured() and uid:
        try:
            remote = load_user_document(uid, kind)
            if remote is not None:
                return normalize_fn(remote)
        except Exception as e:
            log.debug("Supabase user load failed (%s); using local file.", e)

    if supabase_configured() and not uid:
        room_id = get_room_id()
        try:
            remote = load_room_document(room_id, kind)
            if remote is not None:
                return normalize_fn(remote)
        except Exception as e:
            log.debug("Supabase room load failed (%s); using local file.", e)

    raw = _load_local_candidates(local_filename, default_fn)
    if raw is None:
        raw = _load_local(_local_path(local_filename), default_fn)
    return normalize_fn(raw)


def save_json_document(
    kind: DocumentKind,
    doc: dict[str, Any],
    *,
    normalize_fn: Callable[[dict[str, Any]], dict[str, Any]],
    local_filename: str,
) -> dict[str, Any]:
    normalized = normalize_fn(doc)
    uid = get_user_id()

    if supabase_configured() and uid:
        try:
            saved = save_user_document(uid, kind, normalized)
            normalized = normalize_fn(saved)
        except Exception as e:
            log.debug("Supabase user save failed (%s); writing local copy.", e)
    elif supabase_configured():
        try:
            saved = save_room_document(get_room_id(), kind, normalized)
            normalized = normalize_fn(saved)
        except Exception as e:
            log.debug("Supabase room save failed (%s); writing local copy.", e)

    _save_local(_local_path(local_filename), normalized)
    _save_local(_canonical_local_path(local_filename), normalized)
    return normalized


def persistence_status() -> dict[str, Any]:
    return {
        "supabase": supabase_configured(),
        "auth": is_authenticated(),
        "user_id": get_user_id(),
        "room_id": get_room_id(),
        "storage": "supabase+local" if supabase_configured() else "local",
    }
