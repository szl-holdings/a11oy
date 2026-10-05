# SPDX-License-Identifier: Apache-2.0
"""Synthetic metadata/SDK boundaries only; no provider or private-store access."""
import copy
import hashlib
import json
from pathlib import Path
import time

import pytest

from scripts import inspect_gdw_held_acquisition as inspection
import gdw_durable_storage as storage
import gdw_durable_startup as startup
from tests.test_gdw_durable_startup import admission


class Evidence:
    source = "c" * 40

    def __init__(self):
        self.calls = []
        self.fail_at = None

    def check(self, name):
        self.calls.append(name)
        if self.fail_at == len(self.calls):
            raise RuntimeError("PRIVATE_TRANSPORT_CANARY")

    def observe_run(self): self.check("run")
    def require_active_acquisition(self): self.check("active")
    def require_current_main(self): self.check("main")


def fixture_record():
    record = json.loads(json.dumps(admission()).replace("b" * 40, inspection.PRIOR_SOURCE))
    context = {"repository": startup.REPOSITORY, "ref": "refs/heads/main",
        "revision": inspection.PRIOR_SOURCE, "workflow_path": startup.WORKFLOW,
        "run_id": inspection.PRIOR_RUN, "run_attempt": inspection.PRIOR_ATTEMPT,
        "job_id": inspection.PRIOR_JOB, "event_name": "push", "source_admission_state": "VERIFIED",
        "source_admission_sha256": inspection.PRIOR_SOURCE_RECEIPT}
    record["source"] = context
    record["qualification"].update(source=dict(context, job_id=inspection.PRIOR_QUALIFICATION_JOB),
        report_sha256=inspection.PRIOR_QUALIFICATION, artifact_id=inspection.PRIOR_ARTIFACT,
        artifact_archive_sha256=inspection.PRIOR_ARCHIVE)
    record["runtime"]["source_manifest_sha256"] = storage.sha256(storage.canonical(record["runtime"]["source_manifest"]))
    record["runtime"]["base_observation"]["execution"].update(run_id=inspection.PRIOR_RUN, run_attempt=1)
    record["latency"].update(run_id=inspection.PRIOR_RUN, run_attempt=1)
    record["provider"]["resource_group_observation_sha256"] = storage.sha256(storage.canonical(None))
    encoded = storage.canonical(record)
    startup.parse_admission(encoded)
    value = {"schema": storage.SCHEMA, "space": storage.SPACE, "dataset": storage.DATASET,
        "bucket": storage.BUCKET, "kind": "BOOTSTRAP", "epoch": 0, "sequence": 0,
        "writer_id": "0" * 32, "operation_id": "a" * 32, "previous_manifest_sha256": None,
        "source_revision": inspection.PRIOR_SOURCE, "snapshots": record["snapshots"],
        "qualification_sha256": storage.sha256(encoded)}
    return record, value


class DatasetAPI:
    endpoint = storage.ENDPOINT

    def __init__(self, record=None, head=None):
        self.calls = []
        self.revision = "e" * 40
        self.files = {}
        self.private = True
        self.changed = False
        self.bad_blob = False
        self.oversize = False
        self.transport_error = False
        if head is not None:
            self.files[storage.HEAD_PATH] = storage.canonical(head)
            self.files[f"{storage.HISTORY_PREFIX}/{head['operation_id']}.json"] = storage.canonical(head)
            self.files[f"{storage.ADMISSION_PREFIX}/{head['qualification_sha256']}.json"] = storage.canonical(record)

    def dataset_info(self, repo_id, *, revision, expand):
        self.calls.append(("dataset_info", revision))
        assert repo_id == storage.DATASET and expand == ["sha", "private", "resourceGroup"]
        if self.transport_error: raise RuntimeError("PRIVATE_TRANSPORT_CANARY")
        result = self.revision
        if self.changed and len(self.calls) > 2 and revision == "main": result = "f" * 40
        return {"id": storage.DATASET, "private": self.private, "sha": result, "resource_group": None}

    def get_paths_info(self, repo_id, paths, *, repo_type, revision):
        assert repo_id == storage.DATASET and repo_type == "dataset" and revision in {self.revision, "f" * 40}
        self.calls.append(("paths", paths[0]))
        if paths[0] not in self.files: return []
        data = self.files[paths[0]]
        digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        return [{"path": paths[0], "size": (storage.MAX_ADMISSION_BYTES + 1 if self.oversize else len(data)),
            "blob_id": ("1" * 40 if self.bad_blob else digest), "lfs": None}]

    def hf_hub_download(self, repo_id, *, filename, repo_type, revision, local_dir, cache_dir):
        assert repo_id == storage.DATASET and repo_type == "dataset" and revision == self.revision
        self.calls.append(("download", filename))
        path = Path(local_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.files[filename])
        return str(path)

    def __getattr__(self, name):
        pytest.fail("unexpected provider method " + name)


def inspect(tmp_path, api, evidence=None):
    tmp_path.chmod(0o700)
    return inspection.inspect_held_acquisition(api, private_directory=tmp_path,
        evidence=evidence or Evidence(), deadline=time.monotonic() + 60)


