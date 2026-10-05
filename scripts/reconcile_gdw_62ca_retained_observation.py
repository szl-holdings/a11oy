#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: verify one immutable read-only observation, never authorize recovery.

The caller supplies the existing GET-only native evidence reader and its hard
process deadline. No incident selector, provider SDK, database, writer or CLI is
exposed. This historical observation is not a lease on current provider state.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import time
from urllib.parse import urlsplit

from scripts import gdw_acquisition_evidence as native

SCHEMA = "szl.gdw-62ca-retained-observation/v1"
MAX_SECONDS = 120
SOURCE = "1b2775485b05915662624c947004cd887b21cf5d"
RUN = 37318344262
ATTEMPT = 1
WORKFLOW = ".github/workflows/gdw-artifact-readonly-triage.yml"
REPOSITORY_ID = 1225834126
PRODUCER_JOB = 111790857066
CONTRACT_JOB = 111790709197
ARTIFACT = 11349341865
ARCHIVE_BYTES = 1091
ARCHIVE_SHA256 = "055c8200399d6f27e7fee4b0a371e775803dc62daf9cdbb396ae445524025d21"
MEMBER = "gdw-artifact-triage.json"
REPORT_BYTES = 1814
REPORT_SHA256 = "ecfc526f3e68775934e0f0c448670cc3c0c0bd899072ed579bb6d26ae0e4d250"
DATASET_REVISION = "f5dbdcaea236db3b0d25b8d8cfe8d64369b25d78"
EXPECTED_OBJECTS = 224
EXPECTED_SET_SHA256 = "7a28c53fa647e639375c6a90d3e34e89fe74bc2004f8161b5f38ac793301be42"
EMPTY_SET_SHA256 = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
PRIOR_SOURCE = "62ca4d1506fe95f8bedf2143f5f8b60c786dcd74"
PRIOR_RUN = 37263869028
PRIOR_JOB = 111616768413
PRIOR_ARTIFACT = 11325467455
PRIOR_ARCHIVE_SHA256 = "d290fa69bf530ec3cc27daccfd0daef13904064c2f3a75f73fe2bc71c2515afd"
PRIOR_REPORT_SHA256 = "f4e638d0b73f865add47e16c7de5bdfff9f9ce8b6b505ee4e6debf1098db35a2"
CODES = frozenset({"OBSERVATION_UNAVAILABLE", "OBSERVATION_RUN_UNQUALIFIED",
    "OBSERVATION_SOURCE_UNQUALIFIED", "OBSERVATION_JOBS_UNQUALIFIED",
    "OBSERVATION_ARTIFACT_UNQUALIFIED", "OBSERVATION_REPORT_UNQUALIFIED"})


class ObservationHeld(RuntimeError):
    """Closed codes only; no private exception text or transport bodies."""
    def __init__(self, code):
        self.code = code if type(code) is str and code in CODES else "OBSERVATION_UNAVAILABLE"
        super().__init__(self.code)


