# SPDX-License-Identifier: Apache-2.0
"""Fixed native failure metadata and synthetic SDK reads; never provider bytes."""
import base64
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import time
import zipfile

import httpx
import pytest

import gdw_durable_startup as startup
import gdw_durable_storage as storage
from scripts import gdw_acquisition_evidence as native
from scripts import inspect_gdw_62ca_acquisition as inspection
from scripts import inspect_gdw_held_acquisition as legacy
from tests.test_gdw_held_acquisition_inspection import DatasetAPI, fixture_record


# Exact public, closed GitHub failure artifact 11325467455. This contains only
# gdw-durable-acquisition.json, not a HEAD, admission, capture, object or database.
FAILURE_ARCHIVE = base64.b64decode(
    "UEsDBBQACAAIACgkRV0AAAAAAAAAAAAAAAAcAAAAZ2R3LWR1cmFibGUtYWNxdWlzaXRpb24uanNvbmWOwUrEMBRF937GW3cUt92lbWQCIdU2FVw9YvLaCbTNmKQVFf9dRhQE1+dyz/kAR+c5vC20ZjRu8TmTg3I0c6ICnDfTGlL2Fm1wBCXUTLVK1Ewiqx8G0QstWoWDYo9MSFZJDgWcY9i9o4g0jmRzghJUq5H3mlVS9EfeQAGRUg6R/juTPdFioIT0Pl9P7vXgtmieZzoY+7L55LMP681+CwUkspEy7mbeKGEkG6L7e5TNdElmnRZ3rNZ4P1RS1OxSDD8YUzb5MqraQTWse0KuNO++C3/RkcsGPq++AFBLBwg4BZup2wAAACoBAABQSwECLQMUAAgACAAoJEVdOAWbqdsAAAAqAQAAHAAAAAAAAAAAACAAgIEAAAAAZ2R3LWR1cmFibGUtYWNxdWlzaXRpb24uanNvblBLBQYAAAAAAQABAEoAAAAlAQAAAAA="
)
SOURCE = "62ca4d1506fe95f8bedf2143f5f8b60c786dcd74"
RUN = 37263869028
FAILURE_JOB = 111616768413
FALSE_FLAGS = (
    "provider_objects_verified", "provider_writes_performed", "runtime_state_verified",
    "restore_admitted", "deployment_admitted", "retry_admitted", "secret_values_recorded",
)


