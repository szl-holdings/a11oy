#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Deterministic acceptance fixtures for the Proof-to-Discovery engine.

Every case is prespecified: the bundle is fixed, and the expected verdicts,
action-gate answer, and recommendation are written down here before the
engine runs. The suite must show zero false qualification of known-invalid
evidence across the whole manifest: no corrupted, stale, model-generated,
downgraded, or unregistered-signer record may ever contribute to a PROVEN
verdict or an authorized action.

All keys, instants, and payloads are derived deterministically from constants;
nothing here touches the network, the clock, or the live estate. The fixtures
are synthetic and claim nothing about any real model.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

from .experiments import Experiment
from .graph import Obligation, ObligationGraph
from .policy import AuthorizationGrant, TrustPolicy
from .records import EvidenceRecord

EVALUATED_AT = "2026-11-18T06:00:00Z"
RECENT = "2026-11-18T05:30:00Z"
STALE = "2026-11-18T03:00:00Z"
BOUNDARY = "2026-11-18T05:00:00Z"
BOUNDARY_STALE = "2026-11-18T04:59:59Z"
OWNER_BOUNDARY = "2026-11-18T04:00:00Z"
ANCIENT = "2020-01-01T00:00:00Z"
FUTURE = "2026-11-18T06:30:00Z"

ACTION = "deploy-flagship54"

OWNER_SEED = hashlib.sha256(b"szl-p2d-owner-seed-v1").digest()
WITNESS_SEED = hashlib.sha256(b"szl-p2d-witness-seed-v1").digest()
WITNESS2_SEED = hashlib.sha256(b"szl-p2d-witness-2-seed-v1").digest()
ADVERSARY_SEED = hashlib.sha256(b"szl-p2d-adversary-seed-v1").digest()

from . import ed25519  # noqa: E402  (keys derived after seeds)

OWNER_KEY = ed25519.public_key(OWNER_SEED).hex()
WITNESS_KEY = ed25519.public_key(WITNESS_SEED).hex()
WITNESS2_KEY = ed25519.public_key(WITNESS2_SEED).hex()
ADVERSARY_KEY = ed25519.public_key(ADVERSARY_SEED).hex()

POLICY = TrustPolicy(
    witness_keys=frozenset({WITNESS_KEY, WITNESS2_KEY}),
    owner_keys=frozenset({OWNER_KEY}),
    cost_weight=1.0,
    risk_weight=1.0,
)
RISK_HEAVY_POLICY = TrustPolicy(
    witness_keys=POLICY.witness_keys,
    owner_keys=POLICY.owner_keys,
    cost_weight=1.0,
    risk_weight=100.0,
)

GRANT = AuthorizationGrant.build(
    grant_id="grant-demo-1",
    decision_id="demo-deploy-v1",
    action=ACTION,
    granted_at="2026-11-18T05:00:00Z",
    expires_at="2026-11-18T07:00:00Z",
    owner_seed=OWNER_SEED,
)


def fixture_graph() -> ObligationGraph:
    """The standard five-obligation demo decision used by most cases."""
    return ObligationGraph(
        decision_id="demo-deploy-v1",
        decision_statement="Admit the demonstration model for deployment.",
        decision_value=1_000_000.0,
        obligations=(
            Obligation(
                obligation_id="artifact-integrity",
                question="Is the artifact the exact content it claims to be?",
                required_tier="CONTENT_HASH_BINDING",
                freshness_seconds=3600,
                blocking=True,
            ),
            Obligation(
                obligation_id="adversarial-audit",
                question="Did an independent adversarial audit pass?",
                required_tier="SIGNED_WITNESS",
                freshness_seconds=3600,
                blocking=True,
            ),
            Obligation(
                obligation_id="owner-authorization",
                question="Did the owner authorize this deployment window?",
                required_tier="OWNER_DIRECTIVE",
                freshness_seconds=7200,
                blocking=True,
            ),
            Obligation(
                obligation_id="baseline-comparison",
                question="Does the candidate beat the recorded baseline?",
                required_tier="SIGNED_WITNESS",
                freshness_seconds=None,
                blocking=True,
            ),
            Obligation(
                obligation_id="telemetry-readout",
                question="Is the read-only telemetry readout present?",
                required_tier="CONTENT_HASH_BINDING",
                freshness_seconds=3600,
                blocking=False,
            ),
        ),
    )


def _payload(obligation_id: str, record_id: str) -> dict:
    return {
        "obligation": obligation_id,
        "subject": "fixture-model-demo",
        "statement": f"fixture evidence for {obligation_id} ({record_id})",
    }


def record(
    record_id: str,
    obligation_id: str,
    *,
    stance: str = "supports",
    tier: str = "CONTENT_HASH_BINDING",
    seed: bytes | None = None,
    observed_at: str = RECENT,
) -> EvidenceRecord:
    return EvidenceRecord.build(
        record_id=record_id,
        obligation_id=obligation_id,
        stance=stance,
        witness_tier=tier,
        payload=_payload(obligation_id, record_id),
        observed_at=observed_at,
        signer_seed=seed,
        source_uri="demo://acceptance-fixtures",
    )


def full_valid_bundle() -> dict[str, EvidenceRecord]:
    """One honest record per obligation, each at exactly its required tier."""
    return {
        "r-artifact": record("r-artifact", "artifact-integrity"),
        "r-audit": record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
        "r-owner": record("r-owner", "owner-authorization", tier="OWNER_DIRECTIVE", seed=OWNER_SEED),
        "r-baseline": record(
            "r-baseline", "baseline-comparison", tier="SIGNED_WITNESS", seed=WITNESS2_SEED
        ),
        "r-telemetry": record("r-telemetry", "telemetry-readout"),
    }


def corrupt_payload(item: EvidenceRecord) -> EvidenceRecord:
    return replace(item, payload={**item.payload, "statement": "tampered-after-signing"})


def corrupt_hash(item: EvidenceRecord) -> EvidenceRecord:
    flipped = ("0" if item.content_sha256[-1] != "0" else "1")
    return replace(item, content_sha256=item.content_sha256[:-1] + flipped)


def corrupt_signature(item: EvidenceRecord) -> EvidenceRecord:
    assert item.signature is not None
    flipped = ("0" if item.signature[-1] != "0" else "1")
    return replace(item, signature=item.signature[:-1] + flipped)


