"""Concrete action handlers — kept intentionally safe.

Each handler implements ``execute(event: ActionEvent, *, dry_run: bool)``.
No handler in this file performs destructive or irreversible operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

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
    """Optional outgoing webhook. Disabled in dry_run mode."""

    type_name = "webhook"

    def __init__(self, url: str, method: str = "POST", timeout_sec: float = 4.0) -> None:
        if not url:
            raise ValueError("webhook handler requires a url")
        self.url = url
        self.method = (method or "POST").upper()
        self.timeout_sec = float(timeout_sec)

    def execute(self, event: ActionEvent, *, dry_run: bool) -> Dict[str, Any]:
        body = {
            "rule": event.rule_name,
            "activity": event.activity,
            "confidence": event.confidence,
            "at": event.iso_time,
        }
        if dry_run:
            log.info(
                "[%s] webhook DRY-RUN would %s %s payload=%s",
                event.rule_name, self.method, self.url, body,
            )
            return {"executed": False, "dry_run": True, "url": self.url, "method": self.method, "body": body}

        try:
            import httpx

            with httpx.Client(timeout=self.timeout_sec) as cli:
                resp = cli.request(self.method, self.url, json=body)
            log.info(
                "[%s] webhook -> %s %s -> %d",
                event.rule_name, self.method, self.url, resp.status_code,
            )
            return {
                "executed": True,
                "dry_run": False,
                "url": self.url,
                "method": self.method,
                "status": resp.status_code,
            }
        except Exception as e:
            log.warning("[%s] webhook FAILED %s: %s", event.rule_name, self.url, e)
            return {"executed": False, "error": str(e), "url": self.url, "method": self.method}


_HANDLERS: Dict[str, type[ActionHandler]] = {
    LogHandler.type_name: LogHandler,
    WebhookHandler.type_name: WebhookHandler,
}


def build_handler(action_cfg: Dict[str, Any]) -> ActionHandler:
    """Instantiate a handler from its ``action:`` YAML block."""
    type_name = str(action_cfg.get("type", "log"))
    cls = _HANDLERS.get(type_name)
    if cls is None:
        raise ValueError(f"Unknown action type: {type_name!r}. Known: {sorted(_HANDLERS)}")
    kwargs = {k: v for k, v in action_cfg.items() if k != "type"}
    return cls(**kwargs)
