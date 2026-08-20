#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Focused fail-closed contract and assembled-route checks for the formal lab."""

import base64
import concurrent.futures
import hashlib
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import serve
import szl_dsse
import szl_formal_conjecture_lab as lab


ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(serve.app)
ROUTES = {
    "/api/a11oy/v1/formal-conjecture-lab/status",
    "/api/a11oy/v1/formal-conjecture-lab/attempts",
    "/api/a11oy/v1/formal-conjecture-lab/attempts/{attempt_id}",
    "/api/a11oy/v1/formal-conjecture-lab/attempts/{attempt_id}/kernel-receipts",
}


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "_STATE_PATH", tmp_path / "formal-lab.jsonl")


def attempt_request(*, artifact="theorem fixture : True := by trivial", suffix="one"):
    return {
        "schema_version": lab.ATTEMPT_SCHEMA,
        "source_kind": "OPERATOR_DECLARED",
        "conjecture_id": f"fixture:{suffix}",
        "title": f"Bounded fixture {suffix}",
        "statement": f"A declared statement for fixture {suffix}.",
        "artifact": artifact,
        "artifact_format": "LEAN4" if artifact is not None else "TEXT",
        "brain_node_ids": [f"brain:fixture:{suffix}"],
    }


def signed_kernel_request(attempt, *, exit_code=0, sorry_count=0,
                          unsafe_count=0, claimed="ACCEPTED"):
    payload = {
        "schema_version": lab.KERNEL_SCHEMA,
        "attempt_id": attempt["attempt_id"],
        "conjecture_id": attempt["conjecture_id"],
        "statement_sha256": attempt["statement_sha256"],
        "artifact_sha256": attempt["artifact_sha256"],
        "checker_id": "LEAN4",
        "checker_version": "4.19.0-test",
        "kernel_commit_sha256": "1" * 64,
        "exit_code": exit_code,
        "sorry_count": sorry_count,
        "unsafe_declaration_count": unsafe_count,
        "compiler_output_sha256": "2" * 64,
        "checked_at": "2026-07-13T00:00:00Z",
        "claimed_verdict": claimed,
    }
    envelope = {
        "payloadType": lab.KERNEL_PAYLOAD_TYPE,
        "payload": base64.b64encode(lab._canonical_bytes(payload)).decode("ascii"),
        "signatures": [{"sig": base64.b64encode(b"test-signature").decode("ascii"),
                         "keyid": "szlholdings-cosign"}],
    }
    return {"schema_version": lab.KERNEL_SCHEMA, "dsse_envelope": envelope}


def accept_test_signature(monkeypatch):
    monkeypatch.setattr(
        szl_dsse,
        "verify_envelope",
        lambda envelope: {
            "verified": True,
            "keyid_expected": "szlholdings-cosign",
            "pub_fingerprint_sha256": "3" * 64,
            "pae_sha256": "4" * 64,
        },
    )


def test_declaration_is_bounded_hashed_server_side_receipted_and_idempotent():
    created = lab.declare_attempt(attempt_request())
    attempt = created["attempt"]
    assert created["created"] is True
    assert created["write_receipt_minted"] is True
    assert attempt["state"] == lab.KERNEL_UNCHECKED
    assert attempt["statement_sha256"] == hashlib.sha256(
        attempt["statement"].encode("utf-8")
    ).hexdigest()
    assert attempt["artifact_sha256"] == hashlib.sha256(
        attempt["artifact"].encode("utf-8")
    ).hexdigest()
    assert attempt["write_receipt"]["dsse"]["signed"] is False
    assert attempt["write_receipt"]["dsse"]["signatures"] == []
    assert lab.verify_event_chain(lab._read_events())["valid"] is True

    replay = lab.declare_attempt(attempt_request())
    assert replay["created"] is False
    assert replay["write_receipt_minted"] is False
    assert lab.verify_event_chain(lab._read_events())["depth"] == 1


def test_concurrent_duplicate_declarations_append_exactly_one_event():
    request = attempt_request(suffix="concurrent")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: lab.declare_attempt(request), range(16)))
    assert sum(1 for result in results if result["created"]) == 1
    assert sum(1 for result in results if result["write_receipt_minted"]) == 1
    chain = lab.verify_event_chain(lab._read_events())
    assert chain["valid"] is True
    assert chain["depth"] == 1


def test_statement_without_artifact_stays_declared_and_cannot_take_kernel_receipt(monkeypatch):
    created = lab.declare_attempt(attempt_request(artifact=None, suffix="declared"))
    attempt = created["attempt"]
    assert attempt["state"] == lab.DECLARED
    accept_test_signature(monkeypatch)
    request = signed_kernel_request({**attempt, "artifact_sha256": "5" * 64})
    with pytest.raises(lab.StateConflict, match="no formal artifact"):
        lab.ingest_kernel_receipt(attempt["attempt_id"], request)


def test_verified_kernel_state_is_derived_and_client_label_is_not_trusted(monkeypatch):
    accept_test_signature(monkeypatch)
    rejected_attempt = lab.declare_attempt(attempt_request(suffix="rejected"))["attempt"]
    rejected = lab.ingest_kernel_receipt(
        rejected_attempt["attempt_id"],
        signed_kernel_request(rejected_attempt, exit_code=1, claimed="ACCEPTED"),
    )["attempt"]
    assert rejected["state"] == lab.KERNEL_REJECTED
    assert rejected["kernel_result"]["client_label_trusted"] is False
    assert rejected["kernel_result"]["label_conflict"] is True
    assert rejected["kernel_result"]["proof_promoted"] is False

    accepted_attempt = lab.declare_attempt(attempt_request(suffix="accepted"))["attempt"]
    accepted = lab.ingest_kernel_receipt(
        accepted_attempt["attempt_id"], signed_kernel_request(accepted_attempt)
    )["attempt"]
    assert accepted["state"] == lab.KERNEL_ACCEPTED
    assert accepted["automatic_proof_promotion"] is False
    assert accepted["proof_status"] == "NOT_PROMOTED"
    assert accepted["publication_claim_authorized"] is False
    assert accepted["locked_proven_count"] == 8


