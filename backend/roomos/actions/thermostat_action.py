"""Thermostat action — heat/cool setpoints from Settings + mood preferences."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..devices.action_arbiter import ActionSource
from ..devices.command_gateway import gateway_apply_thermostat
from ..utils.logging import get_logger
from .rules import ActionEvent, ActionHandler

log = get_logger("roomos.actions.thermostat")


class ThermostatHandler(ActionHandler):
    type_name = "thermostat"

    def __init__(
        self,
        *,
        heat_f: Optional[float] = None,
        cool_f: Optional[float] = None,
        integration: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.heat_f = heat_f
        self.cool_f = cool_f
        self.integration = dict(integration or {})

    def execute(self, event: ActionEvent, *, dry_run: bool) -> Dict[str, Any]:
        enabled = bool(self.integration.get("enabled"))
        heat = self.heat_f
        cool = self.cool_f
        if heat is None and event.payload.get("heat_f") is not None:
            heat = float(event.payload["heat_f"])
        if cool is None and event.payload.get("cool_f") is not None:
            cool = float(event.payload["cool_f"])
        if heat is None:
            heat = self.integration.get("targetHeatF")
            if heat is not None:
                heat = float(heat)
        if cool is None:
            cool = self.integration.get("targetCoolF")
            if cool is not None:
                cool = float(cool)

        brand = self.integration.get("brand", "?")

        if dry_run or not enabled:
            return {
                "executed": False,
                "dry_run": True,
                "skipped": True,
                "reason": "dry_run" if dry_run else "integration_disabled",
                "brand": brand,
                "heat_f": heat,
                "cool_f": cool,
            }

        if heat is None and cool is None:
            return {"executed": False, "error": "thermostat action needs heat_f or cool_f"}

        try:
            import asyncio

            device_id = str(
                self.integration.get("id")
                or self.integration.get("deviceId")
                or "thermostat"
            )
            result = asyncio.run(
                gateway_apply_thermostat(
                    self.integration,
                    source=ActionSource.AUTOMATION_RULE,
                    device_id=device_id,
                    heat_f=heat,
                    cool_f=cool,
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
                }
            return {"executed": True, "dry_run": False, **result}
        except Exception as e:
            log.warning("[%s] thermostat FAILED: %s", event.rule_name, e)
            return {"executed": False, "error": str(e), "brand": brand}
