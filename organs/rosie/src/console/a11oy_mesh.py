"""rosie.console.a11oy_mesh — surface a11oy's live state into the console.

Thin glue that uses A11oyClient (the instilled wire) to pull a11oy's live
liveness/readiness and the head of its proof ledger, shaped for the operator
console's a11oy panel. Kept separate from a11oy_client so the transport client
stays a pure SDK and this module owns the console-facing shape.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .a11oy_client import A11oyClient, A11oyError


@dataclass(frozen=True)
class A11oyPanel:
    """Console-facing snapshot of a11oy."""

    reachable: bool
    healthy: bool
    ready: bool
    sha: str | None
    ledger_total: int | None
    recent_receipts: list[dict[str, Any]]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "reachable": self.reachable,
            "healthy": self.healthy,
            "ready": self.ready,
            "sha": self.sha,
            "ledger_total": self.ledger_total,
            "recent_receipts": self.recent_receipts,
            "error": self.error,
        }


def a11oy_panel(client: A11oyClient, recent: int = 5) -> A11oyPanel:
    """Build the console a11oy panel from live a11oy HTTP calls.

    Degrades honestly: if a11oy is unreachable the panel reports
    ``reachable=False`` with the error, rather than fabricating a green state.
    """
    try:
        health = client.health()
    except A11oyError as exc:
        return A11oyPanel(
            reachable=False, healthy=False, ready=False, sha=None,
            ledger_total=None, recent_receipts=[], error=str(exc),
        )

    ready = False
    try:
        ready = client.ready().get("status") == "ready"
    except A11oyError:
        ready = False

    total: int | None = None
    receipts: list[dict[str, Any]] = []
    try:
        page = client.ledger(limit=recent)
        total = page.get("total")
        receipts = page.get("receipts", [])
    except A11oyError:
        pass

    return A11oyPanel(
        reachable=True,
        healthy=health.get("status") == "ok",
        ready=ready,
        sha=health.get("sha"),
        ledger_total=total,
        recent_receipts=receipts,
    )
