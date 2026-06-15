"""Multi-room camera registry and status API."""

from __future__ import annotations

import asyncio
import json
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from ..core.state import state

router = APIRouter(prefix="/api/rooms", tags=["rooms"])

_MJPEG_BOUNDARY = "roomosroomframe"


class RoomCameraPayload(BaseModel):
    source: int | str
    backend: str = "auto"


class CreateRoomRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    camera: RoomCameraPayload
    deviceIds: List[str] = Field(default_factory=list)


class UpdateRoomRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    enabled: Optional[bool] = None
    camera: Optional[RoomCameraPayload] = None
    deviceIds: Optional[List[str]] = None


class ReorderRoomsRequest(BaseModel):
    roomIds: List[str] = Field(..., min_length=1)


class SetActiveRoomRequest(BaseModel):
    roomId: str = Field(..., min_length=1)


@router.get("")
def list_rooms() -> dict[str, Any]:
    return state.rooms_status()


@router.get("/status")
def rooms_status() -> dict[str, Any]:
    return state.rooms_status()


@router.post("")
def create_room(req: CreateRoomRequest) -> dict[str, Any]:
    try:
        room = state.rooms_store.add_room(
            name=req.name,
            source=req.camera.source,
            backend=req.camera.backend,
            device_ids=req.deviceIds,
        )
        state.orchestrator.sync_previews()
        return {"room": room.to_dict(), **state.rooms_status()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/{room_id}")
def update_room(room_id: str, req: UpdateRoomRequest) -> dict[str, Any]:
    try:
        kwargs: dict[str, Any] = {}
        if req.name is not None:
            kwargs["name"] = req.name
        if req.enabled is not None:
            kwargs["enabled"] = req.enabled
        if req.camera is not None:
            kwargs["source"] = req.camera.source
            kwargs["backend"] = req.camera.backend
        if req.deviceIds is not None:
            kwargs["device_ids"] = req.deviceIds
        room = state.rooms_store.update_room(room_id, **kwargs)
        state.orchestrator.sync_previews()
        if req.enabled is False and state.orchestrator.active_room_id == room_id:
            enabled = state.rooms_store.document().enabled_rooms()
            if enabled:
                state.rooms_store.set_active_room_id(enabled[0].id)
        return {"room": room.to_dict(), **state.rooms_status()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{room_id}")
def delete_room(room_id: str) -> dict[str, Any]:
    if not state.rooms_store.delete_room(room_id):
        raise HTTPException(status_code=404, detail="Room not found")
    state.orchestrator.sync_previews()
    return state.rooms_status()


@router.post("/reorder")
def reorder_rooms(req: ReorderRoomsRequest) -> dict[str, Any]:
    state.rooms_store.reorder_rooms(req.roomIds)
    return state.rooms_status()


@router.post("/active")
def set_active_room(req: SetActiveRoomRequest) -> dict[str, Any]:
    try:
        state.rooms_store.set_active_room_id(req.roomId)
        if state.live_mode == "live":
            state.restart_engine_for_room(req.roomId)
        return state.rooms_status()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


class SetRoomEnabledRequest(BaseModel):
    enabled: bool


@router.post("/{room_id}/enabled")
def set_room_enabled(room_id: str, req: SetRoomEnabledRequest) -> dict[str, Any]:
    try:
        state.rooms_store.update_room(room_id, enabled=req.enabled)
        state.orchestrator.sync_previews()
        if not req.enabled and state.orchestrator.active_room_id == room_id:
            enabled_rooms = state.rooms_store.document().enabled_rooms()
            if enabled_rooms:
                state.rooms_store.set_active_room_id(enabled_rooms[0].id)
        return state.rooms_status()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{room_id}/preview.jpg")
def room_preview_jpg(room_id: str) -> Response:
    data = state.room_preview_jpeg(room_id)
    if data is None:
        raise HTTPException(status_code=503, detail="No preview for this room yet")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{room_id}/preview.mjpeg")
async def room_preview_mjpeg(room_id: str) -> StreamingResponse:
    hub = state.room_previews.hub

    async def stream():
        last_gen = -1
        while True:
            jpeg, gen = await asyncio.to_thread(
                hub.wait_for_new_frame,
                room_id,
                last_gen,
                timeout=0.1,
            )
            if jpeg is not None and gen > last_gen:
                yield (
                    f"--{_MJPEG_BOUNDARY}\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpeg)}\r\n\r\n"
                ).encode() + jpeg + b"\r\n"
                last_gen = gen
            else:
                await asyncio.sleep(0.05)

    return StreamingResponse(
        stream(),
        media_type=f"multipart/x-mixed-replace; boundary={_MJPEG_BOUNDARY}",
        headers={"Cache-Control": "no-store"},
    )
