#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic native Actions metadata; no fixture authorizes provider work."""
import copy
import hashlib
import io
import json
import stat
import time
import zipfile

import httpx
import pytest

from scripts import gdw_acquisition_evidence as evidence


@pytest.mark.parametrize("raw", [b'{"x":1e999}', b'{"nested":[{"x":-1e999}]}',
    b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}'])
def test_nonfinite_numbers_at_any_depth_are_rejected(raw):
    with pytest.raises(evidence.EvidenceBlocked): evidence.strict(raw)


def archive_fixture():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as writer:
        writer.writestr("safe.json", b'{"state":"SYNTHETIC"}\n')
    data = stream.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    meta = {"id": 44, "expired": False, "name": "fixed-123-1", "digest": "sha256:" + digest,
        "size_in_bytes": len(data), "created_at": "2026-10-04T01:00:10Z",
        "workflow_run": {"id": 123, "head_sha": "b" * 40, "head_branch": "main",
            "repository_id": 99, "head_repository_id": 99}}
    return meta, data, digest


def validate(meta, data, digest):
    return evidence.validate_archive(meta, data, artifact_id=44, expected_digest=digest,
        expected_name="fixed-123-1", source="b" * 40, run_id=123, repository_id=99, members=frozenset({"safe.json"}))


def test_archive_is_hash_bound_and_read_in_memory_only(monkeypatch):
    meta, data, digest = archive_fixture()
    monkeypatch.setattr(zipfile.ZipFile, "extract", lambda *_a, **_k: pytest.fail("archive extraction attempted"))
    assert validate(meta, data, digest) == {"safe.json": b'{"state":"SYNTHETIC"}\n'}


@pytest.mark.parametrize("path,value", [
    (("id",), 45), (("expired",), True), (("name",), "fixed-123-2"), (("digest",), "sha256:" + "a" * 64),
    (("size_in_bytes",), 10), (("workflow_run", "id"), 124), (("workflow_run", "head_sha"), "c" * 40),
    (("workflow_run", "head_branch"), "feature"), (("workflow_run", "repository_id"), 98),
    (("workflow_run", "head_repository_id"), 98),
])
def test_wrong_native_artifact_identity_fails_closed(path, value):
    meta, data, digest = archive_fixture()
    target = meta
    for name in path[:-1]: target = target[name]
    target[path[-1]] = value
    with pytest.raises(evidence.EvidenceBlocked): validate(meta, data, digest)


@pytest.mark.parametrize("kind", ["traversal", "duplicate", "extra", "symlink", "directory", "nonjson", "duplicatejson", "oversize"])
def test_archive_never_admits_unlisted_or_executable_members(kind):
    meta, _data, _digest = archive_fixture()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as writer:
        path = "../safe.json" if kind == "traversal" else "safe.json"
        item = zipfile.ZipInfo(path)
        if kind == "symlink": item.external_attr = (stat.S_IFLNK | 0o777) << 16
        if kind == "directory": item.external_attr = (stat.S_IFDIR | 0o755) << 16
        raw = b'{"ok":true}'
        if kind == "nonjson": raw = b"arbitrary bytes"
        if kind == "duplicatejson": raw = b'{"ok":true,"ok":false}'
        if kind == "oversize": raw = b" " * (evidence.MAX_MEMBER + 1)
        writer.writestr(item, raw)
        if kind == "duplicate": writer.writestr(path, raw)
        if kind == "extra": writer.writestr("private.sqlite3", raw)
    data = output.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    meta.update(size_in_bytes=len(data), digest="sha256:" + digest)
    with pytest.raises(evidence.EvidenceBlocked): validate(meta, data, digest)


def native_fixture():
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": evidence.REPOSITORY, "GITHUB_REPOSITORY_ID": "99",
        "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "b" * 40, "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": evidence.REPOSITORY + "/" + evidence.WORKFLOW + "@refs/heads/main",
        "GITHUB_EVENT_NAME": "push", "GITHUB_JOB": evidence.ACQUISITION_JOB_KEY, "GH_TOKEN": "synthetic-token"}
    run = {"id": 123, "run_attempt": 1, "path": evidence.WORKFLOW, "event": "push", "head_sha": "b" * 40,
        "head_branch": "main", "repository": {"id": 99, "full_name": evidence.REPOSITORY},
        "head_repository": {"id": 99}, "run_started_at": "2026-10-04T01:00:00Z"}
    jobs = {"total_count": 2, "jobs": [{"name": name, "id": index, "run_id": 123, "run_attempt": 1,
        "head_sha": "b" * 40, "status": "completed", "conclusion": "success", "completed_at": "2026-10-04T01:00:20Z"}
        for index, name in enumerate((evidence.SOURCE_JOB, evidence.ACQUISITION_JOB), 1)]}
    branch = {"name": "main", "protected": True, "commit": {"sha": "b" * 40}}
    meta, archive, digest = archive_fixture()
    calls = []
    def transport(request):
        calls.append(request)
        path = request.url.path
        if request.url.host == "capture.blob.core.windows.net":
            assert "authorization" not in request.headers
            return httpx.Response(200, content=archive)
        assert request.method == "GET"
        assert request.url.host == "api.github.com"
        if path.endswith("/zip"):
            return httpx.Response(302, headers={"location": "https://capture.blob.core.windows.net/signed?token=synthetic"})
        if "/artifacts/" in path: return httpx.Response(200, json=meta)
        if path.endswith("/branches/main"): return httpx.Response(200, json=branch)
        if path.endswith("/jobs"): return httpx.Response(200, json=jobs)
        return httpx.Response(200, json=run)
    client = httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=False)
    native = evidence.NativeEvidence(env, time.monotonic() + 10, client=client)
    return native, run, jobs, branch, meta, digest, calls


