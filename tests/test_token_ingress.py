# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11

import hashlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.token_ingress import register
from routers.token_ingress_core import (
    IngressWorkload,
    PrefixFoundry,
    SemanticTokenContract,
    TokenizerNodeSignal,
    TokenizerParityCase,
    choose_ingress_node,
    ingest_repository_files,
    qualify_tokenizer_candidate,
    verifier_reinvestment,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _contract(source: str = "oracle", **overrides: str) -> SemanticTokenContract:
    fields = {
        "source": source,
        "tokenizer_family": "BPE",
        "vocabulary_sha256": _digest("vocabulary"),
        "normalization_sha256": _digest("normalization"),
        "special_tokens_sha256": _digest("special-tokens"),
        "added_tokens_sha256": _digest("added-tokens"),
        "chat_template_sha256": _digest("chat-template"),
        "document_separator_sha256": _digest("document-separator"),
    }
    fields.update(overrides)
    return SemanticTokenContract(**fields)


def _contract_payload(source: str = "oracle", **overrides: str) -> dict[str, str]:
    contract = _contract(source, **overrides)
    return {
        "source": contract.source,
        "tokenizer_family": contract.tokenizer_family,
        "vocabulary_sha256": contract.vocabulary_sha256,
        "normalization_sha256": contract.normalization_sha256,
        "special_tokens_sha256": contract.special_tokens_sha256,
        "added_tokens_sha256": contract.added_tokens_sha256,
        "chat_template_sha256": contract.chat_template_sha256,
        "document_separator_sha256": contract.document_separator_sha256,
    }


def _client() -> TestClient:
    app = FastAPI()
    registration = register(app, ns="a11oy")
    assert registration["ok"] is True
    return TestClient(app)


def test_ingress_routing_prefers_warm_locality_for_prefix_work() -> None:
    nodes = [
        TokenizerNodeSignal("fast-cold", 200_000, 0.10, 0.05, 0.10, measured=True),
        TokenizerNodeSignal("warm", 150_000, 0.95, 0.90, 0.80, measured=True),
    ]
    result = choose_ingress_node(
        nodes,
        IngressWorkload(prefix_heavy=True, prefill_heavy=True),
    )
    assert result["status"] == "PASS"
    assert result["node"] == "warm"
    assert result["evidence"] == "MEASURED"


def test_ingress_routing_blocks_without_available_node() -> None:
    result = choose_ingress_node(
        [TokenizerNodeSignal("offline", 10, 0.0, 0.0, 0.0, available=False)],
        IngressWorkload(),
    )
    assert result == {
        "status": "BLOCKED",
        "reason": "no available ingress nodes",
        "node": None,
    }


def test_ingress_routing_rejects_non_finite_signal() -> None:
    with pytest.raises(ValueError, match="finite"):
        choose_ingress_node(
            [TokenizerNodeSignal("invalid", float("nan"), 0.5, 0.5, 0.5)],
            IngressWorkload(),
        )


def test_semantic_contract_digest_ignores_provider_branding() -> None:
    assert _contract("oracle").digest() == _contract("candidate").digest()


def test_semantic_qualification_passes_only_exact_contract_and_cases() -> None:
    result = qualify_tokenizer_candidate(
        _contract("oracle"),
        _contract("candidate"),
        [TokenizerParityCase("representative", (1, 2), (1, 2), "hello", "hello")],
    )
    assert result["status"] == "PASS"
    assert result["eligible"] is True
    assert result["contract_mismatches"] == []
    assert result["case_mismatches"] == []


def test_semantic_qualification_fails_on_template_drift() -> None:
    result = qualify_tokenizer_candidate(
        _contract("oracle"),
        _contract("candidate", chat_template_sha256=_digest("other-template")),
        [TokenizerParityCase("representative", (1, 2), (1, 2), "hello", "hello")],
    )
    assert result["status"] == "FAIL"
    assert result["eligible"] is False
    assert result["contract_mismatches"] == ["chat_template_sha256"]


def test_semantic_qualification_fails_on_decoded_text_drift() -> None:
    result = qualify_tokenizer_candidate(
        _contract("oracle"),
        _contract("candidate"),
        [TokenizerParityCase("decode", (1, 2), (1, 2), "hello", " hello")],
    )
    assert result["status"] == "FAIL"
    assert result["case_mismatches"] == ["decode"]


def test_semantic_qualification_blocks_without_representative_cases() -> None:
    result = qualify_tokenizer_candidate(
        _contract("oracle"),
        _contract("candidate"),
        [],
    )
    assert result["status"] == "BLOCKED"
    assert result["eligible"] is False


def test_prefix_foundry_is_contract_bound_and_bounded() -> None:
    foundry = PrefixFoundry(max_entries=2, max_bytes=7)
    contract_a = _contract("a").digest()
    contract_b = _contract("b", chat_template_sha256=_digest("b-template")).digest()

    first = foundry.put("system", contract_a, b"abc")
    assert foundry.put("system", contract_a, b"abc") == first
    assert foundry.put("system", contract_b, b"abc") != first

    third = foundry.put("tool", contract_a, b"de")
    assert foundry.get(first) is None
    assert foundry.get(third) == b"de"
    assert foundry.snapshot() == {"entries": 2, "bytes": 5}


def test_repository_ingestion_is_deterministic_and_binary_safe(tmp_path: Path) -> None:
    (tmp_path / "z.txt").write_text("zeta\n", encoding="utf-8")
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02")

    result = ingest_repository_files(
        tmp_path,
        ["z.txt", "blob.bin", "a.txt", "z.txt", "missing.txt"],
    )
    repeated = ingest_repository_files(
        tmp_path,
        ["missing.txt", "a.txt", "blob.bin", "z.txt"],
    )

    assert result["status"] == "PASS"
    assert result["batch_sha256"] == repeated["batch_sha256"]
    assert [row["path"] for row in result["files"]] == ["a.txt", "blob.bin", "z.txt"]
    assert result["text_payloads"] == {"a.txt": "alpha\n", "z.txt": "zeta\n"}
    assert {item["reason"] for item in result["skipped"]} == {
        "binary",
        "not-a-file",
    }


def test_repository_ingestion_rejects_parent_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes repository root"):
        ingest_repository_files(tmp_path, ["../secret.txt"])


def test_repository_ingestion_skips_symlink(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-token-ingress.txt"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    result = ingest_repository_files(tmp_path, ["linked.txt"])
    assert result["status"] == "PASS"
    assert result["files"] == []
    assert result["skipped"] == [{"path": "linked.txt", "reason": "symlink"}]


def test_repository_ingestion_enforces_file_count_and_total_budgets(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"1234")
    (tmp_path / "b.txt").write_bytes(b"5678")

    count_result = ingest_repository_files(tmp_path, ["a.txt", "b.txt"], max_files=1)
    byte_result = ingest_repository_files(
        tmp_path,
        ["a.txt", "b.txt"],
        max_total_bytes=6,
    )

    assert count_result["status"] == "BLOCKED"
    assert count_result["reason"] == "file-count-budget"
    assert byte_result["status"] == "BLOCKED"
    assert byte_result["reason"] == "total-ingest-byte-budget"
    assert byte_result["total_bytes"] == 4


def test_verifier_reinvestment_preserves_evidence_authority() -> None:
    modeled = verifier_reinvestment(100.0)
    measured = verifier_reinvestment(100.0, measured=True)
    assert modeled["evidence"] == "MODELED"
    assert measured["evidence"] == "MEASURED"
    assert sum(modeled["verification_budget_ms"].values()) == pytest.approx(100.0)


def test_verifier_reinvestment_rejects_non_finite_budget() -> None:
    with pytest.raises(ValueError, match="finite"):
        verifier_reinvestment(float("inf"))


def test_http_status_reports_bounded_zero_effector_contract() -> None:
    response = _client().get("/api/a11oy/v1/token-ingress/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["implementation"] == "REAL"
    assert payload["telemetry"] == "CALLER_SAMPLE_ONLY"
    assert payload["tokenizer_promotion"] == "FAIL_CLOSED_SEMANTIC_CONTRACT_REQUIRED"
    assert payload["effectors"] == 0
    assert payload["provider_calls"] == 0
    assert payload["network_calls"] == 0


def test_http_route_forces_public_evidence_to_sample() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/route",
        json={
            "nodes": [
                {
                    "node_id": "sample",
                    "tokenizer_tokens_per_sec": 1000,
                    "tokenizer_cache_warmth": 0.9,
                    "prefix_cache_hit_rate": 0.8,
                    "kv_cache_hit_rate": 0.7,
                    "measured": True,
                }
            ],
            "workload": {"prefix_heavy": True},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["evidence"] == "SAMPLE"
    assert payload["telemetry_authority"] == "CALLER_SUPPLIED_NOT_MEASURED"


def test_http_route_returns_conflict_when_no_node_is_available() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/route",
        json={
            "nodes": [
                {
                    "node_id": "offline",
                    "tokenizer_tokens_per_sec": 1,
                    "tokenizer_cache_warmth": 0,
                    "prefix_cache_hit_rate": 0,
                    "kv_cache_hit_rate": 0,
                    "available": False,
                }
            ]
        },
    )
    assert response.status_code == 409
    payload = response.json()
    assert payload["accepted"] is False
    assert payload["status"] == "BLOCKED"


def test_http_route_rejects_non_finite_and_duplicate_json() -> None:
    client = _client()
    non_finite = client.post(
        "/api/a11oy/v1/token-ingress/route",
        content=b'{"nodes":[{"node_id":"n","tokenizer_tokens_per_sec":NaN}]}',
        headers={"content-type": "application/json"},
    )
    duplicate = client.post(
        "/api/a11oy/v1/token-ingress/route",
        content=b'{"nodes":[],"nodes":[]}',
        headers={"content-type": "application/json"},
    )
    assert non_finite.status_code == 422
    assert duplicate.status_code == 422


def test_http_route_rejects_boolean_number_and_unknown_field() -> None:
    client = _client()
    boolean_number = client.post(
        "/api/a11oy/v1/token-ingress/route",
        json={
            "nodes": [
                {
                    "node_id": "n",
                    "tokenizer_tokens_per_sec": True,
                    "tokenizer_cache_warmth": 0.5,
                    "prefix_cache_hit_rate": 0.5,
                    "kv_cache_hit_rate": 0.5,
                }
            ]
        },
    )
    unknown = client.post(
        "/api/a11oy/v1/token-ingress/route",
        json={
            "nodes": [
                {
                    "node_id": "n",
                    "tokenizer_tokens_per_sec": 1,
                    "tokenizer_cache_warmth": 0.5,
                    "prefix_cache_hit_rate": 0.5,
                    "kv_cache_hit_rate": 0.5,
                    "provider_key": "not-accepted",
                }
            ]
        },
    )
    assert boolean_number.status_code == 422
    assert unknown.status_code == 422


def test_http_semantic_qualification_passes_exact_contract() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/qualify",
        json={
            "oracle_contract": _contract_payload("oracle"),
            "candidate_contract": _contract_payload("candidate"),
            "cases": [
                {
                    "name": "exact",
                    "oracle_ids": [1, 2],
                    "candidate_ids": [1, 2],
                    "oracle_decoded_text": "hello",
                    "candidate_decoded_text": "hello",
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["eligible"] is True
    assert payload["contract_mismatches"] == []


def test_http_semantic_qualification_fails_on_contract_drift() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/qualify",
        json={
            "oracle_contract": _contract_payload("oracle"),
            "candidate_contract": _contract_payload(
                "candidate",
                document_separator_sha256=_digest("different-separator"),
            ),
            "cases": [
                {
                    "name": "ids-match",
                    "oracle_ids": [1, 2],
                    "candidate_ids": [1, 2],
                    "oracle_decoded_text": "hello",
                    "candidate_decoded_text": "hello",
                }
            ],
        },
    )
    assert response.status_code == 409
    payload = response.json()
    assert payload["accepted"] is False
    assert payload["contract_mismatches"] == ["document_separator_sha256"]


def test_http_semantic_qualification_blocks_empty_cases() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/qualify",
        json={
            "oracle_contract": _contract_payload("oracle"),
            "candidate_contract": _contract_payload("candidate"),
            "cases": [],
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["accepted"] is False
    assert payload["status"] == "BLOCKED"


def test_http_semantic_qualification_rejects_boolean_token_ids() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/qualify",
        json={
            "oracle_contract": _contract_payload("oracle"),
            "candidate_contract": _contract_payload("candidate"),
            "cases": [
                {
                    "name": "invalid",
                    "oracle_ids": [True],
                    "candidate_ids": [1],
                    "oracle_decoded_text": "a",
                    "candidate_decoded_text": "a",
                }
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["accepted"] is False


def test_http_verification_budget_is_always_modeled() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/verification-budget",
        json={"saved_milliseconds": 25, "measured": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence"] == "MODELED"
    assert payload["measurement_authority"] == "NOT_ACCEPTED_FROM_PUBLIC_CALLER"
