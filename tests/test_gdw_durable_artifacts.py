#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Real retained GDW payload/receipt bindings, offline private object boundary."""

import hashlib
import json
from pathlib import Path
import sqlite3
import stat
import time
from datetime import datetime, timedelta, timezone

import pytest

import gdw_durable_runtime as durable
import gdw_runtime
import gdw_proofs
from tests.test_gdw_durable_runtime import stores
from tests.test_gdw_runtime import _queued_proof


def exported(stores):
    _queued_proof(stores.gdw)
    report = gdw_runtime.drain_once(limit=1, lease_seconds=30, worker_id="artifact-fixture", workspace=stores.gdw)
    assert report["exported"] == 1 and report["failed"] == 0
    with sqlite3.connect(stores.paths["gdw"]) as db:
        payload, artifact = db.execute("SELECT payload_json,artifact_json FROM effect_outbox WHERE status='EXPORTED'").fetchone()
    return json.loads(payload), json.loads(artifact)


def copy_database(stores, tmp_path):
    target = tmp_path / "candidate.sqlite3"
    with sqlite3.connect(stores.paths["gdw"]) as source, sqlite3.connect(target) as destination:
        source.backup(destination)
    return target


def test_hash_verified_reconstruction_preserves_database_and_logical_identity(stores):
    payload, artifact = exported(stores)
    logical = Path(artifact["path"])
    cache = stores.gate.artifacts
    physical = cache.resolve(logical)
    assert physical.is_relative_to(stores.directory) and physical != logical
    expected = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    assert hashlib.sha256(expected).hexdigest() == artifact["sha256"]
    before = stores.paths["gdw"].read_bytes()
    physical.unlink()
    report = cache.prepare(stores.paths["gdw"], time.monotonic() + 10)
    assert report == {"verified_count": 1, "reconstructed_count": 1,
                      "reconstruction": "RECONSTRUCTED_FROM_RETAINED_PAYLOAD"}
    assert physical.read_bytes() == expected
    assert stores.paths["gdw"].read_bytes() == before
    assert stores.gdw.integrity()["ok"] is True
    assert stores.artifact_publications[-1][0] == cache.object_path(logical, artifact["sha256"])


def test_native_export_satisfies_private_provider_ancestor_contract(stores):
    publish = stores.gate.artifacts.publish
    checked = []

    def private_provider(path, *args):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert path.stat().st_nlink == 1
        parent = path.parent
        while parent != stores.directory:
            assert stat.S_IMODE(parent.stat().st_mode) == 0o700
            assert parent.resolve() == parent
            parent = parent.parent
        checked.append(path)
        return publish(path, *args)

    stores.gate.artifacts.publish = private_provider
    exported(stores)
    assert checked
    assert not stores.gate.poisoned


@pytest.mark.parametrize("unsafe_owner", ["public_directory", "symlink"])
def test_managed_export_rejects_existing_unsafe_owner_without_repair(stores, unsafe_owner):
    identity = _queued_proof(stores.gdw)
    with sqlite3.connect(stores.paths["gdw"]) as db:
        payload = json.loads(db.execute("SELECT payload_json FROM effect_outbox").fetchone()[0])
    owner_scope = hashlib.sha256(stores.gdw.owner_id.encode()).hexdigest()[:32]
    parent = stores.gate.artifacts.directory / "proof_export"
    owner = parent / owner_scope
    if unsafe_owner == "public_directory":
        owner.mkdir(mode=0o755)
    else:
        target = stores.directory / "unadmitted-artifact-directory"
        target.mkdir(mode=0o700)
        owner.symlink_to(target, target_is_directory=True)
    with pytest.raises(durable.DurableStorageUnavailable):
        gdw_proofs.export_proof_payload(payload, artifact_id=identity, owner_id=stores.gdw.owner_id)
    assert not stores.artifact_publications
    assert not list(owner.glob("*.json"))
    if unsafe_owner == "public_directory":
        assert stat.S_IMODE(owner.stat().st_mode) == 0o755
    else:
        assert owner.is_symlink()


@pytest.mark.parametrize("field,value", [
    ("sha256", "0" * 64), ("size", 123), ("immutable", False),
    ("path", "/data/a11oy/gdw/proofs/../../secrets.json"),
    ("owner_scope", "0" * 32), ("artifact_identity", "0" * 64),
])
def test_unproven_artifact_identity_never_publishes(stores, tmp_path, field, value):
    _, artifact = exported(stores)
    candidate = copy_database(stores, tmp_path)
    artifact[field] = value
    with sqlite3.connect(candidate) as db:
        db.execute("UPDATE effect_outbox SET artifact_json=?", (json.dumps(artifact),))
    count = len(stores.artifact_publications)
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.gate.artifacts.prepare(candidate, time.monotonic() + 10)
    assert len(stores.artifact_publications) == count


