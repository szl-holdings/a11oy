#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Admit one fresh continuation from the accepted read-only GDW diagnostic.

The historical acquisition is never retried.  This helper binds its fixed
read-only successor diagnostic, re-qualifies the preserved capture, and proves
the exact current retained-artifact set and private HEAD are still absent.  It
performs no provider mutation.  The effectful worker must repeat these fences
before its own first write and must never be re-run after an uncertain outcome.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

import gdw_durable_storage as storage
from scripts import gdw_acquisition_evidence as native
from scripts import triage_gdw_artifacts_readonly as triage


SCHEMA = "szl.gdw-diagnostic-continuation-prerequisite/v1"
CLASSIFICATION_SCHEMA = "szl.gdw-diagnostic-continuation-classification/v1"
DIAGNOSTIC_SOURCE = "1b2775485b05915662624c947004cd887b21cf5d"
TRANSITION_PARENT_SOURCE = "e97df96f1a228b866287f17d8792bea8d82b415d"
DIAGNOSTIC_RUN = 37318344262
DIAGNOSTIC_ATTEMPT = 1
DIAGNOSTIC_ARTIFACT = 11349341865
DIAGNOSTIC_ARTIFACT_BYTES = 1091
DIAGNOSTIC_ARCHIVE_SHA256 = "055c8200399d6f27e7fee4b0a371e775803dc62daf9cdbb396ae445524025d21"
DIAGNOSTIC_REPORT_SHA256 = "ecfc526f3e68775934e0f0c448670cc3c0c0bd899072ed579bb6d26ae0e4d250"
DIAGNOSTIC_DATASET_REVISION = "f5dbdcaea236db3b0d25b8d8cfe8d64369b25d78"
EXPECTED_OBJECT_COUNT = 224
EXPECTED_OBJECT_SET_SHA256 = "7a28c53fa647e639375c6a90d3e34e89fe74bc2004f8161b5f38ac793301be42"
EMPTY_OBJECT_SET_SHA256 = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
RECONCILIATION_JOB_KEY = "recovery-reconciliation"
RECONCILIATION_JOB = "Reconcile the accepted diagnostic before fresh continuation"
ACQUISITION_JOB_KEY = native.ACQUISITION_JOB_KEY
ACQUISITION_JOB = native.ACQUISITION_JOB
MAX_SECONDS = 360
OBJECT_WORKER_SCHEMA = "szl.gdw-continuation-object-worker/v1"
OBJECT_WORKER_BYTES = 4096
OBJECT_WORKER_SECONDS = 300
SAFE_DIAGNOSTIC_STAGES = frozenset({
    "PROVIDER_CLIENT_INITIALIZATION",
    "CURRENT_SOURCE_AUTHORITY",
    "CAPTURE_REFERENCES",
    "PREQUALIFICATION_DATASET_STATE",
    "CAPTURE_LOGICAL_CONTINUITY",
    "ARTIFACT_NAMESPACE_ABSENCE",
    "POSTQUALIFICATION_DATASET_STATE",
    "FINAL_ABSENCE_CONTRACT",
})


class ContinuationBlocked(RuntimeError):
    def __init__(self, code="DIAGNOSTIC_CONTINUATION_UNAVAILABLE", stage=None):
        self.code = code if type(code) is str and code in {
            "CURRENT_CONTEXT_UNQUALIFIED", "DIAGNOSTIC_PRODUCER_UNQUALIFIED",
            "DIAGNOSTIC_ARTIFACT_UNQUALIFIED", "DIAGNOSTIC_REPORT_UNQUALIFIED",
            "CURRENT_ABSENCE_UNVERIFIED", "CONTINUATION_REPORT_UNQUALIFIED",
            "DIAGNOSTIC_CONTINUATION_UNAVAILABLE",
        } else "DIAGNOSTIC_CONTINUATION_UNAVAILABLE"
        self.stage = stage if type(stage) is str and stage in SAFE_DIAGNOSTIC_STAGES else None
        super().__init__(self.code)


def _require(value, code):
    if value is not True:
        raise ContinuationBlocked(code)


@contextmanager
def _diagnostic_stage(stage):
    """Expose only a fixed non-sensitive phase when a read-only gate holds."""
    if stage not in SAFE_DIAGNOSTIC_STAGES:
        raise ContinuationBlocked()
    try:
        yield
    except ContinuationBlocked as error:
        if error.stage is not None:
            raise
        raise ContinuationBlocked(error.code, stage) from None
    except Exception:
        raise ContinuationBlocked("CURRENT_ABSENCE_UNVERIFIED", stage) from None


def _integer(value):
    return type(value) is int and value > 0


def _run_binding(run, *, source, run_id, event, path, status, conclusion):
    _require(type(run) is dict and run.get("id") == run_id
        and run.get("run_attempt") == 1 and run.get("head_sha") == source
        and run.get("head_branch") == "main" and run.get("event") == event
        and run.get("path") == path and run.get("status") == status
        and run.get("conclusion") == conclusion
        and run.get("repository", {}).get("id") == 1225834126
        and run.get("repository", {}).get("full_name") == native.REPOSITORY
        and run.get("head_repository", {}).get("id") == 1225834126,
        "DIAGNOSTIC_PRODUCER_UNQUALIFIED" if run_id == DIAGNOSTIC_RUN else "CURRENT_CONTEXT_UNQUALIFIED")


