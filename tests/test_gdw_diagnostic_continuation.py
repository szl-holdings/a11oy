#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline successor tests for the accepted diagnostic-bound continuation."""

import ast
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import time

import pytest

import gdw_durable_storage as storage
from scripts import acquire_gdw_durable_storage as acquisition
from scripts import reconcile_gdw_diagnostic_continuation as continuation
from scripts import triage_gdw_artifacts_readonly as triage
from tests.test_gdw_durable_acquisition import cli_sibling_modules, native_acquisition
from tests.test_gdw_durable_runtime import stores


def diagnostic_report():
    return {
        "artifact_effect_observation": {
            "all_retained_rows_validated": True, "candidate_unchanged": True,
            "classification": "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME",
            "expected_object_count": continuation.EXPECTED_OBJECT_COUNT,
            "expected_object_set_sha256": continuation.EXPECTED_OBJECT_SET_SHA256,
            "historical_writer_attribution": "NOT_ESTABLISHED",
            "missing_object_count": continuation.EXPECTED_OBJECT_COUNT,
            "observed_object_set_sha256": continuation.EMPTY_OBJECT_SET_SHA256,
            "present_object_count": 0, "provider_objects_fully_validated": False,
            "provider_writes_performed": False},
        "capture_qualification": "LOGICAL_CONTINUITY_VERIFIED",
        "captured_originals_unchanged_during_qualification": True,
        "deployment_admitted": False,
        "diagnostic_code": "READ_ONLY_OBSERVATION_COMPLETE",
        "historical_writer_attribution": "NOT_ESTABLISHED",
        "metadata_stable_during_read": True,
        "prior_acquisition_archive_sha256": triage.PRIOR_ARTIFACT_SHA256,
        "prior_acquisition_artifact_id": triage.PRIOR_ARTIFACT,
        "prior_acquisition_report_sha256": triage.PRIOR_REPORT_SHA256,
        "prior_job_id": triage.PRIOR_JOB,
        "prior_native_metadata_verified": True,
        "prior_provider_effects": "NOT_ESTABLISHED",
        "prior_run_attempt": triage.PRIOR_ATTEMPT,
        "prior_run_id": triage.PRIOR_RUN,
        "prior_source_revision": triage.PRIOR_SOURCE,
        "prior_stage": "ARTIFACT_PUBLICATION", "prior_stage_state": "BOUNDARY_ENTERED",
        "private_bytes_reported": False,
        "private_head_metadata": {"head_presence": "ABSENT",
                                  "revision": continuation.DIAGNOSTIC_DATASET_REVISION},
        "provider_writes_performed": False, "qualified_database_count": 2,
        "read_boundary": "COMPLETE", "restore_admitted": False,
        "retry_admitted": False, "run_attempt": 1,
        "run_id": continuation.DIAGNOSTIC_RUN, "schema": triage.SCHEMA,
        "source_revision": continuation.DIAGNOSTIC_SOURCE, "state": "OBSERVED"}


def reconciliation_report(source="a" * 40, qualification_sha256="b" * 64,
                          dataset_revision="c" * 40):
    context = {"source_revision": source, "run_id": 900, "run_attempt": 1,
               "job_id": 901, "job_key": continuation.RECONCILIATION_JOB_KEY}
    return continuation._report(context, qualification_sha256, dataset_revision)


def test_embedded_diagnostic_receipt_is_the_exact_accepted_closed_record():
    raw = storage.canonical(diagnostic_report())
    assert len(raw) == 1814
    assert hashlib.sha256(raw).hexdigest() == continuation.DIAGNOSTIC_REPORT_SHA256
    assert continuation.validate_diagnostic_report(raw) == diagnostic_report()


@pytest.mark.parametrize("path,value", [
    (("source_revision",), "0" * 40),
    (("prior_provider_effects",), "NONE"),
    (("private_head_metadata", "head_presence"), "PRESENT"),
    (("artifact_effect_observation", "present_object_count"), 1),
    (("artifact_effect_observation", "classification"), "ALL_EXPECTED_OBJECTS_PRESENT_AND_VALIDATED_AT_READ_TIME"),
    (("retry_admitted",), True),
])
def test_diagnostic_tampering_never_admits_continuation(path, value):
    report = diagnostic_report()
    target = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(continuation.ContinuationBlocked):
        continuation.validate_diagnostic_report(storage.canonical(report))


def test_reconciliation_and_classification_are_canonical_nonadmitting_records():
    qualification = storage.canonical({"schema": "fixture", "state": "QUALIFIED"})
    report = reconciliation_report(qualification_sha256=hashlib.sha256(qualification).hexdigest())
    raw = storage.canonical(report)
    assert continuation.validate_reconciliation_report(raw) == report
    classified = continuation.classify_reconciliation(raw, qualification, "a" * 40)
    assert classified["mode"] == "managed-recovery"
    assert classified["provider_writes_performed"] is False
    assert classified["replay_admitted"] is False
    assert classified["restore_admitted"] is classified["deployment_admitted"] is False