@pytest.mark.parametrize("column,value", [
    ("payload_json", None), ("artifact_json", None), ("exported_at", None),
    ("payload_json", '{"payload_sha256":"a","payload_sha256":"b"}'),
    ("intent_sha256", "0" * 64), ("database_generation_id", "0" * 32),
])
def test_native_binding_and_lifecycle_failures_block_reconstruction(stores, tmp_path, column, value):
    exported(stores)
    candidate = copy_database(stores, tmp_path)
    with sqlite3.connect(candidate) as db:
        db.execute(f"UPDATE effect_outbox SET {column}=?", (value,))
    count = len(stores.artifact_publications)
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.gate.artifacts.prepare(candidate, time.monotonic() + 10)
    assert len(stores.artifact_publications) == count


def test_corrupt_cache_file_is_not_overwritten_or_claimed(stores):
    _, artifact = exported(stores)
    path = stores.gate.artifacts.resolve(Path(artifact["path"]))
    path.write_bytes(b"changed private cache")
    count = len(stores.artifact_publications)
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.gate.artifacts.prepare(stores.paths["gdw"], time.monotonic() + 10)
    assert path.read_bytes() == b"changed private cache"
    assert len(stores.artifact_publications) == count


@pytest.mark.parametrize("failure", ["timeout", "hash", "xet", "path"])
def test_artifact_failure_prevents_exported_snapshot_ack_and_poison_replay(stores, tmp_path, failure):
    _queued_proof(stores.gdw)
    original = stores.gate.artifacts.publish

    def fail(path, object_path, digest, deadline):
        if failure == "timeout":
            raise TimeoutError("uncertain private publication")
        value = original(path, object_path, digest, deadline)
        value[{"hash": "sha256", "xet": "xet_hash", "path": "path"}[failure]] = "invalid"
        return value

    stores.gate.artifacts.publish = fail
    with pytest.raises(durable.DurableStorageUnavailable):
        gdw_runtime.drain_once(limit=1, lease_seconds=30, worker_id="artifact-failure", workspace=stores.gdw)
    assert stores.gate.poisoned
    last_acknowledged = tmp_path / "last-acknowledged.sqlite3"
    last_acknowledged.write_bytes(stores.published[-1]["gdw"])
    with sqlite3.connect(last_acknowledged) as db:
        assert db.execute("SELECT status FROM effect_outbox").fetchone()[0] == "CLAIMED"
        assert db.execute("SELECT artifact_json FROM effect_outbox").fetchone()[0] is None
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.gdw.pending_proofs()
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.series.list_receipts()


def test_unadmitted_logical_prefix_cannot_escape_local_cache(stores):
    for path in (Path("/etc/passwd"), Path("/data/other/proof.json"),
                 Path("/data/a11oy/gdw/proofs/../receipts/invalid.json")):
        with pytest.raises(durable.DurableStorageUnavailable):
            stores.gate.artifacts.resolve(path)


def test_canonical_compacted_lifecycle_does_not_recreate_removed_payload(stores):
    exported(stores)
    result = stores.gdw.collect_garbage(now=datetime.now(timezone.utc) + timedelta(seconds=stores.gdw.retention_seconds + 1))
    assert result["effects_compacted"] == 1
    count = len(stores.artifact_publications)
    report = stores.gate.artifacts.prepare(stores.paths["gdw"], time.monotonic() + 10)
    assert report["verified_count"] == report["reconstructed_count"] == 0
    assert len(stores.artifact_publications) == count
    with sqlite3.connect(stores.paths["gdw"]) as db:
        assert db.execute("SELECT payload_json,artifact_json FROM effect_outbox").fetchone() == (None, None)


def test_all_retained_rows_are_checked_before_any_publication(stores, tmp_path):
    exported(stores)
    _queued_proof(stores.gdw, "second-request")
    assert gdw_runtime.drain_once(limit=1, lease_seconds=30, worker_id="second-worker", workspace=stores.gdw)["exported"] == 1
    candidate = copy_database(stores, tmp_path)
    with sqlite3.connect(candidate) as db:
        row = db.execute("SELECT rowid,artifact_json FROM effect_outbox ORDER BY rowid DESC LIMIT 1").fetchone()
        value = json.loads(row[1])
        value["sha256"] = "0" * 64
        db.execute("UPDATE effect_outbox SET artifact_json=? WHERE rowid=?", (json.dumps(value), row[0]))
    count = len(stores.artifact_publications)
    with pytest.raises(durable.DurableStorageUnavailable):
        stores.gate.artifacts.prepare(candidate, time.monotonic() + 10)
    assert len(stores.artifact_publications) == count


PRIVATE_DIAGNOSTIC_SENTINEL = "private-owner/payload?credential=do-not-disclose"


class _HostileArtifactError(RuntimeError):
    def __str__(self):
        raise AssertionError("private error was formatted")

    def __repr__(self):
        raise AssertionError("private error was represented")


