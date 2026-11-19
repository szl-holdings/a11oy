#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""The Flagship54-style admission demonstration (DEMONSTRATION, not a claim).

This demo assembles the questions from the Proof-to-Discovery memo into one
obligation graph: was the terminal training state valid, were the weights
preserved, can an independent party recover the artifacts, did the model
actually improve, are its abstentions calibrated, does the runtime satisfy
security and performance requirements, and can a third party reproduce the
evidence chain. A synthetic evidence bundle answers some of them honestly at
the required witness tiers and leaves the rest UNRESOLVED. The engine then
answers the operator's question the way the doctrine demands: what is
PROVEN, what is missing, which authorized experiment would resolve it, and
whether action is permitted.

Every record and key here is synthetic and deterministic. This demonstration
asserts nothing about any real model, repository, or deployment. Its purpose
is to show the shape of an honest answer, and to be machine-checkable itself
via ``--check``.
"""

from __future__ import annotations

import json

from .cases import EVALUATED_AT, OWNER_KEY, POLICY, WITNESS_KEY, WITNESS_SEED
from .experiments import Experiment, recommend
from .graph import Obligation, ObligationGraph, evaluate
from .policy import evaluate_action
from .records import EvidenceRecord

ACTION = "admit-for-deployment"


def demonstration_graph() -> ObligationGraph:
    return ObligationGraph(
        decision_id="flagship54-admission-demo",
        decision_statement=(
            "Admit the demonstration training run's terminal checkpoint for deployment."
        ),
        decision_value=1_000_000.0,
        obligations=(
            Obligation(
                obligation_id="terminal-state-valid",
                question="Was the terminal training state valid?",
                required_tier="CONTENT_HASH_BINDING",
                freshness_seconds=None,
                blocking=True,
            ),
            Obligation(
                obligation_id="weights-preserved",
                question="Were the correct weights preserved, byte for byte?",
                required_tier="CONTENT_HASH_BINDING",
                freshness_seconds=None,
                blocking=True,
            ),
            Obligation(
                obligation_id="independently-recoverable",
                question="Can an independent party recover the artifacts from immutable source?",
                required_tier="SIGNED_WITNESS",
                freshness_seconds=86400,
                blocking=True,
            ),
            Obligation(
                obligation_id="actual-improvement",
                question="Did the model actually improve over the declared baseline?",
                required_tier="SIGNED_WITNESS",
                freshness_seconds=None,
                blocking=True,
            ),
            Obligation(
                obligation_id="calibrated-abstention",
                question="Are the abstention decisions calibrated on held-out data?",
                required_tier="SIGNED_WITNESS",
                freshness_seconds=86400,
                blocking=True,
            ),
            Obligation(
                obligation_id="runtime-security-performance",
                question="Does the runtime satisfy the declared security and performance floors?",
                required_tier="SIGNED_WITNESS",
                freshness_seconds=86400,
                blocking=True,
            ),
            Obligation(
                obligation_id="independent-reproducibility",
                question="Can an independent party reproduce the evidence chain?",
                required_tier="SIGNED_WITNESS",
                freshness_seconds=86400,
                blocking=True,
                depends_on=("terminal-state-valid", "weights-preserved"),
            ),
        ),
    )


def demonstration_records() -> tuple[EvidenceRecord, ...]:
    """A synthetic bundle: some obligations honestly supported, the rest missing."""
    return (
        EvidenceRecord.build(
            record_id="demo-r-terminal",
            obligation_id="terminal-state-valid",
            stance="supports",
            witness_tier="CONTENT_HASH_BINDING",
            payload={
                "run": "demo-run-001",
                "terminal_step": 54000,
                "statement": "terminal checkpoint digest matches the training contract digest",
            },
            observed_at="2026-11-18T00:00:00Z",
            source_uri="demo://flagship54/terminal-state",
        ),
        EvidenceRecord.build(
            record_id="demo-r-weights",
            obligation_id="weights-preserved",
            stance="supports",
            witness_tier="CONTENT_HASH_BINDING",
            payload={
                "run": "demo-run-001",
                "statement": "weight safetensors digest bound to the immutable tag",
            },
            observed_at="2026-11-18T00:05:00Z",
            source_uri="demo://flagship54/weights",
        ),
        EvidenceRecord.build(
            record_id="demo-r-improvement",
            obligation_id="actual-improvement",
            stance="supports",
            witness_tier="SIGNED_WITNESS",
            payload={
                "run": "demo-run-001",
                "held_out": "demo-holdout-v1",
                "statement": "held-out improvement over baseline within declared bounds",
            },
            observed_at="2026-11-18T01:00:00Z",
            signer_seed=WITNESS_SEED,
            source_uri="demo://flagship54/improvement",
        ),
        EvidenceRecord.build(
            record_id="demo-r-runtime",
            obligation_id="runtime-security-performance",
            stance="supports",
            witness_tier="SIGNED_WITNESS",
            payload={
                "run": "demo-run-001",
                "statement": "runtime floors met in the offline harness",
            },
            observed_at="2026-11-18T02:00:00Z",
            signer_seed=WITNESS_SEED,
            source_uri="demo://flagship54/runtime",
        ),
    )


def demonstration_experiments() -> tuple[Experiment, ...]:
    """The authorized experiment catalog for the demonstration."""
    return (
        Experiment(
            experiment_id="exp-recovery-drill",
            resolves=("independently-recoverable",),
            resolve_probability={"independently-recoverable": 0.85},
            cost=50.0,
            risk=0.01,
            authorized=True,
            note="cold-start recovery drill against the immutable source",
        ),
        Experiment(
            experiment_id="exp-calibration-audit",
            resolves=("calibrated-abstention",),
            resolve_probability={"calibrated-abstention": 0.8},
            cost=120.0,
            risk=0.02,
            authorized=True,
            note="reliability audit of abstention on fresh held-out data",
        ),
        Experiment(
            experiment_id="exp-full-chain-audit",
            resolves=(
                "independently-recoverable",
                "calibrated-abstention",
                "independent-reproducibility",
            ),
            resolve_probability={
                "independently-recoverable": 0.7,
                "calibrated-abstention": 0.65,
                "independent-reproducibility": 0.6,
            },
            cost=300.0,
            risk=0.05,
            authorized=True,
            note="external auditor walks the full chain in one engagement",
        ),
        Experiment(
            experiment_id="exp-untargeted-benchmark",
            resolves=("actual-improvement",),
            resolve_probability={"actual-improvement": 0.9},
            cost=10.0,
            risk=0.0,
            authorized=False,
            note="re-benchmarks an already-PROVEN obligation; not authorized in this window",
        ),
    )


def build_report() -> dict:
    """Run the demonstration and return its machine-checkable report."""
    graph = demonstration_graph()
    records = demonstration_records()
    evaluation = evaluate(graph, records, POLICY, EVALUATED_AT)
    action = evaluate_action(
        graph=graph,
        evaluation=evaluation,
        grant=None,
        policy=POLICY,
        action=ACTION,
        evaluated_at=EVALUATED_AT,
    )
    recommendation = recommend(
        graph=graph,
        evaluation=evaluation,
        experiments=demonstration_experiments(),
        policy=POLICY,
    )
    return {
        "demonstration": True,
        "claims": "synthetic fixtures only; no live-estate claims",
        "decision_id": graph.decision_id,
        "decision_statement": graph.decision_statement,
        "evaluated_at": evaluation.evaluated_at,
        "obligations": {
            item.obligation_id: {
                "question": item.question,
                "verdict": item.verdict,
                "blocking": item.blocking,
                "supporting_records": list(item.supporting_records),
                "refuting_records": list(item.refuting_records),
                "notes": list(item.notes),
            }
            for item in evaluation.verdicts.values()
        },
        "unresolved_blocking": list(evaluation.blocking_unresolved()),
        "refuted": list(evaluation.refuted()),
        "anomalies": list(evaluation.anomalies),
        "action": {
            "action": action.action,
            "may_act": action.may_act,
            "reasons": list(action.reasons),
        },
        "recommendation": {
            "recommended": (
                {
                    "experiment_id": recommendation.recommended.experiment_id,
                    "evsi": recommendation.recommended.evsi,
                    "score": recommendation.recommended.score,
                    "rationale": recommendation.recommended.rationale,
                }
                if recommendation.recommended is not None
                else None
            ),
            "blocked_by_authorization": list(recommendation.blocked_by_authorization),
            "unresolved_blocking": list(recommendation.unresolved_blocking),
            "rationale": recommendation.rationale,
            "all_scores": [
                {
                    "experiment_id": item.experiment_id,
                    "evsi": item.evsi,
                    "score": item.score,
                    "rationale": item.rationale,
                }
                for item in recommendation.scores
            ],
        },
        "keys": {
            "owner_key": OWNER_KEY[:16] + "...",
            "witness_key": WITNESS_KEY[:16] + "...",
        },
    }


def check_report(report: dict) -> list[str]:
    """Structural acceptance checks for the demonstration itself."""
    problems: list[str] = []
    verdicts = {name: item["verdict"] for name, item in report["obligations"].items()}
    expected_proven = {"terminal-state-valid", "weights-preserved", "actual-improvement",
                       "runtime-security-performance"}
    expected_unresolved = {"independently-recoverable", "calibrated-abstention",
                          "independent-reproducibility"}
    for name in expected_proven:
        if verdicts.get(name) != "PROVEN":
            problems.append(f"expected {name} PROVEN, got {verdicts.get(name)}")
    for name in expected_unresolved:
        if verdicts.get(name) != "UNRESOLVED":
            problems.append(f"expected {name} UNRESOLVED, got {verdicts.get(name)}")
    if report["refuted"]:
        problems.append("demonstration must not manufacture refutations")
    if report["action"]["may_act"]:
        problems.append("action must be refused while blocking obligations are unresolved")
    if report["recommendation"]["recommended"] is None:
        problems.append("a recommendation is expected while evidence is missing")
    if report["recommendation"]["blocked_by_authorization"] != ["exp-untargeted-benchmark"]:
        problems.append("unauthorized experiments must be listed as blocked, not recommended")
    if report["recommendation"]["recommended"] is not None:
        if report["recommendation"]["recommended"]["experiment_id"] in report[
            "recommendation"
        ]["blocked_by_authorization"]:
            problems.append("an unauthorized experiment was recommended")
    if not report["demonstration"] or "no live-estate claims" not in report["claims"]:
        problems.append("demonstration labeling is missing")
    return problems


def render(report: dict) -> str:
    """Human-readable rendering of the demonstration report."""
    lines = [
        "A11oy Proof-to-Discovery v1 - Flagship54 admission demonstration",
        "(DEMONSTRATION with synthetic fixtures; no live-estate claims)",
        "",
        f"Decision: {report['decision_statement']}",
        f"Evaluated at: {report['evaluated_at']} (all times UTC)",
        "",
        "Obligation verdicts:",
    ]
    for name, item in report["obligations"].items():
        marker = {"PROVEN": "[PROVEN]  ", "REFUTED": "[REFUTED] ", "UNRESOLVED": "[UNRESOLVED]"}
        lines.append(f"  {marker[item['verdict']]} {name}: {item['question']}")
        for note in item["notes"]:
            lines.append(f"      note: {note}")
    lines.append("")
    if report["unresolved_blocking"]:
        lines.append("Missing evidence (blocking): " + ", ".join(report["unresolved_blocking"]))
    if report["refuted"]:
        lines.append("Refuted: " + ", ".join(report["refuted"]))
    lines.append("")
    lines.append(f"May act ({report['action']['action']})? {report['action']['may_act']}")
    for reason in report["action"]["reasons"]:
        lines.append(f"  - {reason}")
    recommendation = report["recommendation"]
    if recommendation["recommended"] is not None:
        top = recommendation["recommended"]
        lines.append(
            f"Next authorized experiment: {top['experiment_id']} "
            f"(EVSI {top['evsi']:.2f}, score {top['score']:.2f})"
        )
        lines.append(f"  - {top['rationale']}")
    else:
        lines.append("Next authorized experiment: none")
        lines.append(f"  - {recommendation['rationale']}")
    if recommendation["blocked_by_authorization"]:
        lines.append(
            "Blocked by authorization (never recommended): "
            + ", ".join(recommendation["blocked_by_authorization"])
        )
    lines.append("")
    lines.append("All scores are declared estimates from the experiment catalog.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        import sys

        argv = list(sys.argv[1:])
    report = build_report()
    if "--check" in argv:
        problems = check_report(report)
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1 if problems else 0
    if "--json" in argv:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