def verify_current_context(evidence, job_key, job_name):
    """Bind one signed direct successor and its unique first push run."""
    try:
        _require(job_key in {RECONCILIATION_JOB_KEY, ACQUISITION_JOB_KEY}
            and job_name in {RECONCILIATION_JOB, ACQUISITION_JOB}
            and evidence.executing_job == job_key and evidence.event == "push"
            and evidence.attempt == 1 and evidence.repository_id == 1225834126
            and os.environ.get("GITHUB_WORKFLOW_SHA") == evidence.source,
            "CURRENT_CONTEXT_UNQUALIFIED")
        evidence.observe_run()
        _run_binding(evidence.run, source=evidence.source, run_id=evidence.run_id,
            event="push", path=native.WORKFLOW, status="in_progress", conclusion=None)
        job = evidence.jobs.get(job_name)
        source_job = evidence.jobs.get(native.SOURCE_JOB)
        _require(type(job) is dict and _integer(job.get("id"))
            and job.get("status") == "in_progress" and job.get("conclusion") is None
            and job.get("completed_at") is None
            and evidence.started <= native.timestamp(job.get("started_at")) <= datetime.now(timezone.utc)
            and type(source_job) is dict and source_job.get("status") == "completed"
            and source_job.get("conclusion") == "success", "CURRENT_CONTEXT_UNQUALIFIED")
        commit = evidence.request(f"/repos/{native.REPOSITORY}/git/commits/{evidence.source}")
        parents = commit.get("parents")
        _require(commit.get("sha") == evidence.source and type(parents) is list and len(parents) == 1
            and parents[0].get("sha") == TRANSITION_PARENT_SOURCE
            and commit.get("verification", {}).get("verified") is True
            and commit.get("verification", {}).get("reason") == "valid",
            "CURRENT_CONTEXT_UNQUALIFIED")
        parent = evidence.request(
            f"/repos/{native.REPOSITORY}/git/commits/{TRANSITION_PARENT_SOURCE}")
        comparison = evidence.request(f"/repos/{native.REPOSITORY}/compare/"
            f"{DIAGNOSTIC_SOURCE}...{TRANSITION_PARENT_SOURCE}")
        _require(parent.get("sha") == TRANSITION_PARENT_SOURCE
            and parent.get("verification", {}).get("verified") is True
            and parent.get("verification", {}).get("reason") == "valid"
            and comparison.get("status") in {"identical", "ahead"}
            and comparison.get("merge_base_commit", {}).get("sha") == DIAGNOSTIC_SOURCE,
            "CURRENT_CONTEXT_UNQUALIFIED")
        listing = evidence.request(f"/repos/{native.REPOSITORY}/actions/workflows/hf-sync.yml/runs"
            f"?event=push&head_sha={evidence.source}&per_page=100")
        rows = listing.get("workflow_runs")
        _require(type(listing.get("total_count")) is int and listing["total_count"] == 1
            and type(rows) is list and len(rows) == 1 and rows[0].get("id") == evidence.run_id,
            "CURRENT_CONTEXT_UNQUALIFIED")
        evidence.require_current_main()
        return {"source_revision": evidence.source, "run_id": evidence.run_id,
                "run_attempt": evidence.attempt, "job_id": job["id"], "job_key": job_key}
    except ContinuationBlocked:
        raise
    except Exception:
        raise ContinuationBlocked("CURRENT_CONTEXT_UNQUALIFIED") from None


def validate_diagnostic_report(raw):
    try:
        value = native.strict(raw, 4096)
        _require(hashlib.sha256(raw).hexdigest() == DIAGNOSTIC_REPORT_SHA256
            and value.get("schema") == triage.SCHEMA and value.get("state") == "OBSERVED"
            and value.get("diagnostic_code") == "READ_ONLY_OBSERVATION_COMPLETE"
            and value.get("source_revision") == DIAGNOSTIC_SOURCE
            and value.get("run_id") == DIAGNOSTIC_RUN and value.get("run_attempt") == 1
            and value.get("read_boundary") == "COMPLETE"
            and value.get("capture_qualification") == "LOGICAL_CONTINUITY_VERIFIED"
            and value.get("qualified_database_count") == 2
            and value.get("captured_originals_unchanged_during_qualification") is True
            and value.get("metadata_stable_during_read") is True
            and value.get("provider_writes_performed") is False
            and value.get("restore_admitted") is False and value.get("deployment_admitted") is False
            and value.get("retry_admitted") is False
            and value.get("prior_provider_effects") == "NOT_ESTABLISHED"
            and value.get("historical_writer_attribution") == "NOT_ESTABLISHED"
            and value.get("private_head_metadata") == {
                "revision": DIAGNOSTIC_DATASET_REVISION, "head_presence": "ABSENT"},
            "DIAGNOSTIC_REPORT_UNQUALIFIED")
        effects = value.get("artifact_effect_observation")
        _require(type(effects) is dict
            and effects.get("classification") == "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME"
            and effects.get("expected_object_count") == EXPECTED_OBJECT_COUNT
            and effects.get("missing_object_count") == EXPECTED_OBJECT_COUNT
            and effects.get("present_object_count") == 0
            and effects.get("expected_object_set_sha256") == EXPECTED_OBJECT_SET_SHA256
            and effects.get("observed_object_set_sha256") == EMPTY_OBJECT_SET_SHA256
            and effects.get("all_retained_rows_validated") is True
            and effects.get("candidate_unchanged") is True
            and effects.get("provider_objects_fully_validated") is False
            and effects.get("provider_writes_performed") is False
            and effects.get("historical_writer_attribution") == "NOT_ESTABLISHED",
            "DIAGNOSTIC_REPORT_UNQUALIFIED")
        return value
    except ContinuationBlocked:
        raise
    except Exception:
        raise ContinuationBlocked("DIAGNOSTIC_REPORT_UNQUALIFIED") from None