@dataclass(frozen=True)
class AcceptanceCase:
    """One prespecified scenario with its expected answers."""

    name: str
    family: str
    graph: ObligationGraph
    records: tuple[EvidenceRecord, ...]
    grant: AuthorizationGrant | None
    action: str
    experiments: tuple[Experiment, ...]
    policy: TrustPolicy
    evaluated_at: str
    expected_verdicts: dict[str, str]
    expected_may_act: bool
    expected_recommendation: str | None
    known_invalid: bool = False


P = "PROVEN"
R = "REFUTED"
U = "UNRESOLVED"

ALL_PROVEN = {
    "artifact-integrity": P,
    "adversarial-audit": P,
    "owner-authorization": P,
    "baseline-comparison": P,
    "telemetry-readout": P,
}


def _case(name, family, records, verdicts, *, grant=GRANT, action=ACTION,
          experiments=(), policy=POLICY, graph=None, recommendation=None,
          known_invalid=False, evaluated_at=EVALUATED_AT):
    return AcceptanceCase(
        name=name,
        family=family,
        graph=graph or fixture_graph(),
        records=tuple(records),
        grant=grant,
        action=action,
        experiments=tuple(experiments),
        policy=policy,
        evaluated_at=evaluated_at,
        expected_verdicts=verdicts,
        expected_may_act=None,  # filled by _finalize below
        expected_recommendation=recommendation,
        known_invalid=known_invalid,
    )


def _expect_act(case: AcceptanceCase, may_act: bool) -> AcceptanceCase:
    return replace(case, expected_may_act=may_act)


