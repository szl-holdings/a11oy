"""
yawar_bus — thin HTTP client that publishes Amaru receipts to the platform
yawar-bus (the Prism Bus HTTP surface in `artifacts/api-server`).

If the bus is unreachable, publication is best-effort and logged — chakra
evaluation never silently fails because the bus is down (we surface the
error on the receipt's metadata).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_BUS_URL = os.environ.get(
    "AMARU_YAWAR_BUS_URL", "http://localhost:8080/api/prism-bus/publish"
)
DEFAULT_BUS_TOKEN = os.environ.get("AMARU_YAWAR_BUS_TOKEN", "")
DEFAULT_DOMAIN = os.environ.get("AMARU_YAWAR_BUS_DOMAIN", "amaru")


class YawarBusClient:
    def __init__(
        self,
        *,
        url: str = DEFAULT_BUS_URL,
        token: str = DEFAULT_BUS_TOKEN,
        domain: str = DEFAULT_DOMAIN,
        timeout: float = 2.0,
    ) -> None:
        self._url = url
        self._token = token
        self._domain = domain
        self._timeout = timeout

    async def publish(
        self,
        *,
        type_: str,
        source_id: str,
        payload: dict[str, Any],
        severity: str = "info",
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        body = {
            "type": type_,
            "domain": self._domain,
            "sourceId": source_id,
            "payload": payload,
            "severity": severity,
        }
        if correlation_id:
            body["correlationId"] = correlation_id

        headers = {"content-type": "application/json"}
        if self._token:
            headers["authorization"] = f"Bearer {self._token}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self._url, json=body, headers=headers)
            return {
                "ok": 200 <= resp.status_code < 300,
                "status": resp.status_code,
                "url": self._url,
            }
        except Exception as exc:  # noqa: BLE001 — best-effort publication
            log.warning("yawar_bus.publish_failed url=%s err=%s", self._url, exc)
            return {"ok": False, "status": 0, "url": self._url, "error": str(exc)}


_bus = YawarBusClient()


def get_bus() -> YawarBusClient:
    return _bus