def _diagnostic_artifact(evidence):
    """Download only the closed diagnostic JSON, never a capture archive."""
    run = evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{DIAGNOSTIC_RUN}/attempts/1")
    _run_binding(run, source=DIAGNOSTIC_SOURCE, run_id=DIAGNOSTIC_RUN,
        event="workflow_dispatch", path=triage.WORKFLOW, status="completed", conclusion="success")
    listing = evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{DIAGNOSTIC_RUN}/attempts/1/jobs?per_page=100")
    jobs = listing.get("jobs")
    _require(type(jobs) is list and listing.get("total_count") == 2 and len(jobs) == 2
        and {job.get("name") for job in jobs} == {"contract", "triage"}
        and all(job.get("status") == "completed" and job.get("conclusion") == "success"
                and job.get("run_id") == DIAGNOSTIC_RUN and job.get("run_attempt") == 1
                and job.get("head_sha") == DIAGNOSTIC_SOURCE for job in jobs),
        "DIAGNOSTIC_PRODUCER_UNQUALIFIED")
    artifact = evidence.request(f"/repos/{native.REPOSITORY}/actions/artifacts/{DIAGNOSTIC_ARTIFACT}")
    _require(artifact.get("id") == DIAGNOSTIC_ARTIFACT
        and artifact.get("name") == f"gdw-artifact-readonly-{DIAGNOSTIC_RUN}-1"
        and artifact.get("size_in_bytes") == DIAGNOSTIC_ARTIFACT_BYTES
        and artifact.get("expired") is False
        and artifact.get("digest") == "sha256:" + DIAGNOSTIC_ARCHIVE_SHA256
        and artifact.get("workflow_run", {}).get("id") == DIAGNOSTIC_RUN
        and artifact.get("workflow_run", {}).get("head_sha") == DIAGNOSTIC_SOURCE,
        "DIAGNOSTIC_ARTIFACT_UNQUALIFIED")
    evidence.budget()
    try:
        with evidence.client.stream("GET",
                f"{native.API}/repos/{native.REPOSITORY}/actions/artifacts/{DIAGNOSTIC_ARTIFACT}/zip",
                headers={"Authorization": "Bearer " + evidence.token,
                         "Accept": "application/vnd.github+json"}) as response:
            _require(response.status_code == 302, "DIAGNOSTIC_ARTIFACT_UNQUALIFIED")
            location = response.headers.get("location", "")
        parsed = urlsplit(location)
        host = parsed.hostname or ""
        _require(parsed.scheme == "https" and parsed.port in (None, 443)
            and not parsed.username and not parsed.password and not parsed.fragment
            and len(location) <= 16384
            and (host.endswith(".blob.core.windows.net") or host.endswith(".actions.githubusercontent.com")),
            "DIAGNOSTIC_ARTIFACT_UNQUALIFIED")
        with evidence.client.stream("GET", location, headers={}) as response:
            _require(response.status_code == 200, "DIAGNOSTIC_ARTIFACT_UNQUALIFIED")
            archive = bytearray()
            for chunk in response.iter_bytes(chunk_size=4096):
                evidence.budget()
                _require(len(archive) + len(chunk) <= DIAGNOSTIC_ARTIFACT_BYTES,
                    "DIAGNOSTIC_ARTIFACT_UNQUALIFIED")
                archive.extend(chunk)
        members = native.validate_archive(artifact, bytes(archive), artifact_id=DIAGNOSTIC_ARTIFACT,
            expected_digest=DIAGNOSTIC_ARCHIVE_SHA256,
            expected_name=f"gdw-artifact-readonly-{DIAGNOSTIC_RUN}-1",
            source=DIAGNOSTIC_SOURCE, run_id=DIAGNOSTIC_RUN, repository_id=1225834126,
            members=frozenset({"gdw-artifact-triage.json"}))
        return validate_diagnostic_report(members["gdw-artifact-triage.json"])
    except ContinuationBlocked:
        raise
    except Exception:
        raise ContinuationBlocked("DIAGNOSTIC_ARTIFACT_UNQUALIFIED") from None


