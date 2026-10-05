#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline native triage tests: no fake publication receipt, secrets or provider writes."""

import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import sqlite3
import time
import sys
from types import SimpleNamespace

import pytest
import yaml

import gdw_runtime
from scripts import triage_gdw_artifacts_readonly as triage
from tests.test_gdw_durable_runtime import stores
from tests.test_gdw_durable_artifacts import exported, copy_database
from tests.test_gdw_runtime import _queued_proof
from tests.test_gdw_store_recovery import capture, originals
from tests.test_gdw_artifact_readonly_protocol import effects as synthetic_effects


class ReadOnlyArtifactAPI:
    endpoint = "https://huggingface.co"

    def __init__(self, objects, *, reported_size_delta=0, move_after_download=False,
                 failure=None):
        self.objects = dict(objects)
        self.reported_size_delta = reported_size_delta
        self.move_after_download = move_after_download
        self.failure = failure
        self.calls = []
        self.downloaded = False

    def bucket_info(self, *, bucket_id):
        self.calls.append(("bucket_info", bucket_id))
        return {"id": bucket_id, "private": True}

    def get_bucket_paths_info(self, *, bucket_id, paths):
        self.calls.append(("get_bucket_paths_info", tuple(paths)))
        if self.failure:
            raise RuntimeError(self.failure)
        path = paths[0]
        if path not in self.objects:
            return []
        data = self.objects[path]
        suffix = "b" if self.move_after_download and self.downloaded else "a"
        return [{"path": path, "type": "file", "size": len(data) + self.reported_size_delta,
                 "xet_hash": suffix * 64}]

    def download_bucket_files(self, *, bucket_id, files, raise_on_missing_files):
        self.calls.append(("download_bucket_files", len(files), raise_on_missing_files))
        assert raise_on_missing_files is True and len(files) == 1
        observed, target = files[0]
        Path(target).write_bytes(self.objects[observed["path"]])
        self.downloaded = True


def retained_candidate(stores, tmp_path, *, count=1):
    exported(stores)
    if count == 2:
        _queued_proof(stores.gdw, request_id="request-2")
        report = gdw_runtime.drain_once(limit=1, lease_seconds=30,
                                        worker_id="artifact-fixture-2", workspace=stores.gdw)
        assert report["exported"] == 1 and report["failed"] == 0
    return copy_database(stores, tmp_path)


def planned_objects(stores, database, tmp_path):
    pending, summary = triage.local_artifact_plan(
        database, tmp_path / "private-plan", time.monotonic() + 10,
        logical_roots=stores.gate.artifacts.roots,
    )
    return pending, summary, {path: physical.read_bytes()
                              for path, (physical, _digest, _size) in pending.items()}


def test_retained_rows_reach_blocked_callback_without_upload_or_database_change(stores, tmp_path):
    exported(stores)
    database = copy_database(stores, tmp_path)
    before = database.read_bytes()
    count = len(stores.artifact_publications)
    observed = triage.local_artifact_observation(database, tmp_path / "read-only-local", time.monotonic() + 10,
                                                logical_roots=stores.gate.artifacts.roots)
    assert observed == {"state": "OBSERVED", "diagnostic_code": "LOCAL_ROWS_VALIDATED_PUBLICATION_NOT_ATTEMPTED",
                        "publication_callback_reached": True, "candidate_unchanged": True}
    assert stores.artifact_publications[count:] == []
    assert database.read_bytes() == before


def test_invalid_record_is_diagnosed_before_callback_without_leaking_payload(stores, tmp_path):
    exported(stores)
    database = copy_database(stores, tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE effect_outbox SET artifact_json=? WHERE status='EXPORTED'",
                           (json.dumps({"private_test_marker": "do-not-disclose-private-owner"}),))
    before = database.read_bytes()
    observed = triage.local_artifact_observation(database, tmp_path / "invalid-local", time.monotonic() + 10,
                                                logical_roots=stores.gate.artifacts.roots)
    assert observed["state"] == "HELD" and observed["diagnostic_code"] == "ARTIFACT_RECONSTRUCTION_MISMATCH"
    assert observed["publication_callback_reached"] is False and observed["candidate_unchanged"] is True
    assert "do-not-disclose" not in json.dumps(observed)
    assert database.read_bytes() == before


def test_empty_retained_set_does_not_claim_artifact_publication(stores, tmp_path):
    database = copy_database(stores, tmp_path)
    observed = triage.local_artifact_observation(database, tmp_path / "empty-local", time.monotonic() + 10,
                                                logical_roots=stores.gate.artifacts.roots)
    assert observed["diagnostic_code"] == "NO_RETAINED_ARTIFACTS"
    assert observed["publication_callback_reached"] is False


def test_complete_retained_set_is_planned_without_calling_publisher(stores, tmp_path):
    database = retained_candidate(stores, tmp_path)
    before = database.read_bytes()
    count = len(stores.artifact_publications)
    pending, summary, objects = planned_objects(stores, database, tmp_path)
    assert len(pending) == summary["expected_object_count"] == len(objects) == 1
    assert summary["all_retained_rows_validated"] is summary["candidate_unchanged"] is True
    assert len(summary["expected_object_set_sha256"]) == 64
    assert len(stores.artifact_publications) == count
    assert database.read_bytes() == before


def test_prepare_remains_the_only_artifact_publication_entrypoint():
    from gdw_durable_artifacts import ArtifactCache
    assert ".publish(" not in inspect.getsource(ArtifactCache._validated_objects)
    assert inspect.getsource(ArtifactCache.prepare).count("self.publish(") == 1


