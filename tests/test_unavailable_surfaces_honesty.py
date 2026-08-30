#!/usr/bin/env python3
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# test_unavailable_surfaces_honesty.py — Doctrine v11 guard for the two surfaces
# that render as UNAVAILABLE in the live estate: `sovereign` and `brainreranker`.
#
# What these tests pin down
# ------------------------
# 1. sovereign — an ENVIRONMENT gap, not a code bug. With SZL_LOCAL_LLM_URL unset
#    the panel MUST read UNAVAILABLE, must name the reason machine-readably, and
#    must NOT invent a doctrine self-test answer. With the env set AND a node that
#    answers THIS request (mocked at the registry-probe boundary — never a network
#    call from CI) the panel MUST go LIVE-SOVEREIGN with the node's real answer.
#    Both directions matter: no fabricated live, and no stuck-UNAVAILABLE either.
#
# 2. brainreranker — the surface label must reflect what is actually served this
#    request. The evidence inventory IS read live (graph bytes hashed, one
#    admission/quarantine decision per raw node), while the model/evaluation
#    pipeline is BLOCKED because no trained model manifest exists in-image. The
#    honest tier for that state is MODELED; UNAVAILABLE is reserved for a graph
#    that could not be read at all, and MEASURED for a fully READY pipeline.
#
# Pure stdlib + pytest + TestClient. No network. Λ stays Conjecture 1.

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import szl_brain_reranker as rr  # noqa: E402
import szl_sovereign_panel as sp  # noqa: E402


# ---------------------------------------------------------------------------
# 1. sovereign — honest env gate
# ---------------------------------------------------------------------------

def test_sovereign_reason_codes_are_honest_and_distinct():
    """Unset env and a silent-but-configured node are different honest reasons."""
    assert sp.unavailable_reason(reachable=True, env_present=True) is None
    assert sp.unavailable_reason(reachable=True, env_present=False) is None
    assert sp.unavailable_reason(False, False) == sp.REASON_ENV_UNSET
    assert sp.unavailable_reason(False, True) == sp.REASON_NODE_UNREACHABLE


def test_sovereign_unavailable_when_env_unset(monkeypatch):
    """No SZL_LOCAL_LLM_URL => honest UNAVAILABLE, named reason, zero fabrication."""
    monkeypatch.delenv("SZL_LOCAL_LLM_URL", raising=False)
    monkeypatch.setattr(
        sp, "_probe_reachability",
        lambda: {"reachable": False, "models": [], "base_url": "http://localhost:11434/v1",
                 "env_present": False, "api_style": None, "via": "test probe",
                 "dependency": None, "note": "node not reachable this request",
                 "base_url_source": sp.BASE_FROM_DEFAULT,
                 "unavailable_reason": sp.REASON_ENV_UNSET},
    )
    payload = sp.build_payload()
    assert payload["label"] == sp.UNAVAILABLE
    assert payload["claim"] == sp.UNAVAILABLE
    assert payload["unavailable_reason"] == sp.REASON_ENV_UNSET
    assert "ENVIRONMENT GAP" in payload["unavailable_reason_text"]
    assert payload["sovereign"]["reachable"] is False
    assert payload["sovereign"]["env_present"] is False
    assert payload["sovereign"]["base_url_source"] == sp.BASE_FROM_DEFAULT
    # No fabricated doctrine line, and no fabricated stage observation.
    assert payload["doctrine_selftest"]["label"] == sp.UNAVAILABLE
    assert payload["doctrine_selftest"]["answer"] is None
    assert payload["stage"]["active_stage"] == "UNKNOWN"
    # Λ stays a conjecture; trust never 1.0.
    assert payload["doctrine"]["lambda"] == "Conjecture 1"
    assert payload["doctrine"]["trust_ceiling"] < 1.0


def test_sovereign_live_when_env_set_and_node_answers(monkeypatch):
    """Env set + a node that answers THIS request => LIVE-SOVEREIGN with a REAL answer.

    The mock sits at the registry-probe boundary, so the panel's own gating logic
    (reachable -> self-test -> stage -> receipt) is the thing under test. No network.
    """
    monkeypatch.setenv("SZL_LOCAL_LLM_URL", "http://tower.local:11434/v1")
    fake = type(sys)("szl_llm_registry")
    fake.sovereign_probe = lambda: {
        "live": True, "models": ["llama3-szl-finetuned-q4"],
        "base_url": "http://tower.local:11434/v1", "env_present": True,
        "api_style": "ollama /api", "note": "node live (mock node answered this request)",
    }
    fake.sovereign_generate = lambda prompt: {
        "live": True, "text": "Honest labels, no fabricated measurement.",
        "model": "llama3-szl-finetuned-q4", "api_style": "ollama /api",
    }
    monkeypatch.setitem(sys.modules, "szl_llm_registry", fake)

    payload = sp.build_payload()
    assert payload["label"] == sp.LIVE_SOVEREIGN
    assert payload["unavailable_reason"] is None
    assert payload["unavailable_reason_text"] is None
    sov = payload["sovereign"]
    assert sov["reachable"] is True
    assert sov["env_present"] is True
    assert sov["base_url_source"] == sp.BASE_FROM_ENV
    assert sov["models_live"] == ["llama3-szl-finetuned-q4"]
    st = payload["doctrine_selftest"]
    assert st["label"] == sp.LIVE_SOVEREIGN
    assert st["answer"] == "Honest labels, no fabricated measurement."
    assert st["live"] is True
    assert payload["stage"]["active_stage"] == "STAGE_B_TAG_PRESENT"
    # A live node still does not upgrade the doctrine posture.
    assert payload["doctrine"]["adds_to_locked_8"] == 0
    assert payload["doctrine"]["lambda"] == "Conjecture 1"


