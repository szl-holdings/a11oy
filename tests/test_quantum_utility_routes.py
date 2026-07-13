# SPDX-License-Identifier: Apache-2.0
"""Assembled-app wiring checks for the SZL Quantum Utility Gate."""

import json
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


def test_all_quantum_utility_routes_precede_the_node_proxy_catchall():
    ordered = [getattr(route, "path", None) for route in serve.app.router.routes]
    proxy_index = ordered.index("/api/a11oy/{path:path}")
    assert all(ordered.index(path) < proxy_index for path in ROUTES)


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
    assert response.json()["label"] == "STRUCTURAL-ONLY"
    assert response.json()["effectors"] == response.json()["provider_calls"] == response.json()["qpu_calls"] == 0

    oversized = CLIENT.post(
        "/api/a11oy/v1/quantum-utility/qubo/baseline",
        content=b'{"padding":"' + (b"x" * (256 * 1024)) + b'"}',
        headers={"content-type": "application/json"},
    )
    assert oversized.status_code == 413
    assert "256 KiB" in oversized.json()["error"]
    assert oversized.json()["effectors"] == oversized.json()["provider_calls"] == oversized.json()["qpu_calls"] == 0


def test_content_length_over_limit_is_rejected_before_body_parsing():
    response = CLIENT.post(
        "/api/a11oy/v1/quantum-utility/qubo/baseline",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": str(256 * 1024 + 1)},
    )
    assert response.status_code == 413
    assert response.json()["label"] == "STRUCTURAL-ONLY"
    assert response.json()["effectors"] == response.json()["provider_calls"] == response.json()["qpu_calls"] == 0


def test_chunked_body_without_content_length_aborts_at_stream_limit():
    def chunks():
        yield b'{"padding":"'
        for _ in range(257):
            yield b"x" * 1024
        yield b'"}'

    response = CLIENT.post(
        "/api/a11oy/v1/quantum-utility/qubo/baseline",
        content=chunks(),
        headers={"content-type": "application/json", "transfer-encoding": "chunked"},
    )
    assert response.status_code == 413
    assert "256 KiB" in response.json()["error"]
    assert response.json()["effectors"] == response.json()["provider_calls"] == response.json()["qpu_calls"] == 0


def test_quantum_utility_is_pinned_local_against_proxy_fallback():
    assert "v1/quantum-utility/" in serve._LOCAL_ONLY_A11OY_PREFIXES


def test_unavailable_and_replay_error_envelopes_keep_the_zero_effector_boundary():
    unavailable = serve._quantum_utility_unavailable()
    unavailable_body = json.loads(unavailable.body)
    assert unavailable.status_code == 503
    assert unavailable_body["label"] == unavailable_body["mode"] == "UNAVAILABLE"
    assert unavailable_body["effectors"] == unavailable_body["provider_calls"] == unavailable_body["qpu_calls"] == 0

    replay_error = CLIENT.post("/api/a11oy/v1/quantum-utility/receipt/replay", json={})
    replay_body = replay_error.json()
    assert replay_error.status_code == 422
    assert replay_body["label"] == "STRUCTURAL-ONLY"
    assert replay_body["effectors"] == replay_body["provider_calls"] == replay_body["qpu_calls"] == 0


def test_docker_image_explicitly_copies_the_gate_module():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY szl_quantum_utility.py ./" in dockerfile
