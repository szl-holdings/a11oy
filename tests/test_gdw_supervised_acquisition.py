# SPDX-License-Identifier: Apache-2.0
"""Offline native-contract controls; synthetic successor context grants no authority."""
import base64
import copy
import hashlib
import io
import time
import zipfile
from types import SimpleNamespace

import httpx
import pytest

import gdw_durable_storage as storage
from scripts import gdw_acquisition_evidence as native
from scripts import reconcile_gdw_supervised_acquisition as supervised

# Exact public metadata-only GitHub artifact11365342348, not private-store bytes.
ARCHIVE = base64.b64decode(
    "UEsDBBQACAAIAHeVRV0AAAAAAAAAAAAAAAAYAAAAZ2R3LWFydGlmYWN0LXRyaWFnZS5qc29unVRNj9s2EL33Z/DstOK35JvXq7QuNvbCqwTNiRiSQy8DreRQtNNNsP+9kO11nM0WBXoRBM6Q82bee/ONQMoxgMsGQ0CXTW8HTHvIse/I9BuBtjUJM8QOvUn9l8HsoY0eMnoyzWmHE+Kg84cTs+vcPXSbi1ALwxBDdKf3yHJl6r9u63lTX5vV1Z/1vLkzt+v6rl42ZtaYdT27Ns3iXU0mBP/eosvoTW8/jcBcv+symTImfo4NmM1wD0wqMiUaWOkkD6CERsUrrqVTUBWeIxdYVgG1sI4VhQglVdTKwEtwuuK8oBYFIxNyH4fcp+igNV9SzJgM5Jyi3Z3baEx918yubhZ3f9TXZEIe4jDEbvMa2ONE/wWsCJI7D7R0zAIUruBSWCtDBRydRYmeMrDCl0iphVJzxwKlVFFWMFsJSSZkm3DALr8oXYyBfh89plNkMGHXto+XBAZoB7xIPDQ7mC2m0KeHc8bTSPI27xKazztoLwm9Wf2+mM9uzHy1bBbL94vmo/lQrxdvF4epnG5506e4iR20w3eNGL9L48RevHgUjsdt2z8+jG2Bf4j5Eq2PsOn6IUdnXO+RTMlBNqvlzUezurqr1x9mzWK1NPPVu9ubuqn/H5+YwUMGM2SwLT6DTQhncW9T7JMB93kXhzg+ZCC5+7jH7+x6VhUBVGWD5AU67hzTHpwLvvCAgfKqEIUSjgUOWgbNAzLrNHVMUgnBk9ernBwbPZlSypkUSgspX8tNuO3ThdyCQMVLX1jNQ6kkeC80UuW0R2l9CKEKlcPSKisLiShQebSBFlXpLZfAzoA+9fZUnyqqtCoF5c+xDvI4hfMI95hiiPhicGfRHRfP8CoNx9S060bC8GGbyZReno4QuGaKl6oqWPkcGvpdcmgS7uNwZFgxB8JTWaiAlQylRR8YFTyM/6pwulTeeS3ONYcMm1Fbs3WzeDubN+b2/dXNYn6Q1o9J4zePqVer98vr2fqjqZdNvX7Gvx83o30cfXVk4wfjHcP3CP48r3HtHg6OxnYHFFfjiiQTctFS8FKXSoaKMVEopnQlNKsAnXdFybStCl0pAEee/tvhE3Ky4ehLyGBhwPMSG6uCN7bfdR7SI5mSC2slHK2FP9s0YU6Prxy/4PI7i1xqrblWYkIGd48PQKZk+Nr+uvFf3jxr/s2IpO/axzc5Rdjgb/tRkj/THaiSHFhVlKESArm22mOpPXDFFXeu8krRivLx8om94+qor8nTL/8AUEsHCJ8XsYyiAwAAFgcAAFBLAQItAxQACAAIAHeVRV2fF7GMogMAABYHAAAYAAAAAAAAAAAAIACkgQAAAABnZHctYXJ0aWZhY3QtdHJpYWdlLmpzb25QSwUGAAAAAAEAAQBGAAAA6AMAAAAA"
)


