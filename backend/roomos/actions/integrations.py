"""Outbound integrations for room automation (demo-safe)."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..utils.logging import get_logger

log = get_logger("roomos.actions.integrations")


def home_assistant_settings(integrations: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalized Home Assistant block from ``actions.integrations``."""
    raw = (integrations or {}).get("home_assistant") or {}
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def resolve_ha_token(ha: Dict[str, Any]) -> str:
    direct = str(ha.get("token") or "").strip()
    if direct:
        return direct
    env_key = ha.get("token_env")
    if env_key:
        return os.environ.get(str(env_key), "").strip()
    return ""


def ha_webhook_url(base_url: str, webhook_id: str) -> str:
    base = str(base_url).rstrip("/")
    wid = str(webhook_id).strip().strip("/")
    if not base or not wid:
        raise ValueError("home_assistant webhook requires base_url and webhook_id")
    return f"{base}/api/webhook/{wid}"


def ha_service_url(base_url: str, domain: str, service: str) -> str:
    base = str(base_url).rstrip("/")
    return f"{base}/api/services/{domain.strip()}/{service.strip()}"


def post_json(
    *,
    url: str,
    body: Dict[str, Any],
    method: str = "POST",
    timeout_sec: float = 8.0,
    headers: Optional[Dict[str, str]] = None,
    verify_ssl: bool = True,
) -> Dict[str, Any]:
    """POST JSON via httpx; returns small result dict for action logs."""
    import httpx

    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    with httpx.Client(timeout=float(timeout_sec), verify=bool(verify_ssl)) as cli:
        resp = cli.request(method.upper(), url, json=body, headers=hdrs)
    return {"status": int(resp.status_code), "ok": resp.is_success}


def fire_home_assistant_webhook(
    ha: Dict[str, Any],
    *,
    webhook_id: str,
    body: Dict[str, Any],
    rule_name: str,
) -> Dict[str, Any]:
    url = ha_webhook_url(str(ha.get("base_url", "http://127.0.0.1:8123")), webhook_id)
    result = post_json(
        url=url,
        body=body,
        timeout_sec=float(ha.get("timeout_sec", 8.0)),
        verify_ssl=bool(ha.get("verify_ssl", True)),
    )
    log.info(
        "[%s] home_assistant webhook -> %s status=%s",
        rule_name,
        url,
        result.get("status"),
    )
    return {"executed": True, "dry_run": False, "mode": "webhook", "url": url, **result}


def fire_home_assistant_service(
    ha: Dict[str, Any],
    *,
    domain: str,
    service: str,
    data: Dict[str, Any],
    rule_name: str,
) -> Dict[str, Any]:
    token = resolve_ha_token(ha)
    if not token:
        raise ValueError(
            "home_assistant service mode requires token or token_env "
            "(long-lived access token from Home Assistant profile)."
        )
    url = ha_service_url(str(ha.get("base_url", "http://127.0.0.1:8123")), domain, service)
    result = post_json(
        url=url,
        body=data,
        timeout_sec=float(ha.get("timeout_sec", 8.0)),
        verify_ssl=bool(ha.get("verify_ssl", True)),
        headers={"Authorization": f"Bearer {token}"},
    )
    log.info(
        "[%s] home_assistant service %s.%s -> %s status=%s",
        rule_name,
        domain,
        service,
        url,
        result.get("status"),
    )
    return {
        "executed": True,
        "dry_run": False,
        "mode": "service",
        "domain": domain,
        "service": service,
        **result,
    }
