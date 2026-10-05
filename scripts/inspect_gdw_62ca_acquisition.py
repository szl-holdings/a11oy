#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only metadata inspection of the fixed 62ca artifact-publication attempt.

Only metadata in the existing private dataset is read. No bucket content,
original database, configuration, pause, commit or upload API is available to
the adapter. Even an observed bootstrap is metadata evidence, never permission
to restore, retry acquisition or deploy. The canonical caller supplies a hard
process deadline and always returns HELD/exit 2 for this inspection.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

import gdw_durable_storage as storage
import gdw_durable_startup as startup
from scripts import gdw_acquisition_evidence as native

SCHEMA = "szl.gdw-held-acquisition-inspection-62ca/v1"
PRIOR_SOURCE = "62ca4d1506fe95f8bedf2143f5f8b60c786dcd74"
PRIOR_RUN = 37263869028
PRIOR_ATTEMPT = 1
PRIOR_JOB = 111616768413
PRIOR_QUALIFICATION_JOB = 111616609573
PRIOR_SOURCE_RECEIPT = "596d2dd741cec3684fbf2f87040be96823757caaa0331bd7bc6c4267b58ae96e"
PRIOR_QUALIFICATION = "37bdf39c89fc6aee7aa50de0da96465c3941fb4632fd75012c6e03afd767b973"
PRIOR_ARTIFACT = 11324504756
PRIOR_ARCHIVE = "127c4412063effef9c554a6cf6f6a084e17d69a7b4a3675521e03aee33d2af0d"

# The qualification artifact above is distinct from the safe failed-acquisition
# artifact below. These immutable native facts select an inspection, never retry.
PRIOR_SOURCE_JOB = 111616471901
PRIOR_RECONCILIATION_JOB = 111616522098
REPOSITORY_ID = 1225834126
FAILURE_ARTIFACT = 11325467455
FAILURE_ARCHIVE_BYTES = 389
FAILURE_ARCHIVE_SHA256 = "d290fa69bf530ec3cc27daccfd0daef13904064c2f3a75f73fe2bc71c2515afd"
FAILURE_REPORT_BYTES = 298
FAILURE_REPORT_SHA256 = "f4e638d0b73f865add47e16c7de5bdfff9f9ce8b6b505ee4e6debf1098db35a2"
MAX_SECONDS = 120
CLASSIFICATIONS = frozenset({"ABSENT", "ACKNOWLEDGED", "INVALID", "UNAVAILABLE"})


class InspectionInvalid(RuntimeError):
    """A fixed contract failure; its message is never copied to a report."""


def _require(value):
    if value is not True:
        raise InspectionInvalid()


def _report(source, classification, *, revision=None, head_digest=None, admission_digest=None, prior_verified=False):
    _require(storage._revision(source) and type(classification) is str and classification in CLASSIFICATIONS)
    _require(type(prior_verified) is bool)
    return {"schema": SCHEMA, "state": "HELD", "mode": "INSPECT_ONLY",
        "classification": classification, "source_revision": source,
        "prior_source_revision": PRIOR_SOURCE, "prior_run_id": PRIOR_RUN,
        "prior_run_attempt": PRIOR_ATTEMPT, "prior_job_id": PRIOR_JOB,
        "dataset_revision": revision, "head_sha256": head_digest,
        "admission_sha256": admission_digest,
        "scope": "PRIVATE_DATASET_METADATA_ONLY",
        "prior_acquisition_artifact_id": FAILURE_ARTIFACT,
        "prior_acquisition_archive_sha256": FAILURE_ARCHIVE_SHA256,
        "prior_acquisition_report_sha256": FAILURE_REPORT_SHA256,
        "prior_native_artifact_verified": prior_verified,
        "prior_stage": "ARTIFACT_PUBLICATION", "prior_stage_state": "BOUNDARY_ENTERED",
        "prior_provider_effects": "NOT_ESTABLISHED", "runtime_state_verified": False,
        "provider_objects_verified": False, "provider_writes_performed": False,
        "restore_admitted": False, "deployment_admitted": False,
        "retry_admitted": False, "secret_values_recorded": False}


def validate_result(value):
    """Strict parent-process allowlist; no worker text or arbitrary JSON escapes."""
    _require(type(value) is dict and set(value) == set(_report("a" * 40, "UNAVAILABLE")))
    expected = _report(value["source_revision"], value["classification"],
        revision=value["dataset_revision"], head_digest=value["head_sha256"],
        admission_digest=value["admission_sha256"], prior_verified=value["prior_native_artifact_verified"])
    _require(storage.canonical(value) == storage.canonical(expected))
    if value["classification"] in {"ABSENT", "ACKNOWLEDGED"}:
        _require(storage._revision(value["dataset_revision"]) and value["prior_native_artifact_verified"] is True)
    else:
        _require(value["dataset_revision"] is None)
    for key in ("head_sha256", "admission_sha256"):
        _require(storage._digest(value[key]) if value["classification"] == "ACKNOWLEDGED" else value[key] is None)
    return json.loads(storage.canonical(value))