def test_actual_bounded_http_path_verifies_attempt_and_strips_cross_host_authorization():
    native, _run, _jobs, _branch, _meta, digest, calls = native_fixture()
    native.observe_run()
    result = native.artifact(44, digest, name="fixed-123-1", job_name=evidence.SOURCE_JOB, members=frozenset({"safe.json"}))
    assert result == {"safe.json": b'{"state":"SYNTHETIC"}\n'}
    assert len(calls) == 6
    assert calls[-1].url.host == "capture.blob.core.windows.net"
    assert "authorization" not in calls[-1].headers


def active_acquisition_fixture():
    native, run, jobs, branch, meta, digest, calls = native_fixture()
    run.update(status="in_progress", conclusion=None)
    jobs["jobs"][1].update(status="in_progress", conclusion=None, completed_at=None,
                           started_at="2026-10-04T01:00:30Z")
    return native, run, jobs, calls


def test_acquisition_requires_active_native_job_while_completed_producer_remains_readable():
    native, _run, _jobs, _calls = active_acquisition_fixture()
    native.observe_run()
    native.require_active_acquisition()
    completed, *_rest = native_fixture()
    completed.observe_run()
    with pytest.raises(evidence.EvidenceBlocked): completed.require_active_acquisition()
    # The read-only consumer still accepts artifacts from a completed producer.
    _meta, _data, digest = archive_fixture()
    assert completed.artifact(44, digest, name="fixed-123-1", job_name=evidence.ACQUISITION_JOB,
        members=frozenset({"safe.json"}))


@pytest.mark.parametrize("defect", ["wrong_job", "missing_job_key", "completed_run", "cancelled_run",
    "run_conclusion", "completed_job", "job_conclusion", "completed_timestamp", "early_job", "missing_job"])
def test_inactive_or_replayed_acquisition_is_rejected_before_artifact_reads(defect):
    native, run, jobs, calls = active_acquisition_fixture()
    if defect == "wrong_job": native.executing_job = "runtime-config"
    if defect == "missing_job_key": native.executing_job = None
    if defect == "completed_run": run["status"] = "completed"
    if defect == "cancelled_run": run.update(status="completed", conclusion="cancelled")
    if defect == "run_conclusion": run["conclusion"] = "failure"
    job = jobs["jobs"][1]
    if defect == "completed_job": job["status"] = "completed"
    if defect == "job_conclusion": job["conclusion"] = "success"
    if defect == "completed_timestamp": job["completed_at"] = "2026-10-04T01:00:31Z"
    if defect == "early_job": job["started_at"] = "2026-10-04T00:59:59Z"
    if defect == "missing_job": jobs["jobs"] = jobs["jobs"][:1]; jobs["total_count"] = 1
    native.observe_run()
    with pytest.raises(evidence.EvidenceBlocked): native.require_active_acquisition()
    assert not any("/artifacts/" in request.url.path for request in calls)


@pytest.mark.parametrize("defect", ["attempt", "workflow", "fork", "event", "unprotected", "source", "job_attempt", "pagination", "duplicate_job"])
def test_unqualified_native_run_fails_before_any_artifact_download(defect):
    native, run, jobs, branch, _meta, _digest, calls = native_fixture()
    if defect == "attempt": run["run_attempt"] = 2
    if defect == "workflow": run["path"] = "other.yml"
    if defect == "fork": run["head_repository"]["id"] = 98
    if defect == "event": run["event"] = "pull_request"
    if defect == "unprotected": branch["protected"] = False
    if defect == "source": branch["commit"]["sha"] = "c" * 40
    if defect == "job_attempt": jobs["jobs"][0]["run_attempt"] = 2
    if defect == "pagination": jobs["total_count"] = 101
    if defect == "duplicate_job": jobs["jobs"][1]["name"] = jobs["jobs"][0]["name"]
    with pytest.raises(evidence.EvidenceBlocked): native.observe_run()
    assert not any("/artifacts/" in request.url.path for request in calls)


@pytest.mark.parametrize("defect", ["producer_failed", "before_attempt", "after_producer"])
def test_artifact_requires_successful_current_attempt_producer(defect):
    native, _run, jobs, _branch, meta, digest, calls = native_fixture()
    native.observe_run()
    if defect == "producer_failed": jobs["jobs"][0]["conclusion"] = "failure"
    if defect == "before_attempt": meta["created_at"] = "2026-10-04T00:59:59Z"
    if defect == "after_producer": meta["created_at"] = "2026-10-04T01:00:21Z"
    # NativeEvidence holds parsed detached HTTP objects, so mutate its producer
    # explicitly for this negative instead of relying on fake transport aliases.
    if defect == "producer_failed": native.jobs[evidence.SOURCE_JOB]["conclusion"] = "failure"
    with pytest.raises(evidence.EvidenceBlocked):
        native.artifact(44, digest, name="fixed-123-1", job_name=evidence.SOURCE_JOB, members=frozenset({"safe.json"}))
    assert not any(request.url.path.endswith("/zip") for request in calls)
