# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
tests/test_functest_router_receipts.py — FUNCTIONAL-PROOF squad.

Proves two consumer/investor-facing fixes are REAL and operational:

  FIX 1  /v1/router/stats (+ /api/a11oy/v1/router/stats)
         The landing-page router scene consumes exact process-lifetime routing-
         decision counters backed by trusted receipt writes. The compatibility
         fields `throughput` and `servedThisWindow` carry counts, never modeled
         load, QPS, tokens, or inference completions.

  FIX 2  policy/evaluate now emits a real Khipu receipt (`receipts.in ≡ receipts.out`).
         The provenance emit helper (app.state.szl_emit_signed_receipt) produces a
         hash-chained DAG node whose digest is non-empty and verifiable. Honesty
         is preserved: `signed` is True only when the cosign key is present.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import serve  # noqa: E402

client = TestClient(serve.app)


# ---------------------------------------------------------------------------
# FIX 1 — /v1/router/stats is explicit about live receipt-backed counters
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/v1/router/stats", "/api/a11oy/v1/router/stats"])
def test_router_stats_is_available_and_honestly_observed(path):
    r = client.get(path)
    assert r.status_code == 200, f"{path} must be available (was {r.status_code})"
    j = r.json()
    assert j["state"] == "LIVE"
    assert j["mode"] == j["data_kind"] == "live"
    assert j["throughput_state"] == "OBSERVED"
    assert j["catalog_state"] == "LIVE"
    assert j["counter_scope"] == "process_lifetime"
    assert j["counter_started_at"] and j["observed_at"]
    assert j["source"] == "szl_llm_registry.router_stats_snapshot"
    assert isinstance(j["routes"], list) and len(j["routes"]) >= 5
    assert "MODELED" not in j["honesty"]


@pytest.mark.parametrize("path", ["/v1/router/stats", "/api/a11oy/v1/router/stats"])
def test_router_stats_matches_viz_contract(path):
    """The /static/viz/router/ scene normalizeStats() reads exactly these keys."""
    j = client.get(path).json()
    assert isinstance(j.get("servedThisWindow"), int)
    served_from_routes = 0
    for route in j["routes"]:
        for key in (
            "organ", "tier", "model", "throughput", "routing_decisions",
            "throughput_unit", "license",
        ):
            assert key in route, f"route missing {key} (scene depends on it)"
        assert isinstance(route["throughput"], int) and route["throughput"] >= 0
        assert route["routing_decisions"] == route["throughput"]
        assert route["throughput_unit"] == "routing_decisions_since_process_start"
        assert route["license"] in ("GREEN", "AMBER", "RED")
        assert route["tier"].startswith("T")
        served_from_routes += route["throughput"]
    # The legacy field is the honest sum of per-route routing decisions.
    assert j["servedThisWindow"] == served_from_routes
    assert j["routingDecisionsSinceStart"] == served_from_routes


def test_router_stats_derives_from_runtime_router_catalog():
    """Every runtime registry model is present; no fake catalog rows are added."""
    registry = serve._llm_reg
    real_ids = {model["model_id"] for model in registry.MODEL_REGISTRY}
    j = client.get("/v1/router/stats").json()
    assert j["catalog_source"] == "szl_llm_registry.MODEL_REGISTRY"
    assert j["catalog_state"] == "LIVE"
    served_models = {route["model"] for route in j["routes"]}
    assert served_models == real_ids
    assert all(route["catalog_member"] is True for route in j["routes"])


def test_router_stats_covers_every_runtime_tier():
    registry = serve._llm_reg
    j = client.get("/v1/router/stats").json()
    assert len(j["routes"]) == len(registry.MODEL_REGISTRY)
    tiers = {route["tier"] for route in j["routes"]}
    expected = {f"T{model['tier']}" for model in registry.MODEL_REGISTRY}
    assert tiers == expected


