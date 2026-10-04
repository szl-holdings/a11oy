#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline native protocol controls; synthetic selectors grant no authority."""
import copy
import hashlib
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

import acquire_gdw_durable_storage as acquisition
import gdw_durable_storage as storage
import gdw_durable_guard as guard
import preserve_hf_gdw_store as preservation
from test_gdw_durable_startup import admission
from test_gdw_durable_runtime import stores


def fixture():
    record = admission()
    body = {"schema": storage.SCHEMA, "space": storage.SPACE, "dataset": storage.DATASET,
            "bucket": storage.BUCKET, "kind": "BOOTSTRAP", "epoch": 0, "sequence": 0,
            "writer_id": "0" * 32, "operation_id": "a" * 32, "previous_manifest_sha256": None,
            "source_revision": record["source"]["revision"], "snapshots": record["snapshots"],
            "qualification_sha256": hashlib.sha256(acquisition.canonical(record)).hexdigest()}
    return record, storage.Head("e" * 40, storage.canonical(body))


def test_selector_is_canonical_detached_and_performs_no_io(monkeypatch):
    record, head = fixture()
    monkeypatch.setattr(Path, "open", lambda *_a, **_k: pytest.fail("pure selector performed I/O"))
    locator = acquisition.locator_for_bootstrap(head, record)
    assert acquisition.parse_acquisition_locator(acquisition.canonical(locator)) == locator
    assert locator["admission_sha256"] == head.value["qualification_sha256"]
    assert locator["qualification_sha256"] == record["qualification"]["report_sha256"]
    assert locator["legacy_guard_sha256"] == hashlib.sha256(acquisition.canonical(record["legacy_guard"])).hexdigest()
    record["snapshots"]["gdw"]["generation"] = "changed"
    assert locator["generations"]["gdw"] == "f" * 32


@pytest.mark.parametrize("field,value", [
    ("state", "PLANNED"), ("source_revision", "0" * 40), ("dataset_revision", "main"),
    ("operation_id", "0" * 32), ("admission_sha256", "0" * 64),
    ("source_manifest_sha256", "0" * 64), ("qualification_sha256", "0" * 64),
    ("legacy_guard_sha256", "0" * 64), ("resource_group_sha256", "0" * 64),
    ("space", "SZLHOLDINGS/other"), ("dataset", "SZLHOLDINGS/public"),
    ("generations", {"gdw": "0" * 32, "series_a": "store_" + "f" * 32}),
])
def test_unbound_selector_inputs_rejected(field, value):
    record, head = fixture()
    locator = acquisition.locator_for_bootstrap(head, record)
    locator[field] = value
    with pytest.raises(acquisition.AcquisitionBlocked):
        acquisition.parse_acquisition_locator(acquisition.canonical(locator))


@pytest.mark.parametrize("kind", ["pretty", "duplicate", "extra", "missing", "oversize", "nan"])
def test_selector_strict_byte_and_shape_bounds(kind):
    record, head = fixture()
    locator = acquisition.locator_for_bootstrap(head, record)
    if kind == "extra": locator["authorized"] = True
    if kind == "missing": del locator["legacy_guard_sha256"]
    data = acquisition.canonical(locator)
    if kind == "pretty": data = json.dumps(locator, indent=2).encode()
    if kind == "duplicate": data = data[:-2] + b',"schema":"duplicate"}\n'
    if kind == "oversize": data = b" " * (acquisition.MAX_LOCATOR_BYTES + 1)
    if kind == "nan": data = data.replace(b'"BOOTSTRAP_ACKNOWLEDGED"', b'NaN')
    with pytest.raises(acquisition.AcquisitionBlocked): acquisition.parse_acquisition_locator(data)


def test_changed_admission_cannot_render_matching_bootstrap_selector():
    record, head = fixture()
    changed = copy.deepcopy(record)
    changed["qualification"]["report_sha256"] = "a" * 64
    with pytest.raises(acquisition.AcquisitionBlocked):
        acquisition.locator_for_bootstrap(head, changed)


