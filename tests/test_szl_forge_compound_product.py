"""Fail-closed contract tests for the unified SZL-Forge product surface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "model_release" / "szl-forge-compound-product.json"
SCHEMA_PATH = ROOT / "model_release" / "szl-forge-compound-product.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_compound_product_manifest_validates() -> None:
    manifest = _load(MANIFEST_PATH)
    schema = _load(SCHEMA_PATH)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)


def test_one_product_does_not_claim_one_checkpoint() -> None:
    manifest = _load(MANIFEST_PATH)
    product = manifest["public_product"]
    boundary = manifest["architecture_boundary"]
    assert product["product_id"] == "SZL-Forge"
    assert product["system_type"] == "COMPOUND_GOVERNED_AI_SYSTEM"
    assert product["single_checkpoint"] is False
    assert boundary["unified_experience_not_unified_weights"] is True
    assert set(boundary["weight_bearing_component_ids"]) == {
        "receipt-agent-profile",
        "khipu-brain-navigator-profile",
    }
    components = {item["component_id"]: item for item in manifest["components"]}
    for component_id in boundary["non_weight_component_ids"]:
        assert components[component_id]["weight_relation"] == "NOT_MODEL_WEIGHTS"


def test_exact_served_identity_is_bound_to_current_live_receipt() -> None:
    manifest = _load(MANIFEST_PATH)
    evidence = manifest["local_evidence"]
    receipt_path = ROOT / evidence["receipt_path"]
    receipt = _load(receipt_path)
    assert _sha256(receipt_path) == evidence["receipt_sha256"]
    assert receipt["verification_state"] == "PASS"
    assert {turn["exact_served_model"] for turn in receipt["turns"]} == set(
        evidence["verified_exact_tags"]
    )
    assert {turn["exact_served_model"] for turn in receipt["turns"]} == {
        "khipu:latest",
        "receiptagent:latest",
    }
    required = set(manifest["served_identity_contract"]["required_per_turn_fields"])
    for turn in receipt["turns"]:
        assert required <= set(turn)
    assert manifest["served_identity_contract"]["current_key_scope"] == "PROCESS_BOOT_EPHEMERAL"


def test_all_screenshot_named_repos_have_fail_closed_migrations() -> None:
    manifest = _load(MANIFEST_PATH)
    migrations = manifest["legacy_repo_migration"]
    assert {item["source_id"] for item in migrations} == {
        "SZLHOLDINGS/a11oy-v19-substrate",
        "SZLHOLDINGS/governed-inference-meter",
        "SZLHOLDINGS/szl-blocked",
        "SZLHOLDINGS/szl-govsign",
        "SZLHOLDINGS/szl-provctl",
        "SZLHOLDINGS/szl-invariants",
        "SZLHOLDINGS/szl-ouroboros",
        "SZLHOLDINGS/szl-formulas",
    }
    component_ids = {item["component_id"] for item in manifest["components"]}
    for migration in migrations:
        assert migration["canonical_component_id"] in component_ids
        assert migration["merge_into_checkpoint"] is False
        assert migration["state"] == "DECLARED_PLAN_NOT_EXECUTED"
        assert "NOT_LIVE_READBACK" in migration["source_observation"]


def test_hub_topology_has_one_space_and_independently_typed_members() -> None:
    topology = _load(MANIFEST_PATH)["hub_topology"]
    assert topology["one_public_entrypoint"] == {
        "target_id": "SZLHOLDINGS/SZL-Forge",
        "artifact_type": "SPACE",
        "state": "PLANNED_REMOTE_STATE_NOT_ASSERTED",
        "role": "Fail-closed product shell, system card, live readiness, selected profile, exact-served identity, citations, receipt download, and limitations.",
    }
    assert topology["canonical_collection"]["artifact_type"] == "COLLECTION"
    assert {item["artifact_type"] for item in topology["weight_artifacts"]} == {
        "MODEL_ADAPTER"
    }
    assert all(
        item["artifact_type"] != "MODEL_ADAPTER"
        for item in topology["support_artifacts"]
    )


def test_promotion_remains_blocked_despite_local_runtime_pass() -> None:
    manifest = _load(MANIFEST_PATH)
    gates = {item["gate_id"]: item["state"] for item in manifest["promotion_gates"]}
    assert gates["local-runtime-exact-tag-and-receipt"] == "PASS_LOCAL_ONLY"
    assert gates["remote-weight-artifact-binding"] == "BLOCKING"
    assert gates["durable-release-signing-and-transparency"] == "BLOCKING"
    assert gates["public-hub-readback"] == "BLOCKING"
    assert gates["human-release-approval"] == "BLOCKING"
    assert set(manifest["external_mutations"].values()) == {False}
    assert set(manifest["claims_boundary"].values()) == {False}
