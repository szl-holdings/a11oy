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

from scripts import acquire_gdw_durable_storage as acquisition
import gdw_durable_storage as storage
import gdw_durable_guard as guard
from scripts import preserve_hf_gdw_store as preservation
from tests.test_gdw_durable_startup import admission
from tests.test_gdw_durable_runtime import stores


@pytest.fixture(autouse=True)
def cli_sibling_modules(monkeypatch):
    """Reproduce exact CLI sibling imports without PYTHONPATH or network effects."""
    import sys
    import importlib
    # Loading the qualifier needs these two exact siblings first. monkeypatch
    # restores all aliases after each test; application imports are unchanged.
    for name in ("preserve_hf_gdw_store", "gdw_orphan_forensics",
                 "qualify_gdw_store_recovery", "gdw_acquisition_evidence", "probe_gdw_runtime_base", "inspect_gdw_held_acquisition", "inspect_gdw_62ca_acquisition",
                 "reconcile_gdw_supervised_acquisition"):
        module = importlib.import_module("scripts." + name)
        monkeypatch.setitem(sys.modules, name, module)


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
    assert result["pause_acknowledgement"] == ("ACKNOWLEDGED" if expected_effects else "NOT_APPLICABLE")
    assert len(source_checks) >= 3


@pytest.mark.parametrize("reply", ["exception", "malformed"])
def test_uncertain_pause_reply_uses_stable_readback_without_retry(reply):
    api = PausedAPI(); api.fail = True
    if reply == "malformed":
        api.fail = False
        def malformed(**kwargs):
            assert kwargs == {"repo_id": storage.SPACE}
            api.pauses += 1
            api.stage = "PAUSED"
            return {}
        api.pause_space = malformed
    result = acquisition.pause_qualified_source(api, acquisition.original_identities(qualified_fixture()[2]),
        require_owned_source=lambda: None, deadline=time.monotonic() + 10)
    assert api.stage == "PAUSED" and api.pauses == 1
    assert result["pause_submitted"] is True
    assert result["pause_acknowledgement"] == "NOT_ESTABLISHED"


@pytest.mark.parametrize("reply", ["exception", "malformed"])
def test_uncertain_pause_reply_without_stable_paused_readback_is_held(reply):
    api = PausedAPI()
    def uncertain(**kwargs):
        assert kwargs == {"repo_id": storage.SPACE}
        api.pauses += 1
        if reply == "exception":
            raise TimeoutError("synthetic lost reply")
        return {}
    api.pause_space = uncertain
    with pytest.raises(acquisition.AcquisitionBlocked, match="PAUSE_OUTCOME_UNCERTAIN"):
        acquisition.pause_qualified_source(api, acquisition.original_identities(qualified_fixture()[2]),
            require_owned_source=lambda: None, deadline=time.monotonic() + 10)
    assert api.stage == "RUNTIME_ERROR" and api.pauses == 1


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


@pytest.mark.parametrize("outcome,readback_stage,expected", [
    ("valid", "PAUSED", "ACKNOWLEDGED"),
    ("malformed", "PAUSED", "NOT_ESTABLISHED"),
    ("non_paused", "RUNTIME_ERROR", "BLOCKED"),
    ("lost_reply", "PAUSED", "NOT_ESTABLISHED"),
])
def test_official_hf_131_pause_response_never_retries_and_requires_readback(
        tmp_path, monkeypatch, outcome, readback_stage, expected):
    huggingface_hub = pytest.importorskip("huggingface_hub")
    httpx = pytest.importorskip("httpx")
    assert huggingface_hub.__version__ == "1.31.0"
    from huggingface_hub.utils import _detect_agent
    from huggingface_hub.utils._http import default_client_factory

    monkeypatch.setattr(_detect_agent, "_registry", None)
    monkeypatch.setattr(_detect_agent.constants, "AGENT_HARNESSES_PATH",
                        str(tmp_path / "agent-harnesses.json"))
    requests = []

    def response(request):
        requests.append(request)
        assert request.url.scheme == "https"
        assert request.url.host == "huggingface.co"
        assert "authorization" not in request.headers
        if request.url.path == "/api/agent-harnesses":
            assert request.method == "GET"
            return httpx.Response(200, json={
                "standardEnvVars": [], "harnesses": {}}, request=request)
        assert request.method == "POST"
        assert request.url.path == "/api/spaces/SZLHOLDINGS/a11oy/pause"
        if outcome == "lost_reply":
            raise httpx.ReadTimeout("synthetic lost reply", request=request)
        if outcome == "malformed":
            return httpx.Response(200, json={"stage": "PAUSED", "hardware": None}, request=request)
        stage = "PAUSED" if outcome == "valid" else "RUNTIME_ERROR"
        return httpx.Response(200, json={"stage": stage,
            "hardware": {"current": None, "requested": "cpu-basic"}}, request=request)

    observations = iter((
        {"stage": "RUNTIME_ERROR", "hf_revision": guard.SPACE_REVISION},
        {"stage": readback_stage, "hf_revision": guard.SPACE_REVISION},
        {"stage": readback_stage, "hf_revision": guard.SPACE_REVISION},
    ))
    def observe(_api, _expected, *, require_owned_source, deadline):
        require_owned_source()
        assert deadline > time.monotonic()
        return next(observations)
    monkeypatch.setattr(acquisition, "observe_originals", observe)
    huggingface_hub.set_client_factory(
        lambda: httpx.Client(transport=httpx.MockTransport(response)))
    try:
        api = huggingface_hub.HfApi(endpoint=storage.ENDPOINT, token=False)
        if expected == "BLOCKED":
            with pytest.raises(acquisition.AcquisitionBlocked,
                               match="^PAUSE_OUTCOME_UNCERTAIN$"):
                acquisition.pause_qualified_source(api, {},
                    require_owned_source=lambda: None,
                    deadline=time.monotonic() + 30)
        else:
            result = acquisition.pause_qualified_source(api, {},
                require_owned_source=lambda: None,
                deadline=time.monotonic() + 30)
            assert result["pause_submitted"] is True
            assert result["pause_acknowledgement"] == expected
    finally:
        huggingface_hub.set_client_factory(default_client_factory)

    pause_requests = [request for request in requests
                      if request.url.path == "/api/spaces/SZLHOLDINGS/a11oy/pause"]
    agent_requests = [request for request in requests
                      if request.url.path == "/api/agent-harnesses"]
    assert len(pause_requests) == 1
    assert len(agent_requests) == 1
    assert len(requests) == 2


