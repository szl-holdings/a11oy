"""Brain-capabilities honesty contract.

The route is a manifest for UI and ecosystem wiring. It must stay honest about
what is operational, partial, modeled, simulated, or unavailable.

Signed-off-by: Codex <codex@openai.com>
"""

import json
import pathlib

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("starlette.testclient")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import szl_brain_capabilities as bc  # noqa: E402
import szl_brain_evidence_eval as evidence_eval  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_manifest_uses_only_allowed_statuses():
    manifest = bc.build_manifest("a11oy")
    allowed = set(manifest["allowed_statuses"])

    assert manifest["overall_status"] == "PARTIALLY OPERATIONAL"
    assert manifest["claim_policy"]["no_agi_or_asi_claim"] is True
    assert manifest["summary"]["ready_for_autonomous_claims"] is False
    assert manifest["summary"]["ready_for_training_claims"] is False
    assert manifest["summary"]["capabilities_total"] == len(manifest["capabilities"])
    assert "content_sha256" not in manifest

    for item in manifest["capabilities"]:
        assert item["status"] in allowed
        assert item["evidence"], item["id"]
        assert item["next_step"], item["id"]


def test_training_and_router_are_not_promoted_to_operational():
    manifest = bc.build_manifest("a11oy")
    by_id = {item["id"]: item for item in manifest["capabilities"]}

    assert by_id["training_and_weights"]["status"] == "UNAVAILABLE"
    assert by_id["llm_router"]["status"] == "SIMULATED"
    assert by_id["query_audit_receipts"]["status"] == "SIMULATED"


def test_retrieval_pilot_is_replayable_bounded_and_not_promoted():
    manifest = bc.build_manifest("a11oy")
    retrieval = {item["id"]: item for item in manifest["capabilities"]}[
        "brain_retrieval"
    ]
    pilot = retrieval["evaluation"]
    committed_path = (
        ROOT / "research" / "brain-evidence-admission" / "evidence-manifest.json"
    )
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    results_path = (
        ROOT / "research" / "brain-evidence-admission" / "evaluation-results.json"
    )
    results = json.loads(results_path.read_text(encoding="utf-8"))

    assert evidence_eval.verify_committed(ROOT)["ok"] is True
    assert retrieval["status"] == "PARTIALLY OPERATIONAL"
    assert pilot["status"] == committed["label"] == "MEASURED_LOCAL_PILOT"
    assert pilot["protocol_id"] == committed["protocol_id"]
    assert pilot["claims_boundary"]["external_validity"] == (
        results["claims_boundary"]["external_validity"]
    )
    assert pilot["claims_boundary"]["proof_credit"] == 0
    assert pilot["claims_boundary"]["model_trust_delta"] == 0
    assert pilot["claims_boundary"]["model_promotion_allowed"] is False
    assert pilot["claims_boundary"]["training_triggered"] is False
    assert committed["admission_summary"]["raw_graph_nodes_admitted"] == 0
    assert committed["claims_boundary"]["training_triggered"] is False
    assert set(pilot["artifacts"][:-1]) <= set(committed["artifact_receipts"])
    assert pilot["artifacts"][-1] == (
        "research/brain-evidence-admission/evidence-manifest.json"
    )


def test_routes_register_and_return_manifest():
    app = FastAPI()
    status = bc.register(app, ns="a11oy")
    assert status == "brain-capabilities-wired:3"

    with TestClient(app) as client:
        info = client.get("/api/a11oy/v1/brain/capabilities/info")
        manifest = client.get("/api/a11oy/v1/brain/capabilities")

    assert info.status_code == 200
    assert manifest.status_code == 200
    assert info.json()["pure_read"] is True
    body = manifest.json()
    assert body["schema"] == "szl.brain-capabilities.v1"
    assert "content_sha256" not in body


def test_failed_underlying_registration_degrades_affected_capabilities():
    runtime_status = {
        "estate_brain_graph": False,
        "brain_retrieval": False,
        "brain_memory": False,
        "provenance_lineage": False,
        "query_audit_receipts": False,
    }
    app = FastAPI()
    bc.register(app, ns="a11oy", runtime_status=runtime_status)

    with TestClient(app) as client:
        body = client.get("/api/a11oy/v1/brain/capabilities").json()

    assert body["overall_status"] == "UNAVAILABLE"
    assert body["summary"]["ready_for_showcase"] is False
    by_id = {item["id"]: item for item in body["capabilities"]}
    for capability_id in runtime_status:
        assert by_id[capability_id]["status"] == "UNAVAILABLE"
        assert by_id[capability_id]["runtime_registration"] == "FAILED_OR_ABSENT"


def test_successful_underlying_registration_preserves_declared_maturity():
    manifest = bc.build_manifest(
        "a11oy",
        {"estate_brain_graph": True, "brain_retrieval": True},
    )
    by_id = {item["id"]: item for item in manifest["capabilities"]}

    assert manifest["overall_status"] == "PARTIALLY OPERATIONAL"
    assert by_id["estate_brain_graph"]["status"] == "PARTIALLY OPERATIONAL"
    assert by_id["brain_retrieval"]["status"] == "PARTIALLY OPERATIONAL"
    assert by_id["estate_brain_graph"]["runtime_registration"] == "REGISTERED"
