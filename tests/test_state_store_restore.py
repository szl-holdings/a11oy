#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Snapshot/restore, history fallback, legacy bootstrap and status shape.

Everything is offline: a directory stands in for the bucket and an in-memory
CAS stands in for the private fence dataset.
"""

import copy
import hashlib
import json
import os
import sqlite3
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import a11oy_canonical_domain as canonical_domain
import a11oy_state_store as ss
import gdw_sqlite_repair
from tests.state_store_support import (FakeClock, FakeHeadBackend, count, fingerprint,
                                       make_db, replica)


@pytest.fixture(autouse=True)
def no_active_store(monkeypatch):
    monkeypatch.setattr(ss, "_ACTIVE", None)
    yield
    monkeypatch.setattr(ss, "_ACTIVE", None)


@pytest.fixture
def world(tmp_path):
    return {"objects": ss.LocalDirObjectStore(tmp_path / "bucket"), "backend": FakeHeadBackend(),
            "clock": FakeClock(), "tmp": tmp_path}


def make(world, name, **overrides):
    return replica(world["tmp"], name, world["objects"], world["backend"], world["clock"], **overrides)


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _corrupt(objects: ss.LocalDirObjectStore, remote: str) -> None:
    target = objects.root / remote
    data = bytearray(target.read_bytes())
    data[len(data) // 2] ^= 0xFF
    target.write_bytes(bytes(data))


# ---- round trip --------------------------------------------------------------
def test_snapshot_restore_round_trip_preserves_the_logical_fingerprint(world):
    a = make(world, "a")
    a.boot()
    for label in ("gdw", "series_a", "khipu", "unay"):
        make_db(a.local_path(label), 25)
    entries = a.snapshot_once(force=True)
    assert set(entries) == {"gdw", "series_a", "khipu", "unay"}
    head = world["backend"].head()
    for label, entry in head["snapshots"].items():
        assert entry["path"].startswith(f"{ss.PREFIX}/{label}/")
        assert entry["path"].endswith(f"-1-{entry['seq']}-{entry['sha256'][:16]}.sqlite3")
        assert world["objects"].size(entry["path"]) == entry["size"]
        assert entry["logical_sha256"] == fingerprint(a.local_path(label))
    expected = {label: fingerprint(a.local_path(label)) for label in entries}
    a.close()

    b = make(world, "b")
    b.boot()
    for label, digest in expected.items():
        assert fingerprint(b.local_path(label)) == digest
        assert b.status()["stores"][label]["origin"] == ss.ORIGIN_RESTORED
    assert b.epoch == 2


def test_unchanged_store_is_not_uploaded_again(world):
    a = make(world, "a")
    a.boot()
    make_db(a.local_path("gdw"), 3)
    first = a.snapshot_once(force=True)
    again = a.snapshot_once(force=True)
    assert "gdw" in first and again == {}
    assert len(world["objects"].list(f"{ss.PREFIX}/gdw/")) == 1


def test_debounce_then_periodic_capture(world):
    a = make(world, "a", debounce_s=30.0, periodic_s=300.0)
    a.boot()
    clock = world["clock"]
    make_db(a.local_path("gdw"), 1)
    assert a.snapshot_once() == {}, "a fresh change waits for the debounce window"
    clock.advance(31)
    assert "gdw" in a.snapshot_once()
    # Continuous writes never go quiet; the periodic bound still captures them.
    captured = False
    for step in range(40):
        make_db(a.local_path("gdw"), 1, start=100 + step)
        clock.advance(10)
        captured = captured or "gdw" in a.snapshot_once()
    assert captured
    assert a.status()["stores"]["gdw"]["unsnapshotted_change_age_s"] is None or \
        a.status()["stores"]["gdw"]["unsnapshotted_change_age_s"] <= 300


# ---- history fallback ----------------------------------------------------------
def test_restore_walks_back_to_the_previous_verified_snapshot(world):
    a = make(world, "a")
    a.boot()
    make_db(a.local_path("gdw"), 10)
    a.snapshot_once(force=True)
    older = fingerprint(a.local_path("gdw"))
    make_db(a.local_path("gdw"), 10, start=10)
    a.snapshot_once(force=True)
    a.close()
    head = world["backend"].head()
    assert len(head["history"]["gdw"]) == 1
    _corrupt(world["objects"], head["snapshots"]["gdw"]["path"])

    b = make(world, "b")
    b.boot()
    assert b.status()["stores"]["gdw"]["health"] == "OK"
    assert fingerprint(b.local_path("gdw")) == older
    assert count(b.local_path("gdw")) == 10
    b.snapshot_once(force=True)
    republished = world["backend"].head()["snapshots"]["gdw"]
    assert republished["path"] != head["snapshots"]["gdw"]["path"]
    assert republished["logical_sha256"] == older, "HEAD no longer names the corrupt object"


def test_store_without_any_verified_snapshot_is_blocked_not_recreated(world):
    a = make(world, "a")
    a.boot()
    make_db(a.local_path("gdw"), 4)
    make_db(a.local_path("khipu"), 4)
    a.snapshot_once(force=True)
    a.close()
    head = world["backend"].head()
    _corrupt(world["objects"], head["snapshots"]["gdw"]["path"])

    b = make(world, "b")
    b.boot()
    assert b.blocked_labels() == ["gdw"]
    assert not b.local_path("gdw").exists()
    assert b.writable(), "GDW has its own degraded mode; other stores keep serving"
    make_db(b.local_path("khipu"), 1, start=4)
    b.snapshot_once(force=True)
    assert world["backend"].head()["snapshots"]["gdw"] == head["snapshots"]["gdw"], \
        "a blocked store's last good HEAD entry is never replaced"
    b.close()

    _corrupt(world["objects"], world["backend"].head()["snapshots"]["khipu"]["path"])
    for entry in world["backend"].head()["history"].get("khipu", []):
        _corrupt(world["objects"], entry["path"])
    c = make(world, "c")
    c.boot()
    assert "khipu" in c.blocked_labels()
    assert not c.writable() and c.fence_reason() == "STATE_STORE_BLOCKED_KHIPU"


def test_snapshot_failure_never_touches_the_live_db_and_publishes_later(world):
    a = make(world, "a")
    a.boot()
    gdw = a.local_path("gdw")
    make_db(gdw, 6)
    before = fingerprint(gdw)
    world["backend"].unreachable = True
    a.snapshot_once(force=True)
    status = a.status()
    assert status["pending_publish"] == ["gdw"]
    assert status["last_error"]["code"] == "STATE_DATASET_UNREACHABLE"
    assert fingerprint(gdw) == before and gdw_sqlite_repair.inspect(gdw)["ok"]
    world["backend"].unreachable = False
    world["clock"].advance(301)
    a.snapshot_once()
    head = world["backend"].head()
    assert "gdw" in head["snapshots"] and a.status()["pending_publish"] == []


# ---- legacy bootstrap ---------------------------------------------------------
def _orphan_legacy_gdw(path: Path) -> str:
    """A GDW-like store whose freelist pages become 'Page N: never used'."""
    make_db(path, 50)
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE junk(id INTEGER PRIMARY KEY, payload BLOB)")
    connection.executemany("INSERT INTO junk(payload) VALUES(?)", [(os.urandom(3000),) for _ in range(24)])
    connection.commit()
    connection.execute("DELETE FROM junk")
    connection.commit()
    connection.close()
    logical = fingerprint(path)
    data = bytearray(path.read_bytes())
    data[32:40] = b"\x00" * 8  # unlink the freelist trunk and its count
    path.write_bytes(bytes(data))
    report = gdw_sqlite_repair.inspect(path)
    assert not report["ok"] and report["repairable"]
    return logical


def test_orphan_page_legacy_store_is_bootstrapped_repaired_and_frozen(world):
    legacy = world["tmp"] / "legacy" / "a11oy" / "gdw" / "gdw.sqlite3"
    legacy.parent.mkdir(parents=True)
    logical = _orphan_legacy_gdw(legacy)
    legacy_sha = _sha(legacy)
    series = world["tmp"] / "legacy" / "a11oy" / "series-a" / "control-plane-v2.sqlite3"
    make_db(series, 9)

    a = make(world, "a")
    a.boot()
    local = a.local_path("gdw")
    assert gdw_sqlite_repair.inspect(local)["ok"]
    assert fingerprint(local) == logical
    assert count(a.local_path("series_a")) == 9
    assert _sha(legacy) == legacy_sha, "the legacy file is only ever read"
    head = world["backend"].head()
    assert head["claim"]["origins"]["gdw"] == ss.ORIGIN_LEGACY
    assert {"gdw", "series_a"} <= set(head["snapshots"])
    receipts = world["objects"].list(f"{ss.PREFIX}/gdw/quarantine/")
    assert len(receipts) == 1
    receipt = json.loads(world["objects"].get_bytes(receipts[0]))
    assert receipt["schema"] == gdw_sqlite_repair.RECEIPT_SCHEMA
    assert receipt["status"] == "APPLIED" and receipt["original_source"] == "legacy:gdw"
    frozen = json.loads(world["objects"].get_bytes(ss.LEGACY_FROZEN_PATH))
    assert frozen["schema"] == ss.FROZEN_SCHEMA
    assert set(frozen["stores"]) == {"gdw", "series_a"}
    a.close()

    # Later legacy edits are ignored: HEAD is the only authority from now on.
    make_db(series, 5, start=100)
    b = make(world, "b")
    b.boot()
    assert count(b.local_path("series_a")) == 9


def test_unrepairable_legacy_store_is_blocked_and_left_untouched(world):
    legacy = world["tmp"] / "legacy" / "a11oy" / "gdw" / "gdw.sqlite3"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"SQLite format 3\x00" + b"\x01" * 4080)
    before = _sha(legacy)
    a = make(world, "a")
    a.boot()
    assert a.blocked_labels() == ["gdw"]
    assert _sha(legacy) == before
    assert "gdw" not in world["backend"].head()["snapshots"]


def test_unfenced_mode_is_loud_and_adopts_snapshots_by_listing(world):
    legacy = world["tmp"] / "legacy" / "khipu" / "khipu_a11oy.sqlite3"
    make_db(legacy, 3)
    a = replica(world["tmp"], "a", world["objects"], None, world["clock"])
    a.boot()
    status = a.status()
    assert status["mode"] == ss.MODE_UNFENCED and status["unfenced"] is True
    assert status["role"] == ss.ROLE_UNFENCED_WRITER and status["writable"] is True
    make_db(a.local_path("khipu"), 2, start=3)
    world["clock"].advance(5)
    a.snapshot_once(force=True)
    expected = fingerprint(a.local_path("khipu"))
    unfenced_head = json.loads(world["objects"].get_bytes(ss.UNFENCED_HEAD_PATH))
    assert unfenced_head["authoritative"] is False
    a.close()

    b = replica(world["tmp"], "b", world["objects"], None, world["clock"])
    b.boot()
    assert fingerprint(b.local_path("khipu")) == expected
    assert b.status()["stores"]["khipu"]["origin"] == ss.ORIGIN_ADOPTED

    # The owner creates the dataset later: the first fenced boot adopts v2 objects.
    c = make(world, "c")
    c.boot()
    assert fingerprint(c.local_path("khipu")) == expected
    assert world["backend"].head()["claim"]["origins"]["khipu"] == ss.ORIGIN_ADOPTED


# ---- LMDB -----------------------------------------------------------------------
def test_lmdb_envs_bootstrap_snapshot_and_restore(world):
    lmdb = pytest.importorskip("lmdb")
    import szl_khipu_lmdb

    legacy = world["tmp"] / "legacy" / "khipu_lmdb_a11oy"
    legacy.mkdir(parents=True)
    env = lmdb.open(str(legacy), map_size=8 * 1024 * 1024, subdir=True)
    with env.begin(write=True) as txn:
        for index in range(20):
            txn.put(b"seq:%020d" % index, b"receipt-%d" % index)
    env.close()

    a = make(world, "a")
    a.boot()
    local = a.local_path("khipu_lmdb")
    assert ss.lmdb_logical_digest(local)["entries"] == 20
    store = szl_khipu_lmdb.KhipuLMDB(path=str(local), organ="khipu", ns="a11oy")
    try:
        store.append("state-store-test", {"n": 1})
        a.snapshot_once(force=True)  # through env.copy(compact=True) on the open env
        a.close()
    finally:
        registered = szl_khipu_lmdb._ENV_REGISTRY.pop(os.path.abspath(str(local)), None)
        if registered is not None:
            registered.close()
    expected = ss.lmdb_logical_digest(local)
    assert expected["entries"] > 20

    b = make(world, "b")
    b.boot()
    assert ss.lmdb_logical_digest(b.local_path("khipu_lmdb")) == expected
    assert world["backend"].head()["snapshots"]["khipu_lmdb"]["path"].endswith(".mdb")


# ---- status route ---------------------------------------------------------------
def test_status_route_shape_names_labels_but_no_paths(world, monkeypatch):
    a = make(world, "a")
    a.boot()
    make_db(a.local_path("gdw"), 2)
    a.snapshot_once(force=True)
    monkeypatch.setattr(ss, "_ACTIVE", a)
    app = FastAPI()
    ss.register(app)
    response = TestClient(app).get("/api/a11oy/v1/storage/status")
    assert response.status_code == 200
    body = response.json()
    assert {"schema", "mode", "role", "writable", "epoch", "lease", "stores", "alert",
            "last_error", "durable_v1", "pending_publish"} <= set(body)
    assert body["schema"] == ss.STATUS_SCHEMA
    assert body["durable_v1"]["status"] == "RETIRED"
    assert body["lease"]["state"] == ss.STATE_ACTIVE and body["epoch"] == 1
    assert set(body["stores"]) == {spec.label for spec in ss.STORES}
    gdw = body["stores"]["gdw"]
    assert len(gdw["sha16"]) == 16 and gdw["integrity"] in ("integrity_check", "quick_check")
    rendered = json.dumps(body)
    assert str(world["tmp"]) not in rendered and "/data" not in rendered
    assert ss.PREFIX not in rendered, "object paths stay out of the public status"


def test_status_alerts_when_snapshots_stop(world):
    a = make(world, "a", alert_s=900.0)
    a.boot()
    make_db(a.local_path("gdw"), 1)
    a.snapshot_once(force=True)
    assert a.status()["alert"] is False
    world["clock"].advance(901)
    assert a.status()["alert"] is True


def test_disabled_store_is_inert(monkeypatch):
    monkeypatch.delenv(ss.ENABLE_ENV, raising=False)
    assert ss.activate() is None
    assert ss.local_path("gdw") is None and ss.local_dir("unay") is None
    assert ss.writable() is True
    assert ss.status()["mode"] == ss.MODE_DISABLED


def test_activation_failure_installs_a_blocked_read_only_store(monkeypatch, tmp_path):
    monkeypatch.setenv(ss.ENABLE_ENV, ss.ENABLED_VALUE)
    monkeypatch.setenv("UNAY_DATA_DIR", "/data")
    monkeypatch.setenv("A11OY_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv(ss.DURABLE_V1_ENV, "private-dataset-v1")

    def factory(_values):
        raise ss.StorageBlocked("HF_TOKEN_MISSING")

    with pytest.raises(ss.StorageBlocked, match="HF_TOKEN_MISSING"):
        ss.activate(factory=factory)
    status = ss.status()
    assert status["role"] == ss.ROLE_BLOCKED and status["writable"] is False
    assert status["last_error"]["code"] == "HF_TOKEN_MISSING"
    assert status["durable_v1"] == {"status": "RETIRED", "env_ignored": True}
    assert ss.DURABLE_V1_ENV not in os.environ
    assert ss.local_path("gdw") == tmp_path / "state" / "gdw" / "gdw.sqlite3"
    assert os.environ["UNAY_DATA_DIR"] == str(tmp_path / "state" / "unay")


def test_unpublished_snapshot_keeps_the_change_pending_until_published(world):
    a = make(world, "a", alert_s=900.0)
    a.boot()
    make_db(a.local_path("gdw"), 2)
    world["backend"].unreachable = True
    a.snapshot_once(force=True)
    world["clock"].advance(60)
    a.snapshot_once(force=True)  # same bytes as the pending object: still pending
    assert a.status()["pending_publish"] == ["gdw"]
    assert a.status()["stores"]["gdw"]["unsnapshotted_change_age_s"] is not None
    world["clock"].advance(901)
    assert a.status()["alert"] is True


def test_absent_fence_dataset_selects_unfenced_mode_but_transient_faults_retry(world):
    class Probing(FakeHeadBackend):
        def __init__(self, failures):
            super().__init__()
            self.failures = list(failures)

        def probe(self):
            if self.failures:
                raise self.failures.pop(0)

    absent = Probing([ss.DatasetUnavailable("STATE_DATASET_ABSENT")])
    a = replica(world["tmp"], "a", world["objects"], absent, world["clock"])
    a.boot()
    assert a.mode == ss.MODE_UNFENCED and a.status()["mode_reason"] == "STATE_DATASET_ABSENT"

    flaky = Probing([ss.StorageBlocked("STATE_DATASET_UNREACHABLE")] * 2)
    b = replica(world["tmp"], "b", world["objects"], flaky, world["clock"])
    b.boot()
    assert b.mode == ss.MODE_FENCED and b.role == ss.ROLE_WRITER


def test_head_validation_rejects_unknown_labels_and_foreign_paths(world):
    a = make(world, "a")
    a.boot()
    make_db(a.local_path("gdw"), 1)
    a.snapshot_once(force=True)
    head = world["backend"].head()
    bad = json.loads(json.dumps(head))
    bad["snapshots"]["gdw"]["path"] = "a11oy/gdw/gdw.sqlite3"
    with pytest.raises(ss.StorageBlocked):
        ss.validate_head(bad)
    bad = json.loads(json.dumps(head))
    bad["snapshots"]["other"] = head["snapshots"]["gdw"]
    with pytest.raises(ss.StorageBlocked):
        ss.validate_head(bad)


class StorageStatusHttpTests(unittest.TestCase):
    def _client(self):
        app = FastAPI()
        ss.register(app)
        proxy_calls = []

        # Match the production catch-all's method ownership. A GET-only status
        # route lets HEAD fall through to this handler instead of its owner.
        @app.api_route(
            "/api/a11oy/{path:path}",
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
        )
        async def proxy(path: str):
            proxy_calls.append(path)
            return JSONResponse({"error": "unexpected proxy dispatch"}, status_code=404)

        canonical_domain.ensure_html_documents_accept_head(app)
        return app, TestClient(app), proxy_calls

    def test_get_and_head_keep_the_same_read_only_owner(self):
        payload = {
            "schema": ss.STATUS_SCHEMA,
            "mode": ss.MODE_FENCED,
            "role": ss.ROLE_WRITER,
            "writable": True,
            "epoch": 4,
            "lease": {"state": ss.STATE_ACTIVE, "sequence": 11},
            "stores": {},
            "alert": False,
        }

        class ReadOnlyStatusStore:
            def __init__(self):
                self.status_calls = 0
                self.mutation_calls = []

            def status(self):
                self.status_calls += 1
                return copy.deepcopy(payload)

            def begin_write(self):
                self.mutation_calls.append("begin_write")
                raise AssertionError("GET/HEAD entered write admission")

            def end_write(self):
                self.mutation_calls.append("end_write")
                raise AssertionError("GET/HEAD ended write admission")

        store = ReadOnlyStatusStore()
        with patch.dict(os.environ, {"A11OY_STATE_STORE": "v2"}):
            with patch.object(ss, "_ACTIVE", store):
                app, client, proxy_calls = self._client()
                path = "/api/a11oy/v1/storage/status"
                owned = [route for route in app.routes if getattr(route, "path", None) == path]
                self.assertEqual(len(owned), 2)
                self.assertIs(owned[0].endpoint, owned[1].endpoint)
                for _ in range(2):
                    get = client.get(path)
                    head = client.head(path)
                    self.assertEqual(get.status_code, 200)
                    self.assertEqual(head.status_code, 200)
                    self.assertEqual(get.json(), payload)
                    self.assertEqual(head.content, b"")
                    for header in ("content-type", "content-length", "cache-control"):
                        self.assertEqual(head.headers[header], get.headers[header])
                    self.assertEqual(get.headers["cache-control"], "no-store")
                self.assertEqual(store.status_calls, 4)
                self.assertEqual(store.mutation_calls, [])
                self.assertEqual(proxy_calls, [])
                self.assertEqual({frozenset(route.methods) for route in owned},
                                 {frozenset({"GET"}), frozenset({"HEAD"})})

    def test_head_preserves_unavailable_storage_truth_without_activation(self):
        with patch.dict(os.environ, {"A11OY_STATE_STORE": "v2"}):
            with patch.object(ss, "_ACTIVE", None):
                _, client, proxy_calls = self._client()
                path = "/api/a11oy/v1/storage/status"
                get = client.get(path)
                head = client.head(path)
                self.assertEqual(get.status_code, 200)
                self.assertEqual(head.status_code, 200)
                self.assertEqual(get.json()["role"], ss.ROLE_NOT_ACTIVATED)
                self.assertFalse(get.json()["writable"])
                self.assertTrue(get.json()["alert"])
                self.assertEqual(head.content, b"")
                self.assertEqual(head.headers["cache-control"], "no-store")
                self.assertEqual(proxy_calls, [])
                self.assertIsNone(ss._ACTIVE)

    def test_head_preserves_the_get_schema_identity(self):
        app = FastAPI()
        ss.register(app)
        path = "/api/a11oy/v1/storage/status"
        get_route = next(route for route in app.routes
                         if getattr(route, "path", None) == path and "GET" in route.methods)
        baseline = FastAPI()
        baseline.get(path)(get_route.endpoint)
        expected_id = baseline.openapi()["paths"][path]["get"]["operationId"]
        self.assertEqual(expected_id,
                         "a11oy_storage_status_api_a11oy_v1_storage_status_get")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            schema = app.openapi()
        self.assertEqual(set(schema["paths"][path]), {"get"})
        self.assertEqual(schema["paths"][path]["get"]["operationId"], expected_id)