def _valid_positive_cases() -> list[AcceptanceCase]:
    full = full_valid_bundle()
    chain_graph = ObligationGraph(
        decision_id="chain-decision-v1",
        decision_statement="Chained demo decision.",
        decision_value=10.0,
        obligations=(
            Obligation("chain-c", "C?", "CONTENT_HASH_BINDING", 3600, True, ("chain-b",)),
            Obligation("chain-b", "B?", "SIGNED_WITNESS", 3600, True, ("chain-a",)),
            Obligation("chain-a", "A?", "CONTENT_HASH_BINDING", 3600, True, ()),
        ),
    )
    chain_records = (
        record("r-chain-a", "chain-a"),
        record("r-chain-b", "chain-b", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
        record("r-chain-c", "chain-c"),
    )
    grant_chain = AuthorizationGrant.build(
        grant_id="grant-chain-1",
        decision_id="chain-decision-v1",
        action=ACTION,
        granted_at="2026-11-18T05:00:00Z",
        expires_at="2026-11-18T07:00:00Z",
        owner_seed=OWNER_SEED,
    )
    cases = [
        _case("valid-all-proven-grant-valid", "valid_positive", full.values(), ALL_PROVEN),
        _expect_act(
            _case("valid-all-proven-no-grant", "valid_positive", full.values(), ALL_PROVEN,
                  grant=None),
            False,
        ),
        _case(
            "valid-owner-directive-covers-witness-obligation",
            "valid_positive",
            [
                record("r-artifact", "artifact-integrity"),
                record("r-audit-owner", "adversarial-audit", tier="OWNER_DIRECTIVE", seed=OWNER_SEED),
                record("r-owner", "owner-authorization", tier="OWNER_DIRECTIVE", seed=OWNER_SEED),
                record("r-baseline", "baseline-comparison", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                record("r-telemetry", "telemetry-readout"),
            ],
            ALL_PROVEN,
        ),
        _case(
            "valid-multiple-supporters",
            "valid_positive",
            [
                record("r-artifact", "artifact-integrity"),
                record("r-audit-1", "adversarial-audit", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                record("r-audit-2", "adversarial-audit", tier="SIGNED_WITNESS", seed=WITNESS2_SEED),
                record("r-audit-3", "adversarial-audit", tier="OWNER_DIRECTIVE", seed=OWNER_SEED),
                record("r-owner", "owner-authorization", tier="OWNER_DIRECTIVE", seed=OWNER_SEED),
                record("r-baseline", "baseline-comparison", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                record("r-telemetry", "telemetry-readout"),
            ],
            ALL_PROVEN,
        ),
        _case(
            "valid-freshness-exact-boundary",
            "valid_positive",
            [
                record("r-artifact", "artifact-integrity", observed_at=BOUNDARY),
                record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                record("r-owner", "owner-authorization", tier="OWNER_DIRECTIVE", seed=OWNER_SEED),
                record("r-baseline", "baseline-comparison", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                record("r-telemetry", "telemetry-readout"),
            ],
            ALL_PROVEN,
        ),
        _case(
            "valid-signed-witness-covers-hash-obligation",
            "valid_positive",
            [
                record("r-artifact-signed", "artifact-integrity", tier="SIGNED_WITNESS",
                       seed=WITNESS_SEED),
                record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                record("r-owner", "owner-authorization", tier="OWNER_DIRECTIVE", seed=OWNER_SEED),
                record("r-baseline", "baseline-comparison", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                record("r-telemetry", "telemetry-readout"),
            ],
            ALL_PROVEN,
        ),
        _case(
            "valid-non-blocking-missing-still-acts",
            "valid_positive",
            [full["r-artifact"], full["r-audit"], full["r-owner"], full["r-baseline"]],
            {**{key: value for key, value in ALL_PROVEN.items() if key != "telemetry-readout"},
             "telemetry-readout": U},
        ),
        _case(
            "valid-no-freshness-bound-ancient-evidence",
            "valid_positive",
            [
                record("r-artifact", "artifact-integrity"),
                record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                record("r-owner", "owner-authorization", tier="OWNER_DIRECTIVE", seed=OWNER_SEED),
                record("r-baseline", "baseline-comparison", tier="SIGNED_WITNESS",
                       seed=WITNESS_SEED, observed_at=ANCIENT),
                record("r-telemetry", "telemetry-readout"),
            ],
            ALL_PROVEN,
        ),
        _case(
            "valid-dependency-chain-proven",
            "valid_positive",
            chain_records,
            {"chain-a": P, "chain-b": P, "chain-c": P},
            graph=chain_graph,
            grant=grant_chain,
        ),
        _case(
            "valid-owner-directive-covers-hash-obligation",
            "valid_positive",
            [
                record("r-artifact-owner", "artifact-integrity", tier="OWNER_DIRECTIVE",
                       seed=OWNER_SEED),
                record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                record("r-owner", "owner-authorization", tier="OWNER_DIRECTIVE", seed=OWNER_SEED),
                record("r-baseline", "baseline-comparison", tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                record("r-telemetry", "telemetry-readout"),
            ],
            ALL_PROVEN,
        ),
        _case(
            "valid-second-registered-witness",
            "valid_positive",
            [
                full["r-artifact"],
                record("r-audit-2", "adversarial-audit", tier="SIGNED_WITNESS",
                       seed=WITNESS2_SEED),
                full["r-owner"],
                full["r-baseline"],
                full["r-telemetry"],
            ],
            ALL_PROVEN,
        ),
        _case(
            "valid-grant-exactly-in-force-now",
            "valid_positive",
            full.values(),
            ALL_PROVEN,
            grant=AuthorizationGrant.build(
                grant_id="grant-edge",
                decision_id="demo-deploy-v1",
                action=ACTION,
                granted_at=EVALUATED_AT,
                expires_at="2026-11-18T07:00:00Z",
                owner_seed=OWNER_SEED,
            ),
        ),
        _case(
            "valid-owner-boundary-fresh",
            "valid_positive",
            [
                full["r-artifact"],
                full["r-audit"],
                record("r-owner-b", "owner-authorization", tier="OWNER_DIRECTIVE",
                       seed=OWNER_SEED, observed_at=OWNER_BOUNDARY),
                full["r-baseline"],
                full["r-telemetry"],
            ],
            ALL_PROVEN,
        ),
    ]
    # Duplicate determinism case: identical evaluation twice.
    cases.append(
        _case(
            "valid-deterministic-rerun",
            "valid_positive",
            full.values(),
            ALL_PROVEN,
        )
    )
    # Grant covers a different action only when evaluated for that action.
    cases.append(
        _expect_act(
            _case(
                "valid-grant-other-action-refused",
                "valid_positive",
                full.values(),
                ALL_PROVEN,
                action="delete-model",
            ),
            False,
        )
    )
    return cases


def _refuted_cases() -> list[AcceptanceCase]:
    full = full_valid_bundle()
    refuter = record("r-audit-refuter", "adversarial-audit", stance="refutes",
                     tier="SIGNED_WITNESS", seed=WITNESS_SEED)
    chain_graph = ObligationGraph(
        decision_id="chain-decision-v1",
        decision_statement="Chained demo decision.",
        decision_value=10.0,
        obligations=(
            Obligation("chain-c", "C?", "CONTENT_HASH_BINDING", 3600, True, ("chain-b",)),
            Obligation("chain-b", "B?", "SIGNED_WITNESS", 3600, True, ()),
        ),
    )
    return [
        _case(
            "refuted-signed-refuter-blocks-action",
            "refuted",
            [full["r-artifact"], refuter, full["r-owner"], full["r-baseline"],
             full["r-telemetry"]],
            {**ALL_PROVEN, "adversarial-audit": R},
            known_invalid=True,
        ),
        _case(
            "refuted-refuter-wins-over-supporter",
            "refuted",
            [full["r-artifact"], full["r-audit"], refuter, full["r-owner"],
             full["r-baseline"], full["r-telemetry"]],
            {**ALL_PROVEN, "adversarial-audit": R},
            known_invalid=True,
        ),
        _case(
            "refuted-hash-refuter-on-hash-obligation",
            "refuted",
            [record("r-artifact-refuter", "artifact-integrity", stance="refutes"),
             full["r-audit"], full["r-owner"], full["r-baseline"], full["r-telemetry"]],
            {**ALL_PROVEN, "artifact-integrity": R},
            known_invalid=True,
        ),
        _case(
            "refuted-owner-refuter-covers-witness-obligation",
            "refuted",
            [full["r-artifact"], full["r-audit"],
             record("r-audit-owner-refuter", "adversarial-audit", stance="refutes",
                    tier="OWNER_DIRECTIVE", seed=OWNER_SEED),
             full["r-owner"], full["r-baseline"], full["r-telemetry"]],
            {**ALL_PROVEN, "adversarial-audit": R},
            known_invalid=True,
        ),
        _expect_act(
            _case(
                "refuted-non-blocking-refuter-blocks-action",
                "refuted",
                [full["r-artifact"], full["r-audit"], full["r-owner"], full["r-baseline"],
                 record("r-telemetry-refuter", "telemetry-readout", stance="refutes")],
                {**ALL_PROVEN, "telemetry-readout": R},
            ),
            False,
        ),
        _case(
            "refuted-stale-supporter-fresh-refuter",
            "refuted",
            [full["r-artifact"],
             record("r-audit-old", "adversarial-audit", tier="SIGNED_WITNESS",
                    seed=WITNESS_SEED, observed_at=STALE),
             record("r-audit-refuter", "adversarial-audit", stance="refutes",
                    tier="SIGNED_WITNESS", seed=WITNESS_SEED),
             full["r-owner"], full["r-baseline"], full["r-telemetry"]],
            {**ALL_PROVEN, "adversarial-audit": R},
            known_invalid=True,
        ),
        _case(
            "refuted-stale-refuter-inadmissible-supporter-fresh",
            "refuted",
            [full["r-artifact"], full["r-audit"],
             record("r-audit-refuter-stale", "adversarial-audit", stance="refutes",
                    tier="SIGNED_WITNESS", seed=WITNESS_SEED, observed_at=STALE),
             full["r-owner"], full["r-baseline"], full["r-telemetry"]],
            ALL_PROVEN,
        ),
        _case(
            "refuted-plus-missing-obligation",
            "refuted",
            [full["r-artifact"], refuter, full["r-baseline"], full["r-telemetry"]],
            {"artifact-integrity": P, "adversarial-audit": R, "baseline-comparison": P,
             "telemetry-readout": P, "owner-authorization": U},
            known_invalid=True,
        ),
        _case(
            "refuted-witness-refuter-below-owner-requirement",
            "refuted",
            [full["r-artifact"], full["r-audit"],
             record("r-owner-refuter", "owner-authorization", stance="refutes",
                    tier="SIGNED_WITNESS", seed=WITNESS_SEED),
             full["r-baseline"], full["r-telemetry"]],
            {**ALL_PROVEN, "owner-authorization": U},
            known_invalid=True,
        ),
        _case(
            "refuted-two-refuters",
            "refuted",
            [full["r-artifact"], refuter,
             record("r-audit-refuter-2", "adversarial-audit", stance="refutes",
                    tier="SIGNED_WITNESS", seed=WITNESS2_SEED),
             full["r-owner"], full["r-baseline"], full["r-telemetry"]],
            {**ALL_PROVEN, "adversarial-audit": R},
            known_invalid=True,
        ),
        _case(
            "refuted-dependency-blocks-dependent",
            "refuted",
            [
                record("r-chain-c", "chain-c"),
                record("r-chain-b-refuter", "chain-b", stance="refutes",
                       tier="SIGNED_WITNESS", seed=WITNESS_SEED),
            ],
            {"chain-b": R, "chain-c": U},
            graph=chain_graph,
            known_invalid=True,
        ),
        _expect_act(
            _case(
                "refuted-without-grant",
                "refuted",
                [full["r-artifact"], refuter, full["r-owner"], full["r-baseline"],
                 full["r-telemetry"]],
                {**ALL_PROVEN, "adversarial-audit": R},
                grant=None,
            ),
            False,
        ),
        _case(
            "refuted-refuter-at-exact-boundary",
            "refuted",
            [full["r-artifact"],
             record("r-audit-refuter-b", "adversarial-audit", stance="refutes",
                    tier="SIGNED_WITNESS", seed=WITNESS_SEED, observed_at=BOUNDARY),
             full["r-owner"], full["r-baseline"], full["r-telemetry"]],
            {**ALL_PROVEN, "adversarial-audit": R},
            known_invalid=True,
        ),
        _case(
            "refuted-model-refuter-ignored",
            "refuted",
            [full["r-artifact"],
             record("r-audit-model-refuter", "adversarial-audit", stance="refutes",
                    tier="MODEL_GENERATED"),
             full["r-audit"], full["r-owner"], full["r-baseline"], full["r-telemetry"]],
            ALL_PROVEN,
        ),
        _case(
            "refuted-recommender-refuses-sampling",
            "refuted",
            [full["r-artifact"], refuter, full["r-owner"], full["r-baseline"],
             full["r-telemetry"]],
            {**ALL_PROVEN, "adversarial-audit": R},
            experiments=(Experiment("exp-audit", ("adversarial-audit",),
                                    {"adversarial-audit": 0.9}, 100.0, 0.01, True),),
            recommendation=None,
            known_invalid=True,
        ),
    ]


def _stale_cases() -> list[AcceptanceCase]:
    full = full_valid_bundle()

    def bundle(overrides: dict | None = None) -> list[EvidenceRecord]:
        merged = dict(full)
        if overrides:
            merged.update(overrides)
        return list(merged.values())

    return [
        _expect_act(
            _case(
                "stale-all-supporters",
                "stale",
                [
                    record("r-artifact", "artifact-integrity", observed_at=STALE),
                    record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS",
                           seed=WITNESS_SEED, observed_at=STALE),
                    record("r-owner", "owner-authorization", tier="OWNER_DIRECTIVE",
                           seed=OWNER_SEED, observed_at=STALE),
                    record("r-baseline", "baseline-comparison", tier="SIGNED_WITNESS",
                           seed=WITNESS_SEED, observed_at=STALE),
                    record("r-telemetry", "telemetry-readout", observed_at=STALE),
                ],
                {**ALL_PROVEN, "artifact-integrity": U, "adversarial-audit": U,
                 "owner-authorization": U, "telemetry-readout": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "stale-single-blocking-obligation",
                "stale",
                bundle({"r-audit": record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS",
                                     seed=WITNESS_SEED, observed_at=STALE)}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "stale-one-second-past-boundary",
                "stale",
                bundle({"r-artifact": record("r-artifact", "artifact-integrity",
                                         observed_at=BOUNDARY_STALE)}),
                {**ALL_PROVEN, "artifact-integrity": U},
                known_invalid=True,
            ),
            False,
        ),
        _case(
            "stale-witness-at-exact-boundary-fresh",
            "stale",
            bundle({"r-audit": record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS",
                                  seed=WITNESS_SEED, observed_at=BOUNDARY)}),
            ALL_PROVEN,
        ),
        _case(
            "stale-no-bound-never-stale",
            "stale",
            bundle({"r-baseline": record("r-baseline", "baseline-comparison",
                                     tier="SIGNED_WITNESS", seed=WITNESS_SEED,
                                     observed_at=ANCIENT)}),
            ALL_PROVEN,
        ),
        _case(
            "stale-non-blocking-does-not-gate-action",
            "stale",
            bundle({"r-telemetry": record("r-telemetry", "telemetry-readout", observed_at=STALE)}),
            {**ALL_PROVEN, "telemetry-readout": U},
        ),
        _case(
            "stale-supporter-fresh-supporter-same-obligation",
            "stale",
            [
                full["r-artifact"],
                record("r-audit-stale", "adversarial-audit", tier="SIGNED_WITNESS",
                       seed=WITNESS_SEED, observed_at=STALE),
                full["r-audit"],
                full["r-owner"],
                full["r-baseline"],
                full["r-telemetry"],
            ],
            ALL_PROVEN,
        ),
        _expect_act(
            _case(
                "stale-owner-directive",
                "stale",
                bundle({"r-owner": record("r-owner", "owner-authorization", tier="OWNER_DIRECTIVE",
                                      seed=OWNER_SEED, observed_at=STALE)}),
                {**ALL_PROVEN, "owner-authorization": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "stale-future-observation-refused",
                "stale",
                bundle({"r-audit": record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS",
                                      seed=WITNESS_SEED, observed_at=FUTURE)}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "stale-unparseable-instant",
                "stale",
                bundle({"r-audit": record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS",
                                      seed=WITNESS_SEED, observed_at="2026-11-18 05:30:00")}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "stale-duplicate-id-keeps-first-record",
                "stale",
                [
                    full["r-artifact"],
                    record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS",
                           seed=WITNESS_SEED, observed_at=STALE),
                    record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS",
                           seed=WITNESS_SEED),
                    full["r-owner"],
                    full["r-baseline"],
                    full["r-telemetry"],
                ],
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _case(
            "stale-refuter-ignored-when-supporter-fresh",
            "stale",
            [
                full["r-artifact"],
                record("r-audit-refuter-stale", "adversarial-audit", stance="refutes",
                       tier="SIGNED_WITNESS", seed=WITNESS_SEED, observed_at=STALE),
                full["r-audit"],
                full["r-owner"],
                full["r-baseline"],
                full["r-telemetry"],
            ],
            ALL_PROVEN,
        ),
        _expect_act(
            _case(
                "stale-mixed-across-obligations",
                "stale",
                bundle({"r-audit": record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS",
                                      seed=WITNESS_SEED, observed_at=STALE)}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _case(
            "stale-owner-boundary-exact-fresh",
            "stale",
            bundle({"r-owner": record("r-owner", "owner-authorization", tier="OWNER_DIRECTIVE",
                                  seed=OWNER_SEED, observed_at=OWNER_BOUNDARY)}),
            ALL_PROVEN,
        ),
        _expect_act(
            _case(
                "stale-all-supporters-valid-grant-refused",
                "stale",
                [
                    record("r-artifact", "artifact-integrity", observed_at=STALE),
                    record("r-audit", "adversarial-audit", tier="SIGNED_WITNESS",
                           seed=WITNESS_SEED, observed_at=STALE),
                    record("r-owner", "owner-authorization", tier="OWNER_DIRECTIVE",
                           seed=OWNER_SEED, observed_at=STALE),
                    record("r-baseline", "baseline-comparison", tier="SIGNED_WITNESS",
                           seed=WITNESS_SEED, observed_at=STALE),
                    record("r-telemetry", "telemetry-readout", observed_at=STALE),
                ],
                {**ALL_PROVEN, "artifact-integrity": U, "adversarial-audit": U,
                 "owner-authorization": U, "telemetry-readout": U},
            ),
            False,
        ),
    ]


def _corrupted_cases() -> list[AcceptanceCase]:
    full = full_valid_bundle()

    def bundle(overrides: dict | None = None) -> list[EvidenceRecord]:
        merged = dict(full)
        if overrides:
            merged.update(overrides)
        return list(merged.values())

    tampered_audit = corrupt_payload(full["r-audit"])
    return [
        _expect_act(
            _case(
                "corrupted-payload-tampered-after-signing",
                "corrupted",
                bundle({"r-audit": tampered_audit}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "corrupted-hash-field-tampered",
                "corrupted",
                bundle({"r-artifact": corrupt_hash(full["r-artifact"])}),
                {**ALL_PROVEN, "artifact-integrity": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "corrupted-signature-tampered",
                "corrupted",
                bundle({"r-audit": corrupt_signature(full["r-audit"])}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "corrupted-hash-bound-payload-tampered",
                "corrupted",
                bundle({"r-artifact": corrupt_payload(full["r-artifact"])}),
                {**ALL_PROVEN, "artifact-integrity": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "corrupted-signature-truncated",
                "corrupted",
                bundle({"r-audit": replace(full["r-audit"], signature=full["r-audit"].signature[:-2])}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "corrupted-signer-key-swapped-to-registered-peer",
                "corrupted",
                bundle({"r-audit": replace(full["r-audit"], signer_key=WITNESS2_KEY)}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "corrupted-hash-tier-carrying-signature",
                "corrupted",
                bundle({"r-artifact": replace(
                    record("r-artifact-signed", "artifact-integrity", tier="SIGNED_WITNESS",
                           seed=WITNESS_SEED),
                    witness_tier="CONTENT_HASH_BINDING")}),
                {**ALL_PROVEN, "artifact-integrity": U},
                known_invalid=True,
            ),
            False,
        ),
        _case(
            "corrupted-refuter-inadmissible-supporter-stands",
            "corrupted",
            [
                full["r-artifact"],
                corrupt_payload(record("r-audit-refuter", "adversarial-audit", stance="refutes",
                                       tier="SIGNED_WITNESS", seed=WITNESS_SEED)),
                full["r-audit"],
                full["r-owner"],
                full["r-baseline"],
                full["r-telemetry"],
            ],
            ALL_PROVEN,
        ),
        _case(
            "corrupted-non-blocking-does-not-gate-action",
            "corrupted",
            bundle({"r-telemetry": corrupt_hash(full["r-telemetry"])}),
            {**ALL_PROVEN, "telemetry-readout": U},
        ),
        _expect_act(
            _case(
                "corrupted-unregistered-signer",
                "corrupted",
                bundle({"r-audit": record("r-audit-adv", "adversarial-audit",
                                      tier="SIGNED_WITNESS", seed=ADVERSARY_SEED)}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "corrupted-unknown-witness-tier",
                "corrupted",
                bundle({"r-artifact": replace(full["r-artifact"], witness_tier="APPROXIMATE_TRUST")}),
                {**ALL_PROVEN, "artifact-integrity": U},
                known_invalid=True,
            ),
            False,
        ),
        _case(
            "corrupted-unknown-obligation-record-ignored",
            "corrupted",
            [
                full["r-artifact"],
                full["r-audit"],
                replace(full["r-audit"], record_id="r-unknown-obligation",
                        obligation_id="obligation-99"),
                full["r-owner"],
                full["r-baseline"],
                full["r-telemetry"],
            ],
            ALL_PROVEN,
        ),
        _expect_act(
            _case(
                "corrupted-unknown-stance",
                "corrupted",
                bundle({"r-audit": replace(full["r-audit"], stance="asserts")}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _case(
            "corrupted-duplicate-identical-records-ignored",
            "corrupted",
            [full["r-artifact"], full["r-audit"], full["r-audit"], full["r-owner"],
             full["r-baseline"], full["r-telemetry"]],
            ALL_PROVEN,
        ),
        _expect_act(
            _case(
                "corrupted-tier-swap-breaks-signature",
                "corrupted",
                bundle({"r-audit": replace(full["r-audit"], witness_tier="OWNER_DIRECTIVE")}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
    ]


def _missing_cases() -> list[AcceptanceCase]:
    full = full_valid_bundle()
    chain_graph = ObligationGraph(
        decision_id="chain-decision-v1",
        decision_statement="Chained demo decision.",
        decision_value=10.0,
        obligations=(
            Obligation("chain-c", "C?", "CONTENT_HASH_BINDING", 3600, True, ("chain-b",)),
            Obligation("chain-b", "B?", "SIGNED_WITNESS", 3600, True, ()),
        ),
    )
    return [
        _expect_act(
            _case("missing-no-records-at-all", "missing", [], {key: U for key in ALL_PROVEN}),
            False,
        ),
        _expect_act(
            _case(
                "missing-one-blocking-obligation",
                "missing",
                [full["r-artifact"], full["r-audit"], full["r-baseline"], full["r-telemetry"]],
                {**ALL_PROVEN, "owner-authorization": U},
            ),
            False,
        ),
        _case(
            "missing-non-blocking-still-acts",
            "missing",
            [full["r-artifact"], full["r-audit"], full["r-owner"], full["r-baseline"]],
            {**ALL_PROVEN, "telemetry-readout": U},
        ),
        _expect_act(
            _case(
                "missing-everything-no-grant",
                "missing",
                [],
                {key: U for key in ALL_PROVEN},
                grant=None,
            ),
            False,
        ),
        _expect_act(
            _case(
                "missing-only-model-claims-present",
                "missing",
                [
                    record("r-m1", "artifact-integrity", tier="MODEL_GENERATED"),
                    record("r-m2", "adversarial-audit", tier="MODEL_GENERATED"),
                    record("r-m3", "owner-authorization", tier="MODEL_GENERATED"),
                    record("r-m4", "baseline-comparison", tier="MODEL_GENERATED"),
                    record("r-m5", "telemetry-readout", tier="MODEL_GENERATED"),
                ],
                {key: U for key in ALL_PROVEN},
            ),
            False,
        ),
        _case(
            "missing-with-experiment-recommendation",
            "missing",
            [full["r-artifact"], full["r-baseline"], full["r-telemetry"]],
            {**ALL_PROVEN, "adversarial-audit": U, "owner-authorization": U},
            experiments=(
                Experiment("exp-full", ("adversarial-audit", "owner-authorization"),
                           {"adversarial-audit": 0.7, "owner-authorization": 0.9},
                           500.0, 0.05, True),
            ),
            recommendation="exp-full",
        ),
        _expect_act(
            _case(
                "missing-dependency-unresolved-propagates",
                "missing",
                [record("r-chain-c", "chain-c")],
                {"chain-b": U, "chain-c": U},
                graph=chain_graph,
            ),
            False,
        ),
        _expect_act(
            _case(
                "missing-partial-mix",
                "missing",
                [full["r-artifact"], full["r-audit"], full["r-baseline"], full["r-telemetry"]],
                {**ALL_PROVEN, "owner-authorization": U},
            ),
            False,
        ),
        _expect_act(
            _case(
                "missing-no-bound-obligation-still-unresolved",
                "missing",
                [full["r-artifact"], full["r-audit"], full["r-owner"], full["r-telemetry"]],
                {**ALL_PROVEN, "baseline-comparison": U},
            ),
            False,
        ),
        _expect_act(
            _case(
                "missing-grant-is-the-only-difference",
                "missing",
                [full["r-artifact"], full["r-audit"], full["r-baseline"], full["r-telemetry"]],
                {**ALL_PROVEN, "owner-authorization": U},
            ),
            False,
        ),
    ]


def _model_claim_cases() -> list[AcceptanceCase]:
    full = full_valid_bundle()
    return [
        _expect_act(
            _case(
                "model-supporters-everywhere-never-qualify",
                "model_claim_only",
                [
                    record("r-m1", "artifact-integrity", tier="MODEL_GENERATED"),
                    record("r-m2", "adversarial-audit", tier="MODEL_GENERATED"),
                    record("r-m3", "owner-authorization", tier="MODEL_GENERATED"),
                    record("r-m4", "baseline-comparison", tier="MODEL_GENERATED"),
                    record("r-m5", "telemetry-readout", tier="MODEL_GENERATED"),
                ],
                {key: U for key in ALL_PROVEN},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "model-refuter-never-refutes",
                "model_claim_only",
                [full["r-artifact"],
                 record("r-m-refuter", "adversarial-audit", stance="refutes",
                        tier="MODEL_GENERATED"),
                 full["r-owner"], full["r-baseline"], full["r-telemetry"]],
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _case(
            "model-plus-signed-supporter",
            "model_claim_only",
            [
                full["r-artifact"],
                record("r-m-audit", "adversarial-audit", tier="MODEL_GENERATED"),
                full["r-audit"],
                full["r-owner"],
                full["r-baseline"],
                full["r-telemetry"],
            ],
            ALL_PROVEN,
        ),
        _expect_act(
            _case(
                "model-below-signed-requirement",
                "model_claim_only",
                [full["r-artifact"],
                 record("r-m-audit", "adversarial-audit", tier="MODEL_GENERATED"),
                 full["r-owner"], full["r-baseline"], full["r-telemetry"]],
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "model-below-owner-requirement",
                "model_claim_only",
                [full["r-artifact"], full["r-audit"],
                 record("r-m-owner", "owner-authorization", tier="MODEL_GENERATED"),
                 full["r-baseline"], full["r-telemetry"]],
                {**ALL_PROVEN, "owner-authorization": U},
                known_invalid=True,
            ),
            False,
        ),
        _case(
            "model-refuter-plus-real-refuter-refutes",
            "model_claim_only",
            [
                full["r-artifact"],
                record("r-m-refuter", "adversarial-audit", stance="refutes",
                       tier="MODEL_GENERATED"),
                record("r-refuter", "adversarial-audit", stance="refutes",
                       tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                full["r-owner"],
                full["r-baseline"],
                full["r-telemetry"],
            ],
            {**ALL_PROVEN, "adversarial-audit": R},
        ),
        _case(
            "model-only-on-non-blocking",
            "model_claim_only",
            [
                full["r-artifact"],
                full["r-audit"],
                full["r-owner"],
                full["r-baseline"],
                record("r-m-telemetry", "telemetry-readout", tier="MODEL_GENERATED"),
            ],
            {**ALL_PROVEN, "telemetry-readout": U},
        ),
        _expect_act(
            _case(
                "model-record-with-spoofed-signature-still-annotation",
                "model_claim_only",
                [
                    replace(
                        record("r-m-spoof", "adversarial-audit", tier="MODEL_GENERATED"),
                        signature=full["r-audit"].signature,
                        signer_key=WITNESS_KEY,
                    ),
                    full["r-artifact"],
                    full["r-owner"],
                    full["r-baseline"],
                    full["r-telemetry"],
                ],
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _case(
            "model-supporters-excluded-from-receipts",
            "model_claim_only",
            [
                full["r-artifact"],
                record("r-m-audit", "adversarial-audit", tier="MODEL_GENERATED"),
                full["r-audit"],
                full["r-owner"],
                full["r-baseline"],
                full["r-telemetry"],
            ],
            ALL_PROVEN,
        ),
        _expect_act(
            _case(
                "model-everywhere-except-one-hash-record",
                "model_claim_only",
                [
                    full["r-artifact"],
                    record("r-m2", "adversarial-audit", tier="MODEL_GENERATED"),
                    record("r-m3", "owner-authorization", tier="MODEL_GENERATED"),
                    record("r-m4", "baseline-comparison", tier="MODEL_GENERATED"),
                    record("r-m5", "telemetry-readout", tier="MODEL_GENERATED"),
                ],
                {"artifact-integrity": P, "adversarial-audit": U, "owner-authorization": U,
                 "baseline-comparison": U, "telemetry-readout": U},
                known_invalid=True,
            ),
            False,
        ),
    ]


def _downgrade_cases() -> list[AcceptanceCase]:
    full = full_valid_bundle()

    def bundle(overrides: dict | None = None) -> list[EvidenceRecord]:
        merged = dict(full)
        if overrides:
            merged.update(overrides)
        return list(merged.values())

    return [
        _expect_act(
            _case(
                "downgrade-hash-bound-against-witness-requirement",
                "downgrade_tier",
                bundle({"r-audit": record("r-audit-hash", "adversarial-audit")}),
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "downgrade-hash-bound-against-owner-requirement",
                "downgrade_tier",
                bundle({"r-owner": record("r-owner-hash", "owner-authorization")}),
                {**ALL_PROVEN, "owner-authorization": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "downgrade-signed-witness-against-owner-requirement",
                "downgrade_tier",
                bundle({"r-owner": record("r-owner-signed", "owner-authorization",
                                      tier="SIGNED_WITNESS", seed=WITNESS_SEED)}),
                {**ALL_PROVEN, "owner-authorization": U},
                known_invalid=True,
            ),
            False,
        ),
        _case(
            "upgrade-owner-directive-covers-witness-requirement",
            "downgrade_tier",
            bundle({"r-audit": record("r-audit-owner", "adversarial-audit",
                                  tier="OWNER_DIRECTIVE", seed=OWNER_SEED)}),
            ALL_PROVEN,
        ),
        _case(
            "upgrade-owner-directive-covers-hash-requirement",
            "downgrade_tier",
            bundle({"r-artifact": record("r-artifact-owner", "artifact-integrity",
                                     tier="OWNER_DIRECTIVE", seed=OWNER_SEED)}),
            ALL_PROVEN,
        ),
        _case(
            "upgrade-signed-witness-covers-hash-requirement",
            "downgrade_tier",
            bundle({"r-artifact": record("r-artifact-signed", "artifact-integrity",
                                     tier="SIGNED_WITNESS", seed=WITNESS_SEED)}),
            ALL_PROVEN,
        ),
        _expect_act(
            _case(
                "downgrade-many-weak-records-still-unresolved",
                "downgrade_tier",
                [
                    full["r-artifact"],
                    full["r-owner"],
                    full["r-baseline"],
                    full["r-telemetry"],
                    record("r-audit-w1", "adversarial-audit"),
                    record("r-audit-w2", "adversarial-audit"),
                    record("r-audit-w3", "adversarial-audit"),
                    record("r-audit-w4", "adversarial-audit"),
                    record("r-audit-w5", "adversarial-audit"),
                ],
                {**ALL_PROVEN, "adversarial-audit": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "downgrade-model-against-lowest-requirement",
                "downgrade_tier",
                bundle({"r-artifact": record("r-artifact-model", "artifact-integrity",
                                         tier="MODEL_GENERATED")}),
                {**ALL_PROVEN, "artifact-integrity": U},
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "downgrade-mixed-upgrade-and-downgrade",
                "downgrade_tier",
                bundle({
                    "r-audit": record("r-audit-owner", "adversarial-audit",
                                      tier="OWNER_DIRECTIVE", seed=OWNER_SEED),
                    "r-owner": record("r-owner-signed", "owner-authorization",
                                      tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                }),
                {**ALL_PROVEN, "owner-authorization": U},
                known_invalid=True,
            ),
            False,
        ),
        _case(
            "exact-tier-match-everywhere",
            "downgrade_tier",
            list(full_valid_bundle().values()),
            ALL_PROVEN,
        ),
    ]


def _authorization_cases() -> list[AcceptanceCase]:
    full = full_valid_bundle()
    records = list(full.values())

    def grant_with(**fields) -> AuthorizationGrant:
        base = {
            "grant_id": "grant-test",
            "decision_id": "demo-deploy-v1",
            "action": ACTION,
            "granted_at": "2026-11-18T05:00:00Z",
            "expires_at": "2026-11-18T07:00:00Z",
            "owner_seed": OWNER_SEED,
        }
        base.update(fields)
        return AuthorizationGrant.build(**base)

    forged = AuthorizationGrant.build(
        grant_id="grant-forged",
        decision_id="demo-deploy-v1",
        action=ACTION,
        granted_at="2026-11-18T05:00:00Z",
        expires_at="2026-11-18T07:00:00Z",
        owner_seed=ADVERSARY_SEED,
    )
    tampered = replace(grant_with(), action="delete-everything")
    return [
        _expect_act(
            _case("auth-no-grant", "authorization", records, ALL_PROVEN, grant=None),
            False,
        ),
        _case("auth-valid-grant", "authorization", records, ALL_PROVEN,
              grant=grant_with()),
        _expect_act(
            _case("auth-forged-grant-adversary-key", "authorization", records, ALL_PROVEN,
                  grant=forged, known_invalid=True),
            False,
        ),
        _expect_act(
            _case(
                "auth-grant-signed-by-witness-not-owner",
                "authorization",
                records,
                ALL_PROVEN,
                grant=AuthorizationGrant.build(
                    grant_id="grant-witness",
                    decision_id="demo-deploy-v1",
                    action=ACTION,
                    granted_at="2026-11-18T05:00:00Z",
                    expires_at="2026-11-18T07:00:00Z",
                    owner_seed=WITNESS_SEED,
                ),
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "auth-expired-grant-one-second",
                "authorization",
                records,
                ALL_PROVEN,
                grant=grant_with(expires_at="2026-11-18T05:59:59Z"),
            ),
            False,
        ),
        _expect_act(
            _case(
                "auth-grant-for-other-decision",
                "authorization",
                records,
                ALL_PROVEN,
                grant=grant_with(decision_id="other-decision-v1"),
            ),
            False,
        ),
        _expect_act(
            _case(
                "auth-grant-for-other-action",
                "authorization",
                records,
                ALL_PROVEN,
                grant=grant_with(action="provision-preview"),
            ),
            False,
        ),
        _expect_act(
            _case(
                "auth-tampered-grant-payload",
                "authorization",
                records,
                ALL_PROVEN,
                grant=tampered,
                known_invalid=True,
            ),
            False,
        ),
        _expect_act(
            _case(
                "auth-grant-not-yet-in-force",
                "authorization",
                records,
                ALL_PROVEN,
                grant=grant_with(granted_at="2026-11-18T06:30:00Z"),
            ),
            False,
        ),
        _expect_act(
            _case(
                "auth-valid-grant-but-obligation-unresolved",
                "authorization",
                [full["r-artifact"], full["r-audit"], full["r-baseline"], full["r-telemetry"]],
                {**ALL_PROVEN, "owner-authorization": U},
                grant=grant_with(),
            ),
            False,
        ),
    ]


def _evsi_cases() -> list[AcceptanceCase]:
    full = full_valid_bundle()
    unresolved = [full["r-artifact"], full["r-baseline"], full["r-telemetry"]]
    verdicts_two = {**ALL_PROVEN, "adversarial-audit": U, "owner-authorization": U}

    def exp(experiment_id, resolves, probabilities, cost, risk, authorized=True):
        return Experiment(experiment_id, tuple(resolves), probabilities, cost, risk, authorized)

    return [
        _case(
            "evsi-single-completing-experiment",
            "evsi",
            unresolved,
            verdicts_two,
            experiments=(exp("exp-full", ("adversarial-audit", "owner-authorization"),
                             {"adversarial-audit": 0.8, "owner-authorization": 0.5},
                             100.0, 0.01),),
            recommendation="exp-full",
        ),
        _case(
            "evsi-cost-tradeoff-picks-cheaper",
            "evsi",
            unresolved,
            verdicts_two,
            experiments=(
                exp("exp-a", ("adversarial-audit", "owner-authorization"),
                    {"adversarial-audit": 0.5, "owner-authorization": 0.5}, 1000.0, 0.0),
                exp("exp-b", ("adversarial-audit", "owner-authorization"),
                    {"adversarial-audit": 0.5, "owner-authorization": 0.5}, 100.0, 0.0),
            ),
            recommendation="exp-b",
        ),
        _case(
            "evsi-risk-weight-flips-winner",
            "evsi",
            unresolved,
            verdicts_two,
            experiments=(
                exp("exp-c", ("adversarial-audit", "owner-authorization"),
                    {"adversarial-audit": 0.9, "owner-authorization": 0.9}, 100.0, 6000.0),
                exp("exp-d", ("adversarial-audit", "owner-authorization"),
                    {"adversarial-audit": 0.5, "owner-authorization": 0.5}, 100.0, 0.001),
            ),
            policy=RISK_HEAVY_POLICY,
            recommendation="exp-d",
        ),
        _case(
            "evsi-unauthorized-never-recommended",
            "evsi",
            unresolved,
            verdicts_two,
            experiments=(
                exp("exp-top", ("adversarial-audit", "owner-authorization"),
                    {"adversarial-audit": 0.9, "owner-authorization": 0.9}, 100.0, 0.01,
                    authorized=False),
                exp("exp-ok", ("adversarial-audit", "owner-authorization"),
                    {"adversarial-audit": 0.5, "owner-authorization": 0.5}, 100.0, 0.01),
            ),
            recommendation="exp-ok",
        ),
        _case(
            "evsi-no-completing-experiment",
            "evsi",
            unresolved,
            verdicts_two,
            experiments=(exp("exp-partial", ("adversarial-audit",),
                             {"adversarial-audit": 0.9}, 50.0, 0.0),),
            recommendation=None,
        ),
        _case(
            "evsi-deterministic-tie-break",
            "evsi",
            unresolved,
            verdicts_two,
            experiments=(
                exp("exp-y", ("adversarial-audit", "owner-authorization"),
                    {"adversarial-audit": 0.5, "owner-authorization": 0.5}, 100.0, 0.0),
                exp("exp-x", ("adversarial-audit", "owner-authorization"),
                    {"adversarial-audit": 0.5, "owner-authorization": 0.5}, 100.0, 0.0),
            ),
            recommendation="exp-x",
        ),
        _case(
            "evsi-all-proven-no-experiment-needed",
            "evsi",
            list(full.values()),
            ALL_PROVEN,
            experiments=(exp("exp-any", ("adversarial-audit",),
                             {"adversarial-audit": 0.9}, 1.0, 0.0),),
            recommendation=None,
        ),
        _case(
            "evsi-refuted-no-recommendation",
            "evsi",
            [
                full["r-artifact"],
                record("r-audit-refuter", "adversarial-audit", stance="refutes",
                       tier="SIGNED_WITNESS", seed=WITNESS_SEED),
                full["r-owner"],
                full["r-baseline"],
                full["r-telemetry"],
            ],
            {**ALL_PROVEN, "adversarial-audit": R},
            experiments=(exp("exp-audit", ("adversarial-audit",),
                             {"adversarial-audit": 0.9}, 100.0, 0.01),),
            recommendation=None,
        ),
        _case(
            "evsi-zero-probability-dominates-do-nothing",
            "evsi",
            [full["r-artifact"], full["r-audit"], full["r-baseline"], full["r-telemetry"]],
            {**ALL_PROVEN, "owner-authorization": U},
            experiments=(exp("exp-zero", ("owner-authorization",),
                             {"owner-authorization": 0.0}, 10.0, 0.0),),
            recommendation=None,
        ),
        _case(
            "evsi-partial-coverage-scores-zero",
            "evsi",
            [full["r-artifact"], full["r-audit"], full["r-baseline"], full["r-telemetry"]],
            {**ALL_PROVEN, "owner-authorization": U},
            experiments=(exp("exp-half", ("adversarial-audit",),
                             {"adversarial-audit": 0.9}, 0.0, 0.0),),
            recommendation=None,
        ),
    ]


def build_acceptance_manifest() -> tuple[AcceptanceCase, ...]:
    """The full prespecified acceptance manifest, deterministically built.

    Cases that did not pin ``expected_may_act`` explicitly get the value the
    doctrine demands: acting requires a grant, every blocking obligation
    PROVEN, and nothing REFUTED. The suite then checks the engine agrees.
    """
    builders = (
        _valid_positive_cases,
        _refuted_cases,
        _stale_cases,
        _corrupted_cases,
        _missing_cases,
        _model_claim_cases,
        _downgrade_cases,
        _authorization_cases,
        _evsi_cases,
    )
    finalized: list[AcceptanceCase] = []
    for builder in builders:
        for case in builder():
            if case.expected_may_act is None:
                blocking_unresolved = any(
                    verdict != P
                    for obligation_id, verdict in case.expected_verdicts.items()
                    if case.graph.obligation_by_id(obligation_id).blocking
                )
                any_refuted = any(verdict == R for verdict in case.expected_verdicts.values())
                case = replace(
                    case,
                    expected_may_act=bool(
                        case.grant is not None and not blocking_unresolved and not any_refuted
                    ),
                )
            finalized.append(case)
    return tuple(finalized)


CASE_COUNT = len(build_acceptance_manifest())