@pytest.mark.parametrize("presence,classification", [
    ("all", "ALL_EXPECTED_OBJECTS_PRESENT_AND_VALIDATED_AT_READ_TIME"),
    ("none", "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME"),
    ("partial", "PARTIAL_EXPECTED_OBJECT_SET_PRESENT_AT_READ_TIME"),
])
def test_exact_current_object_set_is_classified_without_writer_attribution(
        stores, tmp_path, presence, classification):
    database = retained_candidate(stores, tmp_path, count=2)
    pending, _summary, objects = planned_objects(stores, database, tmp_path)
    assert len(objects) == 2
    if presence == "none":
        objects = {}
    elif presence == "partial":
        objects = {next(iter(objects.items()))[0]: next(iter(objects.items()))[1]}
    api = ReadOnlyArtifactAPI(objects)
    before = database.read_bytes()
    result = triage.artifact_effect_observation(
        api, database, tmp_path / "effect-observation", lambda: None,
        time.monotonic() + 10, logical_roots=stores.gate.artifacts.roots,
    )
    assert result["classification"] == classification
    assert result["present_object_count"] == len(objects)
    assert result["missing_object_count"] == len(pending) - len(objects)
    assert result["provider_objects_fully_validated"] is (presence == "all")
    assert result["historical_writer_attribution"] == "NOT_ESTABLISHED"
    assert result["provider_writes_performed"] is False
    assert database.read_bytes() == before
    serialized = json.dumps(result)
    assert all(path not in serialized for path in pending)
    assert "owner" not in serialized and "payload" not in serialized
    assert not any(call[0] == "download_bucket_files" for call in api.calls) if presence == "none" else True


def test_all_rows_validate_before_first_provider_read(stores, tmp_path):
    database = retained_candidate(stores, tmp_path, count=2)
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT rowid,artifact_json FROM effect_outbox WHERE status='EXPORTED' ORDER BY rowid"
        ).fetchall()
        assert len(rows) == 2
        changed = json.loads(rows[-1][1])
        changed["sha256"] = "0" * 64
        connection.execute("UPDATE effect_outbox SET artifact_json=? WHERE rowid=?",
                           (json.dumps(changed), rows[-1][0]))
    api = ReadOnlyArtifactAPI({})
    with pytest.raises(Exception):
        triage.artifact_effect_observation(
            api, database, tmp_path / "invalid-effect-observation", lambda: None,
            time.monotonic() + 10, logical_roots=stores.gate.artifacts.roots,
        )
    assert api.calls == []


def test_mismatched_identity_blocks_before_any_private_download(stores, tmp_path):
    database = retained_candidate(stores, tmp_path)
    _pending, _summary, objects = planned_objects(stores, database, tmp_path)
    api = ReadOnlyArtifactAPI(objects, reported_size_delta=1)
    with pytest.raises(triage.TriageHeld):
        triage.artifact_effect_observation(
            api, database, tmp_path / "mismatch-observation", lambda: None,
            time.monotonic() + 10, logical_roots=stores.gate.artifacts.roots,
        )
    assert not any(call[0] == "download_bucket_files" for call in api.calls)


def test_object_identity_movement_during_readback_is_held(stores, tmp_path):
    database = retained_candidate(stores, tmp_path)
    _pending, _summary, objects = planned_objects(stores, database, tmp_path)
    api = ReadOnlyArtifactAPI(objects, move_after_download=True)
    with pytest.raises(triage.TriageHeld):
        triage.artifact_effect_observation(
            api, database, tmp_path / "moving-object-observation", lambda: None,
            time.monotonic() + 10, logical_roots=stores.gate.artifacts.roots,
        )
    assert any(call[0] == "download_bucket_files" for call in api.calls)


def test_missing_object_appearance_during_observation_is_held(stores, tmp_path):
    database = retained_candidate(stores, tmp_path)
    _pending, _summary, objects = planned_objects(stores, database, tmp_path)
    class AppearingAPI(ReadOnlyArtifactAPI):
        def __init__(self, values):
            super().__init__(values)
            self.observations = 0
        def get_bucket_paths_info(self, *, bucket_id, paths):
            self.observations += 1
            if self.observations == 1:
                self.calls.append(("get_bucket_paths_info", tuple(paths)))
                return []
            return super().get_bucket_paths_info(bucket_id=bucket_id, paths=paths)
    api = AppearingAPI(objects)
    with pytest.raises(triage.TriageHeld):
        triage.artifact_effect_observation(
            api, database, tmp_path / "appearing-object-observation", lambda: None,
            time.monotonic() + 10, logical_roots=stores.gate.artifacts.roots,
        )
    assert not any(call[0] == "download_bucket_files" for call in api.calls)


def test_source_movement_interrupts_exact_path_reads(stores, tmp_path):
    database = retained_candidate(stores, tmp_path)
    _pending, _summary, objects = planned_objects(stores, database, tmp_path)
    calls = 0
    def source():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise triage.TriageHeld("READ_ONLY_TRIAGE_HELD")
    api = ReadOnlyArtifactAPI(objects)
    with pytest.raises(triage.TriageHeld):
        triage.artifact_effect_observation(
            api, database, tmp_path / "moving-source-observation", source,
            time.monotonic() + 10, logical_roots=stores.gate.artifacts.roots,
        )
    assert not any(call[0] == "download_bucket_files" for call in api.calls)


def test_private_head_movement_holds_after_object_observation(monkeypatch, tmp_path):
    from scripts import acquire_gdw_durable_storage as acquisition
    from scripts import qualify_gdw_store_recovery as recovery

    monkeypatch.setattr(acquisition, "_read", lambda _path: b"{}")
    monkeypatch.setattr(recovery, "_json", lambda _raw: {})
    monkeypatch.setattr(recovery, "validate_historical_anchors", lambda *_args: None)
    monkeypatch.setattr(recovery, "qualify_capture", lambda *_args, **_kwargs: {
        "state": "LOGICAL_CONTINUITY_VERIFIED",
        "provider_writes_performed": False,
        "originals_mutated": False,
        "restore_admitted": False,
        "deployment_admitted": False,
        "databases": {
            label: {"state": "LOGICAL_CONTINUITY_VERIFIED",
                    "captured_originals_unchanged": True,
                    "all_declared_stored_values_unchanged": True}
            for label in ("gdw", "series_a")
        },
    })
    heads = iter([
        {"revision": "a" * 40, "head_presence": "ABSENT"},
        {"revision": "b" * 40, "head_presence": "ABSENT"},
    ])
    monkeypatch.setattr(triage, "private_head_metadata", lambda _api: next(heads))
    monkeypatch.setattr(triage, "supervised_artifact_effect_observation", lambda *_args, **_kwargs: {
        "classification": "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME",
    })
    api = type("SyntheticAPI", (), {"endpoint": "https://huggingface.co"})()
    with pytest.raises(triage.TriageHeld):
        triage.observe_capture(api, tmp_path, lambda: None, time.monotonic() + 10)