def native_fixture(monkeypatch):
    """Real NativeEvidence over a GET-only in-memory transport."""
    started = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    env = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": native.REPOSITORY,
        "GITHUB_REPOSITORY_ID": "1225834126", "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": "b" * 40, "GITHUB_WORKFLOW_SHA": "b" * 40,
        "GITHUB_WORKFLOW_REF": native.REPOSITORY + "/" + native.WORKFLOW + "@refs/heads/main",
        "GITHUB_RUN_ID": "900", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_EVENT_NAME": "push", "GITHUB_JOB": native.ACQUISITION_JOB_KEY,
        "GH_TOKEN": "synthetic-token",
    }
    monkeypatch.setenv("GITHUB_WORKFLOW_SHA", env["GITHUB_SHA"])
    run = {
        "id": 900, "run_attempt": 1, "workflow_id": 288177871,
        "path": native.WORKFLOW, "event": "push", "head_branch": "main",
        "head_sha": env["GITHUB_SHA"], "status": "in_progress", "conclusion": None,
        "run_started_at": started,
        "repository": {"id": 1225834126, "full_name": native.REPOSITORY},
        "head_repository": {"id": 1225834126},
    }
    active = {
        "id": 901, "run_id": 900, "run_attempt": 1, "head_sha": env["GITHUB_SHA"],
        "name": native.ACQUISITION_JOB, "status": "in_progress", "conclusion": None,
        "started_at": started, "completed_at": None,
    }
    jobs = {"total_count": 4, "jobs": [active, dict(
        active, id=902, name=native.SOURCE_JOB, status="completed", conclusion="success",
        completed_at=started,
    )] + [
        dict(active, id=identifier, name=name, status="completed", conclusion="skipped",
             completed_at=started)
        for identifier, name in (
            (903, "Reconcile the held acquisition before provider mutation"),
            (904, native.QUALIFICATION_JOB),
        )
    ]}
    prior_run = dict(copy.deepcopy(run), id=RUN, head_sha=SOURCE, status="completed",
                     conclusion="failure", run_started_at="2026-10-05T04:31:06Z")
    producer = {
        "id": FAILURE_JOB, "run_id": RUN, "run_attempt": 1, "head_sha": SOURCE,
        "name": native.ACQUISITION_JOB, "status": "completed", "conclusion": "failure",
        "started_at": "2026-10-05T04:32:32Z", "completed_at": "2026-10-05T04:33:19Z",
        "steps": [
            {"name": "Reconcile again, verify native candidates, and acquire private storage once",
             "status": "completed", "conclusion": "failure"},
            {"name": "Install the persistent old-source guard and both managed configurations once",
             "status": "completed", "conclusion": "skipped"},
            {"name": "Retain only the immutable selector and safe guarded configuration result",
             "status": "completed", "conclusion": "success"},
        ],
    }
    prior_jobs = {"total_count": 13, "jobs": [producer] + [
        dict(producer, id=identifier, name=name, conclusion="success", steps=[])
        for identifier, name in (
            (111616471901, native.SOURCE_JOB),
            (111616522098, "Reconcile the held acquisition before provider mutation"),
            (111616609573, native.QUALIFICATION_JOB),
        )
    ] + [
        dict(producer, id=identifier, name=name, conclusion="skipped", steps=[])
        for identifier, name in (
            (111616769593, "Resume the canonical Space without changing its allocation"),
            (111616946613, "Deploy, source-bind, and attest exact surface"),
            (111616947075, "Verify post-deploy configuration and bounded live proofs"),
            (111616947443, "Publish and live-verify six domain-native flagship Spaces"),
            (111616948013, "Probe and ingest exact post-deploy readiness verdict"),
            (111616948054, "Prove exact live source, runtime, routes, and singleton state"),
            (111616948338, "Rebind and functionally verify the existing Finance projection"),
            (111616948584, "Re-authorize exact protected main after all publication proofs"),
            (111616948662, "Await strict live and repository parity"),
        )
    ]}
    artifact = {
        "id": 11325467455, "expired": False,
        "name": "canonical-durable-acquisition-37263869028-1", "size_in_bytes": 389,
        "digest": "sha256:d290fa69bf530ec3cc27daccfd0daef13904064c2f3a75f73fe2bc71c2515afd",
        "created_at": "2026-10-05T04:33:18Z",
        "workflow_run": {"id": RUN, "head_sha": SOURCE, "head_branch": "main",
                         "repository_id": 1225834126, "head_repository_id": 1225834126},
    }
    state = {
        "run": run, "jobs": jobs, "prior_run": prior_run, "prior_jobs": prior_jobs,
        "artifact": artifact, "archive": FAILURE_ARCHIVE,
        "branch": {"name": "main", "protected": True, "commit": {"sha": env["GITHUB_SHA"]}},
        "location": "https://metadata.blob.core.windows.net/fixed?signature=synthetic",
        "download_status": 200,
    }
    calls = []

    def transport(request):
        calls.append(request)
        assert request.method == "GET"
        if request.url.host == "metadata.blob.core.windows.net":
            assert "authorization" not in request.headers
            return httpx.Response(state["download_status"], content=state["archive"])
        assert request.url.host == "api.github.com"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        path = request.url.path
        if path == f"/repos/{native.REPOSITORY}/actions/artifacts/11325467455/zip":
            return httpx.Response(302, headers={"location": state["location"]})
        if path == f"/repos/{native.REPOSITORY}/actions/artifacts/11325467455":
            return httpx.Response(200, json=state["artifact"])
        if path == f"/repos/{native.REPOSITORY}/branches/main":
            return httpx.Response(200, json=state["branch"])
        for run_id, prefix in ((900, ""), (RUN, "prior_")):
            if path == f"/repos/{native.REPOSITORY}/actions/runs/{run_id}/attempts/1/jobs":
                assert request.url.params == httpx.QueryParams("per_page=100")
                return httpx.Response(200, json=state[prefix + "jobs"])
            if path in {f"/repos/{native.REPOSITORY}/actions/runs/{run_id}/attempts/1",
                        f"/repos/{native.REPOSITORY}/actions/runs/{run_id}"}:
                return httpx.Response(200, json=state[prefix + "run"])
        pytest.fail("unexpected native metadata request: " + path)

    client = httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=False, trust_env=False)
    evidence = native.NativeEvidence(env, time.monotonic() + 60, client=client)
    return evidence, state, calls


