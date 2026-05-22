"""Configurable rule engine."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.io import append_jsonl
from ..utils.logging import get_logger
from .rules import ActionEvent, ActionHandler, build_handler

log = get_logger("roomos.actions.engine")


def _automation_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    """Compact payload for live UI + logs."""
    result = dict(record.get("result") or {})
    executed = bool(result.get("executed"))
    skipped = bool(result.get("skipped")) or bool(result.get("dry_run")) and not executed
    summary = result.get("message") or result.get("error") or result.get("target") or result.get("url")
    if not summary and record.get("action_type") == "home_assistant":
        summary = result.get("mode", "home_assistant")
    if skipped and record.get("dry_run"):
        summary = f"Dry-run: would run {record.get('action_type')} ({record.get('rule')})"
    elif skipped:
        summary = f"Skipped: {result.get('reason', 'disabled')}"
    elif executed:
        summary = f"Sent {record.get('action_type')} ({record.get('rule')})"
    else:
        summary = f"Failed: {result.get('error', 'unknown')}"
    return {
        "at": record.get("t"),
        "rule": record.get("rule"),
        "activity": record.get("activity"),
        "actionType": record.get("action_type"),
        "dryRun": bool(record.get("dry_run")),
        "executed": executed,
        "skipped": skipped,
        "summary": str(summary),
    }


@dataclass
class ActionRule:
    name: str
    activity: str
    min_confidence: float
    sustain_windows: int
    cooldown_sec: float
    handler: ActionHandler
    enabled: bool = True
    raw_action_cfg: Dict[str, Any] = field(default_factory=dict)
    _consecutive: int = 0
    _last_fired_at: float = 0.0

    def step(self, label: str, confidence: float, now: float) -> Optional[ActionEvent]:
        if not self.enabled:
            return None
        if label != self.activity or confidence < self.min_confidence:
            self._consecutive = 0
            return None
        # While we're inside the cooldown after a previous fire, refuse to
        # accumulate sustain windows — the next eligible fire must be backed
        # by a *fresh* sustain stretch after the cooldown elapses.
        if self._last_fired_at and (now - self._last_fired_at) < self.cooldown_sec:
            self._consecutive = 0
            return None
        self._consecutive += 1
        if self._consecutive < self.sustain_windows:
            return None
        self._last_fired_at = now
        self._consecutive = 0
        iso = datetime.now(timezone.utc).isoformat()
        return ActionEvent(
            rule_name=self.name,
            activity=self.activity,
            confidence=confidence,
            at=now,
            iso_time=iso,
            action_type=str(self.raw_action_cfg.get("type", "log")),
            payload=dict(self.raw_action_cfg),
        )


class ActionEngine:
    def __init__(
        self,
        rules: List[ActionRule],
        *,
        dry_run: bool = True,
        events_log: Optional[Path] = None,
        integrations: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.rules = rules
        self.dry_run = bool(dry_run)
        self.events_log = Path(events_log) if events_log else None
        self.integrations = dict(integrations or {})
        self.last_automation: Optional[Dict[str, Any]] = None

    # --- factory -------------------------------------------------------

    @classmethod
    def from_config(cls, cfg: Config) -> "ActionEngine":
        ac = cfg.actions
        integrations = dict(ac.get("integrations", {}) or {})
        defaults = {
            "min_confidence": float(ac.get("default_min_confidence", 0.55)),
            "sustain_windows": int(ac.get("default_sustain_windows", 3)),
            "cooldown_sec": float(ac.get("default_cooldown_sec", 60.0)),
        }
        rules: List[ActionRule] = []
        for raw in list(ac.get("rules", [])):
            when = dict(raw.get("when", {}))
            activity = str(when.get("activity"))
            if not activity:
                log.warning("Skipping action rule with no 'when.activity': %s", raw)
                continue
            action_cfg = dict(raw.get("action", {"type": "log"}))
            try:
                handler = build_handler(action_cfg, integrations=integrations)
            except Exception as e:
                log.warning("Skipping rule %s: handler build failed (%s)", raw.get("name"), e)
                continue
            rules.append(
                ActionRule(
                    name=str(raw.get("name", f"rule_{len(rules)}")),
                    activity=activity,
                    min_confidence=float(when.get("min_confidence", defaults["min_confidence"])),
                    sustain_windows=int(when.get("sustain_windows", defaults["sustain_windows"])),
                    cooldown_sec=float(raw.get("cooldown_sec", defaults["cooldown_sec"])),
                    handler=handler,
                    enabled=bool(raw.get("enabled", True)),
                    raw_action_cfg=action_cfg,
                )
            )
        events_log_raw = ac.get("events_log", "data/events/actions.jsonl")
        events_log: Optional[Path]
        if events_log_raw in (None, ""):
            events_log = None
        else:
            events_log = Path(events_log_raw)
            if not events_log.is_absolute() and cfg.project_root is not None:
                events_log = cfg.project_root / events_log
        ha = integrations.get("home_assistant") or {}
        log.info(
            "Action engine: %d rules, dry_run=%s, home_assistant.enabled=%s",
            len(rules),
            bool(ac.get("dry_run", True)),
            bool(ha.get("enabled")) if isinstance(ha, dict) else False,
        )
        return cls(
            rules=rules,
            dry_run=bool(ac.get("dry_run", True)),
            events_log=events_log,
            integrations=integrations,
        )

    # --- per-prediction hook ------------------------------------------

    def on_prediction(self, *, label: str, confidence: float, at: Optional[float] = None) -> List[Dict[str, Any]]:
        """Evaluate all rules against a single smoothed prediction."""
        now = at if at is not None else time.monotonic()
        fired: List[Dict[str, Any]] = []
        for rule in self.rules:
            event = rule.step(label, confidence, now)
            if event is None:
                continue
            try:
                result = rule.handler.execute(event, dry_run=self.dry_run)
            except Exception as e:
                log.warning("Handler for rule=%s failed: %s", rule.name, e)
                result = {"executed": False, "error": str(e)}
            record = {
                "t": event.iso_time,
                "rule": event.rule_name,
                "activity": event.activity,
                "confidence": event.confidence,
                "action_type": event.action_type,
                "dry_run": self.dry_run,
                "result": result,
            }
            fired.append(record)
            self.last_automation = _automation_summary(record)
            if self.events_log:
                try:
                    append_jsonl(self.events_log, record)
                except Exception as e:
                    log.debug("Failed to write event log: %s", e)
        return fired