def test_reconciliation_main_persists_both_success_receipts(monkeypatch, tmp_path):
    qualification = storage.canonical({"schema": "fixture", "state": "QUALIFIED"})
    report = reconciliation_report(
        qualification_sha256=hashlib.sha256(qualification).hexdigest())
    monkeypatch.setattr(continuation, "execute_native_reconciliation",
        lambda *_args: (report, qualification))
    output = tmp_path / "reconciliation.json"
    qualification_output = tmp_path / "qualification.json"
    github_output = tmp_path / "github-output"

    status = continuation.main(["--reconcile", "--github-output", str(github_output),
        "--output", str(output), "--qualification-output", str(qualification_output)])

    assert status == 0
    assert output.read_bytes() == storage.canonical(report)
    assert qualification_output.read_bytes() == qualification
    assert github_output.read_text(encoding="ascii") == "admitted=true\n"


def test_reconciliation_main_persists_safe_held_receipt(monkeypatch, tmp_path):
    def held(*_args):
        raise continuation.ContinuationBlocked(
            "CURRENT_ABSENCE_UNVERIFIED", "CAPTURE_LOGICAL_CONTINUITY")

    monkeypatch.setattr(continuation, "execute_native_reconciliation", held)
    output = tmp_path / "held.json"
    github_output = tmp_path / "github-output"
    qualification_output = tmp_path / "qualification.json"
    status = continuation.main(["--reconcile", "--github-output", str(github_output),
        "--output", str(output), "--qualification-output", str(qualification_output)])

    assert status == 2
    receipt = json.loads(output.read_bytes())
    assert receipt["state"] == "HELD"
    assert receipt["diagnostic_code"] == "CURRENT_ABSENCE_UNVERIFIED"
    assert receipt["diagnostic_stage"] == "CAPTURE_LOGICAL_CONTINUITY"
    assert all(receipt[key] is False for key in ("provider_writes_performed",
        "replay_admitted", "restore_admitted", "deployment_admitted",
        "secret_values_recorded"))
    assert set(receipt) == {"schema", "state", "diagnostic_code", "diagnostic_stage",
        "provider_writes_performed", "replay_admitted", "restore_admitted",
        "deployment_admitted", "secret_values_recorded"}
    assert not qualification_output.exists()
    assert not github_output.exists()


@pytest.mark.parametrize("field,value", [
    ("scope", "RETRY"), ("diagnostic_run_id", 1), ("head_presence", "PRESENT"),
    ("dataset_revision", "main"),
    ("expected_object_count", 223), ("provider_writes_performed", True),
    ("replay_admitted", True), ("restore_admitted", True),
])
def test_reconciliation_report_rejects_every_authority_or_receipt_change(field, value):
    report = reconciliation_report()
    report[field] = value
    with pytest.raises(continuation.ContinuationBlocked):
        continuation.validate_reconciliation_report(storage.canonical(report))


class FenceAPI:
    endpoint = storage.ENDPOINT

    def __init__(self):
        self.objects = {}
        self.revision = "c" * 40

    def dataset_info(self, repo_id, *, revision, expand):
        return {"id": storage.DATASET, "private": True,
                "sha": self.revision}

    def get_paths_info(self, repo_id, paths, *, repo_type, revision):
        return []

    def get_bucket_paths_info(self, *, bucket_id, paths):
        result = []
        for path in paths:
            if path in self.objects:
                size, xet = self.objects[path]
                result.append({"path": path, "type": "file", "size": size,
                               "xet_hash": xet})
        return (item for item in result)


class Evidence:
    def __init__(self):
        self.calls = 0

    def require_current_main(self):
        self.calls += 1


def synthetic_pending(count=continuation.EXPECTED_OBJECT_COUNT):
    pending = {}
    for index in range(count):
        owner = f"{index:064x}"
        digest = hashlib.sha256(str(index).encode()).hexdigest()
        path = f"{storage.ARTIFACT_PREFIX}/{owner}/{digest}.json"
        pending[path] = (Path(f"/private/{index}"), digest, index + 1)
    return pending


