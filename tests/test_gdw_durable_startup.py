#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic metadata controls; no test record is an operational admission."""

import copy
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

import gdw_durable_startup as startup
import gdw_durable_source as source
import gdw_durable_guard as guard
import gdw_durable_image as image
from tests.test_gdw_durable_source import manifest as source_manifest, install_image
from tests.test_gdw_durable_guard import fixture as guard_fixture


def workflow():
    return {"repository": startup.REPOSITORY, "ref": "refs/heads/main", "revision": "b" * 40,
            "workflow_path": startup.WORKFLOW, "run_id": 123, "run_attempt": 1, "job_id": 456,
            "event_name": "workflow_dispatch", "source_admission_state": "VERIFIED",
            "source_admission_sha256": "c" * 64}


def snapshot(label):
    value = {"path": f"{startup.OBJECT_PREFIX}/{'a' * 32}/{label}-{'d' * 64}.sqlite3",
            "size": 4096, "sha256": "d" * 64, "xet_hash": "e" * 64,
            "generation": "f" * 32 if label == "gdw" else "store_" + "f" * 32,
            "receipt_count": 2, "receipt_sequence": 0 if label == "gdw" else 2,
            "receipt_head_sha256": "a" * 64}
    if label == "series_a":
        value["receipt_rows_sha256"] = "7" * 64
    return value


def bind_base_observation(record):
    """Synthetic fixture only; this never represents an actual Python 3.14 probe."""
    record["runtime"]["base_observation"] = {
        "schema": image.SCHEMA, "state": "OBSERVED", "repository": image.REPOSITORY,
        "source_revision": record["source"]["revision"],
        "dockerfile_sha256": record["runtime"]["source_manifest"]["dockerfile"]["sha256"],
        "scope": "PINNED_BASE_STDLIB_ONLY", "final_runtime": "FINAL_RUNTIME_NOT_OBSERVED",
        "execution": {"runner": "GITHUB_ACTIONS_CANONICAL_MAIN", "run_id": record["source"]["run_id"],
                      "run_attempt": record["source"]["run_attempt"]},
        "base": {"reference": image.BASE_REFERENCE, "platform": image.PLATFORM,
                 "manifest_sha256": "1" * 64, "config_sha256": "2" * 64},
        "interpreter": {"implementation": "cpython", "version": [3, 14, 0],
                        "executable": image.EXECUTABLE, "isolation": "ISOLATED_NO_SITE_NO_BYTECODE",
                        "native_platform": image.PLATFORM},
        "sqlite": {"python_version": record["runtime"]["sqlite_version"],
                   "sql_version": record["runtime"]["sqlite_version"],
                   "source_id": "2026-01-01 00:00:00 " + "3" * 64,
                   "compile_options_count": 1, "compile_options_sha256": "4" * 64},
        "requirements": dict(image.REQUIREMENTS),
    }
    return record


def admission():
    empty = hashlib.sha256(startup.canonical([])).hexdigest()
    legacy, _observed = guard_fixture()
    legacy["observation"]["observed_at"] = "2026-10-04T17:00:00Z"
    record = {
        "schema": startup.SCHEMA, "state": "QUALIFIED_CAPTURED_STATE_FOR_PRIVATE_DATASET_STORAGE",
        "created_at": "2026-10-04T18:00:00Z", "space": startup.SPACE, "dataset": startup.DATASET,
        "bucket": startup.BUCKET, "source": workflow(),
        "capture": {"capture_id": f"123-1-{'b' * 40}-{'a' * 32}", "source_revision": "b" * 40,
                    "run_id": 123, "run_attempt": 1, "report_sha256": "c" * 64,
                    "manifest_sha256": "d" * 64, "manifest_xet_hash": "e" * 64},
        "qualification": {"schema": "szl.gdw-store-recovery-qualification/v1", "state": "LOGICAL_CONTINUITY_VERIFIED",
            "report_sha256": "f" * 64, "source": workflow(), "artifact_id": 789,
            "artifact_archive_sha256": "a" * 64, "capture_report_sha256": "c" * 64,
            "historical_anchor_state": "VERIFIED", "historical_anchor_sha256": "b" * 64,
            "all_declared_stored_values_unchanged": True, "receipt_bytes_unchanged": True,
            "database_generations_unchanged": True, "later_acknowledged_writes_state": "NOT_ESTABLISHED",
            "logical_fingerprint_sha256": {label: "c" * 64 for label in startup._LABELS},
            "candidates": {label: {"sha256": "d" * 64, "size": 4096, "method": "SQLITE_NATIVE_BACKUP",
                                    "integrity": "OK", "foreign_key_violations": 0} for label in startup._LABELS}},
        "legacy_quiescence": {"state": "ALL_LEGACY_WRITERS_VERIFIED_STOPPED_SPACE_PAUSED", "space_revision": guard.SPACE_REVISION,
            "observed_at": "2026-10-04T17:00:00Z", "source_revision": "b" * 40,
            "writer_inventory_sha256": "a" * 64, "observation_sha256": "b" * 64},
        "legacy_guard": legacy,
        "provider": {"endpoint": "https://huggingface.co", "dataset_private": True, "bucket_private": True,
                     "resource_group_observation_sha256": "d" * 64, "audience_equivalence": "NOT_ESTABLISHED"},
        "runtime": {"sdk_version": "1.31.0", "sqlite_version": sqlite3.sqlite_version,
                    "source_manifest": source_manifest(),
                    "source_manifest_sha256": hashlib.sha256(source.canonical(source_manifest())).hexdigest()},
        "snapshots": {label: snapshot(label) for label in startup._LABELS},
        "retained_artifacts": {"state": "ALL_RETAINED_OBJECTS_READBACK_VERIFIED", "count": 0, "total_bytes": 0,
            "identities_sha256": empty, "native_bindings_state": "VERIFIED",
            "reconstruction": "RECONSTRUCTED_FROM_RETAINED_PAYLOAD"},
        "latency": {"scope": "CANONICAL_ACQUISITION_FULL_PAIR_AND_ARTIFACT_UPLOAD_READBACK_RESTORE",
            "runner": "GITHUB_ACTIONS_CANONICAL_MAIN", "run_id": 123, "run_attempt": 1,
            "sample_count": 1, "samples_ms": [1250], "snapshot_sha256": {label: "d" * 64 for label in startup._LABELS},
            "artifact_identities_sha256": empty, "receipt_sha256": "b" * 64,
            "runtime_self_check": "REQUIRED_BEFORE_INSTALL_ON_ACTUAL_HOST", "ack_deadline_ms": 60000,
            "throughput_claim": "NOT_CLAIMED"},
    }
    return bind_base_observation(record)


