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
from .core.config import settings
from .core.state import state


@asynccontextmanager
async def _lifespan(app: FastAPI):
    setup_logging(level=settings.roomos_log_level)
    state.hub.bind_loop(asyncio.get_running_loop())
    if settings.roomos_autostart:
        state.start_engine()
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
def health() -> dict[str, str]:
    return {"status": "ok", "service": "roomos"}


app.include_router(live_api.router)
app.include_router(preferences_api.router)
