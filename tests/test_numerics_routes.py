# SPDX-License-Identifier: Apache-2.0
"""Assembled FastAPI and Docker wiring guards for numerical adapters."""

from pathlib import Path

from starlette.testclient import TestClient

import serve
import szl_numerics_adapter as adapter


ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(serve.app)
ROUTES = {
    "/api/a11oy/v1/numerics/status",
    "/api/a11oy/v1/numerics/run/{engine}",
    "/api/a11oy/v1/numerics/compare",
}


def payload():
    return {
        "schema": adapter.REQUEST_SCHEMA,
        "request_id": "route-fixture",
        "operation": "MATRIX_SOLVE",
        "inputs": {"matrix": [[2, 0], [0, 4]], "rhs": [2, 8]},
        "tolerance": {"absolute": 1e-9, "relative": 1e-9},
    }


def test_routes_are_real_and_precede_both_catchalls():
    ordered = [getattr(route, "path", None) for route in serve.app.router.routes]
    assert ROUTES <= set(ordered)
    proxy = ordered.index("/api/a11oy/{path:path}")
    spa = ordered.index("/{full_path:path}")
    assert all(ordered.index(path) < proxy and ordered.index(path) < spa for path in ROUTES)


def test_status_is_renderable_when_every_engine_is_unavailable():
    response = CLIENT.get("/api/a11oy/v1/numerics/status")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "EXTERNAL_ENGINES_ONLY"
    assert body["substrate_evidence"] == "UNKNOWN"
    assert body["proof_uplift"] == body["trust_uplift"] == 0


def test_run_is_honestly_unavailable_or_a_bounded_result_never_a_proof():
    response = CLIENT.post("/api/a11oy/v1/numerics/run/octave", json=payload())
    assert response.status_code in (200, 503)
    body = response.json()
    assert body["state"] in ("RESULT", "UNAVAILABLE")
    assert body["substrate_evidence"] == "UNKNOWN"
    assert body["proof_uplift"] == body["trust_uplift"] == 0
    assert body["receipt"]["signature_state"] == "UNSIGNED_DETERMINISTIC_DIGEST_ONLY"


def test_route_rejects_arbitrary_code_and_oversize_bodies():
    hidden = payload()
    hidden["code"] = "disp('must never run')"
    rejected = CLIENT.post("/api/a11oy/v1/numerics/run/octave", json=hidden)
    assert rejected.status_code == 422
    assert rejected.json()["state"] == "REJECTED"
    assert rejected.json()["proof_uplift"] == rejected.json()["trust_uplift"] == 0

    oversized = CLIENT.post(
        "/api/a11oy/v1/numerics/compare",
        content=b'{"padding":"' + b"x" * (128 * 1024) + b'"}',
        headers={"content-type": "application/json"},
    )
    assert oversized.status_code == 422
    assert "128 KiB" in oversized.json()["error"]


def test_docker_copies_only_host_contract_and_fixed_script_not_engines():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY szl_numerics_adapter.py ./" in dockerfile
    assert "COPY numerics/ ./numerics/" in dockerfile
    assert "apt-get install" not in "\n".join(
        line for line in dockerfile.splitlines() if "octave" in line.lower() or "matlab" in line.lower()
    )
    assert "pip install matlab" not in dockerfile.lower()