@pytest.mark.parametrize("defect", [
    "missing", "extra", "malformed-databases", "malformed-entry",
    "wrong-state", "false-originals", "false-values", "non-boolean",
])
def test_nested_capture_qualification_is_complete_and_strict(defect):
    item = {"state": "LOGICAL_CONTINUITY_VERIFIED",
            "captured_originals_unchanged": True,
            "all_declared_stored_values_unchanged": True}
    qualified = {"databases": {"gdw": dict(item), "series_a": dict(item)}}
    if defect == "missing":
        del qualified["databases"]["series_a"]
    elif defect == "extra":
        qualified["databases"]["other"] = dict(item)
    elif defect == "malformed-databases":
        qualified["databases"] = []
    elif defect == "malformed-entry":
        qualified["databases"]["gdw"] = []
    elif defect == "wrong-state":
        qualified["databases"]["gdw"]["state"] = "UNQUALIFIED"
    elif defect == "false-originals":
        qualified["databases"]["gdw"]["captured_originals_unchanged"] = False
    elif defect == "false-values":
        qualified["databases"]["series_a"]["all_declared_stored_values_unchanged"] = False
    else:
        qualified["databases"]["gdw"]["captured_originals_unchanged"] = 1
    with pytest.raises(triage.TriageHeld):
        triage._qualified_capture_databases(qualified, frozenset(("gdw", "series_a")))


def test_actual_qualifier_shape_reaches_artifact_observation(
        capture, tmp_path, monkeypatch):
    from scripts import acquire_gdw_durable_storage as acquisition
    from scripts import qualify_gdw_store_recovery as recovery

    hub, reference = capture
    reference_bytes = recovery.preservation._json_bytes(reference)
    reads = iter((reference_bytes, b"{}"))
    monkeypatch.setattr(acquisition, "_read", lambda _path: next(reads))
    monkeypatch.setattr(recovery, "validate_historical_anchors", lambda *_args: None)
    qualify = recovery.qualify_capture
    actual = {}
    def qualify_without_synthetic_shape(api, current, workspace, owned, deadline, **_kwargs):
        report = qualify(api, current, workspace, owned, deadline)
        actual.update(report)
        return report
    monkeypatch.setattr(recovery, "qualify_capture", qualify_without_synthetic_shape)
    monkeypatch.setattr(triage, "private_head_metadata", lambda _api: {
        "revision": "a" * 40, "head_presence": "ABSENT",
    })
    observed = []
    def effects(workspace, *_args, **_kwargs):
        database = workspace / "capture/working/gdw/candidate.sqlite3"
        assert database.is_file()
        observed.append(database)
        return {"classification": "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME"}
    # This test isolates the actual qualifier shape; worker integration is
    # exercised separately without claiming its synthetic transport is native.
    monkeypatch.setattr(triage, "supervised_artifact_effect_observation", effects)

    result = triage.observe_capture(hub, tmp_path / "actual-shape", lambda: None,
                                    time.monotonic() + 30)
    assert actual["state"] == "LOGICAL_CONTINUITY_VERIFIED"
    assert "captured_originals_unchanged" not in actual
    assert set(actual["databases"]) == {"gdw", "series_a"}
    assert len(observed) == 1 and result["qualified_database_count"] == 2
    assert result["captured_originals_unchanged_during_qualification"] is True
    assert "captured_originals_unchanged" not in result


@pytest.mark.parametrize("method", ["batch_bucket_files", "create_commit", "upload_file",
                                    "delete_file", "pause_space", "restart_space"])
def test_exact_object_reader_exposes_no_mutation_method(stores, tmp_path, method):
    database = retained_candidate(stores, tmp_path)
    pending, _summary, _objects = planned_objects(stores, database, tmp_path)
    admitted = {path: (digest, size)
                for path, (_physical, digest, size) in pending.items()}
    directory = tmp_path / "reader"
    directory.mkdir(mode=0o700)
    reader = triage.ReadOnlyArtifactHub(ReadOnlyArtifactAPI({}), admitted, directory,
                                        lambda: None, time.monotonic() + 10)
    with pytest.raises(AttributeError):
        getattr(reader, method)


def test_exact_object_reader_rejects_unplanned_path_before_sdk(stores, tmp_path):
    database = retained_candidate(stores, tmp_path)
    pending, _summary, _objects = planned_objects(stores, database, tmp_path)
    admitted = {path: (digest, size)
                for path, (_physical, digest, size) in pending.items()}
    api = ReadOnlyArtifactAPI({})
    directory = tmp_path / "reader-unplanned"
    directory.mkdir(mode=0o700)
    reader = triage.ReadOnlyArtifactHub(api, admitted, directory,
                                        lambda: None, time.monotonic() + 10)
    unplanned = "a11oy/durable-artifacts/v1/" + "0" * 64 + "/" + "0" * 64 + ".json"
    with pytest.raises(triage.TriageHeld):
        reader.observe(unplanned)
    with pytest.raises(triage.TriageHeld):
        reader.download({"path": unplanned, "type": "file", "size": 1,
                         "xet_hash": "a" * 64}, directory / "unplanned.json")
    assert api.calls == []


def environment():
    source = "a" * 40
    return source, {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": triage.REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "triage", "GITHUB_SHA": source,
        "GITHUB_WORKFLOW_SHA": source, "GITHUB_RUN_ID": "900",
        "GITHUB_WORKFLOW_REF": f"{triage.REPOSITORY}/{triage.WORKFLOW}@refs/heads/main"}