def inspect(tmp_path, api, evidence):
    tmp_path.chmod(0o700)
    return inspection.inspect_held_acquisition(
        api, private_directory=tmp_path, evidence=evidence, deadline=evidence.deadline,
    )


def bound_record():
    record, head = fixture_record()
    record = json.loads(json.dumps(record).replace(legacy.PRIOR_SOURCE, SOURCE))
    record["source"].update(run_id=RUN, run_attempt=1, job_id=FAILURE_JOB,
                            source_admission_sha256=inspection.PRIOR_SOURCE_RECEIPT)
    record["qualification"].update(
        source=dict(record["source"], job_id=inspection.PRIOR_QUALIFICATION_JOB),
        report_sha256=inspection.PRIOR_QUALIFICATION, artifact_id=inspection.PRIOR_ARTIFACT,
        artifact_archive_sha256=inspection.PRIOR_ARCHIVE,
    )
    record["runtime"]["source_manifest_sha256"] = storage.sha256(storage.canonical(record["runtime"]["source_manifest"]))
    record["runtime"]["base_observation"]["execution"].update(run_id=RUN, run_attempt=1)
    record["latency"].update(run_id=RUN, run_attempt=1)
    head.update(source_revision=SOURCE, qualification_sha256=storage.sha256(storage.canonical(record)))
    return record, head


def test_fixed_tuple_is_the_verified_62ca_incident_and_not_its_failure_artifact():
    expected = {
        "PRIOR_SOURCE": SOURCE, "PRIOR_RUN": RUN, "PRIOR_ATTEMPT": 1,
        "PRIOR_JOB": FAILURE_JOB, "PRIOR_QUALIFICATION_JOB": 111616609573,
        "PRIOR_SOURCE_RECEIPT": "596d2dd741cec3684fbf2f87040be96823757caaa0331bd7bc6c4267b58ae96e",
        "PRIOR_QUALIFICATION": "37bdf39c89fc6aee7aa50de0da96465c3941fb4632fd75012c6e03afd767b973",
        "PRIOR_ARTIFACT": 11324504756,
        "PRIOR_ARCHIVE": "127c4412063effef9c554a6cf6f6a084e17d69a7b4a3675521e03aee33d2af0d",
        "PRIOR_SOURCE_JOB": 111616471901, "PRIOR_RECONCILIATION_JOB": 111616522098,
        "REPOSITORY_ID": 1225834126, "FAILURE_ARTIFACT": 11325467455,
        "FAILURE_ARCHIVE_BYTES": 389,
        "FAILURE_ARCHIVE_SHA256": "d290fa69bf530ec3cc27daccfd0daef13904064c2f3a75f73fe2bc71c2515afd",
        "FAILURE_REPORT_BYTES": 298,
        "FAILURE_REPORT_SHA256": "f4e638d0b73f865add47e16c7de5bdfff9f9ce8b6b505ee4e6debf1098db35a2",
    }
    assert {key: getattr(inspection, key) for key in expected} == expected
    assert inspection.SCHEMA == "szl.gdw-held-acquisition-inspection-62ca/v1"
    assert legacy.PRIOR_SOURCE == "d61a838e8763f560ddbd113bfa398f4bb64f2342"
    assert legacy.PRIOR_RUN == 37244394814
    assert inspection.PRIOR_ARTIFACT != inspection.FAILURE_ARTIFACT


