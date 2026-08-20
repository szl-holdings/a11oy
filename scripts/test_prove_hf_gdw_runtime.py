from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import ec


SCRIPT = Path(__file__).with_name("prove_hf_gdw_runtime.py")
SPEC = importlib.util.spec_from_file_location("prove_hf_gdw_runtime", SCRIPT)
assert SPEC and SPEC.loader
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)


SOURCE_SHA = "a" * 40
GENERATION_ID = "b" * 32
_HEALTH_ATTEMPT = 0


def _complete_integrity():
    return {
        "ok": True,
        "database_generation_id": GENERATION_ID,
        "journal_mode": "DELETE",
        "sqlite_integrity": "ok",
        "pending_proofs": 0,
        "pending_effects": 0,
        "claimed_effects": 0,
        "dead_letter_effects": 0,
        "invalid_effect_bindings": 0,
        "invalid_exported_artifacts": 0,
        "invalid_recovery_audits": 0,
    }


def _recovery_report(
    *,
    status="RESCHEDULED",
    eligible=1,
    rescheduled=1,
    claimed=0,
    recovery_id=(
        "gdw-recovery-aaaaaaaaaaaa-bbbbbbbbbbbb-1"
    ),
):
    selection = [
        {
            "namespace": "a11oy",
            "owner_id": "operator",
            "idempotency_key": f"effect-{index}",
            "database_generation_id": GENERATION_ID,
            "request_id": f"request-{index}",
            "kind": "proof_export",
            "receipt_hash": None,
            "payload_sha256": "1" * 64,
            "intent_sha256": "2" * 64,
            "attempts": 1,
            "max_attempts": 20,
            "next_attempt_at": "2026-07-29T01:00:00+00:00",
            "claim_generation": 1,
            "last_error_sha256": "3" * 64,
        }
        for index in range(rescheduled)
    ]
    selection_sha256 = proof._canonical_hash(selection)
    attempts = sum(item["attempts"] for item in selection)
    outcome = {
        "schema": "szl.gdw.transient-effect-recovery/v2",
        "status": status,
        "recovery_id": recovery_id,
        "source_revision": SOURCE_SHA,
        "requested_limit": 100,
        "failure_class": "hf-hard-link-enotsup/v1",
        "database_generation_id": GENERATION_ID,
        "inspected_pending_effects": max(eligible, rescheduled, claimed),
        "eligible_effects": eligible,
        "rescheduled_effects": rescheduled,
        "attempts_before": attempts,
        "attempts_after": attempts,
        "selection": selection,
        "selection_sha256": selection_sha256,
        "sqlite_integrity": "ok",
        "claimed_effects": claimed,
        "dead_letter_effects": 0,
        "invalid_effect_bindings": 0,
        "invalid_exported_artifacts": 0,
        "invalid_recovery_audits": 0,
        "credential_values_recorded": False,
    }
    outcome_sha256 = proof._canonical_hash(outcome)
    operator = {
        "namespace": "a11oy",
        "owner_id": "operator",
        "credential_key_id": "operator-key",
    }
    binding = {
        "schema": "szl.gdw.transient-effect-recovery-authorization/v1",
        "action_type": "gdw.transient-effect-recovery",
        **operator,
        "recovery_id": recovery_id,
        "source_revision": SOURCE_SHA,
        "database_generation_id": GENERATION_ID,
        "limit": 100,
        "failure_class": "hf-hard-link-enotsup/v1",
    }
    binding_sha256 = proof._canonical_hash(binding)
    witnesses = [
        {
            "id": "principal:a11oy:operator:operator-key",
            "role": "operator",
            "attested": True,
        },
        {
            "id": f"workload:szl-holdings/a11oy@{SOURCE_SHA}",
            "role": "workload",
            "attested": True,
        },
    ]
    governance = {
        "schema": "szl.gdw.transient-effect-recovery-governance/v1",
        "decision": "ALLOW",
        "binding": binding,
        "binding_sha256": binding_sha256,
        "policy_gateway": {
            "decision": "ALLOW",
            "gate": "ThresholdPolicySeverity",
            "receipt_hash": "c" * 64,
            "receipt_signed": True,
            "receipts_in_eq_out": True,
            "action_id": f"gdw-recovery:{binding_sha256}",
            "witnesses": witnesses,
        },
    }
    request = {
        "schema": "szl.gdw.transient-effect-recovery-request/v1",
        **operator,
        "recovery_id": recovery_id,
        "source_revision": SOURCE_SHA,
        "database_generation_id": GENERATION_ID,
        "limit": 100,
        "failure_class": "hf-hard-link-enotsup/v1",
        "governance_binding_sha256": binding_sha256,
    }
    receipt_payload = {
        "schema": "szl.gdw.transient-effect-recovery-receipt/v2",
        "operator": operator,
        "recovery_id": recovery_id,
        "source_revision": SOURCE_SHA,
        "database_generation_id": GENERATION_ID,
        "request_sha256": proof._canonical_hash(request),
        "outcome_sha256": outcome_sha256,
        "governance_sha256": proof._canonical_hash(governance),
        "selection_sha256": outcome["selection_sha256"],
        "rescheduled_effects": rescheduled,
        "attempts_before": attempts,
        "attempts_after": attempts,
        "sequence": 0,
        "previous_receipt_sha256": "0" * 64,
        "previous_chain_sha256": "0" * 64,
        "atomic_with_mutation": True,
        "created_at": "2026-07-29T00:00:00+00:00",
        "credential_values_recorded": False,
    }
    envelope = {
        "payloadType": "application/vnd.szl.khipu+json",
        "payload": base64.b64encode(
            json.dumps(
                receipt_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).decode("ascii"),
        "_dsse": "DSSEv1",
        "_pae_sha256": "d" * 64,
        "_signed_at": "2026-07-29T00:00:00+00:00",
        "signatures": [],
        "honesty": "UNSIGNED - no signature fabricated",
        "signed": False,
    }
    receipt_sha256 = proof._canonical_hash(receipt_payload)
    receipt = {
        **receipt_payload,
        "receipt_status": "UNSIGNED_KHIPU_DSSE",
        "receipt_sha256": receipt_sha256,
        "dsse_envelope_sha256": proof._canonical_hash(envelope),
        "chain_sha256": proof._canonical_hash(
            {
                "previous_chain_sha256": "0" * 64,
                "receipt_sha256": receipt_sha256,
                "receipt_status": "UNSIGNED_KHIPU_DSSE",
                "dsse_envelope_sha256": proof._canonical_hash(envelope),
            }
        ),
        "dsse_envelope": envelope,
    }
    return {
        **outcome,
        "governance": governance,
        "audit_receipt": receipt,
        "replayed": False,
    }


def _reseal_recovery_report(report):
    outcome = dict(report)
    receipt = dict(outcome.pop("audit_receipt"))
    outcome.pop("replayed")
    outcome.pop("governance")
    receipt["outcome_sha256"] = proof._canonical_hash(outcome)
    receipt_payload = {
        key: value
        for key, value in receipt.items()
        if key
        not in {
            "receipt_status",
            "receipt_sha256",
            "dsse_envelope_sha256",
            "chain_sha256",
            "dsse_envelope",
        }
    }
    receipt["receipt_sha256"] = proof._canonical_hash(receipt_payload)
    envelope = dict(receipt["dsse_envelope"])
    envelope["payload"] = base64.b64encode(
        json.dumps(
            receipt_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    receipt["dsse_envelope"] = envelope
    receipt["dsse_envelope_sha256"] = proof._canonical_hash(envelope)
    receipt["chain_sha256"] = proof._canonical_hash(
        {
            "previous_chain_sha256": receipt["previous_chain_sha256"],
            "receipt_sha256": receipt["receipt_sha256"],
            "receipt_status": receipt["receipt_status"],
            "dsse_envelope_sha256": receipt["dsse_envelope_sha256"],
        }
    )
    report["audit_receipt"] = receipt
    return report


def _live_response(method: str, url: str, **_kwargs):
    global _HEALTH_ATTEMPT
    if url.endswith("/api/build-info"):
        return {"build": {"revision": SOURCE_SHA}}
    if url.endswith("/gdw/healthz"):
        _HEALTH_ATTEMPT += 1
        return {
            "status": "REAL",
            "write_ready": True,
            "write_blockers": [],
            "persistence": {
                "storage": {
                    "journal_mode_observed": "DELETE",
                    "database_generation_id": GENERATION_ID,
                },
                "drain": {
                    "last_outcome": "SUCCEEDED",
                    "last_attempt_at": f"attempt-{_HEALTH_ATTEMPT}",
                    "last_success_at": f"success-{_HEALTH_ATTEMPT}",
                },
            },
        }
    if method == "POST" and url.endswith("/gdw/step"):
        return {
            "decision": "ACCEPT",
            "receipt_status": "UNSIGNED_ATOMIC",
            "proof": {"status": "OUTBOX_PENDING"},
            "database_generation_id": GENERATION_ID,
            "replayed": False,
        }
    if method == "POST" and "/gdw/drain" in url:
        return {
            "failed": 0,
            "pending_effects": 0,
            "legacy_pending_proofs": 0,
            "integrity_ok": True,
            "database_generation_id": GENERATION_ID,
        }
    if url.endswith("/gdw/integrity/global"):
        return _complete_integrity()
    if url.endswith("/gdw/integrity"):
        return _complete_integrity()
    if url.endswith(
        (
            "/gdw/sessions/protected-promotion",
            "/gdw/sessions/protected-promotion-aaaaaaaaaaaaaaaa",
        )
    ):
        return {"database_generation_id": GENERATION_ID}
    raise AssertionError(f"unexpected request: {method} {url}")


def test_live_proof_binds_source_generation_transition_and_artifacts(
    monkeypatch,
):
    monkeypatch.setattr(proof, "request_json", _live_response)

    report = proof.prove(
        origin="https://example.invalid",
        source_sha=SOURCE_SHA,
        operator_token="x" * 48,
    )

    assert report["source_revision"] == SOURCE_SHA
    assert report["runtime_source_revision"] == SOURCE_SHA
    assert report["transition"]["session_id"] == (
        "protected-promotion-aaaaaaaaaaaaaaaa"
    )
    assert report["transition"]["receipt_status"] == "UNSIGNED_ATOMIC"
    assert report["global_integrity"]["pending_effects"] == 0
    assert report["integrity"]["invalid_effect_bindings"] == 0
    assert report["integrity"]["invalid_exported_artifacts"] == 0
    assert report["credential_values_recorded"] is False


def test_live_proof_recovers_bound_backoff_before_requiring_real_health(
    monkeypatch,
):
    events = []
    health_calls = 0
    global_calls = 0

    def response(method: str, url: str, **kwargs):
        nonlocal global_calls, health_calls
        if url.endswith("/api/build-info"):
            events.append("build")
            return {"build": {"revision": SOURCE_SHA}}
        if url.endswith("/gdw/healthz"):
            health_calls += 1
            events.append(f"health-{health_calls}")
            if health_calls == 1:
                return {
                    "status": "UNAVAILABLE",
                    "write_ready": False,
                    "write_blockers": [
                        "OUTBOX_SUPERVISOR_NOT_QUIESCENT"
                    ],
                    "persistence": {
                        "storage": {
                            "journal_mode_observed": "DELETE",
                            "database_generation_id": GENERATION_ID,
                        },
                        "drain": {
                            "last_outcome": "RETRY_SCHEDULED",
                            "last_success_at": None,
                            "last_report": {
                                "pending_effects": 0,
                                "claimed_effects": 0,
                                "dead_letter_effects": 0,
                                "invalid_effect_bindings": 0,
                                "invalid_exported_artifacts": 0,
                            },
                        },
                    },
                }
            return _live_response(method, url, **kwargs)
        if url.endswith("/gdw/integrity/global"):
            global_calls += 1
            if global_calls == 1:
                return {
                    **_complete_integrity(),
                    "pending_effects": 1,
                }
        if method == "POST" and "/recovery/transient-effects" in url:
            events.append("recovery")
            assert kwargs["headers"] == {
                "X-Expected-Source-Revision": SOURCE_SHA,
                "Idempotency-Key": (
                    "gdw-recovery-aaaaaaaaaaaa-bbbbbbbbbbbb-1"
                ),
            }
            return _recovery_report()
        if method == "POST" and url.endswith("/gdw/step"):
            events.append("step")
        return _live_response(method, url, **kwargs)

    monkeypatch.setattr(proof, "request_json", response)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    report = proof.prove(
        origin="https://example.invalid",
        source_sha=SOURCE_SHA,
        operator_token="x" * 48,
    )

    assert events.index("health-1") < events.index("recovery")
    assert events.index("recovery") < events.index("health-2")
    assert events.index("health-2") < events.index("step")
    assert report["transient_recovery"]["applied_rounds"] == 1
    assert report["transient_recovery"]["rescheduled_effects"] == 1
    assert report["transient_recovery"][
        "attempt_accounting_preserved"
    ] is True


def test_failed_recovery_requests_consume_the_eight_call_budget(monkeypatch):
    recovery_ids = []

    def response(method: str, url: str, **kwargs):
        if method == "POST" and "/gdw/drain" in url:
            return {
                "failed": 0,
                "pending_effects": 1,
                "legacy_pending_proofs": 0,
                "integrity_ok": True,
                "database_generation_id": GENERATION_ID,
            }
        if url.endswith("/gdw/healthz"):
            return {
                "status": "UNAVAILABLE",
                "write_ready": False,
                "write_blockers": ["OUTBOX_SUPERVISOR_NOT_QUIESCENT"],
                "persistence": {
                    "storage": {
                        "database_generation_id": GENERATION_ID,
                    },
                    "drain": {
                        "last_outcome": "RETRY_SCHEDULED",
                        "last_success_at": None,
                    },
                },
            }
        if url.endswith("/gdw/integrity/global"):
            return {
                **_complete_integrity(),
                "pending_effects": 1,
            }
        if method == "POST" and "/recovery/transient-effects" in url:
            recovery_ids.append(kwargs["headers"]["Idempotency-Key"])
            raise RuntimeError("recovery request refused")
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(proof, "request_json", response)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)
    evidence = proof._new_recovery_evidence()

    with pytest.raises(RuntimeError, match="did not converge"):
        proof._prove_drain_convergence(
            base="https://example.invalid",
            operator_token="x" * 48,
            database_generation_id=GENERATION_ID,
            source_sha=SOURCE_SHA,
            recovery_evidence=evidence,
            attempts=12,
            delay_seconds=0,
        )

    assert evidence["calls"] == 8
    assert recovery_ids == [
        f"gdw-recovery-aaaaaaaaaaaa-bbbbbbbbbbbb-{number}"
        for number in range(1, 9)
    ]


@pytest.mark.parametrize(
    "invalid_binding",
    [
        "operator-shape",
        "request-sha256",
        "created-at",
        "credential-values",
    ],
)
def test_transient_recovery_rejects_self_consistent_invalid_receipt_bindings(
    monkeypatch,
    invalid_binding,
):
    report = _recovery_report()
    if invalid_binding == "operator-shape":
        report["audit_receipt"]["operator"]["extra"] = "unbound"
    elif invalid_binding == "request-sha256":
        report["audit_receipt"]["request_sha256"] = "f" * 64
    elif invalid_binding == "created-at":
        report["audit_receipt"]["created_at"] = "not-a-timestamp"
    else:
        report["credential_values_recorded"] = True
        report["audit_receipt"]["credential_values_recorded"] = True
    _reseal_recovery_report(report)
    monkeypatch.setattr(
        proof,
        "request_json",
        lambda *args, **kwargs: report,
    )

    with pytest.raises(RuntimeError, match="recovery contract"):
        proof._recover_transient_effects(
            base="https://example.invalid",
            operator_token="x" * 48,
            source_sha=SOURCE_SHA,
            database_generation_id=GENERATION_ID,
            evidence=proof._new_recovery_evidence(),
        )


def test_transient_recovery_accepts_the_authoritative_selection_id_grammar(
    monkeypatch,
):
    report = _recovery_report()
    report["selection"][0]["request_id"] = ".Recovery.A"
    report["selection"][0]["idempotency_key"] = "Effect.A"
    selection_sha256 = proof._canonical_hash(report["selection"])
    report["selection_sha256"] = selection_sha256
    report["audit_receipt"]["selection_sha256"] = selection_sha256
    _reseal_recovery_report(report)
    monkeypatch.setattr(
        proof,
        "request_json",
        lambda *args, **kwargs: report,
    )

    observed = proof._recover_transient_effects(
        base="https://example.invalid",
        operator_token="x" * 48,
        source_sha=SOURCE_SHA,
        database_generation_id=GENERATION_ID,
        evidence=proof._new_recovery_evidence(),
    )

    assert observed["selection"][0]["request_id"] == ".Recovery.A"
    assert observed["selection"][0]["idempotency_key"] == "Effect.A"


def test_transient_recovery_cryptographically_rejects_a_forged_pae_signature(
    monkeypatch,
):
    report = _recovery_report()
    receipt = report["audit_receipt"]
    receipt_payload = {
        key: value
        for key, value in receipt.items()
        if key
        not in {
            "receipt_status",
            "receipt_sha256",
            "dsse_envelope_sha256",
            "chain_sha256",
            "dsse_envelope",
        }
    }
    private_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(
        proof.szl_dsse,
        "_load_private_key",
        lambda: private_key,
    )
    envelope = proof.szl_dsse.sign_payload(
        receipt_payload,
        proof.szl_dsse.KHIPU_PAYLOAD_TYPE,
    )
    monkeypatch.setattr(proof.szl_dsse, "_load_private_key", lambda: None)
    receipt["receipt_status"] = "SIGNED_KHIPU_DSSE"
    receipt["dsse_envelope"] = envelope
    receipt["dsse_envelope_sha256"] = proof._canonical_hash(envelope)
    receipt["chain_sha256"] = proof._canonical_hash(
        {
            "previous_chain_sha256": receipt["previous_chain_sha256"],
            "receipt_sha256": receipt["receipt_sha256"],
            "receipt_status": receipt["receipt_status"],
            "dsse_envelope_sha256": receipt["dsse_envelope_sha256"],
        }
    )
    monkeypatch.setattr(proof, "request_json", lambda *args, **kwargs: report)

    observed = proof._recover_transient_effects(
        base="https://example.invalid",
        operator_token="x" * 48,
        source_sha=SOURCE_SHA,
        database_generation_id=GENERATION_ID,
        evidence=proof._new_recovery_evidence(),
    )
    assert observed["audit_receipt"]["receipt_status"] == "SIGNED_KHIPU_DSSE"

    forged = json.loads(json.dumps(report))
    forged_receipt = forged["audit_receipt"]
    forged_signature = bytearray(
        base64.b64decode(
            forged_receipt["dsse_envelope"]["signatures"][0]["sig"]
        )
    )
    forged_signature[-1] ^= 1
    forged_receipt["dsse_envelope"]["signatures"][0]["sig"] = (
        base64.b64encode(bytes(forged_signature)).decode("ascii")
    )
    forged_receipt["dsse_envelope_sha256"] = proof._canonical_hash(
        forged_receipt["dsse_envelope"]
    )
    forged_receipt["chain_sha256"] = proof._canonical_hash(
        {
            "previous_chain_sha256": forged_receipt["previous_chain_sha256"],
            "receipt_sha256": forged_receipt["receipt_sha256"],
            "receipt_status": forged_receipt["receipt_status"],
            "dsse_envelope_sha256": forged_receipt["dsse_envelope_sha256"],
        }
    )
    monkeypatch.setattr(proof, "request_json", lambda *args, **kwargs: forged)
    with pytest.raises(RuntimeError, match="recovery contract"):
        proof._recover_transient_effects(
            base="https://example.invalid",
            operator_token="x" * 48,
            source_sha=SOURCE_SHA,
            database_generation_id=GENERATION_ID,
            evidence=proof._new_recovery_evidence(),
        )


@pytest.mark.parametrize("numeric_replay", [0, 1])
def test_transient_recovery_rejects_numeric_replay_flags(
    monkeypatch,
    numeric_replay,
):
    report = _recovery_report()
    report["replayed"] = numeric_replay
    monkeypatch.setattr(
        proof,
        "request_json",
        lambda *args, **kwargs: report,
    )

    with pytest.raises(RuntimeError, match="recovery contract"):
        proof._recover_transient_effects(
            base="https://example.invalid",
            operator_token="x" * 48,
            source_sha=SOURCE_SHA,
            database_generation_id=GENERATION_ID,
            evidence=proof._new_recovery_evidence(),
        )


def test_transient_recovery_rejects_a_resealed_nonfuture_selection(
    monkeypatch,
):
    report = _recovery_report()
    report["selection"][0]["next_attempt_at"] = report["audit_receipt"][
        "created_at"
    ]
    selection_sha256 = proof._canonical_hash(report["selection"])
    report["selection_sha256"] = selection_sha256
    report["audit_receipt"]["selection_sha256"] = selection_sha256
    _reseal_recovery_report(report)
    monkeypatch.setattr(
        proof,
        "request_json",
        lambda *args, **kwargs: report,
    )

    with pytest.raises(RuntimeError, match="recovery contract"):
        proof._recover_transient_effects(
            base="https://example.invalid",
            operator_token="x" * 48,
            source_sha=SOURCE_SHA,
            database_generation_id=GENERATION_ID,
            evidence=proof._new_recovery_evidence(),
        )


def test_transient_recovery_rejects_attempt_accounting_change(monkeypatch):
    report = _recovery_report()
    report["attempts_after"] = report["attempts_before"] + 1
    monkeypatch.setattr(
        proof,
        "request_json",
        lambda *args, **kwargs: report,
    )

    with pytest.raises(RuntimeError, match="recovery contract"):
        proof._recover_transient_effects(
            base="https://example.invalid",
            operator_token="x" * 48,
            source_sha=SOURCE_SHA,
            database_generation_id=GENERATION_ID,
            evidence=proof._new_recovery_evidence(),
        )


def test_live_proof_never_accepts_a_different_runtime_source(monkeypatch):
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        proof,
        "request_json",
        lambda method, url, **kwargs: {
            "build": {"revision": "c" * 40}
        },
    )

    with pytest.raises(RuntimeError, match="SOURCE_REVISION_MISMATCH"):
        proof.prove(
            origin="https://example.invalid",
            source_sha=SOURCE_SHA,
            operator_token="x" * 48,
        )


def test_live_proof_waits_for_supervised_drain_quiescence(monkeypatch):
    drain_calls = 0
    integrity_calls = 0
    health_calls = 0

    def response(method: str, url: str, **kwargs):
        nonlocal drain_calls, integrity_calls, health_calls
        if method == "POST" and "/gdw/drain" in url:
            drain_calls += 1
            if drain_calls == 1:
                return {
                    "failed": 0,
                    "pending_effects": 2,
                    "legacy_pending_proofs": 0,
                    "integrity_ok": True,
                    "database_generation_id": GENERATION_ID,
                }
        if url.endswith("/gdw/integrity/global"):
            integrity_calls += 1
            if integrity_calls == 1:
                return {
                    **_complete_integrity(),
                    "pending_effects": 2,
                    "claimed_effects": 2,
                }
        if url.endswith("/gdw/healthz"):
            health_calls += 1
        return _live_response(method, url, **kwargs)

    monkeypatch.setattr(proof, "request_json", response)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    report = proof.prove(
        origin="https://example.invalid",
        source_sha=SOURCE_SHA,
        operator_token="x" * 48,
    )

    assert drain_calls == 2
    assert integrity_calls >= 2
    assert health_calls >= 3
    assert report["drain"]["pending_effects"] == 0
    assert report["global_integrity"]["claimed_effects"] == 0


def test_convergence_counts_only_completed_supervisor_passes(monkeypatch):
    health_calls = 0
    drain_calls = 0
    confirmation_at = []
    completions = [
        "2026-07-29T00:00:01+00:00",
        "2026-07-29T00:00:01+00:00",
        "2026-07-29T00:00:01+00:00",
        "2026-07-29T00:00:02+00:00",
        "2026-07-29T00:00:02+00:00",
        "2026-07-29T00:00:03+00:00",
    ]

    def response(method: str, url: str, **_kwargs):
        nonlocal health_calls, drain_calls
        if method == "POST" and "/gdw/drain" in url:
            drain_calls += 1
            if drain_calls == 2:
                confirmation_at.append(health_calls)
            return {
                "failed": 0,
                "pending_effects": 0,
                "legacy_pending_proofs": 0,
                "integrity_ok": True,
                "database_generation_id": GENERATION_ID,
            }
        if url.endswith("/gdw/integrity/global"):
            return _complete_integrity()
        if url.endswith("/gdw/healthz"):
            marker = completions[health_calls]
            health_calls += 1
            return {
                "status": "REAL",
                "write_ready": True,
                "write_blockers": [],
                "persistence": {
                    "storage": {
                        "database_generation_id": GENERATION_ID,
                    },
                    "drain": {
                        "last_outcome": "SUCCEEDED",
                        "last_attempt_at": f"attempt-{health_calls}",
                        "last_success_at": marker,
                    },
                },
            }
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(proof, "request_json", response)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    proof._prove_drain_convergence(
        base="https://example.invalid",
        operator_token="x" * 48,
        database_generation_id=GENERATION_ID,
        attempts=6,
        delay_seconds=0,
        required_stable_samples=3,
    )

    assert confirmation_at == [6]


def test_live_proof_rejects_persistent_supervisor_failure(monkeypatch):
    operator_token = "secret-token-" + ("x" * 48)
    health_calls = 0

    def response(method: str, url: str, **kwargs):
        nonlocal health_calls
        if method == "POST" and "/gdw/drain" in url:
            return {
                "failed": 1,
                "pending_effects": 2,
                "legacy_pending_proofs": 0,
                "integrity_ok": True,
                "database_generation_id": GENERATION_ID,
            }
        if url.endswith("/gdw/healthz"):
            body = _live_response(method, url, **kwargs)
            health_calls += 1
            if health_calls == 1:
                return body
            body["status"] = "UNAVAILABLE"
            body["write_ready"] = False
            body["write_blockers"] = ["OUTBOX_SUPERVISOR_NOT_HEALTHY"]
            body["persistence"]["drain"]["last_outcome"] = "RETRY_SCHEDULED"
            body["persistence"]["drain"]["last_report"] = {
                "errors": ["proof_export:OSError", operator_token],
            }
            return body
        if url.endswith("/gdw/integrity/global"):
            return {
                **_complete_integrity(),
                "pending_effects": 2,
                "dead_letter_effects": 1,
            }
        return _live_response(method, url, **kwargs)

    monkeypatch.setattr(proof, "request_json", response)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="did not converge") as exc_info:
        proof.prove(
            origin="https://example.invalid",
            source_sha=SOURCE_SHA,
            operator_token=operator_token,
        )
    error = str(exc_info.value)
    assert '"global_dead_letter_effects": 1' in error
    assert '"global_pending_effects": 2' in error
    assert '"supervisor_errors": ["proof_export:OSError"]' in error
    assert operator_token not in error


