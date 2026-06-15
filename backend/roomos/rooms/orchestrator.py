"""Multi-room presence state machine: active → grace → away."""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import numpy as np

from ..config import load_config
from ..devices.action_arbiter import ActionSource
from ..utils.logging import get_logger
from .models import OrchestratorMode, RoomRecord
from .store import RoomsStore

if TYPE_CHECKING:
    from ..inference.live_pipeline import LiveSnapshot
    from .preview_manager import RoomPreviewManager

log = get_logger("roomos.rooms.orchestrator")

WALKWAY_BRIGHTNESS = 40
WALKWAY_COLOR = "#F5F0E8"
GRACE_MOTION_THRESHOLD = 8.0  # mean abs diff on 64x64 gray thumb
# Burst/smoothed bar to end grace before the away label fully unwinds (confirm_bursts + cooldown).
GRACE_PRESENCE_BURST_THRESHOLD = 0.28


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _motion_score(prev: np.ndarray, curr: np.ndarray) -> float:
    try:
        import cv2

        g1 = cv2.resize(prev, (64, 64))
        g2 = cv2.resize(curr, (64, 64))
        if len(g1.shape) == 3:
            g1 = cv2.cvtColor(g1, cv2.COLOR_BGR2GRAY)
        if len(g2.shape) == 3:
            g2 = cv2.cvtColor(g2, cv2.COLOR_BGR2GRAY)
        return float(np.abs(g1.astype(np.float32) - g2.astype(np.float32)).mean())
    except Exception:
        return 0.0


def _non_away_beats_away(probs: Dict[str, float]) -> bool:
    if not probs:
        return False
    away_p = float(probs.get("away", 0.0))
    non_away = max(
        (float(probs.get(k, 0.0)) for k in probs if k != "away"),
        default=0.0,
    )
    return non_away > away_p and non_away >= GRACE_PRESENCE_BURST_THRESHOLD


def _snap_suggests_presence(snap: "LiveSnapshot") -> bool:
    """True when smoothed or burst-level read indicates someone is back."""
    label = str(snap.primary_state or "").strip()
    if label and label not in ("away", "unknown"):
        return True
    if _non_away_beats_away(snap.model_probs or {}):
        return True
    # Smoothed distribution often shifts before the committed primary label.
    return _non_away_beats_away(snap.distribution or {})


def _resume_mood_from_snapshot(snap: "LiveSnapshot", *, fallback: str) -> str:
    """Best-effort mood while smoothed label may still read away."""
    label = str(snap.primary_state or "").strip()
    if label and label not in ("away", "unknown"):
        return label
    for probs in (snap.model_probs, snap.distribution):
        if not probs:
            continue
        candidates = [
            (str(k), float(v))
            for k, v in probs.items()
            if str(k) not in ("away", "unknown")
        ]
        if not candidates:
            continue
        top_label, top_conf = max(candidates, key=lambda kv: kv[1])
        if top_conf >= GRACE_PRESENCE_BURST_THRESHOLD:
            return top_label
    return fallback


