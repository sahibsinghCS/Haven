"""Smart plug action — uses brand + credentials from Settings (integrations.json)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..devices.action_arbiter import ActionSource
from ..devices.command_gateway import gateway_apply_plug
from ..utils.logging import get_logger
from .rules import ActionEvent, ActionHandler

log = get_logger("roomos.actions.smart_plug")


class SmartPlugHandler(ActionHandler):
    type_name = "smart_plug"

    def __init__(
        self,
        *,
        state: str = "",
        integration: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.state = str(state or "").strip().lower()
        self.integration = dict(integration or {})

    def execute(self, event: ActionEvent, *, dry_run: bool) -> Dict[str, Any]:
        enabled = bool(self.integration.get("enabled"))
        state = self.state or str(event.payload.get("state") or "").strip().lower()
        brand = self.integration.get("brand", "?")

        if not state:
            return {"executed": False, "error": "smart_plug action requires state: on or off"}

        if dry_run or not enabled:
            log.info(
                "[%s] smart_plug DRY-RUN brand=%s state=%s (dry_run=%s enabled=%s)",
                event.rule_name,
                brand,
                state,
                dry_run,
                enabled,
            )
            return {
                "executed": False,
                "dry_run": True,
                "skipped": True,
                "reason": "dry_run" if dry_run else "integration_disabled",
                "brand": brand,
                "state": state,
            }

        try:
            import asyncio

            device_id = str(
                self.integration.get("id")
                or self.integration.get("deviceId")
                or self.integration.get("host")
                or ""
            )
            result = asyncio.run(
                gateway_apply_plug(
                    self.integration,
                    state,
                    source=ActionSource.AUTOMATION_RULE,
                    device_id=device_id,
                    dry_run=False,
                    context={"rule": event.rule_name, "activity": event.activity},
                )
            )
            if result.get("skipped"):
                return {
                    "executed": False,
                    "skipped": True,
                    "reason": result.get("reason"),
                    "arbiter": result.get("arbiter"),
                    "brand": brand,
                    "state": state,
                }
            log.info(
                "[%s] smart_plug -> %s %s",
                event.rule_name,
                result.get("brand"),
                result.get("state"),
            )
            return {"executed": True, "dry_run": False, **result}
        except Exception as e:
            log.warning("[%s] smart_plug FAILED: %s", event.rule_name, e)
            return {"executed": False, "error": str(e), "brand": brand, "state": state}
