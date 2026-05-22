"""Concrete action handlers — kept intentionally safe.

Each handler implements ``execute(event: ActionEvent, *, dry_run: bool)``.
Destructive HA defaults are off; real calls need explicit config (see docs/AUTOMATION.md).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..utils.logging import get_logger

log = get_logger("roomos.actions")


@dataclass
class ActionEvent:
    rule_name: str
    activity: str
    confidence: float
    at: float                 # monotonic seconds
    iso_time: str
    action_type: str
    payload: Dict[str, Any]


class ActionHandler(ABC):
    type_name: str = ""

    @abstractmethod
    def execute(self, event: ActionEvent, *, dry_run: bool) -> Dict[str, Any]:
        """Return a small dict describing what was done (for logging)."""


class LogHandler(ActionHandler):
    type_name = "log"

    def __init__(self, message: str = "") -> None:
        self.message = message

    def execute(self, event: ActionEvent, *, dry_run: bool) -> Dict[str, Any]:
        msg = self.message or f"action triggered: rule={event.rule_name} activity={event.activity}"
        log.info("[%s] %s (conf=%.2f, dry_run=%s)", event.rule_name, msg, event.confidence, dry_run)
        return {"executed": True, "dry_run": dry_run, "message": msg}


class WebhookHandler(ActionHandler):
    """POST JSON to any URL (local demo receiver, Zapier, etc.). Skipped when dry_run."""

    type_name = "webhook"

    def __init__(self, url: str, method: str = "POST", timeout_sec: float = 4.0) -> None:
        if not url:
            raise ValueError("webhook handler requires a url")
        self.url = url
        self.method = (method or "POST").upper()
        self.timeout_sec = float(timeout_sec)

    def execute(self, event: ActionEvent, *, dry_run: bool) -> Dict[str, Any]:
        body = {
            "source": "roomos",
            "rule": event.rule_name,
            "activity": event.activity,
            "confidence": round(float(event.confidence), 4),
            "at": event.iso_time,
        }
        if dry_run:
            log.info(
                "[%s] webhook DRY-RUN would %s %s payload=%s",
                event.rule_name,
                self.method,
                self.url,
                body,
            )
            return {
                "executed": False,
                "dry_run": True,
                "skipped": True,
                "reason": "dry_run",
                "url": self.url,
                "method": self.method,
                "body": body,
            }

        try:
            from .integrations import post_json

            result = post_json(
                url=self.url,
                body=body,
                method=self.method,
                timeout_sec=self.timeout_sec,
            )
            log.info(
                "[%s] webhook -> %s %s status=%s",
                event.rule_name,
                self.method,
                self.url,
                result.get("status"),
            )
            return {
                "executed": True,
                "dry_run": False,
                "url": self.url,
                "method": self.method,
                **result,
            }
        except Exception as e:
            log.warning("[%s] webhook FAILED %s: %s", event.rule_name, self.url, e)
            return {"executed": False, "error": str(e), "url": self.url, "method": self.method}


_HANDLERS: Dict[str, type[ActionHandler]] = {
    LogHandler.type_name: LogHandler,
    WebhookHandler.type_name: WebhookHandler,
}


def build_handler(
    action_cfg: Dict[str, Any],
    *,
    integrations: Optional[Dict[str, Any]] = None,
) -> ActionHandler:
    """Instantiate a handler from its ``action:`` YAML block."""
    type_name = str(action_cfg.get("type", "log"))
    kwargs = {k: v for k, v in action_cfg.items() if k != "type"}
    if type_name == "home_assistant":
        from .home_assistant import HomeAssistantHandler

        ha = (integrations or {}).get("home_assistant") if integrations else {}
        kwargs["integration"] = dict(ha) if isinstance(ha, dict) else {}
        return HomeAssistantHandler(**kwargs)
    cls = _HANDLERS.get(type_name)
    if cls is None:
        known = sorted(_HANDLERS) + ["home_assistant"]
        raise ValueError(f"Unknown action type: {type_name!r}. Known: {known}")
    return cls(**kwargs)
