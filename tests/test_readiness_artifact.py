#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline adversarial evidence fixtures; no fixture authorizes a deployment."""
import ast
import asyncio
import builtins
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import threading
import zipfile

import httpx
import pytest

import szl_readiness_artifact as subject

SOURCE = "a" * 40
NOW = datetime(2026, 10, 13, 10, 5, tzinfo=timezone.utc)
START = "2026-10-13T10:00:00Z"
CHECKED = "2026-10-13T10:02:00Z"
DONE = "2026-10-13T10:04:00Z"
MATRIX = {"endpoints": {"/api/livez": {"method": "GET", "schema": "generic_obj"}}}
ENV = {"SPACE_ID": "SZLHOLDINGS/a11oy", "SZL_GIT_SHA": SOURCE, "SZL_READINESS_GH_TOKEN": "fixture"}


def fixture():
    payload = {
        "schema": "szl.readiness-verdict/v1", "harness": "a11oy-readiness probe", "doctrine": "v11",
        "base": subject.ORIGIN, "checkedAt": CHECKED, "sourceRevision": SOURCE,
        "sourceRevisionBefore": SOURCE, "sourceRevisionAfter": SOURCE, "sourceRevisionStatus": "OBSERVED",
        "summary": dict(endpoints=1, ok=1, skippedStateChanging=0, requiredNotProbed=0,
                        lies=0, unreachable=0, throttled=0, degraded=0, blockingDegraded=0, p95_worst=1),
        "results": [dict(path="/api/livez", method="GET", status=200, samples=1,
                         lie=False, unreachable=False, throttled=False, degraded=False,
                         schemaOk=True, citationOk=True, labelPolicyOk=True, freshOk=None)],
    }
    job = dict(name=subject.PRODUCER, run_id=7, run_attempt=2, head_sha=SOURCE,
               status="completed", conclusion="success", started_at=START, completed_at=DONE)
    run = dict(id=7, run_attempt=2, path=subject.WORKFLOW, event="push", head_sha=SOURCE,
               head_branch="main", status="completed", conclusion="success", run_started_at=START,
               repository=dict(id=subject.REPOSITORY_ID, full_name=subject.REPOSITORY),
               head_repository=dict(id=subject.REPOSITORY_ID))
    return payload, job, run


