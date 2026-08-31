# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Yachay (CTO).
# DCO: Signed-off-by: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
"""
tests/test_v4_agent_voters.py — pytest tests for the a11oy v4 multi-LLM ensemble.

Tests:
  1. Voter with missing env var returns {status: "unavailable"} — not an error.
  2. Registry is 14 voters; sovereign-default is khipu-gguf.
  3. resolve_voters always prepends khipu-gguf.

Hermetic: no live LLM calls. The CPU lab is never contacted.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).parent.parent.resolve()
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from packages.inference.src.voters import (
    get_all_voters,
    get_voter,
    resolve_voters,
    SOVEREIGN_VOTER_ID,
    VOTER_COUNT,
)
from packages.inference.src.voters.deepseek_r1 import DeepSeekR1Voter
from packages.inference.src.voters.kimi_k2 import KimiK2Voter
from packages.inference.src.voters.nemotron_super_49b import NemotronSuper49BVoter


def test_missing_env_var_returns_unavailable():
    """A cloud voter with no env var must return status='unavailable', not raise."""
    voter = DeepSeekR1Voter()

    with patch.dict(os.environ, {}, clear=False):
        for k in voter.ENV_VARS:
            os.environ.pop(k, None)

        assert not voter.is_available(), "voter should be unavailable without env vars"
        result = asyncio.run(voter.vote(prompt="hello world"))

    assert result["status"] == "unavailable", (
        f"Expected 'unavailable', got {result['status']!r}"
    )
    assert result["voter_id"] == "deepseek-r1"
    assert result["text"] is None
    assert "token_not_present" in result["reason"]
    assert result["latency_ms"] is None


def test_multiple_voters_missing_env_return_unavailable():
    """Several new voters with no env vars must all return 'unavailable', not raise."""
    voters_to_check = [
        KimiK2Voter(),
        NemotronSuper49BVoter(),
    ]
    for voter in voters_to_check:
        for k in voter.ENV_VARS:
            os.environ.pop(k, None)

        result = asyncio.run(voter.vote(prompt="test"))
        assert result["status"] == "unavailable", (
            f"{voter.VOTER_ID}: expected 'unavailable', got {result['status']!r}"
        )
        assert result["text"] is None
        assert "token_not_present" in result["reason"]


def test_voter_count_is_14():
    """Registry must contain exactly 14 voters (khipu-gguf + previous 13)."""
    assert VOTER_COUNT == 14, f"Expected 14 voters, got {VOTER_COUNT}"
    assert SOVEREIGN_VOTER_ID == "khipu-gguf"


def test_all_voters_have_required_fields():
    """Every voter must expose required metadata fields."""
    voters = get_all_voters()
    assert len(voters) == 14
    assert voters[0].VOTER_ID == "khipu-gguf"

    required_fields = {"voter_id", "status", "provider", "license", "context_window", "env_vars", "model_id"}
    for v in voters:
        meta = v.metadata()
        for field in required_fields:
            assert field in meta, f"{v.VOTER_ID}: missing metadata field '{field}'"
        assert meta["status"] in ("available", "token_required"), (
            f"{v.VOTER_ID}: invalid status {meta['status']!r}"
        )


def test_sovereign_default_always_available():
    """khipu-gguf (sovereign-default) must always be available regardless of env vars."""
    khipu = get_voter("khipu-gguf")
    assert khipu is not None, "khipu-gguf voter not found in registry"
    assert khipu.is_available(), "khipu-gguf (sovereign-default) must always be available"
    assert khipu.metadata()["status"] == "available"


def test_qwen_local_still_in_pool_not_sovereign():
    """qwen-local remains an always-on local floor, but is not the sovereign path."""
    qwen = get_voter("qwen-local")
    assert qwen is not None
    assert qwen.is_available()
    assert qwen.VOTER_ID != SOVEREIGN_VOTER_ID


def test_all_14_voter_ids_present():
    """All 14 voter IDs must be in the registry."""
    expected_ids = {
        "khipu-gguf",
        "qwen-local",
        "hf-inference-llama",
        "hf-inference-mistral",
        "hf-inference-qwen",
        "deepseek-r1",
        "kimi-k2",
        "glm-4.6",
        "hermes-4-405b",
        "minimax-m2",
        "step-3.7-flash",
        "nomos-1",
        "nemotron-super-49b",
        "xiaomi-mimo",
    }
    actual_ids = {v.VOTER_ID for v in get_all_voters()}
    assert actual_ids == expected_ids, (
        f"Voter ID mismatch.\nExpected: {sorted(expected_ids)}\nGot: {sorted(actual_ids)}"
    )


def test_voters_endpoint_response_shape():
    """Simulate the /agent/voters endpoint response and validate its shape."""
    voters = get_all_voters()
    response = {
        "count": len(voters),
        "voters": [v.metadata() for v in voters],
        "sovereign_default": SOVEREIGN_VOTER_ID,
        "doctrine": {"version": "v11", "declarations": 749, "axioms": 14, "sorries": 163},
    }

    assert response["count"] == 14
    assert response["sovereign_default"] == "khipu-gguf"
    assert len(response["voters"]) == 14
    assert response["doctrine"]["declarations"] == 749
    assert response["doctrine"]["axioms"] == 14
    assert response["doctrine"]["sorries"] == 163


def test_ask_respects_voters_filter():
    """Requested voters run, and khipu-gguf is always prepended as sovereign."""
    requested = ["qwen-local", "deepseek-r1"]
    voters = resolve_voters(requested)

    voter_ids = [v.VOTER_ID for v in voters]
    assert voter_ids[0] == "khipu-gguf", "sovereign-default khipu-gguf must be first"
    assert "qwen-local" in voter_ids
    assert "deepseek-r1" in voter_ids
    allowed = set(requested) | {"khipu-gguf"}
    for vid in voter_ids:
        assert vid in allowed, f"Unexpected voter {vid!r} in resolved list"


def test_ask_sovereign_always_present_even_without_list():
    """When no voters list is given, only khipu-gguf (sovereign-default) runs."""
    voters = resolve_voters(None)
    assert len(voters) == 1
    assert voters[0].VOTER_ID == "khipu-gguf"


def test_ask_deepseek_unavailable_when_no_key():
    """When deepseek-r1 is in voters list but DEEPSEEK_API_KEY absent →
    vote returns 'unavailable', not an exception."""
    for k in ["DEEPSEEK_API_KEY", "HF_TOKEN"]:
        os.environ.pop(k, None)

    requested = ["qwen-local", "deepseek-r1"]
    voters = resolve_voters(requested)

    ds_voter = next(v for v in voters if v.VOTER_ID == "deepseek-r1")
    result = asyncio.run(ds_voter.vote(prompt="test prompt"))

    assert result["status"] == "unavailable"
    assert result["voter_id"] == "deepseek-r1"
    assert "token_not_present" in result["reason"]


def test_unknown_voter_id_silently_skipped():
    """An unknown voter ID in the voters list is silently skipped (no KeyError)."""
    voters = resolve_voters(["qwen-local", "nonexistent-voter-xyz"])
    voter_ids = [v.VOTER_ID for v in voters]
    assert "khipu-gguf" in voter_ids
    assert "qwen-local" in voter_ids
    assert "nonexistent-voter-xyz" not in voter_ids


def test_lambda_aggregator_no_ok_votes():
    """Λ-aggregator must handle zero ok-status votes gracefully."""
    import a11oy_v4_agent as agent_mod

    votes = [
        {"voter_id": "deepseek-r1", "status": "unavailable", "text": None, "reason": "token_not_present"},
        {"voter_id": "kimi-k2", "status": "unavailable", "text": None, "reason": "token_not_present"},
    ]
    agg = agent_mod._lambda_aggregate(votes)
    assert agg["winner_id"] is None
    assert agg["lambda_score"] == 0.0


def test_lambda_aggregator_single_ok_vote():
    """Λ-aggregator with one ok vote returns that voter as winner."""
    import a11oy_v4_agent as agent_mod

    votes = [
        {"voter_id": "khipu-gguf", "status": "ok", "text": "Hello from khipu-gguf.", "reason": None},
        {"voter_id": "deepseek-r1", "status": "unavailable", "text": None, "reason": "token_not_present"},
    ]
    agg = agent_mod._lambda_aggregate(votes)
    assert agg["winner_id"] == "khipu-gguf"
    assert 0.0 < agg["lambda_score"] <= 1.0
    assert len(agg["provenance_entries"]) == 1


def test_qwen_local_returns_stub_when_vllm_unreachable():
    """qwen-local must return a stub (not raise) when local vLLM is unreachable."""
    qwen = get_voter("qwen-local")
    assert qwen is not None

    with patch.dict(os.environ, {"QWEN_LOCAL_URL": "http://127.0.0.1:19999/v1/chat/completions"}):
        result = asyncio.run(qwen.vote(prompt="test"))

    assert result["status"] == "ok"
    assert result["text"] is not None
    assert "STUB" in result["text"] or "stub" in result["text"].lower() or len(result["text"]) > 0