def test_fence_proves_all_paths_absent_then_accepts_only_its_exact_ack(monkeypatch, tmp_path):
    api, evidence = FenceAPI(), Evidence()
    pending = synthetic_pending()
    plan = {"expected_object_count": continuation.EXPECTED_OBJECT_COUNT,
            "expected_object_set_sha256": continuation.EXPECTED_OBJECT_SET_SHA256,
            "candidate_unchanged": True, "all_retained_rows_validated": True}
    monkeypatch.setattr(triage, "local_artifact_plan", lambda *_a, **_k: (pending, plan))
    directory = tmp_path / "fence"; directory.mkdir(mode=0o700)
    fence = continuation.DiagnosticContinuationFence(api, evidence,
        time.monotonic() + 30, directory, api.revision)
    fence.bind_candidate(tmp_path / "candidate.sqlite3")
    path, (_physical, digest, size) = next(iter(pending.items()))
    fence.before_artifact(path, digest, size)
    fence.begin_artifact_add(path)
    api.objects[path] = (size, "c" * 64)
    fence.complete_artifact_add(path)
    fence.acknowledge_artifact({"path": path, "sha256": digest,
                               "size": size, "xet_hash": "c" * 64})
    fence.before_artifact(path, digest, size)
    fence.acknowledge_artifact({"path": path, "sha256": digest,
                               "size": size, "xet_hash": "c" * 64})
    api.objects[path] = (size, "d" * 64)
    with pytest.raises(continuation.ContinuationBlocked):
        fence.before_artifact(path, digest, size)
    assert evidence.calls >= 10


def test_fence_artifact_reader_accepts_sdk_shaped_empty_and_present_generators(tmp_path):
    api, evidence = FenceAPI(), Evidence()
    directory = tmp_path / "fence"; directory.mkdir(mode=0o700)
    fence = continuation.DiagnosticContinuationFence(api, evidence,
        time.monotonic() + 30, directory, api.revision)
    path = f"{storage.ARTIFACT_PREFIX}/{'a' * 64}/{'b' * 64}.json"
    assert fence._artifact(path) is None
    api.objects[path] = (17, "c" * 64)
    assert fence._artifact(path) == {
        "path": path, "type": "file", "size": 17, "xet_hash": "c" * 64}


@pytest.mark.parametrize("present", [False, True])
def test_fence_artifact_reader_uses_official_hf_131_mock_transport(tmp_path, present):
    huggingface_hub = pytest.importorskip("huggingface_hub")
    httpx = pytest.importorskip("httpx")
    assert huggingface_hub.__version__ == "1.31.0"
    from huggingface_hub.utils._http import default_client_factory

    path = f"{storage.ARTIFACT_PREFIX}/{'a' * 64}/{'b' * 64}.json"
    requests = []
    payload = ([{"type": "file", "path": path, "size": 17,
                 "xetHash": "c" * 64, "mtime": "2026-10-06T00:00:00.000Z"}]
               if present else [])

    def response(request):
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path == (
            "/api/buckets/SZLHOLDINGS/szl-evidence/paths-info")
        assert json.loads(request.content) == {"paths": [path]}
        return httpx.Response(200, json=payload, request=request)

    huggingface_hub.set_client_factory(
        lambda: httpx.Client(transport=httpx.MockTransport(response)))
    try:
        api = huggingface_hub.HfApi(endpoint=storage.ENDPOINT, token=False)
        directory = tmp_path / "fence"; directory.mkdir(mode=0o700)
        fence = continuation.DiagnosticContinuationFence(api, Evidence(),
            time.monotonic() + 30, directory, "c" * 40)
        observed = fence._artifact(path)
    finally:
        huggingface_hub.set_client_factory(default_client_factory)
    assert len(requests) == 1
    assert (observed is None) is (not present)
    if present:
        assert storage._value(observed, "path") == path
        assert storage._value(observed, "size") == 17
        assert storage._value(observed, "xet_hash") == "c" * 64


def test_fence_artifact_reader_consumes_at_most_two_generator_rows(tmp_path):
    path = f"{storage.ARTIFACT_PREFIX}/{'a' * 64}/{'b' * 64}.json"
    consumed = []
    class API(FenceAPI):
        def get_bucket_paths_info(self, **_kwargs):
            def rows():
                for index in range(3):
                    consumed.append(index)
                    yield {"path": path, "type": "file", "size": 17,
                           "xet_hash": "c" * 64}
            return rows()
    api = API()
    directory = tmp_path / "fence"; directory.mkdir(mode=0o700)
    fence = continuation.DiagnosticContinuationFence(api, Evidence(),
        time.monotonic() + 30, directory, api.revision)
    with pytest.raises(continuation.ContinuationBlocked):
        fence._artifact(path)
    assert consumed == [0, 1]


