"""Live snapshot HTTP + WebSocket routes."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from roomos.utils.logging import get_logger

from ..core.state import state

log = get_logger("roomos.api.live")
router = APIRouter(prefix="/api/live", tags=["live"])


class FeedbackRequest(BaseModel):
    corrected_label: str = Field(..., min_length=1)
    notes: str = Field(default="", max_length=1000)


def _snapshot_payload(snap) -> dict[str, Any]:
    return snap.to_frontend_dict()


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "engine_running": bool(state.engine and state.engine.is_running()),
        "engine_error": state.engine_error,
        "has_snapshot": state.hub.latest is not None,
    }


@router.post("/start")
def start_engine() -> dict[str, Any]:
    return state.start_engine()


@router.post("/stop")
def stop_engine() -> dict[str, Any]:
    return state.stop_engine()


@router.get("/snapshot")
def latest_snapshot() -> dict[str, Any]:
    snap = state.hub.latest
    if snap is None:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "No live snapshot available yet.",
                "engine_running": bool(state.engine and state.engine.is_running()),
                "engine_error": state.engine_error,
            },
        )
    return _snapshot_payload(snap)


@router.get("/feedback/status")
def feedback_status() -> dict[str, Any]:
    if state.engine is None:
        return {"enabled": False, "examples": 0, "has_evidence": False}
    return state.engine.feedback_status()


@router.post("/feedback")
def report_feedback(req: FeedbackRequest) -> dict[str, Any]:
    if state.engine is None:
        raise HTTPException(status_code=409, detail="Live inference engine is not running.")
    try:
        correction = state.engine.record_feedback(
            corrected_label=req.corrected_label,
            notes=req.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {
        "status": "recorded",
        "id": correction.id,
        "createdAt": correction.created_at,
        "predictedLabel": correction.predicted_label,
        "correctedLabel": correction.corrected_label,
        "screenshotCount": len(correction.screenshot_paths),
        "influence": correction.influence,
    }


@router.websocket("/ws")
async def ws_snapshots(ws: WebSocket) -> None:
    """Stream snapshots as they're produced. Sends the latest immediately."""
    await ws.accept()
    state.hub.bind_loop(asyncio.get_running_loop())
    q = await state.hub.subscribe()
    try:
        if state.hub.latest is not None:
            await ws.send_text(json.dumps(_snapshot_payload(state.hub.latest)))
        while True:
            snap = await q.get()
            await ws.send_text(json.dumps(_snapshot_payload(snap)))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning("WebSocket loop ended: %s", e)
    finally:
        await state.hub.unsubscribe(q)
        try:
            await ws.close()
        except Exception:
            pass
