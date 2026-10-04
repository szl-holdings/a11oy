from __future__ import annotations

import base64
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


SCRIPT = Path(__file__).with_name("prove_hf_gdw_runtime.py")
SPEC = importlib.util.spec_from_file_location("prove_hf_gdw_runtime", SCRIPT)
assert SPEC and SPEC.loader
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)

import szl_dsse  # noqa: E402  (repository root is on sys.path via the script)


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
        origin="https://szlholdings-a11oy.hf.space",
        source_sha=SOURCE_SHA,
        operator_token="x" * 48,
        require_signed_receipt=False,
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
        origin="https://szlholdings-a11oy.hf.space",
        source_sha=SOURCE_SHA,
        operator_token="x" * 48,
        require_signed_receipt=False,
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
            base="https://szlholdings-a11oy.hf.space",
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
            base="https://szlholdings-a11oy.hf.space",
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
        base="https://szlholdings-a11oy.hf.space",
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
        szl_dsse,
        "_load_private_key",
        lambda: private_key,
    )
    envelope = szl_dsse.sign_payload(
        receipt_payload,
        szl_dsse.KHIPU_PAYLOAD_TYPE,
    )
    monkeypatch.setattr(szl_dsse, "_load_private_key", lambda: None)
    # Only the pinned key is trusted; for this offline test the "pinned" DER
    # is the test key's public half.
    test_der = private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    monkeypatch.setattr(proof, "_pinned_key_der", lambda: test_der)
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
        base="https://szlholdings-a11oy.hf.space",
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
            base="https://szlholdings-a11oy.hf.space",
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
            base="https://szlholdings-a11oy.hf.space",
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
            base="https://szlholdings-a11oy.hf.space",
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
            base="https://szlholdings-a11oy.hf.space",
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
            origin="https://szlholdings-a11oy.hf.space",
            source_sha=SOURCE_SHA,
            operator_token="x" * 48,
            require_signed_receipt=False,
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
        origin="https://szlholdings-a11oy.hf.space",
        source_sha=SOURCE_SHA,
        operator_token="x" * 48,
        require_signed_receipt=False,
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
        base="https://szlholdings-a11oy.hf.space",
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
            origin="https://szlholdings-a11oy.hf.space",
            source_sha=SOURCE_SHA,
            operator_token=operator_token,
            require_signed_receipt=False,
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
            origin="https://szlholdings-a11oy.hf.space",
            source_sha=SOURCE_SHA,
            operator_token="x" * 48,
            require_signed_receipt=False,
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
        base="https://szlholdings-a11oy.hf.space",
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


def _http_error(status, body="{}", retry_after=None):
    """Return a factory so every attempt observes a fresh, unread body."""

    import email.message
    import io
    from urllib.error import HTTPError

    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    def build():
        return HTTPError(
            "https://szlholdings-a11oy.hf.space/api",
            status,
            "error",
            headers,
            io.BytesIO(body.encode("utf-8")),
        )

    return build


class _FakeResponse:
    def __init__(self, payload, *, url, status=200):
        self._payload = json.dumps(payload).encode("utf-8")
        self._url = url
        self.status = status

    def read(self, *_size):
        return self._payload

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


GDW_URL = "https://szlholdings-a11oy.hf.space/api/a11oy/v1/gdw/step"
HEALTH_URL = "https://szlholdings-a11oy.hf.space/api/a11oy/v1/gdw/healthz"


def _install_transport(monkeypatch, outcomes):
    calls = []
    slept = []

    class Opener:
        def open(self, request, timeout=None):
            calls.append(request)
            outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
            if callable(outcome):
                raise outcome()
            return _FakeResponse(outcome, url=request.full_url)

    transport = proof.bounds.BoundedTransport(
        deadline_seconds=600, opener=Opener(), sleep=slept.append,
        clock=lambda: 0.0,
    )
    monkeypatch.setattr(proof, "_TRANSPORT", transport)
    return calls, slept


def test_request_json_retries_a_saturated_admission_ceiling(monkeypatch):
    calls, slept = _install_transport(
        monkeypatch,
        [
            _http_error(429, '{"detail":"GDW quota exceeded: OWNER_SESSIONS_QUOTA"}'),
            _http_error(429, '{"detail":"GDW quota exceeded: OWNER_SESSIONS_QUOTA"}'),
            {"decision": "ACCEPT"},
        ],
    )
    assert proof.request_json("POST", GDW_URL) == {"decision": "ACCEPT"}
    assert len(calls) == 3
    assert slept == [2.0, 4.0]


def test_request_json_honours_retry_after(monkeypatch):
    _calls, slept = _install_transport(
        monkeypatch,
        [_http_error(503, "{}", retry_after=7), {"ok": True}],
    )
    assert proof.request_json("GET", HEALTH_URL) == {"ok": True}
    assert slept == [7.0]


def test_request_json_retries_a_booting_runtime(monkeypatch):
    calls, _slept = _install_transport(
        monkeypatch,
        [_http_error(502), _http_error(504), {"status": "REAL"}],
    )
    assert proof.request_json("GET", HEALTH_URL) == {"status": "REAL"}
    assert len(calls) == 3