def prior_native_metadata():
    expected = {
        111616471901: ("Admit the queued source before provider mutation", "success"),
        111616522098: ("Reconcile the held acquisition before provider mutation", "success"),
        111616609573: ("Check manual authority prerequisites before provider writes", "success"),
        triage.PRIOR_JOB: ("Acquire qualified private storage through the canonical publisher", "failure"),
        111616769593: ("Resume the canonical Space without changing its allocation", "skipped"),
        111616946613: ("Deploy, source-bind, and attest exact surface", "skipped"),
        111616947075: ("Verify post-deploy configuration and bounded live proofs", "skipped"),
        111616947443: ("Publish and live-verify six domain-native flagship Spaces", "skipped"),
        111616948013: ("Probe and ingest exact post-deploy readiness verdict", "skipped"),
        111616948054: ("Prove exact live source, runtime, routes, and singleton state", "skipped"),
        111616948338: ("Rebind and functionally verify the existing Finance projection", "skipped"),
        111616948584: ("Re-authorize exact protected main after all publication proofs", "skipped"),
        111616948662: ("Await strict live and repository parity", "skipped"),
    }
    jobs = []
    for job_id, (name, conclusion) in expected.items():
        steps = []
        if job_id == triage.PRIOR_JOB:
            steps = [
                {"name": "Reconcile again, verify native candidates, and acquire private storage once",
                 "status": "completed", "conclusion": "failure"},
                {"name": "Install the persistent old-source guard and both managed configurations once",
                 "status": "completed", "conclusion": "skipped"},
                {"name": "Retain only the immutable selector and safe guarded configuration result",
                 "status": "completed", "conclusion": "success"},
            ]
        jobs.append({"id": job_id, "name": name, "conclusion": conclusion, "status": "completed",
                     "head_sha": triage.PRIOR_SOURCE, "run_id": triage.PRIOR_RUN,
                     "run_attempt": triage.PRIOR_ATTEMPT, "steps": steps})
    return {
        "run": {"id": triage.PRIOR_RUN, "run_attempt": 1, "head_sha": triage.PRIOR_SOURCE,
                "head_branch": "main", "event": "push", "path": ".github/workflows/hf-sync.yml",
                "status": "completed", "conclusion": "failure",
                "repository": {"id": 1225834126, "full_name": triage.REPOSITORY},
                "head_repository": {"id": 1225834126}},
        "jobs": {"total_count": len(jobs), "jobs": jobs},
        "artifact": {"id": triage.PRIOR_ARTIFACT,
                     "name": f"canonical-durable-acquisition-{triage.PRIOR_RUN}-1",
                     "size_in_bytes": triage.PRIOR_ARTIFACT_BYTES, "expired": False,
                     "digest": "sha256:" + triage.PRIOR_ARTIFACT_SHA256,
                     "workflow_run": {"id": triage.PRIOR_RUN, "repository_id": 1225834126,
                                      "head_repository_id": 1225834126, "head_branch": "main",
                                      "head_sha": triage.PRIOR_SOURCE}},
    }


@pytest.mark.parametrize("defect", [None, "artifact_digest", "job_conclusion", "run_source"])
def test_prior_ambiguous_attempt_requires_exact_native_metadata(monkeypatch, defect):
    state = prior_native_metadata()
    if defect == "artifact_digest": state["artifact"]["digest"] = "sha256:" + "0" * 64
    if defect == "job_conclusion":
        next(job for job in state["jobs"]["jobs"] if job["id"] == triage.PRIOR_JOB)["conclusion"] = "success"
    if defect == "run_source": state["run"]["head_sha"] = "0" * 40
    def response(_session, suffix):
        if suffix.startswith("actions/runs/") and suffix.endswith("jobs?per_page=100"):
            return state["jobs"]
        if suffix.startswith("actions/runs/"):
            return state["run"]
        if suffix == f"actions/artifacts/{triage.PRIOR_ARTIFACT}":
            return state["artifact"]
        raise AssertionError(suffix)
    monkeypatch.setattr(triage, "github_json", response)
    if defect is not None:
        with pytest.raises(triage.TriageHeld):
            triage.verify_prior_attempt(object())
    else:
        result = triage.verify_prior_attempt(object())
        assert result["prior_native_metadata_verified"] is True
        assert result["prior_stage"] == "ARTIFACT_PUBLICATION"
        assert result["prior_stage_state"] == "BOUNDARY_ENTERED"


@pytest.mark.parametrize("key,value", [("GITHUB_ACTIONS", "false"), ("GITHUB_REPOSITORY", "other/repo"),
    ("GITHUB_REF", "refs/heads/other"), ("GITHUB_EVENT_NAME", "push"), ("GITHUB_RUN_ATTEMPT", "2"),
    ("GITHUB_JOB", "other"), ("GITHUB_SHA", "b" * 40), ("GITHUB_WORKFLOW_SHA", "b" * 40),
    ("GITHUB_RUN_ID", "0"), ("GITHUB_WORKFLOW_REF", "untrusted")])
def test_invalid_context_never_admits_private_reads(key, value):
    source, env = environment()
    env[key] = value
    with pytest.raises(triage.TriageHeld):
        triage.native_context(env, source)


def test_exact_native_context():
    source, env = environment()
    assert triage.native_context(env, source) == {"source_revision": source, "run_id": 900, "run_attempt": 1}


@pytest.mark.parametrize("bad", ["main", "", "A" * 40, "a" * 39, "a" * 41])
def test_source_must_be_exact_lowercase_commit(bad):
    _source, env = environment()
    with pytest.raises(triage.TriageHeld):
        triage.native_context(env, bad)


def test_triage_source_has_no_provider_mutator_and_uses_real_readonly_qualification():
    source = Path(triage.__file__).read_text()
    tree = ast.parse(source)
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {"pause_space", "restart_space", "resume_space", "batch_bucket_files",
        "add_bucket_files", "copy_bucket_files",
        "delete_repo", "delete_file", "create_commit", "upload_file", "upload_folder", "sync_bucket", "publish_artifact"}
    assert "recovery.ReadOnlyCaptureHub(api)" in source
    assert "qualified.get(\"provider_writes_performed\") is False" in source
    callback = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "stop_before_publication")
    assert not any(isinstance(node, ast.Return) for node in ast.walk(callback))
    assert any(isinstance(node, ast.Raise) for node in ast.walk(callback))