def test_fence_artifact_reader_holds_on_generator_iteration_error(tmp_path):
    path = f"{storage.ARTIFACT_PREFIX}/{'a' * 64}/{'b' * 64}.json"
    class API(FenceAPI):
        def get_bucket_paths_info(self, **_kwargs):
            def rows():
                yield {"path": path, "type": "file", "size": 17,
                       "xet_hash": "c" * 64}
                raise RuntimeError("private provider detail")
            return rows()
    api = API()
    directory = tmp_path / "fence"; directory.mkdir(mode=0o700)
    fence = continuation.DiagnosticContinuationFence(api, Evidence(),
        time.monotonic() + 30, directory, api.revision)
    with pytest.raises(continuation.ContinuationBlocked) as held:
        fence._artifact(path)
    assert str(held.value) == "CURRENT_ABSENCE_UNVERIFIED"


def test_fence_rejects_preexisting_expected_object_before_any_ack(monkeypatch, tmp_path):
    api, evidence = FenceAPI(), Evidence()
    pending = synthetic_pending()
    plan = {"expected_object_count": continuation.EXPECTED_OBJECT_COUNT,
            "expected_object_set_sha256": continuation.EXPECTED_OBJECT_SET_SHA256,
            "candidate_unchanged": True, "all_retained_rows_validated": True}
    monkeypatch.setattr(triage, "local_artifact_plan", lambda *_a, **_k: (pending, plan))
    path, (_physical, _digest, size) = next(iter(pending.items()))
    api.objects[path] = (size, "c" * 64)
    directory = tmp_path / "fence"; directory.mkdir(mode=0o700)
    fence = continuation.DiagnosticContinuationFence(api, evidence,
        time.monotonic() + 30, directory, api.revision)
    with pytest.raises(continuation.ContinuationBlocked):
        fence.bind_candidate(tmp_path / "candidate.sqlite3")
    assert fence.acknowledged == {}


def test_fence_rejects_shared_dataset_revision_movement_before_any_write(
        monkeypatch, tmp_path):
    api, evidence = FenceAPI(), Evidence()
    pending = synthetic_pending()
    plan = {"expected_object_count": continuation.EXPECTED_OBJECT_COUNT,
            "expected_object_set_sha256": continuation.EXPECTED_OBJECT_SET_SHA256,
            "candidate_unchanged": True, "all_retained_rows_validated": True}
    monkeypatch.setattr(triage, "local_artifact_plan", lambda *_a, **_k: (pending, plan))
    directory = tmp_path / "fence"; directory.mkdir(mode=0o700)
    fence = continuation.DiagnosticContinuationFence(api, evidence,
        time.monotonic() + 30, directory, api.revision)
    api.revision = "d" * 40
    with pytest.raises(continuation.ContinuationBlocked):
        fence.bind_candidate(tmp_path / "candidate.sqlite3")
    assert api.objects == {}
    assert fence.bind_count == 0


def test_fence_rejects_a_racing_object_that_this_worker_did_not_add(monkeypatch, tmp_path):
    api, evidence = FenceAPI(), Evidence()
    pending = synthetic_pending()
    plan = {"expected_object_count": continuation.EXPECTED_OBJECT_COUNT,
            "expected_object_set_sha256": continuation.EXPECTED_OBJECT_SET_SHA256,
            "candidate_unchanged": True, "all_retained_rows_validated": True}
    monkeypatch.setattr(triage, "local_artifact_plan", lambda *_a, **_k: (pending, plan))
    directory = tmp_path / "fence"; directory.mkdir(mode=0o700)
    fence = continuation.DiagnosticContinuationFence(api, evidence,
        time.monotonic() + 30, directory, api.revision)
    fence.bind_candidate(tmp_path / "candidate.sqlite3")
    path, (_physical, digest, size) = next(iter(pending.items()))
    fence.before_artifact(path, digest, size)
    api.objects[path] = (size, "c" * 64)
    with pytest.raises(continuation.ContinuationBlocked):
        fence.acknowledge_artifact({"path": path, "sha256": digest,
                                   "size": size, "xet_hash": "c" * 64})
    assert fence.acknowledged == {}


def test_fence_rejects_a_second_add_if_acknowledged_object_disappears(monkeypatch, tmp_path):
    api, evidence = FenceAPI(), Evidence()
    pending = synthetic_pending()
    plan = {"expected_object_count": continuation.EXPECTED_OBJECT_COUNT,
            "expected_object_set_sha256": continuation.EXPECTED_OBJECT_SET_SHA256,
            "candidate_unchanged": True, "all_retained_rows_validated": True}
    monkeypatch.setattr(triage, "local_artifact_plan", lambda *_a, **_k: (pending, plan))
    directory = tmp_path / "fence"; directory.mkdir(mode=0o700)
    fence = continuation.DiagnosticContinuationFence(api, evidence,
        time.monotonic() + 30, directory, api.revision)
    fence.bind_candidate(tmp_path / "candidate.sqlite3")
    path, (_physical, digest, size) = next(iter(pending.items()))
    record = {"path": path, "sha256": digest, "size": size, "xet_hash": "c" * 64}
    fence.before_artifact(path, digest, size)
    fence.begin_artifact_add(path)
    api.objects[path] = (size, record["xet_hash"])
    fence.complete_artifact_add(path)
    fence.acknowledge_artifact(record)
    fence.before_artifact(path, digest, size)
    del api.objects[path]
    wrapper = acquisition._AdmittedAcquisitionHub(api, lambda: None, fence)
    local = tmp_path / "artifact.json"; local.write_bytes(b"x")
    with pytest.raises(continuation.ContinuationBlocked):
        wrapper.batch_bucket_files(bucket_id=storage.BUCKET, add=[(local, path)])
    assert fence.acknowledged[path] == (digest, size, record["xet_hash"])