def _require(value, code):
    if value is not True:
        raise ObservationHeld(code)


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _expected_report():
    return {
        "schema": "szl.gdw-artifact-readonly-triage/v2", "state": "OBSERVED",
        "diagnostic_code": "READ_ONLY_OBSERVATION_COMPLETE", "read_boundary": "COMPLETE",
        "source_revision": SOURCE, "run_id": RUN, "run_attempt": ATTEMPT,
        "capture_qualification": "LOGICAL_CONTINUITY_VERIFIED", "qualified_database_count": 2,
        "captured_originals_unchanged_during_qualification": True,
        "metadata_stable_during_read": True,
        "private_head_metadata": {"head_presence": "ABSENT", "revision": DATASET_REVISION},
        "artifact_effect_observation": {
            "all_retained_rows_validated": True, "candidate_unchanged": True,
            "classification": "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME",
            "expected_object_count": EXPECTED_OBJECTS, "expected_object_set_sha256": EXPECTED_SET_SHA256,
            "present_object_count": 0, "missing_object_count": EXPECTED_OBJECTS,
            "observed_object_set_sha256": EMPTY_SET_SHA256,
            "provider_objects_fully_validated": False, "provider_writes_performed": False,
            "historical_writer_attribution": "NOT_ESTABLISHED",
        },
        "prior_source_revision": PRIOR_SOURCE, "prior_run_id": PRIOR_RUN, "prior_run_attempt": 1,
        "prior_job_id": PRIOR_JOB, "prior_acquisition_artifact_id": PRIOR_ARTIFACT,
        "prior_acquisition_archive_sha256": PRIOR_ARCHIVE_SHA256,
        "prior_acquisition_report_sha256": PRIOR_REPORT_SHA256,
        "prior_native_metadata_verified": True, "prior_stage": "ARTIFACT_PUBLICATION",
        "prior_stage_state": "BOUNDARY_ENTERED", "prior_provider_effects": "NOT_ESTABLISHED",
        "historical_writer_attribution": "NOT_ESTABLISHED", "private_bytes_reported": False,
        "provider_writes_performed": False, "retry_admitted": False,
        "restore_admitted": False, "deployment_admitted": False,
    }


def validate_observation_report(raw):
    """Accept exactly the safe v2 bytes; no looser incident or authority shape."""
    try:
        _require(type(raw) is bytes and len(raw) == REPORT_BYTES
            and hashlib.sha256(raw).hexdigest() == REPORT_SHA256, "OBSERVATION_REPORT_UNQUALIFIED")
        value = native.strict(raw, REPORT_BYTES)
        _require(_canonical(value) == raw == _canonical(_expected_report()), "OBSERVATION_REPORT_UNQUALIFIED")
        return value
    except ObservationHeld:
        raise
    except Exception:
        raise ObservationHeld("OBSERVATION_REPORT_UNQUALIFIED") from None


def _run_binding(run):
    _require(type(run) is dict and type(run.get("id")) is int and run["id"] == RUN
        and type(run.get("run_attempt")) is int and run["run_attempt"] == ATTEMPT
        and run.get("path") == WORKFLOW and run.get("event") == "workflow_dispatch"
        and run.get("head_sha") == SOURCE and run.get("head_branch") == "main"
        and run.get("repository", {}).get("id") == REPOSITORY_ID
        and run.get("repository", {}).get("full_name") == native.REPOSITORY
        and run.get("head_repository", {}).get("id") == REPOSITORY_ID
        and type(run.get("workflow_id")) is int and run["workflow_id"] > 0
        and run.get("status") == "completed" and run.get("conclusion") == "success",
        "OBSERVATION_RUN_UNQUALIFIED")
    created, started, ended = (native.timestamp(run.get(key))
        for key in ("created_at", "run_started_at", "updated_at"))
    _require(created <= started <= ended <= datetime.now(timezone.utc), "OBSERVATION_RUN_UNQUALIFIED")
    return started, ended