def fixture(monkeypatch, job_key=supervised.RECONCILIATION_JOB_KEY):
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": native.REPOSITORY,
        "GITHUB_REPOSITORY_ID": str(supervised.REPOSITORY_ID), "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": "a" * 40, "GITHUB_WORKFLOW_SHA": "a" * 40,
        "GITHUB_RUN_ID": "900", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": native.REPOSITORY + "/" + native.WORKFLOW + "@refs/heads/main",
        "GITHUB_EVENT_NAME": "push", "GITHUB_JOB": job_key, "GH_TOKEN": "synthetic-token"}
    monkeypatch.setenv("GITHUB_WORKFLOW_SHA", env["GITHUB_SHA"])
    run = {"id": 900, "run_attempt": 1, "workflow_id": 700, "path": native.WORKFLOW,
        "event": "push", "head_sha": env["GITHUB_SHA"], "head_branch": "main",
        "repository": {"id": supervised.REPOSITORY_ID, "full_name": native.REPOSITORY},
        "head_repository": {"id": supervised.REPOSITORY_ID},
        "status": "in_progress", "conclusion": None, "run_started_at": "2026-10-05T18:44:00Z"}
    job = {"id": 901, "name": supervised.JOB_NAMES[job_key], "run_id": 900, "run_attempt": 1,
        "head_sha": env["GITHUB_SHA"], "status": "in_progress", "conclusion": None,
        "started_at": "2026-10-05T18:44:01Z", "completed_at": None}
    jobs = {"total_count": 2, "jobs": [job, dict(job, id=902, name=native.SOURCE_JOB,
        status="completed", conclusion="success", completed_at="2026-10-05T18:44:01Z")]}
    previous_run = dict(copy.deepcopy(run), id=supervised.INSPECTION_RUN, head_sha=supervised.PARENT_SOURCE,
        workflow_id=supervised.INSPECTION_WORKFLOW_ID, path=supervised.INSPECTION_WORKFLOW,
        event="workflow_dispatch", status="completed", conclusion="success", run_started_at="2026-10-05T18:40:52Z")
    previous_job = {"id": supervised.INSPECTION_JOB, "run_id": supervised.INSPECTION_RUN,
        "run_attempt": 1, "head_sha": supervised.PARENT_SOURCE, "name": "triage",
        "status": "completed", "conclusion": "success", "started_at": "2026-10-05T18:41:23Z",
        "completed_at": "2026-10-05T18:43:50Z", "steps": [
            {"name": "Reconcile exact retained artifact objects without provider mutation", "status": "completed",
             "conclusion": "success", "started_at": "2026-10-05T18:41:31Z", "completed_at": "2026-10-05T18:43:46Z"},
            {"name": "Retain only the closed diagnostic record", "status": "completed", "conclusion": "success",
             "started_at": "2026-10-05T18:43:46Z", "completed_at": "2026-10-05T18:43:47Z"}]}
    previous_jobs = {"total_count": 2, "jobs": [previous_job,
        dict(previous_job, id=supervised.INSPECTION_CONTRACT_JOB, name="contract",
             started_at="2026-10-05T18:40:57Z", completed_at="2026-10-05T18:41:20Z", steps=[{
                 "name": "Prove read-only triage boundaries with actual disposable databases",
                 "status": "completed", "conclusion": "success"}])]}
    meta = {"id": supervised.ARTIFACT_ID, "expired": False,
        "name": f"gdw-artifact-readonly-{supervised.INSPECTION_RUN}-1", "size_in_bytes": 1092,
        "digest": "sha256:" + supervised.ARCHIVE_SHA256, "created_at": "2026-10-05T18:43:47Z",
        "workflow_run": {"id": supervised.INSPECTION_RUN, "head_sha": supervised.PARENT_SOURCE,
            "head_branch": "main", "repository_id": supervised.REPOSITORY_ID,
            "head_repository_id": supervised.REPOSITORY_ID}}
    commit = {"sha": env["GITHUB_SHA"], "parents": [{"sha": supervised.PARENT_SOURCE}],
        "verification": {"verified": True, "reason": "valid"}}
    branch = {"name": "main", "protected": True, "commit": {"sha": env["GITHUB_SHA"]}}
    state = {"run": run, "latest_run": copy.deepcopy(run), "jobs": jobs, "prior_run": previous_run,
        "prior_latest_run": copy.deepcopy(previous_run),
        "prior_jobs": previous_jobs, "meta": meta, "commit": commit, "branch": branch,
        "listing": {"total_count": 1, "workflow_runs": [copy.deepcopy(run)]}, "archive": ARCHIVE,
        "location": "https://metadata.blob.core.windows.net/fixed?signature=synthetic", "object_status": 200}
    calls = []
    def transport(request):
        calls.append(request)
        assert request.method == "GET"
        if request.url.host == "metadata.blob.core.windows.net":
            assert "authorization" not in request.headers
            return httpx.Response(state["object_status"], content=state["archive"])
        assert request.url.host == "api.github.com"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        path = request.url.path
        if path.endswith("/zip"): return httpx.Response(302, headers={"location": state["location"]})
        if "/actions/artifacts/" in path: return httpx.Response(200, json=state["meta"])
        if "/git/commits/" in path: return httpx.Response(200, json=state["commit"])
        if "/branches/main" in path: return httpx.Response(200, json=state["branch"])
        if "/actions/workflows/" in path:
            assert set(request.url.params) == {"event", "head_sha", "per_page"}
            return httpx.Response(200, json=state["listing"])
        prior = str(supervised.INSPECTION_RUN) in path
        if path.endswith("/jobs"): return httpx.Response(200, json=state["prior_jobs" if prior else "jobs"])
        if prior: return httpx.Response(200, json=state["prior_run" if "/attempts/" in path else "prior_latest_run"])
        return httpx.Response(200, json=state["run" if "/attempts/" in path else "latest_run"])
    client = httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=False)
    evidence = native.NativeEvidence(env, time.monotonic() + 60, client=client)
    return evidence, state, calls