def test_workflow_only_manual_triage_with_fixed_artifact_and_no_publish_path():
    raw = (triage.ROOT / triage.WORKFLOW).read_text()
    workflow = yaml.safe_load(raw)
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers) == {"pull_request", "workflow_dispatch"}
    jobs = workflow["jobs"]
    assert set(jobs) == {"contract", "triage"}
    job = jobs["triage"]
    assert job["needs"] == "contract"
    assert job["permissions"] == {"contents": "read", "actions": "read"}
    for required in ["github.event_name == 'workflow_dispatch'", "github.ref == 'refs/heads/main'",
                     "github.sha == inputs.source_sha", "github.run_attempt == 1"]:
        assert required in job["if"]
    assert all("continue-on-error" not in step for step in job["steps"])
    upload = [step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(upload) == 1 and upload[0]["with"]["path"] == "${{ runner.temp }}/gdw-artifact-triage.json"
    assert not any(key in jobs["contract"].get("env", {}) for key in ("HF_TOKEN", "GH_TOKEN"))


def test_native_triage_roots_match_reviewed_worker_not_caller(monkeypatch):
    from gdw_durable_artifacts import LOGICAL_ROOTS
    monkeypatch.setenv("GDW_PROOF_DIR", "/untrusted/proofs")
    monkeypatch.setenv("GDW_RECEIPT_PROJECTION_DIR", "/untrusted/receipts")
    assert triage.trusted_artifact_environment() == {
        "GDW_PROOF_DIR": str(LOGICAL_ROOTS["proof_export"]),
        "GDW_RECEIPT_PROJECTION_DIR": str(LOGICAL_ROOTS["receipt_projection"]),
    }
    assert "os.environ.update(trusted_artifact_environment())" in Path(triage.__file__).read_text()


@pytest.mark.parametrize("observation_fails", [False, True])
def test_native_main_reaches_readonly_observation_with_real_private_output_context(monkeypatch, tmp_path, capfd, observation_fails):
    import logging
    import os
    import sys
    from types import SimpleNamespace

    source, env = environment()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("HF_TOKEN", "synthetic-hf-token")
    monkeypatch.setenv("GH_TOKEN", "synthetic-gh-token")
    for key in ("HF_HOME", "HF_DEBUG", "HF_HUB_VERBOSITY", "HF_HUB_DISABLE_PROGRESS_BARS",
                "GDW_PROOF_DIR", "GDW_RECEIPT_PROJECTION_DIR"):
        monkeypatch.setenv(key, "synthetic-parent")
    output = tmp_path / "gdw-artifact-triage.json"
    monkeypatch.setattr(sys, "argv", ["triage", "--source-sha", source, "--output", str(output)])
    monkeypatch.setattr(triage.signal, "alarm", lambda *_: None)
    monkeypatch.setattr(triage.signal, "signal", lambda *_: None)
    monkeypatch.setattr(triage.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=source + "\n"))

    class Session:
        def __init__(self): self.headers = {}
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, *args, **kwargs): raise AssertionError("no network in synthetic main test")

    calls = []
    def verified(session, context):
        assert context["source_revision"] == source
        calls.append("native-identity")
    def prior(session):
        calls.append("prior-attempt")
        return {"prior_native_metadata_verified": True}
    def api_factory(**kwargs):
        assert kwargs == {"endpoint": "https://huggingface.co", "token": "synthetic-hf-token"}
        calls.append("read-client")
        return object()
    def observation(api, directory, owned, deadline, *, note):
        note("CAPTURE_QUALIFICATION")
        # The real private-output manager must hide Python and native fd output.
        os.write(1, b"private-capture-test-marker\n")
        os.write(2, b"private-capture-test-marker\n")
        assert directory.is_dir() and not output.exists()
        calls.append("observation")
        if observation_fails:
            raise RuntimeError("private-capture-test-marker")
        return {"capture_qualification": "SYNTHETIC_TEST_ONLY"}
    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(Session=Session))
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(__version__="1.31.0", HfApi=api_factory))
    monkeypatch.setattr(triage, "verify_native", verified)
    monkeypatch.setattr(triage, "verify_prior_attempt", prior)
    monkeypatch.setattr(triage, "observe_capture", observation)
    disabled = logging.root.manager.disable
    try:
        assert triage.main() == (2 if observation_fails else 0)
    finally:
        logging.disable(disabled)
    assert calls == ["native-identity", "prior-attempt", "read-client", "observation"]
    captured = capfd.readouterr()
    assert "private-capture-test-marker" not in captured.out + captured.err
    assert "synthetic-hf-token" not in captured.out + captured.err
    record = json.loads(output.read_text())
    assert record["state"] == ("HELD" if observation_fails else "OBSERVED")
    assert record["read_boundary"] == ("CAPTURE_QUALIFICATION" if observation_fails else "COMPLETE")
    if not observation_fails:
        assert record["capture_qualification"] == "SYNTHETIC_TEST_ONLY"
    assert record["provider_writes_performed"] is record["restore_admitted"] is record["deployment_admitted"] is False
    assert "recovery._private_output()" not in Path(triage.__file__).read_text()


@pytest.mark.parametrize("boundary", sorted(triage.READ_BOUNDARIES))
def test_readonly_boundary_is_a_fixed_enum_not_error_text(boundary):
    record = {}
    triage.mark_boundary(record, boundary)
    assert record == {"read_boundary": boundary}
    with pytest.raises(triage.TriageHeld):
        triage.mark_boundary(record, "private-owner/path?token=example")
    assert record == {"read_boundary": boundary}