def test_exact_native_archive_contains_only_the_closed_failure_metadata():
    assert len(FAILURE_ARCHIVE) == 389
    assert hashlib.sha256(FAILURE_ARCHIVE).hexdigest() == inspection.FAILURE_ARCHIVE_SHA256
    with zipfile.ZipFile(io.BytesIO(FAILURE_ARCHIVE)) as archive:
        assert archive.namelist() == ["gdw-durable-acquisition.json"]
        raw = archive.read("gdw-durable-acquisition.json")
    assert len(raw) == 298 and hashlib.sha256(raw).hexdigest() == inspection.FAILURE_REPORT_SHA256
    assert json.loads(raw) == {
        "schema": "szl.gdw-durable-acquisition/v1", "state": "HELD",
        "stage": "ARTIFACT_PUBLICATION", "stage_state": "BOUNDARY_ENTERED",
        "diagnostic_code": "CANONICAL_ACQUISITION_UNAVAILABLE",
        "provider_effects": "NOT_ESTABLISHED", "restore_admitted": False,
        "deployment_admitted": False, "secret_values_recorded": False,
    }
    assert raw == storage.canonical(json.loads(raw))


@pytest.mark.parametrize("classification", ["ABSENT", "ACKNOWLEDGED", "INVALID", "UNAVAILABLE"])
def test_report_profiles_cannot_be_substituted_for_one_another(classification):
    kwargs = {
        "revision": "e" * 40 if classification in {"ABSENT", "ACKNOWLEDGED"} else None,
        "head_digest": "a" * 64 if classification == "ACKNOWLEDGED" else None,
        "admission_digest": "b" * 64 if classification == "ACKNOWLEDGED" else None,
    }
    old = legacy._report("b" * 40, classification, **kwargs)
    new = inspection._report("b" * 40, classification, prior_verified=True, **kwargs)
    assert legacy.validate_inspection_report(storage.canonical(old)) == old
    assert inspection.validate_inspection_report(storage.canonical(new)) == new
    with pytest.raises(Exception):
        inspection.validate_inspection_report(storage.canonical(old))
    with pytest.raises(Exception):
        legacy.validate_inspection_report(storage.canonical(new))
    assert all(new[key] is False for key in FALSE_FLAGS)
    assert new["prior_provider_effects"] == "NOT_ESTABLISHED"


@pytest.mark.parametrize("classification", ["ABSENT", "ACKNOWLEDGED"])
def test_successful_metadata_requires_literal_native_failure_verification(classification):
    kwargs = {"revision": "e" * 40}
    if classification == "ACKNOWLEDGED":
        kwargs.update(head_digest="a" * 64, admission_digest="b" * 64)
    report = inspection._report("b" * 40, classification, prior_verified=True, **kwargs)
    for invalid in (False, 0, 1, "true", None):
        changed = dict(report, prior_native_artifact_verified=invalid)
        with pytest.raises(Exception):
            inspection.validate_inspection_report(storage.canonical(changed))


def test_real_native_failure_must_verify_before_absence_metadata(tmp_path, monkeypatch):
    evidence, state, calls = native_fixture(monkeypatch)

    class OrderedDataset(DatasetAPI):
        def dataset_info(self, *args, **kwargs):
            assert any(request.url.host == "metadata.blob.core.windows.net" for request in calls)
            return super().dataset_info(*args, **kwargs)

    api = OrderedDataset()
    report = inspect(tmp_path, api, evidence)
    assert report["classification"] == "ABSENT"
    assert report["prior_native_artifact_verified"] is True
    assert report["dataset_revision"] == api.revision
    assert api.calls == [("dataset_info", "main"), ("paths", storage.HEAD_PATH),
                         ("dataset_info", "main"), ("paths", storage.HEAD_PATH)]
    assert inspection.validate_inspection_report(storage.canonical(report)) == report
    assert all(report[key] is False for key in FALSE_FLAGS)


