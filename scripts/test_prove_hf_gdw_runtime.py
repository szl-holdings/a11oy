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
        "pending_proofs": 0,
        "pending_effects": 0,
        "claimed_effects": 0,
        "dead_letter_effects": 0,
        "invalid_effect_bindings": 0,
        "invalid_exported_artifacts": 0,
    }


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
    if url.endswith("/gdw/sessions/protected-promotion-aaaaaaaaaaaaaaaa"):
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
    assert report["transition"]["receipt_status"] == "UNSIGNED_ATOMIC"
    assert report["global_integrity"]["pending_effects"] == 0
    assert report["integrity"]["invalid_effect_bindings"] == 0
    assert report["integrity"]["invalid_exported_artifacts"] == 0
    assert report["credential_values_recorded"] is False


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
        attempts=5,
        delay_seconds=0,
    )

    assert report["restart_requested"] is True
    assert report["before_prepared_at"] == "before-restart"
    assert report["after_prepared_at"] == "after-restart"
    assert report["global_integrity"]["pending_effects"] == 0
    assert report["credential_values_recorded"] is False
