#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: fixed 62ca read prerequisites, not an acquisition or retry path.

The initial canonical reconciliation worker reads native evidence and dataset
metadata only. A distinct, one-time candidate scan belongs inside the existing
900-second canonical acquisition supervisor, before pause or object writes.
Per-write checks re-observe source/fence only: uploading the first admitted
object must not be misclassified as a failed repeat of the all-missing scan.
No old helper, caller, workflow hold, provider writer or supervisor is changed.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

from scripts import gdw_acquisition_evidence as native
from scripts import reconcile_gdw_62ca_retained_observation as retained

SCHEMA = "szl.gdw-supervised-acquisition-62ca-prerequisite/v1"
SCAN_SCHEMA = "szl.gdw-supervised-acquisition-62ca-scan/v1"
PARENT_SOURCE = "02312993e02150388d9dd3e76617833610376e97"
DATASET = "SZLHOLDINGS/szl-evidence"
ENDPOINT = "https://huggingface.co"
HEAD_PATH = "a11oy/durable-store/v1/head.json"
RECONCILIATION_JOB_KEY = "recovery-reconciliation"
RECONCILIATION_JOB = "Reconcile the held acquisition before provider mutation"
JOB_NAMES = {RECONCILIATION_JOB_KEY: RECONCILIATION_JOB,
    native.ACQUISITION_JOB_KEY: native.ACQUISITION_JOB}
MAX_SECONDS = 120
MAX_SCAN_SECONDS = 300
READ_CALLBACK_BATCH = 32
ROOT = Path(__file__).resolve().parent.parent
CODES = frozenset({"NATIVE_CONTEXT_UNQUALIFIED", "SOURCE_SUCCESSOR_UNQUALIFIED",
    "NATIVE_RUN_NOT_UNIQUE", "SOURCE_ADMISSION_UNQUALIFIED", "RETAINED_OBSERVATION_UNQUALIFIED",
    "EXPECTED_ABSENCE_UNVERIFIED", "CANDIDATE_SCAN_UNQUALIFIED", "RECONCILIATION_UNAVAILABLE"})


class ReconciliationHeld(RuntimeError):
    def __init__(self, code):
        self.code = code if type(code) is str and code in CODES else "RECONCILIATION_UNAVAILABLE"
        super().__init__(self.code)