def qualified_fixture():
    captured = {"schema": preservation.SCHEMA, "space": storage.SPACE, "bucket": storage.BUCKET,
        "source_revision": "b" * 40, "state": "BLOCKED", "preservation_state": "VERIFIED",
        "initial_identities_stable": True, "captured_originals_unchanged_after_inspection": True,
        "originals_mutated": False, "space_mutated": False, "restore_admitted": False,
        "deployment_admitted": False, "private_bytes_in_public_artifacts": False, "secret_values_recorded": False,
        "capture_id": "123-1-" + "b" * 40 + "-" + "a" * 32,
        "private_manifest": {"sha256": "a" * 64}, "databases": {}, "files": []}
    for label, path in preservation.DATABASES.items():
        captured["databases"][label] = {"database_generation_id": "f" * 32 if label == "gdw" else "store_" + "f" * 32}
    for path in preservation.SOURCE_PATHS:
        row = {"source_path": path, "present": path in preservation.DATABASES.values(), "private_copy_path": None, "sha256": None}
        if row["present"]: row.update(size=4096, xet_hash="e" * 64, sha256="d" * 64)
        captured["files"].append(row)
    encoded = acquisition.canonical(captured)
    report = {"schema": "szl.gdw-store-recovery-qualification/v1", "state": "LOGICAL_CONTINUITY_VERIFIED",
        "inspector_source_revision": "b" * 40, "capture_id": captured["capture_id"], "capture_source_revision": "b" * 40,
        "preservation_manifest_sha256": "a" * 64, "historical_anchor_state": "VERIFIED",
        "captured_historical_anchor_state": "VERIFIED", "originals_mutated": False,
        "provider_writes_performed": False, "restore_admitted": False, "deployment_admitted": False,
        "private_bytes_in_public_artifacts": False, "secret_values_recorded": False, "later_acknowledged_writes_verified": False,
        "historical_anchor_reference": {"capture_report_sha256": hashlib.sha256(encoded).hexdigest()}, "databases": {}}
    for label in storage.LABELS:
        report["databases"][label] = {"state": "LOGICAL_CONTINUITY_VERIFIED", "captured_originals_unchanged": True,
            "all_declared_stored_values_unchanged": True, "schema_unchanged": True, "receipt_bytes_unchanged": True,
            "database_generation_unchanged": True, "historical_anchor_state": "VERIFIED",
            "database_generation_id": captured["databases"][label]["database_generation_id"],
            "candidate_sha256": "d" * 64, "candidate_bytes": 4096, "candidate_method": "SQLITE_NATIVE_BACKUP",
            "candidate_integrity": {"classification": "OK", "foreign_key_check_complete": True,
                "integrity_check_complete": True, "foreign_key_violation_count": 0},
            "original_logical_state": {"logical_sha256": "a" * 64, "schema_sha256": "b" * 64},
            "original_receipts": {"digest_errors": 0, "binding_errors": 0, "chain_link_errors": 0},
            "candidate_historical_anchor": {"state": "VERIFIED"}}
    return copy.deepcopy(captured), report, captured, encoded


def test_native_qualified_pair_selection_keeps_no_restore_claim():
    preserved, report, reference, encoded = qualified_fixture()
    selected = acquisition.validate_qualified_reports(preserved, report, reference, encoded, "b" * 40)
    assert set(selected) == set(storage.LABELS)
    assert report["restore_admitted"] is report["deployment_admitted"] is False
    assert selected["gdw"]["sha256"] == "d" * 64


@pytest.mark.parametrize("defect", ["source", "current_original", "companion", "not_qualified", "later_claim",
    "capture", "generation", "receipt", "fk", "boolean_fk", "missing_store", "hash", "anchor"])
def test_incomplete_qualification_never_selects_a_candidate(defect):
    preserved, report, reference, encoded = qualified_fixture()
    if defect == "source": report["inspector_source_revision"] = "c" * 40
    if defect == "current_original": preserved["files"][0]["xet_hash"] = "f" * 64
    if defect == "companion": preserved["files"][1].update(present=True, size=0, sha256="e" * 64, xet_hash="d" * 64)
    if defect == "not_qualified": report["state"] = "BLOCKED"
    if defect == "later_claim": report["later_acknowledged_writes_verified"] = True
    if defect == "capture": report["capture_id"] = "other"
    if defect == "generation": report["databases"]["gdw"]["database_generation_id"] = "a" * 32
    if defect == "receipt": report["databases"]["series_a"]["original_receipts"]["chain_link_errors"] = 1
    if defect == "fk": report["databases"]["gdw"]["candidate_integrity"]["foreign_key_violation_count"] = 1
    if defect == "boolean_fk": report["databases"]["gdw"]["candidate_integrity"]["foreign_key_violation_count"] = False
    if defect == "missing_store": report["databases"].pop("series_a")
    if defect == "hash": report["databases"]["gdw"]["candidate_sha256"] = "0" * 64
    if defect == "anchor": report["captured_historical_anchor_state"] = "NOT_CHECKED"
    with pytest.raises(acquisition.AcquisitionBlocked):
        acquisition.validate_qualified_reports(preserved, report, reference, encoded, "b" * 40)