def _object_worker_request(value, *, now=None):
    _require(type(value) is dict and set(value) == {"schema", "workspace",
        "source_revision", "run_id", "run_attempt", "job_key",
        "candidate_sha256", "deadline"}, "CURRENT_ABSENCE_UNVERIFIED")
    _require(value["schema"] == OBJECT_WORKER_SCHEMA
        and type(value["workspace"]) is str and 0 < len(value["workspace"]) <= 1024
        and not any(character in value["workspace"] for character in ("\0", "\n", "\r"))
        and storage._revision(value["source_revision"])
        and type(value["run_id"]) is int and value["run_id"] > 0
        and type(value["run_attempt"]) is int and value["run_attempt"] == 1
        and value["job_key"] in {RECONCILIATION_JOB_KEY, ACQUISITION_JOB_KEY}
        and storage._digest(value["candidate_sha256"]), "CURRENT_ABSENCE_UNVERIFIED")
    instant = time.monotonic() if now is None else now
    _require(type(value["deadline"]) in (int, float)
        and 0 < value["deadline"] - instant <= OBJECT_WORKER_SECONDS,
        "CURRENT_ABSENCE_UNVERIFIED")
    return dict(value)


def _object_worker_report(request, effects):
    return {"schema": OBJECT_WORKER_SCHEMA, "state": "OBSERVED",
        **{key: request[key] for key in ("source_revision", "run_id", "run_attempt",
                                         "job_key", "candidate_sha256")},
        "artifact_effect_observation": effects,
        "provider_writes_performed": False, "replay_admitted": False,
        "restore_admitted": False, "deployment_admitted": False}


def _held_object_worker_report():
    return {"schema": OBJECT_WORKER_SCHEMA, "state": "HELD",
        "source_revision": None, "run_id": None, "run_attempt": None,
        "job_key": None, "candidate_sha256": None,
        "artifact_effect_observation": None,
        "provider_writes_performed": False, "replay_admitted": False,
        "restore_admitted": False, "deployment_admitted": False}


def _validate_object_worker_report(value):
    _require(type(value) is dict and set(value) == set(_held_object_worker_report())
        and value.get("schema") == OBJECT_WORKER_SCHEMA
        and all(value.get(key) is False for key in ("provider_writes_performed",
            "replay_admitted", "restore_admitted", "deployment_admitted")),
        "CURRENT_ABSENCE_UNVERIFIED")
    if value.get("state") == "HELD":
        _require(all(value.get(key) is None for key in ("source_revision", "run_id",
            "run_attempt", "job_key", "candidate_sha256", "artifact_effect_observation")),
            "CURRENT_ABSENCE_UNVERIFIED")
        return dict(value)
    _require(value.get("state") == "OBSERVED"
        and storage._revision(value.get("source_revision"))
        and _integer(value.get("run_id")) and value.get("run_attempt") == 1
        and value.get("job_key") in {RECONCILIATION_JOB_KEY, ACQUISITION_JOB_KEY}
        and storage._digest(value.get("candidate_sha256")),
        "CURRENT_ABSENCE_UNVERIFIED")
    effects = triage.validate_artifact_effect_observation(
        value.get("artifact_effect_observation"))
    return dict(value, artifact_effect_observation=effects)


def _object_workspace(value, deadline):
    workspace = Path(value).resolve()
    _require(workspace.is_absolute() and workspace == Path(value)
        and workspace.name in {"capture", "continuation-prewrite"},
        "CURRENT_ABSENCE_UNVERIFIED")
    storage._private_directory(workspace)
    candidate = workspace / "working/gdw/candidate.sqlite3"
    storage._private_path(candidate, workspace)
    _require(not any(os.path.lexists(str(candidate) + suffix)
        for suffix in ("-wal", "-shm", "-journal")), "CURRENT_ABSENCE_UNVERIFIED")
    identity = storage._file_identity(candidate, workspace,
        storage.MAX_SNAPSHOT_BYTES, deadline)
    return workspace, candidate, identity["sha256"]