def test_fence_rejects_an_unplanned_artifact_path_before_sdk_call(monkeypatch, tmp_path):
    api, evidence = FenceAPI(), Evidence()
    pending = synthetic_pending()
    plan = {"expected_object_count": continuation.EXPECTED_OBJECT_COUNT,
            "expected_object_set_sha256": continuation.EXPECTED_OBJECT_SET_SHA256,
            "candidate_unchanged": True, "all_retained_rows_validated": True}
    monkeypatch.setattr(triage, "local_artifact_plan", lambda *_a, **_k: (pending, plan))
    directory = tmp_path / "fence"; directory.mkdir(mode=0o700)
    fence = continuation.DiagnosticContinuationFence(api, evidence,
        time.monotonic() + 30, directory, api.revision)
    fence.bind_candidate(tmp_path / "candidate.sqlite3")
    wrapper = acquisition._AdmittedAcquisitionHub(api, lambda: None, fence)
    local = tmp_path / "artifact.json"; local.write_bytes(b"x")
    forged = f"{storage.ARTIFACT_PREFIX}/{'f' * 64}/{'e' * 64}.json"
    assert forged not in pending
    with pytest.raises(continuation.ContinuationBlocked):
        wrapper.batch_bucket_files(bucket_id=storage.BUCKET, add=[(local, forged)])
    assert api.objects == {}


