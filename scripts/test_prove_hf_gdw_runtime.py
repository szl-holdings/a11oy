from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("prove_hf_gdw_runtime.py")
SPEC = importlib.util.spec_from_file_location("prove_hf_gdw_runtime", SCRIPT)
assert SPEC and SPEC.loader
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)


SOURCE_SHA = "a" * 40
GENERATION_ID = "b" * 32


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
    if url.endswith("/api/build-info"):
        return {"build": {"revision": SOURCE_SHA}}
    if url.endswith("/gdw/healthz"):
        return {
            "status": "REAL",
            "write_ready": True,
            "write_blockers": [],
            "persistence": {
                "storage": {
                    "journal_mode_observed": "DELETE",
                    "database_generation_id": GENERATION_ID,
                },
                "drain": {"last_outcome": "SUCCEEDED"},
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
    if url.endswith("/gdw/sessions/protected-promotion"):
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

    def response(method: str, url: str, **kwargs):
        nonlocal drain_calls, integrity_calls
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
    assert report["drain"]["pending_effects"] == 0
    assert report["global_integrity"]["claimed_effects"] == 0


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