class FakeTransport:
    def __init__(self):
        self.payload, self.job, self.run = fixture()
        self.main = {"name": "main", "protected": True, "commit": {"sha": SOURCE}}
        self.jobs = [self.job, {**self.job, "name": subject.RELOCK}]
        self.jobs_count = 2
        self.name = "canonical-a11oy-readiness-7-2"
        self.extra_member = None
        self.meta_change = {}
        self.raw = None
        self.calls = []
        self.closed = False

    def archive(self, _id):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            def write_member(name, content):
                info = zipfile.ZipInfo(name, date_time=(2026, 10, 13, 10, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)

            write_member("readiness-verdict.json", self.raw or json.dumps(self.payload))
            if self.extra_member:
                write_member(self.extra_member, "{}")
        return output.getvalue()

    def meta(self):
        archive = self.archive(9)
        return {"id": 9, "name": self.name, "expired": False,
                "digest": "sha256:" + hashlib.sha256(archive).hexdigest(), "size_in_bytes": len(archive),
                "created_at": "2026-10-13T10:03:00Z",
                "workflow_run": dict(id=7, head_sha=SOURCE, head_branch="main",
                                     repository_id=subject.REPOSITORY_ID, head_repository_id=subject.REPOSITORY_ID),
                **self.meta_change}

    def json(self, path):
        self.calls.append(path)
        if path == "/branches/main":
            return self.main
        if path.startswith("/actions/workflows/"):
            return {"workflow_runs": [{"id": 7, "run_attempt": 2}]}
        if path.endswith("/jobs?per_page=100"):
            return {"total_count": self.jobs_count, "jobs": self.jobs}
        if path.endswith("/artifacts?per_page=100"):
            return {"total_count": 1, "artifacts": [self.meta()]}
        if path == "/actions/runs/7/attempts/2":
            return self.run
        raise AssertionError(path)

    def close(self):
        self.closed = True


def observe(fake=None, now=NOW):
    return subject.acquire(fake or FakeTransport(), SOURCE, MATRIX, now=now)


def test_exact_artifact_retains_original_clock_and_provenance():
    fake = FakeTransport()
    result = observe(fake)
    assert result["verdict"]["checkedAt"] == CHECKED
    assert result["verdict"]["summary"]["requiredNotProbed"] == 0
    assert result["evidence"]["artifact_sha256"] == fake.meta()["digest"][7:]
    assert result["evidence"]["signatures_verified"] is False
    assert fake.calls.count("/branches/main") == 2


@pytest.mark.parametrize("field,value", [
    ("event", "pull_request"), ("path", ".github/workflows/foreign.yml"),
    ("head_sha", "b" * 40), ("head_branch", "feature"), ("run_attempt", 1),
    ("conclusion", "failure"), ("status", "in_progress"),
    ("repository", {"id": 2, "full_name": subject.REPOSITORY}),
    ("head_repository", {"id": 2}),
])
def test_reject_foreign_or_failed_run_without_falling_back(field, value):
    fake = FakeTransport()
    fake.run[field] = value
    with pytest.raises(subject.EvidenceBlocked):
        observe(fake)
    assert sum("/workflows/" in path for path in fake.calls) == 1


@pytest.mark.parametrize("mutation", ["skipped", "missing", "duplicate", "incomplete", "old-attempt", "future"])
def test_job_attempt_and_complete_census(mutation):
    fake = FakeTransport()
    if mutation == "skipped": fake.job["conclusion"] = "skipped"
    if mutation == "missing": fake.jobs.pop(); fake.jobs_count = 1
    if mutation == "duplicate": fake.jobs.append(dict(fake.job)); fake.jobs_count = 3
    if mutation == "incomplete": fake.jobs_count = 101
    if mutation == "old-attempt": fake.job["run_attempt"] = 1
    if mutation == "future": fake.job["completed_at"] = "2026-10-14T10:00:00Z"
    with pytest.raises(subject.EvidenceBlocked): observe(fake)


@pytest.mark.parametrize("change", [
    {"digest": "sha256:" + "0" * 64}, {"expired": True}, {"size_in_bytes": 1},
    {"digest": "sha256:" + "b" * 64}, {"created_at": "2026-10-12T10:03:00Z"},
    {"workflow_run": {"id": 7, "head_sha": "b" * 40}},
])
def test_archive_metadata_identity_and_digest(change):
    fake = FakeTransport(); fake.meta_change = change
    with pytest.raises(subject.EvidenceBlocked): observe(fake)


@pytest.mark.parametrize("member", ["../readiness-verdict.json", "unexpected.json", "dir/"])
def test_archive_does_not_extract_unexpected_members(member):
    fake = FakeTransport(); fake.extra_member = member
    with pytest.raises(subject.EvidenceBlocked): observe(fake)


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', '[]'])
def test_artifact_json_is_strict(raw):
    fake = FakeTransport(); fake.raw = raw
    with pytest.raises(subject.EvidenceBlocked): observe(fake)


@pytest.mark.parametrize("mutation", ["missing-required", "skipped", "required-bool", "wrong-origin", "wrong-bracket",
                                      "false-summary", "duplicate-row", "missing-row", "bad-schema", "unavailable",
                                      "bad-status", "unknown-freshness"])
def test_unprobed_or_incomplete_verdict_fails_closed(mutation):
    fake = FakeTransport(); body = fake.payload; row = body["results"][0]
    if mutation == "missing-required": del body["summary"]["requiredNotProbed"]
    if mutation == "skipped": row["skipped"] = True
    if mutation == "required-bool": body["summary"]["requiredNotProbed"] = False
    if mutation == "wrong-origin": body["base"] = "https://other.invalid"
    if mutation == "wrong-bracket": body["sourceRevisionAfter"] = "b" * 40
    if mutation == "false-summary": body["summary"]["ok"] = 0
    if mutation == "duplicate-row": body["results"].append(copy.deepcopy(row))
    if mutation == "missing-row": body["results"] = []
    if mutation == "bad-schema": row["schemaOk"] = False
    if mutation == "unavailable": row["degraded"] = True
    if mutation == "bad-status": row["status"] = 503
    if mutation == "unknown-freshness": row["freshOk"] = False
    with pytest.raises(subject.EvidenceBlocked): observe(fake)


def test_ingest_expiry_and_observation_job_clock():
    with pytest.raises(subject.EvidenceBlocked): observe(now=NOW + timedelta(hours=2))
    fake = FakeTransport(); fake.payload["checkedAt"] = "2026-10-13T09:59:59Z"
    with pytest.raises(subject.EvidenceBlocked): observe(fake)


def test_transport_only_gets_and_strips_authorization_at_redirect():
    seen = []
    def respond(request):
        seen.append(request)
        if request.url.host == "api.github.com":
            return httpx.Response(302, headers={"location": "https://fixture.blob.core.windows.net/a?sig=private"})
        return httpx.Response(200, content=b"archive")
    transport = subject.Transport("fixture-token", threading.Event(),
                                  client=httpx.Client(transport=httpx.MockTransport(respond)))
    assert transport.archive(9) == b"archive"
    assert [request.method for request in seen] == ["GET", "GET"]
    assert seen[0].headers["authorization"] == "Bearer fixture-token"
    assert "authorization" not in seen[1].headers
    transport.close()


@pytest.mark.parametrize("url", ["http://x.blob.core.windows.net/a", "https://evil.invalid/a",
                                "https://x.blob.core.windows.net.evil.invalid/a",
                                "https://user@x.blob.core.windows.net/a", "https://x.blob.core.windows.net:444/a"])
def test_redirect_allowlist_never_sends_token_elsewhere(url):
    seen = []
    def respond(request):
        seen.append(request); return httpx.Response(302, headers={"location": url})
    transport = subject.Transport("fixture", threading.Event(), client=httpx.Client(transport=httpx.MockTransport(respond)))
    with pytest.raises(subject.EvidenceBlocked): transport.archive(9)
    assert len(seen) == 1
    transport.close()


def test_bounded_transport_and_cancel_before_network(monkeypatch):
    monkeypatch.setattr(subject, "MAX_JSON", 4)
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"12345")))
    stop = threading.Event(); transport = subject.Transport("fixture", stop, client=client)
    with pytest.raises(subject.EvidenceBlocked, match="BYTE_BOUND"): transport.json("/x")
    stop.set()
    with pytest.raises(subject.EvidenceBlocked, match="DEADLINE"): transport.json("/x")
    transport.close()


