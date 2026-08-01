#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Contract and route tests for the plan-only governed graph analyzer."""

import copy
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routers import governed_graph_operations as graph_ops


def _node(contract: dict, node_id: str) -> dict:
    return next(node for node in contract["nodes"] if node["id"] == node_id)


def _codes(result: dict, issue_type: str) -> set[str]:
    return {issue["code"] for issue in result["gates"][issue_type]}


def _client_with_page(tmp_path: Path, monkeypatch) -> tuple[TestClient, FastAPI, dict]:
    module_path = tmp_path / "routers" / "governed_graph_operations.py"
    page_path = tmp_path / "pages" / "graph-operations.html"
    module_path.parent.mkdir(parents=True)
    page_path.parent.mkdir(parents=True)
    page_path.write_text("<!doctype html><title>Governed Graph Operations</title>", encoding="utf-8")
    monkeypatch.setattr(graph_ops, "__file__", str(module_path))

    app = FastAPI()
    wired = graph_ops.register(app, ns="a11oy")

    @app.get("/api/a11oy/{path:path}")
    async def node_proxy(path: str):
        return HTMLResponse(f"proxy:{path}")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        return HTMLResponse(f"spa:{full_path}")

    return TestClient(app), app, wired


@pytest.mark.parametrize(
    ("sample_id", "expected_graph_id", "expected_iterations"),
    (
        ("protected-release", "protected-release", 0),
        ("research-diamond", "research-diamond", 0),
        ("bounded-repair", "bounded-repair", 3),
    ),
)
def test_valid_samples_are_ready_plan_only_contracts(
    sample_id: str, expected_graph_id: str, expected_iterations: int
) -> None:
    result = graph_ops.analyse_graph(graph_ops.sample_contract(sample_id))

    assert result["ok"] is True
    assert result["graph_id"] == expected_graph_id
    assert result["decision"] == "READY_TO_ORCHESTRATE"
    assert result["gates"]["pass"] is True
    assert result["gates"]["blocker_count"] == 0
    assert result["execution"] == {
        "mode": "PLAN_ONLY",
        "authorized": False,
        "effectors": 0,
        "provider_calls": 0,
        "writes": 0,
        "note": result["execution"]["note"],
    }
    assert result["contracts"]["bounded_loop_iterations"] == expected_iterations
    assert len(result["contract_digest"]) == 64
    assert result["plan_id"] == f"ggp-{result['contract_digest'][:20]}"


def test_digest_and_analysis_are_deterministic_for_equivalent_mapping_order() -> None:
    contract = graph_ops.sample_contract("research-diamond")
    reordered = {key: copy.deepcopy(contract[key]) for key in reversed(contract)}
    reordered["budget"] = {
        key: reordered["budget"][key] for key in reversed(reordered["budget"])
    }

    first = graph_ops.analyse_graph(contract)
    second = graph_ops.analyse_graph(copy.deepcopy(contract))
    mapping_reordered = graph_ops.analyse_graph(reordered)

    assert first == second == mapping_reordered
    assert first["contract_digest"] == graph_ops._sha256(first["normalized_contract"])


def test_fake_data_edge_is_reported_without_inventing_an_artifact() -> None:
    contract = graph_ops.sample_contract("research-diamond")
    papers = _node(contract, "papers")
    papers["consumes"] = ["research.question"]

    result = graph_ops.analyse_graph(contract)

    assert result["contracts"]["fake_edges"] == [
        {
            "source": "scope",
            "target": "papers",
            "reason": "consumer declares no use of predecessor output",
        }
    ]
    assert "FAKE_DATA_EDGE" in _codes(result, "advisories")
    assert result["gates"]["pass"] is True


def test_missing_reducer_fan_in_is_a_blocker() -> None:
    contract = graph_ops.sample_contract("research-diamond")
    reduce_node = _node(contract, "reduce")
    reduce_node["consumes"].remove("finding.operators")

    result = graph_ops.analyse_graph(contract)

    assert result["contracts"]["fan_in"] == [
        {
            "node": "reduce",
            "expected": 3,
            "contractually_received": 2,
            "complete": False,
        }
    ]
    assert "FAN_IN_INCOMPLETE" in _codes(result, "blockers")
    assert result["decision"] == "REVISE"


def test_parallel_hidden_resource_conflict_is_a_blocker() -> None:
    contract = graph_ops.sample_contract("research-diamond")
    _node(contract, "papers")["resources"] = ["exclusive:source-index"]
    _node(contract, "repos")["resources"] = ["exclusive:source-index"]

    result = graph_ops.analyse_graph(contract)

    assert result["contracts"]["hidden_resource_edges"] == [
        {
            "nodes": ["papers", "repos"],
            "layer": 1,
            "writes": [],
            "resources": ["exclusive:source-index"],
        }
    ]
    assert "HIDDEN_RESOURCE_EDGE" in _codes(result, "blockers")


