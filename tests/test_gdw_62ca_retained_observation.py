# SPDX-License-Identifier: Apache-2.0
"""Offline immutable safe-record verification; no provider request or private data."""
import ast
import base64
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import time
import zipfile

import httpx
import pytest

from scripts import gdw_acquisition_evidence as native
from scripts import reconcile_gdw_62ca_retained_observation as observation

# Exact public-safe artifact11349341865: one closed JSON record, never SQLite or
# retained artifact payloads. Fixed bytes let these tests run without the estate.
SAFE_ARCHIVE = base64.b64decode(
    "UEsDBBQACAAIABptRV0AAAAAAAAAAAAAAAAYAAAAZ2R3LWFydGlmYWN0LXRyaWFnZS5qc29unVRNb+M2EL33Z/DstOKnJN9sR9u6yNqBoyyaEzEkhw4XiuSlaKfeRf57ITtxvEmKAr0YwsyY82bee/ODQEzBg00avUebdGd6jDtIoWvJ+AeBptERE4QWnY7dY6930AQHCR0Zp7jFEbHQukNEb1t7D+36LNVA3wcf7PN7ZLHU1V/X1ayuLvVy+mc1q2/09aq6qRa1ntR6VU0udT3/XJERwb83aBM63ZmvAzDbbdtExoyJ97kek+7vgUlFxiQHVljJPSiRo+Ilz6VVUGaOIxdYlB5zYSzLMuELqqiRnhdg85LzjBoUjIzIfehTF4OFRj/GkDBqSCkGsz2NUevqpp5Mr+Y3f1SXZEQeQt+Hdv0R2ONG/wWs8JJbB7SwzABkNuNSGCN9CRytQYmOMjDCFUipgSLnlnlKqaIsY6YUkozIJmKPbXrTOhsS3S44jM+ZXvtt0+zPCfTQ9HhWeBi21xuMvosPp4qngeRN2kbU37bQnBN6tfx9Pptc6dlyUc8Xt/P6Tn+pVvNP88NWnv/ldBfDOrTQ9K8a0W4bh429efEoHIebpts/DGOBewjpHK0LsG67PgWrbeeQjMlBNsvF1Z1eTm+q1ZdJPV8u9Gz5+fqqqqv/xycmcJBA9wlMgy9gI8JJ3JsYuqjBftuGPgwPaYj2PuzwlV3HysyDKo2XPEPLrWW5A2u9yxygp7zMRKaEZZ5DLn3OPTJjc2qZpBK8Ix93eXZscGRMKWdSqFxI+VFtxE0Xz+TmBSpeuMzk3BdKgnMiR6ps7lAa570vfWmxMMrITCIKVA6Np1lZOMMlsBOgr5157k8VVbkqBOUvuRbSsIXTCncYgw/4ZnEn0R0PT/8hDcfSuG0HwvBhk8iYnkcHCDxniheqzFjxkuq7bbSoI+5Cf2RYMQvCUZkpj6X0hUHnGRXcD98qs3mhnHW5OPXsE6wHbU1W9fzTZFbr69vp1Xx2kNbPRcNvGkqny9vF5WR1p6tFXa1e8O+Gy2j2g6+ObPxkvGP6HsGd9jWc3UPgaGx7QDEdTiQZkbORvHTGWUBgXDnDTeaYNIUrrMfCKcFVaZh0eUGe/tvhI/Jsw8GXkMBAj6cjNnQFp023bR3EPRmTM2tFHKyF720aMcX9B+E3XL6yyGnBhWCKjUhv7/EByJj035tf1+7x4kXzFwOSrm32FykGWONvu0GS7+mmhuW5FIU0mSypVIopJmwp8iwT1hVFbhi1Xg4Ge2HveDqqS/L0yz9QSwcIaA869aEDAAAWBwAAUEsBAi0DFAAIAAgAGm1FXWgPOvWhAwAAFgcAABgAAAAAAAAAAAAgAKSBAAAAAGdkdy1hcnRpZmFjdC10cmlhZ2UuanNvblBLBQYAAAAAAQABAEYAAADnAwAAAAA="
)
with zipfile.ZipFile(io.BytesIO(SAFE_ARCHIVE)) as archive:
    SAFE_REPORT = archive.read("gdw-artifact-triage.json")


