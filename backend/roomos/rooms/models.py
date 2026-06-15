"""Data models for multi-room camera configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Union

OrchestratorMode = Literal["active", "grace", "away"]

VideoSourceLike = Union[int, str]


@dataclass
class RoomCamera:
    source: VideoSourceLike
    backend: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "backend": self.backend}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoomCamera":
        source = data.get("source", 0)
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        return cls(source=source, backend=str(data.get("backend") or "auto"))


@dataclass
class RoomRecord:
    id: str
    name: str
    enabled: bool = True
    camera: RoomCamera = field(default_factory=lambda: RoomCamera(source=0))
    device_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "camera": self.camera.to_dict(),
            "deviceIds": list(self.device_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoomRecord":
        cam_raw = data.get("camera") or {}
        cam = RoomCamera.from_dict(cam_raw if isinstance(cam_raw, dict) else {})
        device_ids = data.get("deviceIds") or data.get("device_ids") or []
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or "Room"),
            enabled=bool(data.get("enabled", True)),
            camera=cam,
            device_ids=[str(x) for x in device_ids if x],
        )


@dataclass
class OrchestratorState:
    mode: OrchestratorMode = "away"
    grace_started_at: Optional[str] = None
    grace_duration_sec: int = 60

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "graceStartedAt": self.grace_started_at,
            "graceDurationSec": self.grace_duration_sec,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrchestratorState":
        mode = str(data.get("mode") or "away")
        if mode not in ("active", "grace", "away"):
            mode = "away"
        return cls(
            mode=mode,  # type: ignore[arg-type]
            grace_started_at=data.get("graceStartedAt"),
            grace_duration_sec=int(data.get("graceDurationSec", 60)),
        )


@dataclass
class RoomDocument:
    rooms: List[RoomRecord] = field(default_factory=list)
    active_room_id: Optional[str] = None
    orchestrator: OrchestratorState = field(default_factory=OrchestratorState)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rooms": [r.to_dict() for r in self.rooms],
            "activeRoomId": self.active_room_id,
            "orchestrator": self.orchestrator.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoomDocument":
        rooms_raw = data.get("rooms") or []
        rooms = [RoomRecord.from_dict(r) for r in rooms_raw if isinstance(r, dict)]
        orch_raw = data.get("orchestrator") or {}
        return cls(
            rooms=rooms,
            active_room_id=data.get("activeRoomId"),
            orchestrator=OrchestratorState.from_dict(orch_raw)
            if isinstance(orch_raw, dict)
            else OrchestratorState(),
        )

    def room_by_id(self, room_id: str) -> Optional[RoomRecord]:
        for room in self.rooms:
            if room.id == room_id:
                return room
        return None

    def enabled_rooms(self) -> List[RoomRecord]:
        return [r for r in self.rooms if r.enabled]
