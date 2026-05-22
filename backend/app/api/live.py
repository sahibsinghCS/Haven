"""Live snapshot HTTP + WebSocket routes."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel, Field

from roomos.utils.logging import get_logger

from ..core.state import state

log = get_logger("roomos.api.live")
router = APIRouter(prefix="/api/live", tags=["live"])


class FeedbackRequest(BaseModel):
    corrected_label: str = Field(..., min_length=1)
    notes: str = Field(default="", max_length=1000)


class LiveModeRequest(BaseModel):
    """``live`` = OpenCV camera + model; ``replay`` = fixture sequence; ``off`` = stop."""

    mode: str = Field(..., min_length=2)


def _snapshot_payload(snap) -> dict[str, Any]:
    return snap.to_frontend_dict()


@router.get("/status")
def status() -> dict[str, Any]:
    return state.status_payload()


@router.post("/mode")
def set_live_mode(req: LiveModeRequest) -> dict[str, Any]:
    """Switch live camera inference vs deterministic demo replay."""
    return state.set_live_mode(req.mode)


@router.get("/preview.jpg")
def preview_frame() -> Response:
    """Latest preview JPEG (live OpenCV feed or demo replay frame)."""
    data = state.preview.latest_jpeg()
    if data is None:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "No preview yet. Wait for the engine to produce a frame.",
                "engine_running": state.is_running,
                "live_mode": state.live_mode,
            },
        )
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.post("/start")
def start_engine() -> dict[str, Any]:
    return state.start_engine()


@router.post("/start/live")
def start_live_engine() -> dict[str, Any]:
    return state.start_engine(mode="live")


@router.post("/start/replay")
def start_replay_engine() -> dict[str, Any]:
    return state.start_engine(mode="replay")


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
                "engine_running": state.is_running,
                "live_mode": state.live_mode,
                "engine_error": state.engine_error,
            },
        )
    return _snapshot_payload(snap)


@router.get("/feedback/status")
def feedback_status() -> dict[str, Any]:
    if state.live_mode == "replay":
        return {
            "enabled": False,
            "examples": 0,
            "has_evidence": False,
            "reason": "demo_replay_active",
        }
    if state.engine is None:
        return {"enabled": False, "examples": 0, "has_evidence": False}
    return state.engine.feedback_status()


@router.post("/feedback")
def report_feedback(req: FeedbackRequest) -> dict[str, Any]:
    if state.live_mode == "replay":
        raise HTTPException(
            status_code=409,
            detail=(
                "Demo replay is active — corrections are disabled. "
                "Switch to live mode: POST /api/live/mode {\"mode\":\"live\"}."
            ),
        )
    if state.engine is None:
        raise HTTPException(status_code=409, detail="Live inference engine is not running.")
    try:
        result = state.engine.record_feedback(
            corrected_label=req.corrected_label,
            notes=req.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    correction = result["correction"]
    preview = result.get("probability_preview") or {}
    storage = result.get("storage") or {}
    return {
        "status": "recorded",
        "id": correction.id,
        "createdAt": correction.created_at,
        "predictedLabel": correction.predicted_label,
        "correctedLabel": correction.corrected_label,
        "screenshotCount": len(correction.screenshot_paths),
        "influence": correction.influence,
        "memoryExamples": int(result.get("memory_examples", 0)),
        "retrainsModel": False,
        "effects": {
            "immediate": (
                "This burst's feature fingerprint is saved; similar reads get probability nudges "
                "on the next inference ticks (not a full model retrain)."
            ),
            "ongoing": (
                f"Future bursts similar to this moment bias toward '{correction.corrected_label}' "
                f"(cosine similarity ≥ {storage.get('similarity_floor', '?')})."
            ),
            "notIncluded": "XGBoost weights stay the same until you run npm run train:* with new labels.",
        },
        "probabilityPreview": preview,
        "storage": {
            "dir": storage.get("storage_dir"),
            "examplesFile": storage.get("examples_file"),
            "eventsLog": storage.get("events_log"),
            "screenshotsDir": storage.get("screenshots_dir"),
        },
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
