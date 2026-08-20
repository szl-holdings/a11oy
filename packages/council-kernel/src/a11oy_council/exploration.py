"""Budgeted counterfactual branch market with no self-promotion path."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
import re
from threading import RLock
from typing import Any, Mapping, Sequence

from .kernel import HashChainLedger, canonical_json, sha256_text


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class BranchState(str, Enum):
    QUARANTINED = "QUARANTINED"
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"


class FindingSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendationState(str, Enum):
    NO_SELECTION = "NO_SELECTION"
    RECOMMEND = "RECOMMEND"


def _nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _sha256(name: str, value: str) -> None:
    if not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be lowercase SHA-256 hex")


def _unit(name: str, value: float) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class BranchCandidate:
    branch_id: str
    parent_decision_digest: str
    hypothesis: str
    patch_digest: str
    proposer_id: str
    proposer_trust_domain: str
    estimated_cost_microunits: int
    expected_value: float
    risk_score: float
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("branch_id", "hypothesis", "proposer_id", "proposer_trust_domain"):
            _nonempty(name, getattr(self, name))
        _sha256("parent_decision_digest", self.parent_decision_digest)
        _sha256("patch_digest", self.patch_digest)
        if self.estimated_cost_microunits < 0:
            raise ValueError("estimated branch cost cannot be negative")
        _unit("expected_value", self.expected_value)
        _unit("risk_score", self.risk_score)
        if any(not item.strip() for item in self.evidence_refs):
            raise ValueError("evidence_refs must contain non-empty strings")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "parent_decision_digest": self.parent_decision_digest,
            "hypothesis": self.hypothesis,
            "patch_digest": self.patch_digest,
            "proposer_id": self.proposer_id,
            "proposer_trust_domain": self.proposer_trust_domain,
            "estimated_cost_microunits": self.estimated_cost_microunits,
            "expected_value": self.expected_value,
            "risk_score": self.risk_score,
            "evidence_refs": list(self.evidence_refs),
        }

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.canonical_dict()))


@dataclass(frozen=True, slots=True)
class BranchFinding:
    finding_id: str
    severity: FindingSeverity
    statement: str

    def __post_init__(self) -> None:
        _nonempty("finding_id", self.finding_id)
        _nonempty("statement", self.statement)

    def canonical_dict(self) -> dict[str, str]:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity.value,
            "statement": self.statement,
        }


@dataclass(frozen=True, slots=True)
class BranchEvaluation:
    branch_id: str
    candidate_digest: str
    evaluator_id: str
    evaluator_trust_domain: str
    evaluated_at: datetime
    source_digest: str
    verifier_score: float
    test_pass_rate: float
    static_checks_pass: bool
    policy_checks_pass: bool
    counterexamples: tuple[str, ...] = ()
    findings: tuple[BranchFinding, ...] = ()

    def __post_init__(self) -> None:
        for name in ("branch_id", "evaluator_id", "evaluator_trust_domain"):
            _nonempty(name, getattr(self, name))
        _sha256("candidate_digest", self.candidate_digest)
        _sha256("source_digest", self.source_digest)
        _utc(self.evaluated_at)
        _unit("verifier_score", self.verifier_score)
        _unit("test_pass_rate", self.test_pass_rate)
        if any(not item.strip() for item in self.counterexamples):
            raise ValueError("counterexamples must contain non-empty strings")
        finding_ids = [finding.finding_id for finding in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("finding identifiers must be unique")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "candidate_digest": self.candidate_digest,
            "evaluator_id": self.evaluator_id,
            "evaluator_trust_domain": self.evaluator_trust_domain,
            "evaluated_at": _utc(self.evaluated_at).isoformat().replace("+00:00", "Z"),
            "source_digest": self.source_digest,
            "verifier_score": self.verifier_score,
            "test_pass_rate": self.test_pass_rate,
            "static_checks_pass": self.static_checks_pass,
            "policy_checks_pass": self.policy_checks_pass,
            "counterexamples": list(self.counterexamples),
            "findings": [finding.canonical_dict() for finding in self.findings],
        }

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.canonical_dict()))


@dataclass(frozen=True, slots=True)
class BranchMarketPolicy:
    maximum_branches: int = 8
    total_budget_microunits: int = 100_000
    maximum_branch_cost_microunits: int = 25_000
    minimum_evidence_refs: int = 1
    minimum_verifier_score: float = 0.75
    minimum_test_pass_rate: float = 1.0
    maximum_risk_score: float = 0.4
    require_independent_trust_domain: bool = True
    blocked_severities: frozenset[FindingSeverity] = field(
        default_factory=lambda: frozenset(
            {FindingSeverity.HIGH, FindingSeverity.CRITICAL}
        )
    )

    def __post_init__(self) -> None:
        if self.maximum_branches <= 0:
            raise ValueError("maximum_branches must be positive")
        if self.total_budget_microunits < 0:
            raise ValueError("total branch budget cannot be negative")
        if self.maximum_branch_cost_microunits < 0:
            raise ValueError("maximum branch cost cannot be negative")
        if self.minimum_evidence_refs < 0:
            raise ValueError("minimum evidence count cannot be negative")
        _unit("minimum_verifier_score", self.minimum_verifier_score)
        _unit("minimum_test_pass_rate", self.minimum_test_pass_rate)
        _unit("maximum_risk_score", self.maximum_risk_score)


@dataclass(frozen=True, slots=True)
class BranchDisposition:
    branch_id: str
    candidate_digest: str
    evaluation_digest: str | None
    state: BranchState
    score: float
    reasons: tuple[str, ...]
    disposition_digest: str

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "candidate_digest": self.candidate_digest,
            "evaluation_digest": self.evaluation_digest,
            "state": self.state.value,
            "score": self.score,
            "reasons": list(self.reasons),
            "disposition_digest": self.disposition_digest,
        }


@dataclass(frozen=True, slots=True)
class MarketRecommendation:
    state: RecommendationState
    branch_ids: tuple[str, ...]
    market_snapshot_digest: str
    promotion_authorized: bool
    recommendation_digest: str

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "branch_ids": list(self.branch_ids),
            "market_snapshot_digest": self.market_snapshot_digest,
            "promotion_authorized": self.promotion_authorized,
            "recommendation_digest": self.recommendation_digest,
        }


class CounterfactualBranchMarket:
    """Admit, evaluate, and rank bounded branches without executing them."""

    def __init__(
        self,
        parent_decision_digest: str,
        *,
        policy: BranchMarketPolicy | None = None,
        ledger: HashChainLedger | None = None,
    ) -> None:
        _sha256("parent_decision_digest", parent_decision_digest)
        self.parent_decision_digest = parent_decision_digest
        self.policy = policy or BranchMarketPolicy()
        self.ledger = ledger or HashChainLedger()
        self._candidates: dict[str, BranchCandidate] = {}
        self._evaluations: dict[str, BranchEvaluation] = {}
        self._dispositions: dict[str, BranchDisposition] = {}
        self._reserved_cost = 0
        self._lock = RLock()

    @property
    def candidates(self) -> Mapping[str, BranchCandidate]:
        with self._lock:
            return dict(self._candidates)

    @property
    def dispositions(self) -> Mapping[str, BranchDisposition]:
        with self._lock:
            return dict(self._dispositions)

    @property
    def reserved_cost_microunits(self) -> int:
        with self._lock:
            return self._reserved_cost

    def admit(self, candidate: BranchCandidate) -> BranchDisposition:
        with self._lock:
            existing = self._candidates.get(candidate.branch_id)
            if existing is not None:
                if existing.digest != candidate.digest:
                    raise ValueError("branch_id already names different content")
                return self._dispositions[candidate.branch_id]

            reasons: list[str] = []
            if candidate.parent_decision_digest != self.parent_decision_digest:
                reasons.append("candidate parent decision does not match the market")
            if len(self._candidates) >= self.policy.maximum_branches:
                reasons.append("market branch-count budget is exhausted")
            if candidate.estimated_cost_microunits > self.policy.maximum_branch_cost_microunits:
                reasons.append("candidate cost exceeds the per-branch budget")
            if (
                self._reserved_cost + candidate.estimated_cost_microunits
                > self.policy.total_budget_microunits
            ):
                reasons.append("candidate cost exceeds the remaining market budget")
            if candidate.risk_score > self.policy.maximum_risk_score:
                reasons.append("candidate risk exceeds the market policy")
            if len(candidate.evidence_refs) < self.policy.minimum_evidence_refs:
                reasons.append("candidate evidence count is below market policy")

            state = BranchState.BLOCKED if reasons else BranchState.QUARANTINED
            if not reasons:
                reasons.append("candidate admitted to quarantine pending independent evaluation")
                self._reserved_cost += candidate.estimated_cost_microunits
            self._candidates[candidate.branch_id] = candidate
            disposition = self._build_disposition(
                candidate,
                evaluation=None,
                state=state,
                score=0.0,
                reasons=reasons,
            )
            self._dispositions[candidate.branch_id] = disposition
            self.ledger.append(
                "branch.admitted",
                {
                    "branch_id": candidate.branch_id,
                    "candidate_digest": candidate.digest,
                    "state": state.value,
                    "reserved_cost_microunits": self._reserved_cost,
                },
            )
            return disposition

    def evaluate(self, evaluation: BranchEvaluation) -> BranchDisposition:
        with self._lock:
            candidate = self._candidates.get(evaluation.branch_id)
            if candidate is None:
                raise KeyError(f"unknown branch_id: {evaluation.branch_id}")
            current = self._dispositions[evaluation.branch_id]
            if current.state is BranchState.BLOCKED:
                return current
            if evaluation.candidate_digest != candidate.digest:
                return self._record_block(
                    candidate,
                    evaluation,
                    "evaluation candidate digest does not match",
                )
            existing = self._evaluations.get(evaluation.branch_id)
            if existing is not None and existing.digest != evaluation.digest:
                raise ValueError("branch already has a different evaluation")

            reasons: list[str] = []
            if (
                self.policy.require_independent_trust_domain
                and evaluation.evaluator_trust_domain == candidate.proposer_trust_domain
            ):
                reasons.append("evaluation trust domain is not independent")
            if not evaluation.static_checks_pass:
                reasons.append("static checks did not pass")
            if not evaluation.policy_checks_pass:
                reasons.append("policy checks did not pass")
            if evaluation.verifier_score < self.policy.minimum_verifier_score:
                reasons.append("verifier score is below policy")
            if evaluation.test_pass_rate < self.policy.minimum_test_pass_rate:
                reasons.append("test pass rate is below policy")
            blocked_findings = tuple(
                finding
                for finding in evaluation.findings
                if finding.severity in self.policy.blocked_severities
            )
            if blocked_findings:
                reasons.append(
                    "blocking findings are present: "
                    + ", ".join(sorted(finding.finding_id for finding in blocked_findings))
                )

            state = BranchState.BLOCKED if reasons else BranchState.ELIGIBLE
            score = self._score(candidate, evaluation) if not reasons else 0.0
            if not reasons:
                reasons.append("independence, verification, test, policy, risk, and evidence gates passed")
            self._evaluations[evaluation.branch_id] = evaluation
            disposition = self._build_disposition(
                candidate,
                evaluation=evaluation,
                state=state,
                score=score,
                reasons=reasons,
            )
            self._dispositions[evaluation.branch_id] = disposition
            self.ledger.append(
                "branch.evaluated",
                {
                    "branch_id": evaluation.branch_id,
                    "candidate_digest": candidate.digest,
                    "evaluation_digest": evaluation.digest,
                    "state": state.value,
                    "score": score,
                },
            )
            return disposition

    def recommend(self, *, limit: int = 1) -> MarketRecommendation:
        if limit <= 0:
            raise ValueError("recommendation limit must be positive")
        with self._lock:
            eligible = sorted(
                (
                    disposition
                    for disposition in self._dispositions.values()
                    if disposition.state is BranchState.ELIGIBLE
                ),
                key=lambda disposition: (
                    -disposition.score,
                    self._candidates[disposition.branch_id].estimated_cost_microunits,
                    disposition.candidate_digest,
                ),
            )
            selected = tuple(disposition.branch_id for disposition in eligible[:limit])
            snapshot = {
                "parent_decision_digest": self.parent_decision_digest,
                "reserved_cost_microunits": self._reserved_cost,
                "dispositions": [
                    self._dispositions[branch_id].canonical_dict()
                    for branch_id in sorted(self._dispositions)
                ],
            }
            snapshot_digest = sha256_text(canonical_json(snapshot))
            state = (
                RecommendationState.RECOMMEND
                if selected
                else RecommendationState.NO_SELECTION
            )
            body = {
                "state": state.value,
                "branch_ids": list(selected),
                "market_snapshot_digest": snapshot_digest,
                "promotion_authorized": False,
            }
            recommendation = MarketRecommendation(
                state=state,
                branch_ids=selected,
                market_snapshot_digest=snapshot_digest,
                promotion_authorized=False,
                recommendation_digest=sha256_text(canonical_json(body)),
            )
            self.ledger.append(
                "branch.market_recommended",
                {
                    "state": state.value,
                    "branch_ids": list(selected),
                    "market_snapshot_digest": snapshot_digest,
                    "promotion_authorized": False,
                    "recommendation_digest": recommendation.recommendation_digest,
                },
            )
            return recommendation

    def _record_block(
        self,
        candidate: BranchCandidate,
        evaluation: BranchEvaluation,
        reason: str,
    ) -> BranchDisposition:
        disposition = self._build_disposition(
            candidate,
            evaluation=evaluation,
            state=BranchState.BLOCKED,
            score=0.0,
            reasons=(reason,),
        )
        self._evaluations[evaluation.branch_id] = evaluation
        self._dispositions[evaluation.branch_id] = disposition
        self.ledger.append(
            "branch.evaluated",
            {
                "branch_id": evaluation.branch_id,
                "candidate_digest": candidate.digest,
                "evaluation_digest": evaluation.digest,
                "state": BranchState.BLOCKED.value,
                "score": 0.0,
            },
        )
        return disposition

    def _build_disposition(
        self,
        candidate: BranchCandidate,
        *,
        evaluation: BranchEvaluation | None,
        state: BranchState,
        score: float,
        reasons: Sequence[str],
    ) -> BranchDisposition:
        body = {
            "branch_id": candidate.branch_id,
            "candidate_digest": candidate.digest,
            "evaluation_digest": evaluation.digest if evaluation is not None else None,
            "state": state.value,
            "score": score,
            "reasons": list(reasons),
        }
        return BranchDisposition(
            branch_id=candidate.branch_id,
            candidate_digest=candidate.digest,
            evaluation_digest=body["evaluation_digest"],
            state=state,
            score=score,
            reasons=tuple(reasons),
            disposition_digest=sha256_text(canonical_json(body)),
        )

    def _score(
        self,
        candidate: BranchCandidate,
        evaluation: BranchEvaluation,
    ) -> float:
        evidence_completeness = min(
            1.0,
            len(candidate.evidence_refs) / max(1, self.policy.minimum_evidence_refs),
        )
        cost_efficiency = 1.0
        if self.policy.maximum_branch_cost_microunits > 0:
            cost_efficiency = 1.0 - min(
                1.0,
                candidate.estimated_cost_microunits
                / self.policy.maximum_branch_cost_microunits,
            )
        counterexample_credit = min(1.0, len(evaluation.counterexamples) / 5.0)
        score = (
            0.30 * evaluation.verifier_score
            + 0.20 * evaluation.test_pass_rate
            + 0.15 * candidate.expected_value
            + 0.10 * (1.0 - candidate.risk_score)
            + 0.10 * cost_efficiency
            + 0.10 * evidence_completeness
            + 0.05 * counterexample_credit
        )
        return round(score, 6)
