# SPDX-License-Identifier: Apache-2.0
"""Fail-closed source/Space attestation contract for separate Git histories."""

import hashlib
import json
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_source_attestation as attestation


_BUILD_ENV = (
    "A11OY_SOURCE_COMMIT",
    "SZL_GIT_SHA",
    "SPACE_COMMIT_SHA",
    "GITHUB_SHA",
    "VERCEL_GIT_COMMIT_SHA",
    "SPACE_REPOSITORY_COMMIT",
    "A11OY_DEPLOYED_COMMIT",
    "A11OY_BUILD_DIGEST",
    "SZL_BUILD_DIGEST",
    "A11OY_IMAGE_DIGEST",
    "CONTAINER_IMAGE_DIGEST",
    "A11OY_DEPLOYED_AT",
    "DEPLOYED_AT",
    "SZL_BUILD_TIME",
    "A11OY_HF_RUNTIME_BINDING",
)


@pytest.fixture(autouse=True)
def clear_build_inputs(monkeypatch):
    for name in _BUILD_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    ("source_sha", "space_sha"),
    [("1" * 40, "1" * 40), ("1" * 40, "2" * 40)],
    ids=["equal-sha-strings", "distinct-sha-strings"],
)
def test_cross_repository_shas_do_not_prove_alignment(
    monkeypatch, source_sha, space_sha
):
    monkeypatch.setenv("SZL_GIT_SHA", source_sha)
    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", space_sha)

    v2 = attestation.build_attestation_v2("SZLHOLDINGS/a11oy", {})
    v1 = attestation.build_attestation("SZLHOLDINGS/a11oy", {})

    assert v2["source_commit"] == {"value": source_sha, "evidence_class": "ENV_DECLARATION"}
    assert v1["source"]["state"] == "ENV_DECLARATION"
    assert v2["deployed_commit"] == {
        "value": space_sha,
        "evidence_class": "ENV_DECLARATION",
    }
    assert v2["deployed_commit"]["evidence_class"] != "MEASURED"
    assert v2["alignment_state"] == v1["alignment_state"] == "UNKNOWN"
    assert v1["claims"]["github_parity"] == "NOT_CLAIMED"
    assert v2["claims"]["artifact_equivalence"] == "NOT_CLAIMED"


def test_missing_and_malformed_environment_stays_unknown(monkeypatch):
    missing = attestation.build_attestation_v2("SZLHOLDINGS/a11oy", {})
    assert missing["source_commit"] == {"value": None, "evidence_class": "UNKNOWN"}
    assert missing["deployed_commit"] == {"value": None, "evidence_class": "UNKNOWN"}
    assert missing["alignment_state"] == "UNKNOWN"

    for name in _BUILD_ENV:
        monkeypatch.setenv(name, "not-a-valid-build-fact")
    malformed = attestation.build_attestation_v2("SZLHOLDINGS/a11oy", {})
    assert malformed["source_commit"] == {"value": None, "evidence_class": "UNKNOWN"}
    assert malformed["deployed_commit"] == {"value": None, "evidence_class": "UNKNOWN"}
    assert malformed["alignment_state"] == "UNKNOWN"


def test_space_sha_is_not_misclassified_as_github_source(monkeypatch):
    monkeypatch.setenv("SPACE_COMMIT_SHA", "a" * 40)
    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", "a" * 40)

    result = attestation.build_attestation_v2("SZLHOLDINGS/a11oy", {})

    assert result["source_commit"] == {"value": None, "evidence_class": "UNKNOWN"}
    assert result["deployed_commit"] == {
        "value": "a" * 40,
        "evidence_class": "ENV_DECLARATION",
    }
    assert result["alignment_state"] == "UNKNOWN"


@pytest.mark.parametrize("attempted_label", ["MATCH", "CONFLICT", "VERIFIED"])
def test_caller_cannot_override_unknown(monkeypatch, attempted_label):
    sha = "b" * 40
    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", sha)
    source = {"repository": "szl-holdings/a11oy", "commit": sha}

    v2 = attestation.build_attestation_v2(
        "SZLHOLDINGS/a11oy", source, attempted_label, force=True
    )
    v1 = attestation.build_attestation(
        "SZLHOLDINGS/a11oy", source, attempted_label, force=True
    )

    assert v2["source_commit"] == {"value": sha, "evidence_class": "CALLER_DECLARED"}
    assert v1["source"]["state"] == "CALLER_DECLARED"
    assert v2["deployed_commit"]["value"] == sha
    assert v2["alignment_state"] == v1["alignment_state"] == "UNKNOWN"