def _producer(listing, started, ended):
    _require(type(listing) is dict and type(listing.get("total_count")) is int
        and listing["total_count"] == 2 and type(listing.get("jobs")) is list
        and len(listing["jobs"]) == 2, "OBSERVATION_JOBS_UNQUALIFIED")
    expected = {CONTRACT_JOB: "contract", PRODUCER_JOB: "triage"}
    seen = set()
    producer = None
    for job in listing["jobs"]:
        _require(type(job) is dict and type(job.get("id")) is int and job["id"] in expected
            and job["id"] not in seen and job.get("name") == expected[job["id"]]
            and type(job.get("run_id")) is int and job["run_id"] == RUN
            and type(job.get("run_attempt")) is int and job["run_attempt"] == ATTEMPT
            and job.get("head_sha") == SOURCE and job.get("status") == "completed"
            and job.get("conclusion") == "success", "OBSERVATION_JOBS_UNQUALIFIED")
        seen.add(job["id"])
        _require(started <= native.timestamp(job.get("started_at"))
            <= native.timestamp(job.get("completed_at")) <= ended, "OBSERVATION_JOBS_UNQUALIFIED")
        steps = job.get("steps")
        _require(type(steps) is list and 1 <= len(steps) <= 30
            and all(type(step) is dict and type(step.get("name")) is str
                and step.get("status") == "completed" and step.get("conclusion") == "success" for step in steps)
            and len({step["name"] for step in steps}) == len(steps), "OBSERVATION_JOBS_UNQUALIFIED")
        names = {step["name"] for step in steps}
        if job["id"] == PRODUCER_JOB:
            _require({"Reconcile exact retained artifact objects without provider mutation",
                "Retain only the closed diagnostic record"} <= names, "OBSERVATION_JOBS_UNQUALIFIED")
            producer = job
        else:
            _require("Prove read-only triage boundaries with actual disposable databases" in names,
                "OBSERVATION_JOBS_UNQUALIFIED")
    _require(seen == set(expected) and producer is not None, "OBSERVATION_JOBS_UNQUALIFIED")
    return producer


def _artifact_binding(meta, producer):
    _require(type(meta) is dict and type(meta.get("id")) is int and meta["id"] == ARTIFACT
        and meta.get("name") == f"gdw-artifact-readonly-{RUN}-{ATTEMPT}"
        and meta.get("expired") is False and type(meta.get("size_in_bytes")) is int
        and meta["size_in_bytes"] == ARCHIVE_BYTES and meta.get("digest") == "sha256:" + ARCHIVE_SHA256,
        "OBSERVATION_ARTIFACT_UNQUALIFIED")
    run = meta.get("workflow_run")
    _require(type(run) is dict and type(run.get("id")) is int and run["id"] == RUN
        and run.get("head_sha") == SOURCE and run.get("head_branch") == "main"
        and run.get("repository_id") == REPOSITORY_ID and run.get("head_repository_id") == REPOSITORY_ID,
        "OBSERVATION_ARTIFACT_UNQUALIFIED")
    created = native.timestamp(meta.get("created_at"))
    _require(native.timestamp(producer.get("started_at")) <= created
        <= native.timestamp(producer.get("completed_at"))
        and created < datetime.now(timezone.utc) < native.timestamp(meta.get("expires_at")),
        "OBSERVATION_ARTIFACT_UNQUALIFIED")


def _archive(evidence, budget):
    budget()
    with evidence.client.stream("GET", f"{native.API}/repos/{native.REPOSITORY}/actions/artifacts/{ARTIFACT}/zip",
            headers={"Authorization": "Bearer " + evidence.token, "Accept": "application/vnd.github+json"}) as response:
        _require(response.status_code == 302, "OBSERVATION_ARTIFACT_UNQUALIFIED")
        location = response.headers.get("location", "")
    budget()
    parsed = urlsplit(location)
    host = parsed.hostname or ""
    _require(parsed.scheme == "https" and parsed.port in (None, 443) and not parsed.username
        and not parsed.password and not parsed.fragment and len(location) <= 16384
        and (host.endswith(".blob.core.windows.net") or host.endswith(".actions.githubusercontent.com")),
        "OBSERVATION_ARTIFACT_UNQUALIFIED")
    with evidence.client.stream("GET", location, headers={}) as response:
        budget()
        _require(response.status_code == 200, "OBSERVATION_ARTIFACT_UNQUALIFIED")
        archive = bytearray()
        for chunk in response.iter_bytes(chunk_size=1024):
            budget()
            _require(len(archive) + len(chunk) <= ARCHIVE_BYTES, "OBSERVATION_ARTIFACT_UNQUALIFIED")
            archive.extend(chunk)
    budget()
    return bytes(archive)


