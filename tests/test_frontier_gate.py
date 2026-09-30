# SPDX-License-Identifier: Apache-2.0
from szl_frontier_gate import (
    TRUST_CEILING,
    bind_count,
    clamp_trust,
    decide,
    estate_gate,
    frontier_status,
    never_live_from_http,
    retrieve_or_abstain,
)


def test_trust_ceiling_refuses_one():
    out = clamp_trust(1.0)
    assert out["admitted"] == TRUST_CEILING
    assert out["kind"] == "policy"
    assert out["honesty"] == "HOLD"


def test_zero_stays_zero():
    assert bind_count(0)["kind"] == "zero"
    assert bind_count(0)["value"] == 0


def test_http_200_is_not_live():
    assert never_live_from_http(200)["live"] is False


def test_estate_gate_cannot_all_done_over_skipped_children():
    out = estate_gate({"a": "EXECUTED_PASS", "b": "NOT_EXECUTED"})
    assert out["all_done"] is False
    assert out["verdict"] == "HOLD"
    assert "b" in out["failed_or_skipped"]


def test_empty_children_is_hold_not_all_done():
    out = estate_gate({})
    assert out["all_done"] is False
    assert out["verdict"] == "HOLD"


def test_private_query_abstains():
    out = retrieve_or_abstain("What is my private memory?", [{"id": "p", "visibility": "public"}])
    assert out["abstain"] is True
    assert out["reason"] == "PRIVATE_SOURCE_NOT_BOUND"


def test_tenant_attempt_abstains():
    out = retrieve_or_abstain("Lyte pin", [{"id": "p", "visibility": "public"}], tenant="acct-9")
    assert out["abstain"] is True


def test_revoked_docs_abstain():
    out = retrieve_or_abstain("pin", [{"id": "p", "visibility": "public", "revoked": True}])
    assert out["abstain"] is True


def test_allow_from_retrieved_instruction_is_blocked():
    out = decide({"action": "ALLOW", "retrieved_approved": True, "trust": 1.0})
    assert out["decision"] == "BLOCKED"
    assert out["trust"]["admitted"] == TRUST_CEILING


def test_receipt_cannot_execute():
    assert decide({"source": "receipt"})["decision"] == "BLOCKED"


def test_frontier_status_refuses_agi_claim():
    body = frontier_status()
    assert body["agi_claim"] is False
    assert body["lambda"] == "Conjecture 1"
    assert body["compiled_kernel"]["v1"] == "missing"
    assert body["estate_gate"]["all_done"] is False