@pytest.fixture(autouse=True)
def fixed_observation_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, _zone=None):
            return datetime(2026, 10, 5, 14, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(observation, "datetime", Clock)


def fixture_metadata():
    run = {"id": observation.RUN, "run_attempt": 1, "workflow_id": 300,
        "path": observation.WORKFLOW, "event": "workflow_dispatch", "head_branch": "main",
        "head_sha": observation.SOURCE, "status": "completed", "conclusion": "success",
        "created_at": "2026-10-05T13:38:13Z", "run_started_at": "2026-10-05T13:38:14Z",
        "updated_at": "2026-10-05T13:40:56Z",
        "repository": {"id": observation.REPOSITORY_ID, "full_name": native.REPOSITORY},
        "head_repository": {"id": observation.REPOSITORY_ID}}
    jobs = []
    for identifier, name, started, ended, steps in (
        (observation.CONTRACT_JOB, "contract", "13:38:15", "13:38:33",
            ["Prove read-only triage boundaries with actual disposable databases"]),
        (observation.PRODUCER_JOB, "triage", "13:38:35", "13:40:55",
            ["Reconcile exact retained artifact objects without provider mutation",
             "Retain only the closed diagnostic record"]),
    ):
        jobs.append({"id": identifier, "name": name, "run_id": observation.RUN, "run_attempt": 1,
            "head_sha": observation.SOURCE, "status": "completed", "conclusion": "success",
            "started_at": "2026-10-05T" + started + "Z", "completed_at": "2026-10-05T" + ended + "Z",
            "steps": [{"name": step, "status": "completed", "conclusion": "success"} for step in steps]})
    return {"run": run, "current": copy.deepcopy(run), "jobs": {"total_count": 2, "jobs": jobs},
        "commit": {"sha": observation.SOURCE, "verification": {"verified": True, "reason": "valid"}},
        "artifact": {"id": observation.ARTIFACT, "name": f"gdw-artifact-readonly-{observation.RUN}-1",
            "expired": False, "size_in_bytes": 1091, "digest": "sha256:" + observation.ARCHIVE_SHA256,
            "created_at": "2026-10-05T13:40:54Z", "expires_at": "2027-01-03T13:38:14Z",
            "workflow_run": {"id": observation.RUN, "head_sha": observation.SOURCE,
                "head_branch": "main", "repository_id": observation.REPOSITORY_ID,
                "head_repository_id": observation.REPOSITORY_ID}},
        "archive": SAFE_ARCHIVE, "redirect": "https://safe.actions.githubusercontent.com/closed.zip"}


def native_reader(state):
    calls = []
    current_reads = [0]
    def handle(request):
        assert request.method == "GET"
        calls.append((request.url.host, request.url.path))
        if request.url.host != "api.github.com":
            assert request.url.host == "safe.actions.githubusercontent.com"
            assert "Authorization" not in request.headers
            return httpx.Response(200, content=state["archive"])
        suffix = str(request.url).split(f"/repos/{native.REPOSITORY}/", 1)[1]
        if suffix == f"actions/artifacts/{observation.ARTIFACT}/zip":
            return httpx.Response(302, headers={"location": state["redirect"]})
        if suffix == f"actions/runs/{observation.RUN}":
            current_reads[0] += 1
            value = state.get("late_current", state["current"]) if current_reads[0] > 1 else state["current"]
        else:
            key = {f"actions/runs/{observation.RUN}/attempts/1": "run",
                f"actions/runs/{observation.RUN}/attempts/1/jobs?per_page=100": "jobs",
                f"git/commits/{observation.SOURCE}": "commit",
                f"actions/artifacts/{observation.ARTIFACT}": "artifact"}[suffix]
            value = state[key]
        return httpx.Response(200, json=value)
    environ = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": native.REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_WORKFLOW_REF": native.REPOSITORY + "/" + native.WORKFLOW + "@refs/heads/main",
        "GITHUB_SHA": "b" * 40, "GITHUB_RUN_ID": "900", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_REPOSITORY_ID": str(observation.REPOSITORY_ID), "GITHUB_EVENT_NAME": "push",
        "GH_TOKEN": "synthetic-read-token"}
    client = httpx.Client(transport=httpx.MockTransport(handle), follow_redirects=False, trust_env=False)
    return native.NativeEvidence(environ, time.monotonic() + 30, client=client), calls