def test_triage_uses_canonical_private_read_selector_only_at_native_step():
    workflow = yaml.safe_load((triage.ROOT / triage.WORKFLOW).read_text())
    canonical = yaml.safe_load((triage.ROOT / ".github/workflows/hf-sync.yml").read_text())
    expected = "${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}"
    assert canonical["jobs"]["durable-acquisition"]["env"]["HF_TOKEN"] == expected
    steps = workflow["jobs"]["triage"]["steps"]
    readers = [(index, step) for index, step in enumerate(steps)
               if "scripts/triage_gdw_artifacts_readonly.py --source-sha" in step.get("run", "")]
    assert len(readers) == 1
    index, reader = readers[0]
    assert reader["env"]["HF_TOKEN"] == expected
    assert reader["env"]["GH_TOKEN"] == "${{ github.token }}"

    # No HF credential binding belongs in PR tests, job-wide environment,
    # checkout, dependency installation, output, or upload steps.
    bindings = []
    def visit(value, path=()):
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, path + (key,))
        elif isinstance(value, list):
            for offset, child in enumerate(value):
                visit(child, path + (offset,))
        elif isinstance(value, str) and (
                "secrets.HF_ORG_TOKEN" in value or "secrets.HF_TOKEN" in value):
            bindings.append((path, value))
    visit(workflow)
    assert bindings == [(("jobs", "triage", "steps", index, "env", "HF_TOKEN"), expected)]


def worker_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(triage.tempfile, "gettempdir", lambda: str(tmp_path))
    workspace = tmp_path / "gdw-readonly-triage-synthetic"
    workspace.mkdir(mode=0o700)
    database = workspace / "capture/working/gdw/candidate.sqlite3"
    database.parent.mkdir(parents=True, mode=0o700)
    for directory in (workspace / "capture", workspace / "capture/working", database.parent):
        directory.chmod(0o700)
    database.write_bytes(b"synthetic-candidate-not-a-database")
    database.chmod(0o600)
    return workspace, database


def worker_environment(monkeypatch):
    source, env = environment()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for key, value in {"HF_TOKEN": "synthetic-hf-token", "GH_TOKEN": "synthetic-gh-token",
        "PYTHONPATH": "/untrusted/pythonpath", "PYTHONSTARTUP": "/untrusted/startup",
        "HF_ENDPOINT": "https://untrusted.invalid"}.items():
        monkeypatch.setenv(key, value)
    return source


def bound_worker_report(request, effects=None):
    return {**triage._held_object_worker_report(), "state": "OBSERVED",
        **{key: request[key] for key in ("source_revision", "run_id", "run_attempt", "candidate_sha256")},
        "artifact_effect_observation": synthetic_effects() if effects is None else effects}


@pytest.mark.parametrize("defect", ["outside", "relative", "name", "symlink", "hardlink", "public", "wal", "shm", "journal", "reused"])
def test_worker_accepts_only_fixed_private_candidate_path(tmp_path, monkeypatch, defect):
    workspace, database = worker_workspace(tmp_path, monkeypatch)
    selected = str(workspace)
    if defect == "outside":
        monkeypatch.setattr(triage.tempfile, "gettempdir", lambda: str(tmp_path / "other"))
    elif defect == "relative": selected = workspace.name
    elif defect == "name":
        target = tmp_path / "arbitrary-workspace"
        workspace.rename(target)
        selected = str(target)
    elif defect == "symlink":
        target = workspace / "original"
        database.rename(target)
        database.symlink_to(target)
    elif defect == "hardlink": os.link(database, workspace / "alias")
    elif defect == "public": database.chmod(0o644)
    elif defect == "reused": (workspace / "artifact-effects").mkdir()
    else: Path(str(database) + "-" + defect).write_bytes(b"synthetic-sidecar")
    with pytest.raises(Exception):
        triage._object_worker_paths(selected)


@pytest.mark.parametrize("outcome", ["complete", "malformed", "oversized", "no_lf", "held", "candidate_changed",
    "source_changed", "cleanup_failed", "late", "different_source", "different_candidate", "unknown_effects"])
def test_supervised_v2_report_requires_cleanup_then_source_and_candidate_checks(tmp_path, monkeypatch, outcome):
    from scripts import probe_gdw_runtime_base as base
    workspace, database = worker_workspace(tmp_path, monkeypatch)
    source = worker_environment(monkeypatch)
    events = []
    digest = triage._candidate_digest
    def candidate(*args):
        events.append("candidate")
        return digest(*args)
    monkeypatch.setattr(triage, "_candidate_digest", candidate)
    def owned():
        events.append("source")
        if "cleanup" in events and outcome == "source_changed":
            raise RuntimeError("private-source-movement")
    def run(argv, *, deadline, limit, env, cwd, input_bytes):
        assert argv == [sys.executable, "-I", "-B", str(Path(triage.__file__).resolve()), "--artifact-object-worker"]
        assert limit == triage.OBJECT_WORKER_BYTES and cwd == workspace
        assert 0 < deadline - time.monotonic() <= triage.OBJECT_WORKER_SECONDS
        assert not {"PYTHONPATH", "PYTHONSTARTUP", "HF_ENDPOINT"} & set(env)
        assert env["PATH"] == "/usr/local/bin:/usr/bin:/bin"
        assert env["TMPDIR"] == str(workspace.parent)
        request = triage.validate_object_worker_request(json.loads(input_bytes))
        assert triage._canonical(request) == input_bytes and request["source_revision"] == source
        assert request["candidate_sha256"] == hashlib.sha256(database.read_bytes()).hexdigest()
        events.append("child")
        if outcome == "cleanup_failed":
            raise base.ProbeBlocked("RUNTIME_BASE_PROCESS_CLEANUP_UNCONFIRMED")
        events.append("cleanup")
        if outcome == "candidate_changed": database.write_bytes(b"changed-synthetic-candidate")
        if outcome == "late": monkeypatch.setattr(triage.time, "monotonic", lambda: deadline + 1)
        report = bound_worker_report(request)
        if outcome == "held": report = triage._held_object_worker_report()
        if outcome == "different_source": report["source_revision"] = "b" * 40
        if outcome == "different_candidate": report["candidate_sha256"] = "f" * 64
        if outcome == "unknown_effects": report["artifact_effect_observation"]["classification"] = "UNKNOWN"
        raw = triage._canonical(report)
        if outcome == "malformed": return b"{private-provider-output}\n"
        if outcome == "oversized": return raw + b" " * triage.OBJECT_WORKER_BYTES
        if outcome == "no_lf": return raw[:-1]
        return raw
    monkeypatch.setattr(base, "_run", run)
    if outcome == "complete":
        result = triage.supervised_artifact_effect_observation(workspace, owned, time.monotonic() + 240)
        assert result == synthetic_effects() and result["expected_object_count"] == 224
        assert events == ["candidate", "source", "child", "cleanup", "candidate", "source"]
    else:
        with pytest.raises(triage.TriageHeld, match="^READ_ONLY_TRIAGE_HELD$"):
            triage.supervised_artifact_effect_observation(workspace, owned, time.monotonic() + 240)
        assert events[:3] == ["candidate", "source", "child"]
        if outcome == "cleanup_failed": assert "cleanup" not in events and events.count("candidate") == 1