def test_top_level_cycle_is_rejected_instead_of_scheduled() -> None:
    contract = graph_ops.sample_contract("research-diamond")
    scope = _node(contract, "scope")
    scope["depends_on"] = ["synthesize"]

    with pytest.raises(graph_ops.GraphContractError, match="top-level graph contains a cycle"):
        graph_ops.analyse_graph(contract)


def test_loop_requires_a_finite_cap_and_exit_condition() -> None:
    contract = graph_ops.sample_contract("bounded-repair")
    repair = _node(contract, "repair")
    repair["max_iterations"] = None
    repair["exit_conditions"] = []

    result = graph_ops.analyse_graph(contract)

    assert "UNBOUNDED_LOOP" in _codes(result, "blockers")
    assert result["contracts"]["bounded_loop_iterations"] == 0
    assert result["decision"] == "REVISE"


def test_verifier_requires_fresh_context() -> None:
    contract = graph_ops.sample_contract("research-diamond")
    _node(contract, "verify")["fresh_context"] = False

    result = graph_ops.analyse_graph(contract)

    assert "VERIFIER_CONTEXT_NOT_FRESH" in _codes(result, "blockers")
    assert result["decision"] == "REVISE"


def test_verifier_must_consume_an_artifact_from_every_named_target() -> None:
    contract = graph_ops.sample_contract("research-diamond")
    verifier = _node(contract, "verify")
    verifier["consumes"] = []

    result = graph_ops.analyse_graph(contract)

    assert "VERIFIER_ARTIFACT_NOT_BOUND" in _codes(result, "blockers")
    assert "FAKE_DATA_EDGE" in _codes(result, "advisories")
    assert result["decision"] == "REVISE"


def test_optional_anchor_does_not_satisfy_terminal_coverage() -> None:
    contract = graph_ops.sample_contract("research-diamond")
    contract["anchors"][0]["required"] = False
    contract["anchors"].append(
        {
            "id": "unrelated-required-source",
            "type": "source",
            "nodes": ["verify"],
            "required": True,
            "description": "Required evidence for a non-terminal node.",
        }
    )

    result = graph_ops.analyse_graph(contract)

    assert "TERMINAL_NOT_ANCHORED" in _codes(result, "blockers")
    assert result["contracts"]["anchored_nodes"] == ["verify"]
    assert result["decision"] == "REVISE"


def test_side_effecting_node_requires_write_authority_and_receipt_anchor() -> None:
    contract = graph_ops.sample_contract("protected-release")
    _node(contract, "publish")["authority"] = "READ_ONLY"
    contract["anchors"] = [
        anchor for anchor in contract["anchors"] if anchor["type"] != "receipt"
    ]

    result = graph_ops.analyse_graph(contract)

    assert {
        "WRITE_AUTHORITY_MISSING",
        "WRITE_RECEIPT_ANCHOR_MISSING",
    } <= _codes(result, "blockers")
    assert result["execution"]["authorized"] is False
    assert result["execution"]["writes"] == 0


def test_page_status_sample_and_analyse_routes_are_local_json_or_html(
    tmp_path: Path, monkeypatch
) -> None:
    client, _app, wired = _client_with_page(tmp_path, monkeypatch)

    assert wired["state"] == "REAL"
    assert set(wired["routes"]) == {
        "/graph-operations",
        "/api/a11oy/v1/graph-operations/status",
        "/api/a11oy/v1/graph-operations/sample/{sample_id}",
        "/api/a11oy/v1/graph-operations/analyse",
    }

    page = client.get("/graph-operations")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert page.headers["cache-control"] == "no-store"
    assert "Governed Graph Operations" in page.text

    status = client.get("/api/a11oy/v1/graph-operations/status")
    assert status.status_code == 200
    assert status.headers["content-type"].startswith("application/json")
    assert status.headers["cache-control"] == "no-store"
    assert status.json()["truth_boundary"] == {
        "effectors": 0,
        "writes": 0,
        "provider_calls": 0,
        "receipts_emitted": 0,
        "note": "Real deterministic analyzer; proposed execution remains MODELED.",
    }

    sample = client.get(
        "/api/a11oy/v1/graph-operations/sample/protected-release"
    )
    assert sample.status_code == 200
    assert sample.headers["content-type"].startswith("application/json")
    assert sample.json()["analysis"]["decision"] == "READY_TO_ORCHESTRATE"

    analysed = client.post(
        "/api/a11oy/v1/graph-operations/analyse",
        json=graph_ops.sample_contract("bounded-repair"),
    )
    assert analysed.status_code == 200
    assert analysed.headers["content-type"].startswith("application/json")
    assert analysed.json()["contracts"]["bounded_loop_iterations"] == 3