def test_request_json_never_retries_a_contract_or_integrity_failure(monkeypatch):
    for status in (400, 401, 403, 404, 409, 422, 500):
        calls, _slept = _install_transport(
            monkeypatch, [_http_error(status, '{"detail":"denied: provider secret text"}')]
        )
        with pytest.raises(RuntimeError) as excinfo:
            proof.request_json("POST", GDW_URL)
        assert not isinstance(excinfo.value, proof.TransientRequestError)
        assert excinfo.value.code == "HTTP_STATUS_REJECTED"
        assert excinfo.value.http_status == status
        # The provider body is never read into the error.
        assert "denied" not in str(excinfo.value)
        assert "provider secret text" not in repr(excinfo.value)
        assert len(calls) == 1


def test_request_json_fails_honestly_when_a_transient_condition_persists(monkeypatch):
    calls, _slept = _install_transport(
        monkeypatch,
        [_http_error(429, '{"detail":"GDW quota exceeded: OWNER_SESSIONS_QUOTA"}')],
    )
    with pytest.raises(proof.TransientRequestError) as excinfo:
        proof.request_json("POST", GDW_URL)
    assert len(calls) == proof._REQUEST_ATTEMPTS == 8
    assert excinfo.value.code == "TRANSIENT_RETRY_EXHAUSTED"
    assert "OWNER_SESSIONS_QUOTA" not in str(excinfo.value)


def test_poll_scoped_calls_use_a_short_budget(monkeypatch):
    calls, _slept = _install_transport(monkeypatch, [_http_error(503)])
    with pytest.raises(proof.TransientRequestError):
        proof.request_json("GET", HEALTH_URL, attempts=proof._POLL_ATTEMPTS)
    assert len(calls) == proof._POLL_ATTEMPTS


def test_request_json_rejects_a_redirect_without_following(monkeypatch):
    calls, _slept = _install_transport(monkeypatch, [_http_error(302, "moved")])
    with pytest.raises(proof.ProofBoundaryError) as excinfo:
        proof.request_json("GET", HEALTH_URL)
    assert excinfo.value.code == "REDIRECT_REJECTED"
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("method", "url", "code"),
    [
        ("GET", "https://a-11-oy.com/api/a11oy/v1/gdw/healthz", "DESTINATION_REJECTED"),
        ("GET", "https://szlholdings-a11oy.hf.space.evil.example/api/a11oy/v1/gdw/healthz",
         "DESTINATION_REJECTED"),
        ("GET", "http://szlholdings-a11oy.hf.space/api/a11oy/v1/gdw/healthz", "DESTINATION_REJECTED"),
        ("GET", "https://szlholdings-a11oy.hf.space/api/other/v1/gdw/healthz", "NAMESPACE_SCOPE_REJECTED"),
        ("POST", "https://szlholdings-a11oy.hf.space/api/a11oy/v1/gdw/sessions/x", "EFFECT_SCOPE_REJECTED"),
        ("POST", "https://szlholdings-a11oy.hf.space/api/a11oy/v1/series-a/restart", "EFFECT_SCOPE_REJECTED"),
        ("POST", "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy/restart", "DESTINATION_REJECTED"),
    ],
)
def test_request_json_rejects_out_of_scope_calls_before_network(monkeypatch, method, url, code):
    calls, _slept = _install_transport(monkeypatch, [{"ok": True}])
    with pytest.raises(proof.ProofBoundaryError) as excinfo:
        proof.request_json(method, url)
    assert excinfo.value.code == code
    assert calls == []


# --- Bounded live-proof admission: proof-tagged receipt and CLI -----------


PROOF_RECOVERY_ID = "gdw-proof-aaaaaaaaaaaa-bbbbbbbbbbbb-1"


def _sign_recovery_report(monkeypatch, private_key, report):
    receipt = report["audit_receipt"]
    payload = {
        key: value
        for key, value in receipt.items()
        if key not in {"receipt_status", "receipt_sha256", "dsse_envelope_sha256",
                       "chain_sha256", "dsse_envelope"}
    }
    monkeypatch.setattr(szl_dsse, "_load_private_key", lambda: private_key)
    envelope = szl_dsse.sign_payload(payload, szl_dsse.KHIPU_PAYLOAD_TYPE)
    monkeypatch.setattr(szl_dsse, "_load_private_key", lambda: None)
    receipt["receipt_status"] = "SIGNED_KHIPU_DSSE"
    receipt["dsse_envelope"] = envelope
    receipt["dsse_envelope_sha256"] = proof._canonical_hash(envelope)
    receipt["chain_sha256"] = proof._canonical_hash({
        "previous_chain_sha256": receipt["previous_chain_sha256"],
        "receipt_sha256": receipt["receipt_sha256"],
        "receipt_status": receipt["receipt_status"],
        "dsse_envelope_sha256": receipt["dsse_envelope_sha256"],
    })
    return report


def _der(private_key):
    return private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def _proof_receipt(**kwargs):
    return proof.prove_signed_receipt(
        base="https://szlholdings-a11oy.hf.space",
        operator_token="x" * 48,
        source_sha=SOURCE_SHA,
        database_generation_id=GENERATION_ID,
        recovery_evidence=proof._new_recovery_evidence(),
        **kwargs,
    )


