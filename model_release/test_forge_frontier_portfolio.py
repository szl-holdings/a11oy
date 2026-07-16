"""Contract tests for the non-executed SZL Forge frontier portfolio.

These tests validate structure and honesty boundaries. They do not download a
model, build a dataset, run an evaluation, or provide a promotion receipt.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "forge_frontier_portfolio.schema.json"
MANIFEST_PATH = HERE / "forge_frontier_portfolio.json"


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _assert_unique(items: list[dict], field: str) -> None:
    values = [item[field] for item in items]
    assert len(values) == len(set(values)), f"duplicate {field}: {values}"


def test_manifest_is_draft_2020_12_schema_valid() -> None:
    schema = _load(SCHEMA_PATH)
    manifest = _load(MANIFEST_PATH)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.path))

    assert not errors, "\n".join(
        f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in errors
    )


def test_portfolio_is_explicitly_non_executed_and_non_measured() -> None:
    manifest = _load(MANIFEST_PATH)

    assert manifest["status"] == "RESEARCH_PLAN_NOT_EXECUTED"
    assert manifest["evidence_policy"]["local_measurements_in_this_manifest"] is False
    assert manifest["evidence_policy"]["vendor_benchmarks_are_local_evidence"] is False
    assert manifest["target_laptop_profile"]["evidence_label"] == "DECLARED_PLAN"
    assert manifest["target_laptop_profile"]["local_benchmark_status"] == "NOT_MEASURED"

    for model in manifest["models"]:
        assert model["upstream"]["evidence_label"] == "PRIMARY_REPORTED"
        assert model["upstream"]["url"].startswith("https://")
        assert model["upstream"]["license_spdx"]
        feasibility = model["laptop_feasibility"]
        assert feasibility["evidence_label"] == "ENGINEERING_INFERENCE"
        assert feasibility["local_benchmark_status"] == "NOT_MEASURED"

    for collection in manifest["collections"]:
        assert collection["status"] == "PROPOSED_NOT_BUILT"
        assert collection["evidence_label"] == "DECLARED_PLAN"
        for source in collection["candidate_sources"]:
            assert source["status"] == "OPTIONAL_PENDING_ROW_LEVEL_ADMISSION"
            assert source["evidence_label"] == "PRIMARY_REPORTED"

    for gate in manifest["promotion_gates"]:
        assert gate["required_evidence_label"] == "LOCAL_MEASURED_REQUIRED"
        assert gate["current_status"] == "NOT_MEASURED"
        assert gate["blocking"] is True


def test_ids_and_source_crosswalk_are_complete() -> None:
    manifest = _load(MANIFEST_PATH)

    _assert_unique(manifest["models"], "id")
    _assert_unique(manifest["collections"], "id")
    _assert_unique(manifest["promotion_gates"], "id")
    _assert_unique(manifest["primary_sources"], "id")

    documented_urls = {source["url"] for source in manifest["primary_sources"]}
    upstream_urls = {model["upstream"]["url"] for model in manifest["models"]}
    candidate_urls = {
        source["url"]
        for collection in manifest["collections"]
        for source in collection["candidate_sources"]
    }

    assert upstream_urls <= documented_urls
    assert candidate_urls <= documented_urls
    assert all(source["url"].startswith("https://") for source in manifest["primary_sources"])
    assert all(source["evidence_label"] == "PRIMARY_REPORTED" for source in manifest["primary_sources"])


def test_required_frontier_roles_and_release_controls_are_present() -> None:
    manifest = _load(MANIFEST_PATH)
    dispositions = {model["disposition"] for model in manifest["models"]}
    collection_ids = {collection["id"] for collection in manifest["collections"]}
    gate_ids = {gate["id"] for gate in manifest["promotion_gates"]}

    assert {
        "COMPLETE_EXISTING_PROGRAM",
        "FRONTIER_BAKEOFF_CANDIDATE",
        "BAKEOFF_CONTROL",
        "SPECIALIST_CANDIDATE",
        "SECOND_BRAIN_COMPONENT",
        "SAFETY_COMPONENT",
    } <= dispositions
    assert {
        "SZL-ReceiptBench",
        "SZL-BrainQrels",
        "SZL-FormulaProofObligations",
        "SZL-PolicyAdversarial",
        "SZL-CodeBench",
        "SZL-ModelReceipts",
    } == collection_ids
    assert {
        "upstream-identity",
        "rights-provenance",
        "contamination",
        "task-quality",
        "safety",
        "retrieval-quality",
        "resource-envelope",
        "restart-recovery",
        "receipt-integrity",
    } == gate_ids

    for collection in manifest["collections"]:
        release_artifacts = " ".join(collection["required_release_artifacts"]).lower()
        assert "dataset card" in release_artifacts
        assert "croissant" in release_artifacts
        assert "prov" in release_artifacts
        assert "slsa" in release_artifacts or "in-toto" in release_artifacts


def test_second_brain_remains_fail_closed_by_contract() -> None:
    manifest = _load(MANIFEST_PATH)
    architecture = manifest["retrieval_architecture"]
    invariants = " ".join(architecture["invariants"]).lower()

    assert architecture["status"] == "DECLARED_NOT_IMPLEMENTED_BY_THIS_ARTIFACT"
    assert architecture["evidence_label"] == "ENGINEERING_INFERENCE"
    assert "quarantined" in invariants
    assert "abstains" in invariants
    assert "canonical source" in invariants
    assert "memory writes" in invariants


if __name__ == "__main__":
    tests = [
        test_manifest_is_draft_2020_12_schema_valid,
        test_portfolio_is_explicitly_non_executed_and_non_measured,
        test_ids_and_source_crosswalk_are_complete,
        test_required_frontier_roles_and_release_controls_are_present,
        test_second_brain_remains_fail_closed_by_contract,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
