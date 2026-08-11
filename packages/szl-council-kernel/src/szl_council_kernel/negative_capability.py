from __future__ import annotations

"""Negative Capability Ledger guard used by the router before attempted work."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .errors import AuthorizationError
from .state_bus import StateBus


@dataclass(frozen=True, slots=True)
class NegativeCapabilityDecision:
    allowed: bool
    blockers: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "szl.negative-capability-decision/v1",
            "allowed": self.allowed,
            "blockers": [dict(item) for item in self.blockers],
        }


class NegativeCapabilityGuard:
    def __init__(self, bus: StateBus) -> None:
        self.bus = bus

    def evaluate(
        self,
        *,
        task_class: str,
        tool: str | None = None,
        domain: str | None = None,
        now: str | datetime | None = None,
    ) -> NegativeCapabilityDecision:
        blockers = tuple(
            self.bus.query_negative_capabilities(
                task_class=task_class, tool=tool, domain=domain, now=now
            )
        )
        return NegativeCapabilityDecision(allowed=not blockers, blockers=blockers)

    def require_allowed(
        self,
        *,
        task_class: str,
        tool: str | None = None,
        domain: str | None = None,
        now: str | datetime | None = None,
    ) -> None:
        decision = self.evaluate(task_class=task_class, tool=tool, domain=domain, now=now)
        if not decision.allowed:
            codes = sorted({item["condition_code"] for item in decision.blockers})
            raise AuthorizationError("negative capability ledger blocks task: " + ",".join(codes))