@pytest.mark.parametrize("job_key", tuple(supervised.JOB_NAMES))
def test_real_native_reader_binds_exact_archived_inspection_and_unique_successor(monkeypatch, job_key):
    evidence, state, calls = fixture(monkeypatch, job_key)
    assert len(ARCHIVE) == 1092 and hashlib.sha256(ARCHIVE).hexdigest() == supervised.ARCHIVE_SHA256
    result = supervised.verify_native_prerequisite(evidence)
    assert result == {"source_revision": "a" * 40, "run_id": 900, "run_attempt": 1,
        "job_id": 901, "job_key": job_key}
    assert all(call.method == "GET" for call in calls)
    assert len([call for call in calls if "/actions/workflows/" in call.url.path]) == 2
    assert len([call for call in calls if call.url.path.endswith("/runs/900")]) == 2


def test_exact_native_archive_has_the_complete_closed_triage_report():
    with zipfile.ZipFile(io.BytesIO(ARCHIVE)) as archive:
        assert archive.namelist() == ["gdw-artifact-triage.json"]
        raw = archive.read("gdw-artifact-triage.json")
    assert len(raw) == supervised.REPORT_BYTES == 1814
    assert hashlib.sha256(raw).hexdigest() == supervised.REPORT_SHA256
    assert supervised.validate_triage_report(raw) == supervised._expected_triage_report()
    observed = supervised.validate_triage_report(raw)
    assert observed["artifact_effect_observation"]["expected_object_count"] == 224
    assert observed["prior_provider_effects"] == observed["historical_writer_attribution"] == "NOT_ESTABLISHED"
    assert all(observed[key] is False for key in (
        "provider_writes_performed", "retry_admitted", "restore_admitted", "deployment_admitted"))


def triage_fields():
    fields = []
    for key, value in supervised._expected_triage_report().items():
        fields.append((key,))
        if isinstance(value, dict):
            fields.extend((key, child) for child in value)
    return fields


