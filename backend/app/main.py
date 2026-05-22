"""RoomOS API entry point.

Thin transport wrapper around the ``roomos`` package. Exposes:

* ``GET  /api/health``                    — liveness
* ``GET  /api/live/status``               — engine status
* ``POST /api/live/start``                — start the inference engine
* ``POST /api/live/stop``                 — stop the inference engine
* ``GET  /api/live/snapshot``             — latest LiveInferenceSnapshot
* ``WS   /api/live/ws``                   — stream snapshots as they arrive
* ``GET  /api/preferences``               — PreferenceDocument
* ``PUT  /api/preferences``               — update PreferenceDocument
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from roomos.utils.logging import setup_logging

from .api import live as live_api
from .api import preferences as preferences_api
from roomos.demo.readiness import bundle_readiness, resolve_bundle_dir

from .core.config import settings
from .core.state import state


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


@asynccontextmanager
async def _lifespan(app: FastAPI):
    setup_logging(level=settings.roomos_log_level)
    state.hub.bind_loop(asyncio.get_running_loop())
    readiness = _demo_readiness_payload()
    if not readiness.get("model_ready"):
        import sys

        from roomos.demo.readiness import format_missing_model_help

        msg = format_missing_model_help(bundle_dir=readiness.get("bundle_dir", "data/models/latest"))
        print(msg, file=sys.stderr)
    elif settings.roomos_autostart:
        default_mode = None
        dm = (settings.roomos_demo_mode or "off").strip().lower()
        if dm in ("replay", "demo", "demo-replay"):
            default_mode = "replay"
        result = state.start_engine(mode=default_mode)
        if result.get("status") == "error":
            import sys

            print(result.get("error", "Engine failed to start."), file=sys.stderr)
    yield
    state.stop_engine()


app = FastAPI(title="RoomOS API", version="0.1.0", lifespan=_lifespan)

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
    payload["demo_mode"] = state.live_mode == "replay"
    if state.engine_compat_report is not None:
        payload["compat_ok"] = state.engine_compat_report.get("ok")
    return payload


app.include_router(live_api.router)
app.include_router(preferences_api.router)
