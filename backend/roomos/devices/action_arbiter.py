"""Conflict resolution for device commands (scenes, orchestrator, automation, tests).

Single arbitration point before LAN/cloud device drivers run. Precedence,
per-device cooldown, and duplicate suppression keep preference sync, automation
rules, orchestrator transitions, and manual tests from thrashing hardware.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

from ..utils.logging import get_logger

log = get_logger("roomos.devices.action_arbiter")

# Seconds a higher-priority command blocks conflicting lower-priority ones.
PRIORITY_LOCK_SEC = 15.0

# Default duplicate-suppression windows per source (seconds).
_SOURCE_COOLDOWN: Dict[str, float] = {
    "manual_test": 0.0,
    "orchestrator_resume": 0.0,
    "orchestrator_away": 0.0,
    "orchestrator_grace": 2.0,
    "orchestrator_room": 3.0,
    "preference_sync": 5.0,
    "automation_rule": 10.0,
}


class ActionSource(str, Enum):
    """Who requested a device change (higher ``priority`` wins conflicts)."""

    MANUAL_TEST = "manual_test"
    ORCHESTRATOR_RESUME = "orchestrator_resume"
    ORCHESTRATOR_AWAY = "orchestrator_away"
    ORCHESTRATOR_GRACE = "orchestrator_grace"
    ORCHESTRATOR_ROOM = "orchestrator_room"
    PREFERENCE_SYNC = "preference_sync"
    AUTOMATION_RULE = "automation_rule"


_SOURCE_PRIORITY: Dict[ActionSource, int] = {
    ActionSource.MANUAL_TEST: 100,
    # Restoring room preferences after away/grace must beat the recent all-off.
    ActionSource.ORCHESTRATOR_RESUME: 95,
    ActionSource.ORCHESTRATOR_AWAY: 90,
    ActionSource.ORCHESTRATOR_GRACE: 80,
    ActionSource.ORCHESTRATOR_ROOM: 70,
    ActionSource.PREFERENCE_SYNC: 60,
    ActionSource.AUTOMATION_RULE: 50,
}

# Presence lifecycle sources may preempt each other (leave ↔ return) without the
# 15s priority lock — otherwise a brief grace resume blocks the next away-off.
_LIFECYCLE_SOURCES: frozenset[ActionSource] = frozenset(
    {
        ActionSource.ORCHESTRATOR_RESUME,
        ActionSource.ORCHESTRATOR_AWAY,
        ActionSource.ORCHESTRATOR_GRACE,
    }
)


def source_priority(source: ActionSource) -> int:
    return _SOURCE_PRIORITY.get(source, 0)


def cooldown_for_source(source: ActionSource) -> float:
    return float(_SOURCE_COOLDOWN.get(source.value, 5.0))


def fingerprint_plug(device_id: str, state: str) -> str:
    return f"plug:{device_id}:state:{state.strip().lower()}"


def fingerprint_lights(device_id: str, brightness: int, hex_color: str) -> str:
    color = str(hex_color or "").strip().upper()
    return f"lights:{device_id}:b:{int(brightness)}:c:{color}"


def fingerprint_thermostat(device_id: str, heat_f: Optional[float], cool_f: Optional[float]) -> str:
    h = "none" if heat_f is None else f"{float(heat_f):.1f}"
    c = "none" if cool_f is None else f"{float(cool_f):.1f}"
    return f"thermo:{device_id}:h:{h}:c:{c}"


@dataclass
class DeviceActionIntent:
    """A planned device command before drivers run."""

    source: ActionSource
    device_id: str
    category: str  # smartPlugs | lights | thermostats
    fingerprint: str
    dry_run: bool = False
    context: Dict[str, Any] = field(default_factory=dict)

    @property
    def priority(self) -> int:
        return source_priority(self.source)


@dataclass
class ArbiterDecision:
    """Whether a command may execute and why."""

    allowed: bool
    reason: str
    explanation: str
    source: str
    device_id: str
    fingerprint: str
    priority: int
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "explanation": self.explanation,
            "source": self.source,
            "deviceId": self.device_id,
            "fingerprint": self.fingerprint,
            "priority": self.priority,
            "dryRun": self.dry_run,
        }


@dataclass
class _LastCommand:
    source: ActionSource
    priority: int
    fingerprint: str
    at: float


class DeviceActionArbiter:
    """Thread-safe planner + audit log for device commands."""

    def __init__(self, *, history_limit: int = 100) -> None:
        self._lock = threading.RLock()
        self._last: Dict[str, _LastCommand] = {}
        self._history: Deque[Dict[str, Any]] = deque(maxlen=history_limit)

    def reset(self) -> None:
        with self._lock:
            self._last.clear()
            self._history.clear()

    def plan(self, intent: DeviceActionIntent) -> ArbiterDecision:
        """Decide if ``intent`` should run (does not execute drivers)."""
        now = time.monotonic()
        priority = intent.priority
        source_val = intent.source.value

        if intent.source == ActionSource.MANUAL_TEST:
            decision = ArbiterDecision(
                allowed=True,
                reason="manual_override",
                explanation="Manual test from Settings — always allowed.",
                source=source_val,
                device_id=intent.device_id,
                fingerprint=intent.fingerprint,
                priority=priority,
                dry_run=intent.dry_run,
            )
            self._audit(decision, intent)
            return decision

        if intent.dry_run:
            decision = ArbiterDecision(
                allowed=True,
                reason="dry_run",
                explanation="Dry-run — would apply without sending to device.",
                source=source_val,
                device_id=intent.device_id,
                fingerprint=intent.fingerprint,
                priority=priority,
                dry_run=True,
            )
            self._audit(decision, intent)
            return decision

        cooldown = cooldown_for_source(intent.source)
        last = self._last.get(intent.device_id)

        if last is not None:
            elapsed = now - last.at
            if last.fingerprint == intent.fingerprint and elapsed < cooldown:
                decision = ArbiterDecision(
                    allowed=False,
                    reason="duplicate_suppressed",
                    explanation=(
                        f"Same command for {intent.device_id!r} was applied "
                        f"{elapsed:.1f}s ago (cooldown {cooldown:.0f}s)."
                    ),
                    source=source_val,
                    device_id=intent.device_id,
                    fingerprint=intent.fingerprint,
                    priority=priority,
                )
                self._audit(decision, intent)
                return decision

            lifecycle_handoff = (
                intent.source in _LIFECYCLE_SOURCES
                and last.source in _LIFECYCLE_SOURCES
            )
            if (
                priority < last.priority
                and elapsed < PRIORITY_LOCK_SEC
                and last.fingerprint != intent.fingerprint
                and not lifecycle_handoff
            ):
                decision = ArbiterDecision(
                    allowed=False,
                    reason="preempted_by_higher_priority",
                    explanation=(
                        f"Blocked by recent {last.source.value} command on this device "
                        f"({elapsed:.1f}s ago, lock {PRIORITY_LOCK_SEC:.0f}s)."
                    ),
                    source=source_val,
                    device_id=intent.device_id,
                    fingerprint=intent.fingerprint,
                    priority=priority,
                )
                self._audit(decision, intent)
                return decision

        decision = ArbiterDecision(
            allowed=True,
            reason="allowed",
            explanation=f"Allowed ({source_val}, priority {priority}).",
            source=source_val,
            device_id=intent.device_id,
            fingerprint=intent.fingerprint,
            priority=priority,
        )
        self._audit(decision, intent)
        return decision

    def record_success(self, intent: DeviceActionIntent) -> None:
        """Call after a live (non-dry-run) command succeeds."""
        if intent.dry_run or intent.source == ActionSource.MANUAL_TEST:
            # Manual tests still update last-command for visibility but use
            # zero cooldown so repeat clicks always work.
            pass
        with self._lock:
            self._last[intent.device_id] = _LastCommand(
                source=intent.source,
                priority=intent.priority,
                fingerprint=intent.fingerprint,
                at=time.monotonic(),
            )

    def recent_decisions(self, *, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._history)
        return items[-limit:]

    def _audit(self, decision: ArbiterDecision, intent: DeviceActionIntent) -> None:
        entry = {
            "at": time.time(),
            **decision.to_dict(),
            "category": intent.category,
            "context": dict(intent.context),
        }
        with self._lock:
            self._history.append(entry)
        if decision.allowed:
            log.debug(
                "[arbiter] ALLOW %s %s %s — %s",
                decision.source,
                intent.category,
                intent.device_id,
                decision.explanation,
            )
        else:
            log.info(
                "[arbiter] BLOCK %s %s %s — %s",
                decision.source,
                intent.category,
                intent.device_id,
                decision.explanation,
            )


_arbiter: Optional[DeviceActionArbiter] = None
_arbiter_lock = threading.Lock()


def get_arbiter() -> DeviceActionArbiter:
    global _arbiter
    with _arbiter_lock:
        if _arbiter is None:
            _arbiter = DeviceActionArbiter()
        return _arbiter


def reset_arbiter() -> None:
    """Test helper — clear planner state."""
    get_arbiter().reset()