@pytest.mark.parametrize("defect", [
    "prior_source", "prior_attempt", "prior_event", "prior_conclusion", "incomplete_census",
    "duplicate_job", "qualification_failed", "effect_job_succeeded", "configuration_ran",
    "wrong_failed_step", "upload_failed", "artifact_id", "artifact_digest", "artifact_source",
    "artifact_size", "artifact_time", "expired", "archive_corrupt", "archive_oversize",
    "download_failed", "redirect_host", "redirect_userinfo",
    "swapped_skipped_job_ids", "swapped_skipped_job_names",
])
def test_unverified_prior_failure_never_reaches_private_dataset(tmp_path, monkeypatch, defect):
    evidence, state, _calls = native_fixture(monkeypatch)
    if defect == "prior_source": state["prior_run"]["head_sha"] = "a" * 40
    if defect == "prior_attempt": state["prior_run"]["run_attempt"] = 2
    if defect == "prior_event": state["prior_run"]["event"] = "workflow_dispatch"
    if defect == "prior_conclusion": state["prior_run"]["conclusion"] = "success"
    if defect == "incomplete_census": state["prior_jobs"]["total_count"] = 14
    if defect == "duplicate_job": state["prior_jobs"]["jobs"][-1] = copy.deepcopy(state["prior_jobs"]["jobs"][0])
    if defect == "qualification_failed": state["prior_jobs"]["jobs"][3]["conclusion"] = "failure"
    if defect == "effect_job_succeeded": state["prior_jobs"]["jobs"][-1]["conclusion"] = "success"
    if defect in {"swapped_skipped_job_ids", "swapped_skipped_job_names"}:
        first, second = state["prior_jobs"]["jobs"][4:6]
        key = "id" if defect == "swapped_skipped_job_ids" else "name"
        first[key], second[key] = second[key], first[key]
    steps = state["prior_jobs"]["jobs"][0]["steps"]
    if defect == "configuration_ran": steps[1]["conclusion"] = "success"
    if defect == "wrong_failed_step": steps[0]["name"] = "Unreviewed failure"
    if defect == "upload_failed": steps[2]["conclusion"] = "failure"
    if defect == "artifact_id": state["artifact"]["id"] += 1
    if defect == "artifact_digest": state["artifact"]["digest"] = "sha256:" + "a" * 64
    if defect == "artifact_source": state["artifact"]["workflow_run"]["head_sha"] = "a" * 40
    if defect == "artifact_size": state["artifact"]["size_in_bytes"] += 1
    if defect == "artifact_time": state["artifact"]["created_at"] = "2026-10-05T04:33:20Z"
    if defect == "expired": state["artifact"]["expired"] = True
    if defect == "archive_corrupt": state["archive"] = FAILURE_ARCHIVE[:-1] + b"x"
    if defect == "archive_oversize": state["archive"] = FAILURE_ARCHIVE + b"x"
    if defect == "download_failed": state["download_status"] = 403
    if defect == "redirect_host": state["location"] = "https://unreviewed.invalid/private"
    if defect == "redirect_userinfo": state["location"] = "https://user:secret@metadata.blob.core.windows.net/private"
    api = DatasetAPI()
    report = inspect(tmp_path, api, evidence)
    assert api.calls == []
    assert report["classification"] in {"INVALID", "UNAVAILABLE"}
    assert report["prior_native_artifact_verified"] is False
    assert report["dataset_revision"] is report["head_sha256"] is report["admission_sha256"] is None
    assert all(report[key] is False for key in FALSE_FLAGS)
    assert inspection.validate_inspection_report(storage.canonical(report)) == report


@pytest.mark.parametrize("defect", ["workflow_sha", "event", "attempt", "repository", "prior_source",
                                   "source_failed", "reconciliation_ran", "qualification_ran", "inactive", "stale_main"])
