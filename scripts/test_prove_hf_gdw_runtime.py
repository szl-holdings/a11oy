from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


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
    request = {
        "schema": "szl.gdw.transient-effect-recovery-request/v1",
        **operator,
        "recovery_id": recovery_id,
        "source_revision": SOURCE_SHA,
        "database_generation_id": GENERATION_ID,
        "limit": 100,
        "failure_class": "hf-hard-link-enotsup/v1",
    }
    receipt = {
        "schema": "szl.gdw.transient-effect-recovery-receipt/v1",
        "receipt_status": "UNSIGNED_ATOMIC",
        "operator": operator,
        "recovery_id": recovery_id,
        "source_revision": SOURCE_SHA,
        "database_generation_id": GENERATION_ID,
        "request_sha256": proof._canonical_hash(request),
        "outcome_sha256": outcome_sha256,
        "selection_sha256": outcome["selection_sha256"],
        "rescheduled_effects": rescheduled,
        "attempts_before": attempts,
        "attempts_after": attempts,
        "created_at": "2026-07-29T00:00:00+00:00",
        "credential_values_recorded": False,
    }
    receipt["receipt_sha256"] = proof._canonical_hash(receipt)
    return {**outcome, "audit_receipt": receipt, "replayed": False}


def _reseal_recovery_report(report):
    outcome = dict(report)
    receipt = dict(outcome.pop("audit_receipt"))
    outcome.pop("replayed")
    receipt.pop("receipt_sha256", None)
    receipt["outcome_sha256"] = proof._canonical_hash(outcome)
    receipt["receipt_sha256"] = proof._canonical_hash(receipt)
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