def test_slow_wire_chunks_cannot_hide_deadline_or_cancellation():
    ticks = [0]
    class Trickle(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(100):
                ticks[0] += 4
                yield b"x"
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, stream=Trickle())))
    transport = subject.Transport("fixture", threading.Event(), client=client, clock=lambda: ticks[0])
    with pytest.raises(subject.EvidenceBlocked, match="DEADLINE"):
        transport.json("/x")
    assert ticks[0] == 32
    transport.close()


def test_unexpected_compression_is_rejected_before_body_decode():
    class NeverRead(httpx.SyncByteStream):
        def __iter__(self):
            pytest.fail("compressed body was read")
            yield b""
    client = httpx.Client(transport=httpx.MockTransport(lambda request:
        httpx.Response(200, headers={"content-encoding": "gzip"}, stream=NeverRead())))
    transport = subject.Transport("fixture", threading.Event(), client=client)
    with pytest.raises(subject.EvidenceBlocked, match="ENCODING_INVALID"):
        transport.json("/x")
    transport.close()


def test_no_credential_fails_without_constructing_http_client(monkeypatch):
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: pytest.fail("network client created"))
    reader = subject.Reader(environ={"SPACE_ID": ENV["SPACE_ID"], "SZL_GIT_SHA": SOURCE})
    reader.refresh()
    assert reader.snapshot()["reason"] == "GITHUB_READ_CREDENTIAL_REQUIRED"


def test_new_failure_erases_previous_green_and_snapshot_does_no_work():
    env = dict(ENV); fake = FakeTransport(); good = observe(fake)
    reader = subject.Reader(environ=env, transport_factory=lambda *_: fake,
                            fetch=lambda *a, **k: copy.deepcopy(good))
    reader.refresh()
    assert reader.snapshot(now=NOW)["verdict"]["checkedAt"] == CHECKED
    def fail(*a, **k): raise subject.EvidenceBlocked("READINESS_RUN_UNQUALIFIED")
    reader.fetch = fail
    assert reader.snapshot(now=NOW)["verdict"] is not None
    reader.refresh()
    assert reader.snapshot(now=NOW)["verdict"] is None
    assert reader.snapshot(now=NOW)["reason"] == "READINESS_RUN_UNQUALIFIED"


def test_source_change_during_fetch_and_serve_expiry():
    env = dict(ENV); fake = FakeTransport(); good = observe(fake)
    def change(*a, **k): env["SZL_GIT_SHA"] = "b" * 40; return good
    reader = subject.Reader(environ=env, fetch=change, transport_factory=lambda *_: fake)
    reader.refresh()
    assert reader.snapshot(now=NOW)["reason"] == "READINESS_IDENTITY_CHANGED"
    env["SZL_GIT_SHA"] = SOURCE; reader.state = good
    assert reader.snapshot(now=NOW + timedelta(days=1))["verdict"] is None
    assert reader.state["verdict"]["checkedAt"] == CHECKED