def test_real_isolated_child_uses_validated_nondefault_temp_root(tmp_path, monkeypatch):
    from scripts import probe_gdw_runtime_base as base
    workspace, database = worker_workspace(tmp_path, monkeypatch)
    worker_environment(monkeypatch)
    monkeypatch.setenv("TMPDIR", "/untrusted/ambient-temp-root")
    monkeypatch.setenv("TEMP", "/untrusted/ambient-temp-root")
    original_run = base._run
    code = """
import json, os, runpy, sys, tempfile
from pathlib import Path
assert sys.flags.isolated and sys.flags.ignore_environment and sys.dont_write_bytecode
assert not {'PYTHONPATH', 'PYTHONSTARTUP', 'TEMP', 'HF_ENDPOINT'} & set(os.environ)
module = runpy.run_path(sys.argv[1], run_name='synthetic_temp_root_transport')
request = module['validate_object_worker_request'](json.loads(sys.stdin.buffer.read(4097)))
directory, database = module['_object_worker_paths'](request['workspace'])
assert Path(tempfile.gettempdir()).resolve() == directory.parent
assert os.environ['TMPDIR'] == str(directory.parent)
assert module['_candidate_digest'](database, directory, request['deadline']) == request['candidate_sha256']
report = {**module['_held_object_worker_report'](), 'state': 'OBSERVED',
    **{key: request[key] for key in ('source_revision', 'run_id', 'run_attempt', 'candidate_sha256')},
    'artifact_effect_observation': json.loads(sys.argv[2])}
sys.stdout.buffer.write(module['encode_object_worker_report'](report))
"""
    def run(argv, **kwargs):
        assert argv[-1] == "--artifact-object-worker"
        assert kwargs["env"]["TMPDIR"] == str(workspace.parent)
        return original_run([sys.executable, "-I", "-B", "-c", code,
            str(Path(triage.__file__).resolve()), json.dumps(synthetic_effects())], **kwargs)
    monkeypatch.setattr(base, "_run", run)
    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    result = triage.supervised_artifact_effect_observation(workspace, lambda: None, time.monotonic() + 30)
    assert result == synthetic_effects()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == digest


def test_qualified_capture_crosses_real_parent_boundary_with_synthetic_child_wire(tmp_path, monkeypatch):
    import io
    from scripts import acquire_gdw_durable_storage as acquisition
    from scripts import qualify_gdw_store_recovery as recovery
    from scripts import probe_gdw_runtime_base as base
    workspace, database = worker_workspace(tmp_path, monkeypatch)
    worker_environment(monkeypatch)
    monkeypatch.setattr(acquisition, "_read", lambda _path: b"{}")
    monkeypatch.setattr(recovery, "_json", lambda _raw: {})
    monkeypatch.setattr(recovery, "validate_historical_anchors", lambda *_args: None)
    events = []
    def qualify(*_args, **_kwargs):
        events.append("qualified-both")
        return {"state": "LOGICAL_CONTINUITY_VERIFIED", "provider_writes_performed": False,
            "originals_mutated": False, "restore_admitted": False, "deployment_admitted": False,
            "databases": {label: {"state": "LOGICAL_CONTINUITY_VERIFIED", "captured_originals_unchanged": True,
                "all_declared_stored_values_unchanged": True} for label in ("gdw", "series_a")}}
    monkeypatch.setattr(recovery, "qualify_capture", qualify)
    monkeypatch.setattr(triage, "private_head_metadata", lambda _api:
        {"revision": "a" * 40, "head_presence": "ABSENT"})
    def run(_argv, **kwargs):
        assert events == ["qualified-both"]
        request = triage.validate_object_worker_request(json.loads(kwargs["input_bytes"]))
        assert request["candidate_sha256"] == hashlib.sha256(database.read_bytes()).hexdigest()
        output = io.BytesIO()
        with monkeypatch.context() as child:
            child.setattr(triage.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(kwargs["input_bytes"])))
            child.setattr(triage.sys, "stdout", SimpleNamespace(buffer=output))
            child.setattr(triage, "_artifact_object_worker_observation", lambda raw:
                bound_worker_report(triage.validate_object_worker_request(json.loads(raw))))
            assert triage.artifact_object_worker() == 0
        events.append("synthetic-child-wire")
        return output.getvalue()
    monkeypatch.setattr(base, "_run", run)
    api = SimpleNamespace(endpoint="https://huggingface.co")
    result = triage.observe_capture(api, workspace, lambda: None, time.monotonic() + 240)
    assert events == ["qualified-both", "synthetic-child-wire"]
    assert result["qualified_database_count"] == 2
    assert result["captured_originals_unchanged_during_qualification"] is True
    assert result["artifact_effect_observation"] == synthetic_effects()


def test_actual_isolated_child_serializer_roundtrips_v2_through_parent(tmp_path):
    from scripts import probe_gdw_runtime_base as base
    from tests.test_gdw_artifact_readonly_protocol import report
    code = """
import json, runpy, sys
module = runpy.run_path(sys.argv[1], run_name='synthetic_worker_transport')
entry = module['artifact_object_worker']
entry.__globals__['_artifact_object_worker_observation'] = lambda raw: json.loads(raw)
raise SystemExit(entry())
"""
    expected = report()
    raw = base._run([sys.executable, "-I", "-B", "-c", code, str(Path(triage.__file__).resolve())],
        deadline=time.monotonic() + 5, limit=4096, env={"PATH": "/usr/bin:/bin"}, cwd=tmp_path,
        input_bytes=triage._canonical(expected))
    assert triage.decode_object_worker_report(raw) == expected and raw.endswith(b"\n")


