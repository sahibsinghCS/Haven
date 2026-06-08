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


def _local_path(filename: str) -> Path:
    from roomos.config import load_config

    from .core.config import settings

    cfg = load_config(settings.roomos_config)
    return cfg.resolve_path("data") / storage_slug() / filename


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
            log.warning("Supabase user load failed (%s); trying local file.", e)

    if supabase_configured() and not uid:
        room_id = get_room_id()
        try:
            remote = load_room_document(room_id, kind)
            if remote is not None:
                return normalize_fn(remote)
        except Exception as e:
            log.warning("Supabase room load failed (%s); trying local file.", e)

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
            log.warning("Supabase user save failed (%s); writing local copy.", e)
    elif supabase_configured():
        try:
            saved = save_room_document(get_room_id(), kind, normalized)
            normalized = normalize_fn(saved)
        except Exception as e:
            log.warning("Supabase room save failed (%s); writing local copy.", e)

    _save_local(_local_path(local_filename), normalized)
    return normalized


def persistence_status() -> dict[str, Any]:
    return {
        "supabase": supabase_configured(),
        "auth": is_authenticated(),
        "user_id": get_user_id(),
        "room_id": get_room_id(),
        "storage": "supabase+local" if supabase_configured() else "local",
    }
