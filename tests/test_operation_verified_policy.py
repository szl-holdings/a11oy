# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from policy.operation_verified import (
    AppendOnlyLifecycle,
    AuthorizationError,
    Decision,
    PolicyEvaluator,
    ReceiptIssuer,
    WorkerVerifier,
)

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
DIGEST = "sha256:" + "1" * 64
ROLLBACK = "sha256:" + "2" * 64
POLICY_SHA = "3" * 40
FORMAL_DIGEST = "sha256:" + "4" * 64


def request(**changes):
    value = {
        "request_id": "6a1e3862-8e98-4bdd-962d-c88208bb2e42",
        "trace_id": "a" * 32,
        "principal": "workload:release-agent",
        "action_type": "deploy.production",
        "target": f"oci://ghcr.io/szl-holdings/a11oy@{DIGEST}",
        "source_commit": "5" * 40,
        "artifact_digest": DIGEST,
        "requested_transition": {"from": "staging", "to": "production"},
        "preconditions": [],
        "test_receipts": [],
        "provenance_receipt": {"result": "accepted"},
        "security_receipts": [],
        "blast_radius": {"services": ["a11oy"]},
        "rollback": {"target_digest": ROLLBACK, "procedure": "restore verified digest"},
        "human_approvals": [{"approver": "human:release-owner", "scope": "production", "approved_at": NOW.isoformat()}],
        "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
    }
    value.update(changes)
    return value


@pytest.fixture
def boundary():
    private = ec.generate_private_key(ec.SECP256R1())
    evaluator = PolicyEvaluator(frozenset({"workload:release-agent"}), POLICY_SHA, FORMAL_DIGEST)
    return evaluator, ReceiptIssuer(private, evaluator), WorkerVerifier(private.public_key())


def test_default_denial_and_rejection_cannot_mint(boundary):
    evaluator, issuer, _ = boundary
    unknown = request(principal="workload:unknown-agent")
    assert evaluator.decide(unknown, NOW) == (Decision.DENY, "no matching authorization rule")
    with pytest.raises(AuthorizationError, match="DENY"):
        issuer.issue(unknown, NOW)


def test_signed_bound_receipt_authorizes_once_for_exact_context(boundary):
    _, issuer, worker = boundary
    req = request()
    receipt = issuer.issue(req, NOW)
    assert worker.authorize(
        receipt,
        req,
        expected_environment="production",
        expected_principal="workload:release-agent",
        expected_target_digest=DIGEST,
        expected_policy_version=POLICY_SHA,
        now=NOW,
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"expected_environment": "staging"}, "environment binding mismatch"),
        ({"expected_principal": "workload:other-agent"}, "principal binding mismatch"),
        ({"expected_target_digest": "sha256:" + "9" * 64}, "target_digest binding mismatch"),
        ({"expected_policy_version": "8" * 40}, "policy_version binding mismatch"),
    ],
)
def test_receipt_context_tampering_is_rejected(boundary, mutation, message):
    _, issuer, worker = boundary
    req = request()
    receipt = issuer.issue(req, NOW)
    kwargs = {
        "expected_environment": "production",
        "expected_principal": "workload:release-agent",
        "expected_target_digest": DIGEST,
        "expected_policy_version": POLICY_SHA,
        "now": NOW,
    }
    kwargs.update(mutation)
    with pytest.raises(AuthorizationError, match=message):
        worker.authorize(receipt, req, **kwargs)


def test_signature_request_replay_expiry_and_revocation_fail(boundary):
    _, issuer, worker = boundary
    req = request()
    receipt = issuer.issue(req, NOW)
    tampered = deepcopy(receipt)
    tampered["trace_id"] = "b" * 32
    calls = [
        (tampered, req, {}, NOW, "signature"),
        (receipt, request(artifact_digest="sha256:" + "7" * 64), {}, NOW, "request digest"),
        (receipt, req, {}, NOW + timedelta(minutes=6), "expired"),
        (receipt, req, {"revoked_principals": ["workload:release-agent"]}, NOW, "revoked"),
    ]
    for candidate, candidate_request, extra, at, message in calls:
        with pytest.raises(AuthorizationError, match=message):
            worker.authorize(
                candidate,
                candidate_request,
                expected_environment="production",
                expected_principal="workload:release-agent",
                expected_target_digest=DIGEST,
                expected_policy_version=POLICY_SHA,
                now=at,
                **extra,
            )


def test_unknown_fields_mutable_targets_and_missing_approval_default_deny(boundary):
    evaluator, _, _ = boundary
    cases = [
        request(debug_override=True),
        request(target="oci://ghcr.io/szl-holdings/a11oy:latest"),
        request(human_approvals=[]),
        request(action_type="shell.run"),
    ]
    for candidate in cases:
        assert evaluator.decide(candidate, NOW)[0] is Decision.DENY


def test_finite_refinement_exhausts_supported_action_environment_domain(boundary):
    evaluator, _, _ = boundary
    actions = (
        "deploy.staging",
        "deploy.production",
        "secret.rotate",
        "identity.change",
        "policy.change",
        "database.migrate",
        "traffic.change",
        "ruleset.change",
        "admission.change",
        "model.promote",
        "benchmark.publish",
        "claim.upgrade",
        "infrastructure.destroy",
        "unmodeled.action",
    )
    principals = ("workload:release-agent", "workload:unknown-agent")
    environments = ("staging", "production", "retired")
    approvals = ([], request()["human_approvals"])
    checked = 0
    for action in actions:
        for principal in principals:
            for environment in environments:
                for approval in approvals:
                    candidate = request(
                        action_type=action,
                        principal=principal,
                        requested_transition={"from": "development", "to": environment},
                        human_approvals=approval,
                    )
                    decision, _ = evaluator.decide(candidate, NOW)
                    expected = (
                        action in actions[:-1]
                        and principal == "workload:release-agent"
                        and environment in {"staging", "production"}
                        and (action == "deploy.staging" or bool(approval))
                    )
                    assert (decision is Decision.ALLOW) == expected
                    checked += 1
    assert checked == 168


def test_lifecycle_is_append_only_and_reject_cannot_execute():
    log = AppendOnlyLifecycle("request-1")
    for state in ("PROPOSED", "SCHEMA_VALIDATED", "POLICY_EVALUATED", "REJECTED"):
        log.append(state, NOW.isoformat())
    snapshot = log.events
    with pytest.raises(AuthorizationError):
        log.append("EXECUTING", NOW.isoformat())
    assert log.events == snapshot