def _verified_summary():
    """Closed result shape; only verify_retained_observation establishes it."""
    return {"schema": SCHEMA, "state": "OBSERVATION_VERIFIED", "evidence_class": "REPORTED",
        "scope": "IMMUTABLE_RETAINED_OBJECT_OBSERVATION_ONLY", "source_revision": SOURCE,
        "run_id": RUN, "run_attempt": ATTEMPT, "job_id": PRODUCER_JOB, "contract_job_id": CONTRACT_JOB,
        "artifact_id": ARTIFACT, "archive_sha256": ARCHIVE_SHA256, "report_sha256": REPORT_SHA256,
        "dataset_revision": DATASET_REVISION, "head_presence_at_read_time": "ABSENT",
        "classification": "NO_EXPECTED_OBJECTS_PRESENT_AT_READ_TIME",
        "expected_object_count": EXPECTED_OBJECTS, "expected_object_set_sha256": EXPECTED_SET_SHA256,
        "present_object_count": 0, "missing_object_count": EXPECTED_OBJECTS,
        "prior_source_revision": PRIOR_SOURCE, "prior_run_id": PRIOR_RUN, "prior_job_id": PRIOR_JOB,
        "prior_provider_effects": "NOT_ESTABLISHED", "historical_writer_attribution": "NOT_ESTABLISHED",
        "provider_writes_performed": False, "retry_admitted": False, "restore_admitted": False,
        "deployment_admitted": False, "runtime_state_verified": False, "secret_values_recorded": False}


def verify_retained_observation(evidence):
    """Fixed GitHub GETs only; no current-source, provider-freshness or write admission."""
    try:
        _require(type(evidence.deadline) in (int, float) and math.isfinite(evidence.deadline),
            "OBSERVATION_UNAVAILABLE")
        deadline = min(evidence.deadline, time.monotonic() + MAX_SECONDS)
        def budget():
            _require(time.monotonic() < deadline, "OBSERVATION_UNAVAILABLE")
            evidence.budget()
            _require(time.monotonic() < deadline, "OBSERVATION_UNAVAILABLE")
        def get(suffix):
            budget()
            value = evidence.request(f"/repos/{native.REPOSITORY}/{suffix}")
            budget()
            return value
        run = get(f"actions/runs/{RUN}/attempts/{ATTEMPT}")
        started, ended = _run_binding(run)
        current = get(f"actions/runs/{RUN}")
        _require(_run_binding(current) == (started, ended)
            and current["workflow_id"] == run["workflow_id"], "OBSERVATION_RUN_UNQUALIFIED")
        commit = get(f"git/commits/{SOURCE}")
        _require(type(commit) is dict and commit.get("sha") == SOURCE
            and commit.get("verification", {}).get("verified") is True
            and commit.get("verification", {}).get("reason") == "valid", "OBSERVATION_SOURCE_UNQUALIFIED")
        producer = _producer(get(f"actions/runs/{RUN}/attempts/{ATTEMPT}/jobs?per_page=100"), started, ended)
        meta = get(f"actions/artifacts/{ARTIFACT}")
        _artifact_binding(meta, producer)
        members = native.validate_archive(meta, _archive(evidence, budget), artifact_id=ARTIFACT,
            expected_digest=ARCHIVE_SHA256, expected_name=f"gdw-artifact-readonly-{RUN}-{ATTEMPT}",
            source=SOURCE, run_id=RUN, repository_id=REPOSITORY_ID, members=frozenset({MEMBER}))
        validate_observation_report(members[MEMBER])
        # Recheck the unversioned endpoint after download; a later rerun cannot
        # silently substitute its producer for this first-attempt observation.
        current = get(f"actions/runs/{RUN}")
        _require(_run_binding(current) == (started, ended)
            and current["workflow_id"] == run["workflow_id"], "OBSERVATION_RUN_UNQUALIFIED")
        budget()
        return _verified_summary()
    except ObservationHeld:
        raise
    except Exception:
        raise ObservationHeld("OBSERVATION_UNAVAILABLE") from None
