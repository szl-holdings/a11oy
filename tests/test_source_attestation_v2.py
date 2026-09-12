from __future__ import annotations

import json
from pathlib import Path

import pytest

import szl_source_attestation as source


_ENV = (
    "A11OY_SOURCE_COMMIT", "SZL_GIT_SHA", "SPACE_COMMIT_SHA", "GITHUB_SHA",
    "VERCEL_GIT_COMMIT_SHA",
    "SPACE_REPOSITORY_COMMIT", "A11OY_DEPLOYED_COMMIT", "A11OY_BUILD_DIGEST",
    "SZL_BUILD_DIGEST", "A11OY_IMAGE_DIGEST", "CONTAINER_IMAGE_DIGEST",
    "A11OY_DEPLOYED_AT", "DEPLOYED_AT", "SZL_BUILD_TIME",
)


def _clear(monkeypatch):
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)


def test_missing_build_facts_stay_null_unknown(monkeypatch):
    _clear(monkeypatch)
    result = source.build_attestation_v2(
        "SZLHOLDINGS/a11oy",
        {"repository_url": "https://github.com/szl-holdings/a11oy"},
        "MATCH",
    )
    assert result["source_commit"] == {"value": None, "evidence_class": "UNKNOWN"}
    assert result["deployed_commit"] == {"value": None, "evidence_class": "UNKNOWN"}
    assert result["alignment_state"] == "UNKNOWN"
    assert result["immutable_for_process"] is True


def test_observable_build_facts_are_normalized_and_matched(monkeypatch):
    _clear(monkeypatch)
    sha = "1" * 40
    monkeypatch.setenv("A11OY_SOURCE_COMMIT", sha)
    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", sha)
    monkeypatch.setenv("A11OY_BUILD_DIGEST", "2" * 64)
    monkeypatch.setenv("A11OY_IMAGE_DIGEST", "sha256:" + "3" * 64)
    monkeypatch.setenv("A11OY_DEPLOYED_AT", "2026-07-16T20:30:00-04:00")
    result = source.build_attestation_v2("SZLHOLDINGS/a11oy", {}, "UNKNOWN")
    assert result["alignment_state"] == "MATCH"
    assert result["build_digest"]["value"] == "sha256:" + "2" * 64
    assert result["deploy_timestamp"]["value"] == "2026-07-17T00:30:00Z"


def test_hf_deployment_sha_is_admitted_as_source_commit(monkeypatch):
    _clear(monkeypatch)
    sha = "4" * 40
    monkeypatch.setenv("SZL_GIT_SHA", sha)

    result = source.build_attestation_v2("SZLHOLDINGS/a11oy", {})

    assert result["source_commit"] == {"value": sha, "evidence_class": "MEASURED"}
    assert result["alignment_state"] == "UNKNOWN"


def test_source_schema_accepts_payload(monkeypatch):
    jsonschema = pytest.importorskip("jsonschema")
    _clear(monkeypatch)
    schema = json.loads((Path(__file__).parents[1] / "schemas/source-attestation/source-deploy-attestation.v2.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(source.build_attestation_v2("SZLHOLDINGS/a11oy", {}, "UNKNOWN"))


def test_v1_shape_remains_backward_compatible(monkeypatch):
    _clear(monkeypatch)
    result = source.build_attestation("SZLHOLDINGS/a11oy", {"repository": "szl-holdings/a11oy"}, "MATCH")
    assert result["schema"] == "szl.deployment-source/v1"
    assert result["deployment"]["hf_revision"] is None
    assert result["source"]["repository"] == "szl-holdings/a11oy"
    assert result["alignment_state"] == "UNKNOWN"
    assert set(result["source"]) == {
        "repository", "commit", "path", "relation", "state", "evidence_url",
    }
    assert set(result["deployment"]) == {
        "hf_space", "hf_revision", "revision_state", "measurement_method",
    }
    assert set(result["claims"]) == {
        "github_parity", "reproducible_build", "build_provenance",
    }


def test_product_source_json_is_unsigned_honest_and_never_live(monkeypatch):
    _clear(monkeypatch)
    sha = "1d1d8ace2be629fea9171f05774312c13137400a"
    monkeypatch.setenv("SZL_GIT_SHA", sha)
    payload = source.build_product_source()
    assert payload["schema"] == source.PRODUCT_SOURCE_SCHEMA
    assert payload["path"] == "/.well-known/source.json"
    assert payload["git_sha"] == sha
    assert payload["git_sha_source"] == "env:SZL_GIT_SHA"
    assert payload["identity"] == "/api/a11oy/v1/honest git_sha"
    assert payload["doctrine"] == "v11"
    assert payload["doctrine_lock"]["commit"] == source.DOCTRINE_KERNEL_PIN
    assert payload["doctrine_lock"]["commit"] == "c7c0ba17"
    assert payload["signer"] == "ABSENT"
    assert payload["signer_honesty"] == "UNSIGNED-honest"
    assert payload["certified"] is False
    assert payload["proven_trust"] is False
    assert payload["publication_eligible"] is False
    assert payload["receipt_minted"] is False
    assert payload["dsse"] is None
    assert payload["first_paint"] == "OBSERVED"
    assert payload["status"] == "UNSIGNED-honest"
    for forbidden in ("LIVE", "RUNNING", "PASS"):
        assert payload["first_paint"] != forbidden
        assert payload["status"] != forbidden


def test_product_source_json_matches_be_hardening_kernel_pin():
    from szl_be_hardening import DOCTRINE_LOCK

    assert source.DOCTRINE_KERNEL_PIN == DOCTRINE_LOCK["commit"]
    assert DOCTRINE_LOCK["commit"] == "c7c0ba17"


def test_product_source_route_is_registered_and_exact(monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("starlette.testclient")
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    _clear(monkeypatch)
    monkeypatch.setenv("SZL_GIT_SHA", "1d1d8ace2be629fea9171f05774312c13137400a")
    app = FastAPI()
    result = source.register(
        app,
        "SZLHOLDINGS/a11oy",
        {"repository": "szl-holdings/a11oy"},
        "UNKNOWN",
    )
    assert result["route_product"] == "/.well-known/source.json"
    client = TestClient(app)
    response = client.get("/.well-known/source.json")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store"
    body = response.json()
    assert body["git_sha"] == "1d1d8ace2be629fea9171f05774312c13137400a"
    assert body["signer"] == "ABSENT"
    assert body["certified"] is False
    assert body["first_paint"] == "OBSERVED"
    # Existing attestation routes stay intact.
    assert client.get("/.well-known/szl-source.json").status_code == 200
    assert client.get("/.well-known/szl-source-v2.json").status_code == 200