def _require(value, code):
    if value is not True:
        raise ReconciliationHeld(code)


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _value(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def _budget(deadline):
    _require(type(deadline) in (int, float) and math.isfinite(deadline)
        and time.monotonic() < deadline, "RECONCILIATION_UNAVAILABLE")


def _active_run(run, evidence):
    _require(type(run) is dict and type(run.get("id")) is int and run["id"] == evidence.run_id
        and type(run.get("run_attempt")) is int and run["run_attempt"] == 1
        and run.get("path") == native.WORKFLOW and run.get("event") == "push"
        and run.get("head_sha") == evidence.source and run.get("head_branch") == "main"
        and run.get("repository", {}).get("id") == retained.REPOSITORY_ID
        and run.get("repository", {}).get("full_name") == native.REPOSITORY
        and run.get("head_repository", {}).get("id") == retained.REPOSITORY_ID
        and type(run.get("workflow_id")) is int and run["workflow_id"] > 0
        and run.get("status") == "in_progress" and run.get("conclusion") is None,
        "NATIVE_CONTEXT_UNQUALIFIED")


def _current_context(evidence):
    _require(native.digest(evidence.source, 40) and evidence.source != PARENT_SOURCE
        and evidence.event == "push" and type(evidence.attempt) is int and evidence.attempt == 1
        and type(evidence.repository_id) is int and evidence.repository_id == retained.REPOSITORY_ID
        and evidence.executing_job in JOB_NAMES and os.environ.get("GITHUB_WORKFLOW_SHA") == evidence.source,
        "NATIVE_CONTEXT_UNQUALIFIED")
    evidence.observe_run()
    _active_run(evidence.run, evidence)
    current = evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{evidence.run_id}")
    _active_run(current, evidence)
    job = evidence.jobs.get(JOB_NAMES[evidence.executing_job])
    _require(type(job) is dict and type(job.get("id")) is int and job["id"] > 0
        and job.get("status") == "in_progress" and job.get("conclusion") is None
        and job.get("completed_at") is None
        and evidence.started <= native.timestamp(job.get("started_at")) <= datetime.now(timezone.utc),
        "NATIVE_CONTEXT_UNQUALIFIED")
    admitted = evidence.jobs.get(native.SOURCE_JOB)
    _require(type(admitted) is dict and admitted.get("status") == "completed"
        and admitted.get("conclusion") == "success", "SOURCE_ADMISSION_UNQUALIFIED")
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
    _active_run(rows[0], evidence)
    _require(current["workflow_id"] == evidence.run["workflow_id"] == rows[0]["workflow_id"],
        "NATIVE_RUN_NOT_UNIQUE")
    if evidence.executing_job == native.ACQUISITION_JOB_KEY:
        evidence.require_active_acquisition()
        qualified = evidence.jobs.get(native.QUALIFICATION_JOB)
        _require(type(qualified) is dict and qualified.get("status") == "completed"
            and qualified.get("conclusion") == "success", "NATIVE_CONTEXT_UNQUALIFIED")
    evidence.require_current_main()
    return {"source_revision": evidence.source, "run_id": evidence.run_id, "run_attempt": 1,
        "job_id": job["id"], "job_key": evidence.executing_job}


def _source_admission(evidence):
    listing = evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{evidence.run_id}/artifacts?per_page=100")
    rows = listing.get("artifacts")
    _require(type(rows) is list and type(listing.get("total_count")) is int
        and listing["total_count"] == len(rows) and 1 <= len(rows) <= 100, "SOURCE_ADMISSION_UNQUALIFIED")
    expected = f"canonical-source-admission-{evidence.run_id}-1"
    matches = [row for row in rows if type(row) is dict and row.get("name") == expected]
    _require(len(matches) == 1, "SOURCE_ADMISSION_UNQUALIFIED")
    meta = matches[0]
    binding = meta.get("workflow_run")
    _require(type(meta.get("id")) is int and meta["id"] > 0 and type(meta.get("digest")) is str
        and meta["digest"].startswith("sha256:") and native.digest(meta["digest"][7:])
        and type(binding) is dict and binding.get("id") == evidence.run_id
        and binding.get("head_sha") == evidence.source and binding.get("head_branch") == "main"
        and binding.get("repository_id") == binding.get("head_repository_id") == evidence.repository_id,
        "SOURCE_ADMISSION_UNQUALIFIED")
    members = evidence.artifact(meta["id"], meta["digest"][7:], name=expected, job_name=native.SOURCE_JOB,
        members=frozenset({"canonical-source-admission.json"}))
    raw = members["canonical-source-admission.json"]
    evidence.source_context(raw, JOB_NAMES[evidence.executing_job])
    producer = evidence.jobs[native.SOURCE_JOB]
    _require(native.timestamp(producer.get("started_at")) <= native.timestamp(meta.get("created_at"))
        <= native.timestamp(producer.get("completed_at"))
        and native.timestamp(meta.get("created_at")) < datetime.now(timezone.utc)
        < native.timestamp(meta.get("expires_at")), "SOURCE_ADMISSION_UNQUALIFIED")
    return {"source_admission_artifact_id": meta["id"], "source_admission_archive_sha256": meta["digest"][7:],
        "source_admission_sha256": hashlib.sha256(raw).hexdigest()}


def verify_native_prerequisite(evidence):
    """No provider access: one current native owner and exact immutable evidence."""
    try:
        deadline = min(evidence.deadline, time.monotonic() + MAX_SECONDS)
        _budget(deadline)
        context = _current_context(evidence)
        context.update(_source_admission(evidence))
        _budget(deadline)
        observed = retained.verify_retained_observation(evidence)
        _require(_canonical(observed) == _canonical(retained._verified_summary()), "RETAINED_OBSERVATION_UNQUALIFIED")
        _budget(deadline)
        _require(_current_context(evidence) == {key: context[key]
            for key in ("source_revision", "run_id", "run_attempt", "job_id", "job_key")}, "NATIVE_CONTEXT_UNQUALIFIED")
        _budget(deadline)
        return context
    except ReconciliationHeld:
        raise
    except Exception:
        raise ReconciliationHeld("RECONCILIATION_UNAVAILABLE") from None


def require_expected_absent(api, evidence, deadline):
    """SDK-neutral per-write source/fence guard; never repeats the object scan."""
    try:
        _require(_value(api, "endpoint") == ENDPOINT and native.digest(evidence.source, 40)
            and evidence.source != PARENT_SOURCE, "EXPECTED_ABSENCE_UNVERIFIED")
        _budget(deadline)
        evidence.require_current_main()
        for _ in range(2):
            _budget(deadline)
            info = api.dataset_info(DATASET, revision="main", expand=["sha", "private", "resourceGroup"])
            _require(_value(info, "id") == DATASET and _value(info, "private") is True
                and _value(info, "sha") == retained.DATASET_REVISION, "EXPECTED_ABSENCE_UNVERIFIED")
            _budget(deadline)
            paths = api.get_paths_info(DATASET, [HEAD_PATH], repo_type="dataset", revision=retained.DATASET_REVISION)
            _require(type(paths) is list and not paths, "EXPECTED_ABSENCE_UNVERIFIED")
        _budget(deadline)
        evidence.require_current_main()
        _budget(deadline)
        return {"state": "EXPECTED_HEAD_ABSENT", "source_revision": evidence.source,
            "dataset_revision": retained.DATASET_REVISION, "provider_writes_performed": False}
    except ReconciliationHeld:
        raise
    except Exception:
        raise ReconciliationHeld("EXPECTED_ABSENCE_UNVERIFIED") from None


def _report(context):
    return {"schema": SCHEMA, "state": "PREREQUISITE_VERIFIED",
        "scope": "ONE_SOURCE_ONE_RUN_NATIVE_AND_FENCE_ONLY", **context,
        "observation_source_revision": retained.SOURCE, "observation_run_id": retained.RUN,
        "observation_artifact_id": retained.ARTIFACT, "observation_report_sha256": retained.REPORT_SHA256,
        "prior_source_revision": retained.PRIOR_SOURCE, "prior_run_id": retained.PRIOR_RUN,
        "prior_provider_effects": "NOT_ESTABLISHED", "historical_writer_attribution": "NOT_ESTABLISHED",
        "dataset_revision": retained.DATASET_REVISION, "retained_object_scan_required_before_pause": True,
        "provider_objects_verified": False, "provider_writes_performed": False,
        "retry_admitted": False, "restore_admitted": False, "deployment_admitted": False,
        "secret_values_recorded": False}


def validate_reconciliation_report(raw):
    try:
        value = native.strict(raw, 4096)
        keys = ("source_revision", "run_id", "run_attempt", "job_id", "job_key",
            "source_admission_artifact_id", "source_admission_archive_sha256", "source_admission_sha256")
        context = {key: value[key] for key in keys}
        _require(native.digest(context["source_revision"], 40) and context["source_revision"] != PARENT_SOURCE
            and context["job_key"] in JOB_NAMES and type(context["run_attempt"]) is int and context["run_attempt"] == 1
            and all(type(context[key]) is int and context[key] > 0
                for key in ("run_id", "job_id", "source_admission_artifact_id"))
            and native.digest(context["source_admission_archive_sha256"])
            and native.digest(context["source_admission_sha256"])
            and raw == _canonical(_report(context)), "RECONCILIATION_UNAVAILABLE")
        return value
    except ReconciliationHeld:
        raise
    except Exception:
        raise ReconciliationHeld("RECONCILIATION_UNAVAILABLE") from None


def _scan_report(context, candidates, qualification_digest):
    candidate = candidates["gdw"]
    return {"schema": SCAN_SCHEMA, "state": "CURRENT_RETAINED_SET_VERIFIED",
        "scope": "ONE_CANDIDATE_BEFORE_PAUSE_BEFORE_OBJECT_WRITES", **context,
        "candidates": candidates,
        "candidate_sha256": candidate["sha256"], "candidate_bytes": candidate["size"],
        "capture_qualification_sha256": qualification_digest,
        "dataset_revision": retained.DATASET_REVISION,
        "expected_object_count": retained.EXPECTED_OBJECTS,
        "expected_object_set_sha256": retained.EXPECTED_SET_SHA256,
        "present_object_count": 0, "missing_object_count": retained.EXPECTED_OBJECTS,
        "prior_provider_effects": "NOT_ESTABLISHED", "historical_writer_attribution": "NOT_ESTABLISHED",
        "provider_writes_performed": False, "retry_admitted": False, "restore_admitted": False,
        "deployment_admitted": False, "secret_values_recorded": False}


def validate_scan_report(raw):
    """Closed observation decoder, not a writer lease or publication admission."""
    try:
        value = native.strict(raw, 4096)
        keys = ("source_revision", "run_id", "run_attempt", "job_id", "job_key",
            "source_admission_artifact_id", "source_admission_archive_sha256", "source_admission_sha256")
        context = {key: value[key] for key in keys}
        validate_reconciliation_report(_canonical(_report(context)))
        candidates = value["candidates"]
        _require(type(candidates) is dict and set(candidates) == {"gdw", "series_a"}
            and all(type(item) is dict and set(item) == {"sha256", "size"}
                and native.digest(item["sha256"]) and type(item["size"]) is int
                and 0 < item["size"] <= 256 * 1024 * 1024 for item in candidates.values()),
            "CANDIDATE_SCAN_UNQUALIFIED")
        _require(context["job_key"] == native.ACQUISITION_JOB_KEY
            and native.digest(value["capture_qualification_sha256"])
            and raw == _canonical(_scan_report(context, candidates, value["capture_qualification_sha256"])),
            "CANDIDATE_SCAN_UNQUALIFIED")
        return value
    except ReconciliationHeld:
        raise
    except Exception:
        raise ReconciliationHeld("CANDIDATE_SCAN_UNQUALIFIED") from None


class _ReadOnlyScanGuard:
    """Bound read callback; deliberately unsuitable as any pre-write guard.

    Every invocation checks the admitted native identity and deadline. Every
    32 read callbacks and at both boundaries it re-observes current main and
    the exact clean source checkout. Moving main holds before pause/writes;
    a successful historical or intermediate read is never cached authority.
    """
    def __init__(self, evidence, context, deadline):
        self.evidence, self.context, self.deadline = evidence, dict(context), deadline
        self.calls = 0
        self.observe()

    def _identity(self):
        _budget(self.deadline)
        expected = {"GITHUB_SHA": self.context["source_revision"],
            "GITHUB_WORKFLOW_SHA": self.context["source_revision"],
            "GITHUB_RUN_ID": str(self.context["run_id"]), "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_JOB": native.ACQUISITION_JOB_KEY}
        _require(all(os.environ.get(key) == value for key, value in expected.items())
            and self.evidence.source == self.context["source_revision"]
            and self.evidence.run_id == self.context["run_id"] and self.evidence.attempt == 1
            and self.evidence.executing_job == native.ACQUISITION_JOB_KEY,
            "NATIVE_CONTEXT_UNQUALIFIED")

    def observe(self):
        self._identity()
        for arguments in (("rev-parse", "HEAD"), ("diff", "--quiet", "HEAD", "--")):
            _budget(self.deadline)
            result = subprocess.run(["git", "-C", str(ROOT), *arguments],
                capture_output=True, timeout=min(10, self.deadline - time.monotonic()), check=True)
            if arguments[0] == "rev-parse":
                _require(result.stdout.decode("ascii").strip() == self.context["source_revision"],
                    "SOURCE_SUCCESSOR_UNQUALIFIED")
        self.evidence.require_current_main()
        self._identity()

    def __call__(self):
        self._identity()
        self.calls += 1
        if self.calls % READ_CALLBACK_BATCH == 0:
            self.observe()


def execute_native_reconciliation(workspace, deadline):
    """Only native/source receipt and dataset metadata under the existing <=120s worker."""
    try:
        _require(type(deadline) in (int, float) and math.isfinite(deadline)
            and 0 < deadline - time.monotonic() <= MAX_SECONDS, "RECONCILIATION_UNAVAILABLE")
        import gdw_durable_storage as storage
        storage._private_directory(Path(workspace))
        evidence = native.NativeEvidence(dict(os.environ), deadline)
        context = verify_native_prerequisite(evidence)
        _require(context["job_key"] == RECONCILIATION_JOB_KEY, "NATIVE_CONTEXT_UNQUALIFIED")
        api = storage._hub_api(os.environ.get("HF_TOKEN", ""))
        require_expected_absent(api, evidence, deadline)
        _budget(deadline)
        report = validate_reconciliation_report(_canonical(_report(context)))
        _budget(deadline)
        return report
    except ReconciliationHeld:
        raise
    except Exception:
        raise ReconciliationHeld("RECONCILIATION_UNAVAILABLE") from None


def verify_candidate_scan(api, evidence, workspace, deadline):
    """Fresh one-time scan inside the owned acquisition worker, before pause/writes.

    The caller must compare candidate_sha256 to its later reproduced candidate
    before publishing. This report cannot replace qualification, pause/readback,
    exact byte-identity publication, per-write fence checks, or CAS admission.
    """
    try:
        _require(evidence.executing_job == native.ACQUISITION_JOB_KEY, "NATIVE_CONTEXT_UNQUALIFIED")
        deadline = min(deadline, time.monotonic() + MAX_SCAN_SECONDS)
        _budget(deadline)
        context = verify_native_prerequisite(evidence)
        require_expected_absent(api, evidence, deadline)
        import gdw_durable_storage as storage
        from gdw_durable_artifacts import LOGICAL_ROOTS
        from scripts import acquire_gdw_durable_storage as acquisition
        from scripts import qualify_gdw_store_recovery as recovery
        from scripts import triage_gdw_artifacts_readonly as triage
        directory = storage._private_directory(Path(workspace)) / "fixed-62ca-retained-scan"
        _require(not os.path.lexists(directory), "CANDIDATE_SCAN_UNQUALIFIED")
        directory.mkdir(mode=0o700)
        _require(os.environ.get("GDW_PROOF_DIR") == str(LOGICAL_ROOTS["proof_export"])
            and os.environ.get("GDW_RECEIPT_PROJECTION_DIR") == str(LOGICAL_ROOTS["receipt_projection"]),
            "CANDIDATE_SCAN_UNQUALIFIED")
        reference, captured, anchors, _historical = acquisition._references()
        def owned():
            _budget(deadline)
            evidence.require_current_main()
            _budget(deadline)
        qualified = recovery.qualify_capture(recovery.ReadOnlyCaptureHub(api), reference,
            directory / "capture", owned, deadline, historical_anchors=anchors,
            capture_report_sha256=hashlib.sha256(captured).hexdigest())
        _require(qualified.get("state") == "LOGICAL_CONTINUITY_VERIFIED"
            and qualified.get("provider_writes_performed") is False and qualified.get("originals_mutated") is False
            and qualified.get("restore_admitted") is False and qualified.get("deployment_admitted") is False,
            "CANDIDATE_SCAN_UNQUALIFIED")
        databases = triage._qualified_capture_databases(qualified, frozenset(("gdw", "series_a")))
        database = directory / "capture/working/gdw/candidate.sqlite3"
        candidates = {label: storage._file_identity(directory / f"capture/working/{label}/candidate.sqlite3",
            directory, storage.MAX_SNAPSHOT_BYTES, deadline) for label in ("gdw", "series_a")}
        _require(all(candidates[label] == {"sha256": item.get("candidate_sha256"),
            "size": item.get("candidate_bytes")} for label, item in databases.items()), "CANDIDATE_SCAN_UNQUALIFIED")
        read_only = _ReadOnlyScanGuard(evidence, context, deadline)
        effects = triage.validate_artifact_effect_observation(triage.artifact_effect_observation(api, database,
            directory / "artifact-effects", read_only, deadline, logical_roots=LOGICAL_ROOTS))
        read_only.observe()
        expected = retained._expected_report()["artifact_effect_observation"]
        _require(_canonical(effects) == _canonical(expected)
            and all(storage._file_identity(directory / f"capture/working/{label}/candidate.sqlite3",
                directory, storage.MAX_SNAPSHOT_BYTES, deadline) == candidates[label] for label in ("gdw", "series_a")),
            "CANDIDATE_SCAN_UNQUALIFIED")
        require_expected_absent(api, evidence, deadline)
        _require(_current_context(evidence) == {key: context[key]
            for key in ("source_revision", "run_id", "run_attempt", "job_id", "job_key")}, "NATIVE_CONTEXT_UNQUALIFIED")
        _budget(deadline)
        report = validate_scan_report(_canonical(_scan_report(context, candidates,
            hashlib.sha256(_canonical(qualified)).hexdigest())))
        _budget(deadline)
        return report
    except ReconciliationHeld:
        raise
    except Exception:
        raise ReconciliationHeld("CANDIDATE_SCAN_UNQUALIFIED") from None