class PausedAPI:
    endpoint = storage.ENDPOINT
    def __init__(self, stage="RUNTIME_ERROR"):
        self.stage, self.pauses, self.fail, self.changed = stage, 0, False, False
    def bucket_info(self, **kwargs): return {"id": storage.BUCKET, "private": True}
    def space_info(self, **kwargs):
        return {"id": storage.SPACE, "sha": guard.SPACE_REVISION, "runtime": {"volumes": [
            {"type": "bucket", "source": storage.BUCKET, "mountPath": "/data", "readOnly": False}]}}
    def get_space_runtime(self, **kwargs): return {"stage": self.stage}
    def get_bucket_paths_info(self, **kwargs):
        return [{"path": path, "type": "file", "size": 4096,
                 "xet_hash": ("a" if self.changed else "e") * 64}
                for path in preservation.DATABASES.values()]
    def pause_space(self, **kwargs):
        assert kwargs == {"repo_id": storage.SPACE}
        self.pauses += 1
        self.stage = "PAUSED"
        if self.fail: raise TimeoutError("synthetic lost reply")
        return {"stage": self.stage}


@pytest.mark.parametrize("stage,expected_effects", [("RUNTIME_ERROR", 1), ("PAUSED", 0)])
def test_pause_reads_actual_state_and_unchanged_original_identities(stage, expected_effects):
    api = PausedAPI(stage)
    expected = acquisition.original_identities(qualified_fixture()[2])
    source_checks = []
    result = acquisition.pause_qualified_source(api, expected,
        require_owned_source=lambda: source_checks.append(True), deadline=time.monotonic() + 10)
    assert api.pauses == expected_effects
    assert result["state"] == "PAUSED_SOURCE_AND_ORIGINAL_IDENTITIES_VERIFIED"
    assert result["pause_submitted"] is bool(expected_effects)
    assert len(source_checks) >= 3


def test_lost_pause_acknowledgement_is_not_retried_even_if_provider_paused():
    api = PausedAPI(); api.fail = True
    with pytest.raises(acquisition.AcquisitionBlocked, match="PAUSE_OUTCOME_UNCERTAIN"):
        acquisition.pause_qualified_source(api, acquisition.original_identities(qualified_fixture()[2]),
            require_owned_source=lambda: None, deadline=time.monotonic() + 10)
    assert api.stage == "PAUSED" and api.pauses == 1


@pytest.mark.parametrize("defect", ["running", "changed_original", "source_superseded"])
def test_unqualified_pause_boundary_performs_no_effect(defect):
    api = PausedAPI("RUNNING" if defect == "running" else "RUNTIME_ERROR")
    if defect == "changed_original": api.changed = True
    def owned():
        if defect == "source_superseded": raise acquisition.AcquisitionBlocked("SOURCE_SUPERSEDED")
    with pytest.raises((acquisition.AcquisitionBlocked, preservation.PreservationError)):
        acquisition.pause_qualified_source(api, acquisition.original_identities(qualified_fixture()[2]),
            require_owned_source=owned, deadline=time.monotonic() + 10)
    assert api.pauses == 0


@pytest.mark.parametrize("mutated", [False, True])
def test_bounded_source_read_ignores_access_time_but_rejects_modification(tmp_path, monkeypatch, mutated):
    path = tmp_path / "source.json"; path.write_bytes(b'{"public":"fixture"}')
    real = os.fstat
    calls = 0
    def metadata(fd):
        nonlocal calls
        result = real(fd)
        calls += 1
        values = {name: getattr(result, name) for name in dir(result) if name.startswith("st_")}
        if calls > 1:
            values["st_atime_ns"] += 100
            if mutated: values["st_mtime_ns"] += 1
        return SimpleNamespace(**values)
    monkeypatch.setattr(acquisition.os, "fstat", metadata)
    if mutated:
        with pytest.raises(acquisition.AcquisitionBlocked): acquisition._read(path)
    else:
        assert acquisition._read(path) == b'{"public":"fixture"}'