def test_live_proof_rejects_missing_database_generation(monkeypatch):
    def response(method: str, url: str, **kwargs):
        body = _live_response(method, url, **kwargs)
        if url.endswith("/gdw/healthz"):
            body["persistence"]["storage"]["database_generation_id"] = None
        if method == "POST" and url.endswith("/gdw/step"):
            body["database_generation_id"] = None
        return body

    monkeypatch.setattr(proof, "request_json", response)

    with pytest.raises(RuntimeError, match="database generation"):
        proof.prove(
            origin="https://example.invalid",
            source_sha=SOURCE_SHA,
            operator_token="x" * 48,
        )


def test_restart_proof_preserves_generation_session_and_artifacts(monkeypatch):
    restarted = False

    class Api:
        def restart_space(self, **kwargs):
            nonlocal restarted
            restarted = True
            assert kwargs == {
                "repo_id": "SZLHOLDINGS/a11oy",
                "factory_reboot": False,
            }
            return SimpleNamespace(
                runtime=SimpleNamespace(
                    stage=SimpleNamespace(value="RESTARTING")
                )
            )

    def response(method: str, url: str, **kwargs):
        body = _live_response(method, url, **kwargs)
        if url.endswith("/gdw/healthz"):
            body["persistence"]["prepared_at"] = (
                "after-restart" if restarted else "before-restart"
            )
        if url.endswith("/gdw/sessions/protected-promotion"):
            return {
                "session_id": "protected-promotion",
                "database_generation_id": GENERATION_ID,
                "step": 1,
                "state_hash": "c" * 64,
            }
        return body

    monkeypatch.setattr(proof, "request_json", response)
    monkeypatch.setattr(proof.time, "sleep", lambda _seconds: None)

    report = proof.prove_restart(
        api=Api(),
        repo_id="SZLHOLDINGS/a11oy",
        base="https://example.invalid",
        source_sha=SOURCE_SHA,
        operator_token="x" * 48,
        session_id="protected-promotion",
        attempts=5,
        delay_seconds=0,
    )

    assert report["restart_requested"] is True
    assert report["before_prepared_at"] == "before-restart"
    assert report["after_prepared_at"] == "after-restart"
    assert report["global_integrity"]["pending_effects"] == 0
    assert report["credential_values_recorded"] is False
