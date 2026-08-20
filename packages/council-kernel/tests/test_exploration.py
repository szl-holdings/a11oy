from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import unittest

from a11oy_council.exploration import (
    BranchCandidate,
    BranchEvaluation,
    BranchFinding,
    BranchMarketPolicy,
    BranchState,
    CounterfactualBranchMarket,
    FindingSeverity,
    RecommendationState,
)


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
PARENT = hashlib.sha256(b"parent-decision").hexdigest()
PATCH = hashlib.sha256(b"patch").hexdigest()
SOURCE = hashlib.sha256(b"evaluation-source").hexdigest()
EVIDENCE = "evidence://branch-proof"


def candidate(
    *,
    branch_id: str = "branch-a",
    parent: str = PARENT,
    cost: int = 1_000,
    expected_value: float = 0.8,
    risk_score: float = 0.2,
    evidence: tuple[str, ...] = (EVIDENCE,),
    trust_domain: str = "proposer-domain",
) -> BranchCandidate:
    return BranchCandidate(
        branch_id=branch_id,
        parent_decision_digest=parent,
        hypothesis=f"Hypothesis for {branch_id}",
        patch_digest=hashlib.sha256((PATCH + branch_id).encode()).hexdigest(),
        proposer_id=f"proposer-{branch_id}",
        proposer_trust_domain=trust_domain,
        estimated_cost_microunits=cost,
        expected_value=expected_value,
        risk_score=risk_score,
        evidence_refs=evidence,
    )


def evaluation(
    item: BranchCandidate,
    *,
    trust_domain: str = "independent-domain",
    verifier_score: float = 0.9,
    test_pass_rate: float = 1.0,
    static_checks_pass: bool = True,
    policy_checks_pass: bool = True,
    candidate_digest: str | None = None,
    findings: tuple[BranchFinding, ...] = (),
    counterexamples: tuple[str, ...] = ("counterexample://1",),
    source_digest: str = SOURCE,
) -> BranchEvaluation:
    return BranchEvaluation(
        branch_id=item.branch_id,
        candidate_digest=candidate_digest or item.digest,
        evaluator_id=f"evaluator-{item.branch_id}",
        evaluator_trust_domain=trust_domain,
        evaluated_at=NOW,
        source_digest=source_digest,
        verifier_score=verifier_score,
        test_pass_rate=test_pass_rate,
        static_checks_pass=static_checks_pass,
        policy_checks_pass=policy_checks_pass,
        counterexamples=counterexamples,
        findings=findings,
    )


