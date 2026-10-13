#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Source identity remains bounded, immutable in routes, and distinct from signing."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_attest as attest
import szl_runtime_contracts as contracts


@pytest.fixture(autouse=True)
def isolated_build_sources(monkeypatch, tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    monkeypatch.setattr(attest, "ROOT", root)
    for name in contracts._ENV_SHA_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(attest.JOULE_METER_ENV, raising=False)
    return root


@pytest.mark.parametrize("name", ["A11OY_GIT_SHA", "SZL_GIT_SHA"])
def test_container_source_revision_needs_no_git_directory(monkeypatch, name):
    monkeypatch.setenv(name, "a" * 40)

    result = attest.build_commit()

    assert result["commit"] == "a" * 40
    assert result["source"] == "env:" + name
    assert "not an independently verified build attestation" in result["note"]


def test_source_precedence_matches_canonical_build_info(monkeypatch):
    monkeypatch.setenv("A11OY_GIT_SHA", "A" * 40)
    monkeypatch.setenv("SZL_GIT_SHA", "b" * 40)
    monkeypatch.setattr(contracts, "_safe_git", lambda _args: None)
    app = FastAPI()
    contracts.register(app)

    identity = TestClient(app).get("/api/build-info").json()["build"]
    observed = attest.build_commit()

    assert observed["commit"] == identity["revision"] == "a" * 40
    assert observed["source"] == identity["revision_source"] == "env:A11OY_GIT_SHA"


@pytest.mark.parametrize("value", [
    "c7c0ba17", "not-a-commit", "a" * 39, "a" * 41, "a" * 64,
    "a" * 40 + "\nother-value",
])
def test_malformed_or_non_sha1_runtime_identity_stays_null(monkeypatch, value):
    monkeypatch.setenv("SZL_GIT_SHA", value)

    result = attest.build_commit()

    assert result["commit"] is None
    assert value not in str(result)


@pytest.mark.parametrize("name", ["GITHUB_SHA", "SPACE_COMMIT_SHA", "SOURCE_VERSION"])
def test_generic_ci_or_space_revision_is_not_canonical_source(monkeypatch, name):
    monkeypatch.setenv(name, "a" * 40)

    assert attest.build_commit()["commit"] is None


def test_missing_build_identity_never_uses_locked_kernel_pin():
    result = attest.build_commit()

    assert result["commit"] is None
    assert attest.KERNEL_PIN not in str(result)


def _git_head(root, value):
    git = root / ".git"
    git.mkdir()
    (git / "HEAD").write_text(value + "\n", encoding="utf-8")
    return git


def test_local_detached_head_is_validated_and_labeled_as_checkout(isolated_build_sources):
    _git_head(isolated_build_sources, "A" * 40)

    result = attest.build_commit()

    assert result["commit"] == "a" * 40
    assert result["source"] == ".git/HEAD (detached)"
    assert "local checkout" in result["note"]


def test_local_loose_ref_is_a_full_commit(isolated_build_sources):
    git = _git_head(isolated_build_sources, "ref: refs/heads/main")
    branch = git / "refs/heads/main"
    branch.parent.mkdir(parents=True)
    branch.write_text("b" * 40 + "\n", encoding="utf-8")

    result = attest.build_commit()

    assert result["commit"] == "b" * 40
    assert result["source"] == ".git/refs/heads/main"


@pytest.mark.parametrize("value", ["c7c0ba17", "bad", "a" * 64, "a" * 40 + "\nextra"])
def test_invalid_loose_ref_cannot_fall_back_to_stale_packed_ref(
    isolated_build_sources, value,
):
    git = _git_head(isolated_build_sources, "ref: refs/heads/main")
    branch = git / "refs/heads/main"
    branch.parent.mkdir(parents=True)
    branch.write_text(value, encoding="utf-8")
    (git / "packed-refs").write_text("b" * 40 + " refs/heads/main\n", encoding="utf-8")

    assert attest.build_commit()["commit"] is None


@pytest.mark.parametrize("payload", [b"\xff", b"a" * 4097])
def test_unreadable_or_oversized_loose_ref_cannot_fall_back_to_stale_pack(
    isolated_build_sources, payload,
):
    git = _git_head(isolated_build_sources, "ref: refs/heads/main")
    branch = git / "refs/heads/main"
    branch.parent.mkdir(parents=True)
    branch.write_bytes(payload)
    (git / "packed-refs").write_text("b" * 40 + " refs/heads/main\n", encoding="utf-8")

    assert attest.build_commit()["commit"] is None


def test_packed_refs_require_exact_ref_and_full_commit(isolated_build_sources):
    git = _git_head(isolated_build_sources, "ref: refs/heads/main")
    (git / "packed-refs").write_text(
        "# pack-refs with: peeled\n" + "b" * 40 + " refs/heads/main-old\n"
        + "a" * 40 + " refs/heads/main\n" + "^" + "c" * 40 + "\n",
        encoding="utf-8",
    )

    result = attest.build_commit()

    assert result["commit"] == "a" * 40
    assert result["source"] == ".git/packed-refs"


def test_malformed_packed_commit_stays_null(isolated_build_sources):
    git = _git_head(isolated_build_sources, "ref: refs/heads/main")
    (git / "packed-refs").write_text("c7c0ba17 refs/heads/main\n", encoding="utf-8")

    assert attest.build_commit()["commit"] is None


@pytest.mark.parametrize("ref", [
    "../outside", "/tmp/outside", "refs/heads/../../outside",
    "refs/heads/../main", "refs//main", "refs/.hidden/main",
    "refs/heads/main.lock", "refs/heads/main\\other",
])
def test_unsafe_git_ref_is_rejected_before_ref_read(isolated_build_sources, monkeypatch, ref):
    _git_head(isolated_build_sources, "ref: " + ref)
    original = attest._read_git_metadata
    reads = []

    def observed_read(git, relative, limit=4096):
        reads.append(relative)
        return original(git, relative, limit)

    monkeypatch.setattr(attest, "_read_git_metadata", observed_read)

    assert attest.build_commit()["commit"] is None
    assert reads == ["HEAD"]


@pytest.mark.parametrize("location", ["HEAD", "refs/heads/main", "packed-refs"])
def test_git_metadata_symlink_cannot_read_outside_checkout(
    isolated_build_sources, tmp_path, location,
):
    outside = tmp_path / "outside"
    outside.write_text("a" * 40 + (" refs/heads/main" if location == "packed-refs" else ""),
                       encoding="utf-8")
    git = _git_head(isolated_build_sources, "ref: refs/heads/main")
    target = git / location
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    target.symlink_to(outside)

    assert attest.build_commit()["commit"] is None


def test_git_directory_cannot_escape_checkout(isolated_build_sources, tmp_path):
    outside = tmp_path / "outside-git"
    outside.mkdir()
    (outside / "HEAD").write_text("a" * 40, encoding="utf-8")
    (isolated_build_sources / ".git").symlink_to(outside, target_is_directory=True)

    assert attest.build_commit()["commit"] is None


def test_oversized_git_metadata_is_unavailable(isolated_build_sources):
    _git_head(isolated_build_sources, "a" * 4097)

    assert attest.build_commit()["commit"] is None


def _manifest(client):
    response = client.get("/api/a11oy/v1/attest/manifest")
    assert response.status_code == 200
    result = response.json()
    assert result["envelope"]["signed"] is False
    assert result["envelope"]["signatures"] == []
    assert result["verification"]["signature"]["status"] == "UNSIGNED-READ-ONLY"
    assert result["rekor"]["attempted"] is False
    assert result["lake"] == {"appended": False, "status": "READ_ONLY"}
    return result["statement"]["predicate"]["provenance"]["build_commit"]


def test_routes_prefer_runtime_snapshot_and_reads_never_refresh_or_sign(monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    monkeypatch.setattr(contracts, "_safe_git", lambda _args: None)
    app = FastAPI()
    attest.register(app)
    monkeypatch.setenv("SZL_GIT_SHA", "b" * 40)
    contracts.register(app)
    monkeypatch.setenv("SZL_GIT_SHA", "c" * 40)

    def forbidden(*args, **kwargs):
        raise AssertionError("a read cannot refresh build metadata, sign, submit, or append")

    for name in ("build_commit", "sign_statement", "rekor_submit", "lake_receipt"):
        monkeypatch.setattr(attest, name, forbidden)
    monkeypatch.setattr(contracts, "_safe_git", forbidden)
    monkeypatch.setattr(contracts, "_safe_env_sha", forbidden)
    client = TestClient(app)

    first = _manifest(client)
    second = _manifest(client)
    canonical = client.get("/api/build-info").json()["build"]

    assert first == second
    assert first["commit"] == canonical["revision"] == "b" * 40
    assert first["source"] == canonical["revision_source"] == "env:SZL_GIT_SHA"
    assert client.get("/api/a11oy/v1/attest/verify").json()["ok"] is True


def test_unavailable_runtime_provider_cannot_use_standalone_fallback(monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    monkeypatch.setattr(contracts, "_safe_git", lambda _args: None)
    app = FastAPI()
    attest.register(app)
    monkeypatch.delenv("SZL_GIT_SHA")
    contracts.register(app)
    monkeypatch.setenv("SZL_GIT_SHA", "b" * 40)
    client = TestClient(app)

    assert client.get("/api/build-info").status_code == 503
    assert _manifest(client)["commit"] is None


@pytest.mark.parametrize("identity", [
    None, {},
    {"state": "UNKNOWN", "revision": "a" * 40, "revision_source": "env:SZL_GIT_SHA"},
    {"state": "OBSERVED", "revision": "c7c0ba17", "revision_source": "env:SZL_GIT_SHA"},
    {"state": "OBSERVED", "revision": "a" * 64, "revision_source": "env:SZL_GIT_SHA"},
    {"state": "OBSERVED", "revision": "a" * 40, "revision_source": "env:GITHUB_SHA"},
])
def test_invalid_registered_provider_never_falls_back(monkeypatch, identity):
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    attest.register(app)
    app.state.szl_build_identity_reader = lambda: identity

    assert _manifest(TestClient(app))["commit"] is None


def test_failed_registered_provider_never_falls_back(monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    attest.register(app)

    def unavailable():
        raise OSError("metadata unavailable")

    app.state.szl_build_identity_reader = unavailable

    assert _manifest(TestClient(app))["commit"] is None


def test_standalone_route_uses_its_frozen_observation(monkeypatch):
    monkeypatch.setenv("SZL_GIT_SHA", "a" * 40)
    app = FastAPI()
    attest.register(app)
    monkeypatch.setenv("SZL_GIT_SHA", "b" * 40)

    assert _manifest(TestClient(app))["commit"] == "a" * 40
