#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only prerequisite for one canonical successor of the artifact triage.

This is not restore or deployment admission. It binds one signed direct source
successor and its sole push run to one successful read-only native producer,
then observes the same private dataset revision and HEAD absence twice. The
historical expected-set absence is not absence of every bucket object or retry
authority. Acquisition must bind and reobserve its candidate plan separately.
No mutation method is used. The caller enforces the hard process deadline,
private output suppression and the canonical workflow DAG.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

import gdw_durable_storage as storage
from scripts import gdw_acquisition_evidence as native

SCHEMA = "szl.gdw-supervised-acquisition-prerequisite/v2"
PARENT_SOURCE = "f1653a2908f944e37b7de87da36363cc9d661913"
INSPECTION_RUN = 37357773764
INSPECTION_ATTEMPT = 1
INSPECTION_JOB = 111924632435
INSPECTION_CONTRACT_JOB = 111924448606
INSPECTION_WORKFLOW = ".github/workflows/gdw-artifact-readonly-triage.yml"
INSPECTION_WORKFLOW_ID = 375098171
ARTIFACT_ID = 11365342348
ARCHIVE_BYTES = 1092
ARCHIVE_SHA256 = "a6aa374c1878af66e142260a4f2ff9283c3566935dc88f958ce65bcc7265305b"
REPORT_BYTES = 1814
REPORT_SHA256 = "9c8ffa25849305a95248d280989ac91e038e00cd04e3a5eb47d7e3b6949dbe37"
DATASET_REVISION = "fd57865f92240626794729aecdc0827b90796aac"
EXPECTED_OBJECT_COUNT = 224
EXPECTED_OBJECT_SET_SHA256 = "7a28c53fa647e639375c6a90d3e34e89fe74bc2004f8161b5f38ac793301be42"
OBSERVED_OBJECT_SET_SHA256 = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
REPOSITORY_ID = 1225834126
RECONCILIATION_JOB_KEY = "recovery-reconciliation"
RECONCILIATION_JOB = "Reconcile the held acquisition before provider mutation"
JOB_NAMES = {RECONCILIATION_JOB_KEY: RECONCILIATION_JOB,
             native.ACQUISITION_JOB_KEY: native.ACQUISITION_JOB}
MAX_SECONDS = 120
CODES = frozenset({"NATIVE_CONTEXT_UNQUALIFIED", "SOURCE_SUCCESSOR_UNQUALIFIED",
    "NATIVE_RUN_NOT_UNIQUE", "INSPECTION_PRODUCER_UNQUALIFIED", "INSPECTION_ARTIFACT_UNQUALIFIED",
    "EXPECTED_ABSENCE_UNVERIFIED", "RECONCILIATION_UNAVAILABLE"})


class SupervisedBlocked(RuntimeError):
    def __init__(self, code):
        self.code = code if type(code) is str and code in CODES else "RECONCILIATION_UNAVAILABLE"
        super().__init__(self.code)


def _require(value, code):
    if value is not True:
        raise SupervisedBlocked(code)


def _integer(value):
    return type(value) is int and value > 0


def _run_binding(run, *, source, run_id, repository_id, active):
    _require(type(run) is dict and run.get("id") == run_id and type(run.get("id")) is int
        and run.get("run_attempt") == 1 and type(run.get("run_attempt")) is int
        and run.get("path") == native.WORKFLOW and run.get("event") == "push"
        and run.get("head_sha") == source and run.get("head_branch") == "main"
        and run.get("repository", {}).get("id") == repository_id
        and run.get("repository", {}).get("full_name") == native.REPOSITORY
        and run.get("head_repository", {}).get("id") == repository_id,
        "NATIVE_CONTEXT_UNQUALIFIED")
    _require(run.get("status") == ("in_progress" if active else "completed")
        and run.get("conclusion") == (None if active else "failure"), "NATIVE_CONTEXT_UNQUALIFIED")