def test_tampered_or_unsigned_kernel_receipt_is_rejected_without_state_change():
    attempt = lab.declare_attempt(attempt_request(suffix="unsigned"))["attempt"]
    request = signed_kernel_request(attempt)
    request["dsse_envelope"]["signatures"] = []
    with pytest.raises(lab.ContractError, match="one SZL cosign signature"):
        lab.ingest_kernel_receipt(attempt["attempt_id"], request)
    assert lab.get_attempt(attempt["attempt_id"])["state"] == lab.KERNEL_UNCHECKED
    assert lab.verify_event_chain(lab._read_events())["depth"] == 1


def test_strict_contract_rejects_hidden_execution_fields_and_factory_source_is_exact(monkeypatch):
    hidden = attempt_request(suffix="hidden")
    hidden["command"] = "lake env lean artifact.lean"
    with pytest.raises(lab.ContractError, match="fields must be exactly"):
        lab.declare_attempt(hidden)

    factory = attempt_request(suffix="factory")
    factory["source_kind"] = "CONJECTURE_FACTORY_CACHE"
    monkeypatch.setattr(
        "szl_conjecture_factory.load_conjecture",
        lambda receipt_id, force_refresh: {
            "title": factory["title"],
            "statement": factory["statement"],
            "receipt": {"receipt_id": receipt_id},
            "_envelope_status": "cached",
        },
    )
    stored = lab.declare_attempt(factory)["attempt"]
    assert stored["source_crosscheck"]["crosscheck"] == "EXACT_LOCAL_CACHE_MATCH"

    mismatched = dict(factory)
    mismatched["conjecture_id"] = "fixture:factory-mismatch"
    mismatched["statement"] = "different text"
    with pytest.raises(lab.ContractError, match="exactly match"):
        lab.declare_attempt(mismatched)


def test_get_views_are_read_only_and_status_is_explicitly_fail_closed():
    attempt = lab.declare_attempt(attempt_request(suffix="reads"))["attempt"]
    before = lab._STATE_PATH.read_bytes()
    status = lab.status()
    listed = lab.list_attempts()
    single = lab.get_attempt(attempt["attempt_id"])
    after = lab._STATE_PATH.read_bytes()
    assert before == after
    assert listed["read_receipt_minted"] is False
    assert single["attempt_id"] == attempt["attempt_id"]
    assert status["kernel_execution"]["state"] == lab.UNAVAILABLE
    assert status["controls"]["network_calls"] == "DISABLED"
    assert status["controls"]["command_execution"] == "DISABLED"
    assert status["controls"]["secret_reads"] == "DISABLED"
    assert status["proof_policy"]["automatic_promotion"] is False
    assert status["proof_policy"]["locked_proven_count"] == 8


def test_module_has_no_network_process_or_dynamic_code_execution_imports():
    source = (ROOT / "szl_formal_conjecture_lab.py").read_text(encoding="utf-8").lower()
    for forbidden in ("import subprocess", "import socket", "import urllib", "eval(", "exec("):
        assert forbidden not in source


def test_routes_are_real_precede_catchalls_and_docker_copies_module(monkeypatch):
    ordered = [getattr(route, "path", None) for route in serve.app.router.routes]
    assert ROUTES <= set(ordered)
    proxy = ordered.index("/api/a11oy/{path:path}")
    spa = ordered.index("/{full_path:path}")
    assert all(ordered.index(route) < proxy and ordered.index(route) < spa for route in ROUTES)
    assert "v1/formal-conjecture-lab/" in serve._LOCAL_ONLY_A11OY_PREFIXES
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY szl_formal_conjecture_lab.py ./" in dockerfile

    response = CLIENT.post(
        "/api/a11oy/v1/formal-conjecture-lab/attempts", json=attempt_request(suffix="route")
    )
    assert response.status_code == 201
    attempt_id = response.json()["attempt"]["attempt_id"]
    before = lab._STATE_PATH.read_bytes()
    assert CLIENT.get("/api/a11oy/v1/formal-conjecture-lab/status").status_code == 200
    assert CLIENT.get("/api/a11oy/v1/formal-conjecture-lab/attempts").status_code == 200
    single = CLIENT.get(f"/api/a11oy/v1/formal-conjecture-lab/attempts/{attempt_id}")
    assert single.status_code == 200
    assert single.json()["read_receipt_minted"] is False
    assert lab._STATE_PATH.read_bytes() == before


def test_route_rejects_hidden_and_oversize_bodies():
    hidden = attempt_request(suffix="route-hidden")
    hidden["url"] = "https://must-not-fetch.invalid"
    response = CLIENT.post("/api/a11oy/v1/formal-conjecture-lab/attempts", json=hidden)
    assert response.status_code == 422
    assert response.json()["state"] == lab.UNAVAILABLE

    oversized = CLIENT.post(
        "/api/a11oy/v1/formal-conjecture-lab/attempts",
        content=b'{"padding":"' + b"x" * lab.MAX_BODY_BYTES + b'"}',
        headers={"content-type": "application/json"},
    )
    assert oversized.status_code == 413
    assert "body exceeds" in oversized.json()["error"]