class PresenceOrchestrator:
    """Coordinates per-room inference, grace period, and device scenes."""

    def __init__(
        self,
        store: RoomsStore,
        *,
        config_path: str,
        preview_manager: Optional["RoomPreviewManager"] = None,
        restart_engine: Optional[Callable[[str], None]] = None,
        stop_engine: Optional[Callable[[], None]] = None,
    ) -> None:
        self._store = store
        self._config_path = config_path
        self._preview = preview_manager
        self._restart_engine = restart_engine
        self._stop_engine = stop_engine
        self._lock = threading.RLock()
        self._grace_thread: Optional[threading.Thread] = None
        self._grace_stop = threading.Event()
        self._last_mood_by_room: Dict[str, str] = {}
        self._prev_grace_frames: Dict[str, np.ndarray] = {}
        self._inference_room_id: Optional[str] = None
        self._last_primary_state: Optional[str] = None
        self._grace_origin_room_id: Optional[str] = None
        self._pending_mood_restore: Dict[str, str] = {}

    @property
    def mode(self) -> OrchestratorMode:
        return self._store.document().orchestrator.mode

    @property
    def active_room_id(self) -> Optional[str]:
        doc = self._store.document()
        return doc.active_room_id

    def set_inference_room(self, room_id: Optional[str]) -> None:
        with self._lock:
            self._inference_room_id = room_id
            if self._preview is not None:
                self._preview.set_inference_room(room_id)

    def on_live_started(self) -> None:
        doc = self._store.document()
        active_id = doc.active_room_id
        enabled = doc.enabled_rooms()
        if not enabled:
            log.warning("No enabled rooms — orchestrator idle")
            return
        if active_id is None or doc.room_by_id(active_id) is None:
            active_id = enabled[0].id
            self._store.set_active_room_id(active_id)
        self._store.update_orchestrator(mode="active", grace_started_at=None)
        self.set_inference_room(active_id)
        if self._preview is not None:
            self._preview.sync_rooms(doc.rooms)
        self._turn_off_non_active_devices(active_id)
        mood = str(self._last_primary_state or "").strip()
        if not mood:
            try:
                from app.core.state import state

                snap = state.hub.latest
                if snap is not None:
                    mood = str(snap.primary_state or "").strip()
            except Exception:
                mood = ""
        if mood and mood != "away":
            self._last_mood_by_room[active_id] = mood
            self._apply_active_room_mood(active_id, mood)

    def on_live_stopped(self) -> None:
        self._stop_grace_scanner()
        self._store.update_orchestrator(mode="away", grace_started_at=None)
        self.set_inference_room(None)
        if self._preview is not None:
            self._preview.stop_all()
        self._apply_all_devices_off()

    def handle_snapshot(self, room_id: str, snap: "LiveSnapshot") -> None:
        with self._lock:
            mode = self.mode
            label = str(snap.primary_state or "")
            self._last_primary_state = label

            if mode == "active" and room_id == self.active_room_id:
                if label == "away":
                    self._enter_grace(room_id)
                    return
                if label != "away":
                    pending = self._pending_mood_restore.pop(room_id, None)
                    if pending is not None:
                        self._last_mood_by_room[room_id] = pending
                        self._apply_active_room_mood(
                            room_id,
                            pending,
                            action_source=ActionSource.ORCHESTRATOR_RESUME,
                        )
                    elif label != self._last_mood_by_room.get(room_id):
                        self._last_mood_by_room[room_id] = label
                        self._apply_active_room_mood(room_id, label)
                return

            if mode == "grace" and room_id == self.active_room_id:
                if _snap_suggests_presence(snap):
                    fallback = self._last_mood_by_room.get(room_id, "work")
                    resume_mood = _resume_mood_from_snapshot(snap, fallback=fallback)
                    self._resume_from_grace(room_id, resume_mood)

    def _enter_grace(self, from_room_id: str) -> None:
        log.info("Room %s away — entering grace period", from_room_id)
        self._grace_origin_room_id = from_room_id
        restore_mood = self._last_mood_by_room.get(from_room_id, "work")
        if restore_mood and restore_mood != "away":
            self._pending_mood_restore[from_room_id] = restore_mood
        self._store.update_orchestrator(mode="grace", grace_started_at=_now_iso())
        # Apply saved away preferences to the room that went away (fan off, lights dim, etc.).
        self._apply_active_room_mood(
            from_room_id,
            "away",
            action_source=ActionSource.ORCHESTRATOR_AWAY,
        )
        self._apply_walkway_lights(exclude_room_id=from_room_id)
        self._turn_off_non_active_devices(from_room_id)
        self._prev_grace_frames.clear()
        self._start_grace_scanner(from_room_id)

    def _resume_from_grace(self, room_id: str, mood: str) -> None:
        """User returned during grace — restore active mode and room preferences."""
        resume_mood = str(mood or "").strip() or "work"
        if resume_mood == "away":
            resume_mood = self._last_mood_by_room.get(room_id, "work")
        log.info(
            "Room %s presence resumed — leaving grace for mood=%s",
            room_id,
            resume_mood,
        )
        self._stop_grace_scanner()
        self._grace_origin_room_id = None
        self._store.update_orchestrator(mode="active", grace_started_at=None)
        self._last_mood_by_room[room_id] = resume_mood
        self._pending_mood_restore.pop(room_id, None)
        self._apply_active_room_mood(
            room_id,
            resume_mood,
            action_source=ActionSource.ORCHESTRATOR_RESUME,
        )

    def _enter_global_away(self) -> None:
        log.info("Grace expired with no occupancy — global away")
        self._grace_origin_room_id = None
        self._stop_grace_scanner()
        self._store.update_orchestrator(mode="away", grace_started_at=None)
        self._apply_all_devices_off()
        if self._stop_engine is not None:
            try:
                self._stop_engine()
            except Exception as e:
                log.warning("Stop engine on global away failed: %s", e)

    def _promote_room(self, room_id: str) -> None:
        log.info("Occupancy detected in room %s — becoming active", room_id)
        self._grace_origin_room_id = None
        self._stop_grace_scanner()
        self._store.set_active_room_id(room_id)
        self._store.update_orchestrator(mode="active", grace_started_at=None)
        self.set_inference_room(room_id)
        if self._restart_engine is not None:
            try:
                self._restart_engine(room_id)
            except Exception as e:
                log.warning("Restart engine for room %s failed: %s", room_id, e)

    def _start_grace_scanner(self, exclude_room_id: str) -> None:
        self._stop_grace_scanner()
        self._grace_stop.clear()

        def _run() -> None:
            doc = self._store.document()
            grace_sec = doc.orchestrator.grace_duration_sec
            started = time.monotonic()
            while not self._grace_stop.is_set():
                if time.monotonic() - started >= grace_sec:
                    self._enter_global_away()
                    return
                self._scan_grace_rooms(exclude_room_id)
                self._grace_stop.wait(1.5)

        self._grace_thread = threading.Thread(
            target=_run, name="room-grace-scan", daemon=True
        )
        self._grace_thread.start()

    def _stop_grace_scanner(self) -> None:
        """Signal the grace loop to exit; join unless we're already on that thread."""
        self._grace_stop.set()
        thread = self._grace_thread
        self._grace_thread = None
        if thread is None or not thread.is_alive():
            return
        if thread is threading.current_thread():
            # Grace expired or promoted another room from inside the scanner loop.
            return
        thread.join(timeout=3.0)

    def _scan_grace_rooms(self, exclude_room_id: str) -> None:
        if self._preview is None:
            return
        doc = self._store.document()
        for room in doc.enabled_rooms():
            if room.id == exclude_room_id:
                continue
            bgr = self._preview.latest_bgr(room.id)
            if bgr is None:
                continue
            prev = self._prev_grace_frames.get(room.id)
            self._prev_grace_frames[room.id] = bgr.copy()
            if prev is None:
                continue
            if _motion_score(prev, bgr) >= GRACE_MOTION_THRESHOLD:
                self._promote_room(room.id)
                return

    def _integrations(self) -> dict[str, Any]:
        try:
            from ..integrations.device_bridge import merge_runtime_integrations

            return merge_runtime_integrations({})
        except Exception:
            return {}

    def _dry_run(self) -> bool:
        try:
            from ..devices.scene_apply import preference_sync_dry_run

            return preference_sync_dry_run(True)
        except Exception:
            return True

    def _apply_active_room_mood(
        self,
        room_id: str,
        mood: str,
        *,
        action_source: ActionSource = ActionSource.ORCHESTRATOR_ROOM,
    ) -> None:
        from ..devices.scene_apply import (
            apply_room_scene_async,
            resolve_apply_scene_for_mood,
        )

        room = self._store.get_room(room_id)
        if room is None:
            return
        scene = resolve_apply_scene_for_mood(mood)
        try:
            record = asyncio.run(
                apply_room_scene_async(
                    scene,
                    device_ids=room.device_ids,
                    dry_run=self._dry_run(),
                    integrations=self._integrations(),
                    room_state=mood,
                    room_id=room_id,
                    action_source=action_source,
                )
            )
            suppressed = record.get("suppressed") or []
            if suppressed and action_source != ActionSource.ORCHESTRATOR_RESUME:
                log.warning(
                    "Room %s mood %s suppressed (%s) — retrying with resume priority",
                    room_id,
                    mood,
                    suppressed,
                )
                self._apply_active_room_mood(
                    room_id,
                    mood,
                    action_source=ActionSource.ORCHESTRATOR_RESUME,
                )
        except Exception as e:
            log.warning("Active room scene apply failed: %s", e)

    def _apply_walkway_lights(self, *, exclude_room_id: Optional[str] = None) -> None:
        from ..devices.scene_apply import apply_walkway_lights_async

        doc = self._store.document()
        target_ids: list[str] = []
        for room in doc.rooms:
            if exclude_room_id is not None and room.id == exclude_room_id:
                continue
            target_ids.extend(room.device_ids)
        if not target_ids:
            return
        try:
            asyncio.run(
                apply_walkway_lights_async(
                    target_ids,
                    brightness=WALKWAY_BRIGHTNESS,
                    hex_color=WALKWAY_COLOR,
                    dry_run=self._dry_run(),
                    integrations=self._integrations(),
                )
            )
        except Exception as e:
            log.warning("Walkway lights failed: %s", e)

    def _apply_all_devices_off(self) -> None:
        """Apply saved away preferences for every room (used when grace expires or live stops)."""
        doc = self._store.document()
        for room in doc.rooms:
            if not room.device_ids:
                continue
            self._apply_active_room_mood(
                room.id,
                "away",
                action_source=ActionSource.ORCHESTRATOR_AWAY,
            )

    def _turn_off_non_active_devices(self, active_id: Optional[str]) -> None:
        doc = self._store.document()
        for room in doc.rooms:
            if active_id is not None and room.id == active_id:
                continue
            if not room.device_ids:
                continue
            self._apply_active_room_mood(
                room.id,
                "away",
                action_source=ActionSource.ORCHESTRATOR_AWAY,
            )

    def status_payload(self) -> dict[str, Any]:
        doc = self._store.document()
        orch = doc.orchestrator
        rooms_out: List[dict[str, Any]] = []
        for room in doc.rooms:
            preview_luma = None
            preview_available = False
            if self._preview is not None:
                preview_luma = self._preview.hub.mean_luma(room.id)
                preview_available = self._preview.hub.latest_jpeg(room.id) is not None
            rooms_out.append(
                {
                    "id": room.id,
                    "name": room.name,
                    "enabled": room.enabled,
                    "camera": room.camera.to_dict(),
                    "deviceIds": list(room.device_ids),
                    "isActive": room.id == doc.active_room_id,
                    "inferenceActive": room.id == self._inference_room_id,
                    "previewAvailable": preview_available,
                    "previewMeanLuma": preview_luma,
                    "lastMood": self._last_mood_by_room.get(room.id),
                }
            )
        grace_remaining: Optional[float] = None
        if orch.mode == "grace" and orch.grace_started_at:
            try:
                started = datetime.fromisoformat(
                    orch.grace_started_at.replace("Z", "+00:00")
                )
                elapsed = (
                    datetime.now(timezone.utc) - started
                ).total_seconds()
                grace_remaining = max(0.0, float(orch.grace_duration_sec) - elapsed)
            except Exception:
                grace_remaining = None

        return {
            "orchestratorMode": orch.mode,
            "activeRoomId": doc.active_room_id,
            "graceDurationSec": orch.grace_duration_sec,
            "graceStartedAt": orch.grace_started_at,
            "graceRemainingSec": grace_remaining,
            "lastPrimaryState": self._last_primary_state,
            "rooms": rooms_out,
        }

    def camera_for_room(self, room_id: str) -> tuple[Any, str]:
        room = self._store.get_room(room_id)
        if room is None:
            raise ValueError(f"Unknown room: {room_id}")
        return room.camera.source, room.camera.backend

    def sync_previews(self) -> None:
        if self._preview is not None:
            self._preview.sync_rooms(self._store.document().rooms)
