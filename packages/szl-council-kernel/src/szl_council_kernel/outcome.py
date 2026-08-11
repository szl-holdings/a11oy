from __future__ import annotations

"""Delayed causal outcome contracts and signed settlement payloads."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from .canonical import digest_object, isoformat_utc, utc_now
from .errors import ValidationError
from .models import OutcomeContract


@dataclass(frozen=True, slots=True)
class OutcomeObservation:
    observed_at: str
    value: float
    source_digest: str
    confounder_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_at": self.observed_at,
            "value": self.value,
            "source_digest": self.source_digest,
            "confounder_codes": list(self.confounder_codes),
        }


def settle_outcome_contract(
    contract: OutcomeContract,
    observations: Iterable[OutcomeObservation],
    *,
    cost_usd: float = 0.0,
    opportunity_cost_usd: float = 0.0,
    issued_at: str | datetime | None = None,
) -> dict[str, Any]:
    values = tuple(observations)
    if not values:
        raise ValidationError("outcome settlement requires at least one observation")
    final = values[-1].value
    delta = final - contract.baseline
    attained = {
        "INCREASE": delta > 0,
        "DECREASE": delta < 0,
        "HOLD": delta == 0,
    }[contract.expected_direction]
    stop_loss_triggered = False
    if contract.stop_loss is not None:
        if contract.expected_direction == "INCREASE":
            stop_loss_triggered = final <= contract.stop_loss
        elif contract.expected_direction == "DECREASE":
            stop_loss_triggered = final >= contract.stop_loss
    body = {
        "schema": "szl.outcome-settlement/v1",
        "outcome_id": contract.outcome_id,
        "contract_digest": contract.digest,
        "observations": [item.to_dict() for item in values],
        "final_value": final,
        "delta": delta,
        "target_attained": attained,
        "stop_loss_triggered": stop_loss_triggered,
        "cost_usd": cost_usd,
        "opportunity_cost_usd": opportunity_cost_usd,
        "issued_at": isoformat_utc(issued_at or utc_now()),
    }
    return {**body, "settlement_digest": digest_object(body)}