def test_reconciliation_source_has_no_provider_mutation_call():
    tree = ast.parse(Path(continuation.__file__).read_text(encoding="utf-8"))
    called = {node.func.attr for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not called & {"batch_bucket_files", "add_bucket_files", "copy_bucket_files",
                         "create_commit", "pause_space", "restart_space", "resume_space",
                         "delete_file", "delete_repo", "upload_file", "upload_folder"}


def object_request(now=100.0):
    return {"schema": continuation.OBJECT_WORKER_SCHEMA,
        "workspace": "/tmp/parent/capture", "source_revision": "a" * 40,
        "run_id": 900, "run_attempt": 1,
        "job_key": continuation.RECONCILIATION_JOB_KEY,
        "candidate_sha256": "b" * 64, "deadline": now + 60}


def object_effects():
    return {"expected_object_count": continuation.EXPECTED_OBJECT_COUNT,
        "expected_object_set_sha256": continuation.EXPECTED_OBJECT_SET_SHA256,
        "candidate_unchanged": True, "all_retained_rows_validated": True,
        "classification": "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME",
        "present_object_count": 0,
        "missing_object_count": continuation.EXPECTED_OBJECT_COUNT,
        "observed_object_set_sha256": continuation.EMPTY_OBJECT_SET_SHA256,
        "provider_objects_fully_validated": False,
        "provider_writes_performed": False,
        "historical_writer_attribution": "NOT_ESTABLISHED"}


def current_absence_fixture(monkeypatch, state):
    """Run the real cross-module selector over an otherwise offline capture."""
    from scripts import qualify_gdw_store_recovery as recovery

    reproduce = recovery.qualify_capture

    def reproduce_without_source(*args, **kwargs):
        report = reproduce(*args, **kwargs)
        report.pop("inspector_source_revision", None)
        return report

    def read_reference(path, *_args, **_kwargs):
        normalized = str(path).replace("\\", "/")
        if normalized.endswith(acquisition.CAPTURE_REFERENCE):
            return state.arguments["capture_bytes"]
        assert normalized.endswith(acquisition.HISTORICAL_REFERENCE)
        return state.arguments["anchor_bytes"]

    monkeypatch.setattr(recovery, "qualify_capture", reproduce_without_source)
    monkeypatch.setattr(acquisition, "_read", read_reference)
    monkeypatch.setattr(triage, "private_head_metadata", lambda *_a, **_k: {
        "revision": "c" * 40, "head_presence": "ABSENT"})
    monkeypatch.setattr(continuation, "supervised_artifact_absence",
                        lambda *_a, **_k: object_effects())
    return SimpleNamespace(
        source=state.arguments["source_context"]["revision"],
        require_current_main=state.arguments["require_owned_source"],
    )


def test_fresh_preflight_qualification_binds_verified_source_before_selection(
        native_acquisition, monkeypatch, tmp_path):
    state = native_acquisition
    evidence = current_absence_fixture(monkeypatch, state)
    qualified, observation = continuation.observe_current_absence(
        state.api, tmp_path / "fresh-preflight", evidence, time.monotonic() + 20)
    selected = acquisition.select_qualified_capture(
        qualified, state.arguments["reference"], state.arguments["capture_bytes"],
        evidence.source)
    assert qualified["inspector_source_revision"] == evidence.source
    assert observation["dataset_revision"] == "c" * 40
    assert selected == acquisition.select_qualified_capture(
        state.arguments["qualified"], state.arguments["reference"],
        state.arguments["capture_bytes"], evidence.source)
    assert observation["missing_object_count"] == continuation.EXPECTED_OBJECT_COUNT


def test_reconciliation_serializes_verified_source_for_acquisition_selector(
        native_acquisition, monkeypatch, tmp_path):
    state = native_acquisition
    evidence = current_absence_fixture(monkeypatch, state)
    context = {"source_revision": evidence.source, "run_id": 900,
               "run_attempt": 1, "job_id": 901,
               "job_key": continuation.RECONCILIATION_JOB_KEY}
    monkeypatch.setattr(continuation.native, "NativeEvidence", lambda *_a, **_k: evidence)
    monkeypatch.setattr(continuation, "verify_current_context", lambda *_a, **_k: context)
    monkeypatch.setattr(continuation, "_diagnostic_artifact", lambda *_a, **_k: None)
    monkeypatch.setattr(storage, "_hub_api", lambda *_a, **_k: state.api)
    workspace = tmp_path / "native-reconciliation"
    workspace.mkdir(mode=0o700)
    report, encoded = continuation.execute_native_reconciliation(
        workspace, time.monotonic() + 20)
    qualified = continuation.native.strict(encoded, 1024 * 1024)
    selected = acquisition.select_qualified_capture(
        qualified, state.arguments["reference"], state.arguments["capture_bytes"],
        evidence.source)
    assert report["qualification_sha256"] == hashlib.sha256(encoded).hexdigest()
    assert qualified["inspector_source_revision"] == evidence.source
    assert selected == acquisition.select_qualified_capture(
        state.arguments["qualified"], state.arguments["reference"],
        state.arguments["capture_bytes"], evidence.source)


def test_object_worker_wire_is_closed_source_bound_and_nonadmitting():
    request = object_request()
    assert continuation._object_worker_request(request, now=100) == request
    report = continuation._object_worker_report(request, object_effects())
    assert continuation._validate_object_worker_report(report) == report
    assert all(report[key] is False for key in
        ("provider_writes_performed", "replay_admitted", "restore_admitted", "deployment_admitted"))
    assert continuation._validate_object_worker_report(
        continuation._held_object_worker_report())["state"] == "HELD"


def test_actual_isolated_worker_binds_reviewed_artifact_roots_before_provider_read(
        native_acquisition, tmp_path, monkeypatch):
    from gdw_durable_artifacts import LOGICAL_ROOTS
    from scripts import probe_gdw_runtime_base as base

    state = native_acquisition
    workspace = tmp_path / "capture"
    database = workspace / "working/gdw/candidate.sqlite3"
    database.parent.mkdir(parents=True, mode=0o700)
    database.write_bytes(state.originals["gdw"])
    for directory in (workspace, workspace / "working", database.parent):
        directory.chmod(0o700)
    database.chmod(0o600)

    def canonical_artifact(kind, identity, encoded):
        artifact = json.loads(encoded)
        artifact["path"] = str(
            LOGICAL_ROOTS[kind] / artifact["owner_scope"] / f"{identity}.json")
        return json.dumps(artifact, sort_keys=True)

    with sqlite3.connect(database) as connection:
        for identity, kind, encoded in connection.execute(
                "SELECT intent_sha256, kind, artifact_json FROM effect_outbox "
                "WHERE status='EXPORTED'"):
            connection.execute("UPDATE effect_outbox SET artifact_json=? "
                "WHERE intent_sha256=?", (canonical_artifact(kind, identity, encoded), identity))
        for identity, encoded in connection.execute(
                "SELECT payload_sha256, artifact_json FROM proof_outbox "
                "WHERE status='EXPORTED'"):
            connection.execute("UPDATE proof_outbox SET artifact_json=? "
                "WHERE payload_sha256=?", (canonical_artifact(
                    "proof_export", identity, encoded), identity))

    for key, value in triage.trusted_artifact_environment().items():
        monkeypatch.setenv(key, value)
    _pending, plan = triage.local_artifact_plan(database,
        tmp_path / "expected-plan", time.monotonic() + 20)
    assert plan["expected_object_count"] > 0

    source = "a" * 40
    deadline = time.monotonic() + 20
    request = {"schema": continuation.OBJECT_WORKER_SCHEMA,
        "workspace": str(workspace), "source_revision": source,
        "run_id": 900, "run_attempt": 1,
        "job_key": continuation.RECONCILIATION_JOB_KEY,
        "candidate_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "deadline": deadline}
    code = r'''
import os, runpy, sys
module = runpy.run_path(sys.argv[1], run_name="isolated_continuation_worker")
worker = module["_artifact_object_worker_observation"]
scope = worker.__globals__
scope["EXPECTED_OBJECT_COUNT"] = int(sys.argv[2])
scope["EXPECTED_OBJECT_SET_SHA256"] = sys.argv[3]
class Evidence:
    source = os.environ["GITHUB_SHA"]
    def require_current_main(self):
        return None
scope["native"].NativeEvidence = lambda *_args, **_kwargs: Evidence()
scope["verify_current_context"] = lambda _evidence, job_key, _job_name: {
    "source_revision": os.environ["GITHUB_SHA"],
    "run_id": int(os.environ["GITHUB_RUN_ID"]),
    "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
    "job_key": job_key,
}
class API:
    endpoint = "https://huggingface.co"
    def bucket_info(self, *, bucket_id):
        return {"id": bucket_id, "private": True}
    def list_bucket_tree(self, *, bucket_id, prefix, recursive):
        return iter(())
scope["storage"]._hub_api = lambda _token: API()
raise SystemExit(scope["artifact_object_worker"]())
'''
    environment = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "TMPDIR": str(tmp_path), "HF_TOKEN": "synthetic-hf-token",
        "GH_TOKEN": "synthetic-gh-token", "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "szl-holdings/a11oy", "GITHUB_REPOSITORY_ID": "1",
        "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": source,
        "GITHUB_WORKFLOW_REF": "szl-holdings/a11oy/.github/workflows/hf-sync.yml@refs/heads/main",
        "GITHUB_WORKFLOW_SHA": source, "GITHUB_RUN_ID": "900",
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_EVENT_NAME": "push",
        "GITHUB_JOB": continuation.RECONCILIATION_JOB_KEY,
    }
    assert not {"GDW_PROOF_DIR", "GDW_RECEIPT_PROJECTION_DIR"} & set(environment)
    raw = base._run([sys.executable, "-I", "-B", "-c", code,
        str(Path(continuation.__file__).resolve()),
        str(plan["expected_object_count"]), plan["expected_object_set_sha256"]],
        deadline=deadline, limit=continuation.OBJECT_WORKER_BYTES,
        env=environment, cwd=workspace, input_bytes=storage.canonical(request))
    report = continuation._validate_object_worker_report(
        continuation.native.strict(raw, continuation.OBJECT_WORKER_BYTES))
    assert report["state"] == "OBSERVED"
    assert report["artifact_effect_observation"]["expected_object_count"] == plan[
        "expected_object_count"]


@pytest.mark.parametrize("field,value", [
    ("source_revision", "main"), ("run_id", True), ("run_attempt", 2),
    ("job_key", "unknown"), ("candidate_sha256", "0" * 64),
    ("deadline", float("inf")), ("workspace", "private\npath"),
])
def test_object_worker_request_rejects_unbound_or_malformed_fields(field, value):
    request = object_request()
    request[field] = value
    with pytest.raises(continuation.ContinuationBlocked):
        continuation._object_worker_request(request, now=100)


def test_effectful_worker_reconciles_before_pause_and_uses_reaped_child():
    source = inspect.getsource(acquisition._execute_diagnostic_continuation)
    assert source.index("continuation.observe_current_absence") < source.index("pause_qualified_source")
    assert source.index("fence.bind_candidate") < source.index("pause_qualified_source")
    assert "require_prewrite=fence.require_artifacts_absent" in source
    supervisor = inspect.getsource(continuation.supervised_artifact_absence)
    assert "base._run(" in supervisor and '"--artifact-object-worker"' in supervisor
    assert "_capture_failure=True" in supervisor


def test_acquire_pair_invokes_continuation_fence_around_every_artifact(native_acquisition):
    state = native_acquisition
    calls = []
    class Fence:
        def bind_candidate(self, path): calls.append(("bind", path.name))
        def before_artifact(self, path, digest, size): calls.append(("before", path, digest, size))
        def controls_artifact_path(self, path): return path.startswith(storage.ARTIFACT_PREFIX + "/")
        def begin_artifact_add(self, path): calls.append(("begin", path))
        def complete_artifact_add(self, path): calls.append(("added", path))
        def acknowledge_artifact(self, record): calls.append(("ack", record["path"]))
        def require_artifacts_complete(self): calls.append(("complete",))
    arguments = dict(state.arguments)
    arguments["preserved"] = None
    locator = acquisition.acquire_pair(state.api, continuation_fence=Fence(), **arguments)
    assert locator["state"] == "BOOTSTRAP_ACKNOWLEDGED"
    assert calls[0] == ("bind", "candidate.sqlite3")
    assert sum(item[0] == "before" for item in calls) == 2
    assert sum(item[0] == "begin" for item in calls) == 1
    assert sum(item[0] == "added" for item in calls) == 1
    assert sum(item[0] == "ack" for item in calls) == 2
    assert calls.count(("complete",)) == 1


def test_real_fence_uses_fresh_plan_for_pre_pause_and_acquire_rebind(
        native_acquisition, monkeypatch, tmp_path):
    """Exercise both real binds through the actual acquisition flow."""
    state = native_acquisition
    candidate = tmp_path / "pre-pause-candidate.sqlite3"
    candidate.write_bytes(state.originals["gdw"])
    pending, plan = triage.local_artifact_plan(
        candidate, tmp_path / "expected-plan", time.monotonic() + 20)
    assert pending and plan["expected_object_count"] == len(pending)
    monkeypatch.setattr(continuation, "EXPECTED_OBJECT_COUNT",
                        plan["expected_object_count"])
    monkeypatch.setattr(continuation, "EXPECTED_OBJECT_SET_SHA256",
                        plan["expected_object_set_sha256"])

    contents = state.api.repositories[state.api.revision]
    state.api.revision = "c" * 40
    state.api.repositories = {state.api.revision: contents}
    evidence = SimpleNamespace(
        source=state.arguments["source_context"]["revision"],
        require_current_main=state.arguments["require_owned_source"],
    )
    fence_directory = tmp_path / "continuation-fence"
    fence_directory.mkdir(mode=0o700)
    fence = continuation.DiagnosticContinuationFence(
        state.api, evidence, time.monotonic() + 20, fence_directory,
        state.api.revision)
    fence.bind_candidate(candidate)

    arguments = dict(state.arguments)
    arguments["preserved"] = None
    locator = acquisition.acquire_pair(
        state.api, continuation_fence=fence, **arguments)
    assert locator["state"] == "BOOTSTRAP_ACKNOWLEDGED"
    assert fence.bind_count == 2
    assert (fence_directory / "diagnostic-continuation-plan-1").is_dir()
    assert (fence_directory / "diagnostic-continuation-plan-2").is_dir()
    assert len(fence.acknowledged) == plan["expected_object_count"]


def test_continuation_fence_failure_precedes_first_provider_write(native_acquisition):
    state = native_acquisition
    class Fence:
        def bind_candidate(self, _path): pass
        def before_artifact(self, *_args):
            raise continuation.ContinuationBlocked("CURRENT_ABSENCE_UNVERIFIED")
        def controls_artifact_path(self, _path): pytest.fail("unadmitted provider call")
        def begin_artifact_add(self, _path): pytest.fail("unadmitted provider call")
        def complete_artifact_add(self, _path): pytest.fail("unadmitted provider call")
        def acknowledge_artifact(self, _record): pytest.fail("unadmitted acknowledgement")
        def require_artifacts_complete(self): pytest.fail("unadmitted completion")
    arguments = dict(state.arguments)
    arguments["preserved"] = None
    with pytest.raises(Exception):
        acquisition.acquire_pair(state.api, continuation_fence=Fence(), **arguments)
    assert state.api.additions == state.api.commits == []


def test_pause_rechecks_the_complete_namespace_immediately_before_mutation(monkeypatch):
    observations = iter(({"stage": "RUNTIME_ERROR", "hf_revision": "1" * 40},
                         {"stage": "PAUSED", "hf_revision": "1" * 40},
                         {"stage": "PAUSED", "hf_revision": "1" * 40}))
    monkeypatch.setattr(acquisition, "observe_originals", lambda *_a, **_k: next(observations))
    events = []
    class API:
        def pause_space(self, *, repo_id):
            assert repo_id == storage.SPACE
            events.append("pause")
            return {"stage": "PAUSED"}
    result = acquisition.pause_qualified_source(API(), {},
        require_owned_source=lambda: events.append("source"),
        require_prewrite=lambda: events.append("complete-namespace"),
        deadline=time.monotonic() + 30)
    assert result["pause_submitted"] is True
    assert events == ["complete-namespace", "pause"]
