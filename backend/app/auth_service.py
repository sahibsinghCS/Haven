"""Verify Supabase Auth JWTs for API requests."""

from __future__ import annotations

from typing import Any

import httpx

from roomos.utils.logging import get_logger

from .core.config import settings

log = get_logger("roomos.auth")


def auth_configured() -> bool:
    return bool(settings.supabase_url.strip() and settings.supabase_anon_key.strip())


def verify_access_token(token: str) -> dict[str, Any] | None:
    """Return Supabase user object or None if invalid."""
    token = (token or "").strip()
    if not token or not auth_configured():
        return None

    url = f"{settings.supabase_url.strip().rstrip('/')}/auth/v1/user"
    apikey = settings.supabase_anon_key.strip() or settings.supabase_service_role_key.strip()
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": apikey,
                },
            )
            if r.status_code != 200:
                log.debug("Auth verify failed: status=%s", r.status_code)
                return None
            data = r.json()
            if not isinstance(data, dict) or not data.get("id"):
                return None
            return data
    except Exception as e:
        log.warning("Auth verify error: %s", e)
        return None
