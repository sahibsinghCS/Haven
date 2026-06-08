"""Auth helpers for the web app."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from ..auth_service import auth_configured, verify_access_token
from ..room_context import get_user_email, get_user_id, is_authenticated

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
def auth_me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        user = verify_access_token(token)
        if user:
            return {
                "authenticated": True,
                "user_id": user.get("id"),
                "email": user.get("email"),
            }
    if is_authenticated():
        return {
            "authenticated": True,
            "user_id": get_user_id(),
            "email": get_user_email(),
        }
    return {"authenticated": False, "auth_configured": auth_configured()}


@router.get("/config")
def auth_config() -> dict[str, Any]:
    from ..core.config import settings

    return {
        "auth_configured": auth_configured(),
        "supabase_url": settings.supabase_url.strip() or None,
        "require_auth": auth_configured() and settings.haven_require_auth,
    }