def validate_inspection_report(raw: bytes):
    """Bounded canonical bytes from an inspect-only child, never a locator."""
    from scripts.gdw_acquisition_evidence import strict
    value = validate_result(strict(raw, 4096))
    _require(storage.canonical(value) == raw)
    return value


class ReadOnlyDataset:
    """Exactly three SDK read methods; no delegation to other provider methods."""
    endpoint = storage.ENDPOINT

    def __init__(self, api, require_current_main, deadline):
        _require(storage._value(api, "endpoint") == storage.ENDPOINT)
        self._api, self._owner, self._deadline = api, require_current_main, deadline
        self._paths = {storage.HEAD_PATH}

    def _before(self):
        storage._deadline(self._deadline)
        self._owner()
        storage._deadline(self._deadline)

    def dataset_info(self, repo_id, *, revision, expand):
        _require(repo_id == storage.DATASET and (revision == "main" or storage._revision(revision))
            and expand == ["sha", "private", "resourceGroup"])
        self._before()
        return self._api.dataset_info(repo_id, revision=revision, expand=expand)

    def get_paths_info(self, repo_id, paths, *, repo_type, revision):
        _require(repo_id == storage.DATASET and repo_type == "dataset" and storage._revision(revision)
            and type(paths) is list and len(paths) == 1 and paths[0] in self._paths)
        self._before()
        return self._api.get_paths_info(repo_id, paths, repo_type=repo_type, revision=revision)

    def hf_hub_download(self, repo_id, *, filename, repo_type, revision, local_dir, cache_dir):
        _require(repo_id == storage.DATASET and repo_type == "dataset" and storage._revision(revision)
            and filename in self._paths)
        self._before()
        return self._api.hf_hub_download(repo_id, filename=filename, repo_type=repo_type,
            revision=revision, local_dir=local_dir, cache_dir=cache_dir)

    def allow_bound_head(self, head):
        # Head already parsed the strict canonical shape and fixed path prefixes.
        _require(head.value["kind"] == "BOOTSTRAP" and head.value["source_revision"] == PRIOR_SOURCE)
        self._paths.update({f"{storage.HISTORY_PREFIX}/{head.value['operation_id']}.json",
            f"{storage.ADMISSION_PREFIX}/{head.value['qualification_sha256']}.json"})


def _prior_binding(admission, head, group):
    startup.validate_bootstrap_binding(admission, head.value)
    expected = {"repository": "szl-holdings/a11oy", "ref": "refs/heads/main", "revision": PRIOR_SOURCE,
        "workflow_path": ".github/workflows/hf-sync.yml", "run_id": PRIOR_RUN,
        "run_attempt": PRIOR_ATTEMPT, "job_id": PRIOR_JOB, "event_name": "push",
        "source_admission_state": "VERIFIED", "source_admission_sha256": PRIOR_SOURCE_RECEIPT}
    _require(admission["source"] == expected)
    expected["job_id"] = PRIOR_QUALIFICATION_JOB
    qualification = admission["qualification"]
    _require(qualification["source"] == expected
        and qualification["report_sha256"] == PRIOR_QUALIFICATION
        and qualification["artifact_id"] == PRIOR_ARTIFACT
        and qualification["artifact_archive_sha256"] == PRIOR_ARCHIVE
        and admission["provider"]["resource_group_observation_sha256"] == group)



def _integer(value):
    return type(value) is int and value > 0


def _current_context(evidence):
    """Only the source-admitted first push can perform this fixed inspection."""
    _require(evidence.source != PRIOR_SOURCE and evidence.event == "push"
        and type(evidence.attempt) is int and evidence.attempt == 1
        and type(evidence.repository_id) is int and evidence.repository_id == REPOSITORY_ID
        and evidence.executing_job == native.ACQUISITION_JOB_KEY
        and os.environ.get("GITHUB_WORKFLOW_SHA") == evidence.source)
    evidence.observe_run()
    evidence.require_active_acquisition()
    admitted = evidence.jobs.get(native.SOURCE_JOB)
    _require(type(admitted) is dict and admitted.get("status") == "completed"
        and admitted.get("conclusion") == "success")
    for name in ("Reconcile the held acquisition before provider mutation", native.QUALIFICATION_JOB):
        held = evidence.jobs.get(name)
        _require(type(held) is dict and held.get("status") == "completed"
            and held.get("conclusion") == "skipped")
    evidence.require_current_main()


