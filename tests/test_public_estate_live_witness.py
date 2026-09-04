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


def test_manifest_declares_one_platform_and_six_public_products():
    manifest = witness.load_and_validate_manifest(MANIFEST)
    assert manifest["schema"] == "szl.public-estate/v1"
    assert manifest["platform_count"] == 1
    assert manifest["public_vertical_product_count"] == 6
    assert {item["id"] for item in manifest["public_products"]} == {
        "killinchu",
        "sentra",
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
    assert "sentra" in public_ids
    assert planes["vessels"]["runtime"] == "killinchu"
    assert planes["aegis"]["status"] == "portfolio-label"
    assert planes["aegis"]["runtime"] == "sentra"
    assert planes["immune"]["status"] == "migration-required"
    assert planes["immune"]["runtime"] is None
    assert planes["immune"]["target_runtime"] == "sentra"
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


def test_manifest_rejects_folded_plane_as_seventh_product(tmp_path: Path):
    value = raw_manifest()
    duplicate = copy.deepcopy(value["public_products"][0])
    duplicate.update(
        {
            "id": "vessels",
            "title": "Vessels",
            "hf_repository": "SZLHOLDINGS/vessels",
            "base_url": "https://szlholdings-vessels.hf.space",
        }
    )
    value["allowed_hosts"].append("szlholdings-vessels.hf.space")
    value["public_products"].append(duplicate)
    value["public_vertical_product_count"] = 7
    with pytest.raises(witness.ContractError, match="exactly six"):
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
    assert incomplete["verified_surface_count"] == 6


def test_killinchu_and_lyte_identity_policies_are_explicit_and_narrow():
    manifest = witness.load_and_validate_manifest(MANIFEST)
    killinchu = next(
        item for item in manifest["public_products"] if item["id"] == "killinchu"
    )
    assert killinchu["source_repository_policy"] == "manifest-fixed-runtime-revision"
    assert killinchu["hf_revision_policy"] == "provider-observed"
    for item in manifest["platforms"] + manifest["public_products"]:
        if item["id"] == "lyte":
            assert item["source_repository_policy"] == "lyte-source-bound-build"
            assert item["hf_revision_policy"] == "provider-observed"
            assert item["deployment_source_repository"] == "szl-holdings/lyte-services"
            assert item["revision_policy"] == "exact-default-branch"
            assert "/api/source" not in item["required_paths"]
            assert "/readyz" in item["required_paths"]
        elif item["id"] in {"a11oy", "killinchu"}:
            assert item["source_repository_policy"] == "manifest-fixed-runtime-revision"
            assert item["hf_revision_policy"] == "provider-observed"
        else:
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


def lyte_surface() -> dict:
    manifest = witness.load_and_validate_manifest(MANIFEST)
    return next(item for item in manifest["public_products"] if item["id"] == "lyte")


def lyte_payload() -> dict:
    # Shape read from lyte-services@2131d2e space/server.py, not live evidence.
    return {
        "schema": "szl.build-info/v1",
        "service": "lyte-signal-lattice",
        "source_repository": "szl-holdings/lyte-services",
        "build": {"state": "OBSERVED", "revision": "d" * 40},
        "source_binding": {
            "bindings_agree": True,
            "evidence_sources": ["env:LYTE_SOURCE_REVISION", "container-file"],
        },
    }


def test_lyte_declared_repository_and_observed_revision_normalize_without_hf_claim():
    payload = lyte_payload()
    fields = witness.apply_source_repository_policy(
        witness.selected_build_fields(payload), payload, lyte_surface()
    )
    assert fields["source_revision"] == "d" * 40
    assert fields["source_repository"] == "szl-holdings/lyte-services"
    assert fields["source_repository_evidence"] == "LYTE_RUNTIME_AGREEING_SOURCE_BINDINGS"
    assert "hf_revision" not in fields


@pytest.mark.parametrize("path,value", [
    (("schema",), "other"),
    (("service",), "generic-shell"),
    (("source_repository",), "szl-holdings/a11oy"),
    (("build", "state"), "UNBOUND"),
    (("build", "state"), "MISMATCH"),
    (("build", "revision"), "short"),
    (("source_binding", "bindings_agree"), False),
    (("source_binding", "bindings_agree"), "true"),
    (("source_binding", "evidence_sources"), []),
    (("source_binding", "evidence_sources"), ["request:caller"]),
    (("source_binding", "evidence_sources"), ["env:LYTE_SOURCE_REVISION", "request:caller"]),
    (("source_revision",), "e" * 40),
])
def test_lyte_ambiguous_or_untrusted_identity_is_rejected(path, value):
    payload = lyte_payload()
    target = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(witness.ContractError):
        witness.apply_source_repository_policy(
            witness.selected_build_fields(payload), payload, lyte_surface()
        )


@pytest.mark.parametrize("field,value", [
    ("id", "finance"),
    ("deployment_source_repository", "szl-holdings/a11oy"),
    ("revision_policy", "declared-commit"),
    ("hf_revision_policy", "runtime-declared"),
])
def test_lyte_policy_cannot_be_reused_for_another_identity(tmp_path, field, value):
    manifest = raw_manifest()
    item = next(row for row in manifest["public_products"] if row["id"] == "lyte")
    item[field] = value
    with pytest.raises(witness.ContractError, match="Lyte source policy requires"):
        witness.load_and_validate_manifest(write_manifest(tmp_path, manifest))


def test_kept_sentra_cannot_return_to_retirement_candidates(tmp_path):
    manifest = raw_manifest()
    manifest["retirement_candidates"].append({
        "hf_repository": "SZLHOLDINGS/sentra",
        "state": "evidence-gated",
        "retire_only_after": ["source-snapshot-recorded"],
    })
    with pytest.raises(witness.ContractError, match="kept public Space"):
        witness.load_and_validate_manifest(write_manifest(tmp_path, manifest))


def install_lyte_observations(monkeypatch, payload, tip="d" * 40):
    def read(_opener, url, *, timeout, token=None):
        assert token is None  # Never send GitHub authority to a public app.
        body = json.dumps(payload if url.endswith("/api/build-info") else {}).encode()
        return witness.HttpObservation(url, 200, "application/json", witness.sha256_hex(body), body)

    def github_tip(_opener, repository, branch, *, timeout, token):
        assert repository == "szl-holdings/lyte-services"
        assert branch == "main"
        return tip, {"status": 200}

    monkeypatch.setattr(witness, "request_bytes", read)
    monkeypatch.setattr(witness, "github_default_tip", github_tip)
    monkeypatch.setattr(witness, "hf_space_revision", lambda *a, **kw: ("f" * 40, {"status": 200}))


def test_lyte_surface_is_verified_only_at_exact_default_tip(monkeypatch):
    install_lyte_observations(monkeypatch, lyte_payload())
    row = witness.observe_surface(None, lyte_surface(), timeout=1, token="test-only-github")
    assert row["verified"] is True
    assert row["hf_proof"]["declared_revision"] is None
    assert row["build"]["hf_revision_observed_by_witness"] == "f" * 40
    install_lyte_observations(monkeypatch, lyte_payload(), tip="e" * 40)
    row = witness.observe_surface(None, lyte_surface(), timeout=1, token=None)
    assert row["verified"] is False
    assert any("expected default tip" in message for message in row["failures"])


def test_invalid_identity_retains_failed_surface_row(monkeypatch):
    payload = lyte_payload()
    payload["build"]["state"] = "MISMATCH"
    install_lyte_observations(monkeypatch, payload)
    row = witness.observe_surface(None, lyte_surface(), timeout=1, token=None)
    assert row["id"] == "lyte"
    assert row["verified"] is False
    assert len(row["routes"]) == len(lyte_surface()["required_paths"])
    assert any("source identity policy:" in message for message in row["failures"])


@pytest.mark.parametrize("alteration", ["missing", "duplicate", "foreign", "nonstring"])
def test_partial_or_ambiguous_inventory_cannot_be_complete(alteration):
    manifest = witness.load_and_validate_manifest(MANIFEST)
    rows = [{"id": row["id"], "verified": True} for row in manifest["platforms"] + manifest["public_products"]]
    if alteration == "missing":
        rows.pop()
    elif alteration == "duplicate":
        rows[-1] = dict(rows[0])
    elif alteration == "foreign":
        rows[-1]["id"] = "foreign"
    else:
        rows[-1]["id"] = {"not": "an identifier"}
    receipt = witness.build_receipt(manifest, mode="live", observations=rows, attempt=1)
    assert receipt["complete"] is False
    assert receipt["inventory_complete"] is False


def test_a11oy_runtime_shape_uses_observed_deployer_revision():
    manifest = witness.load_and_validate_manifest(MANIFEST)
    surface = manifest["platforms"][0]
    # Runtime shape from source plus immutable relock artifact 9955879039.
    payload = {
        "status": "OBSERVED", "service": "a11oy", "receipt_minted": False,
        "build": {"state": "OBSERVED", "revision": "a" * 40,
                  "revision_source": "env:SZL_GIT_SHA"},
    }
    fields = witness.apply_source_repository_policy(
        witness.selected_build_fields(payload), payload, surface
    )
    assert fields["source_repository"] == "szl-holdings/a11oy"
    assert fields["source_revision"] == "a" * 40
    assert "hf_revision" not in fields
    payload["build"]["revision_source"] = "request:caller"
    with pytest.raises(witness.ContractError, match="untrusted origin"):
        witness.apply_source_repository_policy(
            witness.selected_build_fields(payload), payload, surface
        )
