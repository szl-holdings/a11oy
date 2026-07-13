# SPDX-License-Identifier: Apache-2.0
"""Assembled-app wiring checks for the SZL Quantum Utility Gate."""

from pathlib import Path

from starlette.testclient import TestClient

import serve


ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(serve.app)

ROUTES = {
    "/api/a11oy/v1/quantum-utility/info",
    "/api/a11oy/v1/quantum-utility/qubo/baseline",
    "/api/a11oy/v1/quantum-utility/hamiltonian/shot-plan",
    "/api/a11oy/v1/quantum-utility/counterfactual/score",
    "/api/a11oy/v1/quantum-utility/claim/rupture-gate",
    "/api/a11oy/v1/quantum-utility/receipt/replay",
}


def _qubo():
    return {
        "problem": {
            "kind": "QUBO",
            "problem_id": "route-fixture",
            "variables": ["x", "y"],
            "offset": 0,
            "linear": {"x": -1, "y": -1},
            "quadratic": [{"left": "x", "right": "y", "coefficient": 2}],
        },
        "max_runtime_ms": 1_000,
    }


def test_all_quantum_utility_routes_are_in_the_real_assembled_app():
    assembled = {getattr(route, "path", None) for route in serve.app.router.routes}
    assert ROUTES <= assembled


def test_info_is_explicitly_proposal_only_and_no_qpu():
    response = CLIENT.get("/api/a11oy/v1/quantum-utility/info")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["label"] == "STRUCTURAL-ONLY"
    assert body["mode"] == "PROPOSAL_ONLY"
    assert body["effectors"] == body["provider_calls"] == body["qpu_calls"] == 0
    assert body["finance_quant_engine_imported"] is False
    assert body["existing_simulator_boundary"]["sim_kind"] == "SIMULATED"


def test_baseline_route_and_receipt_replay_round_trip():
    baseline = CLIENT.post("/api/a11oy/v1/quantum-utility/qubo/baseline", json=_qubo())
    assert baseline.status_code == 200
    payload = baseline.json()
    assert payload["result"]["objective"] == -1
    assert payload["result"]["quantum_hardware_used"] is False
    replay = CLIENT.post("/api/a11oy/v1/quantum-utility/receipt/replay", json=payload["receipt"])
    assert replay.status_code == 200
    assert replay.json()["valid"] is True


def test_route_contract_rejects_hidden_fields_and_oversize_bodies():
    hidden = _qubo()
    hidden["problem"]["provider"] = "must-not-run"
    response = CLIENT.post("/api/a11oy/v1/quantum-utility/qubo/baseline", json=hidden)
    assert response.status_code == 422
    assert response.json()["effectors"] == 0

    oversized = CLIENT.post(
        "/api/a11oy/v1/quantum-utility/qubo/baseline",
        content=b'{"padding":"' + (b"x" * (256 * 1024)) + b'"}',
        headers={"content-type": "application/json"},
    )
    assert oversized.status_code == 413
    assert "256 KiB" in oversized.json()["error"]


def test_quantum_utility_is_pinned_local_against_proxy_fallback():
    assert "v1/quantum-utility/" in serve._LOCAL_ONLY_A11OY_PREFIXES


def test_docker_image_explicitly_copies_the_gate_module():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY szl_quantum_utility.py ./" in dockerfile
