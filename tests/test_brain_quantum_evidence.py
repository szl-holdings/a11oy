# SPDX-License-Identifier: Apache-2.0
# Signed-off-by: Codex <codex@openai.com>

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("starlette.testclient")

from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_brain_quantum_evidence as quantum


def test_manifest_never_promotes_simulation_or_paper_to_hardware():
    manifest = quantum.build_manifest()
    by_id = {row["id"]: row for row in manifest["sources"]}

    assert manifest["overall_status"] == "PARTIALLY OPERATIONAL"
    assert manifest["summary"]["hardware_measurements"] == 0
    assert manifest["summary"]["qpu_execution_verified"] is False
    assert manifest["summary"]["quantum_advantage_verified"] is False
    assert manifest["summary"]["full_operational_brain"] is False
    assert by_id["governed-vqc"]["capability_kind"] == "simulation"
    assert by_id["governed-vqc"]["hardware_used"] is False
    assert by_id["watts-mead-transactional-energy-paper"]["evidence"]["adopted_as_physics"] is False


def test_every_source_is_typed_statused_and_digest_bound():
    manifest = quantum.build_manifest()
    for row in manifest["sources"]:
        assert row["capability_kind"] in manifest["allowed_capability_kinds"]
        assert row["status"] in manifest["allowed_statuses"]
        assert len(row["source_digest"]) == 64


def test_source_failure_closes_to_unavailable():
    def broken():
        raise RuntimeError("injected")

    row = quantum._safe_source("broken-source", broken)
    assert row["status"] == "UNAVAILABLE"
    assert row["hardware_used"] is False


def test_routes_return_evidence_manifest():
    app = FastAPI()
    assert quantum.register(app) == "brain-quantum-evidence-wired:1"
    with TestClient(app) as client:
        info = client.get("/api/a11oy/v1/brain/quantum-evidence/info")
        manifest = client.get("/api/a11oy/v1/brain/quantum-evidence")
    assert info.status_code == 200
    assert info.json()["executes_qpu"] is False
    assert manifest.status_code == 200
    assert manifest.json()["schema"] == quantum.SCHEMA