def _no_eligible_report():
    return _recovery_report(
        status="NO_ELIGIBLE_EFFECTS", eligible=0, rescheduled=0,
        recovery_id=PROOF_RECOVERY_ID,
    )


def test_proof_tagged_receipt_verifies_against_the_pinned_key(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    report = _sign_recovery_report(monkeypatch, key, _no_eligible_report())
    seen = []

    def request_json(method, url, **kwargs):
        seen.append((method, url, kwargs["headers"]["Idempotency-Key"]))
        return report

    monkeypatch.setattr(proof, "request_json", request_json)
    monkeypatch.setattr(proof, "_pinned_key_der", lambda: _der(key))
    receipt = _proof_receipt()
    assert receipt["signature_verified"] is True
    assert receipt["namespace"] == "a11oy"
    assert receipt["receipt_status"] == "SIGNED_KHIPU_DSSE"
    assert receipt["verified_against"] == "ayllu/keys/council-runtime-2026-07-21.pub"
    assert seen[0][0] == "POST"
    assert seen[0][1].startswith(
        "https://szlholdings-a11oy.hf.space/api/a11oy/v1/gdw/recovery/transient-effects"
    )
    assert seen[0][2] == PROOF_RECOVERY_ID


def test_receipt_signed_by_any_other_key_is_rejected(monkeypatch):
    signer = ec.generate_private_key(ec.SECP256R1())
    pinned = ec.generate_private_key(ec.SECP256R1())
    report = _sign_recovery_report(monkeypatch, signer, _no_eligible_report())
    monkeypatch.setattr(proof, "request_json", lambda *a, **k: report)
    monkeypatch.setattr(proof, "_pinned_key_der", lambda: _der(pinned))
    # The in-drain contract check refuses it; szl_dsse runtime trust is not consulted.
    with pytest.raises(RuntimeError):
        _proof_receipt()
    with pytest.raises(proof.ProofBoundaryError) as excinfo:
        proof._verify_signed_envelope(report["audit_receipt"]["dsse_envelope"])
    assert excinfo.value.code == "RECEIPT_SIGNATURE_INVALID"


def test_real_pinned_key_rejects_a_test_signature():
    from cryptography.hazmat.primitives import hashes

    signer = ec.generate_private_key(ec.SECP256R1())
    body = b'{"k":1}'
    sig = signer.sign(
        proof.bounds.dsse_pae(proof.bounds.KHIPU_PAYLOAD_TYPE, body), ec.ECDSA(hashes.SHA256())
    )
    envelope = {
        "payloadType": proof.bounds.KHIPU_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "signed": True,
        "signatures": [{"sig": base64.b64encode(sig).decode("ascii"), "keyid": "x"}],
    }
    with pytest.raises(proof.ProofBoundaryError) as excinfo:
        proof._verify_signed_envelope(envelope)
    assert excinfo.value.code == "RECEIPT_SIGNATURE_INVALID"


def test_unsigned_proof_receipt_fails_closed(monkeypatch):
    report = _no_eligible_report()
    monkeypatch.setattr(proof, "request_json", lambda *a, **k: report)
    with pytest.raises(proof.ProofBoundaryError) as excinfo:
        _proof_receipt()
    assert excinfo.value.code == "RECEIPT_UNSIGNED"


def test_unreviewed_recovery_prefix_is_rejected(monkeypatch):
    monkeypatch.setattr(proof, "request_json", lambda *a, **k: pytest.fail("no call"))
    with pytest.raises(proof.ProofBoundaryError) as excinfo:
        proof._recover_transient_effects(
            base="https://szlholdings-a11oy.hf.space", operator_token="x" * 48,
            source_sha=SOURCE_SHA, database_generation_id=GENERATION_ID,
            evidence=proof._new_recovery_evidence(), recovery_prefix="other-namespace",
        )
    assert excinfo.value.code == "EFFECT_SCOPE_REJECTED"


def test_prove_rejects_a_non_canonical_origin_before_network(monkeypatch):
    monkeypatch.setattr(proof, "request_json", lambda *a, **k: pytest.fail("no call"))
    for origin in ("https://a-11-oy.com", "https://szlholdings-a11oy.hf.space.evil.example"):
        with pytest.raises(proof.ProofBoundaryError) as excinfo:
            proof.prove(origin=origin, source_sha=SOURCE_SHA, operator_token="x" * 48)
        assert excinfo.value.code == "DESTINATION_REJECTED"


def test_restart_helper_refuses_any_other_space(monkeypatch):
    class Api:
        def __getattr__(self, name):
            pytest.fail("no provider call for another Space")

    monkeypatch.setattr(proof, "request_json", lambda *a, **k: pytest.fail("no call"))
    with pytest.raises(proof.ProofBoundaryError) as excinfo:
        proof.prove_restart(
            api=Api(),
            repo_id="SZLHOLDINGS/other",
            base="https://szlholdings-a11oy.hf.space",
            source_sha=SOURCE_SHA,
            operator_token="x" * 48,
            session_id="protected-promotion-aaaaaaaaaaaaaaaa",
        )
    assert excinfo.value.code == "SPACE_SCOPE_REJECTED"


def test_main_setup_required_names_the_secret(monkeypatch, tmp_path):
    monkeypatch.delenv("GDW_OPERATOR_TOKEN", raising=False)
    monkeypatch.setattr(proof, "prove", lambda **k: pytest.fail("no proof without secret"))
    output = tmp_path / "gdw.json"
    assert proof.main(["--source-sha", SOURCE_SHA, "--output", str(output)]) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["state"] == "SETUP_REQUIRED"
    assert report["missing_secret_names"] == ["GDW_OPERATOR_TOKEN"]
    assert report["ok"] is False


def test_main_failure_reports_fixed_code_without_provider_text(monkeypatch, tmp_path):
    secret = "gdw-operator-secret-value-with-32-plus-bytes"
    monkeypatch.setenv("GDW_OPERATOR_TOKEN", secret)

    def fail(**_kwargs):
        raise RuntimeError("provider said: Traceback " + secret)

    monkeypatch.setattr(proof, "prove", fail)
    output = tmp_path / "gdw.json"
    assert proof.main(["--source-sha", SOURCE_SHA, "--output", str(output)]) == 1
    raw = output.read_text(encoding="utf-8")
    report = json.loads(raw)
    assert report["diagnostic_code"] == "GDW_CONTRACT_FAILED"
    assert secret not in raw and "Traceback" not in raw and "provider said" not in raw
    assert proof._TRANSPORT is None


def test_main_pass_report_is_compact_and_admissible(monkeypatch, tmp_path):
    secret = "gdw-operator-secret-value-with-32-plus-bytes"
    monkeypatch.setenv("GDW_OPERATOR_TOKEN", secret)
    pinned_sha = proof.bounds.PINNED_RUNTIME_KEY_DER_SHA256

    def fake_prove(**kwargs):
        assert kwargs["origin"] == "https://szlholdings-a11oy.hf.space"
        assert kwargs["require_signed_receipt"] is True
        assert proof._TRANSPORT is not None
        return {
            "runtime_source_revision": SOURCE_SHA,
            "namespace": "a11oy",
            "health": {"persistence": {"storage": {"database_generation_id": GENERATION_ID}},
                       "noise": "x" * 5000},
            "drain": {"failed": 0, "pending_effects": 0, "legacy_pending_proofs": 0,
                      "integrity_ok": True, "database_generation_id": GENERATION_ID},
            "integrity": _complete_integrity(),
            "global_integrity": _complete_integrity(),
            "transient_recovery": proof._new_recovery_evidence(),
            "signed_receipt": {
                "recovery_id": PROOF_RECOVERY_ID, "status": "NO_ELIGIBLE_EFFECTS",
                "namespace": "a11oy", "owner_id": "operator",
                "receipt_status": "SIGNED_KHIPU_DSSE", "receipt_sha256": "1" * 64,
                "chain_sha256": "2" * 64, "sequence": 3, "signature_verified": True,
                "verified_against": "ayllu/keys/council-runtime-2026-07-21.pub",
                "pinned_key_der_sha256": pinned_sha, "payload_sha256": "3" * 64,
            },
        }

    monkeypatch.setattr(proof, "prove", fake_prove)
    output = tmp_path / "gdw.json"
    assert proof.main(["--source-sha", SOURCE_SHA, "--output", str(output)]) == 0
    raw = output.read_text(encoding="utf-8")
    assert secret not in raw and "xxxxx" not in raw
    report = json.loads(raw)
    assert report["status"] == "PASS" and report["state"] == "PROVEN"
    assert report["bounds"]["redirects_allowed"] is False

    checker_path = Path(__file__).with_name("check_hf_manual_prerequisites.py")
    spec = importlib.util.spec_from_file_location("checker_for_gdw", checker_path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    assert checker.inspect_live_proof(output, "gdw", 0, SOURCE_SHA) == {
        "report_valid": True, "state": "PROVEN"}
    assert checker.inspect_live_proof(output, "gdw", 1, SOURCE_SHA)["state"] == "UNPROVEN"
    assert checker.inspect_live_proof(output, "gdw", 0, "c" * 40)["state"] == "UNPROVEN"


def _managed_fixture():
    spec = importlib.util.spec_from_file_location(
        "gdw_managed_context_test", SCRIPT.with_name("configure_hf_gdw_runtime.py"))
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    admission = {"source": {"revision": SOURCE_SHA},
                 "qualification": {"report_sha256": "b" * 64},
                 "snapshots": {"gdw": {"generation": GENERATION_ID},
                               "series_a": {"generation": "store_" + "d" * 32}}}
    value = {"operation_id": "e" * 32, "kind": "COMMIT", "epoch": 2,
             "qualification_sha256": "f" * 64, "source_revision": SOURCE_SHA,
             "snapshots": admission["snapshots"]}
    head = SimpleNamespace(revision="1" * 40, body=b"immutable-head", value=value)
    reads = []

    def read_at(revision, operation, deadline):
        reads.append((revision, operation, deadline))
        return head, head.body

    backend = SimpleNamespace(read_at=read_at)
    context = config.ManagedProofContext(admission, "f" * 64, backend,
                                        deadline=proof.time.monotonic() + 30)
    witness = {"schema": "szl.gdw-managed-runtime/v1", "mode": "private-dataset-v1",
               **context.identity, "dataset_revision": head.revision,
               "operation_id": value["operation_id"], "writer_epoch": 2,
               "actual_host_full_state_ack_ms": 500,
               "startup_state": "RESTORED_AND_ACKNOWLEDGED", "throughput_claim": "NOT_CLAIMED"}
    return context, witness, backend, reads


def _managed_transport(monkeypatch, witness, *, events=None, mutate_health=None):
    events = [] if events is None else events

    def request(method, url, **_kwargs):
        events.append((method, url))
        value = _live_response(method, url)
        if url.endswith("/gdw/healthz"):
            value["persistence"]["storage"].update({
                "durable_storage": "private-dataset-v1",
                "durability_authority": "verified-private-dataset-head",
                "required_mount": None, "mount_verified": False,
                "persistence_required": True, "managed_admission": witness})
            if mutate_health:
                mutate_health(value)
        return 200, value

    monkeypatch.setattr(proof, "_TRANSPORT", SimpleNamespace(request=request, sleep=lambda _s: None))
    return events


def test_managed_gdw_native_requests_validate_before_each_write_and_report(monkeypatch):
    context, witness, _backend, reads = _managed_fixture()
    events = _managed_transport(monkeypatch, witness)
    report = proof.prove(origin=proof.bounds.CANONICAL_ORIGIN, source_sha=SOURCE_SHA,
                         operator_token="x" * 48, require_signed_receipt=False,
                         managed_context=context)
    assert report["managed_identity"] == context.identity
    assert report["managed_admission"] == witness
    assert proof._summary(report)["managed_admission"] == witness
    writes = [i for i, event in enumerate(events) if event[0] == "POST"]
    assert writes
    for i in writes:
        assert events[i - 1] == ("GET", proof.bounds.CANONICAL_ORIGIN + proof.GDW_PREFIX + "healthz")
    assert len(reads) >= len(writes) + 2
    assert all(read[:2] == (witness["dataset_revision"], witness["operation_id"]) for read in reads)
    assert proof._MANAGED_CONTEXT is None and proof._MANAGED_LATEST is None


@pytest.mark.parametrize("fault", ["no_context", "missing_witness", "admission", "qualification",
                                  "source", "epoch", "generation", "history", "ack_bool",
                                  "unacknowledged", "closed_context", "malformed_storage"])
def test_managed_gdw_refuses_unverified_authority_before_writes(fault, monkeypatch):
    context, witness, backend, reads = _managed_fixture()
    if fault == "admission":
        witness["admission_sha256"] = "9" * 64
    elif fault == "qualification":
        witness["qualification_sha256"] = witness["admission_sha256"]
    elif fault == "source":
        witness["source_revision"] = "9" * 40
    elif fault == "epoch":
        witness["writer_epoch"] = 3
    elif fault == "generation":
        witness["generations"]["gdw"] = "9" * 32
    elif fault == "history":
        original = backend.read_at
        backend.read_at = lambda *args: (original(*args)[0], b"different-history")
    elif fault == "ack_bool":
        witness["actual_host_full_state_ack_ms"] = True
    elif fault == "unacknowledged":
        witness["startup_state"] = "PLANNED"
    elif fault == "closed_context":
        context.close()
    elif fault == "missing_witness":
        witness = None

    def mutate(value):
        if fault == "malformed_storage":
            value["persistence"] = ["not-a-storage-record"]

    events = _managed_transport(monkeypatch, witness, mutate_health=mutate)
    with pytest.raises(proof.ProofBoundaryError) as caught:
        proof.prove(origin=proof.bounds.CANONICAL_ORIGIN, source_sha=SOURCE_SHA,
                    operator_token="x" * 48, require_signed_receipt=False,
                    managed_context=None if fault == "no_context" else context)
    assert caught.value.code == "EFFECT_SCOPE_REJECTED"
    assert all(event[0] == "GET" for event in events)
    assert proof._MANAGED_CONTEXT is None and proof._MANAGED_LATEST is None
    if fault == "no_context":
        assert reads == []


def test_managed_gdw_rechecks_native_history_after_initial_health(monkeypatch):
    context, witness, backend, reads = _managed_fixture()
    events = []
    original = backend.read_at

    def read_at(*args):
        head, history = original(*args)
        if len(reads) > 2:
            return head, b"lost-authority"
        return head, history

    backend.read_at = read_at
    _managed_transport(monkeypatch, witness, events=events)
    with pytest.raises(proof.ProofBoundaryError) as caught:
        proof.prove(origin=proof.bounds.CANONICAL_ORIGIN, source_sha=SOURCE_SHA,
                    operator_token="x" * 48, require_signed_receipt=False, managed_context=context)
    assert caught.value.code == "EFFECT_SCOPE_REJECTED"
    assert len(reads) == 3
    assert all(method == "GET" for method, _url in events)


def test_managed_cli_loader_failure_precedes_transport_and_is_sanitized(monkeypatch, tmp_path):
    monkeypatch.setenv("GDW_OPERATOR_TOKEN", "synthetic-gdw-token-with-more-than-32-bytes")
    calls = []

    def reject(path, *, source_revision, deadline):
        calls.append((path, source_revision, deadline))
        raise RuntimeError("sensitive provider response")

    monkeypatch.setattr(proof, "load_managed_proof_context", reject)
    output, locator = tmp_path / "proof.json", tmp_path / "locator.json"
    assert proof.main(["--source-sha", SOURCE_SHA, "--output", str(output),
                       "--managed-acquisition", str(locator)],
                      transport_factory=lambda **_k: pytest.fail("transport before admission")) == 1
    assert len(calls) == 1 and calls[0][:2] == (locator, SOURCE_SHA)
    assert "sensitive" not in output.read_text()
    assert json.loads(output.read_text())["status"] == "FAIL"
    assert proof._TRANSPORT is None


def test_managed_cli_keeps_loader_time_in_deadline_and_closes_context(monkeypatch, tmp_path):
    monkeypatch.setenv("GDW_OPERATOR_TOKEN", "synthetic-gdw-token-with-more-than-32-bytes")
    now = [10.0]
    monkeypatch.setattr(proof.time, "monotonic", lambda: now[0])
    closed = []
    context = SimpleNamespace(close=lambda: closed.append(True))

    def load(_path, *, source_revision, deadline):
        assert source_revision == SOURCE_SHA and deadline == 70.0
        now[0] += 20
        return context

    def factory(*, deadline_seconds):
        assert deadline_seconds == 40
        return SimpleNamespace()

    def run(**kwargs):
        assert kwargs["managed_context"] is context
        raise proof.ProofBoundaryError("DEADLINE_EXHAUSTED")

    monkeypatch.setattr(proof, "load_managed_proof_context", load)
    monkeypatch.setattr(proof, "prove", run)
    output = tmp_path / "proof.json"
    assert proof.main(["--source-sha", SOURCE_SHA, "--output", str(output),
                       "--managed-acquisition", str(tmp_path / "locator.json"),
                       "--deadline-seconds", "60"], transport_factory=factory) == 1
    assert closed == [True]
    assert json.loads(output.read_text())["diagnostic_code"] == "DEADLINE_EXHAUSTED"
    assert proof._TRANSPORT is None


def test_managed_cli_native_loader_refuses_invalid_locator_before_effects(monkeypatch, tmp_path):
    monkeypatch.setenv("GDW_OPERATOR_TOKEN", "synthetic-gdw-token-with-more-than-32-bytes")
    locator, output = tmp_path / "locator.json", tmp_path / "proof.json"
    locator.write_text("{}\n")
    assert proof.main(["--source-sha", SOURCE_SHA, "--output", str(output),
                       "--managed-acquisition", str(locator)],
                      transport_factory=lambda **_k: pytest.fail("invalid locator admitted")) == 1
    assert json.loads(output.read_text())["status"] == "FAIL"
    assert proof._TRANSPORT is None
RUN_CONTEXT = "123456789:2"


def _terminal_series_report(*, phase="activation", stage="RUNTIME_ERROR"):
    observed = proof.datetime.now(proof.timezone.utc).isoformat()
    return {
        "schema": "szl.series-a-restart-proof/v1",
        "status": "FAIL", "ok": False, "diagnostic_code": "PROVIDER_TERMINAL_STATE",
        "repo_id": proof.bounds.CANONICAL_SPACE, "requested_repo_id_admitted": True,
        "origin": proof.bounds.CANONICAL_ORIGIN, "source_revision": SOURCE_SHA,
        "workflow_run_context": RUN_CONTEXT, "generated_at": observed,
        "secret_values_recorded": False, "credential_authority_state": "UNKNOWN",
        "evidence": {
            "terminal_provider_state": {
                "stage": stage, "phase": phase, "attempt": 2, "observed_at": observed,
                "expected_source_revision": SOURCE_SHA, "runtime_source_verified": False,
            },
            f"{phase}_restart_requested": True,
            f"{phase}_restart_control": {
                "phase": phase, "pause_requested": True, "pause_confirmed": True,
                "confirmed_pause_stage": "PAUSED", "restart_requested": True,
                "writer_overlap_prevented": True,
            },
        },
    }


@pytest.mark.parametrize("phase", ["activation", "durability"])
@pytest.mark.parametrize("stage", ["RUNTIME_ERROR", "BUILD_ERROR", "CONFIG_ERROR", "NO_APP_FILE"])
def test_main_retains_same_run_terminal_failure_before_gdw_requests(monkeypatch, tmp_path, capsys, phase, stage):
    upstream = tmp_path / "series-a.json"
    source_report = _terminal_series_report(phase=phase, stage=stage)
    source_report["evidence"]["provider_error"] = "private provider traceback"
    source_report["evidence"]["terminal_provider_state"]["errorMessage"] = "private database rows"
    upstream.write_text(json.dumps(source_report), encoding="utf-8")
    monkeypatch.setattr(proof, "prove", lambda **_k: pytest.fail("no GDW requests after terminal failure"))
    monkeypatch.setattr(proof.time, "sleep", lambda _s: pytest.fail("no redundant 600-second wait"))
    output = tmp_path / "gdw.json"
    code = proof.main([
        "--source-sha", SOURCE_SHA, "--output", str(output),
        "--run-context", RUN_CONTEXT, "--series-a-proof", str(upstream),
    ], transport_factory=lambda **_k: pytest.fail("no transport before terminal failure"))
    report = json.loads(output.read_text(encoding="utf-8"))
    assert code == 1 and report["ok"] is False and report["state"] == "FAILED"
    assert report["diagnostic_code"] == "PROVIDER_TERMINAL_STATE"
    assert report["workflow_run_context"] == RUN_CONTEXT
    terminal = report["evidence"]["terminal_provider_state"]
    assert terminal["stage"] == stage and terminal["phase"] == phase
    assert terminal["runtime_source_verified"] is False
    assert set(terminal) == {"stage", "phase", "attempt", "observed_at", "expected_source_revision", "runtime_source_verified"}
    assert "private" not in output.read_text(encoding="utf-8") + capsys.readouterr().out
    assert proof._TRANSPORT is None


@pytest.mark.parametrize("path,value", [
    (("schema",), "unrelated/v1"),
    (("status",), "PASS"),
    (("ok",), 0),
    (("diagnostic_code",), "RESTART_PROOF_TIMEOUT"),
    (("repo_id",), "SZLHOLDINGS/other"),
    (("requested_repo_id_admitted",), False),
    (("origin",), "https://untrusted.invalid"),
    (("source_revision",), "b" * 40),
    (("workflow_run_context",), "123456789:1"),
    (("workflow_run_context",), "987654321:2"),
    (("secret_values_recorded",), True),
    (("credential_authority_state",), "VERIFIED"),
    (("evidence",), []),
    (("evidence", "terminal_provider_state"), {}),
    (("evidence", "terminal_provider_state", "stage"), "APP_STARTING"),
    (("evidence", "terminal_provider_state", "stage"), "BUILDING"),
    (("evidence", "terminal_provider_state", "stage"), []),
    (("evidence", "terminal_provider_state", "phase"), "unowned"),
    (("evidence", "terminal_provider_state", "expected_source_revision"), "c" * 40),
    (("evidence", "terminal_provider_state", "runtime_source_verified"), True),
    (("evidence", "terminal_provider_state", "attempt"), True),
    (("evidence", "terminal_provider_state", "attempt"), 0),
    (("evidence", "terminal_provider_state", "attempt"), 91),
    (("evidence", "terminal_provider_state", "observed_at"), "2000-01-01T00:00:00+00:00"),
    (("evidence", "terminal_provider_state", "observed_at"), "2099-01-01T00:00:00+00:00"),
    (("evidence", "terminal_provider_state", "observed_at"), "2026-10-04T00:00:00"),
    (("generated_at",), "2000-01-01T00:00:00+00:00"),
    (("generated_at",), "2099-01-01T00:00:00+00:00"),
    (("evidence", "activation_restart_requested"), False),
    (("evidence", "activation_restart_control", "phase"), "durability"),
    (("evidence", "activation_restart_control", "pause_requested"), False),
    (("evidence", "activation_restart_control", "pause_confirmed"), False),
    (("evidence", "activation_restart_control", "confirmed_pause_stage"), "APP_STARTING"),
    (("evidence", "activation_restart_control", "restart_requested"), False),
    (("evidence", "activation_restart_control", "writer_overlap_prevented"), False),
])
def test_inadmissible_terminal_evidence_keeps_existing_gdw_checks(monkeypatch, tmp_path, path, value):
    report = _terminal_series_report()
    target = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    upstream = tmp_path / "series-a.json"
    upstream.write_text(json.dumps(report), encoding="utf-8")
    _assert_existing_gdw_checks(monkeypatch, tmp_path, upstream)


def _assert_existing_gdw_checks(monkeypatch, tmp_path, upstream, *, run_context=RUN_CONTEXT):
    checked = []
    monkeypatch.setenv("GDW_OPERATOR_TOKEN", "offline-operator-fixture-with-at-least-32-bytes")

    def existing_proof(**kwargs):
        checked.append(kwargs)
        assert proof._TRANSPORT is not None
        raise proof.ProofBoundaryError("RECEIPT_SIGNATURE_INVALID")

    monkeypatch.setattr(proof, "prove", existing_proof)
    output = tmp_path / "gdw.json"
    argv = ["--source-sha", SOURCE_SHA, "--output", str(output)]
    if run_context is not None:
        argv.extend(["--run-context", run_context])
    if upstream is not None:
        argv.extend(["--series-a-proof", str(upstream)])
    assert proof.main(argv, transport_factory=lambda **_k: object()) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert len(checked) == 1
    assert checked[0]["require_signed_receipt"] is True
    assert checked[0]["source_sha"] == SOURCE_SHA
    assert report["diagnostic_code"] == "RECEIPT_SIGNATURE_INVALID"
    assert report["evidence"] == {} and report["ok"] is False


@pytest.mark.parametrize("kind", [
    "missing", "omitted", "malformed", "duplicate", "nested-duplicate",
    "oversized", "non-object", "non-utf8", "nonfinite", "no-run-context",
])
def test_missing_or_malformed_upstream_report_cannot_skip_gdw_checks(monkeypatch, tmp_path, kind):
    upstream = tmp_path / "series-a.json"
    raw = json.dumps(_terminal_series_report()).encode()
    if kind == "malformed":
        raw = b'{"status":'
    elif kind == "duplicate":
        raw = raw[:-1] + b', "status": "FAIL"}'
    elif kind == "nested-duplicate":
        raw = raw.replace(b'"stage": "RUNTIME_ERROR"', b'"stage": "APP_STARTING", "stage": "RUNTIME_ERROR"')
    elif kind == "oversized":
        raw += b" " * (proof.MAX_REPORT_BYTES + 1)
    elif kind == "non-object":
        raw = b'[]'
    elif kind == "non-utf8":
        raw = b'\xff'
    elif kind == "nonfinite":
        raw = raw[:-1] + b', "extra": NaN}'
    if kind != "missing":
        upstream.write_bytes(raw)
    _assert_existing_gdw_checks(
        monkeypatch, tmp_path, None if kind == "omitted" else upstream,
        run_context=None if kind == "no-run-context" else RUN_CONTEXT,
    )


@pytest.mark.parametrize("kind", ["fifo", "symlink", "directory"])
def test_nonregular_report_falls_through_before_a_blocking_read(tmp_path, kind):
    upstream = tmp_path / "series-a.json"
    if kind == "fifo":
        proof.os.mkfifo(upstream)
    elif kind == "symlink":
        target = tmp_path / "target.json"
        target.write_text(json.dumps(_terminal_series_report()), encoding="utf-8")
        upstream.symlink_to(target)
    else:
        upstream.mkdir()
    environment = proof.os.environ.copy()
    environment.pop("GDW_OPERATOR_TOKEN", None)
    output = tmp_path / "gdw.json"
    result = subprocess.run([
        sys.executable, "-B", str(SCRIPT), "--source-sha", SOURCE_SHA,
        "--run-context", RUN_CONTEXT, "--series-a-proof", str(upstream),
        "--output", str(output),
    ], env=environment, capture_output=True, text=True, timeout=3, check=False)
    assert result.returncode == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostic_code"] == "SETUP_REQUIRED"
    assert report["missing_secret_names"] == ["GDW_OPERATOR_TOKEN"]
    assert report["evidence"] == {} and report["ok"] is False


def test_real_series_a_cli_terminal_failure_propagates_to_gdw_without_new_reads(monkeypatch, tmp_path, capsys):
    series_path = Path(__file__).with_name("prove_hf_series_a_restart.py")
    spec = importlib.util.spec_from_file_location("series_a_terminal_chain", series_path)
    series = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(series)
    monkeypatch.setenv("HF_TOKEN", "offline-hf-token-fixture")
    monkeypatch.setattr(series.time, "sleep", lambda _s: None)
    calls = []
    runtime_stages = iter(["APP_STARTING", "RUNTIME_ERROR"])

    class Response:
        status = 200

        def __init__(self, url, payload):
            self.url = url
            self.raw = json.dumps(payload).encode()

        def read(self, *_args):
            return self.raw

        def geturl(self):
            return self.url

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Opener:
        def open(self, request, **_kwargs):
            url = request.full_url
            calls.append((request.get_method(), url))
            if url.endswith("/series-a/status"):
                payload = {"runtime_boot_id": "boot_" + "1" * 32}
            elif url.endswith("/pause"):
                payload = {"stage": "PAUSED"}
            elif url.endswith("/restart"):
                payload = {"stage": "APP_STARTING"}
            elif url.endswith("/runtime"):
                payload = {"stage": next(runtime_stages), "errorMessage": "private provider traceback"}
            else:
                pytest.fail("unexpected provider or application request")
            return Response(url, payload)

    upstream = tmp_path / "series-a.json"
    assert series.main([
        "--source-sha", SOURCE_SHA, "--run-context", RUN_CONTEXT,
        "--output", str(upstream), "--attempts", "30", "--retry-seconds", "0",
    ], transport_factory=lambda **kwargs: series.bounds.BoundedTransport(opener=Opener(), **kwargs)) == 1
    source_report = json.loads(upstream.read_text(encoding="utf-8"))
    assert source_report["diagnostic_code"] == "PROVIDER_TERMINAL_STATE"
    assert source_report["evidence"]["terminal_provider_state"]["attempt"] == 2
    assert source_report["workflow_run_context"] == RUN_CONTEXT
    assert [method for method, _url in calls] == ["GET", "POST", "POST", "GET", "GET"]
    assert source_report["evidence"]["activation_restart_control"]["confirmed_pause_stage"] == "PAUSED"
    monkeypatch.setattr(proof, "prove", lambda **_k: pytest.fail("no redundant GDW proof after terminal restart"))
    output = tmp_path / "gdw.json"
    assert proof.main([
        "--source-sha", SOURCE_SHA, "--run-context", RUN_CONTEXT,
        "--series-a-proof", str(upstream), "--output", str(output),
    ], transport_factory=lambda **_k: pytest.fail("no GDW transport")) == 1
    gdw_report = json.loads(output.read_text(encoding="utf-8"))
    assert gdw_report["diagnostic_code"] == "PROVIDER_TERMINAL_STATE"
    assert gdw_report["evidence"]["terminal_provider_state"] == source_report["evidence"]["terminal_provider_state"]
    assert len(calls) == 5
    assert "private provider" not in capsys.readouterr().out