def test_parser_is_detached_canonical_metadata_without_io(monkeypatch):
    value = admission()
    encoded = startup.canonical(value)
    monkeypatch.setattr(Path, "open", lambda *_a, **_k: pytest.fail("schema parser performed I/O"))
    result = startup.parse_admission(encoded)
    value["source"]["revision"] = "0" * 40
    assert result["source"]["revision"] == "b" * 40
    assert startup.canonical(result) == encoded


@pytest.mark.parametrize("path,value", [
    (("source_revision",), "a" * 40), (("dockerfile_sha256",), "a" * 64),
    (("execution", "run_id"), 124), (("execution", "run_attempt"), 2),
    (("scope",), "FINAL_RUNTIME"), (("final_runtime",), "OBSERVED"),
    (("interpreter", "version"), [3, 14, 1]),
    (("requirements", "sqlite_equality"), "LEARN_FROM_HOST"),
])
def test_base_observation_must_bind_exact_source_run_scope_and_legacy_interpreter(path, value):
    record = admission()
    target = record["runtime"]["base_observation"]
    for key in path[:-1]: target = target[key]
    target[path[-1]] = value
    with pytest.raises(startup.AdmissionBlocked): startup.parse_admission(startup.canonical(record))


def test_sqlite_expected_value_cannot_be_detached_from_base_or_learned_from_host(tmp_path, monkeypatch):
    record = admission()
    record["runtime"]["sqlite_version"] = "3.0.0"
    with pytest.raises(startup.AdmissionBlocked): startup.parse_admission(startup.canonical(record))
    bind_base_observation(record)
    startup.parse_admission(startup.canonical(record))
    monkeypatch.setattr(source, "verify_installed_source", lambda *_a, **_k: pytest.fail("read source after version mismatch"))
    with pytest.raises(startup.AdmissionBlocked): startup.verify_runtime(record, tmp_path, "b" * 40, "1.31.0")


@pytest.mark.parametrize("path,value", [
    (("state",), "LOGICAL_CONTINUITY_VERIFIED"),
    (("qualification", "state"), "BLOCKED"),
    (("qualification", "historical_anchor_state"), "UNQUALIFIED"),
    (("qualification", "receipt_bytes_unchanged"), 1),
    (("qualification", "capture_report_sha256"), "d" * 64),
    (("capture", "capture_id"), f"124-1-{'b' * 40}-{'a' * 32}"),
    (("source", "ref"), "refs/pull/1/merge"),
    (("source", "revision"), "0" * 40),
    (("source", "event_name"), "pull_request"),
    (("source", "source_admission_state"), "UNKNOWN"),
    (("legacy_quiescence", "state"), "RUNNING"),
    (("legacy_quiescence", "source_revision"), "a" * 40),
    (("provider", "dataset_private"), False),
    (("provider", "resource_group_observation_sha256"), "0" * 64),
    (("runtime", "sdk_version"), "1.23.0"),
    (("retained_artifacts", "state"), "NOT_CAPTURED"),
    (("retained_artifacts", "identities_sha256"), "a" * 64),
    (("latency", "sample_count"), 0),
    (("latency", "samples_ms"), [True]),
    (("latency", "snapshot_sha256", "gdw"), "a" * 64),
    (("latency", "runtime_self_check"), "SKIP"),
    (("latency", "throughput_claim"), "MEASURED"),
    (("snapshots", "series_a", "receipt_sequence"), 1),
    (("snapshots", "series_a", "receipt_rows_sha256"), "0" * 64),
    (("snapshots", "gdw", "generation"), "0" * 32),
])
def test_unqualified_admission_fact_rejected(path, value):
    record = admission()
    target = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(startup.AdmissionBlocked):
        startup.parse_admission(startup.canonical(record))