@pytest.mark.parametrize("boundary", [
    "ARTIFACT_DATABASE_OPEN_UNAVAILABLE", "ARTIFACT_SCHEMA_VALIDATION_UNAVAILABLE",
    "ARTIFACT_ROW_READ_UNAVAILABLE", "ARTIFACT_ROW_VALIDATION_UNAVAILABLE",
    "ARTIFACT_CACHE_MATERIALIZATION_UNAVAILABLE", "ARTIFACT_NATIVE_BINDING_UNAVAILABLE",
    "ARTIFACT_PROVIDER_CALL_UNAVAILABLE", "ARTIFACT_PROVIDER_READBACK_UNAVAILABLE",
])
def test_artifact_diagnostic_uses_boundary_not_arbitrary_exception(boundary):
    from gdw_durable_artifacts import _preparation_diagnostic
    error = _HostileArtifactError(PRIVATE_DIAGNOSTIC_SENTINEL)
    assert _preparation_diagnostic(error, boundary) == boundary
    # Even a provider-supplied allowed-looking message is not validation evidence.
    assert _preparation_diagnostic(RuntimeError("ARTIFACT_RECONSTRUCTION_MISMATCH"), boundary) == boundary


def test_artifact_diagnostic_validation_codes_are_closed():
    from gdw_durable_artifacts import _preparation_diagnostic, _ArtifactValidationBlocked
    code = "ARTIFACT_RECONSTRUCTION_MISMATCH"
    assert _preparation_diagnostic(_ArtifactValidationBlocked(code), "ARTIFACT_ROW_VALIDATION_UNAVAILABLE") == code
    assert _preparation_diagnostic(_ArtifactValidationBlocked(PRIVATE_DIAGNOSTIC_SENTINEL), "invalid") == "ARTIFACT_PERSISTENCE_UNAVAILABLE"


@pytest.mark.parametrize("boundary", ["open", "schema", "materialize", "provider"])
def test_artifact_real_prepare_redacts_private_failures(stores, monkeypatch, boundary):
    import gdw_durable_artifacts as artifacts
    from gdw_workspace import GDWWorkspace
    exported(stores)
    cache = stores.gate.artifacts
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise _HostileArtifactError(PRIVATE_DIAGNOSTIC_SENTINEL)
    expected = {
        "open": "ARTIFACT_DATABASE_OPEN_UNAVAILABLE",
        "schema": "ARTIFACT_SCHEMA_VALIDATION_UNAVAILABLE",
        "materialize": "ARTIFACT_CACHE_MATERIALIZATION_UNAVAILABLE",
        "provider": "ARTIFACT_PROVIDER_CALL_UNAVAILABLE",
    }[boundary]
    # Undo fault injection before the real storage fixture tears down.
    with monkeypatch.context() as patch:
        if boundary == "open": patch.setattr(artifacts.sqlite3, "connect", fail)
        elif boundary == "schema": patch.setattr(GDWWorkspace, "_validate_schema", fail)
        elif boundary == "materialize": patch.setattr(cache, "_materialize", fail)
        else: patch.setattr(cache, "publish", fail)
        with pytest.raises(durable.DurableStorageUnavailable) as caught:
            cache.prepare(stores.paths["gdw"], time.monotonic() + 10)
        assert caught.value.args == (expected,)
        assert PRIVATE_DIAGNOSTIC_SENTINEL not in str(caught.value)
        assert caught.value.__suppress_context__ is True
    assert calls == [1]


def test_artifact_bad_readback_reports_fixed_code_without_retry(stores, monkeypatch):
    exported(stores)
    cache = stores.gate.artifacts
    calls = []
    def bad(*args):
        calls.append(1)
        return {"path": PRIVATE_DIAGNOSTIC_SENTINEL, "sha256": "0" * 64}
    monkeypatch.setattr(cache, "publish", bad)
    with pytest.raises(durable.DurableStorageUnavailable, match="^ARTIFACT_PUBLICATION_UNVERIFIED$"):
        cache.prepare(stores.paths["gdw"], time.monotonic() + 10)
    assert calls == [1]


def test_artifact_partial_publication_remains_failure_not_zero_effect_claim(stores, monkeypatch):
    exported(stores)
    _queued_proof(stores.gdw, "diagnostic-second-request")
    assert gdw_runtime.drain_once(limit=1, lease_seconds=30, worker_id="diagnostic-worker", workspace=stores.gdw)["exported"] == 1
    cache = stores.gate.artifacts
    original = cache.publish
    calls = []
    def partial(*args):
        calls.append(1)
        if len(calls) == 2: raise _HostileArtifactError(PRIVATE_DIAGNOSTIC_SENTINEL)
        return original(*args)
    monkeypatch.setattr(cache, "publish", partial)
    before = stores.paths["gdw"].read_bytes()
    with pytest.raises(durable.DurableStorageUnavailable, match="^ARTIFACT_PROVIDER_CALL_UNAVAILABLE$"):
        cache.prepare(stores.paths["gdw"], time.monotonic() + 10)
    assert calls == [1, 1]
    assert stores.paths["gdw"].read_bytes() == before