def test_lifecycle_single_worker_stop_restart_and_fresh_identity():
    calls = []; ready = threading.Event(); env = dict(ENV)
    reader = subject.Reader(environ=env, interval=60)
    def refresh(): calls.append(env["SZL_GIT_SHA"]); ready.set()
    reader.refresh = refresh
    assert reader.thread is None
    assert reader.start() is True; assert ready.wait(1)
    first = reader.thread
    assert reader.start() is False
    reader.stop(); assert not first.is_alive(); assert reader.snapshot()["reason"] == "READER_STOPPED"
    ready.clear(); env["SZL_GIT_SHA"] = "b" * 40
    assert reader.start() is True; assert ready.wait(1)
    assert reader.thread is not first
    reader.stop(); assert calls == [SOURCE, "b" * 40]


def test_exact_route_reads_memory_without_start_or_env_green_fallback(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    source = (subject.ROOT / "serve.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    block = next(node for node in tree.body if isinstance(node, ast.Try) and any(
        isinstance(child, ast.AsyncFunctionDef) and child.name == "_a11oy_readiness_tab_matrix"
        for child in node.body))
    monkeypatch.setenv("SPACE_ID", ENV["SPACE_ID"]); monkeypatch.setenv("SZL_GIT_SHA", SOURCE)
    monkeypatch.setenv("SZL_PROBE_VERDICT_JSON", json.dumps(fixture()[0]))
    reader = subject.Reader(environ=dict(ENV))
    monkeypatch.setattr(subject, "reader", reader)
    monkeypatch.setattr(reader, "start", lambda: pytest.fail("GET started worker"))
    monkeypatch.setattr(reader, "refresh", lambda: pytest.fail("GET fetched"))
    app = FastAPI(); scope = {"app": app, "__file__": str(subject.ROOT / "serve.py")}
    exec(compile(ast.Module(body=[block], type_ignores=[]), "serve.py", "exec"), scope)
    response = TestClient(app).get("/api/a11oy/v1/readiness/tab-matrix?view=summary").json()
    assert response["available"] is False and response["probe_verdict_available"] is False
    assert response["verdict_evidence"]["reason"] == "NOT_OBSERVED"
    assert reader.thread is None


def test_optional_import_failure_leaves_lifecycle_unavailable_without_crashing(monkeypatch):
    from fastapi import FastAPI
    source = (subject.ROOT / "serve.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == "_rd_artifact"
                              for target in node.targets))
    block = next(node for node in tree.body if isinstance(node, ast.Try) and any(
        isinstance(child, ast.AsyncFunctionDef) and child.name == "_a11oy_readiness_tab_matrix"
        for child in node.body))
    original_import = builtins.__import__
    def unavailable(name, *args, **kwargs):
        if name == "szl_readiness_artifact":
            raise ImportError("fixture missing dependency")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", unavailable)
    scope = {"app": FastAPI(), "__file__": str(subject.ROOT / "serve.py"), "asyncio": asyncio}
    lifecycle = []
    for name in ("startup", "shutdown"):
        function = copy.deepcopy(next(node for node in tree.body
                                      if isinstance(node, ast.AsyncFunctionDef) and node.name == name))
        function.decorator_list = []
        function.body = [node for node in function.body if isinstance(node, ast.If)
                         and any(isinstance(item, ast.Name) and item.id == "_rd_artifact"
                                 for item in ast.walk(node.test))]
        assert len(function.body) == 1
        lifecycle.append(function)
    exec(compile(ast.Module(body=[assignment, block, *lifecycle], type_ignores=[]), "serve.py", "exec"), scope)
    assert scope["_rd_artifact"] is None
    asyncio.run(scope["startup"]())
    asyncio.run(scope["shutdown"]())
    assert not any(route.path.endswith("/readiness/tab-matrix") for route in scope["app"].routes)


def test_dockerfile_ships_the_dependency_closure():
    dockerfile = (subject.ROOT / "Dockerfile").read_text(encoding="utf-8")
    for name in ("szl_readiness_artifact.py", ".github/scripts/publish_readiness_verdict.py"):
        assert any(name in line.split()[1:-1] for line in dockerfile.splitlines() if line.startswith("COPY "))
    assert "COPY .github/scripts/publish_readiness_verdict.py ./.github/scripts/" not in dockerfile


def test_validator_loads_from_the_batched_image_path(tmp_path, monkeypatch):
    source = subject.ROOT / ".github/scripts/publish_readiness_verdict.py"
    image_path = tmp_path / "scripts/publish_readiness_verdict.py"
    image_path.parent.mkdir()
    image_path.write_bytes(source.read_bytes())
    subject._validator.cache_clear()
    try:
        monkeypatch.setattr(subject, "ROOT", tmp_path)
        validator = subject._validator()
        payload, _job, _run = fixture()
        compact = validator.compact_verdict(
            payload, expected_origin=subject.ORIGIN,
            expected_source_sha=SOURCE, now=NOW,
        )
        assert compact["sourceRevision"] == SOURCE
    finally:
        subject._validator.cache_clear()