def test_unqualified_current_context_never_reaches_dataset(tmp_path, monkeypatch, defect):
    evidence, state, calls = native_fixture(monkeypatch)
    if defect == "workflow_sha": monkeypatch.setenv("GITHUB_WORKFLOW_SHA", "a" * 40)
    if defect == "event": evidence.event = "workflow_dispatch"; state["run"]["event"] = evidence.event
    if defect == "attempt": evidence.attempt = 2
    if defect == "repository": evidence.repository_id = 1
    if defect == "prior_source": evidence.source = SOURCE
    if defect == "source_failed": state["jobs"]["jobs"][1]["conclusion"] = "failure"
    if defect == "reconciliation_ran": state["jobs"]["jobs"][2]["conclusion"] = "success"
    if defect == "qualification_ran": state["jobs"]["jobs"][3]["conclusion"] = "success"
    if defect == "inactive": state["jobs"]["jobs"][0]["status"] = "completed"
    if defect == "stale_main": state["branch"]["commit"]["sha"] = "a" * 40
    api = DatasetAPI()
    report = inspect(tmp_path, api, evidence)
    assert api.calls == []
    assert not any("/actions/artifacts/" in request.url.path for request in calls)
    assert report["classification"] in {"INVALID", "UNAVAILABLE"}
    assert report["prior_native_artifact_verified"] is False


def test_acknowledged_62ca_metadata_never_reads_objects_or_admits_runtime(tmp_path, monkeypatch):
    evidence, _state, _calls = native_fixture(monkeypatch)
    record, head = bound_record()
    api = DatasetAPI(record, head)
    report = inspect(tmp_path, api, evidence)
    assert report["classification"] == "ACKNOWLEDGED"
    assert report["prior_native_artifact_verified"] is True
    assert report["head_sha256"] == storage.sha256(storage.canonical(head))
    assert report["admission_sha256"] == head["qualification_sha256"]
    assert {path for method, path in api.calls if method == "download"} == set(api.files)
    assert all(not path.startswith(storage.OBJECT_PREFIX) for method, path in api.calls)
    assert all(report[key] is False for key in FALSE_FLAGS)
    assert inspection.validate_inspection_report(storage.canonical(report)) == report


@pytest.mark.parametrize("defect", ["source", "run", "attempt", "job", "qualification_job", "source_receipt",
                                   "qualification", "artifact", "archive"])
def test_each_bound_admission_identity_is_mandatory(defect):
    record, head = bound_record()
    if defect == "source": head["source_revision"] = legacy.PRIOR_SOURCE
    if defect in {"run", "attempt", "job"}:
        record["source"][{"run": "run_id", "attempt": "run_attempt", "job": "job_id"}[defect]] += 1
    if defect == "qualification_job": record["qualification"]["source"]["job_id"] += 1
    if defect == "source_receipt": record["source"]["source_admission_sha256"] = "a" * 64
    if defect == "qualification": record["qualification"]["report_sha256"] = "a" * 64
    if defect == "artifact": record["qualification"]["artifact_id"] = inspection.FAILURE_ARTIFACT
    if defect == "archive": record["qualification"]["artifact_archive_sha256"] = inspection.FAILURE_ARCHIVE_SHA256
    head["qualification_sha256"] = storage.sha256(storage.canonical(record))
    with pytest.raises((inspection.InspectionInvalid, startup.AdmissionBlocked)):
        inspection._prior_binding(record, storage.Head("e" * 40, storage.canonical(head)),
                                  storage.sha256(storage.canonical(None)))


@pytest.mark.parametrize("method", ["pause_space", "restart_space", "batch_bucket_files", "create_commit",
                                    "download_bucket_files", "get_bucket_paths_info", "add_space_variable", "get_space_secrets"])
def test_fixed_reader_exposes_no_object_or_mutation_method(method):
    reader = inspection.ReadOnlyDataset(DatasetAPI(), lambda: None, time.monotonic() + 60)
    with pytest.raises(AttributeError):
        getattr(reader, method)


def test_fixed_reader_rejects_arbitrary_object_paths_before_sdk(tmp_path):
    api = DatasetAPI()
    reader = inspection.ReadOnlyDataset(api, lambda: None, time.monotonic() + 60)
    path = storage.OBJECT_PREFIX + "/unreviewed"
    with pytest.raises(inspection.InspectionInvalid):
        reader.get_paths_info(storage.DATASET, [path], repo_type="dataset", revision="e" * 40)
    with pytest.raises(inspection.InspectionInvalid):
        reader.hf_hub_download(storage.DATASET, filename=path, repo_type="dataset", revision="e" * 40,
                               local_dir=tmp_path, cache_dir=tmp_path)
    assert api.calls == []
