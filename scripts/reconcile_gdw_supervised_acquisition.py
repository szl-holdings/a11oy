#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only prerequisite for one canonical successor of the held inspection.

This is not restore or deployment admission. It binds one signed direct source
successor and its sole push run to the immutable failed-but-inspect-only producer,
then observes the same private dataset revision and HEAD absence twice. Provider
objects are never read and no mutation method is used. The caller enforces the
hard process deadline, private output suppression and the canonical workflow DAG.
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
from scripts import inspect_gdw_held_acquisition as inspection

SCHEMA = "szl.gdw-supervised-acquisition-prerequisite/v1"
PARENT_SOURCE = "a60125af336ea97ac29678a79110c30ec0122e99"
INSPECTION_RUN = 37262929675
INSPECTION_ATTEMPT = 1
INSPECTION_JOB = 111613776558
INSPECTION_SOURCE_JOB = 111613728997
ARTIFACT_ID = 11324359120
ARCHIVE_SHA256 = "863191708947e38f6d3338e0f99cefff25f19fde55919132dd991e099d7c4513"
REPORT_SHA256 = "d5f84ce152b3c46d5295792d1db44b0031568079719aa375a04be9750e38dee8"
DATASET_REVISION = "dd34d6b0b20d918cc862888030569d03d99a9b37"
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


def _prior_producer(evidence):
    run = evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{INSPECTION_RUN}/attempts/1")
    _run_binding(run, source=PARENT_SOURCE, run_id=INSPECTION_RUN,
        repository_id=REPOSITORY_ID, active=False)
    listing = evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{INSPECTION_RUN}/attempts/1/jobs?per_page=100")
    jobs = listing.get("jobs")
    _require(type(listing.get("total_count")) is int and listing["total_count"] == 13
        and type(jobs) is list and len(jobs) == 13, "INSPECTION_PRODUCER_UNQUALIFIED")
    seen = set()
    producer = None
    for job in jobs:
        _require(type(job) is dict and _integer(job.get("id")) and job["id"] not in seen
            and type(job.get("run_id")) is int and job["run_id"] == INSPECTION_RUN
            and type(job.get("run_attempt")) is int and job["run_attempt"] == 1
            and job.get("head_sha") == PARENT_SOURCE and job.get("status") == "completed",
            "INSPECTION_PRODUCER_UNQUALIFIED")
        seen.add(job["id"])
        if job["id"] == INSPECTION_JOB:
            _require(job.get("name") == native.ACQUISITION_JOB and job.get("conclusion") == "failure",
                "INSPECTION_PRODUCER_UNQUALIFIED")
            producer = job
        elif job["id"] == INSPECTION_SOURCE_JOB:
            _require(job.get("name") == native.SOURCE_JOB and job.get("conclusion") == "success",
                "INSPECTION_PRODUCER_UNQUALIFIED")
        else:
            _require(job.get("conclusion") == "skipped", "INSPECTION_PRODUCER_UNQUALIFIED")
    _require(producer is not None and INSPECTION_SOURCE_JOB in seen, "INSPECTION_PRODUCER_UNQUALIFIED")
    steps = producer.get("steps")
    _require(type(steps) is list and 1 <= len(steps) <= 30
        and all(type(item) is dict and type(item.get("name")) is str for item in steps)
        and len({item["name"] for item in steps}) == len(steps), "INSPECTION_PRODUCER_UNQUALIFIED")
    by_name = {item["name"]: item for item in steps}
    failed = [item["name"] for item in steps if item.get("conclusion") == "failure"]
    expected_failure = "Inspect the held prior acquisition without provider mutation"
    _require(failed == [expected_failure]
        and by_name.get("Install the persistent old-source guard and both managed configurations once", {}).get("conclusion") == "skipped"
        and by_name.get("Retain only the immutable selector and safe guarded configuration result", {}).get("conclusion") == "success",
        "INSPECTION_PRODUCER_UNQUALIFIED")
    return run, producer


def _inspection_archive(evidence, run, producer):
    """Specialized fixed failed-inspection producer; no general failure bypass."""
    meta = evidence.request(f"/repos/{native.REPOSITORY}/actions/artifacts/{ARTIFACT_ID}")
    _require(meta.get("size_in_bytes") == 565 and type(meta.get("size_in_bytes")) is int
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
            _require(len(archive) + len(chunk) <= 565, "INSPECTION_ARTIFACT_UNQUALIFIED")
            archive.extend(chunk)
    members = native.validate_archive(meta, bytes(archive), artifact_id=ARTIFACT_ID,
        expected_digest=ARCHIVE_SHA256, expected_name=f"canonical-durable-acquisition-{INSPECTION_RUN}-1",
        source=PARENT_SOURCE, run_id=INSPECTION_RUN, repository_id=REPOSITORY_ID,
        members=frozenset({"gdw-durable-acquisition.json"}))
    raw = members["gdw-durable-acquisition.json"]
    _require(len(raw) == 640 and hashlib.sha256(raw).hexdigest() == REPORT_SHA256,
        "INSPECTION_ARTIFACT_UNQUALIFIED")
    report = inspection.validate_inspection_report(raw)
    _require(report["source_revision"] == PARENT_SOURCE and report["classification"] == "ABSENT"
        and report["dataset_revision"] == DATASET_REVISION, "INSPECTION_ARTIFACT_UNQUALIFIED")
    evidence.budget()


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
        "inspection_artifact_id": ARTIFACT_ID, "inspection_archive_sha256": ARCHIVE_SHA256,
        "inspection_report_sha256": REPORT_SHA256, "dataset_revision": DATASET_REVISION,
        "provider_writes_performed": False, "provider_objects_verified": False,
        "restore_admitted": False, "deployment_admitted": False, "secret_values_recorded": False}


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