@pytest.mark.parametrize("field", triage_fields())
@pytest.mark.parametrize("defect", ["missing", "changed"])
def test_every_historical_observation_field_is_closed_even_if_digest_is_repinned(monkeypatch, field, defect):
    record = supervised._expected_triage_report()
    target = record if len(field) == 1 else record[field[0]]
    key = field[-1]
    if defect == "missing":
        del target[key]
    else:
        old = target[key]
        target[key] = (int(old) if type(old) is bool else
                       old + 1 if type(old) is int else {} if type(old) is dict else "UNQUALIFIED")
    raw = storage.canonical(record)
    # This isolates the closed shape/claims gate from the independent immutable
    # byte identity. Editing a pin must not silently broaden accepted evidence.
    monkeypatch.setattr(supervised, "REPORT_BYTES", len(raw))
    monkeypatch.setattr(supervised, "REPORT_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(supervised.SupervisedBlocked):
        supervised.validate_triage_report(raw)


@pytest.mark.parametrize("defect", ["extra", "duplicate", "noncanonical", "array", "invalid_json"])
def test_triage_report_never_accepts_private_extras_or_loose_encoding(monkeypatch, defect):
    report = supervised._expected_triage_report()
    if defect == "extra": report["private_payload"] = "PRIVATE_CANARY"
    raw = storage.canonical(report)
    if defect == "duplicate": raw = raw[:-2] + b',"state":"OBSERVED"}\n'
    if defect == "noncanonical": raw = b" " + raw
    if defect == "array": raw = b"[]\n"
    if defect == "invalid_json": raw = b"{invalid}\n"
    monkeypatch.setattr(supervised, "REPORT_BYTES", len(raw))
    monkeypatch.setattr(supervised, "REPORT_SHA256", hashlib.sha256(raw).hexdigest())
    with pytest.raises(Exception): supervised.validate_triage_report(raw)


@pytest.mark.parametrize("defect", ["parent", "two_parents", "unsigned", "unprotected", "not_main",
    "workflow_sha", "workflow_dispatch", "attempt", "latest_attempt", "latest_cancelled", "other_job",
    "job_finished", "source_job_failed", "duplicate_run", "incomplete_census", "wrong_census_run",
    "wrong_census_source", "wrong_census_branch", "wrong_census_event", "wrong_census_repo", "workflow_id",
    "prior_run", "prior_attempt", "prior_latest_attempt", "prior_latest_failed", "prior_event", "prior_workflow",
    "prior_workflow_id", "prior_job", "prior_census", "prior_contract_failed", "prior_extra_job",
    "prior_upload_failed", "prior_observation_failed", "prior_missing_contract_step", "prior_duplicate_step",
    "prior_step_order", "prior_job_source", "prior_job_attempt", "prior_job_name", "prior_job_status",
    "artifact_id", "artifact_digest", "artifact_run", "artifact_time", "artifact_expired", "artifact_name",
    "artifact_size", "archive_corrupt", "archive_oversize", "redirect_host", "redirect_credentials", "object_redirect"])
def test_unqualified_native_or_artifact_inputs_cannot_pass(monkeypatch, defect):
    evidence, state, calls = fixture(monkeypatch)
    if defect == "parent": state["commit"]["parents"][0]["sha"] = "f" * 40
    if defect == "two_parents": state["commit"]["parents"] *= 2
    if defect == "unsigned": state["commit"]["verification"]["verified"] = False
    if defect == "unprotected": state["branch"]["protected"] = False
    if defect == "not_main": state["branch"]["commit"]["sha"] = "b" * 40
    if defect == "workflow_sha": monkeypatch.setenv("GITHUB_WORKFLOW_SHA", "b" * 40)
    if defect == "workflow_dispatch": evidence.event = "workflow_dispatch"
    if defect == "attempt": evidence.attempt = 2
    if defect == "latest_attempt": state["latest_run"]["run_attempt"] = 2
    if defect == "latest_cancelled": state["latest_run"].update(status="completed", conclusion="cancelled")
    if defect == "other_job": evidence.executing_job = "manual-prerequisites"
    if defect == "job_finished": state["jobs"]["jobs"][0]["status"] = "completed"
    if defect == "source_job_failed": state["jobs"]["jobs"][1]["conclusion"] = "failure"
    if defect == "duplicate_run": state["listing"]["workflow_runs"] *= 2; state["listing"]["total_count"] = 2
    if defect == "incomplete_census": state["listing"]["total_count"] = 2
    census = state["listing"]["workflow_runs"][0]
    if defect == "wrong_census_run": census["id"] += 1
    if defect == "wrong_census_source": census["head_sha"] = "b" * 40
    if defect == "wrong_census_branch": census["head_branch"] = "other"
    if defect == "wrong_census_event": census["event"] = "workflow_dispatch"
    if defect == "wrong_census_repo": census["head_repository"]["id"] += 1
    if defect == "workflow_id": census["workflow_id"] += 1
    if defect == "prior_run": state["prior_run"]["id"] += 1
    if defect == "prior_attempt": state["prior_run"]["run_attempt"] = 2
    if defect == "prior_latest_attempt": state["prior_latest_run"]["run_attempt"] = 2
    if defect == "prior_latest_failed": state["prior_latest_run"]["conclusion"] = "failure"
    if defect == "prior_event": state["prior_run"]["event"] = "push"
    if defect == "prior_workflow": state["prior_run"]["path"] = native.WORKFLOW
    if defect == "prior_workflow_id": state["prior_run"]["workflow_id"] += 1
    if defect == "prior_job": state["prior_jobs"]["jobs"][0]["id"] += 1
    if defect == "prior_census": state["prior_jobs"]["total_count"] = 3
    if defect == "prior_contract_failed": state["prior_jobs"]["jobs"][1]["conclusion"] = "failure"
    if defect == "prior_extra_job": state["prior_jobs"]["jobs"].append(copy.deepcopy(state["prior_jobs"]["jobs"][0]))
    if defect == "prior_upload_failed": state["prior_jobs"]["jobs"][0]["steps"][1]["conclusion"] = "failure"
    if defect == "prior_observation_failed": state["prior_jobs"]["jobs"][0]["steps"][0]["conclusion"] = "failure"
    if defect == "prior_missing_contract_step": state["prior_jobs"]["jobs"][1]["steps"][0]["name"] = "other"
    if defect == "prior_duplicate_step": state["prior_jobs"]["jobs"][0]["steps"] *= 2
    if defect == "prior_step_order": state["prior_jobs"]["jobs"][0]["steps"][1]["started_at"] = "2026-10-05T18:41:32Z"
    if defect == "prior_job_source": state["prior_jobs"]["jobs"][0]["head_sha"] = "b" * 40
    if defect == "prior_job_attempt": state["prior_jobs"]["jobs"][0]["run_attempt"] = 2
    if defect == "prior_job_name": state["prior_jobs"]["jobs"][0]["name"] = "other"
    if defect == "prior_job_status": state["prior_jobs"]["jobs"][0]["status"] = "in_progress"
    if defect == "artifact_id": state["meta"]["id"] += 1
    if defect == "artifact_digest": state["meta"]["digest"] = "sha256:" + "a" * 64
    if defect == "artifact_run": state["meta"]["workflow_run"]["id"] += 1
    if defect == "artifact_time": state["meta"]["created_at"] = "2026-10-05T00:25:00Z"
    if defect == "artifact_expired": state["meta"]["expired"] = True
    if defect == "artifact_name": state["meta"]["name"] = "other"
    if defect == "artifact_size": state["meta"]["size_in_bytes"] += 1
    if defect == "archive_corrupt": state["archive"] = ARCHIVE[:-1] + b"x"
    if defect == "archive_oversize": state["archive"] = ARCHIVE + b"x"
    if defect == "redirect_host": state["location"] = "https://untrusted.invalid/signed"
    if defect == "redirect_credentials": state["location"] = "https://user:pass@metadata.blob.core.windows.net/signed"
    if defect == "object_redirect": state["object_status"] = 302
    with pytest.raises(supervised.SupervisedBlocked) as error: supervised.verify_native_prerequisite(evidence)
    assert str(error.value) in supervised.CODES


class ReadAPI:
    endpoint = storage.ENDPOINT

    def __init__(self):
        self.calls = []; self.private = True; self.revision = supervised.DATASET_REVISION
        self.present = False; self.changed_after_first = False; self.fail = False

    def dataset_info(self, repo_id, *, revision, expand):
        assert repo_id == storage.DATASET and revision == "main" and expand == ["sha", "private", "resourceGroup"]
        self.calls.append("info")
        if self.fail: raise RuntimeError("PRIVATE_TRANSPORT_CANARY")
        return {"id": storage.DATASET, "private": self.private,
            "sha": "b" * 40 if self.changed_after_first and len(self.calls) > 2 else self.revision}

    def get_paths_info(self, repo_id, paths, *, repo_type, revision):
        assert repo_id == storage.DATASET and paths == [storage.HEAD_PATH]
        assert repo_type == "dataset" and revision == supervised.DATASET_REVISION
        self.calls.append("paths")
        return [{}] if self.present else []

    def __getattr__(self, name): pytest.fail("unadmitted provider method: " + name)


def test_sdk_neutral_absence_adapter_needs_only_source_owner_callback():
    api = ReadAPI(); ownership = []
    owner = SimpleNamespace(source="a" * 40, require_current_main=lambda: ownership.append("current"))
    report = supervised.require_expected_absent(api, owner, time.monotonic() + 10)
    assert api.calls == ["info", "paths", "info", "paths"] and len(ownership) == 5
    assert report["state"] == "EXPECTED_HEAD_ABSENT" and report["provider_writes_performed"] is False


@pytest.mark.parametrize("defect", ["present", "private", "different_revision", "changed", "transport", "owner", "deadline", "source"])
def test_absence_is_never_inferred_after_change_or_unavailable_read(defect):
    api = ReadAPI(); owner = SimpleNamespace(source="a" * 40, require_current_main=lambda: None)
    deadline = time.monotonic() + 10
    if defect == "present": api.present = True
    if defect == "private": api.private = False
    if defect == "different_revision": api.revision = "b" * 40
    if defect == "changed": api.changed_after_first = True
    if defect == "transport": api.fail = True
    if defect == "owner": owner.require_current_main = lambda: (_ for _ in ()).throw(ValueError("PRIVATE_CANARY"))
    if defect == "deadline": deadline = 0
    if defect == "source": owner.source = supervised.PARENT_SOURCE
    with pytest.raises(supervised.SupervisedBlocked) as error: supervised.require_expected_absent(api, owner, deadline)
    assert str(error.value) == "EXPECTED_ABSENCE_UNVERIFIED"


def test_success_report_is_a_bounded_prewrite_prerequisite_only():
    context = {"source_revision": "a" * 40, "run_id": 900, "run_attempt": 1, "job_id": 901,
        "job_key": supervised.RECONCILIATION_JOB_KEY}
    report = supervised._report(context)
    assert supervised.validate_reconciliation_report(storage.canonical(report)) == report
    assert report["restore_admitted"] is report["deployment_admitted"] is report["provider_writes_performed"] is False
    assert report["retry_admitted"] is report["provider_objects_verified"] is False
    assert report["inspection_expected_object_count"] == report["inspection_missing_object_count"] == 224
    assert report["inspection_present_object_count"] == 0
    assert report["prior_provider_effects"] == report["historical_writer_attribution"] == "NOT_ESTABLISHED"


@pytest.mark.parametrize("defect", ["extra", "bool_id", "int_bool", "held", "source", "job", "prior", "revision",
    "retry", "attribution", "objects_verified", "expected_set", "count", "duplicate", "noncanonical", "overflow"])
def test_parent_never_accepts_loose_or_broader_authority_report(defect):
    report = supervised._report({"source_revision": "a" * 40, "run_id": 900, "run_attempt": 1,
        "job_id": 901, "job_key": supervised.RECONCILIATION_JOB_KEY})
    if defect == "extra": report["payload"] = "PRIVATE_CANARY"
    if defect == "bool_id": report["run_attempt"] = True
    if defect == "int_bool": report["provider_writes_performed"] = 0
    if defect == "held": report["state"] = "HELD"
    if defect == "source": report["source_revision"] = supervised.PARENT_SOURCE
    if defect == "job": report["job_key"] = "manual-prerequisites"
    if defect == "prior": report["inspection_run_id"] += 1
    if defect == "revision": report["dataset_revision"] = "b" * 40
    if defect == "retry": report["retry_admitted"] = True
    if defect == "attribution": report["historical_writer_attribution"] = "VERIFIED"
    if defect == "objects_verified": report["provider_objects_verified"] = True
    if defect == "expected_set": report["inspection_expected_object_set_sha256"] = "b" * 64
    if defect == "count": report["inspection_expected_object_count"] += 1
    raw = storage.canonical(report)
    if defect == "duplicate": raw = raw[:-2] + b',"state":"PREREQUISITE_VERIFIED"}\n'
    if defect == "noncanonical": raw = raw.rstrip()
    if defect == "overflow": raw = raw.replace(b'"PREREQUISITE_VERIFIED"', b'1e999')
    with pytest.raises(Exception): supervised.validate_reconciliation_report(raw)


def test_native_execution_never_constructs_hf_api_before_all_native_preconditions(monkeypatch, tmp_path):
    tmp_path.chmod(0o700)
    sentinel = SimpleNamespace()
    monkeypatch.setattr(native, "NativeEvidence", lambda *_: sentinel)
    monkeypatch.setattr(supervised, "verify_native_prerequisite",
        lambda evidence: (_ for _ in ()).throw(supervised.SupervisedBlocked("NATIVE_RUN_NOT_UNIQUE")))
    monkeypatch.setattr(storage, "_hub_api", lambda *_: pytest.fail("HF constructed before native prerequisite"))
    with pytest.raises(supervised.SupervisedBlocked):
        supervised.execute_native_reconciliation(tmp_path, time.monotonic() + 60)


@pytest.mark.parametrize("expired_callback", [1, 2, 3, 4, 5])
def test_each_owner_callback_must_finish_inside_the_absence_deadline(monkeypatch, expired_callback):
    clock = [0.0]; calls = []
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    def owner_check():
        calls.append("current")
        if len(calls) == expired_callback: clock[0] = 11.0
    owner = SimpleNamespace(source="a" * 40, require_current_main=owner_check)
    api = ReadAPI()
    with pytest.raises(supervised.SupervisedBlocked, match="EXPECTED_ABSENCE_UNVERIFIED"):
        supervised.require_expected_absent(api, owner, 10.0)
    assert len(api.calls) == expired_callback - 1


def test_native_result_validation_cannot_run_past_the_deadline(monkeypatch, tmp_path):
    tmp_path.chmod(0o700)
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    context = {"source_revision": "a" * 40, "run_id": 900, "run_attempt": 1,
        "job_id": 901, "job_key": supervised.RECONCILIATION_JOB_KEY}
    monkeypatch.setattr(native, "NativeEvidence", lambda *_: object())
    monkeypatch.setattr(supervised, "verify_native_prerequisite", lambda _: context)
    monkeypatch.setattr(storage, "_hub_api", lambda _: object())
    monkeypatch.setattr(supervised, "require_expected_absent", lambda *_: None)
    validate = supervised.validate_reconciliation_report
    def slow_validate(raw):
        result = validate(raw); clock[0] = 11.0; return result
    monkeypatch.setattr(supervised, "validate_reconciliation_report", slow_validate)
    with pytest.raises(storage.StorageBlocked): supervised.execute_native_reconciliation(tmp_path, 10.0)