@pytest.mark.parametrize("outcome", ["ignore_alarm", "late", "oversized", "malformed"])
def test_actual_child_timeout_or_invalid_output_never_admits_result(tmp_path, monkeypatch, outcome):
    from scripts import probe_gdw_runtime_base as base
    original = base.subprocess.Popen
    launched = []
    def launch(*args, **kwargs):
        process = original(*args, **kwargs)
        launched.append(process)
        return process
    monkeypatch.setattr(base.subprocess, "Popen", launch)
    marker = tmp_path / "started"
    if outcome == "ignore_alarm":
        code = """
import os, signal, sys, time
from pathlib import Path
signal.signal(signal.SIGALRM, signal.SIG_IGN)
signal.setitimer(signal.ITIMER_REAL, 0.01)
Path(sys.argv[1]).write_text(str(os.getpid()))
time.sleep(60)
"""
    elif outcome == "late": code = "import time; time.sleep(2); print('{}')"
    elif outcome == "oversized": code = "import sys; sys.stdout.buffer.write(b'x' * 8192); sys.stdout.buffer.flush()"
    else: code = "print('{malformed}')"
    def invoke():
        return base._run([sys.executable, "-I", "-B", "-c", code, str(marker)],
            deadline=time.monotonic() + (1 if outcome in {"ignore_alarm", "late"} else 5),
            limit=4096, env={"PATH": "/usr/bin:/bin"})
    if outcome == "malformed":
        with pytest.raises(Exception): triage.decode_object_worker_report(invoke())
    else:
        with pytest.raises(base.ProbeBlocked): invoke()
    assert len(launched) == 1 and launched[0].poll() is not None
    with pytest.raises(ProcessLookupError): os.kill(launched[0].pid, 0)
    if outcome == "ignore_alarm": assert int(marker.read_text()) == launched[0].pid


@pytest.mark.parametrize("defect", [None, "candidate", "context", "run", "checkout", "sdk", "prior", "source_changed"])
def test_worker_keeps_native_identity_prior_attempt_and_private_output_controls(tmp_path, monkeypatch, capfd, defect):
    import logging
    workspace, database = worker_workspace(tmp_path, monkeypatch)
    source = worker_environment(monkeypatch)
    for key in ("HF_HUB_VERBOSITY", "HF_DEBUG", "HF_HUB_DISABLE_PROGRESS_BARS",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN", "HF_HUB_DISABLE_TELEMETRY", "HF_HOME",
        "GDW_PROOF_DIR", "GDW_RECEIPT_PROJECTION_DIR"):
        monkeypatch.setenv(key, "synthetic-parent")
    if defect == "context": monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    deadline = time.monotonic() + 30
    request = {"schema": triage.OBJECT_WORKER_SCHEMA, "workspace": str(workspace),
        "source_revision": source, "run_id": 901 if defect == "run" else 900, "run_attempt": 1,
        "candidate_sha256": "c" * 64 if defect == "candidate" else hashlib.sha256(database.read_bytes()).hexdigest(),
        "deadline": deadline}
    monkeypatch.setattr(triage.subprocess, "run", lambda *a, **kw:
        SimpleNamespace(stdout=("d" * 40 if defect == "checkout" else source) + "\n"))
    class Session:
        def __init__(self): self.headers = {}
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def get(self, *_args, **_kwargs): raise AssertionError("no network in offline worker test")
    calls = []
    api = object()
    def verified(session, context):
        assert context == {"source_revision": source, "run_id": 900, "run_attempt": 1}
        assert session.headers["Authorization"] == "Bearer synthetic-gh-token"
        calls.append("native")
    def prior(_session):
        calls.append("prior")
        return {"prior_native_metadata_verified": defect != "prior"}
    def factory(**kwargs):
        assert kwargs == {"endpoint": "https://huggingface.co", "token": "synthetic-hf-token"}
        calls.append("api")
        return api
    def observed(actual_api, candidate, target, owned, actual_deadline):
        assert actual_api is api and candidate == database and target == workspace / "artifact-effects"
        assert actual_deadline == deadline and os.environ["HF_HOME"] == str(workspace / "object-worker-cache")
        owned()
        calls.append("read")
        os.write(1, b"private-worker-test-marker\n")
        os.write(2, b"private-worker-test-marker\n")
        return synthetic_effects()
    def current(_session, suffix):
        assert suffix == "git/ref/heads/main"
        return {"object": {"sha": "d" * 40 if defect == "source_changed" else source}}
    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(Session=Session))
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(
        __version__="1.33.0" if defect == "sdk" else "1.31.0", HfApi=factory))
    monkeypatch.setattr(triage, "verify_native", verified)
    monkeypatch.setattr(triage, "verify_prior_attempt", prior)
    monkeypatch.setattr(triage, "github_json", current)
    monkeypatch.setattr(triage, "artifact_effect_observation", observed)
    previous_logging = logging.root.manager.disable
    previous_mask = os.umask(0o077)
    try:
        if defect is None:
            result = triage._artifact_object_worker_observation(triage._canonical(request))
            assert triage.validate_object_worker_report(result) == bound_worker_report(request)
        else:
            with pytest.raises(triage.TriageHeld):
                triage._artifact_object_worker_observation(triage._canonical(request))
    finally:
        os.umask(previous_mask)
        logging.disable(previous_logging)
    assert calls == (["native", "prior", "api", "read"] if defect is None else
        ["native", "prior", "api"] if defect == "source_changed" else
        ["native", "prior"] if defect == "prior" else [])
    captured = capfd.readouterr()
    assert "private-worker-test-marker" not in captured.out + captured.err
    assert "synthetic-hf-token" not in captured.out + captured.err