@pytest.mark.parametrize("change", ["unknown", "missing", "pretty", "duplicate", "nonfinite", "oversized"])
def test_loose_json_and_field_admission_rejected(change):
    record = admission()
    if change == "unknown": record["admitted"] = True
    if change == "missing": del record["runtime"]["source_manifest"]["absent_modules"]
    data = startup.canonical(record)
    if change == "pretty": data = json.dumps(record, indent=2).encode()
    if change == "duplicate": data = data[:-2] + b',"schema":"duplicate"}\n'
    if change == "nonfinite": data = data.replace(b'1250', b'NaN')
    if change == "oversized": data = b' ' * (startup.MAX_ADMISSION_BYTES + 1)
    with pytest.raises(startup.AdmissionBlocked): startup.parse_admission(data)


def test_series_row_prefix_identity_cannot_be_omitted_from_admission():
    record = admission()
    del record["snapshots"]["series_a"]["receipt_rows_sha256"]
    with pytest.raises(startup.AdmissionBlocked):
        startup.parse_admission(startup.canonical(record))


def test_initial_bootstrap_is_bound_to_admission_candidate_and_source():
    record = admission()
    manifest = {"kind": "BOOTSTRAP", "epoch": 0, "sequence": 0, "source_revision": record["source"]["revision"],
                "qualification_sha256": hashlib.sha256(startup.canonical(record)).hexdigest(),
                "snapshots": record["snapshots"], "space": startup.SPACE, "dataset": startup.DATASET, "bucket": startup.BUCKET}
    startup.validate_bootstrap_binding(record, manifest)
    for field, value in (("kind", "CLAIM"), ("source_revision", "a" * 40), ("qualification_sha256", "a" * 64)):
        bad = copy.deepcopy(manifest); bad[field] = value
        with pytest.raises(startup.AdmissionBlocked): startup.validate_bootstrap_binding(record, bad)
    bad = copy.deepcopy(manifest); bad["snapshots"]["gdw"]["sha256"] = "a" * 64
    with pytest.raises(startup.AdmissionBlocked): startup.validate_bootstrap_binding(record, bad)


def test_actual_source_bytes_and_exact_first_cutover_revision_are_required(tmp_path, monkeypatch):
    record = admission()
    record["runtime"]["source_manifest"], app, inputs = install_image(tmp_path)
    record["runtime"]["source_manifest_sha256"] = hashlib.sha256(source.canonical(record["runtime"]["source_manifest"])).hexdigest()
    bind_base_observation(record)
    monkeypatch.setattr(source, "RUNTIME_INSTALL_ROOT", inputs)
    startup.verify_runtime(record, app, "b" * 40, "1.31.0")
    with pytest.raises(startup.AdmissionBlocked):
        startup.verify_runtime(record, app, "e" * 40, "1.31.0")
    (app / "serve.py").write_bytes(b"changed deployed source")
    with pytest.raises(startup.AdmissionBlocked, match="RUNTIME_INSTALLED_SOURCE_UNQUALIFIED"):
        startup.verify_runtime(record, app, "b" * 40, "1.31.0")


