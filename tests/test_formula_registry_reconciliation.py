import copy
import json
from pathlib import Path

import pytest

import szl_formula_registry as registry


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_LOCKED = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")


def _redigest(document):
    document["registry_digest"]["value"] = registry.compute_payload_digest(
        document["payload"]
    )
    return document


def test_v2_authority_digest_and_source_pins_verify():
    document = registry.load_registry(verify=True)
    assert document["schema_version"] == "szl.formula-authority.v2"
    assert document["signature"]["status"] == "UNSIGNED"
    assert len(document["registry_digest"]["value"]) == 64
    assert document["payload"]["authority"] == "FORMAL_SOURCE_PINNED"
    assert document["payload"]["exhaustive"] is False
    assert document["payload"]["formal_source"]["commit"] == registry.FORMAL_COMMIT
    assert document["payload"]["formal_source"]["locked_count_theorem"].endswith(
        "locked_count_eight"
    )


def test_schema_is_recursively_fail_closed():
    schema = json.loads(
        (
            ROOT
            / "schemas"
            / "formula-registry"
            / "formula-registry.v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert schema["properties"]["schema_version"]["const"] == registry.SCHEMA_VERSION
    assert schema["additionalProperties"] is False
    assert schema["properties"]["registry_digest"]["additionalProperties"] is False
    assert schema["properties"]["signature"]["additionalProperties"] is False
    assert schema["properties"]["payload"]["additionalProperties"] is False
    assert schema["properties"]["payload"]["properties"]["locked_proven_count"][
        "const"
    ] == 8
    assert tuple(
        schema["properties"]["payload"]["properties"]["locked_proven_ids"]["const"]
    ) == EXPECTED_LOCKED
    assert schema["$defs"]["formalSource"]["additionalProperties"] is False
    assert schema["$defs"]["kernelSource"]["additionalProperties"] is False
    assert schema["$defs"]["lambdaRule"]["additionalProperties"] is False
    assert schema["$defs"]["policy"]["additionalProperties"] is False
    assert schema["$defs"]["sourceAsset"]["additionalProperties"] is False
    assert schema["$defs"]["formula"]["additionalProperties"] is False


def test_locked_set_is_exact_formal_eight():
    assert registry.LOCKED_PROVEN_IDS == EXPECTED_LOCKED
    assert registry.LOCKED_PROVEN_COUNT == len(EXPECTED_LOCKED) == 8
    flagged = tuple(
        entry["id"]
        for entry in registry.PAYLOAD["formulas"]
        if entry["locked_proven"]
    )
    assert flagged == EXPECTED_LOCKED
    assert registry.formula("F4")["maturity"] == "LOCKED_PROVEN"
    assert registry.formula("F7")["maturity"] == "LOCKED_PROVEN"
    assert registry.formula("F22")["maturity"] == "LOCKED_PROVEN"


def test_formula_authority_is_constraint_only_and_applicability_bound():
    for formula_id in EXPECTED_LOCKED:
        item = registry.formula(formula_id)
        assert item["applicability_required"] is True
        assert item["can_constrain_execution"] is True
        assert item["can_authorize_action"] is False

    basis = registry.applicability_basis(
        "F4",
        applicability="APPLIES",
        basis_sha256="a" * 64,
    )
    assert basis["formula_id"] == "F4"
    assert basis["authority_digest"] == registry.FORMULA_REGISTRY_DIGEST
    assert basis["formal_source_commit"] == registry.FORMAL_COMMIT
    assert basis["can_authorize_action"] is False

    with pytest.raises(ValueError, match="APPLIES"):
        registry.applicability_basis(
            "F4", applicability="UNKNOWN", basis_sha256="a" * 64
        )
    with pytest.raises(ValueError, match="64 lowercase"):
        registry.applicability_basis(
            "F4", applicability="APPLIES", basis_sha256="invalid"
        )


def test_lambda_remains_conjecture_and_non_authorizing():
    item = registry.formula("F23")
    assert registry.LAMBDA_STATUS == "CONJECTURE_1_ADVISORY"
    assert item["locked_proven"] is False
    assert item["can_constrain_execution"] is False
    assert item["can_authorize_action"] is False
    assert "maxAgg_ne_Lambda" in item["theorem_refs"]
    rule = registry.PAYLOAD["lambda"]
    assert rule["can_authorize"] is False
    assert rule["can_be_sole_allow_basis"] is False


def test_callable_formula_namespace_is_explicitly_unmapped():
    kernel = registry.PAYLOAD["kernel_source"]
    assert kernel["repository"] == "szl-holdings/szl-formulas"
    assert kernel["commit"] == registry.FORMULA_KERNEL_COMMIT
    assert kernel["callable_formula_count"] == 21
    assert kernel["f_id_to_callable_mapping"] == "UNKNOWN_NOT_ASSERTED"


def test_source_assets_are_immutable_git_identities():
    assets = registry.PAYLOAD["source_assets"]
    assert {asset["id"] for asset in assets} == {
        "locked-count",
        "proved-formulas",
        "lambda-boundary",
    }
    assert all(asset["repository"] == registry.FORMAL_REPOSITORY for asset in assets)
    assert all(asset["commit"] == registry.FORMAL_COMMIT for asset in assets)
    assert all(len(asset["blob_sha"]) == 40 for asset in assets)
    assert next(a for a in assets if a["id"] == "locked-count")[
        "blob_sha"
    ] == "bbf5deac32e1558eecf13115ea954393788d0e35"


def test_receipt_basis_exposes_authority_without_fake_signature():
    basis = registry.receipt_basis()
    assert basis["authority_for_locked8"] is True
    assert basis["formula_registry_digest"] == registry.FORMULA_REGISTRY_DIGEST
    assert basis["signature_status"] == "UNSIGNED"
    assert basis["locked_proven_count"] == 8
    assert tuple(basis["locked_proven_ids"]) == EXPECTED_LOCKED
    assert basis["lambda_can_authorize"] is False
    assert basis["f_id_to_callable_mapping"] == "UNKNOWN_NOT_ASSERTED"


def test_historical_snapshots_are_quarantined_from_authority():
    historical = tuple(registry.PAYLOAD["historical_non_authorities"])
    assert historical == registry.EXPECTED_HISTORICAL_NON_AUTHORITIES
    source_paths = {
        item["path"] for item in registry.PAYLOAD["source_assets"]
    }
    assert source_paths.isdisjoint(historical)
    assert "static/thesis.json" in historical
    assert "knowledge.json" in historical


def test_digest_tamper_fails_closed():
    document = copy.deepcopy(registry.REGISTRY)
    document["registry_digest"]["value"] = "0" * 64
    with pytest.raises(ValueError, match="digest mismatch"):
        registry.validate_registry_document(document)


def test_locked_five_regression_fails_even_after_redigest():
    document = copy.deepcopy(registry.REGISTRY)
    document["payload"]["locked_proven_ids"] = ["F1", "F11", "F12", "F18", "F19"]
    document["payload"]["locked_proven_count"] = 5
    for item in document["payload"]["formulas"]:
        if item["id"] in {"F4", "F7", "F22"}:
            item["locked_proven"] = False
            item["maturity"] = "EXPERIMENTAL"
            item["can_constrain_execution"] = False
    _redigest(document)
    with pytest.raises(ValueError, match="exact formal eight"):
        registry.validate_registry_document(document)


def test_locked_set_inflation_fails_even_after_redigest():
    document = copy.deepcopy(registry.REGISTRY)
    document["payload"]["locked_proven_ids"].append("F23")
    document["payload"]["locked_proven_count"] = 9
    f23 = next(
        item for item in document["payload"]["formulas"] if item["id"] == "F23"
    )
    f23["locked_proven"] = True
    f23["maturity"] = "LOCKED_PROVEN"
    _redigest(document)
    with pytest.raises(ValueError, match="exact formal eight"):
        registry.validate_registry_document(document)


def test_lambda_promotion_fails_even_after_redigest():
    document = copy.deepcopy(registry.REGISTRY)
    document["payload"]["lambda"]["can_authorize"] = True
    _redigest(document)
    with pytest.raises(ValueError, match="Conjecture 1"):
        registry.validate_registry_document(document)


def test_invented_callable_mapping_fails_even_after_redigest():
    document = copy.deepcopy(registry.REGISTRY)
    document["payload"]["kernel_source"][
        "f_id_to_callable_mapping"
    ] = "F1=lambda_aggregate"
    _redigest(document)
    with pytest.raises(ValueError, match="kernel binding drift|unproved"):
        registry.validate_registry_document(document)


def test_missing_applicability_gate_fails_even_after_redigest():
    document = copy.deepcopy(registry.REGISTRY)
    document["payload"]["formulas"][0]["applicability_required"] = False
    _redigest(document)
    with pytest.raises(ValueError, match="must require an applicability"):
        registry.validate_registry_document(document)


def test_formula_self_authority_fails_even_after_redigest():
    document = copy.deepcopy(registry.REGISTRY)
    document["payload"]["formulas"][0]["can_authorize_action"] = True
    _redigest(document)
    with pytest.raises(ValueError, match="may not independently authorize"):
        registry.validate_registry_document(document)


@pytest.mark.parametrize("field", ["commit", "blob_sha"])
def test_source_pin_drift_fails_even_after_redigest(field):
    document = copy.deepcopy(registry.REGISTRY)
    document["payload"]["source_assets"][0][field] = "f" * 40
    _redigest(document)
    with pytest.raises(ValueError, match="source asset identity drift"):
        registry.validate_registry_document(document)


def test_extra_metadata_fails_closed():
    document = copy.deepcopy(registry.REGISTRY)
    document["payload"]["unexpected"] = True
    _redigest(document)
    with pytest.raises(ValueError, match="key set drift"):
        registry.validate_registry_document(document)