def test_real_backend_uses_guarded_sdk_compatible_positional_commit(tmp_path):
    tmp_path.chmod(0o700)
    calls = []
    class API:
        endpoint = storage.ENDPOINT
        def create_commit(self, repo_id, **kwargs):
            calls.append(("commit", repo_id, kwargs))
            return SimpleNamespace(oid="f" * 40)
    guarded = acquisition._AdmittedAcquisitionHub(API(), lambda: calls.append(("paused-and-owned",)))
    backend = storage.HFDatasetFenceBackend(guarded, tmp_path, "d" * 64,
        lambda **kwargs: SimpleNamespace(**kwargs))
    assert backend._commit("a" * 40, [(storage.HEAD_PATH, b'{"synthetic":"metadata"}\n')],
                           time.monotonic() + 5) == "f" * 40
    assert calls[0] == ("paused-and-owned",)
    assert calls[1][1] == storage.DATASET and calls[1][2]["parent_commit"] == "a" * 40
    assert len(calls) == 2


@pytest.mark.parametrize("repo_id", ["other/repo", None])
def test_guarded_commit_scope_rejected_before_pause_or_provider(repo_id):
    guarded = acquisition._AdmittedAcquisitionHub(SimpleNamespace(), lambda: pytest.fail("out-of-scope boundary checked"))
    with pytest.raises(acquisition.AcquisitionBlocked):
        guarded.create_commit(repo_id, repo_type="dataset", parent_commit="a" * 40)


@pytest.mark.parametrize("outcome", [200, 302, 412, 429, 500, "lost_reply"])
def test_pause_transport_requires_2xx_and_never_retries(outcome):
    import httpx
    calls = []
    def transport(request):
        calls.append(request)
        if outcome == "lost_reply": raise httpx.ReadTimeout("synthetic lost reply", request=request)
        return httpx.Response(outcome, json={"stage": "PAUSED"})
    with storage.bounded_hub_client(transport=httpx.MockTransport(transport)) as client:
        if outcome == 200:
            assert client.post(f"{storage.ENDPOINT}/api/spaces/{storage.SPACE}/pause").status_code == 200
        else:
            with pytest.raises(storage.StorageBlocked, match="STORAGE_OUTCOME_UNCERTAIN"):
                client.post(f"{storage.ENDPOINT}/api/spaces/{storage.SPACE}/pause")
    assert len(calls) == 1


