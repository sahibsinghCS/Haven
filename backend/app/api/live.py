"""Live snapshot HTTP + WebSocket routes."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
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


class TransitionCorrectRequest(BaseModel):
    corrected_label: str = Field(..., min_length=1)
    notes: str = Field(default="", max_length=1000)


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
    auto = state.engine.auto_retrain_status() if state.engine else {"enabled": False}
    auto_on = bool(auto.get("enabled"))
    confirmed = correction.predicted_label == correction.corrected_label
    min_n = int(auto.get("min_corrections", 3))
    return {
        "status": "recorded",
        "id": correction.id,
        "createdAt": correction.created_at,
        "predictedLabel": correction.predicted_label,
        "correctedLabel": correction.corrected_label,
        "confirmed": confirmed,
        "screenshotCount": len(correction.screenshot_paths),
        "influence": correction.influence,
        "memoryExamples": int(result.get("memory_examples", 0)),
        "retrainsModel": auto_on,
        "autoRetrain": auto,
        "effects": {
            "immediate": (
                "Saved this scene as a positive example — similar moments should stay "
                f"on '{correction.corrected_label}'."
                if confirmed
                else "Saved to room memory; similar bursts get probability nudges right away."
            ),
            "ongoing": (
                f"Future similar scenes reinforce '{correction.corrected_label}'."
                if confirmed
                else f"Future similar scenes bias toward '{correction.corrected_label}'."
            ),
            "notIncluded": (
                f"After {min_n} right/wrong taps, XGBoost auto-retrains and reloads live."
                if auto_on
                else "Enable inference.auto_retrain in configs/inference.yaml for automatic model updates."
            ),
        },
        "probabilityPreview": preview,
        "storage": {
            "dir": storage.get("storage_dir"),
            "examplesFile": storage.get("examples_file"),
            "eventsLog": storage.get("events_log"),
            "screenshotsDir": storage.get("screenshots_dir"),
        },
    }


@router.get("/transitions")
def list_transitions(
    limit: int = 40,
    uncorrected_only: bool = False,
) -> dict[str, Any]:
    """Recent label switches with frame evidence for the Review UI."""
    if state.live_mode == "replay":
        return {
            "enabled": False,
            "transitions": [],
            "reason": "demo_replay_active",
        }
    if state.engine is None:
        return {"enabled": False, "transitions": [], "reason": "engine_off"}
    journal = getattr(state.engine, "_transition_journal", None)
    if journal is None:
        return {"enabled": False, "transitions": [], "reason": "transitions_disabled"}
    items = state.engine.list_transitions(
        limit=max(1, min(100, limit)),
        uncorrected_only=uncorrected_only,
    )
    return {
        "enabled": True,
        **journal.status_payload(),
        "transitions": [t.to_api_dict() for t in items],
    }


@router.get("/transitions/{transition_id}/frames/{frame_index}.jpg")
def transition_frame(transition_id: str, frame_index: int) -> Response:
    if state.engine is None:
        raise HTTPException(status_code=409, detail="Live inference engine is not running.")
    path = state.engine.transition_screenshot_path(transition_id, frame_index)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Transition frame not found.")
    return FileResponse(
        path=Path(path),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/transitions/{transition_id}/correct")
def correct_transition(transition_id: str, req: TransitionCorrectRequest) -> dict[str, Any]:
    """Relabel a past switch — saves to room memory and improves similar bursts."""
    if state.live_mode == "replay":
        raise HTTPException(
            status_code=409,
            detail="Demo replay is active — switch to live mode to review transitions.",
        )
    if state.engine is None:
        raise HTTPException(status_code=409, detail="Live inference engine is not running.")
    try:
        result = state.engine.record_transition_correction(
            transition_id=transition_id,
            corrected_label=req.corrected_label,
            notes=req.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    correction = result["correction"]
    preview = result.get("probability_preview") or {}
    auto = state.engine.auto_retrain_status() if state.engine else {"enabled": False}
    auto_on = bool(auto.get("enabled"))
    confirmed = correction.predicted_label == correction.corrected_label
    min_n = int(auto.get("min_corrections", 3))
    return {
        "status": "recorded",
        "transitionId": transition_id,
        "id": correction.id,
        "createdAt": correction.created_at,
        "predictedLabel": result.get("predicted_label", correction.predicted_label),
        "fromLabel": result.get("from_label"),
        "correctedLabel": correction.corrected_label,
        "confirmed": confirmed,
        "memoryExamples": int(result.get("memory_examples", 0)),
        "retrainsModel": auto_on,
        "autoRetrain": auto,
        "effects": {
            "immediate": (
                "Marked this switch as correct — saved for reinforcement."
                if confirmed
                else "Saved this switch to room memory — similar bursts update immediately."
            ),
            "ongoing": (
                f"Similar scenes should reinforce '{correction.corrected_label}'."
                if confirmed
                else f"Similar scenes should read more like '{correction.corrected_label}'."
            ),
            "notIncluded": (
                f"Auto-retrain after {min_n} right/wrong reviews."
                if auto_on
                else "Auto-retrain disabled in config.",
            ),
        },
        "probabilityPreview": preview,
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
