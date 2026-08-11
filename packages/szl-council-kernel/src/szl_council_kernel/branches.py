from __future__ import annotations

"""Bounded counterfactual branch market for Ouroboros-style exploration."""

from dataclasses import dataclass
from typing import Iterable, Mapping

from .models import AutonomyEnvelope, BranchCandidate

DEFAULT_WEIGHTS = {
    "utility": 1.0,
    "risk": 1.2,
    "cost": 0.6,
    "latency": 0.4,
    "proof": 0.9,
    "diversity": 0.5,
    "novelty": 0.8,
}


@dataclass(frozen=True, slots=True)
class RankedBranch:
    branch: BranchCandidate
    score: float
    eligible: bool
    elimination_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "branch": self.branch.to_dict(),
            "score": round(self.score, 6),
            "eligible": self.eligible,
            "elimination_reasons": list(self.elimination_reasons),
        }


def branch_score(branch: BranchCandidate, weights: Mapping[str, float] | None = None) -> float:
    w = {**DEFAULT_WEIGHTS, **dict(weights or {})}
    return (
        w["utility"] * branch.expected_utility
        - w["risk"] * branch.risk
        - w["cost"] * branch.cost
        - w["latency"] * branch.latency
        + w["proof"] * branch.proof_completeness
        + w["diversity"] * branch.diversity_contribution
        - w["novelty"] * branch.novelty_penalty
    )


def rank_branches(
    branches: Iterable[BranchCandidate],
    envelope: AutonomyEnvelope,
    *,
    weights: Mapping[str, float] | None = None,
    minimum_evidence: int = 1,
) -> tuple[RankedBranch, ...]:
    items: list[RankedBranch] = []
    allowed = set(envelope.capabilities)
    for branch in branches:
        reasons: list[str] = []
        if branch.case_id != envelope.case_id:
            reasons.append("CASE_MISMATCH")
        missing = sorted(set(branch.required_capabilities) - allowed)
        if missing:
            reasons.append("CAPABILITY_OUTSIDE_ENVELOPE")
        if len(branch.evidence_digests) < minimum_evidence:
            reasons.append("INSUFFICIENT_EVIDENCE")
        if branch.novelty_penalty >= 0.9 and branch.proof_completeness < 0.8:
            reasons.append("UNSUPPORTED_NOVELTY")
        items.append(
            RankedBranch(
                branch=branch,
                score=branch_score(branch, weights),
                eligible=not reasons,
                elimination_reasons=tuple(reasons),
            )
        )

    eligible = sorted((item for item in items if item.eligible), key=lambda item: (-item.score, item.branch.branch_id))
    budget = envelope.budgets.max_branches
    selected_ids = {item.branch.branch_id for item in eligible[:budget]}
    final: list[RankedBranch] = []
    for item in items:
        if item.eligible and item.branch.branch_id not in selected_ids:
            final.append(
                RankedBranch(
                    branch=item.branch,
                    score=item.score,
                    eligible=False,
                    elimination_reasons=("BRANCH_BUDGET_PRUNED",),
                )
            )
        else:
            final.append(item)
    return tuple(sorted(final, key=lambda item: (-item.score, item.branch.branch_id)))