@pytest.fixture
def native_startup(tmp_path, monkeypatch):
    """Actual stores/protocol/coordinator; only provider/installed-key edges are synthetic."""
    import os
    import sys
    import time
    from types import SimpleNamespace
    import gdw_durable_runtime as durable
    import gdw_durable_storage as storage
    from gdw_workspace import GDWWorkspace
    from routers.series_a_control_plane import Store, ReceiptSigner
    from tests.test_gdw_durable_storage import ObjectAPI, InitialBackend
    from tests.test_gdw_runtime import _queued_proof

    monkeypatch.delenv("GDW_DURABLE_STORAGE", raising=False)
    monkeypatch.setattr(durable, "_GATE", None)
    monkeypatch.setattr(startup, "_STARTED", False)
    monkeypatch.setattr(startup, "_PARENT_LOCK_FD", None)
    monkeypatch.setattr(startup, "LOCAL_PARENT", tmp_path / "live")
    for key in ("GDW_REQUIRED_MOUNT", "A11OY_SERIES_A_REQUIRE_MOUNT", "GDW_PROOF_DIR", "GDW_RECEIPT_PROJECTION_DIR"):
        monkeypatch.delenv(key, raising=False)
    for key, value in (("GDW_SQLITE_JOURNAL", "DELETE"), ("GDW_SQLITE_SYNCHRONOUS", "FULL"),
                       ("A11OY_SERIES_A_SQLITE_JOURNAL", "DELETE"), ("SZL_GIT_SHA", "b" * 40),
                       ("GDW_NAMESPACE", "a11oy"), ("GDW_SERVICE_OWNER_ID", "owner")):
        monkeypatch.setenv(key, value)
    seed = tmp_path / "seed"; seed.mkdir(mode=0o700)
    paths = {label: seed / (label + ".sqlite3") for label in startup._LABELS}
    gdw = GDWWorkspace(str(paths["gdw"]), namespace="a11oy", owner_id="owner")
    _queued_proof(gdw)
    series = Store(str(paths["series_a"]))
    series.append_event("preserved", {"value": "offline native fixture"})
    signer = ReceiptSigner.__new__(ReceiptSigner)
    signer.private_key, signer.public_pem, signer.source, signer.error = None, "", "unavailable", "offline fixture"
    series.append_receipt("offline.anchor", {"retained": True}, signer)
    for path in paths.values(): path.chmod(0o600)
    stage = seed / "provider"; stage.mkdir(mode=0o700)
    api = ObjectAPI(); raw = storage.HFPrivateObjectStore(api, stage, seed)
    generation = {label: storage.inspect_snapshot(label, path, seed, time.monotonic() + 10)["generation"]
                  for label, path in paths.items()}
    snapshots = raw.publish_snapshots(paths, generation, time.monotonic() + 10)
    record = admission(); record["snapshots"] = snapshots
    for label in startup._LABELS:
        record["qualification"]["candidates"][label].update(sha256=snapshots[label]["sha256"], size=snapshots[label]["size"])
        record["latency"]["snapshot_sha256"][label] = snapshots[label]["sha256"]
    source_root = Path(startup.__file__).resolve().parent
    # A synthetic installed image exercises real descriptor verification without
    # pretending that this local pytest checkout is a deployed Docker payload.
    record["runtime"]["source_manifest"], image_root, image_inputs = install_image(
        tmp_path / "image", contents={name: (source_root / name).read_bytes() for name in source.REQUIRED_FILES})
    record["runtime"]["source_manifest_sha256"] = hashlib.sha256(source.canonical(record["runtime"]["source_manifest"])).hexdigest()
    bind_base_observation(record)
    monkeypatch.setattr(startup, "RUNTIME_SOURCE_ROOT", image_root)
    monkeypatch.setattr(source, "RUNTIME_INSTALL_ROOT", image_inputs)
    encoded = startup.canonical(record)
    manifest = {"schema": storage.SCHEMA, "space": storage.SPACE, "dataset": storage.DATASET,
                "bucket": storage.BUCKET, "operation_id": "a" * 32, "writer_id": "0" * 32,
                "epoch": 0, "sequence": 0, "kind": "BOOTSTRAP", "previous_manifest_sha256": None,
                "source_revision": "b" * 40, "qualification_sha256": hashlib.sha256(encoded).hexdigest(),
                "snapshots": snapshots}
    backend = InitialBackend()
    storage.bootstrap(backend, manifest, encoded, time.monotonic() + 10)
    events = []
    state = SimpleNamespace(record=record, encoded=encoded, backend=backend, api=api, events=events,
                            seed_paths=paths, seed_bytes={label: path.read_bytes() for label, path in paths.items()},
                            generation=generation, raw=raw, series=series, signer=signer,
                            source_root=image_root, source_inputs=image_inputs)

    def loaded(directory, deadline):
        events.append("read_admission")
        return backend.head, state.encoded, state.record["provider"]["resource_group_observation_sha256"]

    def worker(message, directory, deadline):
        operation, arguments = message["operation"], message["arguments"]
        events.append(operation)
        if getattr(state, "fail_publish", False) and operation == "publish_snapshots":
            raise TimeoutError("offline provider outcome unknown")
        staging = directory / ("provider-" + str(len(events))); staging.mkdir(mode=0o700)
        provider = storage.HFPrivateObjectStore(api, staging, directory)
        if operation == "restore_snapshots":
            return provider.restore_snapshots(arguments["snapshots"],
                {label: Path(path) for label, path in arguments["destinations"].items()}, deadline)
        if operation == "publish_snapshots":
            return provider.publish_snapshots({label: Path(path) for label, path in arguments["paths"].items()},
                arguments["generations"], deadline, previous_snapshots=arguments["previous_snapshots"])
        if operation == "publish_artifact":
            return provider.publish_artifact(Path(arguments["local_path"]), arguments["object_path"], arguments["sha256"], deadline)
        raise AssertionError("unexpected provider operation")

    monkeypatch.setattr(storage, "load_admitted_head", loaded)
    monkeypatch.setattr(storage, "WorkerFenceBackend", lambda *_a: backend)
    monkeypatch.setattr(storage, "_worker_call", worker)
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(__version__="1.31.0"))
    monkeypatch.setattr(startup, "verify_installed_credentials", lambda _root: events.append("installed_authority"))
    original_claim = storage.Writer.claim

    def claim(self, *args):
        events.append("claim")
        return original_claim(self, *args)

    monkeypatch.setattr(storage.Writer, "claim", claim)
    monkeypatch.setenv("GDW_DURABLE_STORAGE", durable.MODE)
    monkeypatch.setenv("GDW_PROOF_EXPORT_MODE", guard.EXPORT_GUARD)
    yield state
    startup.close()
    durable._GATE = None