class AdmissionTests(unittest.TestCase):
    def test_valid_candidate_is_quarantined_and_reserves_budget(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        disposition = market.admit(candidate())
        self.assertEqual(disposition.state, BranchState.QUARANTINED)
        self.assertEqual(market.reserved_cost_microunits, 1_000)
        self.assertTrue(market.ledger.verify())

    def test_parent_mismatch_is_blocked(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        disposition = market.admit(
            candidate(parent=hashlib.sha256(b"other-parent").hexdigest())
        )
        self.assertEqual(disposition.state, BranchState.BLOCKED)
        self.assertEqual(market.reserved_cost_microunits, 0)
        self.assertTrue(any("parent decision" in reason for reason in disposition.reasons))

    def test_branch_count_budget_fails_closed(self) -> None:
        market = CounterfactualBranchMarket(
            PARENT,
            policy=BranchMarketPolicy(maximum_branches=1),
        )
        market.admit(candidate(branch_id="branch-a"))
        second = market.admit(candidate(branch_id="branch-b"))
        self.assertEqual(second.state, BranchState.BLOCKED)
        self.assertTrue(any("branch-count" in reason for reason in second.reasons))

    def test_per_branch_cost_budget_fails_closed(self) -> None:
        market = CounterfactualBranchMarket(
            PARENT,
            policy=BranchMarketPolicy(maximum_branch_cost_microunits=999),
        )
        disposition = market.admit(candidate(cost=1_000))
        self.assertEqual(disposition.state, BranchState.BLOCKED)
        self.assertTrue(any("per-branch" in reason for reason in disposition.reasons))

    def test_total_market_budget_fails_closed(self) -> None:
        market = CounterfactualBranchMarket(
            PARENT,
            policy=BranchMarketPolicy(
                total_budget_microunits=1_500,
                maximum_branch_cost_microunits=1_500,
            ),
        )
        market.admit(candidate(branch_id="branch-a", cost=1_000))
        second = market.admit(candidate(branch_id="branch-b", cost=600))
        self.assertEqual(second.state, BranchState.BLOCKED)
        self.assertEqual(market.reserved_cost_microunits, 1_000)
        self.assertTrue(any("remaining market budget" in reason for reason in second.reasons))

    def test_risk_and_evidence_gates_fail_closed(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        risky = market.admit(candidate(branch_id="risky", risk_score=0.9))
        unproven = market.admit(candidate(branch_id="unproven", evidence=()))
        self.assertEqual(risky.state, BranchState.BLOCKED)
        self.assertEqual(unproven.state, BranchState.BLOCKED)
        self.assertTrue(any("risk" in reason for reason in risky.reasons))
        self.assertTrue(any("evidence" in reason for reason in unproven.reasons))

    def test_branch_identifier_cannot_be_rebound(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        original = candidate()
        market.admit(original)
        with self.assertRaises(ValueError):
            market.admit(replace(original, expected_value=0.9))


class EvaluationTests(unittest.TestCase):
    def test_independent_green_evaluation_is_eligible(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        item = candidate()
        market.admit(item)
        disposition = market.evaluate(evaluation(item))
        self.assertEqual(disposition.state, BranchState.ELIGIBLE)
        self.assertGreater(disposition.score, 0.0)
        self.assertTrue(market.ledger.verify())

    def test_same_trust_domain_is_blocked(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        item = candidate(trust_domain="shared-domain")
        market.admit(item)
        disposition = market.evaluate(evaluation(item, trust_domain="shared-domain"))
        self.assertEqual(disposition.state, BranchState.BLOCKED)
        self.assertTrue(any("not independent" in reason for reason in disposition.reasons))

    def test_candidate_digest_mismatch_is_blocked(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        item = candidate()
        market.admit(item)
        disposition = market.evaluate(
            evaluation(
                item,
                candidate_digest=hashlib.sha256(b"different-candidate").hexdigest(),
            )
        )
        self.assertEqual(disposition.state, BranchState.BLOCKED)
        self.assertTrue(any("digest" in reason for reason in disposition.reasons))

    def test_check_and_score_thresholds_fail_closed(self) -> None:
        cases = (
            {"static_checks_pass": False},
            {"policy_checks_pass": False},
            {"verifier_score": 0.5},
            {"test_pass_rate": 0.5},
        )
        for index, overrides in enumerate(cases):
            with self.subTest(overrides=overrides):
                market = CounterfactualBranchMarket(PARENT)
                item = candidate(branch_id=f"branch-{index}")
                market.admit(item)
                disposition = market.evaluate(evaluation(item, **overrides))
                self.assertEqual(disposition.state, BranchState.BLOCKED)

    def test_high_finding_blocks_candidate(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        item = candidate()
        market.admit(item)
        disposition = market.evaluate(
            evaluation(
                item,
                findings=(
                    BranchFinding(
                        finding_id="finding-high",
                        severity=FindingSeverity.HIGH,
                        statement="Authorization boundary is incomplete.",
                    ),
                ),
            )
        )
        self.assertEqual(disposition.state, BranchState.BLOCKED)
        self.assertTrue(any("finding-high" in reason for reason in disposition.reasons))

    def test_medium_finding_is_retained_without_automatic_block(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        item = candidate()
        market.admit(item)
        disposition = market.evaluate(
            evaluation(
                item,
                findings=(
                    BranchFinding(
                        finding_id="finding-medium",
                        severity=FindingSeverity.MEDIUM,
                        statement="Additional benchmark breadth is desirable.",
                    ),
                ),
            )
        )
        self.assertEqual(disposition.state, BranchState.ELIGIBLE)

    def test_evaluation_identifier_cannot_be_rebound(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        item = candidate()
        market.admit(item)
        first = evaluation(item)
        market.evaluate(first)
        with self.assertRaises(ValueError):
            market.evaluate(
                replace(
                    first,
                    source_digest=hashlib.sha256(b"different-source").hexdigest(),
                )
            )


class RecommendationTests(unittest.TestCase):
    def test_market_ranks_candidates_but_never_authorizes_promotion(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        high = candidate(
            branch_id="high-value",
            expected_value=0.95,
            cost=1_000,
        )
        lower = candidate(
            branch_id="lower-value",
            expected_value=0.55,
            cost=500,
        )
        for item in (high, lower):
            market.admit(item)
            market.evaluate(evaluation(item))
        recommendation = market.recommend(limit=2)
        self.assertEqual(recommendation.state, RecommendationState.RECOMMEND)
        self.assertEqual(recommendation.branch_ids[0], "high-value")
        self.assertEqual(set(recommendation.branch_ids), {"high-value", "lower-value"})
        self.assertFalse(recommendation.promotion_authorized)
        self.assertEqual(len(recommendation.market_snapshot_digest), 64)

    def test_market_without_eligible_candidate_returns_no_selection(self) -> None:
        market = CounterfactualBranchMarket(PARENT)
        market.admit(candidate())
        recommendation = market.recommend()
        self.assertEqual(recommendation.state, RecommendationState.NO_SELECTION)
        self.assertEqual(recommendation.branch_ids, ())
        self.assertFalse(recommendation.promotion_authorized)
        self.assertTrue(market.ledger.verify())
        self.assertEqual(len(market.ledger.entries), 2)


if __name__ == "__main__":
    unittest.main()
