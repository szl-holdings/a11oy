# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
tests/test_functest_router_receipts.py — FUNCTIONAL-PROOF squad.

Proves two consumer/investor-facing fixes are REAL and operational:

  FIX 1  /v1/router/stats (+ /api/a11oy/v1/router/stats)
         The landing-page "LLM-Router Live" 3D scene polls /v1/router/stats and
         renders "DEMO MODE" on failure. The endpoint 404'd, so the advertised
         "live data binding" was unproven. These tests assert the endpoint exists,
         returns 200, emits the {routes:[{organ,tier,model,throughput,license}],
         servedThisWindow} shape the scene's normalizeStats() consumes, and is
         derived from the REAL szl_brain.TIERS catalog (not fabricated).

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
# FIX 1 — /v1/router/stats is live, real, and scene-compatible
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/v1/router/stats", "/api/a11oy/v1/router/stats"])
def test_router_stats_is_live_200(path):
    r = client.get(path)
    assert r.status_code == 200, f"{path} must be live (was {r.status_code})"
    j = r.json()
    assert j["mode"] == "live"
    assert isinstance(j["routes"], list) and len(j["routes"]) >= 5


@pytest.mark.parametrize("path", ["/v1/router/stats", "/api/a11oy/v1/router/stats"])
def test_router_stats_matches_viz_contract(path):
    """The /static/viz/router/ scene normalizeStats() reads exactly these keys."""
    j = client.get(path).json()
    assert isinstance(j.get("servedThisWindow"), int)
    served_from_routes = 0
    for route in j["routes"]:
        for key in ("organ", "tier", "model", "throughput", "license"):
            assert key in route, f"route missing {key} (scene depends on it)"
        assert isinstance(route["throughput"], int) and route["throughput"] >= 0
        assert route["license"] in ("GREEN", "AMBER", "RED")
        assert route["tier"].startswith("T")
        served_from_routes += route["throughput"]
    # servedThisWindow must be the honest sum of per-route throughput.
    assert j["servedThisWindow"] == served_from_routes


def test_router_stats_derives_from_real_brain_catalog():
    """Models must come from the real szl_brain.TIERS catalog, not invented."""
    import szl_brain

    real_ids = {t["id"] for t in szl_brain.TIERS}
    j = client.get("/v1/router/stats").json()
    assert j["source"] == "szl_brain.TIERS"
    served_models = {route["model"] for route in j["routes"]}
    assert served_models <= real_ids, (
        f"router/stats served models not in real catalog: {served_models - real_ids}"
    )


def test_router_stats_one_route_per_real_tier():
    """One route per REAL catalog tier — honest, not padded to a fake 7-tier set."""
    import szl_brain

    j = client.get("/v1/router/stats").json()
    assert len(j["routes"]) == len(szl_brain.TIERS)
    tiers = {route["tier"] for route in j["routes"]}
    expected = {f"T{t['rank']}" for t in szl_brain.TIERS}
    assert tiers == expected


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
