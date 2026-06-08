"""Settings / cloud persistence status."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..persistence import persistence_status
from ..supabase_store import supabase_configured

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/status")
def settings_status() -> dict[str, Any]:
    status = persistence_status()
    from ..auth_service import auth_configured
    from ..room_context import is_authenticated

    if is_authenticated():
        msg = "Signed in — your preferences and device connections are saved to your account."
    elif supabase_configured() and auth_configured():
        msg = "Sign in to save preferences and devices to your account (not a shared room id)."
    elif supabase_configured():
        msg = "Cloud on — add SUPABASE_ANON_KEY and sign in from the web app."
    else:
        msg = "Local only — add Supabase keys in backend/.env for cloud save."

    return {"ok": True, **status, "message": msg}
