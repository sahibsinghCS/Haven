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


def supabase_configured() -> bool:
    return bool(settings.supabase_url.strip() and settings.supabase_service_role_key.strip())


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


def load_user_document(user_id: str, kind: DocumentKind) -> Optional[dict[str, Any]]:
    if not supabase_configured():
        return None
    params = {
        "user_id": f"eq.{user_id}",
        "kind": f"eq.{kind}",
        "select": "document",
        "limit": "1",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(_rest_url(USER_TABLE), headers=_headers(), params=params)
            r.raise_for_status()
            rows = r.json()
            if not rows:
                return None
            doc = rows[0].get("document")
            return doc if isinstance(doc, dict) else None
    except Exception as e:
        log.warning("Supabase load user %s/%s failed: %s", user_id, kind, e)
        raise


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
    headers = {**_headers(), "Prefer": "return=representation,resolution=merge-duplicates"}
    params = {"on_conflict": "user_id,kind"}
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(
                _rest_url(USER_TABLE),
                headers=headers,
                params=params,
                json=payload,
            )
            r.raise_for_status()
            rows = r.json()
            if rows and isinstance(rows[0], dict):
                doc = rows[0].get("document")
                if isinstance(doc, dict):
                    return doc
            return document
    except Exception as e:
        log.warning("Supabase save user %s/%s failed: %s", user_id, kind, e)
        raise


def load_room_document(room_id: str, kind: DocumentKind) -> Optional[dict[str, Any]]:
    if not supabase_configured():
        return None
    params = {
        "room_id": f"eq.{room_id}",
        "kind": f"eq.{kind}",
        "select": "document",
        "limit": "1",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(_rest_url(ROOM_TABLE), headers=_headers(), params=params)
            r.raise_for_status()
            rows = r.json()
            if not rows:
                return None
            doc = rows[0].get("document")
            return doc if isinstance(doc, dict) else None
    except Exception as e:
        log.warning("Supabase load room %s/%s failed: %s", room_id, kind, e)
        raise


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
    headers = {**_headers(), "Prefer": "return=representation,resolution=merge-duplicates"}
    params = {"on_conflict": "room_id,kind"}
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(_rest_url(ROOM_TABLE), headers=headers, params=params, json=payload)
            r.raise_for_status()
            rows = r.json()
            if rows and isinstance(rows[0], dict):
                doc = rows[0].get("document")
                if isinstance(doc, dict):
                    return doc
            return document
    except Exception as e:
        log.warning("Supabase save room %s/%s failed: %s", room_id, kind, e)
        raise
