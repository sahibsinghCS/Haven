"""Persist multi-room configuration to backend/data/rooms.json."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from threading import RLock
from typing import Any, List, Optional

from ..integrations.device_bridge import load_ui_device_settings
from ..utils.logging import get_logger
from ..video.input import is_auto_video_source, is_phone_stream_url
from .models import RoomCamera, RoomDocument, RoomRecord

log = get_logger("roomos.rooms.store")

_ROOMS_PATH = Path(__file__).resolve().parents[2] / "data" / "rooms.json"
_CAMERA_PREFS_PATH = Path(__file__).resolve().parents[2] / "data" / "camera_selection.json"


def _all_connected_device_ids() -> List[str]:
    ui = load_ui_device_settings()
    devices = ui.get("devices")
    if not isinstance(devices, dict):
        return []
    out: list[str] = []
    for key in ("smartPlugs", "lights", "thermostats"):
        items = devices.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("connected") and item.get("enabled"):
                device_id = str(item.get("id") or "").strip()
                if device_id:
                    out.append(device_id)
    return out


def _load_camera_prefs() -> tuple[Optional[int | str], Optional[str]]:
    if not _CAMERA_PREFS_PATH.is_file():
        return None, None
    try:
        data = json.loads(_CAMERA_PREFS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    source = data.get("source")
    if isinstance(source, str) and source.isdigit():
        source = int(source)
    backend = data.get("backend")
    return source, str(backend) if backend else None


def _save_camera_prefs(source: int | str, backend: str) -> None:
    _CAMERA_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": source, "backend": backend}
    _CAMERA_PREFS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _prefs_prefer_phone_stream(
    source: Optional[int | str], backend: Optional[str]
) -> bool:
    if source is None:
        return False
    if is_auto_video_source(source):
        return True
    return is_phone_stream_url(source)


def _reconcile_webcam_zero_with_prefs(doc: RoomDocument) -> bool:
    """When rooms.json still points at webcam 0 but prefs have DroidCam, use prefs."""
    saved_source, saved_backend = _load_camera_prefs()
    if not _prefs_prefer_phone_stream(saved_source, saved_backend):
        return False
    changed = False
    for room in doc.rooms:
        if not room.enabled:
            continue
        if isinstance(room.camera.source, int) and room.camera.source == 0:
            room.camera = RoomCamera(
                source=saved_source,  # type: ignore[arg-type]
                backend=saved_backend or "auto",
            )
            log.info(
                "Reconciled room %s camera: webcam 0 -> %r (from camera_selection.json)",
                room.id,
                saved_source,
            )
            changed = True
    return changed


class RoomsStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _ROOMS_PATH
        self._lock = RLock()
        self._doc = self._load_or_migrate()

    def _load_or_migrate(self) -> RoomDocument:
        if self._path.is_file():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                doc = RoomDocument.from_dict(raw)
                if _reconcile_webcam_zero_with_prefs(doc):
                    self._path.parent.mkdir(parents=True, exist_ok=True)
                    self._path.write_text(
                        json.dumps(doc.to_dict(), indent=2), encoding="utf-8"
                    )
                return doc
            except (OSError, json.JSONDecodeError) as e:
                log.warning("Could not read %s: %s — migrating", self._path, e)
        return self._migrate_from_legacy()

    def _migrate_from_legacy(self) -> RoomDocument:
        source, backend = _load_camera_prefs()
        if source is None:
            source = "auto"
        if backend is None:
            backend = "auto"
        room_id = str(uuid.uuid4())
        room = RoomRecord(
            id=room_id,
            name="Main room",
            enabled=True,
            camera=RoomCamera(source=source, backend=backend),
            device_ids=_all_connected_device_ids(),
        )
        doc = RoomDocument(rooms=[room], active_room_id=room_id)
        self._save_unlocked(doc)
        log.info("Migrated single-camera setup to rooms.json (room=%s)", room_id)
        return doc

    def _save_unlocked(self, doc: RoomDocument) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(doc.to_dict(), indent=2), encoding="utf-8")
        self._doc = doc

    def save(self) -> None:
        with self._lock:
            self._save_unlocked(self._doc)

    def document(self) -> RoomDocument:
        with self._lock:
            return RoomDocument.from_dict(self._doc.to_dict())

    def list_rooms(self) -> List[RoomRecord]:
        return self.document().rooms

    def get_room(self, room_id: str) -> Optional[RoomRecord]:
        return self.document().room_by_id(room_id)

    def active_room_id(self) -> Optional[str]:
        return self.document().active_room_id

    def set_active_room_id(self, room_id: str) -> None:
        with self._lock:
            if self._doc.room_by_id(room_id) is None:
                raise ValueError(f"Unknown room: {room_id}")
            self._doc.active_room_id = room_id
            self._save_unlocked(self._doc)

    def _camera_source_taken(
        self, source: int | str, *, skip_room_id: Optional[str] = None
    ) -> bool:
        # ``droidcam:auto`` / ``auto`` resolve to the next free phone per room at runtime.
        if is_auto_video_source(source):
            return False
        for room in self._doc.rooms:
            if skip_room_id and room.id == skip_room_id:
                continue
            other = room.camera.source
            if other == source:
                return True
            if (
                isinstance(source, str)
                and isinstance(other, str)
                and is_phone_stream_url(source)
                and source == other
            ):
                return True
        return False

    def add_room(
        self,
        *,
        name: str,
        source: int | str,
        backend: str = "auto",
        device_ids: Optional[List[str]] = None,
    ) -> RoomRecord:
        with self._lock:
            if isinstance(source, str) and source.isdigit():
                source = int(source)
            if self._camera_source_taken(source):
                raise ValueError(
                    "That camera is already assigned to another room. "
                    "Pick a different DroidCam URL or webcam for each room."
                )
            room_id = str(uuid.uuid4())
            room = RoomRecord(
                id=room_id,
                name=name.strip() or "Room",
                enabled=True,
                camera=RoomCamera(source=source, backend=backend),
                device_ids=list(device_ids or []),
            )
            self._doc.rooms.append(room)
            if self._doc.active_room_id is None:
                self._doc.active_room_id = room_id
            self._save_unlocked(self._doc)
            return room

    def update_room(
        self,
        room_id: str,
        *,
        name: Optional[str] = None,
        enabled: Optional[bool] = None,
        source: Optional[int | str] = None,
        backend: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
    ) -> RoomRecord:
        with self._lock:
            room = self._doc.room_by_id(room_id)
            if room is None:
                raise ValueError(f"Unknown room: {room_id}")
            if name is not None:
                room.name = name.strip() or room.name
            if enabled is not None:
                room.enabled = bool(enabled)
            if source is not None:
                if isinstance(source, str) and source.isdigit():
                    source = int(source)
                if self._camera_source_taken(source, skip_room_id=room_id):
                    raise ValueError(
                        "That camera is already assigned to another room."
                    )
                room.camera.source = source
            if backend is not None:
                room.camera.backend = backend
            if device_ids is not None:
                room.device_ids = list(device_ids)
            self._save_unlocked(self._doc)
            if (
                room_id == self._doc.active_room_id
                and (source is not None or backend is not None)
            ):
                _save_camera_prefs(room.camera.source, room.camera.backend)
            return room

    def delete_room(self, room_id: str) -> bool:
        with self._lock:
            before = len(self._doc.rooms)
            self._doc.rooms = [r for r in self._doc.rooms if r.id != room_id]
            if len(self._doc.rooms) == before:
                return False
            if self._doc.active_room_id == room_id:
                enabled = [r for r in self._doc.rooms if r.enabled]
                self._doc.active_room_id = (
                    enabled[0].id if enabled else (self._doc.rooms[0].id if self._doc.rooms else None)
                )
            self._save_unlocked(self._doc)
            return True

    def reorder_rooms(self, room_ids: List[str]) -> None:
        with self._lock:
            by_id = {r.id: r for r in self._doc.rooms}
            ordered = [by_id[rid] for rid in room_ids if rid in by_id]
            for room in self._doc.rooms:
                if room.id not in room_ids:
                    ordered.append(room)
            self._doc.rooms = ordered
            self._save_unlocked(self._doc)

    def update_orchestrator(self, **kwargs: Any) -> None:
        with self._lock:
            orch = self._doc.orchestrator
            if "mode" in kwargs:
                orch.mode = kwargs["mode"]
            if "grace_started_at" in kwargs:
                orch.grace_started_at = kwargs["grace_started_at"]
            if "grace_duration_sec" in kwargs:
                orch.grace_duration_sec = int(kwargs["grace_duration_sec"])
            self._save_unlocked(self._doc)

    def assign_all_devices_to_room(self, room_id: str) -> None:
        self.update_room(room_id, device_ids=_all_connected_device_ids())