@pytest.mark.parametrize("name", [
    "A11OY_SOURCE_COMMIT", "SZL_GIT_SHA", "GITHUB_SHA", "VERCEL_GIT_COMMIT_SHA",
])
def test_each_source_environment_sha_stays_an_environment_declaration(monkeypatch, name):
    monkeypatch.setenv(name, "7" * 40)
    result = attestation.build_attestation_v2(
        "SZLHOLDINGS/a11oy", {"commit": "8" * 40}
    )
    assert result["source_commit"] == {"value": "7" * 40, "evidence_class": "ENV_DECLARATION"}
    assert result["source_commit"]["evidence_class"] != "CALLER_DECLARED"
    assert result["source_commit"]["evidence_class"] != "MEASURED"


def test_caller_supplied_source_sha_is_not_an_environment_declaration():
    sha = "9" * 40
    v2 = attestation.build_attestation_v2("SZLHOLDINGS/a11oy", {"commit": sha})
    v1 = attestation.build_attestation("SZLHOLDINGS/a11oy", {"commit": sha})
    assert v2["source_commit"] == {"value": sha, "evidence_class": "CALLER_DECLARED"}
    assert v1["source"]["state"] == "CALLER_DECLARED"


def _evidence_classes(payload):
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "evidence_class" in node:
                found.append(node["evidence_class"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return found


@pytest.mark.parametrize(("name", "raw", "expected"), [
    ("A11OY_BUILD_DIGEST", "2" * 64, "sha256:" + "2" * 64),
    ("SZL_BUILD_DIGEST", "sha256:" + "4" * 64, "sha256:" + "4" * 64),
    ("A11OY_IMAGE_DIGEST", "5" * 64, "sha256:" + "5" * 64),
    ("CONTAINER_IMAGE_DIGEST", "sha256:" + "6" * 64, "sha256:" + "6" * 64),
])
def test_environment_digests_stay_declarations(monkeypatch, name, raw, expected):
    monkeypatch.setenv(name, raw)
    slot = "image_digest" if "IMAGE" in name else "build_digest"
    result = attestation.build_attestation_v2("SZLHOLDINGS/a11oy", {})
    assert result[slot] == {"value": expected, "evidence_class": "ENV_DECLARATION"}
    assert "MEASURED" not in _evidence_classes(result)


@pytest.mark.parametrize("name", ["A11OY_DEPLOYED_AT", "DEPLOYED_AT", "SZL_BUILD_TIME"])
def test_environment_timestamps_stay_declarations(monkeypatch, name):
    monkeypatch.setenv(name, "2026-07-16T20:30:00-04:00")
    result = attestation.build_attestation_v2("SZLHOLDINGS/a11oy", {})
    assert result["deploy_timestamp"] == {
        "value": "2026-07-17T00:30:00Z",
        "evidence_class": "ENV_DECLARATION",
    }
    assert "MEASURED" not in _evidence_classes(result)


def test_first_environment_name_wins_and_caller_build_facts_are_unread(monkeypatch):
    monkeypatch.setenv("A11OY_BUILD_DIGEST", "2" * 64)
    monkeypatch.setenv("SZL_BUILD_DIGEST", "9" * 64)
    caller = {
        "commit": "9" * 40,
        "build_digest": "sha256:" + "ab" * 32,
        "image_digest": "sha256:" + "cd" * 32,
        "deploy_timestamp": "2026-01-01T00:00:00Z",
        "timestamp": "2026-01-02T00:00:00Z",
    }
    result = attestation.build_attestation_v2("SZLHOLDINGS/a11oy", caller)
    assert result["build_digest"] == {
        "value": "sha256:" + "2" * 64,
        "evidence_class": "ENV_DECLARATION",
    }
    assert result["image_digest"] == {"value": None, "evidence_class": "UNKNOWN"}
    assert result["deploy_timestamp"] == {"value": None, "evidence_class": "UNKNOWN"}
    assert result["source_commit"] == {"value": "9" * 40, "evidence_class": "CALLER_DECLARED"}
    assert "MEASURED" not in _evidence_classes(result)
    limits = "\n".join(result["limits"])
    assert attestation.INDEPENDENT_ARTIFACT_OBSERVATION in limits
    assert attestation.HOST_REVISION_MEASUREMENT in limits
    assert "does not cover hf_revision" in limits
    assert "does not satisfy the observer gate" in limits


def test_local_digest_match_does_not_measure_the_binding_revision(tmp_path, monkeypatch):
    artifact = b"sibling-bytes"
    (tmp_path / "runtime.artifact").write_bytes(artifact)
    binding = tmp_path / "binding.json"
    binding.write_text(json.dumps({
        "schema": "szl.hf-runtime-binding/v1",
        "hf_revision": "a" * 40,
        "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "artifact_name": "runtime.artifact",
    }), encoding="utf-8")
    monkeypatch.setenv("A11OY_HF_RUNTIME_BINDING", str(binding))
    assert attestation.measure_hf_revision("SZLHOLDINGS/a11oy") == {
        "hf_revision": "a" * 40,
        "revision_state": "DECLARED_WITH_LOCAL_DIGEST",
        "measurement_method": "LOCAL_FILE_SHA256",
    }


def _binding(path, revision, digest):
    path.write_text(json.dumps({
        "schema": "szl.hf-runtime-binding/v1",
        "hf_revision": revision,
        "artifact_sha256": digest,
        "artifact_name": "runtime.artifact",
    }), encoding="utf-8")


def test_revision_only_tamper_stays_local_consistency(tmp_path, monkeypatch):
    artifact = b"sibling-bytes"
    digest = hashlib.sha256(artifact).hexdigest()
    (tmp_path / "runtime.artifact").write_bytes(artifact)
    binding = tmp_path / "binding.json"
    _binding(binding, "a" * 40, digest)
    monkeypatch.setenv("A11OY_HF_RUNTIME_BINDING", str(binding))

    matched = attestation.measure_hf_revision("SZLHOLDINGS/a11oy")
    assert matched["measurement_method"] == "LOCAL_FILE_SHA256"
    assert matched["revision_state"] == "DECLARED_WITH_LOCAL_DIGEST"

    _binding(binding, "b" * 40, digest)
    tampered = attestation.measure_hf_revision("SZLHOLDINGS/a11oy")
    assert tampered == {
        "hf_revision": "b" * 40,
        "revision_state": "DECLARED_WITH_LOCAL_DIGEST",
        "measurement_method": "LOCAL_FILE_SHA256",
    }
    assert tampered["revision_state"] != "MEASURED"
    assert tampered["measurement_method"] != attestation.HOST_REVISION_MEASUREMENT

    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", "b" * 40)
    agreed = attestation.measure_hf_revision("SZLHOLDINGS/a11oy")
    assert agreed == tampered

    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", "a" * 40)
    assert attestation.measure_hf_revision("SZLHOLDINGS/a11oy")["revision_state"] == "UNAVAILABLE"


def test_binding_symlink_and_digest_mismatch_stay_unavailable(tmp_path, monkeypatch):
    artifact = tmp_path / "runtime.artifact"
    artifact.write_bytes(b"real")
    binding = tmp_path / "binding.json"
    binding.write_text(json.dumps({
        "schema": "szl.hf-runtime-binding/v1",
        "hf_revision": "a" * 40,
        "artifact_sha256": hashlib.sha256(b"real").hexdigest(),
        "artifact_name": "runtime.artifact",
    }), encoding="utf-8")
    monkeypatch.setenv("A11OY_HF_RUNTIME_BINDING", str(binding))
    artifact.write_bytes(b"changed")
    assert attestation.measure_hf_revision("SZLHOLDINGS/a11oy")["revision_state"] == "UNAVAILABLE"
    artifact.write_bytes(b"real")
    link = tmp_path / "linked.artifact"
    try:
        os.symlink(artifact, link)
    except OSError:
        return
    binding.write_text(json.dumps({
        "schema": "szl.hf-runtime-binding/v1",
        "hf_revision": "a" * 40,
        "artifact_sha256": hashlib.sha256(b"real").hexdigest(),
        "artifact_name": "linked.artifact",
    }), encoding="utf-8")
    if hasattr(os, "O_NOFOLLOW") or os.path.islink(link):
        assert attestation.measure_hf_revision("SZLHOLDINGS/a11oy")["revision_state"] == "UNAVAILABLE"


def test_get_routes_are_frozen_unsigned_and_read_only(monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", "c" * 40)
    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", "c" * 40)
    app = FastAPI()
    registered = attestation.register(
        app, "SZLHOLDINGS/a11oy", {"repository": "szl-holdings/a11oy"}, "MATCH"
    )
    routes = (registered["route"], registered["route_v2"], registered["route_product"])
    assert all(
        next(route for route in app.router.routes if route.path == path).methods == {"GET"}
        for path in routes
    )

    # GET serves registration-time facts. It must neither refresh nor mint a receipt.
    monkeypatch.setenv("SZL_GIT_SHA", "d" * 40)
    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", "d" * 40)
    with TestClient(app) as client:
        for path in routes:
            first = client.get(path)
            second = client.get(path)
            assert first.status_code == second.status_code == 200
            assert first.content == second.content
            assert first.headers["cache-control"] == "no-store"
            assert client.post(path).status_code == 405

        v1 = client.get(registered["route"]).json()
        v2 = client.get(registered["route_v2"]).json()
        product = client.get(registered["route_product"]).json()

    assert v1["alignment_state"] == v2["alignment_state"] == "UNKNOWN"
    assert v2["source_commit"]["value"] == v2["deployed_commit"]["value"] == "c" * 40
    assert v2["source_commit"]["evidence_class"] == "ENV_DECLARATION"
    assert v1["source"]["state"] == "ENV_DECLARATION"
    assert v2["deployed_commit"]["evidence_class"] == "ENV_DECLARATION"
    assert v1["deployment"]["revision_state"] == "ENV_DECLARATION"
    assert v1["deployment"]["measurement_method"] == "PROCESS_ENVIRONMENT"
    assert v1["attestation_state"] == "UNSIGNED_STRUCTURAL"
    assert product["signer"] == "ABSENT"
    assert product["receipt_minted"] is False
    assert product["dsse"] is None


def test_space_repository_commit_is_an_environment_declaration(monkeypatch):
    present = "e" * 40
    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", present)
    measured = attestation.measure_hf_revision("SZLHOLDINGS/a11oy", force=True)
    assert measured == {
        "hf_revision": present,
        "revision_state": "ENV_DECLARATION",
        "measurement_method": "PROCESS_ENVIRONMENT",
    }
    v1 = attestation.build_attestation("SZLHOLDINGS/a11oy", {})
    assert v1["deployment"]["revision_state"] == "ENV_DECLARATION"
    assert v1["deployment"]["measurement_method"] == "PROCESS_ENVIRONMENT"

    monkeypatch.setenv("SPACE_REPOSITORY_COMMIT", "a" * 40)
    assert attestation.measure_hf_revision("SZLHOLDINGS/a11oy")["hf_revision"] == "a" * 40


def test_deployed_alias_is_not_measured_and_helper_ignores_it(monkeypatch):
    monkeypatch.setenv("A11OY_DEPLOYED_COMMIT", "f" * 40)
    v2 = attestation.build_attestation_v2("SZLHOLDINGS/a11oy", {})
    assert v2["deployed_commit"] == {
        "value": "f" * 40,
        "evidence_class": "ENV_DECLARATION",
    }
    assert v2["immutable_for_process"] is True
    assert attestation.measure_hf_revision("SZLHOLDINGS/a11oy") == {
        "hf_revision": None,
        "revision_state": "UNAVAILABLE",
        "measurement_method": "UNAVAILABLE",
    }


def test_missing_space_repository_commit_stays_unavailable():
    assert attestation.measure_hf_revision("SZLHOLDINGS/a11oy") == {
        "hf_revision": None,
        "revision_state": "UNAVAILABLE",
        "measurement_method": "UNAVAILABLE",
    }
