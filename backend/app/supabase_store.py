"""Supabase PostgREST persistence for per-user and legacy per-room data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

import httpx

from roomos.utils.logging import get_logger

from .core.config import settings

log = get_logger("roomos.supabase")

DocumentKind = Literal["integrations", "preferences"]
USER_TABLE = "haven_user_data"
ROOM_TABLE = "haven_room_data"

_schema_probed = False
_schema_ready = False
_schema_hint_logged = False


def supabase_configured() -> bool:
    return bool(settings.supabase_url.strip() and settings.supabase_service_role_key.strip())


def supabase_schema_ready() -> bool:
    """True when configured tables exist in PostgREST (probe runs at most once)."""
    if not supabase_configured():
        return False
    probe_supabase_schema()
    return _schema_ready


def probe_supabase_schema(*, force: bool = False) -> bool:
    """Check that haven_room_data is visible to PostgREST. Logs migration hint once."""
    global _schema_probed, _schema_ready, _schema_hint_logged

    if not supabase_configured():
        _schema_probed = True
        _schema_ready = False
        return False

    if _schema_probed and not force:
        return _schema_ready

    _schema_probed = True
    _schema_ready = False

    params = {"select": "room_id", "limit": "1"}
    try:
        with httpx.Client(timeout=12.0) as client:
            r = client.get(_rest_url(ROOM_TABLE), headers=_headers(), params=params)
            if r.status_code == 404 and _response_code(r) == "PGRST205":
                if not _schema_hint_logged:
                    _schema_hint_logged = True
                    log.info(
                        "Supabase tables missing — using local files. "
                        "Run once: npm run supabase:migrate "
                        "(set SUPABASE_DB_PASSWORD in backend/.env; see docs/SUPABASE.md)."
                    )
                return False
            r.raise_for_status()
            _schema_ready = True
            return True
    except httpx.HTTPStatusError as e:
        if not _schema_hint_logged:
            _schema_hint_logged = True
            log.warning("Supabase schema probe failed (%s); using local files.", e)
        return False
    except Exception as e:
        if not _schema_hint_logged:
            _schema_hint_logged = True
            log.warning("Supabase schema probe failed (%s); using local files.", e)
        return False


def _response_code(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            return str(body.get("code") or "")
    except Exception:
        pass
    return ""


def _is_missing_table(response: httpx.Response) -> bool:
    return response.status_code == 404 and _response_code(response) == "PGRST205"


def _headers() -> dict[str, str]:
    key = settings.supabase_service_role_key.strip()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _rest_url(table: str) -> str:
    base = settings.supabase_url.strip().rstrip("/")
    return f"{base}/rest/v1/{table}"


def _get_document(table: str, params: dict[str, str], *, context: str) -> Optional[dict[str, Any]]:
    if not supabase_schema_ready():
        return None
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(_rest_url(table), headers=_headers(), params=params)
            if _is_missing_table(r):
                probe_supabase_schema(force=True)
                return None
            r.raise_for_status()
            rows = r.json()
            if not rows:
                return None
            doc = rows[0].get("document")
            return doc if isinstance(doc, dict) else None
    except httpx.HTTPStatusError as e:
        if e.response is not None and _is_missing_table(e.response):
            probe_supabase_schema(force=True)
            return None
        log.warning("Supabase load %s failed: %s", context, e)
        raise
    except Exception as e:
        log.warning("Supabase load %s failed: %s", context, e)
        raise


def _post_document(
    table: str,
    *,
    payload: dict[str, Any],
    conflict: str,
    context: str,
) -> dict[str, Any]:
    if not supabase_schema_ready():
        raise RuntimeError("Supabase tables are not migrated")
    headers = {**_headers(), "Prefer": "return=representation,resolution=merge-duplicates"}
    params = {"on_conflict": conflict}
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(_rest_url(table), headers=headers, params=params, json=payload)
            if _is_missing_table(r):
                probe_supabase_schema(force=True)
                raise RuntimeError("Supabase tables are not migrated")
            r.raise_for_status()
            rows = r.json()
            if rows and isinstance(rows[0], dict):
                doc = rows[0].get("document")
                if isinstance(doc, dict):
                    return doc
            return payload["document"]
    except httpx.HTTPStatusError as e:
        if e.response is not None and _is_missing_table(e.response):
            probe_supabase_schema(force=True)
            raise RuntimeError("Supabase tables are not migrated") from e
        log.warning("Supabase save %s failed: %s", context, e)
        raise
    except Exception as e:
        log.warning("Supabase save %s failed: %s", context, e)
        raise


def load_user_document(user_id: str, kind: DocumentKind) -> Optional[dict[str, Any]]:
    if not supabase_configured():
        return None
    params = {
        "user_id": f"eq.{user_id}",
        "kind": f"eq.{kind}",
        "select": "document",
        "limit": "1",
    }
    return _get_document(USER_TABLE, params, context=f"user {user_id}/{kind}")


def save_user_document(user_id: str, kind: DocumentKind, document: dict[str, Any]) -> dict[str, Any]:
    if not supabase_configured():
        raise RuntimeError("Supabase is not configured")
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "user_id": user_id,
        "kind": kind,
        "document": document,
        "updated_at": now,
    }
    return _post_document(
        USER_TABLE,
        payload=payload,
        conflict="user_id,kind",
        context=f"user {user_id}/{kind}",
    )


def load_room_document(room_id: str, kind: DocumentKind) -> Optional[dict[str, Any]]:
    if not supabase_configured():
        return None
    params = {
        "room_id": f"eq.{room_id}",
        "kind": f"eq.{kind}",
        "select": "document",
        "limit": "1",
    }
    return _get_document(ROOM_TABLE, params, context=f"room {room_id}/{kind}")


def save_room_document(room_id: str, kind: DocumentKind, document: dict[str, Any]) -> dict[str, Any]:
    if not supabase_configured():
        raise RuntimeError("Supabase is not configured")
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "room_id": room_id,
        "kind": kind,
        "document": document,
        "updated_at": now,
    }
    return _post_document(
        ROOM_TABLE,
        payload=payload,
        conflict="room_id,kind",
        context=f"room {room_id}/{kind}",
    )