def test_exact_safe_report_and_archive_are_independently_pinned():
    assert len(SAFE_ARCHIVE) == 1091 and hashlib.sha256(SAFE_ARCHIVE).hexdigest() == observation.ARCHIVE_SHA256
    assert len(SAFE_REPORT) == 1814 and hashlib.sha256(SAFE_REPORT).hexdigest() == observation.REPORT_SHA256
    report = observation.validate_observation_report(SAFE_REPORT)
    assert report["prior_run_id"] == 37263869028
    assert report["artifact_effect_observation"]["missing_object_count"] == 224


def test_real_native_reader_uses_only_fixed_gets_and_never_grants_authority():
    reader, calls = native_reader(fixture_metadata())
    try:
        result = observation.verify_retained_observation(reader)
    finally:
        reader.client.close()
    assert result["state"] == "OBSERVATION_VERIFIED" and result["evidence_class"] == "REPORTED"
    assert result["prior_provider_effects"] == result["historical_writer_attribution"] == "NOT_ESTABLISHED"
    for flag in ("provider_writes_performed", "retry_admitted", "restore_admitted", "deployment_admitted", "runtime_state_verified"):
        assert result[flag] is False
    assert len(calls) == 8 and {host for host, _path in calls} == {"api.github.com", "safe.actions.githubusercontent.com"}


@pytest.mark.parametrize("defect", ["attempt", "bool_attempt", "event", "source", "workflow", "repository",
    "status", "time", "future", "current_rerun", "late_rerun", "late_workflow", "signature", "commit_source",
    "census", "missing_job", "duplicate_job", "job_name", "job_attempt", "job_source", "job_failed", "job_time",
    "step_failed", "upload_missing", "expired", "expires", "artifact_name", "artifact_source", "artifact_repository",
    "artifact_run", "artifact_size", "artifact_digest", "artifact_time", "archive_corrupt", "archive_overflow"])
def test_substituted_or_incomplete_native_evidence_holds(defect):
    state = fixture_metadata()
    run, jobs, artifact = state["run"], state["jobs"], state["artifact"]
    producer = jobs["jobs"][1]
    if defect == "attempt": run["run_attempt"] = 2
    if defect == "bool_attempt": run["run_attempt"] = True
    if defect == "event": run["event"] = "push"
    if defect == "source": run["head_sha"] = "a" * 40
    if defect == "workflow": run["path"] = native.WORKFLOW
    if defect == "repository": run["repository"]["full_name"] = "other/repo"
    if defect == "status": run["conclusion"] = "failure"
    if defect == "time": run["run_started_at"] = "2026-10-05T13:41:00Z"
    if defect == "future": run["updated_at"] = "2030-10-05T13:41:00Z"
    if defect == "current_rerun": state["current"]["run_attempt"] = 2
    if defect in {"late_rerun", "late_workflow"}:
        state["late_current"] = copy.deepcopy(state["current"])
        state["late_current"]["run_attempt" if defect == "late_rerun" else "workflow_id"] = 2
    if defect == "signature": state["commit"]["verification"]["verified"] = False
    if defect == "commit_source": state["commit"]["sha"] = "a" * 40
    if defect == "census": jobs["total_count"] = 3
    if defect == "missing_job": jobs["jobs"].pop()
    if defect == "duplicate_job": jobs["jobs"][1] = copy.deepcopy(jobs["jobs"][0])
    if defect == "job_name": producer["name"] = "other"
    if defect == "job_attempt": producer["run_attempt"] = True
    if defect == "job_source": producer["head_sha"] = "a" * 40
    if defect == "job_failed": producer["conclusion"] = "failure"
    if defect == "job_time": producer["completed_at"] = "2026-10-05T13:50:00Z"
    if defect == "step_failed": producer["steps"][0]["conclusion"] = "failure"
    if defect == "upload_missing": producer["steps"].pop()
    if defect == "expired": artifact["expired"] = True
    if defect == "expires": artifact["expires_at"] = "2026-10-05T13:40:54Z"
    if defect == "artifact_name": artifact["name"] = "other"
    if defect == "artifact_source": artifact["workflow_run"]["head_sha"] = "a" * 40
    if defect == "artifact_repository": artifact["workflow_run"]["repository_id"] = 123
    if defect == "artifact_run": artifact["workflow_run"]["id"] += 1
    if defect == "artifact_size": artifact["size_in_bytes"] += 1
    if defect == "artifact_digest": artifact["digest"] = "sha256:" + "0" * 64
    if defect == "artifact_time": artifact["created_at"] = "2026-10-05T13:38:00Z"
    if defect == "archive_corrupt": state["archive"] = b"X" + SAFE_ARCHIVE[1:]
    if defect == "archive_overflow": state["archive"] += b"X"
    reader, _calls = native_reader(state)
    try:
        with pytest.raises(observation.ObservationHeld) as error:
            observation.verify_retained_observation(reader)
    finally:
        reader.client.close()
    assert str(error.value) in observation.CODES