def _current_context(evidence):
    _require(storage._revision(evidence.source) and evidence.source != PARENT_SOURCE
        and evidence.event == "push" and type(evidence.attempt) is int and evidence.attempt == 1
        and evidence.repository_id == REPOSITORY_ID
        and os.environ.get("GITHUB_WORKFLOW_SHA") == evidence.source
        and evidence.executing_job in JOB_NAMES, "NATIVE_CONTEXT_UNQUALIFIED")
    evidence.observe_run()
    current = evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{evidence.run_id}")
    _run_binding(current, source=evidence.source, run_id=evidence.run_id,
        repository_id=evidence.repository_id, active=True)
    _run_binding(evidence.run, source=evidence.source, run_id=evidence.run_id,
        repository_id=evidence.repository_id, active=True)
    job = evidence.jobs.get(JOB_NAMES[evidence.executing_job])
    _require(type(job) is dict and _integer(job.get("id")) and job.get("status") == "in_progress"
        and job.get("conclusion") is None and job.get("completed_at") is None
        and evidence.started <= native.timestamp(job.get("started_at")) <= datetime.now(timezone.utc),
        "NATIVE_CONTEXT_UNQUALIFIED")
    admitted = evidence.jobs.get(native.SOURCE_JOB)
    _require(type(admitted) is dict and admitted.get("status") == "completed"
        and admitted.get("conclusion") == "success", "NATIVE_CONTEXT_UNQUALIFIED")
    commit = evidence.request(f"/repos/{native.REPOSITORY}/git/commits/{evidence.source}")
    parents = commit.get("parents")
    _require(commit.get("sha") == evidence.source and type(parents) is list and len(parents) == 1
        and parents[0].get("sha") == PARENT_SOURCE
        and commit.get("verification", {}).get("verified") is True
        and commit.get("verification", {}).get("reason") == "valid", "SOURCE_SUCCESSOR_UNQUALIFIED")
    listing = evidence.request(f"/repos/{native.REPOSITORY}/actions/workflows/hf-sync.yml/runs"
        f"?event=push&head_sha={evidence.source}&per_page=100")
    rows = listing.get("workflow_runs")
    _require(type(listing.get("total_count")) is int and listing["total_count"] == 1
        and type(rows) is list and len(rows) == 1, "NATIVE_RUN_NOT_UNIQUE")
    _run_binding(rows[0], source=evidence.source, run_id=evidence.run_id,
        repository_id=evidence.repository_id, active=True)
    _require(_integer(current.get("workflow_id"))
        and type(rows[0].get("workflow_id")) is int and rows[0]["workflow_id"] == current["workflow_id"]
        and type(evidence.run.get("workflow_id")) is int and evidence.run["workflow_id"] == current["workflow_id"],
        "NATIVE_RUN_NOT_UNIQUE")
    evidence.require_current_main()
    return job["id"]


def _triage_run_binding(run):
    _require(type(run) is dict and type(run.get("id")) is int and run["id"] == INSPECTION_RUN
        and type(run.get("run_attempt")) is int and run["run_attempt"] == INSPECTION_ATTEMPT
        and type(run.get("workflow_id")) is int and run["workflow_id"] == INSPECTION_WORKFLOW_ID
        and run.get("path") == INSPECTION_WORKFLOW and run.get("event") == "workflow_dispatch"
        and run.get("head_sha") == PARENT_SOURCE and run.get("head_branch") == "main"
        and run.get("repository", {}).get("id") == REPOSITORY_ID
        and run.get("repository", {}).get("full_name") == native.REPOSITORY
        and run.get("head_repository", {}).get("id") == REPOSITORY_ID
        and run.get("status") == "completed" and run.get("conclusion") == "success",
        "INSPECTION_PRODUCER_UNQUALIFIED")