def test_unknown_sample_and_invalid_analyse_requests_fail_closed(
    tmp_path: Path, monkeypatch
) -> None:
    client, _app, _wired = _client_with_page(tmp_path, monkeypatch)

    unknown = client.get("/api/a11oy/v1/graph-operations/sample/not-real")
    assert unknown.status_code == 404
    assert unknown.json() == {"ok": False, "error": "unknown sample: not-real"}

    malformed = client.post(
        "/api/a11oy/v1/graph-operations/analyse",
        content=b"{not-json",
        headers={"content-type": "application/json"},
    )
    assert malformed.status_code == 400
    assert malformed.json() == {"ok": False, "error": "invalid JSON body"}

    invalid = client.post(
        "/api/a11oy/v1/graph-operations/analyse",
        json={"schema": graph_ops.SCHEMA},
    )
    assert invalid.status_code == 422
    assert invalid.json()["ok"] is False


def test_declared_and_streamed_body_limits_return_413(tmp_path: Path, monkeypatch) -> None:
    client, _app, _wired = _client_with_page(tmp_path, monkeypatch)
    analyse_path = "/api/a11oy/v1/graph-operations/analyse"

    declared = client.post(
        analyse_path,
        content=b"{}",
        headers={
            "content-type": "application/json",
            "content-length": str(graph_ops.MAX_BODY_BYTES + 1),
        },
    )
    assert declared.status_code == 413
    assert declared.json() == {
        "ok": False,
        "error": "request body exceeds the 96 KiB limit",
    }

    def oversized_chunks():
        yield b'{"padding":"'
        for _ in range(97):
            yield b"x" * 1024
        yield b'"}'

    streamed = client.post(
        analyse_path,
        content=oversized_chunks(),
        headers={"content-type": "application/json", "transfer-encoding": "chunked"},
    )
    assert streamed.status_code == 413
    assert streamed.json() == declared.json()


def test_get_routes_are_pure_and_report_no_signing_or_execution(
    tmp_path: Path, monkeypatch
) -> None:
    client, _app, _wired = _client_with_page(tmp_path, monkeypatch)
    contract_before = graph_ops.sample_contract("protected-release")
    status_before = graph_ops.status_payload("a11oy")

    status = client.get("/api/a11oy/v1/graph-operations/status").json()
    sample = client.get(
        "/api/a11oy/v1/graph-operations/sample/protected-release"
    ).json()

    assert graph_ops.sample_contract("protected-release") == contract_before
    assert graph_ops.status_payload("a11oy") == status_before
    assert status["truth_boundary"]["receipts_emitted"] == 0
    assert status["truth_boundary"]["writes"] == 0
    assert sample["analysis"]["execution"]["authorized"] is False
    assert sample["analysis"]["execution"]["effectors"] == 0
    assert sample["analysis"]["execution"]["writes"] == 0


def test_exact_routes_precede_proxy_and_spa_catchalls(tmp_path: Path, monkeypatch) -> None:
    client, app, wired = _client_with_page(tmp_path, monkeypatch)
    ordered = [getattr(route, "path", None) for route in app.router.routes]
    proxy_index = ordered.index("/api/a11oy/{path:path}")
    spa_index = ordered.index("/{full_path:path}")

    for path in wired["routes"]:
        assert ordered.index(path) < proxy_index
        assert ordered.index(path) < spa_index

    api_response = client.get("/api/a11oy/v1/graph-operations/status")
    page_response = client.get("/graph-operations")
    assert api_response.headers["content-type"].startswith("application/json")
    assert page_response.headers["content-type"].startswith("text/html")
    assert not api_response.text.startswith("proxy:")
    assert not page_response.text.startswith("spa:")


def test_missing_page_fails_honestly_instead_of_falling_through_to_spa(
    tmp_path: Path, monkeypatch
) -> None:
    module_path = tmp_path / "routers" / "governed_graph_operations.py"
    module_path.parent.mkdir(parents=True)
    monkeypatch.setattr(graph_ops, "__file__", str(module_path))
    app = FastAPI()
    graph_ops.register(app)

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        return HTMLResponse(f"spa:{full_path}")

    response = TestClient(app).get("/graph-operations")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["state"] == "UNAVAILABLE"


def test_contract_body_hard_cap_is_smaller_than_the_transport_limit() -> None:
    contract = graph_ops.sample_contract("research-diamond")
    contract["nodes"] = contract["nodes"] * 10

    with pytest.raises(graph_ops.GraphContractError, match="hard cap"):
        graph_ops.analyse_graph(contract)

    serialized = json.dumps(graph_ops.sample_contract()).encode("utf-8")
    assert len(serialized) < graph_ops.MAX_BODY_BYTES
