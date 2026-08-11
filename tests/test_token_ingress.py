# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.token_ingress import register
from routers.token_ingress_core import (
    IngressWorkload,
    PrefixFoundry,
    TokenizerNodeSignal,
    TokenizerParityCase,
    choose_ingress_node,
    ingest_repository_files,
    qualify_tokenizer_candidate,
    verifier_reinvestment,
)


def test_ingress_routing_prefers_warm_cache_for_prefix_workload() -> None:
    nodes = [
        TokenizerNodeSignal("fast-cold", 200_000, 0.10, 0.05, 0.10, measured=True),
        TokenizerNodeSignal("warm", 150_000, 0.95, 0.90, 0.80, measured=True),
    ]
    result = choose_ingress_node(nodes, IngressWorkload(prefix_heavy=True, prefill_heavy=True))
    assert result["status"] == "PASS"
    assert result["node"] == "warm"
    assert result["evidence"] == "MEASURED"


def test_ingress_routing_blocks_without_available_node() -> None:
    result = choose_ingress_node(
        [TokenizerNodeSignal("offline", 10, 0.0, 0.0, 0.0, available=False)],
        IngressWorkload(),
    )
    assert result == {"status": "BLOCKED", "reason": "no available ingress nodes", "node": None}


def test_ingress_routing_rejects_non_finite_signal() -> None:
    with pytest.raises(ValueError, match="finite"):
        choose_ingress_node(
            [TokenizerNodeSignal("nan-node", float("nan"), 0.5, 0.5, 0.5)],
            IngressWorkload(),
        )


def test_tokenizer_parity_fails_closed_on_token_mismatch() -> None:
    cases = [
        TokenizerParityCase("same", (1, 2), (1, 2), ("<eos>",), ("<eos>",), "abc", "abc"),
        TokenizerParityCase("different", (3, 4), (3, 5), (), (), "x", "x"),
    ]
    result = qualify_tokenizer_candidate("hf", "candidate", cases)
    assert result["eligible"] is False
    assert result["status"] == "FAIL"
    assert result["mismatches"] == ["different"]


def test_tokenizer_parity_blocks_without_cases() -> None:
    result = qualify_tokenizer_candidate("hf", "candidate", [])
    assert result["status"] == "BLOCKED"
    assert result["eligible"] is False


def test_prefix_foundry_is_content_addressed_and_bounded() -> None:
    foundry = PrefixFoundry(max_entries=2, max_bytes=7)
    first = foundry.put("system", b"abc")
    assert foundry.put("system", b"abc") == first
    second = foundry.put("tool", b"de")
    assert foundry.get(second) == b"de"
    third = foundry.put("persona", b"fgh")
    assert foundry.get(first) is None
    assert foundry.get(third) == b"fgh"
    assert foundry.snapshot() == {"entries": 2, "bytes": 5}


def test_repository_ingestion_is_contained_and_binary_safe(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02")
    result = ingest_repository_files(tmp_path, ["a.txt", "blob.bin", "missing.txt"])
    assert result["status"] == "PASS"
    assert result["text_payloads"] == {"a.txt": "alpha\n"}
    assert {item["reason"] for item in result["skipped"]} == {"binary", "not-a-file"}
    assert len(result["files"]) == 2


def test_repository_ingestion_rejects_parent_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="escapes repository root"):
        ingest_repository_files(tmp_path, ["../secret.txt"])


def test_repository_ingestion_blocks_total_budget(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"1234")
    (tmp_path / "b.txt").write_bytes(b"5678")
    result = ingest_repository_files(tmp_path, ["a.txt", "b.txt"], max_total_bytes=6)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "total-ingest-byte-budget"
    assert result["total_bytes"] == 4


def test_verifier_reinvestment_preserves_honest_evidence_label() -> None:
    modeled = verifier_reinvestment(100.0)
    measured = verifier_reinvestment(100.0, measured=True)
    assert modeled["evidence"] == "MODELED"
    assert measured["evidence"] == "MEASURED"
    assert sum(modeled["verification_budget_ms"].values()) == pytest.approx(100.0)


def test_verifier_reinvestment_rejects_non_finite_budget() -> None:
    with pytest.raises(ValueError, match="finite"):
        verifier_reinvestment(float("inf"))


def _client() -> TestClient:
    app = FastAPI()
    registration = register(app, ns="a11oy")
    assert registration["ok"] is True
    return TestClient(app)


def test_http_status_is_read_only_and_honest() -> None:
    response = _client().get("/api/a11oy/v1/token-ingress/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["implementation"] == "REAL"
    assert payload["telemetry"] == "CALLER_SAMPLE_ONLY"
    assert payload["effectors"] == 0
    assert payload["provider_calls"] == 0


def test_http_route_never_accepts_public_measured_claim() -> None:
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
    assert payload["evidence"] == "SAMPLE"
    assert payload["telemetry_authority"] == "CALLER_SUPPLIED_NOT_MEASURED"


def test_http_route_preserves_blocked_no_node_disposition() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/route",
        json={
            "nodes": [
                {
                    "node_id": "offline",
                    "tokenizer_tokens_per_sec": 1000,
                    "tokenizer_cache_warmth": 0.5,
                    "prefix_cache_hit_rate": 0.5,
                    "kv_cache_hit_rate": 0.5,
                    "available": False,
                }
            ]
        },
    )
    assert response.status_code == 409
    payload = response.json()
    assert payload["accepted"] is False
    assert payload["status"] == "BLOCKED"
    assert payload["node"] is None


def test_http_route_rejects_non_finite_json_number() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/route",
        content=b'{"nodes":[{"node_id":"n","tokenizer_tokens_per_sec":NaN,"tokenizer_cache_warmth":0.5,"prefix_cache_hit_rate":0.5,"kv_cache_hit_rate":0.5}]}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["accepted"] is False


def test_http_route_rejects_duplicate_json_fields() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/route",
        content=b'{"nodes":[],"nodes":[]}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["accepted"] is False


def test_http_qualification_fails_closed_on_semantic_mismatch() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/qualify",
        json={
            "oracle": "hf",
            "candidate": "candidate",
            "cases": [{"name": "mismatch", "oracle_ids": [1, 2], "candidate_ids": [1, 3]}],
        },
    )
    assert response.status_code == 409
    payload = response.json()
    assert payload["status"] == "FAIL"
    assert payload["eligible"] is False
    assert payload["effectors"] == 0


def test_http_qualification_rejects_boolean_token_ids() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/qualify",
        json={
            "oracle": "hf",
            "candidate": "candidate",
            "cases": [{"name": "bad", "oracle_ids": [True], "candidate_ids": [1]}],
        },
    )
    assert response.status_code == 422
    assert response.json()["accepted"] is False


def test_http_verification_budget_is_modeled_only() -> None:
    response = _client().post(
        "/api/a11oy/v1/token-ingress/verification-budget",
        json={"saved_milliseconds": 25, "measured": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence"] == "MODELED"
    assert payload["measurement_authority"] == "NOT_ACCEPTED_FROM_PUBLIC_CALLER"