def _prior_producer(evidence):
    run = evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{INSPECTION_RUN}/attempts/1")
    _triage_run_binding(run)
    # A historical first-attempt endpoint alone must not conceal a later rerun.
    _triage_run_binding(evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{INSPECTION_RUN}"))
    listing = evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{INSPECTION_RUN}/attempts/1/jobs?per_page=100")
    jobs = listing.get("jobs")
    expected = {INSPECTION_CONTRACT_JOB: "contract", INSPECTION_JOB: "triage"}
    _require(type(listing.get("total_count")) is int and listing["total_count"] == 2
        and type(jobs) is list and len(jobs) == 2, "INSPECTION_PRODUCER_UNQUALIFIED")
    seen = set()
    producer = None
    contract = None
    for job in jobs:
        _require(type(job) is dict and _integer(job.get("id")) and job["id"] not in seen
            and job["id"] in expected and job.get("name") == expected[job["id"]]
            and type(job.get("run_id")) is int and job["run_id"] == INSPECTION_RUN
            and type(job.get("run_attempt")) is int and job["run_attempt"] == 1
            and job.get("head_sha") == PARENT_SOURCE and job.get("status") == "completed"
            and job.get("conclusion") == "success",
            "INSPECTION_PRODUCER_UNQUALIFIED")
        seen.add(job["id"])
        steps = job.get("steps")
        _require(type(steps) is list and 1 <= len(steps) <= 30
            and all(type(item) is dict and type(item.get("name")) is str
                and item.get("status") == "completed" and item.get("conclusion") == "success" for item in steps)
            and len({item["name"] for item in steps}) == len(steps), "INSPECTION_PRODUCER_UNQUALIFIED")
        if job["id"] == INSPECTION_JOB:
            producer = job
        else:
            contract = job
    _require(seen == set(expected) and producer is not None and contract is not None,
        "INSPECTION_PRODUCER_UNQUALIFIED")
    _require(any(item["name"] == "Prove read-only triage boundaries with actual disposable databases"
        for item in contract["steps"]), "INSPECTION_PRODUCER_UNQUALIFIED")
    by_name = {item["name"]: item for item in producer["steps"]}
    _require("Reconcile exact retained artifact objects without provider mutation" in by_name
        and "Retain only the closed diagnostic record" in by_name,
        "INSPECTION_PRODUCER_UNQUALIFIED")
    observed = by_name["Reconcile exact retained artifact objects without provider mutation"]
    uploaded = by_name["Retain only the closed diagnostic record"]
    _require(native.timestamp(run.get("run_started_at")) <= native.timestamp(contract.get("started_at"))
        <= native.timestamp(contract.get("completed_at")) <= native.timestamp(producer.get("started_at"))
        <= native.timestamp(observed.get("started_at")) <= native.timestamp(observed.get("completed_at"))
        <= native.timestamp(uploaded.get("started_at")) <= native.timestamp(uploaded.get("completed_at"))
        <= native.timestamp(producer.get("completed_at")), "INSPECTION_PRODUCER_UNQUALIFIED")
    return run, producer


def _inspection_archive(evidence, run, producer):
    """Read exactly the successful native triage ZIP and its closed report."""
    meta = evidence.request(f"/repos/{native.REPOSITORY}/actions/artifacts/{ARTIFACT_ID}")
    _require(meta.get("size_in_bytes") == ARCHIVE_BYTES and type(meta.get("size_in_bytes")) is int
        and native.timestamp(run.get("run_started_at")) <= native.timestamp(producer.get("started_at"))
        <= native.timestamp(meta.get("created_at")) <= native.timestamp(producer.get("completed_at")),
        "INSPECTION_ARTIFACT_UNQUALIFIED")
    evidence.budget()
    with evidence.client.stream("GET", f"{native.API}/repos/{native.REPOSITORY}/actions/artifacts/{ARTIFACT_ID}/zip",
            headers={"Authorization": "Bearer " + evidence.token, "Accept": "application/vnd.github+json"}) as response:
        _require(response.status_code == 302, "INSPECTION_ARTIFACT_UNQUALIFIED")
        location = response.headers.get("location", "")
    parsed = urlsplit(location)
    host = parsed.hostname or ""
    _require(parsed.scheme == "https" and parsed.port in (None, 443) and not parsed.username
        and not parsed.password and not parsed.fragment and len(location) <= 16384
        and (host.endswith(".blob.core.windows.net") or host.endswith(".actions.githubusercontent.com")),
        "INSPECTION_ARTIFACT_UNQUALIFIED")
    with evidence.client.stream("GET", location, headers={}) as response:
        _require(response.status_code == 200, "INSPECTION_ARTIFACT_UNQUALIFIED")
        archive = bytearray()
        for chunk in response.iter_bytes(chunk_size=1024):
            evidence.budget()
            _require(len(archive) + len(chunk) <= ARCHIVE_BYTES, "INSPECTION_ARTIFACT_UNQUALIFIED")
            archive.extend(chunk)
    members = native.validate_archive(meta, bytes(archive), artifact_id=ARTIFACT_ID,
        expected_digest=ARCHIVE_SHA256, expected_name=f"gdw-artifact-readonly-{INSPECTION_RUN}-1",
        source=PARENT_SOURCE, run_id=INSPECTION_RUN, repository_id=REPOSITORY_ID,
        members=frozenset({"gdw-artifact-triage.json"}))
    validate_triage_report(members["gdw-artifact-triage.json"])
    evidence.budget()


def _expected_triage_report():
    """The entire fixed observation, including its explicit proof limits."""
    return {
        "artifact_effect_observation": {
            "all_retained_rows_validated": True, "candidate_unchanged": True,
            "classification": "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME",
            "expected_object_count": EXPECTED_OBJECT_COUNT,
            "expected_object_set_sha256": EXPECTED_OBJECT_SET_SHA256,
            "historical_writer_attribution": "NOT_ESTABLISHED",
            "missing_object_count": EXPECTED_OBJECT_COUNT,
            "observed_object_set_sha256": OBSERVED_OBJECT_SET_SHA256,
            "present_object_count": 0, "provider_objects_fully_validated": False,
            "provider_writes_performed": False},
        "capture_qualification": "LOGICAL_CONTINUITY_VERIFIED",
        "captured_originals_unchanged_during_qualification": True,
        "deployment_admitted": False, "diagnostic_code": "READ_ONLY_OBSERVATION_COMPLETE",
        "historical_writer_attribution": "NOT_ESTABLISHED", "metadata_stable_during_read": True,
        "prior_acquisition_archive_sha256": "d290fa69bf530ec3cc27daccfd0daef13904064c2f3a75f73fe2bc71c2515afd",
        "prior_acquisition_artifact_id": 11325467455,
        "prior_acquisition_report_sha256": "f4e638d0b73f865add47e16c7de5bdfff9f9ce8b6b505ee4e6debf1098db35a2",
        "prior_job_id": 111616768413, "prior_native_metadata_verified": True,
        "prior_provider_effects": "NOT_ESTABLISHED", "prior_run_attempt": 1,
        "prior_run_id": 37263869028, "prior_source_revision": "62ca4d1506fe95f8bedf2143f5f8b60c786dcd74",
        "prior_stage": "ARTIFACT_PUBLICATION", "prior_stage_state": "BOUNDARY_ENTERED",
        "private_bytes_reported": False,
        "private_head_metadata": {"head_presence": "ABSENT", "revision": DATASET_REVISION},
        "provider_writes_performed": False, "qualified_database_count": 2,
        "read_boundary": "COMPLETE", "restore_admitted": False, "retry_admitted": False,
        "run_attempt": INSPECTION_ATTEMPT, "run_id": INSPECTION_RUN,
        "schema": "szl.gdw-artifact-readonly-triage/v2", "source_revision": PARENT_SOURCE, "state": "OBSERVED"}


def validate_triage_report(raw):
    value = native.strict(raw, 4096)
    _require(len(raw) == REPORT_BYTES and hashlib.sha256(raw).hexdigest() == REPORT_SHA256,
        "INSPECTION_ARTIFACT_UNQUALIFIED")
    # Canonical bytes also reject extra/missing fields, bool-as-int, and broader
    # claims even if a future edit were to change only the pinned report digest.
    _require(storage.canonical(_expected_triage_report()) == raw, "INSPECTION_ARTIFACT_UNQUALIFIED")
    return value


def verify_native_prerequisite(evidence):
    """Bind one currently active native job before any private provider read."""
    try:
        job_id = _current_context(evidence)
        run, producer = _prior_producer(evidence)
        _inspection_archive(evidence, run, producer)
        _require(_current_context(evidence) == job_id, "NATIVE_CONTEXT_UNQUALIFIED")
        evidence.budget()
        return {"source_revision": evidence.source, "run_id": evidence.run_id,
            "run_attempt": evidence.attempt, "job_id": job_id, "job_key": evidence.executing_job}
    except SupervisedBlocked:
        raise
    except Exception:
        raise SupervisedBlocked("RECONCILIATION_UNAVAILABLE") from None


def require_expected_absent(api, evidence, deadline):
    """SDK-neutral metadata adapter for the existing 1.23 and 1.31 job lanes."""
    try:
        _require(storage._revision(evidence.source) and evidence.source != PARENT_SOURCE
            and storage._value(api, "endpoint") == storage.ENDPOINT, "EXPECTED_ABSENCE_UNVERIFIED")
        for _ in range(2):
            storage._deadline(deadline)
            evidence.require_current_main()
            storage._deadline(deadline)
            info = api.dataset_info(storage.DATASET, revision="main", expand=["sha", "private", "resourceGroup"])
            _require(storage._value(info, "id") == storage.DATASET and storage._value(info, "private") is True
                and storage._value(info, "sha") == DATASET_REVISION, "EXPECTED_ABSENCE_UNVERIFIED")
            storage._deadline(deadline)
            evidence.require_current_main()
            storage._deadline(deadline)
            paths = api.get_paths_info(storage.DATASET, [storage.HEAD_PATH], repo_type="dataset", revision=DATASET_REVISION)
            _require(type(paths) is list and not paths, "EXPECTED_ABSENCE_UNVERIFIED")
        storage._deadline(deadline)
        evidence.require_current_main()
        storage._deadline(deadline)
        return {"source_revision": evidence.source, "dataset_revision": DATASET_REVISION,
            "state": "EXPECTED_HEAD_ABSENT", "provider_writes_performed": False}
    except SupervisedBlocked:
        raise
    except Exception:
        raise SupervisedBlocked("EXPECTED_ABSENCE_UNVERIFIED") from None


def _report(context):
    return {"schema": SCHEMA, "state": "PREREQUISITE_VERIFIED",
        "scope": "ONE_SOURCE_ONE_RUN_PREWRITE_ONLY", **context,
        "inspection_source_revision": PARENT_SOURCE, "inspection_run_id": INSPECTION_RUN,
        "inspection_run_attempt": 1, "inspection_job_id": INSPECTION_JOB,
        "inspection_workflow_path": INSPECTION_WORKFLOW,
        "inspection_artifact_id": ARTIFACT_ID, "inspection_archive_sha256": ARCHIVE_SHA256,
        "inspection_report_sha256": REPORT_SHA256, "dataset_revision": DATASET_REVISION,
        "inspection_classification": "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME",
        "inspection_expected_object_count": EXPECTED_OBJECT_COUNT,
        "inspection_expected_object_set_sha256": EXPECTED_OBJECT_SET_SHA256,
        "inspection_present_object_count": 0, "inspection_missing_object_count": EXPECTED_OBJECT_COUNT,
        "inspection_observed_object_set_sha256": OBSERVED_OBJECT_SET_SHA256,
        "historical_writer_attribution": "NOT_ESTABLISHED", "prior_provider_effects": "NOT_ESTABLISHED",
        "provider_writes_performed": False, "provider_objects_verified": False,
        "retry_admitted": False, "restore_admitted": False, "deployment_admitted": False,
        "secret_values_recorded": False}


def validate_reconciliation_report(raw):
    value = native.strict(raw, 4096)
    keys = ("source_revision", "run_id", "run_attempt", "job_id", "job_key")
    _require(all(key in value for key in keys), "RECONCILIATION_UNAVAILABLE")
    context = {key: value[key] for key in keys}
    _require(storage._revision(context["source_revision"]) and context["source_revision"] != PARENT_SOURCE
        and all(_integer(context[key]) for key in ("run_id", "run_attempt", "job_id"))
        and context["run_attempt"] == 1 and type(context["job_key"]) is str and context["job_key"] in JOB_NAMES,
        "RECONCILIATION_UNAVAILABLE")
    _require(storage.canonical(_report(context)) == raw, "RECONCILIATION_UNAVAILABLE")
    return value


def execute_native_reconciliation(workspace: Path, deadline):
    """Called only inside the existing credential-isolated canonical worker."""
    _require(type(deadline) in (int, float) and 0 < deadline - time.monotonic() <= MAX_SECONDS,
        "RECONCILIATION_UNAVAILABLE")
    storage._private_directory(workspace)
    evidence = native.NativeEvidence(dict(os.environ), deadline)
    context = verify_native_prerequisite(evidence)
    try:
        api = storage._hub_api(os.environ.get("HF_TOKEN", ""))
        require_expected_absent(api, evidence, deadline)
    except SupervisedBlocked:
        raise
    except Exception:
        raise SupervisedBlocked("RECONCILIATION_UNAVAILABLE") from None
    result = validate_reconciliation_report(storage.canonical(_report(context)))
    storage._deadline(deadline)
    return result
