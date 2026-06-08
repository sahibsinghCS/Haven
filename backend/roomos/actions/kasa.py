"""Direct TP-Link Kasa smart plug control (no Home Assistant)."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional, Tuple

from ..utils.logging import get_logger
from .rules import ActionEvent, ActionHandler

log = get_logger("roomos.actions.kasa")


def resolve_kasa_host(integration: Dict[str, Any], *, action_host: str = "") -> str:
    direct = str(action_host or integration.get("host") or "").strip()
    if direct:
        return direct
    env_key = integration.get("host_env")
    if env_key:
        return os.environ.get(str(env_key), "").strip()
    return ""


def resolve_kasa_credentials(integration: Dict[str, Any]) -> Tuple[str, str]:
    user = str(integration.get("username") or "").strip()
    password = str(integration.get("password") or "").strip()
    user_env = integration.get("username_env")
    pass_env = integration.get("password_env")
    if user_env and not user:
        user = os.environ.get(str(user_env), "").strip()
    if pass_env and not password:
        password = os.environ.get(str(pass_env), "").strip()
    return user, password


async def apply_kasa_state(
    host: str,
    state: str,
    *,
    username: str = "",
    password: str = "",
    timeout_sec: float = 8.0,
) -> Dict[str, Any]:
    """Turn a Kasa plug on or off at ``host`` (local LAN)."""
    from kasa import Credentials, Discover

    normalized = str(state or "").strip().lower()
    if normalized not in ("on", "off"):
        raise ValueError(f"kasa state must be 'on' or 'off', got {state!r}")

    credentials = None
    if username and password:
        credentials = Credentials(username, password)

    device = await asyncio.wait_for(
        Discover.discover_single(host, credentials=credentials),
        timeout=float(timeout_sec),
    )
    await device.update()
    if normalized == "on":
        await device.turn_on()
    else:
        await device.turn_off()

    return {
        "host": host,
        "state": normalized,
        "device": getattr(device, "alias", None) or host,
        "model": getattr(device, "model", None),
    }


class KasaHandler(ActionHandler):
    """Control a Kasa/Tapo Wi-Fi plug on the LAN via python-kasa.

    Requires ``integrations.kasa.enabled: true``, ``dry_run: false``, and
    ``integrations.kasa.host`` (or ``KASA_PLUG_HOST`` env).
    """

    type_name = "kasa"

    def __init__(
        self,
        *,
        state: str = "",
        host: str = "",
        integration: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.state = str(state or "").strip().lower()
        self.host_override = str(host or "").strip()
        self.integration = dict(integration or {})

    def _skipped(self, event: ActionEvent, *, dry_run: bool, reason: str) -> Dict[str, Any]:
        kasa_enabled = bool(self.integration.get("enabled"))
        log.info(
            "[%s] kasa SKIPPED (%s; dry_run=%s kasa_enabled=%s)",
            event.rule_name,
            reason,
            dry_run,
            kasa_enabled,
        )
        return {
            "executed": False,
            "dry_run": dry_run or not kasa_enabled,
            "skipped": True,
            "reason": reason,
            "state": self.state,
            "kasa_enabled": kasa_enabled,
        }

    def execute(self, event: ActionEvent, *, dry_run: bool) -> Dict[str, Any]:
        kasa_enabled = bool(self.integration.get("enabled"))
        host = resolve_kasa_host(self.integration, action_host=self.host_override)
        state = self.state or str(event.payload.get("state") or "").strip().lower()

        if not state:
            return {
                "executed": False,
                "error": "kasa action requires state: on or off",
            }

        if dry_run or not kasa_enabled:
            reason = "dry_run" if dry_run else "integration_disabled"
            body = {"host": host or "?", "state": state}
            log.info(
                "[%s] kasa DRY-RUN would set %s @ %s",
                event.rule_name,
                state,
                body["host"],
            )
            return {
                **self._skipped(event, dry_run=dry_run, reason=reason),
                "would_apply": body,
            }

        if not host:
            return {
                "executed": False,
                "error": "kasa requires integrations.kasa.host or KASA_PLUG_HOST",
            }

        username, password = resolve_kasa_credentials(self.integration)
        timeout_sec = float(self.integration.get("timeout_sec", 8.0))

        try:
            result = asyncio.run(
                apply_kasa_state(
                    host,
                    state,
                    username=username,
                    password=password,
                    timeout_sec=timeout_sec,
                )
            )
            log.info(
                "[%s] kasa -> %s state=%s device=%s",
                event.rule_name,
                host,
                state,
                result.get("device"),
            )
            return {"executed": True, "dry_run": False, **result}
        except Exception as e:
            log.warning("[%s] kasa FAILED %s: %s", event.rule_name, host, e)
            return {"executed": False, "error": str(e), "host": host, "state": state}