def _prior_producer(evidence):
    """Bind the one terminal 62ca attempt and its observed job/step boundary."""
    run = evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{PRIOR_RUN}/attempts/1")
    _require(type(run) is dict and type(run.get("id")) is int and run["id"] == PRIOR_RUN
        and type(run.get("run_attempt")) is int and run["run_attempt"] == PRIOR_ATTEMPT
        and run.get("path") == native.WORKFLOW and run.get("event") == "push"
        and run.get("head_sha") == PRIOR_SOURCE and run.get("head_branch") == "main"
        and run.get("repository", {}).get("id") == REPOSITORY_ID
        and run.get("repository", {}).get("full_name") == native.REPOSITORY
        and run.get("head_repository", {}).get("id") == REPOSITORY_ID
        and run.get("status") == "completed" and run.get("conclusion") == "failure")
    listing = evidence.request(f"/repos/{native.REPOSITORY}/actions/runs/{PRIOR_RUN}/attempts/1/jobs?per_page=100")
    jobs = listing.get("jobs")
    _require(type(listing.get("total_count")) is int and listing["total_count"] == 13
        and type(jobs) is list and len(jobs) == 13)
    expected = {
        PRIOR_SOURCE_JOB: (native.SOURCE_JOB, "success"),
        PRIOR_RECONCILIATION_JOB: ("Reconcile the held acquisition before provider mutation", "success"),
        PRIOR_QUALIFICATION_JOB: (native.QUALIFICATION_JOB, "success"),
        PRIOR_JOB: (native.ACQUISITION_JOB, "failure"),
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
    seen = set()
    names = set()
    producer = None
    for job in jobs:
        _require(type(job) is dict and _integer(job.get("id")) and job["id"] not in seen
            and type(job.get("name")) is str and job["name"] not in names
            and type(job.get("run_id")) is int and job["run_id"] == PRIOR_RUN
            and type(job.get("run_attempt")) is int and job["run_attempt"] == PRIOR_ATTEMPT
            and job.get("head_sha") == PRIOR_SOURCE and job.get("status") == "completed")
        seen.add(job["id"])
        names.add(job["name"])
        _require(job["id"] in expected
            and (job["name"], job.get("conclusion")) == expected[job["id"]])
        if job["id"] == PRIOR_JOB:
            producer = job
    _require(set(expected) == seen and producer is not None)
    steps = producer.get("steps")
    _require(type(steps) is list and 1 <= len(steps) <= 30
        and all(type(step) is dict and type(step.get("name")) is str
                and step.get("status") == "completed" for step in steps)
        and len({step["name"] for step in steps}) == len(steps))
    by_name = {step["name"]: step for step in steps}
    failed = [step["name"] for step in steps if step.get("conclusion") == "failure"]
    _require(failed == ["Reconcile again, verify native candidates, and acquire private storage once"]
        and by_name.get("Install the persistent old-source guard and both managed configurations once", {}).get("conclusion") == "skipped"
        and by_name.get("Retain only the immutable selector and safe guarded configuration result", {}).get("conclusion") == "success")
    return run, producer


def _prior_failure_archive(evidence, run, producer):
    """Read only the exact safe failure artifact; never extract its member."""
    meta = evidence.request(f"/repos/{native.REPOSITORY}/actions/artifacts/{FAILURE_ARTIFACT}")
    _require(type(meta.get("size_in_bytes")) is int and meta["size_in_bytes"] == FAILURE_ARCHIVE_BYTES
        and native.timestamp(run.get("run_started_at")) <= native.timestamp(producer.get("started_at"))
        <= native.timestamp(meta.get("created_at")) <= native.timestamp(producer.get("completed_at")))
    evidence.budget()
    with evidence.client.stream("GET", f"{native.API}/repos/{native.REPOSITORY}/actions/artifacts/{FAILURE_ARTIFACT}/zip",
            headers={"Authorization": "Bearer " + evidence.token, "Accept": "application/vnd.github+json"}) as response:
        _require(response.status_code == 302)
        location = response.headers.get("location", "")
    parsed = urlsplit(location)
    host = parsed.hostname or ""
    _require(parsed.scheme == "https" and parsed.port in (None, 443) and not parsed.username
        and not parsed.password and not parsed.fragment and len(location) <= 16384
        and (host.endswith(".blob.core.windows.net") or host.endswith(".actions.githubusercontent.com")))
    with evidence.client.stream("GET", location, headers={}) as response:
        _require(response.status_code == 200)
        archive = bytearray()
        for chunk in response.iter_bytes(chunk_size=1024):
            evidence.budget()
            _require(len(archive) + len(chunk) <= FAILURE_ARCHIVE_BYTES)
            archive.extend(chunk)
    members = native.validate_archive(meta, bytes(archive), artifact_id=FAILURE_ARTIFACT,
        expected_digest=FAILURE_ARCHIVE_SHA256, expected_name=f"canonical-durable-acquisition-{PRIOR_RUN}-1",
        source=PRIOR_SOURCE, run_id=PRIOR_RUN, repository_id=REPOSITORY_ID,
        members=frozenset({"gdw-durable-acquisition.json"}))
    raw = members["gdw-durable-acquisition.json"]
    _require(len(raw) == FAILURE_REPORT_BYTES and hashlib.sha256(raw).hexdigest() == FAILURE_REPORT_SHA256)
    expected = {"deployment_admitted": False, "diagnostic_code": "CANONICAL_ACQUISITION_UNAVAILABLE",
        "provider_effects": "NOT_ESTABLISHED", "restore_admitted": False,
        "schema": "szl.gdw-durable-acquisition/v1", "secret_values_recorded": False,
        "stage": "ARTIFACT_PUBLICATION", "stage_state": "BOUNDARY_ENTERED", "state": "HELD"}
    report = native.strict(raw, FAILURE_REPORT_BYTES)
    _require(storage.canonical(report) == raw == storage.canonical(expected))
    evidence.budget()


def _verify_prior_failure(evidence):
    """Validate the fixed native failure before any private provider metadata."""
    run, producer = _prior_producer(evidence)
    _prior_failure_archive(evidence, run, producer)
    evidence.budget()


def inspect_held_acquisition(api, *, private_directory: Path, evidence, deadline: float):
    """Reconcile fixed prior metadata under the current canonical job authority.

    Two identical immutable main observations bound every successful result.
    The fixed native report proves entry into a phase, not a provider callback.
    ABSENT concerns HEAD alone; uploaded orphan objects may still exist. An
    ACKNOWLEDGED result proves the private metadata binding only, with no claim
    that stored objects or a running service have been validated.
    """
    source = evidence.source
    _require(storage._revision(source))
    classification = "UNAVAILABLE"
    prior_verified = False
    try:
        _require(type(deadline) in (float, int) and 0 < deadline - time.monotonic() <= MAX_SECONDS)
        _current_context(evidence)
        _verify_prior_failure(evidence)
        prior_verified = True
        evidence.require_current_main()
        directory = storage._private_directory(private_directory)
        reader = ReadOnlyDataset(api, evidence.require_current_main, deadline)
        info = reader.dataset_info(storage.DATASET, revision="main", expand=["sha", "private", "resourceGroup"])
        _require(storage._value(info, "id") == storage.DATASET
            and storage._value(info, "private") is True and storage._revision(storage._value(info, "sha")))
        first_revision = storage._value(info, "sha")
        group = hashlib.sha256(storage.canonical(storage._value(info, "resource_group"))).hexdigest()
        backend = storage.HFDatasetFenceBackend(reader, directory, group, None)
        present = backend._paths(first_revision, storage.HEAD_PATH, deadline)
        if not present:
            # Recheck the exact main identity and absence; no listing of private
            # objects or bytes is needed to establish this bounded fact.
            _require(backend.empty_parent(deadline) == first_revision)
            evidence.require_active_acquisition()
            evidence.require_current_main()
            storage._deadline(deadline)
            return _report(source, "ABSENT", revision=first_revision, prior_verified=prior_verified)
        raw_head = backend._read(first_revision, storage.HEAD_PATH, deadline)
        try:
            head = storage.Head(first_revision, raw_head)
        except storage.StorageBlocked:
            raise InspectionInvalid() from None
        reader.allow_bound_head(head)
        observed, history = backend.read_at(first_revision, head.value["operation_id"], deadline)
        _require(observed.body == head.body == history)
        data = backend.read_admission(head, deadline)
        admission = startup.parse_admission(data)
        _prior_binding(admission, head, group)
        latest = backend.observe(deadline)
        _require(latest.revision == first_revision and latest.body == head.body)
        evidence.require_active_acquisition()
        evidence.require_current_main()
        storage._deadline(deadline)
        return _report(source, "ACKNOWLEDGED", revision=first_revision,
            head_digest=head.digest, admission_digest=head.value["qualification_sha256"], prior_verified=prior_verified)
    except (InspectionInvalid, startup.AdmissionBlocked):
        classification = "INVALID"
    except Exception:
        # Includes transport failures, ownership changes and missing referenced
        # metadata. None may be interpreted as proof that HEAD is absent.
        pass
    return _report(source, classification, prior_verified=prior_verified)


def execute_native_inspection(workspace: Path, deadline: float):
    """The sole source-owned entrypoint; invoked inside the bounded worker."""
    from scripts.gdw_acquisition_evidence import NativeEvidence
    evidence = NativeEvidence(dict(os.environ), deadline)
    api = storage._hub_api(os.environ.get("HF_TOKEN", ""))
    return validate_result(inspect_held_acquisition(api, private_directory=workspace,
        evidence=evidence, deadline=deadline))
