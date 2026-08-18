# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11

import hashlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from szl_budget_router import (
    IngressWorkload,
    PrefixFoundry,
    SemanticTokenContract,
    TokenizerNodeSignal,
    TokenizerParityCase,
    choose_ingress_node,
    ingest_repository_files,
    qualify_tokenizer_candidate,
    register,
    verifier_reinvestment,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _contract(source: str = "oracle", **overrides: str) -> SemanticTokenContract:
    values = {
        "source": source,
        "tokenizer_family": "BPE",
        "vocabulary_sha256": _digest("vocabulary"),
        "normalization_sha256": _digest("normalization"),
        "special_tokens_sha256": _digest("special"),
        "added_tokens_sha256": _digest("added"),
        "chat_template_sha256": _digest("chat"),
        "document_separator_sha256": _digest("separator"),
    }
    values.update(overrides)
    return SemanticTokenContract(**values)


def _payload(source: str = "oracle", **overrides: str) -> dict[str, str]:
    value = _contract(source, **overrides)
    return {
        "source": value.source,
        "tokenizer_family": value.tokenizer_family,
        "vocabulary_sha256": value.vocabulary_sha256,
        "normalization_sha256": value.normalization_sha256,
        "special_tokens_sha256": value.special_tokens_sha256,
        "added_tokens_sha256": value.added_tokens_sha256,
        "chat_template_sha256": value.chat_template_sha256,
        "document_separator_sha256": value.document_separator_sha256,
    }


def _client() -> TestClient:
    app = FastAPI()
    register(app, ns="a11oy")
    return TestClient(app)


def test_existing_budget_routes_remain_registered() -> None:
    app = FastAPI()
    register(app, ns="a11oy")
    paths = {getattr(route, "path", None) for route in app.router.routes}
    assert "/budget-router" in paths
    assert "/api/a11oy/v1/budget/tiers" in paths
    assert "/api/a11oy/v1/budget/route" in paths
    assert "/api/a11oy/v1/budget/skeletons" in paths


def test_prefix_heavy_routing_prefers_warm_locality() -> None:
    result = choose_ingress_node(
        [
            TokenizerNodeSignal("fast-cold", 200_000, 0.1, 0.05, 0.1, measured=True),
            TokenizerNodeSignal("warm", 150_000, 0.95, 0.9, 0.8, measured=True),
        ],
        IngressWorkload(prefix_heavy=True, prefill_heavy=True),
    )
    assert result["status"] == "PASS"
    assert result["node"] == "warm"
    assert result["evidence"] == "MEASURED"


def test_routing_blocks_no_available_node_and_rejects_nan() -> None:
    blocked = choose_ingress_node(
        [TokenizerNodeSignal("off", 1, 0, 0, 0, available=False)],
        IngressWorkload(),
    )
    assert blocked["status"] == "BLOCKED"
    with pytest.raises(ValueError, match="finite"):
        choose_ingress_node(
            [TokenizerNodeSignal("bad", float("nan"), 0.5, 0.5, 0.5)],
            IngressWorkload(),
        )


def test_semantic_contract_pass_and_template_drift_failure() -> None:
    case = TokenizerParityCase("exact", (1, 2), (1, 2), "hello", "hello")
    passed = qualify_tokenizer_candidate(_contract(), _contract("candidate"), [case])
    failed = qualify_tokenizer_candidate(
        _contract(),
        _contract("candidate", chat_template_sha256=_digest("other")),
        [case],
    )
    assert passed["eligible"] is True
    assert failed["eligible"] is False
    assert failed["contract_mismatches"] == ["chat_template_sha256"]


def test_semantic_contract_fails_on_decode_and_blocks_no_cases() -> None:
    failed = qualify_tokenizer_candidate(
        _contract(),
        _contract("candidate"),
        [TokenizerParityCase("decode", (1,), (1,), "a", " a")],
    )
    blocked = qualify_tokenizer_candidate(_contract(), _contract("candidate"), [])
    assert failed["case_mismatches"] == ["decode"]
    assert blocked["status"] == "BLOCKED"


def test_prefix_foundry_binds_contract_and_evicts() -> None:
    foundry = PrefixFoundry(max_entries=2, max_bytes=7)
    first = foundry.put("system", _contract().digest(), b"abc")
    second_contract = _contract(
        "other", chat_template_sha256=_digest("other")
    ).digest()
    assert foundry.put("system", second_contract, b"abc") != first
    third = foundry.put("tool", _contract().digest(), b"de")
    assert foundry.get(first) is None
    assert foundry.get(third) == b"de"


def test_repository_ingestion_is_deterministic_binary_safe_and_contained(
    tmp_path: Path,
) -> None:
    (tmp_path / "z.txt").write_text("zeta\n", encoding="utf-8")
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01")
    first = ingest_repository_files(
        tmp_path, ["z.txt", "a.txt", "blob.bin", "z.txt"]
    )
    second = ingest_repository_files(tmp_path, ["blob.bin", "a.txt", "z.txt"])
    assert first["batch_sha256"] == second["batch_sha256"]
    assert [row["path"] for row in first["files"]] == [
        "a.txt",
        "blob.bin",
        "z.txt",
    ]
    with pytest.raises(ValueError, match="escapes"):
        ingest_repository_files(tmp_path, ["../outside"])


def test_repository_ingestion_refuses_symlink_and_budgets(tmp_path: Path) -> None:
    outside = tmp_path.parent / "budget-token-outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(str(exc))
    assert ingest_repository_files(tmp_path, ["link.txt"])["skipped"] == [
        {"path": "link.txt", "reason": "symlink"}
    ]
    (tmp_path / "a.txt").write_bytes(b"1234")
    (tmp_path / "b.txt").write_bytes(b"5678")
    assert (
        ingest_repository_files(tmp_path, ["a.txt", "b.txt"], max_files=1)[
            "reason"
        ]
        == "file-count-budget"
    )
    assert (
        ingest_repository_files(tmp_path, ["a.txt", "b.txt"], max_total_bytes=6)[
            "reason"
        ]
        == "total-ingest-byte-budget"
    )


def test_verifier_reinvestment_authority() -> None:
    assert verifier_reinvestment(10)["evidence"] == "MODELED"
    assert verifier_reinvestment(10, measured=True)["evidence"] == "MEASURED"
    with pytest.raises(ValueError, match="finite"):
        verifier_reinvestment(float("inf"))


def test_http_status_is_zero_effector() -> None:
    response = _client().get("/api/a11oy/v1/token-ingress/status")
    assert response.status_code == 200
    body = response.json()
    assert body["implementation"] == "REAL"
    assert body["effectors"] == 0
    assert body["provider_calls"] == 0
    assert body["network_calls"] == 0


def test_http_routing_forces_sample_and_blocks_offline() -> None:
    online = _client().post(
        "/api/a11oy/v1/token-ingress/route",
        json={
            "nodes": [
                {
                    "node_id": "n",
                    "tokenizer_tokens_per_sec": 10,
                    "tokenizer_cache_warmth": 0.5,
                    "prefix_cache_hit_rate": 0.5,
                    "kv_cache_hit_rate": 0.5,
                    "measured": True,
                }
            ]
        },
    )
    offline = _client().post(
        "/api/a11oy/v1/token-ingress/route",
        json={
            "nodes": [
                {
                    "node_id": "n",
                    "tokenizer_tokens_per_sec": 10,
                    "tokenizer_cache_warmth": 0.5,
                    "prefix_cache_hit_rate": 0.5,
                    "kv_cache_hit_rate": 0.5,
                    "available": False,
                }
            ]
        },
    )
    assert online.json()["evidence"] == "SAMPLE"
    assert offline.status_code == 409
    assert offline.json()["accepted"] is False


def test_http_rejects_duplicate_nan_boolean_and_unknown_fields() -> None:
    client = _client()
    duplicate = client.post(
        "/api/a11oy/v1/token-ingress/route",
        content=b'{"nodes":[],"nodes":[]}',
        headers={"content-type": "application/json"},
    )
    non_finite = client.post(
        "/api/a11oy/v1/token-ingress/route",
        content=b'{"nodes":[{"node_id":"n","tokenizer_tokens_per_sec":NaN}]}',
        headers={"content-type": "application/json"},
    )
    boolean = client.post(
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
                    "token": "forbidden",
                }
            ]
        },
    )
    assert {
        duplicate.status_code,
        non_finite.status_code,
        boolean.status_code,
        unknown.status_code,
    } == {422}


def test_http_qualification_and_modeled_budget() -> None:
    exact = _client().post(
        "/api/a11oy/v1/token-ingress/qualify",
        json={
            "oracle_contract": _payload(),
            "candidate_contract": _payload("candidate"),
            "cases": [
                {
                    "name": "exact",
                    "oracle_ids": [1],
                    "candidate_ids": [1],
                    "oracle_decoded_text": "a",
                    "candidate_decoded_text": "a",
                }
            ],
        },
    )
    mismatch = _client().post(
        "/api/a11oy/v1/token-ingress/qualify",
        json={
            "oracle_contract": _payload(),
            "candidate_contract": _payload(
                "candidate",
                document_separator_sha256=_digest("different"),
            ),
            "cases": [
                {
                    "name": "exact",
                    "oracle_ids": [1],
                    "candidate_ids": [1],
                    "oracle_decoded_text": "a",
                    "candidate_decoded_text": "a",
                }
            ],
        },
    )
    budget = _client().post(
        "/api/a11oy/v1/token-ingress/verification-budget",
        json={"saved_milliseconds": 25, "measured": True},
    )
    assert exact.status_code == 200
    assert mismatch.status_code == 409
    assert budget.json()["evidence"] == "MODELED"
