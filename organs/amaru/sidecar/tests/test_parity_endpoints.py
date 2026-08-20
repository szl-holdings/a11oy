# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 (NOT a theorem).
"""
Tests for parity endpoints: /v1/confidence and /v1/eval.

Parity targets: Fiddler AI (faithfulness/hallucination), Arize Phoenix (evals),
LangSmith (retrieval evals). amaru's edge: every score is Λ-gated + receipt-stamped.

Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from amaru.app import app  # noqa: E402

_client = TestClient(app)


# ─── /v1/confidence ───────────────────────────────────────────────────────────

class TestConfidenceEndpoint:
    def test_basic_response_shape(self) -> None:
        r = _client.post("/v1/confidence", json={
            "question": "What is chain-of-verification?",
            "answer": "Chain-of-verification reduces hallucination. See https://arxiv.org/abs/2309.11495",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "confidence" in body
        assert "scores" in body
        assert "hallucination_risk" in body

    def test_confidence_in_unit_interval(self) -> None:
        r = _client.post("/v1/confidence", json={
            "question": "What is RAG?",
            "answer": "RAG retrieves docs. See https://arxiv.org/abs/2005.11401",
        })
        body = r.json()
        assert 0.0 <= body["confidence"] <= 1.0

    def test_sub_scores_present(self) -> None:
        r = _client.post("/v1/confidence", json={
            "question": "test",
            "answer": "answer https://example.com",
        })
        body = r.json()
        scores = body["scores"]
        assert "citation_coverage" in scores
        assert "cove_consistency" in scores
        assert "lambda_score" in scores

    def test_no_citation_raises_hallucination_risk(self) -> None:
        r = _client.post("/v1/confidence", json={
            "question": "What is X?",
            "answer": "X is a thing with no source.",
        })
        body = r.json()
        assert body["hallucination_risk"] is True

    def test_cited_answer_lower_risk(self) -> None:
        cited_r = _client.post("/v1/confidence", json={
            "question": "What is chain-of-thought?",
            "answer": "Chain-of-thought prompting. See https://arxiv.org/abs/2201.11903",
        })
        plain_r = _client.post("/v1/confidence", json={
            "question": "What is chain-of-thought?",
            "answer": "Chain-of-thought prompting. No source.",
        })
        assert cited_r.json()["scores"]["citation_coverage"] > plain_r.json()["scores"]["citation_coverage"]

    def test_verification_answer_affects_cove_score(self) -> None:
        consistent_r = _client.post("/v1/confidence", json={
            "question": "test question",
            "answer": "answer about dogs and cats",
            "verification_answer": "answer about dogs and cats",
        })
        divergent_r = _client.post("/v1/confidence", json={
            "question": "test question",
            "answer": "answer about dogs and cats",
            "verification_answer": "completely different topic fish",
        })
        assert consistent_r.json()["scores"]["cove_consistency"] > divergent_r.json()["scores"]["cove_consistency"]

    def test_axis_scores_influence_lambda(self) -> None:
        low_r = _client.post("/v1/confidence", json={
            "question": "test",
            "answer": "answer https://example.com",
            "axis_scores": [0.1] * 13,
        })
        high_r = _client.post("/v1/confidence", json={
            "question": "test",
            "answer": "answer https://example.com",
            "axis_scores": [1.0] * 13,
        })
        assert low_r.json()["scores"]["lambda_score"] < high_r.json()["scores"]["lambda_score"]

    def test_receipt_fields_present(self) -> None:
        r = _client.post("/v1/confidence", json={
            "question": "test",
            "answer": "answer https://example.com",
        })
        body = r.json()
        assert "input_hash" in body
        assert len(body["input_hash"]) == 64  # sha256 hex
        assert "receipt_ts" in body

    def test_doctrine_v11_in_response(self) -> None:
        r = _client.post("/v1/confidence", json={
            "question": "test",
            "answer": "ans https://example.com",
        })
        assert r.json()["doctrine"] == "v11"

    def test_lambda_conjecture_note(self) -> None:
        r = _client.post("/v1/confidence", json={
            "question": "test",
            "answer": "ans https://example.com",
        })
        assert "Conjecture" in r.json()["lambda_status"]
        assert "NOT a theorem" in r.json()["lambda_status"]

    def test_risk_label_present(self) -> None:
        r = _client.post("/v1/confidence", json={
            "question": "q",
            "answer": "a https://x.com",
        })
        assert r.json()["risk_label"] in ("HIGH", "LOW")

    def test_sources_list_present(self) -> None:
        r = _client.post("/v1/confidence", json={
            "question": "q",
            "answer": "a https://x.com",
        })
        sources = r.json()["sources"]
        assert isinstance(sources, list)
        assert any("fiddler.ai" in s.lower() for s in sources)


# ─── /v1/eval ────────────────────────────────────────────────────────────────

class TestRetrievalEvalEndpoint:
    def test_basic_response_shape(self) -> None:
        r = _client.post("/v1/eval", json={
            "question": "What is RAG?",
            "answer": "RAG retrieves documents and generates answers.",
            "chunks": ["RAG stands for Retrieval Augmented Generation."],
        })
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "metrics" in body
        assert "composite" in body

    def test_metrics_keys_present(self) -> None:
        r = _client.post("/v1/eval", json={
            "question": "test",
            "answer": "answer",
            "chunks": ["context chunk"],
        })
        metrics = r.json()["metrics"]
        assert "context_precision" in metrics
        assert "context_recall" in metrics
        assert "answer_faithfulness" in metrics
        assert "source_coverage" in metrics

    def test_all_metrics_in_unit_interval(self) -> None:
        r = _client.post("/v1/eval", json={
            "question": "chain of thought",
            "answer": "chain of thought prompting improves reasoning",
            "chunks": ["chain of thought prompting", "improves reasoning in LLMs"],
        })
        metrics = r.json()["metrics"]
        for k, v in metrics.items():
            assert 0.0 <= v <= 1.0, f"{k}={v} out of range"

    def test_composite_in_unit_interval(self) -> None:
        r = _client.post("/v1/eval", json={
            "question": "q",
            "answer": "a",
            "chunks": ["ctx"],
        })
        assert 0.0 <= r.json()["composite"] <= 1.0

    def test_empty_chunks_honest_abstain(self) -> None:
        r = _client.post("/v1/eval", json={
            "question": "q",
            "answer": "a",
            "chunks": [],
        })
        body = r.json()
        assert body["honest_abstain"] is True
        assert body["composite"] == 0.0

    def test_relevant_chunks_boost_precision(self) -> None:
        high_r = _client.post("/v1/eval", json={
            "question": "retrieval augmented generation",
            "answer": "RAG retrieves documents to augment generation.",
            "chunks": [
                "retrieval augmented generation method",
                "documents retrieved for generation tasks",
                "neural retrieval augmented models",
            ],
        })
        low_r = _client.post("/v1/eval", json={
            "question": "retrieval augmented generation",
            "answer": "RAG retrieves documents.",
            "chunks": [
                "cooking recipes for pasta",
                "weather in london today",
            ],
        })
        assert (
            high_r.json()["metrics"]["context_precision"]
            >= low_r.json()["metrics"]["context_precision"]
        )

    def test_receipt_fields_present(self) -> None:
        r = _client.post("/v1/eval", json={
            "question": "q",
            "answer": "a",
            "chunks": ["c"],
        })
        body = r.json()
        assert "input_hash" in body
        assert len(body["input_hash"]) == 64
        assert "receipt_ts" in body

    def test_method_is_token_overlap(self) -> None:
        r = _client.post("/v1/eval", json={
            "question": "q",
            "answer": "a",
            "chunks": ["c"],
        })
        assert r.json()["method"] == "token_overlap"

    def test_doctrine_v11_in_response(self) -> None:
        r = _client.post("/v1/eval", json={
            "question": "q",
            "answer": "a",
            "chunks": ["c"],
        })
        assert r.json()["doctrine"] == "v11"

    def test_lambda_conjecture_note(self) -> None:
        r = _client.post("/v1/eval", json={
            "question": "q",
            "answer": "a",
            "chunks": ["c"],
        })
        assert "Conjecture" in r.json()["lambda_status"]

    def test_sources_list_present(self) -> None:
        r = _client.post("/v1/eval", json={
            "question": "q",
            "answer": "a",
            "chunks": ["c"],
        })
        sources = r.json()["sources"]
        assert isinstance(sources, list)
        assert any("langsmith" in s.lower() or "langchain" in s.lower() for s in sources)

    def test_chunk_count_matches_input(self) -> None:
        r = _client.post("/v1/eval", json={
            "question": "q",
            "answer": "a",
            "chunks": ["c1", "c2", "c3"],
        })
        assert r.json()["chunk_count"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# Doctrine v11 LOCKED — 749 declarations / 14 unique axioms (15 raw, 1 dup) /
# 163 sorries (112 baseline + 51 Putnam). Kernel commit c7c0ba17.
# Λ = Conjecture 1 (NOT a theorem). SLSA L1 (honest).
# Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>
# ─────────────────────────────────────────────────────────────────────────────