def test_native_coordinator_verifies_restores_claims_and_times_before_install(native_startup):
    import os
    import gdw_durable_runtime as durable
    from gdw_workspace import GDWWorkspace
    from routers.series_a_control_plane import Store
    state = native_startup
    report = startup.activate()
    assert state.events[:4] == ["read_admission", "installed_authority", "restore_snapshots", "claim"]
    assert "publish_snapshots" in state.events[4:]
    assert report["state"] == "RESTORED_AND_ACKNOWLEDGED"
    assert report["admission_sha256"] == hashlib.sha256(state.encoded).hexdigest()
    assert report["qualification_sha256"] == state.record["qualification"]["report_sha256"]
    assert report["admission_sha256"] != report["qualification_sha256"]
    assert os.environ["GDW_PROOF_EXPORT_MODE"] == "outbox"
    assert 1 <= report["actual_host_full_state_ack_ms"] <= 60000
    assert durable._GATE.writer.head.value["kind"] == "COMMIT"
    assert durable._GATE.writer.head.value["epoch"] == 1
    witness = durable._GATE.managed_status()
    assert witness["dataset_revision"] == durable._GATE.writer.head.revision
    assert witness["operation_id"] == durable._GATE.writer.head.value["operation_id"]
    assert witness["generations"] == state.generation
    assert witness["admission_sha256"] == report["admission_sha256"]
    assert witness["qualification_sha256"] == report["qualification_sha256"]
    assert {label: path.read_bytes() for label, path in state.seed_paths.items()} == state.seed_bytes
    series = Store(str(durable._GATE.paths["series_a"]))
    gdw = GDWWorkspace(str(durable._GATE.paths["gdw"]), namespace="a11oy", owner_id="owner")
    assert series.events_since(0)[0]["kind"] == "preserved"
    assert gdw.database_generation_id == state.generation["gdw"]
    from gdw_runtime import drain_once
    assert drain_once(limit=1, lease_seconds=30, worker_id="after-startup", workspace=gdw)["exported"] == 1
    assert not durable._GATE.poisoned


@pytest.mark.parametrize("value", [None, "outbox", "", "other"])
def test_missing_provider_guard_fails_before_any_provider_read(native_startup, monkeypatch, value):
    import gdw_durable_runtime as durable
    if value is None:
        monkeypatch.delenv("GDW_PROOF_EXPORT_MODE", raising=False)
    else:
        monkeypatch.setenv("GDW_PROOF_EXPORT_MODE", value)
    with pytest.raises(startup.AdmissionBlocked):
        startup.activate()
    assert native_startup.events == []
    assert durable._GATE is None
    assert native_startup.backend.head.value["kind"] == "BOOTSTRAP"


def test_actual_health_projection_is_consumed_by_immutable_managed_proof(native_startup, monkeypatch):
    import time
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import gdw_runtime
    import gdw_durable_runtime as durable
    from scripts import prove_hf_gdw_runtime as proof
    from scripts.configure_hf_gdw_runtime import ManagedProofContext
    from routers import gdw_frontier
    state = native_startup
    startup.activate()
    gdw_runtime.prepare_runtime()
    app = FastAPI()
    gdw_frontier.register(app)
    context = ManagedProofContext(state.record, hashlib.sha256(state.encoded).hexdigest(),
        state.backend, deadline=time.monotonic() + 20)
    monkeypatch.setattr(proof, "_MANAGED_CONTEXT", context)
    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/gdw/healthz")
        assert response.status_code == 200
        witness = proof._managed_health(response.json())
    assert witness == durable._GATE.managed_status()
    assert witness["dataset_revision"] == state.backend.head.revision
    projected = response.json()["persistence"]["storage"]
    assert "workspace_path" not in projected
    malicious = gdw_runtime.runtime_health()
    malicious["storage"]["managed_admission"]["private_payload"] = "must not project"
    assert "managed_admission" not in gdw_frontier._public_runtime_health(malicious)["storage"]


