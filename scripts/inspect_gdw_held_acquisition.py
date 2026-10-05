#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only reconciliation of the held d61 canonical acquisition.

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

import gdw_durable_storage as storage
import gdw_durable_startup as startup

SCHEMA = "szl.gdw-held-acquisition-inspection/v1"
PRIOR_SOURCE = "d61a838e8763f560ddbd113bfa398f4bb64f2342"
PRIOR_RUN = 37244394814
PRIOR_ATTEMPT = 1
PRIOR_JOB = 111559424879
PRIOR_QUALIFICATION_JOB = 111559322954
PRIOR_SOURCE_RECEIPT = "1e498e17f212766ff7275657b7e17417c3dbf59f73fd09f3e4d38ee434042712"
PRIOR_QUALIFICATION = "2eac27105865f6f737b2387bc6d6a407c53172c1553b1916b4d30739893c4d3d"
PRIOR_ARTIFACT = 11318298151
PRIOR_ARCHIVE = "caf0c42decb75fe293c14502c01f06b47f1ef0680e4bb5ceeefedb523db6f9a1"
MAX_SECONDS = 120
CLASSIFICATIONS = frozenset({"ABSENT", "ACKNOWLEDGED", "INVALID", "UNAVAILABLE"})


class InspectionInvalid(RuntimeError):
    """A fixed contract failure; its message is never copied to a report."""


def _require(value):
    if value is not True:
        raise InspectionInvalid()


def _report(source, classification, *, revision=None, head_digest=None, admission_digest=None):
    _require(storage._revision(source) and type(classification) is str and classification in CLASSIFICATIONS)
    return {"schema": SCHEMA, "state": "HELD", "mode": "INSPECT_ONLY",
        "classification": classification, "source_revision": source,
        "prior_source_revision": PRIOR_SOURCE, "prior_run_id": PRIOR_RUN,
        "prior_run_attempt": PRIOR_ATTEMPT, "prior_job_id": PRIOR_JOB,
        "dataset_revision": revision, "head_sha256": head_digest,
        "admission_sha256": admission_digest,
        "scope": "PRIVATE_DATASET_METADATA_ONLY",
        "provider_objects_verified": False, "provider_writes_performed": False,
        "restore_admitted": False, "deployment_admitted": False,
        "retry_admitted": False, "secret_values_recorded": False}


def validate_result(value):
    """Strict parent-process allowlist; no worker text or arbitrary JSON escapes."""
    _require(type(value) is dict and set(value) == set(_report("a" * 40, "UNAVAILABLE")))
    expected = _report(value["source_revision"], value["classification"],
        revision=value["dataset_revision"], head_digest=value["head_sha256"],
        admission_digest=value["admission_sha256"])
    _require(storage.canonical(value) == storage.canonical(expected))
    if value["classification"] in {"ABSENT", "ACKNOWLEDGED"}:
        _require(storage._revision(value["dataset_revision"]))
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


def inspect_held_acquisition(api, *, private_directory: Path, evidence, deadline: float):
    """Reconcile fixed prior metadata under the current canonical job authority.

    Two identical immutable main observations bound every successful result.
    ABSENT concerns HEAD alone; uploaded orphan objects may still exist. An
    ACKNOWLEDGED result proves the private metadata binding only, with no claim
    that stored objects or a running service have been validated.
    """
    source = evidence.source
    _require(storage._revision(source))
    classification = "UNAVAILABLE"
    try:
        _require(type(deadline) in (float, int) and 0 < deadline - time.monotonic() <= MAX_SECONDS)
        evidence.observe_run()
        evidence.require_active_acquisition()
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
            return _report(source, "ABSENT", revision=first_revision)
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
            head_digest=head.digest, admission_digest=head.value["qualification_sha256"])
    except (InspectionInvalid, startup.AdmissionBlocked):
        classification = "INVALID"
    except Exception:
        # Includes transport failures, ownership changes and missing referenced
        # metadata. None may be interpreted as proof that HEAD is absent.
        pass
    return _report(source, classification)


def execute_native_inspection(workspace: Path, deadline: float):
    """The sole source-owned entrypoint; invoked inside the bounded worker."""
    from scripts.gdw_acquisition_evidence import NativeEvidence
    evidence = NativeEvidence(dict(os.environ), deadline)
    api = storage._hub_api(os.environ.get("HF_TOKEN", ""))
    return validate_result(inspect_held_acquisition(api, private_directory=workspace,
        evidence=evidence, deadline=deadline))
