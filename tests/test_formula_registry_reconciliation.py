import copy
import json
from pathlib import Path

import pytest

import szl_formula_registry as registry


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_LOCKED = ("F1", "F11", "F12", "F18", "F19")


def test_registry_digest_and_pinned_sources_verify():
    document = registry.load_registry(verify=True)
    assert document["signature"]["status"] == "UNSIGNED"
    assert len(document["registry_digest"]["value"]) == 64
    assert document["payload"]["exhaustive"] is False
    assert "not an inventory" in document["payload"]["coverage_scope"]


def test_schema_is_recursively_fail_closed_for_registry_objects():
    schema = json.loads(
        (ROOT / "schemas" / "formula-registry" / "formula-registry.v1.schema.json")
        .read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    assert schema["properties"]["registry_digest"]["additionalProperties"] is False
    assert schema["properties"]["signature"]["additionalProperties"] is False
    assert schema["properties"]["payload"]["additionalProperties"] is False
    assert schema["$defs"]["policy"]["additionalProperties"] is False
    assert schema["$defs"]["sourceAsset"]["additionalProperties"] is False
    assert schema["$defs"]["formula"]["additionalProperties"] is False


def test_locked_set_is_exact_and_count_cannot_drift():
    assert registry.LOCKED_PROVEN_IDS == EXPECTED_LOCKED
    assert registry.LOCKED_PROVEN_COUNT == len(EXPECTED_LOCKED) == 5
    flagged = tuple(
        entry["id"] for entry in registry.PAYLOAD["formulas"] if entry["locked_proven"]
    )
    assert flagged == EXPECTED_LOCKED


def test_source_present_experimentals_never_enter_locked_set():
    for formula_id in ("F4", "F7", "F22"):
        entry = registry.formula(formula_id)
        assert entry["maturity"] == "EXPERIMENTAL"
        assert entry["locked_proven"] is False
        assert entry["evidence_status"] == "SOURCE_PRESENT_EXPERIMENTAL_NOT_LOCKED"
        source = (ROOT / entry["source_path"]).read_text(encoding="utf-8")
        assert all(theorem in source for theorem in entry["theorem_refs"])


def test_lambda_cannot_be_promoted_by_conditional_results():
    entry = registry.formula("F23")
    assert registry.LAMBDA_STATUS == "CONJECTURE_1_ADVISORY"
    assert entry["maturity"] == "CONJECTURE_1_ADVISORY"
    assert entry["locked_proven"] is False
    source = (ROOT / entry["source_path"]).read_text(encoding="utf-8")
    assert "theorem maxAgg_ne_Lambda" in source


def test_existing_static_thesis_agrees_with_registry():
    thesis = json.loads((ROOT / "static" / "thesis.json").read_text(encoding="utf-8"))
    summary = thesis["proof_summary"]
    assert summary["locked_proven"] == registry.LOCKED_PROVEN_COUNT
    assert tuple(summary["locked_ids"]) == registry.LOCKED_PROVEN_IDS
    locked_flags = tuple(
        item["id"] for item in thesis["proven_formulas"] if item["locked_kernel"]
    )
    assert locked_flags == registry.LOCKED_PROVEN_IDS


def test_receipt_basis_exposes_digest_without_fake_signature():
    basis = registry.receipt_basis()
    assert basis["formula_registry_digest"] == registry.FORMULA_REGISTRY_DIGEST
    assert basis["signature_status"] == "UNSIGNED"
    assert basis["exhaustive"] is False


def _resign_digest_only(document):
    """Recompute the public digest, never a signature, to isolate semantic tampering."""
    document["registry_digest"]["value"] = registry.compute_payload_digest(document["payload"])
    return document


def test_digest_tamper_fails_closed():
    document = copy.deepcopy(registry.REGISTRY)
    document["registry_digest"]["value"] = "0" * 64
    with pytest.raises(ValueError, match="digest mismatch"):
        registry.validate_registry_document(document, verify_source_hashes=False)


@pytest.mark.parametrize("formula_id", ["F4", "F7", "F22"])
def test_experimental_promotion_fails_even_with_recomputed_digest(formula_id):
    document = copy.deepcopy(registry.REGISTRY)
    entry = next(item for item in document["payload"]["formulas"] if item["id"] == formula_id)
    entry["maturity"] = "LOCKED_PROVEN"
    entry["locked_proven"] = True
    _resign_digest_only(document)
    with pytest.raises(ValueError, match="locked five|EXPERIMENTAL"):
        registry.validate_registry_document(document, verify_source_hashes=False)


def test_lambda_promotion_fails_even_with_recomputed_digest():
    document = copy.deepcopy(registry.REGISTRY)
    entry = next(item for item in document["payload"]["formulas"] if item["id"] == "F23")
    entry["maturity"] = "LOCKED_PROVEN"
    entry["locked_proven"] = True
    entry["theorem_refs"].remove("maxAgg_ne_Lambda")
    _resign_digest_only(document)
    with pytest.raises(ValueError, match="locked five|Conjecture 1|counterexample"):
        registry.validate_registry_document(document, verify_source_hashes=False)


def test_duplicate_id_and_theorem_ref_fail_closed():
    duplicate_id = copy.deepcopy(registry.REGISTRY)
    duplicate_id["payload"]["formulas"][1]["id"] = "F1"
    _resign_digest_only(duplicate_id)
    with pytest.raises(ValueError, match="duplicate"):
        registry.validate_registry_document(duplicate_id, verify_source_hashes=False)

    duplicate_ref = copy.deepcopy(registry.REGISTRY)
    duplicate_ref["payload"]["formulas"][1]["theorem_refs"].append(
        duplicate_ref["payload"]["formulas"][1]["theorem_refs"][0]
    )
    _resign_digest_only(duplicate_ref)
    with pytest.raises(ValueError, match="duplicate theorem_refs"):
        registry.validate_registry_document(duplicate_ref, verify_source_hashes=False)

    substituted_ref = copy.deepcopy(registry.REGISTRY)
    substituted_ref["payload"]["formulas"][1]["theorem_refs"][0] = "f2_scheduler_liveness"
    _resign_digest_only(substituted_ref)
    with pytest.raises(ValueError, match="globally unique|F4 semantic drift"):
        registry.validate_registry_document(substituted_ref, verify_source_hashes=False)


def test_path_escape_signature_and_exhaustive_tamper_fail_closed():
    escaped = copy.deepcopy(registry.REGISTRY)
    escaped["payload"]["source_assets"][0]["path"] = "../outside.md"
    _resign_digest_only(escaped)
    with pytest.raises(ValueError, match="escapes registry root"):
        registry.validate_registry_document(escaped, verify_source_hashes=False)

    source_digest = copy.deepcopy(registry.REGISTRY)
    source_digest["payload"]["source_assets"][0]["sha256"] = "f" * 64
    _resign_digest_only(source_digest)
    with pytest.raises(ValueError, match="source asset metadata/digest drift"):
        registry.validate_registry_document(source_digest, verify_source_hashes=False)

    signed = copy.deepcopy(registry.REGISTRY)
    signed["signature"]["status"] = "SIGNED"
    with pytest.raises(ValueError, match="UNSIGNED"):
        registry.validate_registry_document(signed, verify_source_hashes=False)

    exhaustive = copy.deepcopy(registry.REGISTRY)
    exhaustive["payload"]["exhaustive"] = True
    _resign_digest_only(exhaustive)
    with pytest.raises(ValueError, match="exhaustive drift|non-exhaustive"):
        registry.validate_registry_document(exhaustive, verify_source_hashes=False)


def test_handwritten_validator_rejects_metadata_drift_with_recomputed_digest():
    doctrine = copy.deepcopy(registry.REGISTRY)
    doctrine["payload"]["doctrine_version"] = "invalid-version"
    _resign_digest_only(doctrine)
    with pytest.raises(ValueError, match="doctrine_version drift"):
        registry.validate_registry_document(doctrine, verify_source_hashes=False)

    policy = copy.deepcopy(registry.REGISTRY)
    policy["payload"]["policy"]["locked_set_rule"] = "The locked baseline is eight."
    _resign_digest_only(policy)
    with pytest.raises(ValueError, match="policy drift"):
        registry.validate_registry_document(policy, verify_source_hashes=False)

    misleading_name = copy.deepcopy(registry.REGISTRY)
    f12 = next(item for item in misleading_name["payload"]["formulas"] if item["id"] == "F12")
    f12["name"] = "Full Nonlinear Kuramoto Synchronization"
    _resign_digest_only(misleading_name)
    with pytest.raises(ValueError, match="F12 formula name drift"):
        registry.validate_registry_document(misleading_name, verify_source_hashes=False)

    missing_caveat = copy.deepcopy(registry.REGISTRY)
    f12 = next(item for item in missing_caveat["payload"]["formulas"] if item["id"] == "F12")
    del f12["caveat"]
    _resign_digest_only(missing_caveat)
    with pytest.raises(ValueError, match="F12 formula metadata key set drift"):
        registry.validate_registry_document(missing_caveat, verify_source_hashes=False)