@pytest.mark.parametrize("defect", ["source", "record_digest", "credentials", "snapshot", "critical_bytes"])
def test_unqualified_startup_never_claims_or_installs(native_startup, monkeypatch, defect):
    import gdw_durable_runtime as durable
    import gdw_durable_storage as storage
    state = native_startup
    if defect == "source": monkeypatch.setenv("SZL_GIT_SHA", "c" * 40)
    if defect == "record_digest": state.encoded = state.encoded.replace(b'1250', b'1251')
    if defect == "credentials":
        monkeypatch.setattr(startup, "verify_installed_credentials", lambda _r: (_ for _ in ()).throw(startup.AdmissionBlocked("TEST_UNAVAILABLE")))
    if defect == "snapshot":
        state.api.objects.pop(state.record["snapshots"]["gdw"]["path"])
    if defect == "critical_bytes":
        # Change the claimed hash in the immutable record, preserving its own
        # digest; installed source equality must independently reject it.
        next(item for item in state.record["runtime"]["source_manifest"]["installed_files"]
             if item["path"] == "gdw_runtime.py")["sha256"] = "f" * 64
        state.record["runtime"]["source_manifest_sha256"] = hashlib.sha256(
            source.canonical(state.record["runtime"]["source_manifest"])).hexdigest()
        state.encoded = startup.canonical(state.record)
        body = state.backend.head.value
        body["qualification_sha256"] = hashlib.sha256(state.encoded).hexdigest()
        state.backend.head = storage.Head(state.backend.head.revision, storage.canonical(body))
    with pytest.raises(startup.AdmissionBlocked): startup.activate()
    assert "claim" not in state.events
    assert durable._GATE is None and startup._PARENT_LOCK_FD is None
    assert state.backend.head.value["kind"] == "BOOTSTRAP"


def test_actual_host_uncertain_roundtrip_never_installs_or_retries(native_startup):
    import gdw_durable_runtime as durable
    state = native_startup
    state.fail_publish = True
    with pytest.raises(startup.AdmissionBlocked): startup.activate()
    assert state.events.count("claim") == 1
    assert state.events.count("publish_snapshots") == 1
    assert state.backend.head.value["kind"] == "CLAIM"
    assert durable._GATE is None and startup._PARENT_LOCK_FD is None
    with pytest.raises(startup.AdmissionBlocked, match="ALREADY_ATTEMPTED"):
        startup.activate()


def test_missing_first_head_cannot_trigger_runtime_bootstrap(native_startup, monkeypatch):
    import gdw_durable_storage as storage
    import gdw_durable_runtime as durable
    monkeypatch.setattr(storage, "load_admitted_head", lambda *_a: (_ for _ in ()).throw(storage.StorageBlocked("HEAD_UNAVAILABLE")))
    previous = len(native_startup.backend.submissions)
    with pytest.raises(startup.AdmissionBlocked): startup.activate()
    assert len(native_startup.backend.submissions) == previous
    assert durable._GATE is None


def test_canonical_entrypoint_orders_coordinator_before_all_runtime_work(monkeypatch):
    import gdw_runtime
    from types import SimpleNamespace
    events = []
    monkeypatch.setattr(gdw_runtime.durable_storage, "enabled", lambda: True)
    monkeypatch.setattr(startup, "activate", lambda: events.append("admit_restore_claim_ack"))
    monkeypatch.setattr(startup, "close", lambda: events.append("close_storage"))
    monkeypatch.setattr(gdw_runtime, "prepare_runtime", lambda: events.append("prepare"))
    supervisor = SimpleNamespace(start=lambda: events.append("start_supervisor"), stop=lambda: events.append("stop_supervisor"))
    monkeypatch.setattr(gdw_runtime.OutboxSupervisor, "from_environment", lambda: supervisor)
    monkeypatch.setattr(gdw_runtime.runpy, "run_path", lambda *_a, **_k: events.append("import_serve"))
    assert gdw_runtime.main() == 0
    assert events == ["admit_restore_claim_ack", "prepare", "start_supervisor", "import_serve", "stop_supervisor", "close_storage"]


def test_canonical_entrypoint_does_not_prepare_or_start_after_failed_admission(monkeypatch):
    import gdw_runtime
    events = []
    monkeypatch.setattr(gdw_runtime.durable_storage, "enabled", lambda: True)
    monkeypatch.setattr(startup, "activate", lambda: (_ for _ in ()).throw(startup.AdmissionBlocked("UNAVAILABLE")))
    monkeypatch.setattr(startup, "close", lambda: events.append("closed"))
    monkeypatch.setattr(gdw_runtime, "prepare_runtime", lambda: pytest.fail("prepared before admission"))
    monkeypatch.setattr(gdw_runtime.OutboxSupervisor, "from_environment", lambda: pytest.fail("supervisor before admission"))
    with pytest.raises(startup.AdmissionBlocked): gdw_runtime.main()
    assert events == ["closed"]
    assert gdw_runtime.runtime_health()["startup_state"] == "BLOCKED"