@pytest.mark.parametrize("redirect", ["http://safe.actions.githubusercontent.com/closed.zip", "https://evil.example/a",
    "https://safe.actions.githubusercontent.com:444/a", "https://user:secret@safe.actions.githubusercontent.com/a",
    "https://safe.actions.githubusercontent.com/a#fragment", "https://actions.githubusercontent.com.evil.example/a"])
def test_untrusted_redirect_never_receives_a_request(redirect):
    state = fixture_metadata(); state["redirect"] = redirect
    reader, calls = native_reader(state)
    try:
        with pytest.raises(observation.ObservationHeld): observation.verify_retained_observation(reader)
    finally:
        reader.client.close()
    assert all(host == "api.github.com" for host, _path in calls)


@pytest.mark.parametrize("defect", ["extra", "write", "retry", "prior", "counts", "class", "revision", "duplicate", "whitespace", "oversized"])
def test_report_never_accepts_broader_authority_or_loose_bytes(defect):
    value = json.loads(SAFE_REPORT)
    if defect == "extra": value["private_payload"] = "PRIVATE_CANARY"
    if defect == "write": value["provider_writes_performed"] = True
    if defect == "retry": value["retry_admitted"] = True
    if defect == "prior": value["prior_source_revision"] = "a" * 40
    if defect == "counts": value["artifact_effect_observation"]["missing_object_count"] = 0
    if defect == "class": value["artifact_effect_observation"]["classification"] = "ALL_EXPECTED_OBJECTS_PRESENT_AND_VALIDATED_AT_READ_TIME"
    if defect == "revision": value["private_head_metadata"]["revision"] = "a" * 40
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if defect == "duplicate": raw = raw[:-2] + b',"state":"OBSERVED"}\n'
    if defect == "whitespace": raw = SAFE_REPORT.rstrip()
    if defect == "oversized": raw = b"x" * 4097
    with pytest.raises(observation.ObservationHeld, match="OBSERVATION_REPORT_UNQUALIFIED"):
        observation.validate_observation_report(raw)


def test_transport_errors_and_expired_budgets_do_not_expose_private_text():
    reader, calls = native_reader(fixture_metadata())
    reader.deadline = 0
    try:
        with pytest.raises(observation.ObservationHeld) as error: observation.verify_retained_observation(reader)
        assert str(error.value) == "OBSERVATION_UNAVAILABLE" and calls == []
        reader.deadline = time.monotonic() + 30
        reader.request = lambda _path: (_ for _ in ()).throw(RuntimeError("PRIVATE_CANARY"))
        with pytest.raises(observation.ObservationHeld) as error: observation.verify_retained_observation(reader)
        assert str(error.value) == "OBSERVATION_UNAVAILABLE"
    finally:
        reader.client.close()


def test_observation_budget_is_capped_even_when_parent_budget_is_larger(monkeypatch):
    reader, calls = native_reader(fixture_metadata())
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    reader.deadline = 900.0
    request = reader.request
    def slow_read(path):
        result = request(path)
        clock[0] = 121.0
        return result
    reader.request = slow_read
    try:
        with pytest.raises(observation.ObservationHeld, match="OBSERVATION_UNAVAILABLE"):
            observation.verify_retained_observation(reader)
    finally:
        reader.client.close()
    assert len(calls) == 1


def test_module_import_and_call_surface_have_no_provider_or_write_path():
    source = Path(observation.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.Import) and any(name.name in {"huggingface_hub", "sqlite3"} for name in node.names)
        for node in ast.walk(tree))
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {"create_commit", "batch_bucket_files", "upload_file", "pause_space", "restart_space", "write_bytes", "write_text", "extractall"}