@pytest.fixture
def native_acquisition(stores, tmp_path, monkeypatch):
    """Real acquisition/core/stores/artifact path; only archived evidence and Hub are synthetic."""
    from scripts import qualify_gdw_store_recovery as recovery
    import gdw_durable_runtime as durable
    from tests.test_gdw_durable_artifacts import exported
    from tests.test_gdw_durable_storage import ObjectAPI
    from tests.test_gdw_durable_guard import fixture as guard_fixture
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
    pause = {"state": "PAUSED_SOURCE_AND_ORIGINAL_IDENTITIES_VERIFIED", "pause_submitted": False,
        "pause_acknowledgement": "NOT_APPLICABLE", "space_revision": guard.SPACE_REVISION,
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
    def reconcile():
        events.append("reconciled")
        if getattr(api, "reconciliation_changed", False) or storage.HEAD_PATH in api.repositories[api.revision]:
            raise acquisition.AcquisitionBlocked("SUPERVISED_RECONCILIATION_REQUIRED")
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
        require_owned_source=owned, require_prewrite_reconciliation=reconcile,
        deadline=time.monotonic() + 20,
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
    # Initial gate + each of three object submissions + the bootstrap CAS. The
    # acknowledged own HEAD is then read back, never required to remain absent.
    assert state.events.count("reconciled") == 5
    assert admitted["retained_artifacts"]["count"] == 1
    assert admitted["snapshots"]["series_a"]["receipt_count"] == 1
    assert admitted["runtime"]["base_observation"]["final_runtime"] == "FINAL_RUNTIME_NOT_OBSERVED"
    assert b"PRIVATE_PAIR_ROW" not in acquisition.canonical(locator)
    assert all(b"PRIVATE_PAIR_ROW" not in value for value in values.values())
    for label, data in state.originals.items():
        assert state.paths[label].read_bytes() == data
        assert (state.arguments["workspace"] / "roundtrip" / (label + ".sqlite3")).read_bytes() == data


@pytest.mark.parametrize("defect", ["existing_head", "source_superseded", "not_paused", "pause_proof",
    "candidate_changed", "reconciliation_changed"])
def test_unqualified_pair_never_publishes_private_objects_or_bootstrap(native_acquisition, defect):
    state = native_acquisition
    if defect == "existing_head": state.api.repositories[state.api.revision][storage.HEAD_PATH] = b"prior"
    if defect == "source_superseded": state.api.source_current = False
    if defect == "not_paused": state.api.stage = "RUNTIME_ERROR"
    if defect == "pause_proof": state.arguments["paused"]["pause_acknowledgement"] = "ACKNOWLEDGED"
    if defect == "candidate_changed": state.originals["gdw"] += b"changed"
    if defect == "reconciliation_changed": state.api.reconciliation_changed = True
    with pytest.raises((acquisition.AcquisitionBlocked, storage.StorageBlocked)):
        acquisition.acquire_pair(state.api, **state.arguments)
    assert state.api.additions == state.api.commits == []


def test_changed_fence_before_first_private_submission_is_not_retried(native_acquisition):
    state = native_acquisition
    original = state.arguments["require_prewrite_reconciliation"]
    calls = 0
    def reconcile():
        nonlocal calls
        calls += 1
        if calls == 2:
            state.api.reconciliation_changed = True
        original()
    state.arguments["require_prewrite_reconciliation"] = reconcile
    from gdw_durable_runtime import DurableStorageUnavailable
    # The provider-callback boundary includes the prewrite reconciliation fence.
    # Its closed diagnostic does not imply submission; the zero-write and
    # no-retry assertions below still bind the actual synthetic API observations.
    with pytest.raises(DurableStorageUnavailable, match="^ARTIFACT_PROVIDER_CALL_UNAVAILABLE$"):
        acquisition.acquire_pair(state.api, **state.arguments)
    assert calls == 2 and state.api.additions == state.api.commits == []


def test_pair_cas_lost_reply_does_not_retry_or_emit_selector(native_acquisition):
    state = native_acquisition
    state.api.lost_commit = True
    with pytest.raises(storage.StorageBlocked, match="STORAGE_OUTCOME_UNCERTAIN"):
        acquisition.acquire_pair(state.api, **state.arguments)
    assert len(state.api.commits) == 1
    assert storage.HEAD_PATH in state.api.repositories[state.api.revision]
    assert len(state.api.additions) == 3


PRIVATE_FAILURE = "PRIVATE_SYNTHETIC_TOKEN_URL_SQL_NOT_FOR_PUBLIC_OUTPUT"


def held_report(stage="PAUSE_BOUNDARY", code="PAUSE_OUTCOME_UNCERTAIN", *, completed=False):
    progress = acquisition._Progress(stage)
    if completed:
        progress.complete()
    return acquisition._held(progress, acquisition.AcquisitionBlocked(code))


@pytest.mark.parametrize("stage", sorted(acquisition._STAGES))
@pytest.mark.parametrize("completed", [False, True])
def test_closed_boundary_report_always_preserves_effect_uncertainty(stage, completed):
    report = held_report(stage, completed=completed)
    assert acquisition._failure_report(acquisition.canonical(report)) == report
    assert report["provider_effects"] == "NOT_ESTABLISHED"
    assert report["restore_admitted"] is report["deployment_admitted"] is False
    assert report["stage_state"] == ("COMPLETION_OBSERVED" if completed else "BOUNDARY_ENTERED")


@pytest.mark.parametrize("code", [PRIVATE_FAILURE, "TOKEN_" + "A" * 64,
    "https://private.invalid/token", "PAUSE_OUTCOME_UNCERTAIN\n" + PRIVATE_FAILURE])
def test_exception_regex_shape_or_private_message_never_becomes_a_diagnostic(code):
    report = acquisition._held(acquisition._Progress("WORKER_EXECUTION"), RuntimeError(code))
    assert report["diagnostic_code"] == "CANONICAL_ACQUISITION_UNAVAILABLE"
    assert code.encode() not in acquisition.canonical(report)


def test_exception_string_and_attribute_serializers_are_not_invoked():
    class HostileError(RuntimeError):
        @property
        def args(self):
            raise AssertionError("exception property must not be called")
        def __str__(self):
            raise AssertionError("exception must not be formatted")
    report = acquisition._held(acquisition._Progress("WORKER_EXECUTION"), HostileError(PRIVATE_FAILURE))
    assert report["diagnostic_code"] == "CANONICAL_ACQUISITION_UNAVAILABLE"


@pytest.mark.parametrize("field,value", [
    ("schema", "unknown"), ("state", "BOOTSTRAP_ACKNOWLEDGED"), ("stage", PRIVATE_FAILURE),
    ("stage_state", "NO_EFFECTS_OCCURRED"), ("diagnostic_code", PRIVATE_FAILURE),
    ("diagnostic_code", "TOKEN_" + "A" * 64), ("provider_effects", "NONE"),
    ("restore_admitted", True), ("restore_admitted", 0), ("deployment_admitted", True),
    ("secret_values_recorded", True), ("private_payload", PRIVATE_FAILURE),
])
def test_parent_rejects_unknown_fields_values_or_any_admission_flag(field, value):
    report = held_report(); report[field] = value
    with pytest.raises(acquisition.AcquisitionBlocked, match="WORKER_FAILURE_REPORT_INVALID") as caught:
        acquisition._WorkerHeld(acquisition.canonical(report))
    assert PRIVATE_FAILURE not in str(caught.value)


@pytest.mark.parametrize("raw", [b"not-json", b"{}", b"[]", b"{\"stage\":NaN}",
    b"x" * (acquisition.MAX_LOCATOR_BYTES + 1), b"\xff\xfe"])
def test_parent_rejects_malformed_or_oversized_failure_stdout(raw):
    with pytest.raises(acquisition.AcquisitionBlocked, match="WORKER_FAILURE_REPORT_INVALID"):
        acquisition._WorkerHeld(raw)


def test_parent_rejects_duplicate_noncanonical_or_extra_output():
    raw = acquisition.canonical(held_report())
    for changed in (raw + PRIVATE_FAILURE.encode(), b" " + raw,
                    raw.replace(b'"state":"HELD"', b'"state":"HELD","state":"HELD"')):
        with pytest.raises(acquisition.AcquisitionBlocked, match="WORKER_FAILURE_REPORT_INVALID"):
            acquisition._WorkerHeld(changed)


def invalid_worker_request():
    return {"source_artifact_id": 0, "source_artifact_sha256": "a" * 64,
        "qualification_artifact_id": 1, "qualification_artifact_sha256": "b" * 64,
        "publisher_script": PRIVATE_FAILURE}


def test_worker_trusted_logical_roots_validate_retained_artifacts(tmp_path, monkeypatch):
    import subprocess
    import sys
    from scripts import probe_gdw_runtime_base as base

    for name in ("HF_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GDW_PROOF_DIR", str(tmp_path / "untrusted-proofs"))
    monkeypatch.setenv("GDW_RECEIPT_PROJECTION_DIR", str(tmp_path / "untrusted-receipts"))
    code = r'''import socket, sys
network = []
def deny(*args, **kwargs):
    network.append('blocked')
    raise AssertionError('network disabled before target imports')
socket.socket = socket.create_connection = socket.getaddrinfo = deny
def audit(event, args):
    if event.startswith('socket.'):
        deny()
sys.addaudithook(audit)
import hashlib, json, os, sqlite3, time
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root), str(root / 'scripts')]
from gdw_workspace import GDWWorkspace, _SCHEMA_STATEMENTS, SCHEMA_VERSION
from gdw_durable_artifacts import ArtifactCache, LOGICAL_ROOTS
from gdw_durable_runtime import DurableStorageUnavailable
from scripts import acquire_gdw_durable_storage as acquisition

os.umask(0o077)
directory = Path.cwd()
database = directory / 'synthetic.sqlite3'
owner = 'synthetic-owner'
scope = hashlib.sha256(owner.encode()).hexdigest()[:32]
payload = {'proposal_id': 'synthetic-proof', 'namespace': 'synthetic', 'owner_id': owner,
           'database_generation_id': 'a' * 32, 'synthetic': True}
identity = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
payload['payload_sha256'] = identity
encoded = (json.dumps(payload, indent=2, sort_keys=True) + '\n').encode()
digest = hashlib.sha256(encoded).hexdigest()
logical = LOGICAL_ROOTS['proof_export'] / scope / (identity + '.json')
artifact = {'path': str(logical), 'artifact_identity': identity, 'owner_scope': scope,
            'immutable': True, 'sha256': digest, 'size': len(encoded)}
timestamp = '2026-01-01T00:00:00+00:00'
with sqlite3.connect(database) as connection:
    for statement in _SCHEMA_STATEMENTS:
        connection.execute(statement)
    connection.execute('INSERT INTO schema_meta VALUES(?,?,?,?,?)',
                       ('gdw', SCHEMA_VERSION, 'a' * 32, timestamp, timestamp))
    connection.execute('INSERT INTO proof_outbox VALUES(?,?,?,?,?,?,?,?,?,?)',
        ('synthetic', owner, payload['proposal_id'], json.dumps(payload), identity,
         'EXPORTED', json.dumps(artifact), timestamp, timestamp, None))
before = hashlib.sha256(database.read_bytes()).hexdigest()
cache_directory = directory / 'cache'
cache_directory.mkdir(mode=0o700)
calls = []
def publish(path, object_path, sha256, deadline):
    data = path.read_bytes()
    assert data == encoded and sha256 == digest
    calls.append(object_path)
    return {'path': object_path, 'sha256': sha256, 'size': len(data), 'xet_hash': 'b' * 64}
cache = ArtifactCache(cache_directory, publish)
result = None
error_code = None
safe_code = None
try:
    result = cache.prepare(database, time.monotonic() + 30)
except DurableStorageUnavailable as error:
    error_code = error.args[0]
    safe_code = acquisition._safe_code(error)
physical = cache.resolve(logical)
binding_errors = GDWWorkspace.artifact_binding_errors(
    {'kind': 'proof_export', 'owner_id': owner, 'intent_sha256': identity},
    artifact, physical_path=physical)
receipt_artifact = dict(artifact, path=str(LOGICAL_ROOTS['receipt_projection'] / scope / (identity + '.json')))
receipt_binding_errors = GDWWorkspace.artifact_binding_errors(
    {'kind': 'receipt_projection', 'owner_id': owner, 'intent_sha256': identity},
    receipt_artifact, physical_path=physical)
assert hashlib.sha256(database.read_bytes()).hexdigest() == before
assert not network
print(json.dumps({'case': sys.argv[2], 'error_code': error_code, 'safe_code': safe_code,
    'result': result, 'proof_binding_errors': binding_errors,
    'receipt_binding_errors': receipt_binding_errors, 'mock_publication_calls': len(calls),
    'synthetic_database_unchanged': True, 'network_attempts': len(network), 'actual_provider_calls': 0}))
'''
    observed = []
    class EnvironmentChecked(Exception):
        pass

    def transport(*args, **kwargs):
        # Keep the native parent's sanitized environment and private cwd; only
        # replace the provider worker with a synthetic retained-artifact check.
        result = subprocess.run([sys.executable, "-I", "-B", "-c", code,
            str(acquisition.ROOT), "configured_worker"], env=kwargs["env"], cwd=kwargs["cwd"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        assert result.returncode == 0, result.stderr.decode()
        assert result.stderr == b""
        value = json.loads(result.stdout)
        assert value["error_code"] is value["safe_code"] is None
        assert value["proof_binding_errors"] == value["receipt_binding_errors"] == []
        assert value["result"] == {"verified_count": 1, "reconstructed_count": 1,
            "reconstruction": "RECONSTRUCTED_FROM_RETAINED_PAYLOAD"}
        assert value["mock_publication_calls"] == 1
        assert value["synthetic_database_unchanged"] is True
        assert value["network_attempts"] == value["actual_provider_calls"] == 0
        observed.append(value)
        raise EnvironmentChecked()

    monkeypatch.setattr(base, "_run", transport)
    with pytest.raises(EnvironmentChecked):
        acquisition.run_native({})
    assert len(observed) == 1


def test_actual_worker_exit2_propagates_only_closed_held_report(monkeypatch):
    # Invalid selector fails before native imports/provider operations. This
    # launches the actual --worker in its private temporary cwd and uses the
    # real bounded subprocess runner, not a mocked success transport.
    for name in ("HF_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(acquisition._WorkerHeld) as caught:
        acquisition.run_native(invalid_worker_request())
    report = caught.value.report
    assert report["stage"] == "WORKER_REQUEST" and report["stage_state"] == "BOUNDARY_ENTERED"
    assert report["diagnostic_code"] == "ACQUISITION_ARTIFACT_INVALID"
    assert report["provider_effects"] == "NOT_ESTABLISHED"
    assert PRIVATE_FAILURE not in repr(caught.value) + str(caught.value) + repr(caught.value.args)


def test_actual_cli_writes_only_safe_failure_and_exits2(tmp_path):
    import subprocess
    import sys
    target = tmp_path / "gdw-durable-acquisition.json"
    result = subprocess.run([sys.executable, "-B", acquisition.__file__, "--acquire",
        "--source-artifact-id", "0", "--source-artifact-sha256", "a" * 64,
        "--qualification-artifact-id", "1", "--qualification-artifact-sha256", "b" * 64,
        "--publisher-script", PRIVATE_FAILURE, "--output", str(target)],
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    assert result.returncode == 2 and result.stderr == b""
    report = acquisition._failure_report(target.read_bytes())
    assert json.loads(result.stdout) == report
    assert report["stage"] == "WORKER_REQUEST"
    assert PRIVATE_FAILURE.encode() not in result.stdout + target.read_bytes()


def test_outer_report_revalidates_mutated_worker_exception(tmp_path, monkeypatch, capsys):
    error = acquisition._WorkerHeld(acquisition.canonical(held_report()))
    error.report["private_payload"] = PRIVATE_FAILURE
    monkeypatch.setattr(acquisition, "run_native", lambda *_a, **_k: (_ for _ in ()).throw(error))
    target = tmp_path / "gdw-durable-acquisition.json"
    assert acquisition.main(["--acquire", "--output", str(target)]) == 2
    report = acquisition._failure_report(target.read_bytes())
    assert report["diagnostic_code"] == "WORKER_FAILURE_REPORT_INVALID"
    assert PRIVATE_FAILURE not in capsys.readouterr().out


def test_lost_cas_report_identifies_entered_boundary_without_claiming_no_effect(native_acquisition):
    state = native_acquisition
    state.api.lost_commit = True
    progress = acquisition._Progress("PAIR_VALIDATION")
    with pytest.raises(storage.StorageBlocked) as caught:
        acquisition.acquire_pair(state.api, _progress=progress, **state.arguments)
    report = acquisition._held(progress, caught.value)
    assert report["stage"] == "BOOTSTRAP_BOUNDARY"
    assert report["stage_state"] == "BOUNDARY_ENTERED"
    assert report["diagnostic_code"] == "STORAGE_OUTCOME_UNCERTAIN"
    assert report["provider_effects"] == "NOT_ESTABLISHED"
    assert len(state.api.commits) == 1 and storage.HEAD_PATH in state.api.repositories[state.api.revision]


@pytest.mark.parametrize("complete", [False, True])
def test_native_worker_suppresses_private_streams_and_reports_only_owned_phase(tmp_path, complete):
    import subprocess
    import sys
    script = Path(acquisition.__file__).resolve()
    # This owned harness replaces only the effectful execution function. The
    # actual worker request validation, private FD suppression, exception
    # decoder, stdout serialization and exit2 are exercised in a new process.
    code = """import os,runpy,sys
from pathlib import Path
script=Path(sys.argv[1])
sys.path[:0]=[str(script.parent),str(script.parent.parent)]
ns=runpy.run_path(str(script),run_name='owned_offline_worker')
def fail(request,workspace,deadline,*,_progress):
    _progress.enter('BOOTSTRAP_BOUNDARY')
    if sys.argv[2]=='1': _progress.complete()
    print('PRIVATE_SYNTHETIC_TOKEN_URL_SQL_NOT_FOR_PUBLIC_OUTPUT',flush=True)
    os.write(2,b'PRIVATE_SYNTHETIC_TOKEN_URL_SQL_NOT_FOR_PUBLIC_OUTPUT')
    raise ns['AcquisitionBlocked']('STORAGE_OUTCOME_UNCERTAIN')
worker=ns['_worker']
worker.__globals__['_execute_native']=fail
raise SystemExit(worker())
"""
    request = dict(invalid_worker_request(), source_artifact_id=1, deadline=time.monotonic() + 20)
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(script), "1" if complete else "0"],
        input=acquisition.canonical(request), cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    assert result.returncode == 2 and result.stderr == b""
    report = acquisition._failure_report(result.stdout)
    assert report["stage"] == "BOOTSTRAP_BOUNDARY" and report["provider_effects"] == "NOT_ESTABLISHED"
    assert report["stage_state"] == ("COMPLETION_OBSERVED" if complete else "BOUNDARY_ENTERED")
    assert report["diagnostic_code"] == "STORAGE_OUTCOME_UNCERTAIN"
    assert PRIVATE_FAILURE.encode() not in result.stdout
    assert list(tmp_path.iterdir()) == []


def inspection_report(classification="UNAVAILABLE"):
    from scripts import inspect_gdw_62ca_acquisition as inspection
    return inspection._report("b" * 40, classification,
        revision="c" * 40 if classification in {"ABSENT", "ACKNOWLEDGED"} else None,
        head_digest="d" * 64 if classification == "ACKNOWLEDGED" else None,
        admission_digest="e" * 64 if classification == "ACKNOWLEDGED" else None, prior_verified=True)


@pytest.mark.parametrize("classification", ["ABSENT", "ACKNOWLEDGED", "INVALID", "UNAVAILABLE"])
def test_inspection_exit2_remains_held_even_with_acknowledged_metadata(tmp_path, monkeypatch, capsys, classification):
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    report = inspection_report(classification)
    error = acquisition._InspectionHeld(acquisition.canonical(report))
    monkeypatch.setattr(acquisition, "run_native", lambda *_a, **_k: (_ for _ in ()).throw(error))
    target = tmp_path / "gdw-durable-acquisition.json"
    assert acquisition.main(["--inspect-held-acquisition", "--output", str(target)]) == 2
    assert acquisition._inspection_report(target.read_bytes()) == report
    assert json.loads(capsys.readouterr().out) == report
    assert all(report[key] is False for key in ("retry_admitted", "restore_admitted", "deployment_admitted"))


@pytest.mark.parametrize("defect", ["other_source", "false_numeric", "extra", "oversize", "noncanonical", "locator"])
def test_inspection_parent_rejects_wrong_source_noncanonical_or_noninspection_output(monkeypatch, defect):
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    report = inspection_report()
    if defect == "other_source": report["source_revision"] = "a" * 40
    if defect == "false_numeric": report["retry_admitted"] = 0
    if defect == "extra": report["private"] = PRIVATE_FAILURE
    raw = acquisition.canonical(report)
    if defect == "oversize": raw += b" " * 4097
    if defect == "noncanonical": raw = b" " + raw
    if defect == "locator":
        record, head = fixture(); raw = acquisition.canonical(acquisition.locator_for_bootstrap(head, record))
    with pytest.raises(acquisition.AcquisitionBlocked, match="WORKER_FAILURE_REPORT_INVALID"):
        acquisition._InspectionHeld(raw)


@pytest.mark.parametrize("option,value", [
    ("--source-artifact-id", "1"), ("--source-artifact-sha256", "a" * 64),
    ("--qualification-artifact-id", "1"), ("--qualification-artifact-sha256", "a" * 64),
    ("--acquisition-artifact-id", "1"), ("--acquisition-artifact-sha256", "a" * 64),
    ("--publisher-script", PRIVATE_FAILURE), ("--preservation", PRIVATE_FAILURE),
    ("--qualification", PRIVATE_FAILURE), ("--github-output", PRIVATE_FAILURE),
])
def test_inspection_cli_rejects_every_other_mode_input_before_worker(tmp_path, monkeypatch, capsys, option, value):
    monkeypatch.setattr(acquisition, "run_native", lambda *_a, **_k: pytest.fail("override reached worker"))
    target = tmp_path / "gdw-durable-acquisition.json"
    assert acquisition.main(["--inspect-held-acquisition", option, value, "--output", str(target)]) == 2
    assert acquisition._failure_report(target.read_bytes())["diagnostic_code"] == "ACQUISITION_REQUEST_INVALID"
    assert PRIVATE_FAILURE not in capsys.readouterr().out


def test_inspection_parent_enforces_120_seconds_closed_request_and_nonzero_result(monkeypatch):
    from scripts import probe_gdw_runtime_base as base
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    observed = {}
    def transport(*args, **kwargs):
        observed.update(kwargs)
        raise base._CommandFailed(acquisition.canonical(inspection_report("ABSENT")))
    monkeypatch.setattr(base, "_run", transport)
    start = time.monotonic()
    with pytest.raises(acquisition._InspectionHeld): acquisition.run_native({}, _inspect_only=True)
    request = json.loads(observed["input_bytes"])
    assert set(request) == {"mode", "deadline"} and request["mode"] == "INSPECT_HELD"
    assert 119 <= observed["deadline"] - start <= 120.1
    assert observed["deadline"] - request["deadline"] == 5
    assert observed["_capture_failure"] is True
    monkeypatch.setattr(base, "_run", lambda *_a, **_k: acquisition.canonical(inspection_report()))
    with pytest.raises(acquisition.AcquisitionBlocked, match="WORKER_FAILURE_REPORT_INVALID"):
        acquisition.run_native({}, _inspect_only=True)
    with pytest.raises(acquisition.AcquisitionBlocked, match="ACQUISITION_REQUEST_INVALID"):
        acquisition.run_native({"source": "override"}, _inspect_only=True)


def test_actual_inspection_worker_suppresses_streams_and_cannot_dispatch_acquisition(tmp_path, monkeypatch):
    import subprocess
    import sys
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    script = Path(acquisition.__file__).resolve()
    code = """import os,runpy,sys
from pathlib import Path
script=Path(sys.argv[1]); sys.path[:0]=[str(script.parent),str(script.parent.parent)]
import inspect_gdw_62ca_acquisition as inspection
ns=runpy.run_path(str(script),run_name='owned_offline_worker')
def inspect(workspace,deadline):
    print('PRIVATE_SYNTHETIC_TOKEN_URL_SQL_NOT_FOR_PUBLIC_OUTPUT',flush=True)
    os.write(2,b'PRIVATE_SYNTHETIC_TOKEN_URL_SQL_NOT_FOR_PUBLIC_OUTPUT')
    return inspection._report('b'*40,'ABSENT',revision='c'*40,prior_verified=True)
def forbidden(*a,**k): raise AssertionError('acquisition must not execute')
inspection.execute_native_inspection=inspect
worker=ns['_worker']; worker.__globals__['_execute_native']=forbidden
raise SystemExit(worker())
"""
    request = {"mode": "INSPECT_HELD", "deadline": time.monotonic() + 20}
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(script)],
        input=acquisition.canonical(request), cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    assert result.returncode == 2 and result.stderr == b""
    assert acquisition._inspection_report(result.stdout) == inspection_report("ABSENT")
    assert PRIVATE_FAILURE.encode() not in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_actual_inspection_cli_without_native_authority_holds_before_provider(tmp_path):
    import subprocess
    import sys
    target = tmp_path / "gdw-durable-acquisition.json"
    result = subprocess.run([sys.executable, "-B", acquisition.__file__, "--inspect-held-acquisition",
        "--output", str(target)], cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    assert result.returncode == 2 and result.stderr == b""
    report = acquisition._failure_report(target.read_bytes())
    assert report["stage"] == "HELD_ACQUISITION_INSPECTION"
    assert report["diagnostic_code"] == "CANONICAL_CONTEXT_REQUIRED"
    assert json.loads(result.stdout) == report


def supervised_report(monkeypatch):
    from scripts import reconcile_gdw_supervised_acquisition as reconciliation
    context = {"source_revision": "b" * 40, "run_id": 123, "run_attempt": 1,
        "job_id": 456, "job_key": "recovery-reconciliation"}
    for key, value in {"GITHUB_SHA": context["source_revision"], "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": context["job_key"]}.items():
        monkeypatch.setenv(key, value)
    return reconciliation._report(context)


def test_reconciliation_parent_accepts_only_bound_exit0_under_120_seconds(monkeypatch):
    from scripts import probe_gdw_runtime_base as base
    from gdw_durable_artifacts import LOGICAL_ROOTS
    report = supervised_report(monkeypatch)
    observed = {}
    def transport(*args, **kwargs):
        observed.update(kwargs)
        return acquisition.canonical(report)
    monkeypatch.setattr(base, "_run", transport)
    start = time.monotonic()
    assert acquisition.run_native({}, _reconcile_only=True) == report
    request = json.loads(observed["input_bytes"])
    assert set(request) == {"mode", "deadline"} and request["mode"] == "RECONCILE_SUPERVISED"
    assert 119 <= observed["deadline"] - start <= 120.1
    assert observed["deadline"] - request["deadline"] == 5
    assert observed["_capture_failure"] is True
    assert set(observed["env"]) <= {"HF_TOKEN", "GH_TOKEN", "GITHUB_ACTIONS", "GITHUB_REPOSITORY",
        "GITHUB_REPOSITORY_ID", "GITHUB_REF", "GITHUB_SHA", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA",
        "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME", "GITHUB_JOB", "PATH", "PYTHONDONTWRITEBYTECODE",
        "GDW_PROOF_DIR", "GDW_RECEIPT_PROJECTION_DIR"}
    assert observed["env"]["GDW_PROOF_DIR"] == str(LOGICAL_ROOTS["proof_export"])
    assert observed["env"]["GDW_RECEIPT_PROJECTION_DIR"] == str(LOGICAL_ROOTS["receipt_projection"])
    def exit2(*_a, **_k): raise base._CommandFailed(acquisition.canonical(report))
    monkeypatch.setattr(base, "_run", exit2)
    with pytest.raises(acquisition.AcquisitionBlocked, match="WORKER_FAILURE_REPORT_INVALID"):
        acquisition.run_native({}, _reconcile_only=True)
    for request, options in (({"source": "override"}, {"_reconcile_only": True}),
        ({}, {"_inspect_only": True, "_reconcile_only": True})):
        with pytest.raises(acquisition.AcquisitionBlocked, match="ACQUISITION_REQUEST_INVALID"):
            acquisition.run_native(request, **options)


@pytest.mark.parametrize("defect", ["source", "run", "attempt", "job", "extra", "numeric_flag", "locator", "noncanonical"])
def test_reconciliation_parent_rejects_unbound_or_admitting_outputs(monkeypatch, defect):
    report = supervised_report(monkeypatch)
    if defect == "source": report["source_revision"] = "c" * 40
    if defect == "run": report["run_id"] = 124
    if defect == "attempt": report["run_attempt"] = 2
    if defect == "job": report["job_key"] = "durable-acquisition"
    if defect == "extra": report["private"] = PRIVATE_FAILURE
    if defect == "numeric_flag": report["restore_admitted"] = 0
    raw = acquisition.canonical(report)
    if defect == "locator":
        record, head = fixture(); raw = acquisition.canonical(acquisition.locator_for_bootstrap(head, record))
    if defect == "noncanonical": raw = b" " + raw
    with pytest.raises(acquisition.AcquisitionBlocked, match="WORKER_FAILURE_REPORT_INVALID"):
        acquisition._reconciliation_report(raw)


def test_reconciliation_cli_emits_admitted_only_after_validated_success(tmp_path, monkeypatch):
    report = supervised_report(monkeypatch)
    monkeypatch.setattr(acquisition, "run_native", lambda *_a, **_k: report)
    output, decision = tmp_path / "reconciliation.json", tmp_path / "github-output"
    assert acquisition.main(["--reconcile-supervised-acquisition", "--output", str(output),
        "--github-output", str(decision)]) == 0
    assert output.read_bytes() == acquisition.canonical(report)
    assert decision.read_text() == "admitted=true\n"
    assert report["restore_admitted"] is report["deployment_admitted"] is False


@pytest.mark.parametrize("option,value", [
    ("--source-artifact-id", "1"), ("--source-artifact-sha256", "a" * 64),
    ("--qualification-artifact-id", "1"), ("--qualification-artifact-sha256", "a" * 64),
    ("--acquisition-artifact-id", "1"), ("--acquisition-artifact-sha256", "a" * 64),
    ("--publisher-script", PRIVATE_FAILURE), ("--preservation", PRIVATE_FAILURE),
    ("--qualification", PRIVATE_FAILURE),
])
def test_reconciliation_cli_overrides_hold_without_admitted_output(tmp_path, monkeypatch, option, value):
    monkeypatch.setattr(acquisition, "run_native", lambda *_a, **_k: pytest.fail("override reached worker"))
    output, decision = tmp_path / "held.json", tmp_path / "github-output"
    assert acquisition.main(["--reconcile-supervised-acquisition", option, value, "--output", str(output),
        "--github-output", str(decision)]) == 2
    assert acquisition._failure_report(output.read_bytes())["diagnostic_code"] == "ACQUISITION_REQUEST_INVALID"
    assert not decision.exists()


@pytest.mark.parametrize("failure", [False, True])
def test_actual_reconciliation_worker_suppresses_private_streams_and_never_acquires(tmp_path, monkeypatch, failure):
    import subprocess
    import sys
    report = supervised_report(monkeypatch)
    script = Path(acquisition.__file__).resolve()
    code = """import os,runpy,sys
from pathlib import Path
script=Path(sys.argv[1]);sys.path[:0]=[str(script.parent),str(script.parent.parent)]
import reconcile_gdw_supervised_acquisition as reconciliation
ns=runpy.run_path(str(script),run_name='owned_offline_worker')
def reconcile(workspace,deadline):
    print('PRIVATE_SYNTHETIC_TOKEN_URL_SQL_NOT_FOR_PUBLIC_OUTPUT',flush=True)
    os.write(2,b'PRIVATE_SYNTHETIC_TOKEN_URL_SQL_NOT_FOR_PUBLIC_OUTPUT')
    if sys.argv[2]=='1': raise reconciliation.SupervisedBlocked('EXPECTED_ABSENCE_UNVERIFIED')
    return reconciliation._report({'source_revision':'b'*40,'run_id':123,'run_attempt':1,'job_id':456,'job_key':'recovery-reconciliation'})
def forbidden(*a,**k):raise AssertionError('acquisition must not execute')
reconciliation.execute_native_reconciliation=reconcile
worker=ns['_worker'];worker.__globals__['_execute_native']=forbidden
raise SystemExit(worker())
"""
    request = {"mode": "RECONCILE_SUPERVISED", "deadline": time.monotonic() + 20}
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(script), "1" if failure else "0"],
        input=acquisition.canonical(request), cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    assert result.returncode == (2 if failure else 0) and result.stderr == b""
    if failure:
        held = acquisition._failure_report(result.stdout)
        assert held["stage"] == "SUPERVISED_RECONCILIATION"
        assert held["diagnostic_code"] == "EXPECTED_ABSENCE_UNVERIFIED"
    else:
        assert acquisition._reconciliation_report(result.stdout) == report
    assert PRIVATE_FAILURE.encode() not in result.stdout and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("code", [
    "ARTIFACT_DATABASE_OPEN_UNAVAILABLE", "ARTIFACT_SCHEMA_VALIDATION_UNAVAILABLE",
    "ARTIFACT_ROW_READ_UNAVAILABLE", "ARTIFACT_ROW_VALIDATION_UNAVAILABLE",
    "ARTIFACT_CACHE_MATERIALIZATION_UNAVAILABLE", "ARTIFACT_NATIVE_BINDING_UNAVAILABLE",
    "ARTIFACT_PROVIDER_CALL_UNAVAILABLE", "ARTIFACT_PROVIDER_READBACK_UNAVAILABLE",
    "ARTIFACT_RECONSTRUCTION_MISMATCH", "ARTIFACT_PUBLICATION_UNVERIFIED",
])
def test_artifact_failure_survives_held_worker_decoder_without_authority(code):
    from gdw_durable_runtime import DurableStorageUnavailable
    report = acquisition._held(acquisition._Progress("ARTIFACT_PUBLICATION"), DurableStorageUnavailable(code))
    raw = acquisition.canonical(report)
    decoded = acquisition._failure_report(raw)
    assert decoded == report
    assert decoded["diagnostic_code"] == code
    assert decoded["provider_effects"] == "NOT_ESTABLISHED"
    assert all(decoded[key] is False for key in ("restore_admitted", "deployment_admitted", "secret_values_recorded"))


def test_all_artifact_failure_codes_are_recognized_without_widening_worker_schema():
    from gdw_durable_artifacts import ARTIFACT_FAILURE_CODES
    assert ARTIFACT_FAILURE_CODES <= acquisition._DIAGNOSTICS
    assert len(acquisition._FAILURE_FIELDS) == 9
