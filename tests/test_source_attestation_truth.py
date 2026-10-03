# SPDX-License-Identifier: Apache-2.0
"""Fail-closed source/Space attestation contract for separate Git histories."""

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

    assert v2["source_commit"] == {"value": source_sha, "evidence_class": "MEASURED"}
    assert v2["deployed_commit"] == {"value": space_sha, "evidence_class": "MEASURED"}
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
    assert result["deployed_commit"]["value"] == "a" * 40
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

    assert v2["source_commit"]["value"] == sha
    assert v2["deployed_commit"]["value"] == sha
    assert v2["alignment_state"] == v1["alignment_state"] == "UNKNOWN"


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
    assert v1["attestation_state"] == "UNSIGNED_STRUCTURAL"
    assert product["signer"] == "ABSENT"
    assert product["receipt_minted"] is False
    assert product["dsse"] is None
