"""Smart plug action — uses brand + credentials from Settings (integrations.json)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..devices.smart_plug import apply_smart_plug_state
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

            result = asyncio.run(apply_smart_plug_state(self.integration, state))
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
