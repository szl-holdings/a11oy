#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise installed Hub SDK adapters with inert HTTP and native-transfer fixtures.

The real SDK builds and interprets requests; all HTTP and Xet transfer boundaries
are replaced before use. These are source-compatibility tests, not provider CAS,
native transfer, live durability, credential or deployment qualification.
"""

import base64
from contextlib import contextmanager
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import socket
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest
from huggingface_hub import HfApi
from huggingface_hub import _commit_api, file_download, hf_api
from huggingface_hub.errors import BucketBatchError, EntryNotFoundError
from huggingface_hub.utils import _http, _pagination, _xet

import a11oy_state_store as store
from tests.state_store_support import FakeClock, FakeHeadBackend, fingerprint, make_db, replica


PARENT = "a" * 40
NEXT = "b" * 40
REPO = "fixture/state"
BUCKET = "fixture/snapshots"
ORIGIN = "https://hub.invalid"


class FixtureTransport:
    def __init__(self):
        self.requests = []
        self.objects = {}
        self.transfers = {}
        self.body = b'{"schema":"synthetic-head"}'
        self.private = True
        self.info_status = 200
        self.commit_status = 200
        self.commit_oid = NEXT
        self.batch_failed = False
        self.download_corrupt = False

    def file_info(self, path):
        raw = self.objects[path]
        return {"type": "file", "path": path, "size": len(raw),
                "xetHash": hashlib.sha256(raw).hexdigest()}

    def __call__(self, request):
        assert request.url.host == "hub.invalid"
        assert "authorization" not in request.headers
        content = request.read()
        self.requests.append((request.method, str(request.url), content))
        path = request.url.path
        if path == f"/api/datasets/{REPO}":
            return httpx.Response(self.info_status, json={
                "id": REPO, "sha": PARENT, "private": self.private,
            })
        if path == f"/api/datasets/{REPO}/paths-info/{PARENT}":
            assert parse_qs(content.decode()) == {"paths": [store.HEAD_PATH], "expand": ["false"]}
            return httpx.Response(200, json=[{
                "type": "file", "path": store.HEAD_PATH, "size": len(self.body), "oid": NEXT,
            }])
        if path == f"/datasets/{REPO}/resolve/{PARENT}/{store.HEAD_PATH}":
            return httpx.Response(200, content=self.body if request.method == "GET" else b"",
                                  headers={"Content-Length": str(len(self.body)),
                                           "ETag": '"' + NEXT + '"', "X-Repo-Commit": PARENT})
        if path == f"/api/datasets/{REPO}/preupload/main":
            files = json.loads(content)["files"]
            assert len(files) == 1 and files[0]["path"] == store.HEAD_PATH
            return httpx.Response(200, json={"files": [{
                "path": store.HEAD_PATH, "uploadMode": "regular", "shouldIgnore": False,
            }]})
        if path == f"/api/datasets/{REPO}/commit/main":
            return httpx.Response(self.commit_status, json={
                "commitOid": self.commit_oid, "commitUrl": f"{ORIGIN}/datasets/{REPO}/commit/{NEXT}",
            })
        if path == f"/api/buckets/{BUCKET}/paths-info":
            paths = json.loads(content)["paths"]
            return httpx.Response(200, json=[self.file_info(p) for p in paths if p in self.objects])
        if path.startswith(f"/api/buckets/{BUCKET}/tree/"):
            prefix = path.removeprefix(f"/api/buckets/{BUCKET}/tree/")
            assert request.url.params["recursive"] == "true"
            return httpx.Response(200, json=[
                {"type": "directory", "path": prefix},
                *[self.file_info(p) for p in self.objects if p.startswith(prefix)],
            ])
        if path == f"/api/buckets/{BUCKET}/batch":
            rows = [json.loads(line) for line in content.splitlines()]
            assert len(rows) == 1 and rows[0]["type"] == "addFile"
            row = rows[0]
            if self.batch_failed:
                return httpx.Response(200, json={
                    "failed": [{"path": row["path"], "error": "synthetic denied operation"}],
                })
            self.objects[row["path"]] = self.transfers[row["xetHash"]]
            return httpx.Response(200, json={"failed": []})
        if path.startswith(f"/buckets/{BUCKET}/resolve/"):
            remote = path.removeprefix(f"/buckets/{BUCKET}/resolve/")
            raw = self.objects[remote]
            return httpx.Response(200, headers={
                "Content-Length": str(len(raw)), "X-Xet-Hash": hashlib.sha256(raw).hexdigest(),
                "X-Xet-Refresh-Route": f"{ORIGIN}/synthetic-xet-read-token",
            })
        raise AssertionError(f"unexpected synthetic SDK request: {request.method} {path}")


@pytest.fixture
def sdk(monkeypatch, tmp_path):
    transport = FixtureTransport()
    client = httpx.Client(transport=httpx.MockTransport(transport))
    for module in (hf_api, _http, _pagination, _commit_api, file_download):
        if hasattr(module, "get_session"):
            monkeypatch.setattr(module, "get_session", lambda: client)
    monkeypatch.setattr(socket, "create_connection",
                        lambda *_a, **_k: pytest.fail("SDK fixture attempted a real connection"))
    monkeypatch.setenv("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    monkeypatch.setenv("HF_HUB_DISABLE_PROGRESS_BARS", "1")

    class NativeTransferFixture:
        @contextmanager
        def new_upload_commit(self, **kwargs):
            assert kwargs["token_refresh_url"].startswith(ORIGIN + "/api/buckets/")
            yield self

        def start_upload_bytes(self, value, **_kwargs):
            digest = hashlib.sha256(value).hexdigest()
            transport.transfers[digest] = value
            return SimpleNamespace(result=lambda: SimpleNamespace(
                xet_info=SimpleNamespace(hash=digest, file_size=len(value))))

        def start_upload_file(self, path, **kwargs):
            return self.start_upload_bytes(Path(path).read_bytes(), **kwargs)

        @contextmanager
        def new_file_download_group(self, **kwargs):
            assert kwargs["token_refresh_url"] == ORIGIN + "/synthetic-xet-read-token"
            yield self

        def start_download_file(self, info, destination):
            raw = transport.transfers[info.hash]
            if transport.download_corrupt:
                raw = b"X" + raw[1:]
            Path(destination).parent.mkdir(parents=True, exist_ok=True)
            Path(destination).write_bytes(raw)

    monkeypatch.setattr(_xet, "get_xet_session", lambda: NativeTransferFixture())
    api = HfApi(endpoint=ORIGIN, token=False)
    yield SimpleNamespace(transport=transport, api=api,
                          head=store.HFDatasetHeadBackend(api, REPO, tmp_path / "head"),
                          objects=store.HFBucketObjectStore(api, BUCKET, tmp_path / "objects"))
    client.close()


def test_installed_runtime_and_native_extension_match_declared_dependencies():
    import hf_xet
    assert version("huggingface-hub") == "1.33.0"
    assert version("hf-xet") == "1.7.0"
    assert hf_xet.XetFileInfo("a" * 64, 1).file_size == 1
    pins = (Path(__file__).resolve().parents[1] / "requirements-runtime.txt").read_text().splitlines()
    assert pins.count("huggingface_hub==1.33.0") == 1
    assert pins.count("hf-xet==1.7.0") == 1


def test_dataset_observation_binds_immutable_revision_and_exact_bytes(sdk):
    observed = sdk.head.observe()
    assert observed.revision == PARENT
    assert observed.body == sdk.transport.body
    requests = sdk.transport.requests
    assert any(f"/paths-info/{PARENT}" in url for _, url, _ in requests)
    assert any(f"/resolve/{PARENT}/" in url for _, url, _ in requests)
    assert not any(method in {"PUT", "DELETE"} or "/commit/" in url
                   for method, url, _ in requests)


@pytest.mark.parametrize("status,reason", [
    # The Hub intentionally maps an unauthenticated private-repository 401 to
    # RepositoryNotFoundError; neither absent nor forbidden admits storage.
    (401, "STATE_DATASET_ABSENT"), (403, "STATE_DATASET_FORBIDDEN"),
    (404, "STATE_DATASET_ABSENT"),
])
def test_dataset_access_failures_remain_fail_closed(sdk, status, reason):
    sdk.transport.info_status = status
    with pytest.raises(store.DatasetUnavailable, match=reason):
        sdk.head.probe()


def test_public_dataset_is_not_admitted(sdk):
    sdk.transport.private = False
    with pytest.raises(store.DatasetUnavailable, match="STATE_DATASET_NOT_PRIVATE"):
        sdk.head.probe()


def test_cas_submission_carries_parent_and_exact_body_once(sdk):
    assert sdk.head.submit(PARENT, sdk.transport.body, "synthetic-operation") == NEXT
    commits = [body for method, url, body in sdk.transport.requests if "/commit/main" in url]
    assert len(commits) == 1
    header, file = [json.loads(line) for line in commits[0].splitlines()]
    assert header["value"]["parentCommit"] == PARENT
    assert file["value"]["path"] == store.HEAD_PATH
    assert base64.b64decode(file["value"]["content"], validate=True) == sdk.transport.body


@pytest.mark.parametrize("status,expected", [
    (412, store.ParentConflict), (409, store.StorageBlocked), (500, store.StorageBlocked),
])
def test_only_412_is_a_definite_cas_conflict_and_no_submission_retries(sdk, status, expected):
    sdk.transport.commit_status = status
    with pytest.raises(expected):
        sdk.head.submit(PARENT, sdk.transport.body, "synthetic-operation")
    assert sum("/commit/main" in url for _, url, _ in sdk.transport.requests) == 1


def test_malformed_commit_identity_is_uncertain(sdk):
    sdk.transport.commit_oid = "main"
    with pytest.raises(store.StorageBlocked, match="STATE_HEAD_OUTCOME_UNCERTAIN"):
        sdk.head.submit(PARENT, sdk.transport.body, "synthetic-operation")


def test_bucket_sdk_round_trip_preserves_sqlite_integrity_and_fingerprint(sdk, tmp_path):
    source, snapshot, restored = (tmp_path / name for name in ("live.db", "snapshot.db", "restored.db"))
    make_db(source, 7)
    store.sqlite_backup(source, snapshot)
    before = store.verify_sqlite(snapshot, full=True)
    raw = snapshot.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    remote = f"{store.PREFIX}/gdw/20261015T120000Z-1-1-{digest[:16]}.sqlite3"
    sdk.objects.put_file(snapshot, remote)
    assert sdk.objects.size(remote) == len(raw)
    assert sdk.objects.list(store.PREFIX + "/gdw") == [remote]
    sdk.objects.get_file(remote, restored)
    assert hashlib.sha256(restored.read_bytes()).hexdigest() == digest
    assert store.verify_sqlite(restored, full=True) == before


def test_bucket_bytes_and_missing_path_semantics(sdk, tmp_path):
    remote = store.PREFIX + "/synthetic-note.json"
    sdk.objects.put_bytes(remote, b'{"synthetic":true}')
    assert sdk.objects.get_bytes(remote) == b'{"synthetic":true}'
    assert sdk.objects.size("missing") is None
    assert sdk.objects.get_bytes("missing") is None
    with pytest.raises(EntryNotFoundError):
        sdk.objects.get_file("missing", tmp_path / "missing")
    with pytest.raises(store.StorageBlocked, match="OBJECT_TOO_LARGE"):
        sdk.objects.get_bytes(remote, limit=1)


def test_bucket_http200_partial_failure_is_not_acknowledged(sdk):
    sdk.transport.batch_failed = True
    with pytest.raises(BucketBatchError):
        sdk.objects.put_bytes(store.PREFIX + "/failed", b"synthetic")
    assert sdk.transport.objects == {}


@pytest.mark.parametrize("failure", ["partial_batch", "corrupt_readback"])
def test_sdk_object_failure_never_publishes_a_snapshot(sdk, tmp_path, failure):
    backend, clock = FakeHeadBackend(), FakeClock()
    writer = replica(tmp_path, "writer", sdk.objects, backend, clock)
    try:
        writer.boot()
        make_db(writer.local_path("gdw"), 3)
        sdk.transport.batch_failed = failure == "partial_batch"
        sdk.transport.download_corrupt = failure == "corrupt_readback"
        writer.snapshot_once(force=True)
        assert backend.head()["snapshots"] == {}
        assert writer.status()["active_errors"]
        assert writer.status()["stores"]["gdw"]["snapshot_failures"] == 1
    finally:
        writer._close_watchers()


def test_sdk_snapshots_restore_verified_bytes_on_clean_handover(sdk, tmp_path):
    backend, clock = FakeHeadBackend(), FakeClock()
    writer = replica(tmp_path, "writer", sdk.objects, backend, clock)
    reader = replica(tmp_path, "successor", sdk.objects, backend, clock)
    try:
        writer.boot()
        make_db(writer.local_path("gdw"), 7)
        assert "gdw" in writer.snapshot_once(force=True)
        expected = fingerprint(writer.local_path("gdw"))
        writer.close()
        reader.boot()
        assert reader.epoch == 2
        assert reader.status()["stores"]["gdw"]["origin"] == store.ORIGIN_RESTORED
        assert fingerprint(reader.local_path("gdw")) == expected
    finally:
        writer._close_watchers()
        reader._close_watchers()