@pytest.fixture
def native_acquisition(stores, tmp_path, monkeypatch):
    """Real acquisition/core/stores/artifact path; only archived evidence and Hub are synthetic."""
    import qualify_gdw_store_recovery as recovery
    import gdw_durable_runtime as durable
    from test_gdw_durable_artifacts import exported
    from test_gdw_durable_storage import ObjectAPI
    from test_gdw_durable_guard import fixture as guard_fixture
    from routers.series_a_control_plane import ReceiptSigner

    signer = ReceiptSigner.__new__(ReceiptSigner)
    signer.private_key, signer.public_pem, signer.source, signer.error = None, "", "unavailable", "offline fixture"
    stores.series.append_receipt("offline.acquisition", {"retained": "PRIVATE_PAIR_ROW"}, signer)
    exported(stores)
    stores.gate.close()
    monkeypatch.setattr(durable, "_GATE", None)
    monkeypatch.delenv("GDW_DURABLE_STORAGE", raising=False)
    original_bytes = {label: path.read_bytes() for label, path in stores.paths.items()}
    workspace = tmp_path / "acquisition"; workspace.mkdir(mode=0o700)
    preserved, report, reference, _old_encoded = qualified_fixture()
    reference["private_manifest"]["xet_hash"] = "6" * 64
    for label, path in stores.paths.items():
        native = storage.inspect_snapshot(label, path, stores.directory, time.monotonic() + 10)
        reference["databases"][label]["database_generation_id"] = native["generation"]
        row = next(item for item in reference["files"] if item["source_path"] == preservation.DATABASES[label])
        row.update(size=native["size"], sha256=native["sha256"])
        report["databases"][label].update(database_generation_id=native["generation"],
            candidate_bytes=native["size"], candidate_sha256=native["sha256"])
    preserved = copy.deepcopy(reference)
    captured = acquisition.canonical(reference)
    report["historical_anchor_reference"]["capture_report_sha256"] = hashlib.sha256(captured).hexdigest()
    record = admission()
    legacy, observation = guard_fixture()
    pause = {"state": "PAUSED_SOURCE_AND_ORIGINAL_IDENTITIES_VERIFIED", "space_revision": guard.SPACE_REVISION,
        "observed_at": "2026-10-04T17:00:00Z", "observation_sha256": "7" * 64}
    probe = {"state": "PREWRITE_REJECTION_VERIFIED", "scope": guard.PROBE_SCOPE, "python_version": "3.14.0",
        "source_files_sha256": dict(guard.SOURCE_FILES), "source_closure_sha256": legacy["native_probe"]["source_closure_sha256"],
        "cases": [{"name": name, "state": "PREWRITE_REJECTION_VERIFIED", "forbidden_effect_count": 0} for name in guard.CASES],
        "total_forbidden_effect_count": 0, "unguarded_control": "PREPARATION_WRITE_OBSERVED"}
    events = []

    class API(ObjectAPI, PausedAPI):
        def __init__(self):
            ObjectAPI.__init__(self)
            self.stage = "PAUSED"
            self.revision = "1" * 40
            self.repositories = {self.revision: {}}
            self.commits = []
            self.lost_commit = False
            self.source_current = True
        def get_bucket_paths_info(self, *, bucket_id, paths):
            if set(paths) <= set(preservation.SOURCE_PATHS):
                return [SimpleNamespace(type="file", path=item["source_path"], size=item["size"], xet_hash=item["xet_hash"])
                        for item in reference["files"] if item["present"] and item["source_path"] in paths]
            return list(super().get_bucket_paths_info(bucket_id=bucket_id, paths=paths))
        def dataset_info(self, repo_id, *, revision, expand):
            assert repo_id == storage.DATASET
            selected = self.revision if revision == "main" else revision
            assert selected in self.repositories
            return SimpleNamespace(id=repo_id, sha=selected, private=True, resource_group=None)
        def get_paths_info(self, repo_id, paths, *, repo_type, revision):
            assert repo_id == storage.DATASET and repo_type == "dataset"
            items = self.repositories[revision]
            return [SimpleNamespace(path=path, size=len(items[path]), lfs=None,
                    blob_id=hashlib.sha1(b"blob " + str(len(items[path])).encode() + b"\0" + items[path]).hexdigest())
                    for path in paths if path in items]
        def hf_hub_download(self, repo_id, *, filename, repo_type, revision, local_dir, cache_dir):
            assert repo_id == storage.DATASET and repo_type == "dataset"
            target = local_dir / filename
            target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            target.write_bytes(self.repositories[revision][filename])
            return str(target)
        def batch_bucket_files(self, **kwargs):
            assert events[-1] == "owned"
            events.append("private_object")
            return super().batch_bucket_files(**kwargs)
        def create_commit(self, repo_id, **kwargs):
            assert repo_id == storage.DATASET and kwargs["parent_commit"] == self.revision
            assert kwargs["repo_type"] == "dataset" and kwargs["create_pr"] is False
            assert events[-1] == "owned"
            events.append("metadata_cas")
            values = dict(self.repositories[self.revision])
            for operation in kwargs["operations"]:
                assert isinstance(operation.path_or_fileobj, bytes)
                values[operation.path_in_repo] = operation.path_or_fileobj
            self.commits.append(kwargs)
            self.revision = f"{len(self.commits) + 1:040x}"
            self.repositories[self.revision] = values
            if self.lost_commit: raise TimeoutError("PRIVATE_PAIR_ROW")
            return SimpleNamespace(oid=self.revision)

    api = API()
    def owned():
        if not api.source_current: raise acquisition.AcquisitionBlocked("SOURCE_SUPERSEDED")
        events.append("owned")
    def reproduce(_api, _reference, directory, *_args, **_kwargs):
        assert isinstance(_api, recovery.ReadOnlyCaptureHub)
        for label, data in original_bytes.items():
            parent = directory / "working" / label
            parent.mkdir(parents=True, mode=0o700)
            for folder in (directory, directory / "working", parent): folder.chmod(0o700)
            target = parent / "candidate.sqlite3"; target.write_bytes(data); target.chmod(0o600)
        return copy.deepcopy(report)
    monkeypatch.setattr(recovery, "qualify_capture", reproduce)
    monkeypatch.setattr(recovery, "validate_historical_anchors", lambda *_a, **_k: None)
    arguments = dict(source_context=record["source"], qualification_context=record["source"],
        qualification_artifact_id=789, qualification_archive_sha256="8" * 64,
        preserved=preserved, qualified=report, qualification_bytes=acquisition.canonical(report),
        reference=reference, capture_bytes=captured, anchors={}, anchor_bytes=b"{}\n",
        manifest=record["runtime"]["source_manifest"], base_observation=record["runtime"]["base_observation"],
        guard_probe=probe, paused=pause, legacy_observation=observation, workspace=workspace,
        require_owned_source=owned, deadline=time.monotonic() + 20,
        operation_factory=lambda **kwargs: SimpleNamespace(**kwargs))
    return SimpleNamespace(api=api, arguments=arguments, events=events, originals=original_bytes, paths=stores.paths)