def test_sovereign_route_serves_honest_label_via_testclient(monkeypatch):
    """The served route agrees with the panel: UNAVAILABLE + a named reason off-Tower."""
    pytest.importorskip("starlette.testclient")
    from fastapi.testclient import TestClient
    monkeypatch.delenv("SZL_LOCAL_LLM_URL", raising=False)
    serve = importlib.import_module("serve")
    with TestClient(serve.app) as client:
        r = client.get("/api/a11oy/v1/frontier/sovereign",
                       headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0)"})
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == sp.UNAVAILABLE
    assert body["unavailable_reason"] in (sp.REASON_ENV_UNSET, sp.REASON_NODE_UNREACHABLE)
    assert body["doctrine_selftest"]["answer"] is None
    assert body["sovereign"]["reachable"] is False


# ---------------------------------------------------------------------------
# 2. brainreranker — honest label ladder
# ---------------------------------------------------------------------------

def test_brainreranker_modeled_when_inventory_live_and_pipeline_blocked():
    """Live inventory + BLOCKED model pipeline => MODELED, never UNAVAILABLE."""
    status = rr.service_status("a11oy")
    assert status["inventory_label"] == rr.MEASURED
    assert status["inventory"]["raw_node_count"] > 0
    assert status["inventory"]["decision_count"] == status["inventory"]["raw_node_count"]
    assert status["status"] == rr.BLOCKED          # pipeline honestly not operational
    assert status["operational"] is False
    assert status["label"] == rr.MODELED           # but the surface serves real state
    assert status["blocking_reasons"]
    assert "NO model-performance" in status["label_basis"]


def test_brainreranker_unavailable_only_when_graph_unreadable(monkeypatch):
    """If the Brain graph cannot be read, the surface stays honestly UNAVAILABLE."""
    monkeypatch.setattr(rr, "_graph_nodes", lambda ns="a11oy": ([], "GRAPH_NODES_UNAVAILABLE"))
    with rr._LOCK:
        rr._INVENTORY_CACHE.update({"key": None, "value": None})
    try:
        status = rr.service_status("a11oy")
        assert status["inventory_label"] == rr.UNAVAILABLE
        assert status["label"] == rr.UNAVAILABLE
        assert status["status"] == rr.BLOCKED
        assert "could not be read" in status["label_basis"]
    finally:
        with rr._LOCK:
            rr._INVENTORY_CACHE.update({"key": None, "value": None})


def test_brainreranker_measured_only_when_whole_pipeline_ready(monkeypatch):
    """MEASURED is reachable ONLY when dataset+model+evaluation are all READY."""
    ready = {"status": rr.READY, "reasons": [], "receipt_sha256": "0" * 64}
    monkeypatch.setattr(rr, "build_dataset", lambda *a, **k: {
        "rows": [], "dataset_sha256": "a" * 64,
        "dataset_readiness": ready, "model_readiness": ready,
        "evaluation_readiness": ready,
        "split_counts": {"train": 1, "eval": 1, "test": 1},
        "example_type_counts": {name: 1 for name in rr.EXAMPLE_TYPES},
    })
    status = rr.service_status("a11oy")
    assert status["operational"] is True
    assert status["status"] == rr.READY
    assert status["label"] == rr.MEASURED
    assert status["blocking_reasons"] == []


def test_brainreranker_routes_registered_before_spa_catchall():
    """Root-cause guard: the handler stays imported/registered ahead of the SPA."""
    pytest.importorskip("starlette.testclient")
    serve = importlib.import_module("serve")
    route_paths = [getattr(route, "path", "") for route in serve.app.router.routes]
    catchalls = [i for i, path in enumerate(route_paths)
                 if path in {"/{full_path:path}", "/api/a11oy/{path:path}"}]
    for path in ("/api/a11oy/v1/brainreranker/status",
                 "/api/a11oy/v1/brain/reranker/status",
                 "/api/a11oy/v1/brain/reranker/inventory"):
        assert path in route_paths
        if catchalls:
            assert route_paths.index(path) < min(catchalls)


def test_brainreranker_dockerfile_copies_the_handler_module():
    """A dropped COPY is the other way this surface dies; pin it."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "szl_brain_reranker.py" in dockerfile
    serve_src = (ROOT / "serve.py").read_text(encoding="utf-8")
    assert "import szl_brain_reranker" in serve_src
    assert "_szl_brain_reranker.register(app" in serve_src
