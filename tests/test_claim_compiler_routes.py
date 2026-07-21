# SPDX-License-Identifier: Apache-2.0
"""Assembled-app route contract for the bounded EvidenceOS Claim Compiler."""

import json
from pathlib import Path

from starlette.testclient import TestClient

import serve


CLIENT = TestClient(serve.app)
ATOMIZE = "/api/a11oy/v1/claim-integrity/atomize"
EVALUATE = "/api/a11oy/v1/claim-integrity/evaluate"
ROUTES = {
    "/api/a11oy/v1/claim-integrity/info",
    ATOMIZE,
    EVALUATE,
}


def _claim():
    return {
        "claim_id": "claim-route-1",
        "statement": "The bounded route preserves the proposal-only boundary.",
        "atomic": True,
        "evidence_refs": [
            {
                "reference_id": "route-test-source",
                "evidence_state": "SUPPORTED",
                "provenance": {"source_id": "tests/test_claim_compiler_routes.py", "content_sha256": "a" * 64},
            }
        ],
        "consequence_owner": {
            "owner_id": "test:claim-compiler",
            "accountability_scope": "route contract only",
        },
    }


def _assert_refusal(response, status_code, error_code):
    assert response.status_code == status_code
    body = response.json()
    assert body["ready"] is (status_code != 503)
    assert body["accepted"] is False
    assert body["effectors_enabled"] == 0
    assert body["decision_state"] == ("UNAVAILABLE" if status_code == 503 else "PROPOSAL_ONLY")
    assert body["error"]["code"] == error_code


def test_claim_compiler_routes_are_local_and_precede_node_proxy():
    ordered = [getattr(route, "path", None) for route in serve.app.router.routes]
    assert ROUTES <= set(ordered)
    proxy_index = ordered.index("/api/a11oy/{path:path}")
    assert all(ordered.index(path) < proxy_index for path in ROUTES)
    assert "v1/claim-integrity/" in serve._LOCAL_ONLY_A11OY_PREFIXES

    info = CLIENT.get("/api/a11oy/v1/claim-integrity/info")
    assert info.status_code == 200
    assert info.json()["http_registration"] == "REGISTERED"
    assert "HTTP registration" not in info.json()["not_implemented_here"]


def test_atomize_is_structural_only_and_never_enables_effectors():
    response = CLIENT.post(ATOMIZE, json={"text": "Alpha passed. Beta remains open."})
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is body["accepted"] is True
    assert body["semantic_atomization_computed"] is False
    assert body["candidate_count"] == 2
    assert body["decision_state"] == "PROPOSAL_ONLY"
    assert body["effectors_enabled"] == 0
    assert all(atom["atomic"] is False for atom in body["atoms"])


def test_atomize_refuses_output_amplification_beyond_32_candidates():
    response = CLIENT.post(ATOMIZE, json={"text": "x. " * 33})
    _assert_refusal(response, 422, "invalid_claim_request")
    assert len(response.content) < 1024


def test_evaluate_returns_gate_result_and_unsigned_content_digest():
    response = CLIENT.post(EVALUATE, json={"claims": [_claim()]})
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is body["accepted"] is True
    assert body["overall_state"] == "SUPPORTED"
    assert body["decision_state"] == "PROPOSAL_ONLY"
    assert body["effectors_enabled"] == 0
    assert body["receipt"]["signed"] is False
    assert body["receipt"]["attests_truth"] is False
    assert len(body["receipt"]["content_sha256"]) == 64


def test_closed_contract_and_media_type_fail_with_stable_422_envelope():
    hidden = CLIENT.post(ATOMIZE, json={"text": "bounded", "provider": "must-not-run"})
    _assert_refusal(hidden, 422, "invalid_claim_request")

    wrong_type = CLIENT.post(ATOMIZE, content=b'{"text":"bounded"}', headers={"content-type": "text/plain"})
    _assert_refusal(wrong_type, 422, "invalid_claim_request")

    orphan_signal = CLIENT.post(
        EVALUATE,
        json={"claims": [_claim()], "external_signals": {"not-a-claim": {}}},
    )
    _assert_refusal(orphan_signal, 422, "invalid_claim_request")

    ambiguous_ids = CLIENT.post(
        EVALUATE,
        json={"claims": [{"claim_id": "x"}, {"claim_id": " x "}]},
    )
    _assert_refusal(ambiguous_ids, 422, "invalid_claim_request")

    duplicate = CLIENT.post(
        ATOMIZE,
        content=b'{"text":"first","text":"second"}',
        headers={"content-type": "application/json"},
    )
    _assert_refusal(duplicate, 422, "invalid_claim_request")


def test_content_length_and_streaming_body_limits_fail_with_stable_413_envelope():
    declared = CLIENT.post(
        ATOMIZE,
        content=b"{}",
        headers={"content-type": "application/json", "content-length": str(64 * 1024 + 1)},
    )
    _assert_refusal(declared, 413, "request_body_too_large")

    def chunks():
        yield b'{"text":"'
        for _ in range(257):
            yield b"x" * 1024
        yield b'"}'

    streamed = CLIENT.post(
        ATOMIZE,
        content=chunks(),
        headers={"content-type": "application/json", "transfer-encoding": "chunked"},
    )
    _assert_refusal(streamed, 413, "request_body_too_large")


def test_unavailable_and_unexpected_failure_are_stable_503_without_error_leak(monkeypatch):
    monkeypatch.setattr(serve, "_CLAIM_RUPTURE_GATE_READY", False)
    unavailable = CLIENT.post(ATOMIZE, json={"text": "bounded"})
    _assert_refusal(unavailable, 503, "claim_compiler_unavailable")

    monkeypatch.setattr(serve, "_CLAIM_RUPTURE_GATE_READY", True)

    def explode(_payload):
        raise RuntimeError("private internal detail")

    monkeypatch.setattr(serve, "_parse_claim_atomize_request", explode)
    failed = CLIENT.post(ATOMIZE, json={"text": "bounded"})
    _assert_refusal(failed, 503, "claim_compiler_failure")
    assert "private internal detail" not in json.dumps(failed.json())


def test_curated_openapi_binds_both_post_routes_and_refusal_statuses():
    response = CLIENT.get("/api/a11oy/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    expected_schemas = {
        ATOMIZE: json.loads(
            (Path(__file__).resolve().parents[1] / "schemas/evidenceos/claim-atomize-request.v1.schema.json")
            .read_text(encoding="utf-8")
        ),
        EVALUATE: json.loads(
            (Path(__file__).resolve().parents[1] / "schemas/evidenceos/claim-evaluate-request.v1.schema.json")
            .read_text(encoding="utf-8")
        ),
    }
    for path in (ATOMIZE, EVALUATE):
        operation = paths[path]["post"]
        assert operation["requestBody"]["required"] is True
        assert "application/json" in operation["requestBody"]["content"]
        assert operation["requestBody"]["content"]["application/json"]["schema"] == expected_schemas[path]
        assert {"413", "422", "503"} <= set(operation["responses"])