def test_router_stats_increments_only_with_trusted_receipt_write(monkeypatch):
    registry = serve._llm_reg
    monkeypatch.setattr(registry, "_FORUM_LOG", [])
    monkeypatch.setattr(registry, "_ROUTER_DECISIONS_BY_ROUTE", {})
    monkeypatch.setattr(registry, "_ROUTER_COUNTER_STARTED_AT", "2026-08-26T12:00:00Z")

    receipt = {
        "schema": "szl.llm_route.lambda_receipt/v1",
        "tier_selected": 2,
        "model_id": "gpt_5_4",
        "ts": "2026-08-26T12:00:01Z",
    }
    registry._forum_append(receipt)  # untrusted forum-shaped data: not counted
    assert client.get("/v1/router/stats").json()["servedThisWindow"] == 0

    registry._forum_append(receipt, routing_decision=True)
    j = client.get("/v1/router/stats").json()
    target = next(route for route in j["routes"] if route["model"] == "gpt_5_4")
    assert target["routing_decisions"] == 1
    assert j["servedThisWindow"] == 1


def test_public_forum_ingest_cannot_inflate_router_counter(monkeypatch):
    registry = serve._llm_reg
    monkeypatch.setattr(registry, "_FORUM_LOG", [])
    monkeypatch.setattr(registry, "_ROUTER_DECISIONS_BY_ROUTE", {})
    monkeypatch.setattr(registry, "_ROUTER_COUNTER_STARTED_AT", "2026-08-26T12:00:00Z")

    response = client.post(
        "/api/a11oy/v1/llm/forum/ingest",
        json={
            "source": "operator",
            "receipt": {
                "schema": "szl.llm_route.lambda_receipt/v1",
                "tier_selected": 2,
                "model_id": "gpt_5_4",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["ingested"] is True
    stats = client.get("/v1/router/stats").json()
    assert stats["state"] == "LIVE"
    assert stats["servedThisWindow"] == 0


def test_harness_explicit_model_is_counted_under_its_catalog_tier(monkeypatch):
    registry = serve._llm_reg
    monkeypatch.setattr(registry, "_FORUM_LOG", [])
    monkeypatch.setattr(registry, "_ROUTER_DECISIONS_BY_ROUTE", {})
    monkeypatch.setattr(registry, "_ROUTER_COUNTER_STARTED_AT", "2026-08-26T12:00:00Z")

    routed = client.post(
        "/api/a11oy/v1/llm/route",
        json={
            "harness_profile_id": "szl-honest-operator",
            "model_id": "gpt_5_4",
            # The default high axis scores recommend T0; the explicit model is T2.
            "prompt": "attribute this explicit route",
        },
    )
    assert routed.status_code == 200
    receipt = routed.json()["lambda_receipt"]
    assert receipt["model_id"] == "gpt_5_4"
    assert receipt["tier_selected"] == 2
    assert "GPT-5.4 (tier 2)" in routed.json()["response"]

    stats = client.get("/v1/router/stats").json()
    assert stats["state"] == "LIVE"
    assert stats["catalog_state"] == "LIVE"
    target = next(route for route in stats["routes"] if route["model"] == "gpt_5_4")
    assert target["tier"] == "T2"
    assert target["routing_decisions"] == 1
    assert stats["servedThisWindow"] == 1


def test_plain_llm_route_increments_the_trusted_counter(monkeypatch):
    registry = serve._llm_reg
    monkeypatch.setattr(registry, "_FORUM_LOG", [])
    monkeypatch.setattr(registry, "_ROUTER_DECISIONS_BY_ROUTE", {})
    monkeypatch.setattr(registry, "_ROUTER_COUNTER_STARTED_AT", "2026-08-26T12:00:00Z")
    monkeypatch.setattr(
        registry,
        "sovereign_mesh_generate",
        lambda prompt: {
            "live": False,
            "text": "",
            "matrix": {
                "any_reachable": False,
                "node_count": 0,
                "reachable_count": 0,
                "note": "isolated test mesh",
            },
        },
    )

    routed = client.post(
        "/api/a11oy/v1/llm/route",
        json={"prompt": "count this route", "prefer_local": False},
    )
    assert routed.status_code == 200
    receipt = routed.json()["lambda_receipt"]

    stats = client.get("/v1/router/stats").json()
    target = next(
        route for route in stats["routes"] if route["model"] == receipt["model_id"]
    )
    assert target["tier"] == f"T{receipt['tier_selected']}"
    assert target["routing_decisions"] == 1
    assert stats["servedThisWindow"] == 1


def test_router_stats_counter_failure_is_unavailable_not_modeled(monkeypatch):
    monkeypatch.setattr(serve, "_llm_reg_info", None)

    j = client.get("/v1/router/stats").json()

    assert j["state"] == j["throughput_state"] == "UNAVAILABLE"
    assert j["mode"] == j["data_kind"] == "unavailable"
    assert j["routes"] == []
    assert j["servedThisWindow"] is None
    assert "synthetic replacement was fabricated" in j["honesty"]


def test_router_stats_catalog_drift_is_degraded_not_live(monkeypatch):
    registry = serve._llm_reg
    monkeypatch.setattr(
        registry,
        "router_stats_snapshot",
        lambda: {
            "state": "LIVE",
            "counter_state": "OBSERVED",
            "counter_scope": "process_lifetime",
            "counter_started_at": "2026-08-26T12:00:00Z",
            "observed_at": "2026-08-26T12:00:01Z",
            "routing_decisions_total": 1,
            "routes": [
                {"tier": 9, "model_id": "removed-model", "routing_decisions": 1}
            ],
        },
    )

    j = client.get("/v1/router/stats").json()

    assert j["state"] == "DEGRADED"
    assert j["mode"] == "degraded"
    assert j["catalog_state"] == "DRIFT"
    drifted = next(route for route in j["routes"] if route["model"] == "removed-model")
    assert drifted["catalog_member"] is False
    assert j["servedThisWindow"] == 1


# ---------------------------------------------------------------------------
# FIX 2 — receipts.in ≡ receipts.out: a decision leaves a real Khipu receipt
# ---------------------------------------------------------------------------

def test_emit_helper_is_wired_on_app_state():
    emit = getattr(serve.app.state, "szl_emit_signed_receipt", None)
    assert callable(emit), "provenance emit helper must be wired onto app.state"


def test_policy_decision_emits_hashchained_receipt():
    """Emitting a decision receipt yields a non-empty digest and grows the DAG."""
    emit = serve.app.state.szl_emit_signed_receipt
    dag = serve.app.state.szl_khipu_dag

    before = len(dag.nodes)
    node = emit({
        "schema": "szl.a11oy.policy_decision/v1",
        "op": "policy/evaluate",
        "action_id": "functest-decision-1",
        "severity": "critical",
        "decision": "deny",
    }, None)
    after = len(dag.nodes)

    assert after == before + 1, "decision must append exactly one DAG node"
    assert node["digest"] and len(node["digest"]) == 64, "digest must be a SHA-256 hex"
    # Honesty: signed only when a cosign key is present; never faked.
    assert isinstance(node["signed"], bool)
    if not node["signed"]:
        assert node.get("keyid") in (None, "", "szlholdings-cosign")


def test_decision_receipt_is_chain_verifiable():
    """The emitted receipt is a real DSSE envelope the verifier accepts/rejects honestly."""
    import szl_dsse

    emit = serve.app.state.szl_emit_signed_receipt
    node = emit({"schema": "szl.a11oy.policy_decision/v1", "decision": "allow"}, None)
    verdict = szl_dsse.verify_envelope(node["dsse"])
    # Verdict must be honest: verified iff truly signed (no fake green).
    assert verdict["verified"] == bool(node["signed"])
    if not node["signed"]:
        assert "unsigned" in verdict.get("reason", "").lower()
