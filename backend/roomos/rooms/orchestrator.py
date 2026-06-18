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
# Consecutive away bursts on the active room before entering grace (~4.5s at 1.5s stride).
AWAY_ENTER_STREAK = 3
# Origin room (during grace) can resume quickly when you return.
PRESENCE_RESUME_STREAK = 2
# Other room must hold a confident mood label before stealing focus during grace.
GRACE_CROSS_ROOM_PROMOTE_STREAK = 3
# Direct handoff while still in active mode (user left without grace completing).
ACTIVE_MODE_HANDOFF_STREAK = 4
# Active room must read committed "away" this many times before another room can take focus.
ACTIVE_EMPTY_LABEL_STREAK = 3
MIN_CROSS_ROOM_PROMOTE_CONFIDENCE = 0.38
# Minimum gap between active-room swaps to stop ping-pong (grace handoffs are exempt).
PROMOTE_COOLDOWN_SEC = 20.0


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


def _snap_shows_ml_presence(snap: "LiveSnapshot") -> bool:
    """Committed mood label on this room's camera (not motion / burst hints)."""
    label = str(snap.primary_state or "").strip()
    return label not in ("", "away", "unknown")


def _label_confidence(snap: "LiveSnapshot") -> float:
    """Best confidence for the committed primary label (raw + smoothed)."""
    label = str(snap.primary_state or "").strip()
    if not label:
        return 0.0
    raw = float((snap.model_probs or {}).get(label, 0.0))
    smooth = float((snap.distribution or {}).get(label, 0.0))
    return max(raw, smooth, float(snap.primary_confidence or 0.0))


def _snap_confident_ml_presence(snap: "LiveSnapshot") -> bool:
    """Committed non-away label with enough confidence to move focus."""
    if not _snap_shows_ml_presence(snap):
        return False
    if _label_confidence(snap) >= MIN_CROSS_ROOM_PROMOTE_CONFIDENCE:
        return True
    # Smoothed mood can lead the raw burst — trust distribution when activity leads away.
    return _non_away_beats_away(snap.distribution or {})


