"""RoomOS API entry point."""

from __future__ import annotations

import os

# Quiet OpenCV WARN lines when probing non-existent webcam indices on Windows.
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from roomos.utils.logging import setup_logging

from .api import auth as auth_api
from .api import integrations as integrations_api
from .api import live as live_api
from .api import moods as moods_api
from .api import preferences as preferences_api
from .api import rhythm as rhythm_api
from .api import rooms as rooms_api
from .api import settings as settings_api
from .auth_service import auth_configured, verify_access_token
from .room_context import clear_user, is_authenticated, normalize_room_id, set_room_id, set_user
from .supabase_store import probe_supabase_schema, supabase_configured
from roomos.demo.readiness import bundle_readiness, resolve_bundle_dir

from .core.config import settings
from .core.state import state
from .telegram_bot import start_telegram_bot, stop_telegram_bot

_AUTH_OPTIONAL_PREFIXES = (
    "/api/health",
    "/api/auth/",
    "/api/live/",
    "/api/rhythm/",
    "/api/rooms/",
    "/docs",
    "/openapi.json",
    "/redoc",
)

_AUTH_REQUIRED_PREFIXES = (
    "/api/preferences",
    "/api/integrations",
    "/api/settings/",
)


def _demo_readiness_payload() -> dict:
    try:
        bundle_dir = resolve_bundle_dir()
        readiness = bundle_readiness(bundle_dir)
    except Exception as exc:
        return {"model_ready": False, "error": str(exc)}
    return {
        "model_ready": readiness["ready"],
        "bundle_dir": readiness["bundle_dir"],
        "missing_artifacts": readiness["missing_artifacts"],
    }


def _path_requires_auth(path: str) -> bool:
    return any(path.startswith(p) for p in _AUTH_REQUIRED_PREFIXES)


def _path_auth_optional(path: str) -> bool:
    return any(path.startswith(p) for p in _AUTH_OPTIONAL_PREFIXES)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    setup_logging(level=settings.roomos_log_level)
    if supabase_configured():
        probe_supabase_schema()
    set_room_id(settings.haven_room_id_default)
    loop = asyncio.get_running_loop()
    state.hub.bind_loop(loop)
    state.feedback_hub.bind_loop(loop)
    state.preferences_hub.bind_loop(loop)
    readiness = _demo_readiness_payload()
    if not readiness.get("model_ready"):
        import sys

        from roomos.demo.readiness import format_missing_model_help

        msg = format_missing_model_help(bundle_dir=readiness.get("bundle_dir", "data/models/latest"))
        print(msg, file=sys.stderr)
    elif settings.roomos_autostart:
        result = state.start_engine(mode="live")
        if result.get("status") == "error":
            import sys

            print(result.get("error", "Engine failed to start."), file=sys.stderr)
    await start_telegram_bot()
    try:
        yield
    finally:
        await stop_telegram_bot()
        state.stop_engine()


app = FastAPI(title="RoomOS API", version="0.1.0", lifespan=_lifespan)


class HavenAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from fastapi.responses import JSONResponse

        path = request.url.path
        clear_user()

        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            user = verify_access_token(token)
            if user and user.get("id"):
                set_user(str(user["id"]), str(user.get("email") or "") or None)
                set_room_id(f"user-{str(user['id'])[:8]}")

        def _apply_room_header() -> JSONResponse | None:
            header = request.headers.get("x-haven-room-id") or request.headers.get("X-Haven-Room-Id")
            try:
                set_room_id(normalize_room_id(header or settings.haven_room_id_default))
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid X-Haven-Room-Id."})
            return None

        if not _path_requires_auth(path) or _path_auth_optional(path):
            if not is_authenticated():
                err = _apply_room_header()
                if err is not None:
                    return err
            return await call_next(request)

        if is_authenticated():
            return await call_next(request)

        if auth_configured() and settings.haven_require_auth:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Sign in required. Log in on the web app to save preferences and devices."
                },
            )

        err = _apply_room_header()
        if err is not None:
            return err
        return await call_next(request)


app.add_middleware(HavenAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    payload: dict = {"status": "ok", "service": "roomos", **_demo_readiness_payload()}
    if not payload.get("model_ready"):
        payload["status"] = "degraded"
        payload["hint"] = "Run: npm run setup:model  then  npm run demo"
    if state.engine_error:
        payload["engine_error"] = state.engine_error
    payload["live_mode"] = state.live_mode
    payload["cloud"] = {
        "supabase": supabase_configured(),
        "auth": auth_configured(),
        "storage": "supabase+local" if supabase_configured() else "local",
    }
    if state.engine_compat_report is not None:
        payload["compat_ok"] = state.engine_compat_report.get("ok")
    return payload


app.include_router(live_api.router)
app.include_router(rooms_api.router)
app.include_router(auth_api.router)
app.include_router(preferences_api.router)
app.include_router(integrations_api.router)
app.include_router(settings_api.router)
app.include_router(moods_api.router)
app.include_router(moods_api.training_router)
app.include_router(rhythm_api.router)
