from __future__ import annotations

"""Empirical ACT / ESCALATE / BLOCK release gate.

This reference implementation deliberately does not claim conformal or formal
coverage. It combines deterministic policy stops with a Wilson upper bound over
historical false-green observations and a transparent weighted risk score.
"""

import math
from datetime import datetime
from typing import Iterable, Mapping

from .canonical import isoformat_utc, utc_now
from .enums import CouncilState, ReleaseDecision, RiskClass
from .errors import ValidationError
from .models import GateInput, GateResult


def wilson_upper(failures: int, total: int, *, z: float = 1.959963984540054) -> float:
    if isinstance(failures, bool) or not isinstance(failures, int):
        raise ValidationError("Wilson failures must be an integer")
    if isinstance(total, bool) or not isinstance(total, int):
        raise ValidationError("Wilson total must be an integer")
    if not isinstance(z, (int, float)) or isinstance(z, bool) or not math.isfinite(float(z)) or z <= 0:
        raise ValidationError("Wilson z must be a finite positive number")
    if failures < 0 or total < 0 or failures > total:
        raise ValidationError("Wilson observations require 0 <= failures <= total")
    if total == 0:
        return 1.0
    p = failures / total
    denominator = 1 + z * z / total
    center = p + z * z / (2 * total)
    radius = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return min(1.0, max(0.0, (center + radius) / denominator))


def weighted_risk(value: GateInput) -> float:
    risk_base = {
        RiskClass.LOW: 0.10,
        RiskClass.MEDIUM: 0.28,
        RiskClass.HIGH: 0.60,
        RiskClass.CRITICAL: 0.85,
    }[value.risk_class]
    diversity_penalty = max(0.0, (2.5 - value.effective_diversity) / 2.5)
    incompleteness = 1 - (value.evidence_completeness + value.proof_completeness) / 2
    score = (
        0.22 * risk_base
        + 0.10 * diversity_penalty
        + 0.15 * incompleteness
        + 0.11 * value.novelty_score
        + 0.11 * value.ambiguity_score
        + 0.12 * value.irreversibility_score
        + 0.09 * value.drift_score
        + 0.06 * value.expected_blast_radius
        + 0.04 * value.historical_false_green_rate
    )
    return min(1.0, max(0.0, score))


class EmpiricalReleaseGate:
    def __init__(
        self,
        *,
        act_risk_ceiling: float = 0.24,
        escalate_risk_ceiling: float = 0.58,
        false_green_upper_ceiling: float = 0.12,
        minimum_samples: int = 30,
    ) -> None:
        for name, value in (
            ("act_risk_ceiling", act_risk_ceiling),
            ("escalate_risk_ceiling", escalate_risk_ceiling),
            ("false_green_upper_ceiling", false_green_upper_ceiling),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0 <= float(value) <= 1
            ):
                raise ValidationError(f"{name} must be a finite value in 0..1")
        if float(act_risk_ceiling) > float(escalate_risk_ceiling):
            raise ValidationError("act_risk_ceiling cannot exceed escalate_risk_ceiling")
        if isinstance(minimum_samples, bool) or not isinstance(minimum_samples, int) or minimum_samples < 1:
            raise ValidationError("minimum_samples must be a positive integer")
        self.act_risk_ceiling = float(act_risk_ceiling)
        self.escalate_risk_ceiling = float(escalate_risk_ceiling)
        self.false_green_upper_ceiling = float(false_green_upper_ceiling)
        self.minimum_samples = minimum_samples

    def evaluate(
        self,
        value: GateInput,
        *,
        failures: int | None = None,
        issued_at: str | datetime | None = None,
    ) -> GateResult:
        reasons: list[str] = []
        risk = weighted_risk(value)
        sample_failures = failures
        if sample_failures is None:
            sample_failures = round(
                value.historical_false_green_rate * value.calibration_sample_size
            )
        upper = wilson_upper(sample_failures, value.calibration_sample_size)

        if value.council_state in {
            CouncilState.BLOCKED,
            CouncilState.CONFLICT,
            CouncilState.INSUFFICIENT,
            CouncilState.INVALID,
        }:
            decision = ReleaseDecision.BLOCK
            reasons.append(f"COUNCIL_{value.council_state.value}")
        elif value.council_state == CouncilState.REQUIRE_HUMAN:
            decision = ReleaseDecision.ESCALATE
            reasons.append("COUNCIL_REQUIRES_HUMAN")
        elif value.risk_class in {RiskClass.HIGH, RiskClass.CRITICAL}:
            decision = ReleaseDecision.ESCALATE
            reasons.append("HIGH_RISK_REQUIRES_PRODUCTION_ASSURANCE")
        elif value.calibration_sample_size < self.minimum_samples:
            decision = ReleaseDecision.ESCALATE
            reasons.append("CALIBRATION_SAMPLE_TOO_SMALL")
        elif upper > self.false_green_upper_ceiling:
            decision = ReleaseDecision.ESCALATE
            reasons.append("FALSE_GREEN_UPPER_BOUND_TOO_HIGH")
        elif value.effective_diversity < 2.5:
            decision = ReleaseDecision.ESCALATE
            reasons.append("EFFECTIVE_DIVERSITY_TOO_LOW")
        elif value.novelty_score >= 0.75 or value.drift_score >= 0.65:
            decision = ReleaseDecision.ESCALATE
            reasons.append("NOVEL_OR_DRIFTED_CONTEXT")
        elif value.evidence_completeness < 0.8 or value.proof_completeness < 0.8:
            decision = ReleaseDecision.ESCALATE
            reasons.append("EVIDENCE_OR_PROOF_INCOMPLETE")
        elif risk <= self.act_risk_ceiling:
            decision = ReleaseDecision.ACT
            reasons.append("EMPIRICAL_ENVELOPE_ACCEPTED")
        elif risk <= self.escalate_risk_ceiling:
            decision = ReleaseDecision.ESCALATE
            reasons.append("RISK_SCORE_REQUIRES_REVIEW")
        else:
            decision = ReleaseDecision.BLOCK
            reasons.append("RISK_SCORE_EXCEEDS_BOUND")

        return GateResult(
            decision=decision,
            risk_score=risk,
            empirical_false_green_upper=upper,
            reason_codes=tuple(reasons),
            calibration_method="WILSON_UPPER_PLUS_TRANSPARENT_WEIGHTED_RISK_V1",
            formal_coverage_claimed=False,
            issued_at=isoformat_utc(issued_at or utc_now()),
        )