def test_absence_is_observed_twice_without_download_or_mutation(tmp_path):
    api = DatasetAPI()
    evidence = Evidence()
    report = inspect(tmp_path, api, evidence)
    assert report["classification"] == "ABSENT" and report["dataset_revision"] == api.revision
    assert api.calls == [("dataset_info", "main"), ("paths", storage.HEAD_PATH),
                         ("dataset_info", "main"), ("paths", storage.HEAD_PATH)]
    assert evidence.calls[:3] == ["run", "active", "main"]
    assert evidence.calls[-2:] == ["active", "main"]
    assert inspection.validate_inspection_report(storage.canonical(report)) == report
    assert all(report[key] is False for key in ("retry_admitted", "restore_admitted", "deployment_admitted",
        "provider_objects_verified", "provider_writes_performed", "secret_values_recorded"))


def test_actual_core_reader_validates_bootstrap_history_admission_without_objects(tmp_path):
    record, head = fixture_record()
    api = DatasetAPI(record, head)
    report = inspect(tmp_path, api)
    assert report["classification"] == "ACKNOWLEDGED"
    assert report["head_sha256"] == storage.sha256(storage.canonical(head))
    assert report["admission_sha256"] == head["qualification_sha256"]
    assert report["state"] == "HELD" and report["retry_admitted"] is False
    assert {path for method, path in api.calls if method == "download"} == set(api.files)
    assert inspection.validate_inspection_report(storage.canonical(report)) == report


@pytest.mark.parametrize("defect", ["source", "run", "attempt", "job", "qualification_job", "source_receipt",
    "qualification", "archive", "artifact", "group", "history", "head_shape", "changed", "private",
    "bad_blob", "oversize", "missing_admission", "missing_history", "transport"])
def test_ambiguous_or_unbound_metadata_never_proves_absence_or_retry(tmp_path, defect):
    record, head = fixture_record()
    if defect == "source": head["source_revision"] = "a" * 40
    if defect in {"run", "attempt", "job"}:
        record["source"][{"run": "run_id", "attempt": "run_attempt", "job": "job_id"}[defect]] += 1
    if defect == "qualification_job": record["qualification"]["source"]["job_id"] += 1
    if defect == "source_receipt": record["source"]["source_admission_sha256"] = "a" * 64
    if defect == "qualification": record["qualification"]["report_sha256"] = "a" * 64
    if defect == "archive": record["qualification"]["artifact_archive_sha256"] = "a" * 64
    if defect == "artifact": record["qualification"]["artifact_id"] += 1
    if defect == "group": record["provider"]["resource_group_observation_sha256"] = "a" * 64
    head["qualification_sha256"] = storage.sha256(storage.canonical(record))
    api = DatasetAPI(record, head)
    if defect == "history": api.files[f"{storage.HISTORY_PREFIX}/{head['operation_id']}.json"] = b'{}\n'
    if defect == "head_shape": api.files[storage.HEAD_PATH] = b'{"private":"PRIVATE_ROW_CANARY"}\n'
    if defect == "changed": api.changed = True
    if defect == "private": api.private = False
    if defect == "bad_blob": api.bad_blob = True
    if defect == "oversize": api.oversize = True
    if defect == "missing_admission": del api.files[f"{storage.ADMISSION_PREFIX}/{head['qualification_sha256']}.json"]
    if defect == "missing_history": del api.files[f"{storage.HISTORY_PREFIX}/{head['operation_id']}.json"]
    if defect == "transport": api.transport_error = True
    report = inspect(tmp_path, api)
    assert report["classification"] in {"INVALID", "UNAVAILABLE"}
    assert report["dataset_revision"] is report["head_sha256"] is report["admission_sha256"] is None
    assert "CANARY" not in json.dumps(report)
    assert inspection.validate_inspection_report(storage.canonical(report)) == report


@pytest.mark.parametrize("boundary", [1, 2, 3, 4, 5, 6, 7, 8, 9])
def test_source_or_active_job_failure_at_every_absent_boundary_is_unavailable(tmp_path, boundary):
    evidence = Evidence(); evidence.fail_at = boundary
    report = inspect(tmp_path, DatasetAPI(), evidence)
    assert report["classification"] == "UNAVAILABLE"


@pytest.mark.parametrize("defect", ["extra", "boolean", "bool_id", "float_id", "bytes", "duplicate", "large", "nan", "infinite", "locator"])
def test_parent_report_rejects_untrusted_child_output(defect):
    value = inspection._report("c" * 40, "ABSENT", revision="e" * 40)
    if defect == "extra": value["private"] = "PRIVATE_ROW_CANARY"
    if defect == "boolean": value["provider_writes_performed"] = 0
    if defect == "bool_id": value["prior_run_attempt"] = True
    if defect == "float_id": value["prior_run_attempt"] = 1.0
    if defect == "locator": value["state"] = "BOOTSTRAP_ACKNOWLEDGED"
    raw = storage.canonical(value)
    if defect == "bytes": raw = raw.rstrip()
    if defect == "duplicate": raw = raw[:-2] + b',"state":"HELD"}\n'
    if defect == "large": raw = b" " * 4097
    if defect == "nan": raw = raw.replace(b'"HELD"', b'NaN')
    if defect == "infinite": raw = raw.replace(b'"HELD"', b'1e999')
    with pytest.raises(Exception): inspection.validate_inspection_report(raw)


@pytest.mark.parametrize("method", ["pause_space", "restart_space", "batch_bucket_files", "create_commit",
    "download_bucket_files", "get_bucket_paths_info", "add_space_variable", "get_space_secrets"])
def test_adapter_has_no_provider_effect_or_private_store_method(method):
    reader = inspection.ReadOnlyDataset(DatasetAPI(), lambda: None, time.monotonic() + 60)
    with pytest.raises(AttributeError): getattr(reader, method)