def test_fresh_restore_keeps_the_initial_series_anchor_even_for_a_longer_chain(native_startup):
    import time
    import gdw_durable_runtime as durable
    import gdw_durable_storage as storage
    state = native_startup
    # The remote object is internally valid and has the same generation, but
    # replaces the initial chain. Startup must still bind the admitted prefix.
    with sqlite3.connect(state.seed_paths["series_a"]) as db:
        db.execute("DELETE FROM receipts")
        db.execute("DELETE FROM sqlite_sequence WHERE name='receipts'")
    durable._GATE = None
    # Existing unmanaged fixture store now sees the mode flag; use only this
    # test's environment scope to build an adversarial closed native snapshot.
    import os
    mode = os.environ.pop("GDW_DURABLE_STORAGE")
    try:
        state.series.append_receipt("offline.replacement", {"replaced": True}, state.signer)
        state.series.append_receipt("offline.replacement", {"second": True}, state.signer)
    finally:
        os.environ["GDW_DURABLE_STORAGE"] = mode
    altered = state.raw.publish_snapshots(state.seed_paths, state.generation, time.monotonic() + 10)
    value = state.backend.head.value
    value.update(kind="COMMIT", epoch=1, sequence=2, writer_id="f" * 32,
                 previous_manifest_sha256=state.backend.head.digest, snapshots=altered)
    state.backend.head = storage.Head(state.backend.head.revision, storage.canonical(value))
    with pytest.raises(startup.AdmissionBlocked): startup.activate()
    assert "claim" not in state.events and durable._GATE is None


def test_provider_success_past_actual_host_budget_still_prevents_install(native_startup, monkeypatch):
    import gdw_durable_runtime as durable
    original = durable.LocalGate.acknowledge
    completed = []
    real_clock = startup.time.monotonic

    def late(gate):
        original(gate)
        completed.append(True)
        monkeypatch.setattr(startup.time, "monotonic", lambda: real_clock() + 61)

    monkeypatch.setattr(durable.LocalGate, "acknowledge", late)
    with pytest.raises(startup.AdmissionBlocked): startup.activate()
    assert completed and native_startup.backend.head.value["kind"] == "COMMIT"
    assert durable._GATE is None and startup._PARENT_LOCK_FD is None