def test_real_pair_artifacts_restore_and_absent_bootstrap_are_acknowledged_together(native_acquisition):
    import gdw_durable_startup as startup
    state = native_acquisition
    locator = acquisition.acquire_pair(state.api, **state.arguments)
    values = state.api.repositories[state.api.revision]
    head = storage.Head(state.api.revision, values[storage.HEAD_PATH])
    admitted = startup.parse_admission(values[f"{storage.ADMISSION_PREFIX}/{locator['admission_sha256']}.json"])
    assert locator == acquisition.locator_for_bootstrap(head, admitted)
    assert len(state.api.commits) == 1 and len(state.api.additions) == 3
    assert state.api.additions[0][0].startswith(storage.ARTIFACT_PREFIX + "/")
    assert all(item[0].startswith(storage.OBJECT_PREFIX + "/") for item in state.api.additions[1:])
    assert state.events.index("private_object") < state.events.index("metadata_cas")
    assert admitted["retained_artifacts"]["count"] == 1
    assert admitted["snapshots"]["series_a"]["receipt_count"] == 1
    assert admitted["runtime"]["base_observation"]["final_runtime"] == "FINAL_RUNTIME_NOT_OBSERVED"
    assert b"PRIVATE_PAIR_ROW" not in acquisition.canonical(locator)
    assert all(b"PRIVATE_PAIR_ROW" not in value for value in values.values())
    for label, data in state.originals.items():
        assert state.paths[label].read_bytes() == data
        assert (state.arguments["workspace"] / "roundtrip" / (label + ".sqlite3")).read_bytes() == data


@pytest.mark.parametrize("defect", ["existing_head", "source_superseded", "not_paused", "candidate_changed"])
def test_unqualified_pair_never_publishes_private_objects_or_bootstrap(native_acquisition, defect):
    state = native_acquisition
    if defect == "existing_head": state.api.repositories[state.api.revision][storage.HEAD_PATH] = b"prior"
    if defect == "source_superseded": state.api.source_current = False
    if defect == "not_paused": state.api.stage = "RUNTIME_ERROR"
    if defect == "candidate_changed": state.originals["gdw"] += b"changed"
    with pytest.raises((acquisition.AcquisitionBlocked, storage.StorageBlocked)):
        acquisition.acquire_pair(state.api, **state.arguments)
    assert state.api.additions == state.api.commits == []


def test_pair_cas_lost_reply_does_not_retry_or_emit_selector(native_acquisition):
    state = native_acquisition
    state.api.lost_commit = True
    with pytest.raises(storage.StorageBlocked, match="STORAGE_OUTCOME_UNCERTAIN"):
        acquisition.acquire_pair(state.api, **state.arguments)
    assert len(state.api.commits) == 1
    assert storage.HEAD_PATH in state.api.repositories[state.api.revision]
    assert len(state.api.additions) == 3
