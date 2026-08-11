from __future__ import annotations

"""Epistemic diversity measurement over declared and signed identity axes."""

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping

from .models import CouncilIdentity, CouncilPolicy

AXES = (
    "trust_domain",
    "key_id",
    "implementation_digest",
    "model_family",
    "evidence_domain",
    "operator_id",
    "retrieval_path",
    "provider_account",
)


@dataclass(frozen=True, slots=True)
class DiversityReport:
    participant_count: int
    distinct: Mapping[str, int]
    effective_by_axis: Mapping[str, float]
    joint_effective_size: float
    minimum_effective_size: float
    requirements_met: bool
    failed_requirements: tuple[str, ...]
    cluster_assignments: Mapping[str, tuple[str, ...]]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "szl.epistemic-diversity-report/v1",
            "participant_count": self.participant_count,
            "distinct": dict(self.distinct),
            "effective_by_axis": {key: round(value, 6) for key, value in self.effective_by_axis.items()},
            "joint_effective_size": round(self.joint_effective_size, 6),
            "minimum_effective_size": self.minimum_effective_size,
            "requirements_met": self.requirements_met,
            "failed_requirements": list(self.failed_requirements),
            "cluster_assignments": {key: list(value) for key, value in self.cluster_assignments.items()},
        }


def effective_size(values: Iterable[str]) -> float:
    items = list(values)
    if not items:
        return 0.0
    counts = Counter(items)
    total = len(items)
    denominator = sum((count / total) ** 2 for count in counts.values())
    return 0.0 if denominator == 0 else 1.0 / denominator


def compile_diversity(identities: Iterable[CouncilIdentity], policy: CouncilPolicy) -> DiversityReport:
    members = tuple(identities)
    distinct: dict[str, int] = {}
    effective: dict[str, float] = {}
    clusters: dict[str, tuple[str, ...]] = {}
    for axis in AXES:
        values = tuple(str(getattr(identity, axis)) for identity in members)
        distinct[axis] = len(set(values))
        effective[axis] = effective_size(values)
        clusters[axis] = values

    # A council is only as epistemically independent as its weakest declared
    # independence axis.  A joint tuple would incorrectly treat four distinct
    # signing keys as four independent councils even when every operator, model,
    # implementation, evidence source, retrieval path, provider account, and
    # trust domain is shared.  The conservative minimum is intentionally
    # fail-closed: manufactured diversity cannot be rescued by one unique field.
    joint = min(effective.values(), default=0.0)
    minimums = {
        "trust_domain": policy.min_distinct_trust_domains,
        "key_id": policy.min_distinct_keys,
        "implementation_digest": policy.min_distinct_implementations,
        "model_family": policy.min_distinct_model_families,
        "evidence_domain": policy.min_distinct_evidence_domains,
        "operator_id": policy.min_distinct_operators,
        "retrieval_path": policy.min_distinct_retrieval_paths,
        "provider_account": policy.min_distinct_provider_accounts,
    }
    failed = [
        f"DISTINCT_{axis.upper()}_BELOW_MINIMUM"
        for axis, minimum in minimums.items()
        if distinct.get(axis, 0) < minimum
    ]
    if joint < policy.minimum_effective_size:
        failed.append("EFFECTIVE_COUNCIL_SIZE_BELOW_MINIMUM")
    return DiversityReport(
        participant_count=len(members),
        distinct=distinct,
        effective_by_axis=effective,
        joint_effective_size=joint,
        minimum_effective_size=policy.minimum_effective_size,
        requirements_met=not failed,
        failed_requirements=tuple(sorted(failed)),
        cluster_assignments=clusters,
    )