def supervised_artifact_absence(workspace, require_source, deadline):
    """Observe exact object paths in a killable, reaped isolated child."""
    import probe_gdw_runtime_base as base
    workspace, candidate, candidate_sha256 = _object_workspace(workspace, deadline)
    job_key = os.environ.get("GITHUB_JOB")
    request = _object_worker_request({"schema": OBJECT_WORKER_SCHEMA,
        "workspace": str(workspace), "source_revision": os.environ.get("GITHUB_SHA"),
        "run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
        "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")),
        "job_key": job_key, "candidate_sha256": candidate_sha256,
        "deadline": min(deadline - 10, time.monotonic() + OBJECT_WORKER_SECONDS)})
    require_source()
    names = ("HF_TOKEN", "GH_TOKEN", "GITHUB_ACTIONS", "GITHUB_REPOSITORY",
        "GITHUB_REPOSITORY_ID", "GITHUB_REF", "GITHUB_SHA", "GITHUB_WORKFLOW_REF",
        "GITHUB_WORKFLOW_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
        "GITHUB_EVENT_NAME", "GITHUB_JOB")
    environment = {name: os.environ[name] for name in names if name in os.environ}
    environment.update(PATH="/usr/local/bin:/usr/bin:/bin", PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_DISABLE_PROGRESS_BARS="1", HF_HUB_DISABLE_TELEMETRY="1",
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
    raw = base._run([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
        "--artifact-object-worker"], deadline=request["deadline"], limit=OBJECT_WORKER_BYTES,
        env=environment, cwd=workspace, input_bytes=storage.canonical(request),
        _capture_failure=True)
    require_source()
    _workspace, _candidate, after = _object_workspace(workspace, deadline)
    _require(after == candidate_sha256, "CURRENT_ABSENCE_UNVERIFIED")
    report = _validate_object_worker_report(native.strict(raw, OBJECT_WORKER_BYTES))
    _require(storage.canonical(report) == raw and report.get("state") == "OBSERVED"
        and all(report.get(key) == request[key] for key in ("source_revision", "run_id",
            "run_attempt", "job_key", "candidate_sha256")), "CURRENT_ABSENCE_UNVERIFIED")
    return report["artifact_effect_observation"]


def _artifact_object_worker_observation(raw):
    request = _object_worker_request(native.strict(raw, OBJECT_WORKER_BYTES))
    _require(storage.canonical(request) == raw, "CURRENT_ABSENCE_UNVERIFIED")
    workspace, candidate, digest = _object_workspace(request["workspace"], request["deadline"])
    _require(digest == request["candidate_sha256"], "CURRENT_ABSENCE_UNVERIFIED")
    evidence = native.NativeEvidence(dict(os.environ), request["deadline"])
    job_name = RECONCILIATION_JOB if request["job_key"] == RECONCILIATION_JOB_KEY else ACQUISITION_JOB
    context = verify_current_context(evidence, request["job_key"], job_name)
    _require(all(context[key] == request[key] for key in
        ("source_revision", "run_id", "run_attempt", "job_key")),
        "CURRENT_ABSENCE_UNVERIFIED")
    # The isolated child deliberately inherits no caller-selected artifact
    # roots.  Bind the reviewed canonical roots before reconstructing the
    # captured rows, matching the accepted read-only diagnostic worker.
    os.environ.update(triage.trusted_artifact_environment())
    api = storage._hub_api(os.environ.get("HF_TOKEN", ""))
    effects = triage.artifact_namespace_absence(api, candidate,
        workspace / "artifact-effects", evidence.require_current_main, request["deadline"])
    _workspace, _candidate, after = _object_workspace(workspace, request["deadline"])
    _require(after == digest, "CURRENT_ABSENCE_UNVERIFIED")
    evidence.require_current_main()
    return _object_worker_report(request, effects)


def artifact_object_worker():
    import logging
    from scripts import preserve_hf_gdw_store as preservation
    report = _held_object_worker_report()
    try:
        os.umask(0o077)
        logging.disable(logging.CRITICAL)
        with preservation._private_output():
            report = _validate_object_worker_report(_artifact_object_worker_observation(
                sys.stdin.buffer.read(OBJECT_WORKER_BYTES + 1)))
    except BaseException:
        report = _held_object_worker_report()
    sys.stdout.buffer.write(storage.canonical(report))
    return 0 if report["state"] == "OBSERVED" else 2


def observe_current_absence(api, workspace, evidence, deadline):
    """Reproduce the fixed capture and bind it to verified protected source."""
    from scripts import acquire_gdw_durable_storage as acquisition
    from scripts import qualify_gdw_store_recovery as recovery
    with _diagnostic_stage("CURRENT_SOURCE_AUTHORITY"):
        source_revision = getattr(evidence, "source", None)
        require_source = getattr(evidence, "require_current_main", None)
        _require(storage._revision(source_revision) and callable(require_source),
            "CURRENT_ABSENCE_UNVERIFIED")
    with _diagnostic_stage("CAPTURE_REFERENCES"):
        reference_bytes = acquisition._read(acquisition.ROOT / acquisition.CAPTURE_REFERENCE)
        anchor_bytes = acquisition._read(acquisition.ROOT / acquisition.HISTORICAL_REFERENCE)
        reference, anchors = recovery._json(reference_bytes), recovery._json(anchor_bytes)
        capture_hash = hashlib.sha256(reference_bytes).hexdigest()
        recovery.validate_historical_anchors(anchors, reference, capture_hash)
    with _diagnostic_stage("PREQUALIFICATION_DATASET_STATE"):
        require_source()
        before = triage.private_head_metadata(api)
    with _diagnostic_stage("CAPTURE_LOGICAL_CONTINUITY"):
        qualified = recovery.qualify_capture(recovery.ReadOnlyCaptureHub(api), reference,
            workspace / "capture", require_source, deadline, historical_anchors=anchors,
            capture_report_sha256=capture_hash)
        _require(qualified.get("state") == "LOGICAL_CONTINUITY_VERIFIED"
            and qualified.get("provider_writes_performed") is False
            and qualified.get("originals_mutated") is False
            and qualified.get("restore_admitted") is False
            and qualified.get("deployment_admitted") is False,
            "CURRENT_ABSENCE_UNVERIFIED")
        databases = triage._qualified_capture_databases(qualified,
            frozenset(recovery.preservation.DATABASES))
    with _diagnostic_stage("ARTIFACT_NAMESPACE_ABSENCE"):
        effects = supervised_artifact_absence(workspace / "capture", require_source, deadline)
    with _diagnostic_stage("POSTQUALIFICATION_DATASET_STATE"):
        require_source()
        after = triage.private_head_metadata(api)
        require_source()
    with _diagnostic_stage("FINAL_ABSENCE_CONTRACT"):
        _require(before == after and storage._revision(before.get("revision"))
            and before.get("head_presence") == "ABSENT"
            and len(databases) == 2
            and effects.get("classification") == "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME"
            and effects.get("expected_object_count") == EXPECTED_OBJECT_COUNT
            and effects.get("missing_object_count") == EXPECTED_OBJECT_COUNT
            and effects.get("present_object_count") == 0
            and effects.get("expected_object_set_sha256") == EXPECTED_OBJECT_SET_SHA256
            and effects.get("observed_object_set_sha256") == EMPTY_OBJECT_SET_SHA256
            and effects.get("all_retained_rows_validated") is True
            and effects.get("candidate_unchanged") is True
            and effects.get("provider_writes_performed") is False,
            "CURRENT_ABSENCE_UNVERIFIED")
        _require(qualified.get("inspector_source_revision") in (None, source_revision),
            "CURRENT_ABSENCE_UNVERIFIED")
        qualified["inspector_source_revision"] = source_revision
    return qualified, {
        "dataset_revision": before["revision"],
        "head_presence": "ABSENT",
        "expected_object_count": EXPECTED_OBJECT_COUNT,
        "expected_object_set_sha256": EXPECTED_OBJECT_SET_SHA256,
        "present_object_count": 0,
        "missing_object_count": EXPECTED_OBJECT_COUNT,
    }


def _report(context, qualification_sha256, dataset_revision):
    return {"schema": SCHEMA, "state": "PREREQUISITE_VERIFIED",
        "scope": "ONE_SIGNED_SUCCESSOR_ONE_RUN_FRESH_CONTINUATION_ONLY", **context,
        "diagnostic_source_revision": DIAGNOSTIC_SOURCE,
        "diagnostic_run_id": DIAGNOSTIC_RUN, "diagnostic_run_attempt": DIAGNOSTIC_ATTEMPT,
        "diagnostic_artifact_id": DIAGNOSTIC_ARTIFACT,
        "diagnostic_archive_sha256": DIAGNOSTIC_ARCHIVE_SHA256,
        "diagnostic_report_sha256": DIAGNOSTIC_REPORT_SHA256,
        "dataset_revision": dataset_revision, "head_presence": "ABSENT",
        "expected_object_count": EXPECTED_OBJECT_COUNT,
        "expected_object_set_sha256": EXPECTED_OBJECT_SET_SHA256,
        "present_object_count": 0, "missing_object_count": EXPECTED_OBJECT_COUNT,
        "qualification_sha256": qualification_sha256,
        "historical_provider_effects": "NOT_ESTABLISHED",
        "historical_writer_attribution": "NOT_ESTABLISHED",
        "provider_writes_performed": False, "replay_admitted": False,
        "restore_admitted": False, "deployment_admitted": False,
        "secret_values_recorded": False}


def validate_reconciliation_report(raw):
    try:
        value = native.strict(raw, 8192)
        context = {key: value.get(key) for key in
            ("source_revision", "run_id", "run_attempt", "job_id", "job_key")}
        _require(storage._revision(context["source_revision"])
            and context["source_revision"] != DIAGNOSTIC_SOURCE
            and all(_integer(context[key]) for key in ("run_id", "run_attempt", "job_id"))
            and context["run_attempt"] == 1 and context["job_key"] == RECONCILIATION_JOB_KEY
            and storage._digest(value.get("qualification_sha256"))
            and storage._revision(value.get("dataset_revision")),
            "CONTINUATION_REPORT_UNQUALIFIED")
        _require(storage.canonical(_report(context, value["qualification_sha256"],
            value["dataset_revision"])) == raw,
            "CONTINUATION_REPORT_UNQUALIFIED")
        return value
    except ContinuationBlocked:
        raise
    except Exception:
        raise ContinuationBlocked("CONTINUATION_REPORT_UNQUALIFIED") from None


def execute_native_reconciliation(workspace: Path, deadline):
    _require(type(deadline) in (int, float) and 0 < deadline - time.monotonic() <= MAX_SECONDS,
        "DIAGNOSTIC_CONTINUATION_UNAVAILABLE")
    storage._private_directory(workspace)
    evidence = native.NativeEvidence(dict(os.environ), deadline)
    context = verify_current_context(evidence, RECONCILIATION_JOB_KEY, RECONCILIATION_JOB)
    _diagnostic_artifact(evidence)
    try:
        with _diagnostic_stage("PROVIDER_CLIENT_INITIALIZATION"):
            api = storage._hub_api(os.environ.get("HF_TOKEN", ""))
        qualified, observation = observe_current_absence(api, workspace,
            evidence, deadline)
    except ContinuationBlocked:
        raise
    except Exception:
        raise ContinuationBlocked("CURRENT_ABSENCE_UNVERIFIED") from None
    encoded_qualification = storage.canonical(qualified)
    report = _report(context, hashlib.sha256(encoded_qualification).hexdigest(),
        observation["dataset_revision"])
    return validate_reconciliation_report(storage.canonical(report)), encoded_qualification


def classify_reconciliation(report_bytes, qualification_bytes, source_revision):
    report = validate_reconciliation_report(report_bytes)
    _require(report["source_revision"] == source_revision
        and hashlib.sha256(qualification_bytes).hexdigest() == report["qualification_sha256"],
        "CONTINUATION_REPORT_UNQUALIFIED")
    native.strict(qualification_bytes, 1024 * 1024)
    return {"schema": CLASSIFICATION_SCHEMA, "state": "DIAGNOSTIC_CONTINUATION_ONLY",
        "source_revision": source_revision, "mode": "managed-recovery",
        "reconciliation_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "qualification_sha256": report["qualification_sha256"],
        "provider_writes_performed": False, "replay_admitted": False,
        "restore_admitted": False, "deployment_admitted": False,
        "secret_values_recorded": False}


class DiagnosticContinuationFence:
    """Track only writes acknowledged by this one non-retriable worker."""

    def __init__(self, api, evidence, deadline, workspace, dataset_revision):
        _require(storage._value(api, "endpoint") == storage.ENDPOINT,
            "CURRENT_ABSENCE_UNVERIFIED")
        _require(storage._revision(dataset_revision), "CURRENT_ABSENCE_UNVERIFIED")
        self.api = api
        self.evidence = evidence
        self.deadline = deadline
        self.workspace = storage._private_directory(workspace)
        self.dataset_revision = dataset_revision
        self.expected = None
        self.bind_count = 0
        self.acknowledged = {}
        self.pending = {}

    def require_head_absent(self):
        try:
            storage._deadline(self.deadline)
            self.evidence.require_current_main()
            observed = triage.private_head_metadata(self.api)
            _require(observed == {"revision": self.dataset_revision,
                                  "head_presence": "ABSENT"},
                "CURRENT_ABSENCE_UNVERIFIED")
            storage._deadline(self.deadline)
        except ContinuationBlocked:
            raise
        except Exception:
            raise ContinuationBlocked("CURRENT_ABSENCE_UNVERIFIED") from None

    def _artifact(self, path):
        try:
            rows = self.api.get_bucket_paths_info(bucket_id=storage.BUCKET, paths=[path])
            iterator = iter(rows)
            marker = object()
            row = next(iterator, marker)
            _require(next(iterator, marker) is marker, "CURRENT_ABSENCE_UNVERIFIED")
            if row is marker:
                return None
            _require(storage._value(row, "path") == path and storage._value(row, "type") == "file"
                and type(storage._value(row, "size")) is int
                and storage._digest(storage._value(row, "xet_hash")),
                "CURRENT_ABSENCE_UNVERIFIED")
            return row
        except ContinuationBlocked:
            raise
        except Exception:
            raise ContinuationBlocked("CURRENT_ABSENCE_UNVERIFIED") from None

    def bind_candidate(self, database):
        """Freeze the exact diagnostic set and prove every path still absent."""
        self.require_head_absent()
        _require(not self.acknowledged and not self.pending
            and type(self.bind_count) is int and self.bind_count < 2,
            "CURRENT_ABSENCE_UNVERIFIED")
        self.bind_count += 1
        pending, plan = triage.local_artifact_plan(database,
            self.workspace / f"diagnostic-continuation-plan-{self.bind_count}",
            self.deadline)
        _require(plan == {"expected_object_count": EXPECTED_OBJECT_COUNT,
            "expected_object_set_sha256": EXPECTED_OBJECT_SET_SHA256,
            "candidate_unchanged": True, "all_retained_rows_validated": True},
            "CURRENT_ABSENCE_UNVERIFIED")
        expected = {path: (digest, size)
            for path, (_physical, digest, size) in pending.items()}
        _require(len(expected) == EXPECTED_OBJECT_COUNT, "CURRENT_ABSENCE_UNVERIFIED")
        _require(self.expected is None or self.expected == expected,
            "CURRENT_ABSENCE_UNVERIFIED")
        self.expected = expected
        self.require_artifacts_absent()

    def require_artifacts_absent(self):
        """Recheck the complete bound namespace at an immediate write boundary."""
        _require(type(self.expected) is dict and len(self.expected) == EXPECTED_OBJECT_COUNT
            and not self.acknowledged and not self.pending,
            "CURRENT_ABSENCE_UNVERIFIED")
        self.require_head_absent()
        for path in sorted(self.expected):
            _require(self._artifact(path) is None, "CURRENT_ABSENCE_UNVERIFIED")
        self.require_head_absent()

    def controls_artifact_path(self, path):
        _require(type(path) is str and type(self.expected) is dict,
            "CURRENT_ABSENCE_UNVERIFIED")
        if path.startswith(storage.ARTIFACT_PREFIX + "/"):
            _require(path in self.expected, "CURRENT_ABSENCE_UNVERIFIED")
            return True
        return path in self.expected

    def before_artifact(self, path, digest, size):
        _require(type(self.expected) is dict and path in self.expected
            and self.expected[path] == (digest, size),
            "CURRENT_ABSENCE_UNVERIFIED")
        _require(not self.pending, "CURRENT_ABSENCE_UNVERIFIED")
        self.require_head_absent()
        if path in self.acknowledged:
            current = self._artifact(path)
            _require(current is not None
                and storage._value(current, "size") == self.acknowledged[path][1]
                and storage._value(current, "xet_hash") == self.acknowledged[path][2],
                "CURRENT_ABSENCE_UNVERIFIED")
            self.pending[path] = {"mode": "READBACK", "attempted": False,
                                  "completed": False}
        else:
            _require(self._artifact(path) is None, "CURRENT_ABSENCE_UNVERIFIED")
            self.pending[path] = {"mode": "ADD", "attempted": False,
                                  "completed": False}
        self.require_head_absent()

    def begin_artifact_add(self, path):
        """Fence the native add at the last observable pre-submission instant."""
        state = self.pending.get(path)
        _require(state == {"mode": "ADD", "attempted": False, "completed": False},
            "CURRENT_ABSENCE_UNVERIFIED")
        self.require_head_absent()
        _require(self._artifact(path) is None, "CURRENT_ABSENCE_UNVERIFIED")
        self.require_head_absent()
        state["attempted"] = True

    def complete_artifact_add(self, path):
        """Record only a provider add whose request returned synchronously."""
        state = self.pending.get(path)
        _require(state == {"mode": "ADD", "attempted": True, "completed": False},
            "CURRENT_ABSENCE_UNVERIFIED")
        self.require_head_absent()
        state["completed"] = True

    def acknowledge_artifact(self, record):
        path = record.get("path") if type(record) is dict else None
        _require(type(self.expected) is dict and path in self.expected
            and (record.get("sha256"), record.get("size")) == self.expected[path]
            and storage._digest(record.get("xet_hash")), "CURRENT_ABSENCE_UNVERIFIED")
        state = self.pending.get(path)
        if path in self.acknowledged:
            _require(state == {"mode": "READBACK", "attempted": False,
                               "completed": False}, "CURRENT_ABSENCE_UNVERIFIED")
        else:
            _require(state == {"mode": "ADD", "attempted": True,
                               "completed": True}, "CURRENT_ABSENCE_UNVERIFIED")
        current = self._artifact(path)
        _require(current is not None
            and storage._value(current, "size") == record["size"]
            and storage._value(current, "xet_hash") == record["xet_hash"],
            "CURRENT_ABSENCE_UNVERIFIED")
        identity = (record["sha256"], record["size"], record["xet_hash"])
        _require(path not in self.acknowledged or self.acknowledged[path] == identity,
            "CURRENT_ABSENCE_UNVERIFIED")
        self.require_head_absent()
        self.acknowledged[path] = identity
        self.pending.pop(path)

    def require_artifacts_complete(self):
        _require(type(self.expected) is dict and set(self.acknowledged) == set(self.expected),
            "CURRENT_ABSENCE_UNVERIFIED")
        _require(not self.pending, "CURRENT_ABSENCE_UNVERIFIED")
        self.require_head_absent()


def _read_file(path, bound):
    data = Path(path).read_bytes()
    _require(0 < len(data) <= bound, "CONTINUATION_REPORT_UNQUALIFIED")
    return data


def _write_file(path, data):
    path = Path(path)
    _require(path.is_absolute() and type(data) is bytes and len(data) > 0,
        "CONTINUATION_REPORT_UNQUALIFIED")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def main(argv=None):
    import argparse
    import logging
    from scripts import preserve_hf_gdw_store as preservation

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--reconcile", action="store_true")
    mode.add_argument("--classify", action="store_true")
    parser.add_argument("--reconciliation", type=Path)
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--qualification-output", type=Path)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = {"schema": SCHEMA, "state": "HELD",
        "diagnostic_code": "DIAGNOSTIC_CONTINUATION_UNAVAILABLE",
        "provider_writes_performed": False, "replay_admitted": False,
        "restore_admitted": False, "deployment_admitted": False,
        "secret_values_recorded": False}
    old_mask = os.umask(0o077)
    try:
        if args.reconcile:
            _require(args.qualification_output is not None and args.reconciliation is None
                and args.qualification is None and args.github_output is not None,
                "CONTINUATION_REPORT_UNQUALIFIED")
            logging.disable(logging.CRITICAL)
            with tempfile.TemporaryDirectory(prefix="gdw-continuation-reconciliation-") as temporary:
                directory = Path(temporary)
                directory.chmod(0o700)
                with preservation._private_output():
                    report, qualification = execute_native_reconciliation(
                        directory, time.monotonic() + MAX_SECONDS)
            encoded = storage.canonical(report)
            _write_file(args.qualification_output, qualification)
            _write_file(args.output, encoded)
            with args.github_output.open("a", encoding="ascii") as stream:
                stream.write("admitted=true\n")
            result = report
        else:
            _require(args.reconciliation is not None and args.qualification is not None
                and args.qualification_output is None and args.github_output is not None,
                "CONTINUATION_REPORT_UNQUALIFIED")
            result = classify_reconciliation(_read_file(args.reconciliation, 8192),
                _read_file(args.qualification, 1024 * 1024), os.environ.get("GITHUB_SHA", ""))
            _write_file(args.output, storage.canonical(result))
            with args.github_output.open("a", encoding="ascii") as stream:
                stream.write("mode=managed-recovery\n")
        print(json.dumps({"schema": result["schema"], "state": result["state"],
                          "secret_values_recorded": False}, sort_keys=True))
        return 0
    except BaseException as error:
        code = error.code if type(error) is ContinuationBlocked else "DIAGNOSTIC_CONTINUATION_UNAVAILABLE"
        result["diagnostic_code"] = code
        stage = error.stage if type(error) is ContinuationBlocked else None
        if stage is not None:
            result["diagnostic_stage"] = stage
        try:
            if not os.path.lexists(args.output):
                _write_file(args.output, storage.canonical(result))
        except BaseException:
            pass
        print(json.dumps(result, sort_keys=True))
        return 2
    finally:
        os.umask(old_mask)


if __name__ == "__main__":
    raise SystemExit(artifact_object_worker()
        if sys.argv[1:] == ["--artifact-object-worker"] else main())