def _snap_suggests_presence(snap: "LiveSnapshot") -> bool:
    """True when smoothed or burst-level read indicates someone is back."""
    if _snap_shows_ml_presence(snap):
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
        on_active_room_changed: Optional[Callable[[str], None]] = None,
        on_mode_changed: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._store = store
        self._config_path = config_path
        self._preview = preview_manager
        self._on_active_room_changed = on_active_room_changed
        self._on_mode_changed = on_mode_changed
        self._lock = threading.RLock()
        self._grace_thread: Optional[threading.Thread] = None
        self._grace_stop = threading.Event()
        self._last_mood_by_room: Dict[str, str] = {}
        self._inference_room_ids: set[str] = set()
        self._active_room_id: Optional[str] = None
        self._last_primary_state: Optional[str] = None
        self._grace_origin_room_id: Optional[str] = None
        self._pending_mood_restore: Dict[str, str] = {}
        self._away_streak: Dict[str, int] = {}
        self._presence_streak: Dict[str, int] = {}
        self._cross_room_streak: Dict[str, int] = {}
        self._origin_resume_streak: Dict[str, int] = {}
        self._last_label_by_room: Dict[str, str] = {}
        self._last_snap_by_room: Dict[str, "LiveSnapshot"] = {}
        self._active_empty_streak: Dict[str, int] = {}
        self._last_promote_monotonic: float = 0.0

    @property
    def mode(self) -> OrchestratorMode:
        return self._store.document().orchestrator.mode

    @property
    def active_room_id(self) -> Optional[str]:
        doc = self._store.document()
        return doc.active_room_id

    def set_inference_rooms(self, room_ids: set[str]) -> None:
        """Rooms with a live ML engine (all enabled rooms while live is on)."""
        with self._lock:
            self._inference_room_ids = set(room_ids)

    def set_inference_room(self, room_id: Optional[str]) -> None:
        """Backward-compatible: track which room feeds the primary UI snapshot."""
        with self._lock:
            self._active_room_id = room_id
            if self._preview is not None and not self._inference_room_ids:
                self._preview.set_inference_rooms(
                    {room_id} if room_id else set()
                )

    def _reset_presence_streaks(self) -> None:
        self._away_streak.clear()
        self._presence_streak.clear()
        self._cross_room_streak.clear()
        self._origin_resume_streak.clear()

    def _track_active_empty_streak(self, room_id: str, label: str) -> None:
        active_id = self.active_room_id
        if not active_id or room_id != active_id:
            return
        if label == "away":
            self._active_empty_streak[active_id] = (
                self._active_empty_streak.get(active_id, 0) + 1
            )
        else:
            self._active_empty_streak[active_id] = 0

    def _active_room_committed_empty(self) -> bool:
        """Active room has read committed away several times (ignore burst noise)."""
        active_id = self.active_room_id
        if not active_id:
            return True
        return self._active_empty_streak.get(active_id, 0) >= ACTIVE_EMPTY_LABEL_STREAK

    def _active_room_label_blocks_cross_promote(self) -> bool:
        """During grace the vacated room should read away; a mood label means still occupied."""
        active_id = self.active_room_id
        if not active_id:
            return False
        label = str(self._last_label_by_room.get(active_id, "")).strip()
        return label not in ("", "away", "unknown")

    def _origin_blocks_cross_room_promote(self, origin_id: str) -> bool:
        """Block bedroom steal only when origin is about to resume (sustained committed presence)."""
        return (
            self._origin_resume_streak.get(origin_id, 0) >= PRESENCE_RESUME_STREAK
        )

    def _away_streak_reached(self, room_id: str) -> bool:
        self._away_streak[room_id] = self._away_streak.get(room_id, 0) + 1
        return self._away_streak[room_id] >= AWAY_ENTER_STREAK

    def _presence_streak_reached(self, room_id: str, *, threshold: int) -> bool:
        self._presence_streak[room_id] = self._presence_streak.get(room_id, 0) + 1
        for rid in list(self._presence_streak.keys()):
            if rid != room_id:
                self._presence_streak[rid] = 0
        return self._presence_streak[room_id] >= threshold

    def _cross_room_streak_reached(self, room_id: str, *, threshold: int) -> bool:
        """Presence streak for stealing focus — never reset by other rooms' snapshots."""
        self._cross_room_streak[room_id] = self._cross_room_streak.get(room_id, 0) + 1
        return self._cross_room_streak[room_id] >= threshold

    def _origin_resume_streak_reached(self, room_id: str) -> bool:
        self._origin_resume_streak[room_id] = (
            self._origin_resume_streak.get(room_id, 0) + 1
        )
        return self._origin_resume_streak[room_id] >= PRESENCE_RESUME_STREAK

    def _active_room_still_occupied(self) -> bool:
        """True when the focused room's latest read indicates someone is present."""
        active_id = self.active_room_id
        if not active_id:
            return False
        last_snap = self._last_snap_by_room.get(active_id)
        if last_snap is not None and _snap_suggests_presence(last_snap):
            return True
        label = str(self._last_label_by_room.get(active_id, "")).strip()
        return label not in ("", "away", "unknown")

    def _cross_room_promote_allowed(self, *, during_grace: bool) -> bool:
        if during_grace:
            return True
        if self._last_promote_monotonic <= 0:
            return True
        return (time.monotonic() - self._last_promote_monotonic) >= PROMOTE_COOLDOWN_SEC

    def _try_cross_room_promote(self, room_id: str, snap: "LiveSnapshot") -> None:
        """Promote another room during grace when it shows sustained presence."""
        during_grace = self.mode == "grace"
        if during_grace and self._active_room_label_blocks_cross_promote():
            self._cross_room_streak[room_id] = 0
            return
        if not during_grace and not self._active_room_committed_empty():
            self._cross_room_streak[room_id] = 0
            return
        origin = self._grace_origin_room_id
        if origin and origin != room_id and self._origin_blocks_cross_room_promote(origin):
            self._cross_room_streak[room_id] = 0
            return
        if not self._cross_room_promote_allowed(during_grace=during_grace):
            return
        label = str(snap.primary_state or "")
        if _snap_confident_ml_presence(snap) and self._cross_room_streak_reached(
            room_id, threshold=GRACE_CROSS_ROOM_PROMOTE_STREAK
        ):
            self._reset_presence_streaks()
            mood = label or self._last_mood_by_room.get(room_id, "work")
            self._promote_room(room_id, mood=mood)
        elif not _snap_confident_ml_presence(snap):
            self._cross_room_streak[room_id] = 0

    def _maybe_active_mode_handoff(self, room_id: str, snap: "LiveSnapshot") -> None:
        """User moved to another room while live — hand off without a grace detour."""
        if not self._active_room_committed_empty():
            self._cross_room_streak[room_id] = 0
            return
        if not self._cross_room_promote_allowed(during_grace=False):
            return
        label = str(snap.primary_state or "")
        if _snap_confident_ml_presence(snap) and self._cross_room_streak_reached(
            room_id, threshold=ACTIVE_MODE_HANDOFF_STREAK
        ):
            self._reset_presence_streaks()
            mood = label or self._last_mood_by_room.get(room_id, "work")
            self._promote_room(room_id, mood=mood)
        elif not _snap_confident_ml_presence(snap):
            self._cross_room_streak[room_id] = 0

    def _all_enabled_rooms_away(self) -> bool:
        """Global away only when every enabled room's latest ML read is away."""
        doc = self._store.document()
        enabled = doc.enabled_rooms()
        if not enabled:
            return True
        for room in enabled:
            label = str(self._last_label_by_room.get(room.id, "")).strip()
            if label != "away":
                return False
        return True

    def _notify_mode_changed(self, mode: str) -> None:
        if self._on_mode_changed is not None:
            try:
                self._on_mode_changed(mode)
            except Exception as e:
                log.warning("Orchestrator mode hook failed: %s", e)

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
        # Low-FPS preview threads are only used while live inference is off.
        if self._preview is not None and not self._inference_room_ids:
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
            self._last_snap_by_room[room_id] = snap
            self._last_label_by_room[room_id] = label
            self._track_active_empty_streak(room_id, label)
            if room_id == self.active_room_id:
                self._last_primary_state = label

            if mode == "away":
                self._try_wake_from_global_away(room_id, snap)
                return

            if mode == "grace" and room_id != self.active_room_id:
                if label and label not in ("away", "unknown"):
                    self._last_mood_by_room[room_id] = label
                self._try_cross_room_promote(room_id, snap)
                return

            if mode == "grace" and room_id == self.active_room_id:
                if _snap_suggests_presence(snap) and self._origin_resume_streak_reached(
                    room_id
                ):
                    self._reset_presence_streaks()
                    fallback = self._last_mood_by_room.get(room_id, "work")
                    resume_mood = _resume_mood_from_snapshot(snap, fallback=fallback)
                    self._resume_from_grace(room_id, resume_mood)
                elif not _snap_suggests_presence(snap):
                    self._origin_resume_streak[room_id] = 0
                return

            if mode == "active" and room_id == self.active_room_id:
                if label == "away":
                    if _snap_suggests_presence(snap):
                        self._away_streak[room_id] = 0
                        return
                    if self._away_streak_reached(room_id):
                        self._away_streak[room_id] = 0
                        self._enter_grace(room_id)
                    return
                self._away_streak[room_id] = 0
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

            if label and label not in ("away", "unknown"):
                self._last_mood_by_room[room_id] = label
            if mode == "active" and room_id != self.active_room_id:
                self._maybe_active_mode_handoff(room_id, snap)

    def _try_wake_from_global_away(self, room_id: str, snap: "LiveSnapshot") -> None:
        """Leave global away when one room shows sustained presence and others stay away."""
        if not self._cross_room_promote_allowed(during_grace=False):
            return
        label = str(snap.primary_state or "")
        if not _snap_confident_ml_presence(snap):
            self._cross_room_streak[room_id] = 0
            return
        doc = self._store.document()
        for room in doc.enabled_rooms():
            if room.id == room_id:
                continue
            other_label = str(self._last_label_by_room.get(room.id, "")).strip()
            if other_label not in ("", "away", "unknown"):
                self._cross_room_streak[room_id] = 0
                return
        if self._cross_room_streak_reached(
            room_id, threshold=GRACE_CROSS_ROOM_PROMOTE_STREAK
        ):
            self._reset_presence_streaks()
            mood = label or self._last_mood_by_room.get(room_id, "work")
            self._promote_room(room_id, mood=mood)

    def _enter_grace(self, from_room_id: str) -> None:
        log.info("Room %s away — entering grace period", from_room_id)
        self._reset_presence_streaks()
        self._grace_origin_room_id = from_room_id
        restore_mood = self._last_mood_by_room.get(from_room_id, "work")
        if restore_mood and restore_mood != "away":
            self._pending_mood_restore[from_room_id] = restore_mood
        self._store.update_orchestrator(mode="grace", grace_started_at=_now_iso())
        # Grace: lights stay as-is on the vacated room; plugs/thermostats use away prefs.
        self._apply_grace_origin_away_devices(from_room_id)
        # Dim walkway lights only (other rooms) — never touch plugs there.
        self._apply_walkway_lights(exclude_room_id=from_room_id)
        self._start_grace_scanner(from_room_id)
        self._notify_mode_changed("grace")

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
        self._reset_presence_streaks()
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
        self._notify_mode_changed("active")

    def _enter_global_away(self) -> None:
        log.info(
            "Grace expired with all rooms away — global away (devices off, cameras stay on)"
        )
        self._grace_origin_room_id = None
        self._stop_grace_scanner()
        self._store.update_orchestrator(mode="away", grace_started_at=None)
        self._apply_all_devices_off()
        self._reset_presence_streaks()
        self._notify_mode_changed("away")

    def _promote_room(self, room_id: str, *, mood: Optional[str] = None) -> None:
        if self.active_room_id == room_id and self.mode == "active":
            return
        log.info("Presence detected in room %s — becoming active", room_id)
        self._last_promote_monotonic = time.monotonic()
        self._grace_origin_room_id = None
        self._stop_grace_scanner()
        self._store.set_active_room_id(room_id)
        self._store.update_orchestrator(mode="active", grace_started_at=None)
        self.set_inference_room(room_id)
        resume_mood = str(mood or "").strip() or self._last_mood_by_room.get(room_id, "work")
        if resume_mood == "away":
            resume_mood = "work"
        self._last_mood_by_room[room_id] = resume_mood
        self._pending_mood_restore.pop(room_id, None)
        self._apply_active_room_mood(
            room_id,
            resume_mood,
            action_source=ActionSource.ORCHESTRATOR_RESUME,
        )
        self._turn_off_non_active_devices(room_id)
        if self._on_active_room_changed is not None:
            try:
                self._on_active_room_changed(room_id)
            except Exception as e:
                log.warning("Active room changed hook failed: %s", e)
        self._notify_mode_changed("active")

    def _start_grace_scanner(self, exclude_room_id: str) -> None:
        self._stop_grace_scanner()
        self._grace_stop.clear()

        def _run() -> None:
            doc = self._store.document()
            grace_sec = doc.orchestrator.grace_duration_sec
            started = time.monotonic()
            while not self._grace_stop.is_set():
                if time.monotonic() - started >= grace_sec:
                    if self._all_enabled_rooms_away():
                        self._enter_global_away()
                        return
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

    def _apply_grace_origin_away_devices(self, from_room_id: str) -> None:
        """Turn off plugs/thermostats on the vacated room; leave lights unchanged."""
        from ..devices.scene_apply import (
            apply_grace_origin_away_devices_async,
            resolve_apply_scene_for_mood,
        )

        room = self._store.get_room(from_room_id)
        if room is None or not room.device_ids:
            return
        scene = resolve_apply_scene_for_mood("away")
        try:
            asyncio.run(
                apply_grace_origin_away_devices_async(
                    list(room.device_ids),
                    scene=scene,
                    dry_run=self._dry_run(),
                    integrations=self._integrations(),
                    room_id=from_room_id,
                )
            )
        except Exception as e:
            log.warning("Grace origin away devices failed: %s", e)

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
                    "inferenceActive": room.id in self._inference_room_ids,
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
