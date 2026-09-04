# SPDX-License-Identifier: Apache-2.0
"""Contract tests for the fixed-origin SZL public-estate witness."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "public_estate_live_witness.py"
MANIFEST = ROOT / "governance" / "public-estate.v1.json"

spec = importlib.util.spec_from_file_location("public_estate_live_witness", SCRIPT)
assert spec is not None and spec.loader is not None
witness = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = witness
spec.loader.exec_module(witness)


def raw_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def write_manifest(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_manifest_declares_one_platform_and_five_public_products():
    manifest = witness.load_and_validate_manifest(MANIFEST)
    assert manifest["schema"] == "szl.public-estate/v1"
    assert manifest["platform_count"] == 1
    assert manifest["public_vertical_product_count"] == 5
    assert {item["id"] for item in manifest["public_products"]} == {
        "killinchu",
        "lyte",
        "finance",
        "terra",
        "counsel",
    }
    assert len(manifest["manifest_sha256"]) == 64


def test_capability_planes_cannot_reappear_as_public_products():
    manifest = witness.load_and_validate_manifest(MANIFEST)
    planes = {item["id"]: item for item in manifest["capability_planes"]}
    public_ids = {
        item["id"]
        for item in manifest["platforms"] + manifest["public_products"]
    }
    assert not public_ids.intersection(planes)
    assert planes["sentra"]["runtime"] == "killinchu"
    assert planes["vessels"]["runtime"] == "killinchu"
    assert planes["aegis"]["status"] == "portfolio-label"
    assert planes["immune"]["status"] == "migration-required"
    assert planes["immune"]["runtime"] is None
    assert all(
        plane["independent_public_space_allowed"] is False
        for plane in planes.values()
    )


def test_manifest_rejects_silent_immune_runtime(tmp_path: Path):
    value = raw_manifest()
    immune = next(item for item in value["capability_planes"] if item["id"] == "immune")
    immune["runtime"] = "sentra"
    with pytest.raises(witness.ContractError, match="IMMUNE cannot silently alias"):
        witness.load_and_validate_manifest(write_manifest(tmp_path, value))


def test_manifest_rejects_folded_plane_as_sixth_product(tmp_path: Path):
    value = raw_manifest()
    duplicate = copy.deepcopy(value["public_products"][0])
    duplicate.update(
        {
            "id": "sentra",
            "title": "Sentra",
            "hf_repository": "SZLHOLDINGS/sentra",
            "base_url": "https://szlholdings-sentra.hf.space",
        }
    )
    value["allowed_hosts"].append("szlholdings-sentra.hf.space")
    value["public_products"].append(duplicate)
    value["public_vertical_product_count"] = 6
    with pytest.raises(witness.ContractError, match="exactly five"):
        witness.load_and_validate_manifest(write_manifest(tmp_path, value))


def test_manifest_rejects_caller_like_absolute_route(tmp_path: Path):
    value = raw_manifest()
    value["public_products"][0]["required_paths"].append(
        "https://untrusted.example.invalid/probe"
    )
    with pytest.raises(witness.ContractError, match="must begin with"):
        witness.load_and_validate_manifest(write_manifest(tmp_path, value))


def test_manifest_rejects_non_https_or_unknown_origin(tmp_path: Path):
    value = raw_manifest()
    value["public_products"][0]["base_url"] = "http://example.invalid"
    with pytest.raises(witness.ContractError, match="HTTPS"):
        witness.load_and_validate_manifest(write_manifest(tmp_path, value))


def test_build_field_normalization_accepts_nested_source_contract():
    fields = witness.selected_build_fields(
        {
            "build": {
                "repository": "szl-holdings/example",
                "git_sha": "a" * 40,
                "run_id": "123",
            },
            "deployment": {
                "space_repository": "SZLHOLDINGS/example",
                "space_revision": "b" * 40,
                "artifact_sha256": "c" * 64,
            },
        }
    )
    assert fields == {
        "source_repository": "szl-holdings/example",
        "source_revision": "a" * 40,
        "workflow_run_id": "123",
        "hf_repository": "SZLHOLDINGS/example",
        "hf_revision": "b" * 40,
        "artifact_set_sha256": "c" * 64,
    }


def test_join_fixed_never_accepts_another_origin():
    assert witness.join_fixed("https://example.com", "/healthz") == (
        "https://example.com/healthz"
    )
    with pytest.raises(witness.ContractError, match="escaped"):
        witness.join_fixed("https://example.com", "https://other.example/healthz")


def test_offline_receipt_is_deterministic_in_shape_and_not_a_live_claim():
    manifest = witness.load_and_validate_manifest(MANIFEST)
    receipt = witness.build_receipt(
        manifest,
        mode="offline-contract",
        observations=[],
        attempt=1,
    )
    assert receipt["schema"] == "szl.public-estate-witness/v1"
    assert receipt["complete"] is False
    assert receipt["public_surface_count"] == 0
    assert receipt["network_contract"]["method"] == "GET_ONLY"
    assert receipt["network_contract"]["caller_supplied_urls"] is False
    assert receipt["network_contract"]["credentials_sent_to_public_products"] is False
    asserted_hash = receipt.pop("receipt_sha256")
    expected_hash = hashlib.sha256(witness.canonical_json(receipt)).hexdigest()
    assert asserted_hash == expected_hash


def test_live_receipt_is_complete_only_when_every_surface_is_verified():
    manifest = witness.load_and_validate_manifest(MANIFEST)
    observations = [
        {"id": item["id"], "verified": True, "failures": []}
        for item in manifest["platforms"] + manifest["public_products"]
    ]
    complete = witness.build_receipt(
        manifest,
        mode="live",
        observations=observations,
        attempt=2,
    )
    assert complete["complete"] is True
    observations[-1]["verified"] = False
    observations[-1]["failures"] = ["route unavailable"]
    incomplete = witness.build_receipt(
        manifest,
        mode="live",
        observations=observations,
        attempt=3,
    )
    assert incomplete["complete"] is False
    assert incomplete["verified_surface_count"] == 5


def test_killinchu_identity_policies_are_explicit_and_narrow():
    manifest = witness.load_and_validate_manifest(MANIFEST)
    killinchu = next(
        item for item in manifest["public_products"] if item["id"] == "killinchu"
    )
    assert killinchu["source_repository_policy"] == "manifest-fixed-runtime-revision"
    assert killinchu["hf_revision_policy"] == "provider-observed"
    for item in manifest["platforms"] + manifest["public_products"]:
        if item["id"] != "killinchu":
            assert item["source_repository_policy"] == "runtime-declared"
            assert item["hf_revision_policy"] == "runtime-declared"


def test_killinchu_runtime_shape_requires_fixed_service_and_deployer_origin():
    manifest = witness.load_and_validate_manifest(MANIFEST)
    surface = next(
        item for item in manifest["public_products"] if item["id"] == "killinchu"
    )
    payload = {
        "status": "OBSERVED",
        "service": "killinchu",
        "build": {
            "state": "OBSERVED",
            "revision": "d" * 40,
            "revision_source": "env:SZL_GIT_SHA",
        },
    }
    fields = witness.apply_source_repository_policy(
        witness.selected_build_fields(payload), payload, surface
    )
    assert fields["source_revision"] == "d" * 40
    assert fields["source_repository"] == "szl-holdings/killinchu"
    assert fields["source_repository_evidence"] == "MANIFEST_FIXED_RUNTIME_REVISION"

    wrong_service = copy.deepcopy(payload)
    wrong_service["service"] = "other"
    with pytest.raises(witness.ContractError, match="service mismatch"):
        witness.apply_source_repository_policy(
            witness.selected_build_fields(wrong_service), wrong_service, surface
        )

    wrong_origin = copy.deepcopy(payload)
    wrong_origin["build"]["revision_source"] = "request:caller"
    with pytest.raises(witness.ContractError, match="untrusted origin"):
        witness.apply_source_repository_policy(
            witness.selected_build_fields(wrong_origin), wrong_origin, surface
        )


def test_manifest_rejects_unknown_identity_policies(tmp_path: Path):
    value = raw_manifest()
    value["public_products"][0]["source_repository_policy"] = "guess"
    with pytest.raises(witness.ContractError, match="unknown source-repository policy"):
        witness.load_and_validate_manifest(write_manifest(tmp_path, value))

    value = raw_manifest()
    value["public_products"][0]["hf_revision_policy"] = "trust-me"
    with pytest.raises(witness.ContractError, match="unknown Hugging Face revision policy"):
        witness.load_and_validate_manifest(write_manifest(tmp_path, value))


def test_nested_build_revision_is_not_generic_source_identity():
    payload = {
        "service": "another-surface",
        "build": {
            "state": "OBSERVED",
            "revision": "e" * 40,
            "revision_source": "env:SZL_GIT_SHA",
        },
    }
    assert "source_revision" not in witness.selected_build_fields(payload)
