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


def _live_response(method: str, url: str, **_kwargs):
    if url.endswith("/api/build-info"):
        return {"build": {"revision": SOURCE_SHA}}
    if url.endswith("/gdw/healthz"):
        return {
            "status": "REAL",
            "write_ready": True,
            "persistence": {
                "storage": {
                    "journal_mode_observed": "DELETE",
                    "database_generation_id": GENERATION_ID,
                }
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
            "integrity_ok": True,
        }
    if url.endswith("/gdw/integrity"):
        return {
            "ok": True,
            "journal_mode": "DELETE",
            "pending_effects": 0,
            "invalid_effect_bindings": 0,
            "invalid_exported_artifacts": 0,
        }
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