def test_native_parent_lock_blocks_competing_process_before_provider_read(native_startup):
    import subprocess
    import sys
    root = startup.LOCAL_PARENT
    root.mkdir(mode=0o700)
    child = subprocess.Popen([sys.executable, "-c",
        "import fcntl,os,sys; fd=os.open(sys.argv[1],os.O_RDWR|os.O_CREAT,0o600); "
        "fcntl.flock(fd,fcntl.LOCK_EX); print('locked',flush=True); sys.stdin.read()",
        str(root / "startup.lock")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(startup.AdmissionBlocked): startup.activate()
        assert not native_startup.events
    finally:
        child.communicate("", timeout=5)


def test_missing_native_installed_key_is_rejected_without_key_generation(tmp_path, monkeypatch):
    import a11oy_signing_key
    observed = []

    def unavailable(env):
        observed.append(env["A11OY_REQUIRE_PERSISTENT_SIGNING"])
        return None, "", "unavailable", "test-only unavailable"

    monkeypatch.setattr(a11oy_signing_key, "load_signing_key", unavailable)
    with pytest.raises(startup.AdmissionBlocked, match="INSTALLED_SIGNING_AUTHORITY_UNAVAILABLE"):
        startup.verify_installed_credentials(tmp_path)
    assert observed == ["1"]


def test_canonical_publisher_full_image_and_all_source_python_paths_are_bound():
    """Use the immutable native publisher, not a replacement COPY fixture.

    The existing GDW job reads the pinned public repository with no persisted
    credentials. Local invocations use the same exact script via this variable.
    No network, application import or Docker execution occurs inside this test.
    """
    import os
    import importlib.util
    import tempfile
    import time
    from scripts.build_gdw_installed_source_manifest import build_manifest, _git
    import gdw_durable_storage as storage

    root = Path(startup.__file__).resolve().parent
    configured = os.environ.get("GDW_COPY_PUBLISHER_SCRIPT")
    assert configured, "GDW_COPY_PUBLISHER_SCRIPT must identify the exact pinned canonical publisher"
    deadline = time.monotonic() + 120
    revision = _git(root, ["rev-parse", "HEAD"], 128, deadline).decode("ascii").strip()
    value = build_manifest(root, revision, Path(configured), deadline=deadline)
    parsed = source.validate_manifest(value, revision)
    installed = {entry["path"]: entry for entry in parsed["installed_files"]}
    python_paths = {
        path.decode("ascii") for path in _git(root, ["ls-tree", "-r", "--name-only", "-z", revision],
                                              8 * 1024 * 1024, deadline).split(b"\0")
        if path.endswith(b".py")
    }
    installed_python = {path for path in installed if path.endswith(".py")}
    assert installed_python | set(parsed["absent_modules"]) == python_paths
    assert not installed_python.intersection(parsed["absent_modules"])
    assert source.REQUIRED_FILES <= installed.keys()
    assert {"serve.py", "a11oy_v4_agent.py", "szl_hub.py", "OUROBOROS_RUN_ALL.py"} <= installed.keys()

    # Preserve the existing native recursive import-closure gate as well as the
    # complete installed/absent inventory. An actually required local module
    # cannot be reclassified as an optional absence to make this check pass.
    guard_path = root / ".github/scripts/copy_completeness.py"
    specification = importlib.util.spec_from_file_location("_gdw_native_copy_guard", guard_path)
    guard = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(guard)
    closure = guard.collect_transitive_local_imports(
        ["serve.py", "gdw_runtime.py"], str(root), guard._stdlib_names(),
        max_depth=source.MAX_SOURCE_PYTHON_FILES)
    required = {name + ".py" for names in closure.values() for name in names}

    def require_native_closure(candidate):
        missing = required.difference(entry["path"] for entry in candidate["installed_files"])
        assert not missing, "native COPY import closure missing: " + ",".join(sorted(missing))

    require_native_closure(parsed)
    assert "szl_energy_measured.py" in required
    dropped = copy.deepcopy(parsed)
    dropped["installed_files"] = [entry for entry in dropped["installed_files"]
                                  if entry["path"] != "szl_energy_measured.py"]
    dropped["absent_modules"] = sorted(dropped["absent_modules"] + ["szl_energy_measured.py"])
    dropped["python_inventory"]["installed_count"] -= 1
    dropped["python_inventory"]["absent_count"] += 1
    source.validate_manifest(dropped, revision)  # Shape alone cannot prove COPY closure.
    with pytest.raises(AssertionError, match="szl_energy_measured.py"):
        require_native_closure(dropped)

    # Close the builder/runtime boundary with the complete real ~67 MiB image;
    # dispose it in the same test so failed assertions do not accumulate copies.
    with tempfile.TemporaryDirectory(prefix="gdw-source-image-") as temporary:
        parent = Path(temporary)
        app, inputs = parent / "app", parent / "tmp"
        app.mkdir()
        inputs.mkdir()
        for path, entry in installed.items():
            data = (root / entry["source_path"]).read_bytes()
            assert len(data) == entry["size"] and hashlib.sha256(data).hexdigest() == entry["sha256"]
            destination = app / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        (inputs / "requirements-runtime.txt").write_bytes((app / "requirements-runtime.txt").read_bytes())
        observed = source.verify_installed_source(parsed, app, revision, runtime_install_root=inputs)
        assert observed["state"] == "ADMITTED_SOURCE_CONTENT_EQUALITY"
        assert observed["installed_file_count"] == len(installed)

    record = admission()
    record["source"]["revision"] = revision
    record["qualification"]["source"]["revision"] = revision
    record["capture"]["source_revision"] = revision
    record["capture"]["capture_id"] = f"123-1-{revision}-{'a' * 32}"
    record["legacy_quiescence"]["source_revision"] = revision
    record["runtime"]["source_manifest"] = parsed
    record["runtime"]["source_manifest_sha256"] = hashlib.sha256(source.canonical(parsed)).hexdigest()
    bind_base_observation(record)
    encoded = startup.canonical(record)
    message = storage.canonical({"state": "READ_ONLY_ADMISSION_OBSERVATION", "admission": encoded.decode("ascii"),
                                 "head": {"revision": revision}})
    assert len(source.canonical(parsed)) <= source.MAX_MANIFEST_BYTES
    assert len(encoded) <= startup.MAX_ADMISSION_BYTES
    assert len(message) <= storage.MAX_WORKER_MESSAGE_BYTES
    assert startup.parse_admission(encoded) == record


def test_first_source_read_may_update_access_time_without_changing_identity(tmp_path, monkeypatch):
    import os
    record = admission()
    record["runtime"]["source_manifest"], app, inputs = install_image(tmp_path)
    record["runtime"]["source_manifest_sha256"] = hashlib.sha256(source.canonical(record["runtime"]["source_manifest"])).hexdigest()
    bind_base_observation(record)
    monkeypatch.setattr(source, "RUNTIME_INSTALL_ROOT", inputs)
    for entry in record["runtime"]["source_manifest"]["installed_files"]:
        path = app / entry["path"]
        metadata = path.stat()
        os.utime(path, ns=(1, metadata.st_mtime_ns))
    startup.verify_runtime(record, app, "b" * 40, "1.31.0")
    assert (app / "serve.py").stat().st_atime_ns > 1
