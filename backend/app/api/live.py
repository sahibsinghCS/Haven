"""Live snapshot HTTP + WebSocket routes."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from roomos.utils.logging import get_logger

from ..core.feedback_events import FeedbackEvent
from ..core.preferences_events import PreferencesEvent
from ..core.state import state
from ..feedback_broadcast import publish_feedback_result
from roomos.inference.live_pipeline import LiveSnapshot

log = get_logger("roomos.api.live")
router = APIRouter(prefix="/api/live", tags=["live"])


def _ws_envelope(msg_type: str, payload: dict[str, Any]) -> str:
    return json.dumps({"type": msg_type, "payload": payload})


def _snapshot_ws_message(snap) -> str:
    return _ws_envelope("snapshot", _snapshot_payload(snap))


def _feedback_ws_message(event) -> str:
    return _ws_envelope("feedback", event.to_frontend_dict())


def _preferences_ws_message(event) -> str:
    return _ws_envelope("preferences", event.to_frontend_dict())


class FeedbackRequest(BaseModel):
    corrected_label: str = Field(..., min_length=1)
    notes: str = Field(default="", max_length=1000)


class LiveModeRequest(BaseModel):
    """``live`` = OpenCV camera + model; ``off`` = stop."""

    mode: str = Field(..., min_length=2)


class SetCameraRequest(BaseModel):
    """Webcam index (int) or network stream URL (http/rtsp)."""

    source: int | str
    backend: str | None = Field(
        default=None,
        description="OpenCV backend hint: auto, dshow, msmf, …",
    )


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
    """Start or stop live camera inference."""
    return state.set_live_mode(req.mode)


@router.get("/cameras")
def list_cameras(
    max_index: int = 4,
    excludeRoomId: str | None = None,
    forNewRoom: bool = False,
) -> dict[str, Any]:
    """Probe local webcams + LAN DroidCam phones (may take a few seconds)."""
    return state.list_cameras(
        max_index=max(0, min(8, max_index)),
        exclude_room_id=excludeRoomId,
        for_new_room=forNewRoom,
    )


@router.post("/camera")
def set_camera(req: SetCameraRequest) -> dict[str, Any]:
    """Select webcam and restart live inference if it is already running."""
    return state.set_video_source(req.source, backend=req.backend)


_MJPEG_BOUNDARY = "roomosframe"


@router.get("/preview.jpg")
def preview_frame() -> Response:
    """Latest preview JPEG from the live OpenCV feed."""
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


@router.get("/preview.mjpeg")
async def preview_mjpeg(request: Request) -> StreamingResponse:
    """Multipart MJPEG of the latest inference camera frame."""

    async def generate():
        last_gen = -1
        while True:
            if await request.is_disconnected():
                break
            jpeg, gen = await asyncio.to_thread(
                state.preview.wait_for_new_frame,
                last_gen,
                timeout=0.05,
            )
            if jpeg is not None and gen > last_gen:
                header = (
                    f"--{_MJPEG_BOUNDARY}\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpeg)}\r\n\r\n"
                ).encode("latin-1")
                yield header + jpeg + b"\r\n"
                last_gen = gen
            else:
                await asyncio.sleep(0.005)

    return StreamingResponse(
        generate(),
        media_type=f"multipart/x-mixed-replace; boundary={_MJPEG_BOUNDARY}",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/start")
def start_engine() -> dict[str, Any]:
    return state.start_engine()


@router.post("/start/live")
def start_live_engine() -> dict[str, Any]:
    return state.start_engine(mode="live")


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
    if state.engine is None:
        return {"enabled": False, "examples": 0, "has_evidence": False}
    return state.engine.feedback_status()


@router.get("/feedback/screenshots/{correction_id}/frame.jpg")
def feedback_correction_frame(correction_id: str) -> Response:
    """JPEG saved when a correction (web or Telegram) was recorded."""
    if state.engine is None:
        raise HTTPException(status_code=409, detail="Live inference engine is not running.")
    data = state.engine.feedback_correction_jpeg(correction_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Correction screenshot not found.")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/feedback/evidence/frames/{frame_index}.jpg")
def feedback_evidence_frame(frame_index: int) -> Response:
    """JPEG from the burst that the next live feedback tap would store."""
    if state.engine is None:
        raise HTTPException(status_code=409, detail="Live inference engine is not running.")
    data = state.engine.evidence_frame_jpeg(frame_index)
    if data is None:
        raise HTTPException(status_code=404, detail="Evidence frame not available yet.")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.post("/feedback")
def report_feedback(req: FeedbackRequest) -> dict[str, Any]:
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
    publish_feedback_result(result, source="web", notes=req.notes)
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
                "Saved this video frame as a positive example — similar moments should stay "
                f"on '{correction.corrected_label}'."
                if confirmed
                else "Saved this video frame to room memory; similar scenes update right away."
            ),
            "ongoing": (
                f"Future similar scenes reinforce '{correction.corrected_label}'."
                if confirmed
                else f"Future similar scenes bias toward '{correction.corrected_label}'."
            ),
            "notIncluded": (
                "XGBoost retrains in the background from this snapshot (debounced ~10s between runs)."
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
    journal = state.transition_journal()
    if journal is None:
        return {"enabled": False, "transitions": [], "reason": "transitions_disabled"}
    items = journal.list_transitions(
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
    journal = state.transition_journal()
    if journal is None:
        raise HTTPException(status_code=409, detail="Transition journal is disabled.")
    path = journal.screenshot_path(transition_id, frame_index)
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
    if state.engine is None:
        raise HTTPException(
            status_code=409,
            detail="Start Live camera mode to apply corrections (room memory updates while inference is running).",
        )
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
    """Stream snapshots + feedback events. Sends latest snapshot immediately."""
    await ws.accept()
    loop = asyncio.get_running_loop()
    state.hub.bind_loop(loop)
    state.feedback_hub.bind_loop(loop)
    state.preferences_hub.bind_loop(loop)
    snap_q = await state.hub.subscribe()
    fb_q = await state.feedback_hub.subscribe()
    pref_q = await state.preferences_hub.subscribe()
    try:
        if state.hub.latest is not None:
            await ws.send_text(_snapshot_ws_message(state.hub.latest))
        if state.feedback_hub.latest is not None:
            await ws.send_text(_feedback_ws_message(state.feedback_hub.latest))
        if state.preferences_hub.latest is not None:
            await ws.send_text(_preferences_ws_message(state.preferences_hub.latest))
        while True:
            snap_task = asyncio.create_task(snap_q.get())
            fb_task = asyncio.create_task(fb_q.get())
            pref_task = asyncio.create_task(pref_q.get())
            done, pending = await asyncio.wait(
                {snap_task, fb_task, pref_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                item = task.result()
                if isinstance(item, FeedbackEvent):
                    await ws.send_text(_feedback_ws_message(item))
                elif isinstance(item, PreferencesEvent):
                    await ws.send_text(_preferences_ws_message(item))
                elif isinstance(item, LiveSnapshot):
                    await ws.send_text(_snapshot_ws_message(item))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning("WebSocket loop ended: %s", e)
    finally:
        await state.hub.unsubscribe(snap_q)
        await state.feedback_hub.unsubscribe(fb_q)
        await state.preferences_hub.unsubscribe(pref_q)
        try:
            await ws.close()
        except Exception:
            pass
