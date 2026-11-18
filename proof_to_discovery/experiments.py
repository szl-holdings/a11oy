#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The evidence-value recommender: which experiment should run next?

The central question of the Proof-to-Discovery doctrine:

    Which authorized experiment, if performed next, reduces the decision's
    unresolved blocking obligations at the lowest justified cost and risk?

For v1 the model is deliberately simple and declared, not implied: an
experiment has value only if it can complete the currently unresolved
blocking set in one step. Its expected value of sample information is

    EVSI(t) = decision_value * product(resolve_probability[o] for o unresolved blocking)

which is the probability that the experiment completes the missing blocking
evidence, times the declared value of the decision. The recommended
experiment maximizes

    score(t) = EVSI(t) - lambda * cost(t) - mu * risk(t)

over authorized experiments only. Unauthorized experiments are listed as
blocked-by-authorization and are never recommended, no matter how informative
they look. Authorization is a hard constraint, not a penalty term.

All probabilities, costs, risks, and the decision value are declared
estimates supplied by the experiment catalog. They are surfaced in the
recommendation verbatim so an operator can audit the arithmetic. The engine
never manufactures a number.
"""

from __future__ import annotations

from dataclasses import dataclass

from .graph import Evaluation
from .policy import TrustPolicy


@dataclass(frozen=True)
class Experiment:
    """One candidate experiment in the authorized experiment catalog."""

    experiment_id: str
    resolves: tuple[str, ...]
    resolve_probability: dict[str, float]
    cost: float
    risk: float
    authorized: bool
    note: str = ""

    def __post_init__(self) -> None:
        if not self.experiment_id:
            raise ValueError("experiment_id is required")
        for obligation_id in self.resolves:
            if obligation_id not in self.resolve_probability:
                raise ValueError(
                    f"experiment {self.experiment_id} resolves {obligation_id} without a "
                    "declared probability"
                )
        for obligation_id, probability in self.resolve_probability.items():
            if obligation_id not in self.resolves:
                raise ValueError(
                    f"experiment {self.experiment_id} declares probability for "
                    f"{obligation_id} it does not resolve"
                )
            if not 0.0 <= probability <= 1.0:
                raise ValueError(
                    f"experiment {self.experiment_id} probability for {obligation_id} is "
                    f"outside [0, 1]: {probability}"
                )


@dataclass(frozen=True)
class ScoredExperiment:
    """The auditable arithmetic behind one experiment's score."""

    experiment_id: str
    evsi: float
    score: float
    rationale: str


@dataclass(frozen=True)
class Recommendation:
    """What the operator should run next, and everything that was considered."""

    recommended: ScoredExperiment | None
    unresolved_blocking: tuple[str, ...]
    refuted: tuple[str, ...]
    blocked_by_authorization: tuple[str, ...]
    scores: tuple[ScoredExperiment, ...]
    rationale: str


def recommend(
    *,
    graph,
    evaluation: Evaluation,
    experiments: tuple[Experiment, ...],
    policy: TrustPolicy,
) -> Recommendation:
    """Fail-closed EVSI argmax over the authorized experiment catalog."""
    refuted = evaluation.refuted()
    unresolved = tuple(sorted(evaluation.blocking_unresolved()))
    scores: list[ScoredExperiment] = []
    blocked: list[str] = []

    if refuted:
        return Recommendation(
            recommended=None,
            unresolved_blocking=unresolved,
            refuted=refuted,
            blocked_by_authorization=(),
            scores=(),
            rationale=(
                "evidence REFUTES obligations ("
                + ", ".join(refuted)
                + "); no experiment is recommended for a refuted decision. Refutation "
                "requires redesign or retraction, not more sampling."
            ),
        )
    if not unresolved:
        return Recommendation(
            recommended=None,
            unresolved_blocking=(),
            refuted=(),
            blocked_by_authorization=(),
            scores=(),
            rationale=(
                "every blocking obligation is PROVEN; no experiment is required for this decision"
            ),
        )

    for experiment in sorted(experiments, key=lambda item: item.experiment_id):
        if not experiment.authorized:
            blocked.append(experiment.experiment_id)
            continue
        missing = [item for item in unresolved if item not in experiment.resolves]
        if missing:
            scores.append(
                ScoredExperiment(
                    experiment_id=experiment.experiment_id,
                    evsi=0.0,
                    score=0.0,
                    rationale=(
                        "does not complete the unresolved blocking set on its own; missing: "
                        + ", ".join(missing)
                    ),
                )
            )
            continue
        probability = 1.0
        for obligation_id in unresolved:
            probability *= experiment.resolve_probability[obligation_id]
        evsi = evaluation.decision_value * probability
        score = evsi - policy.cost_weight * experiment.cost - policy.risk_weight * experiment.risk
        scores.append(
            ScoredExperiment(
                experiment_id=experiment.experiment_id,
                evsi=evsi,
                score=score,
                rationale=(
                    f"EVSI = decision_value {evaluation.decision_value} x completion "
                    f"probability {probability}; score = EVSI - "
                    f"lambda*cost({experiment.cost}) - mu*risk({experiment.risk})"
                ),
            )
        )

    if not scores:
        return Recommendation(
            recommended=None,
            unresolved_blocking=unresolved,
            refuted=(),
            blocked_by_authorization=tuple(sorted(blocked)),
            scores=(),
            rationale=(
                "no authorized experiment in the catalog addresses the unresolved blocking "
                "obligations: " + ", ".join(unresolved)
            ),
        )

    best_score = max(item.score for item in scores)
    if best_score <= 0:
        return Recommendation(
            recommended=None,
            unresolved_blocking=unresolved,
            refuted=(),
            blocked_by_authorization=tuple(sorted(blocked)),
            scores=tuple(scores),
            rationale=(
                "every authorized experiment has a non-positive score, so the do-nothing "
                "option dominates; no experiment is recommended"
            ),
        )
    best = min(
        (item for item in scores if item.score == best_score),
        key=lambda item: item.experiment_id,
    )
    return Recommendation(
        recommended=best,
        unresolved_blocking=unresolved,
        refuted=(),
        blocked_by_authorization=tuple(sorted(blocked)),
        scores=tuple(scores),
        rationale=(
            f"recommended {best.experiment_id} with score {best.score}; all scores are declared "
            "estimates from the experiment catalog"
        ),
    )
