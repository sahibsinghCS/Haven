"""Home Assistant webhook + REST service actions."""

from __future__ import annotations

from typing import Any, Dict

from ..utils.logging import get_logger
from .integrations import fire_home_assistant_service, fire_home_assistant_webhook
from .rules import ActionEvent, ActionHandler

log = get_logger("roomos.actions.home_assistant")


class HomeAssistantHandler(ActionHandler):
    """Call Home Assistant via webhook trigger or REST ``/api/services/...``.

    Real calls require **both** ``actions.dry_run: false`` and
    ``integrations.home_assistant.enabled: true``.
    """

    type_name = "home_assistant"

    def __init__(
        self,
        *,
        mode: str = "webhook",
        webhook_id: str = "",
        domain: str = "",
        service: str = "",
        entity_id: str = "",
        data: Dict[str, Any] | None = None,
        integration: Dict[str, Any] | None = None,
    ) -> None:
        self.mode = (mode or "webhook").strip().lower()
        self.webhook_id = str(webhook_id or "").strip()
        self.domain = str(domain or "").strip()
        self.service = str(service or "").strip()
        self.entity_id = str(entity_id or "").strip()
        self.data = dict(data or {})
        self.integration = dict(integration or {})

    def _skipped(self, event: ActionEvent, *, dry_run: bool, reason: str) -> Dict[str, Any]:
        ha_enabled = bool(self.integration.get("enabled"))
        log.info(
            "[%s] home_assistant %s SKIPPED (%s; dry_run=%s ha_enabled=%s)",
            event.rule_name,
            self.mode,
            reason,
            dry_run,
            ha_enabled,
        )
        return {
            "executed": False,
            "dry_run": dry_run or not ha_enabled,
            "skipped": True,
            "reason": reason,
            "mode": self.mode,
            "ha_enabled": ha_enabled,
        }

    def execute(self, event: ActionEvent, *, dry_run: bool) -> Dict[str, Any]:
        ha_enabled = bool(self.integration.get("enabled"))
        if dry_run or not ha_enabled:
            reason = "dry_run" if dry_run else "integration_disabled"
            body = self._event_body(event)
            log.info(
                "[%s] home_assistant DRY-RUN would %s %s payload=%s",
                event.rule_name,
                self.mode,
                self._target_label(),
                body,
            )
            return {
                **self._skipped(event, dry_run=dry_run, reason=reason),
                "would_send": body,
                "target": self._target_label(),
            }

        try:
            if self.mode == "webhook":
                wid = self.webhook_id or str(self.integration.get("default_webhook_id") or "").strip()
                if not wid:
                    raise ValueError("home_assistant webhook mode requires webhook_id on the rule")
                return fire_home_assistant_webhook(
                    self.integration,
                    webhook_id=wid,
                    body=self._event_body(event),
                    rule_name=event.rule_name,
                )
            if self.mode == "service":
                if not self.domain or not self.service:
                    raise ValueError("home_assistant service mode requires domain and service")
                payload = dict(self.data)
                if self.entity_id and "entity_id" not in payload:
                    payload["entity_id"] = self.entity_id
                return fire_home_assistant_service(
                    self.integration,
                    domain=self.domain,
                    service=self.service,
                    data=payload,
                    rule_name=event.rule_name,
                )
            raise ValueError(f"Unknown home_assistant mode: {self.mode!r} (use webhook or service)")
        except Exception as e:
            log.warning("[%s] home_assistant FAILED: %s", event.rule_name, e)
            return {"executed": False, "error": str(e), "mode": self.mode}

    def _event_body(self, event: ActionEvent) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "source": "roomos",
            "rule": event.rule_name,
            "activity": event.activity,
            "confidence": round(float(event.confidence), 4),
            "at": event.iso_time,
        }
        body.update(self.data)
        return body

    def _target_label(self) -> str:
        if self.mode == "webhook":
            wid = self.webhook_id or self.integration.get("default_webhook_id") or "?"
            base = self.integration.get("base_url", "http://127.0.0.1:8123")
            return f"webhook {base}/api/webhook/{wid}"
        return f"service {self.domain}.{self.service}"
