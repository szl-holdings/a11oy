"""Actual managed LMDB snapshots and native middleware; provider writes are fakes."""
import json
from pathlib import Path
import secrets

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import a11oy_state_store as ss
import szl_khipu_delivery_routes as routes
import szl_operator_auth as auth
from khipu_lmdb import KhipuLMDB, delivery
from tests.state_store_support import FakeClock, FakeHeadBackend, replica


@pytest.fixture
def world(tmp_path, monkeypatch):
    clock, backend = FakeClock(), FakeHeadBackend()
    objects = ss.LocalDirObjectStore(tmp_path / "objects")
    owner = replica(tmp_path, "writer", objects, backend, clock)
    owner.boot()
    owner.heartbeat_once()
    monkeypatch.setattr(ss, "_ACTIVE", owner)
    monkeypatch.setenv(ss.ENABLE_ENV, ss.ENABLED_VALUE)
    operator, token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", operator)
    monkeypatch.setenv("SZL_TEST_DELIVERY_PEER", token)
    source = KhipuLMDB(str(owner.local_path("khipu_lmdb")), organ="khipu", ns="a11oy", map_size=8*1024*1024)
    mirror = KhipuLMDB(str(owner.local_path("khipu_repl")), organ="khipu-repl", ns="a11oy", map_size=8*1024*1024)
    peer = delivery.Peer("fixture", "https://localhost/api/a11oy/v2/khipu/replicate/batch/fixture",
                         "khipu", "a11oy", "SZL_TEST_DELIVERY_PEER")
    configs = [dict(direction=direction, **vars(peer)) for direction in ("inbound", "outbound")]
    monkeypatch.setenv(routes.CONFIG_ENV, json.dumps(configs))
    app = FastAPI()
    routes.register(app, ns="a11oy", source=source, mirror=mirror)
    auth.install_gate(app)
    ss.register(app)
    with TestClient(app) as client:
        yield dict(root=tmp_path, clock=clock, backend=backend, objects=objects,
                   owner=owner, source=source, mirror=mirror, peer=peer,
                   token=token, operator=operator, client=client)
    owner._close_watchers()
    source.close()
    mirror.close()


def batch(world):
    source, peer = world["source"], world["peer"]
    source.append("fixture", {"value": "bounded-test"})
    return source.prepare_replication_batch(peer.peer_id, peer.binding_sha256)


def inbound(world, body, authorization=None):
    return world["client"].post("/api/a11oy/v2/khipu/replicate/batch/fixture", content=body,
        headers={"Authorization": authorization or "Bearer " + world["token"], "Content-Type": "application/json"})


def test_receiver_authentication_precedes_body_and_snapshot(world, monkeypatch):
    async def forbidden_stream(self):
        pytest.fail("unauthorized receiver must not read body")
        yield b""
    monkeypatch.setattr(Request, "stream", forbidden_stream)
    before = world["backend"].submits
    response = inbound(world, b"not-json", "Bearer denied")
    assert response.status_code == 401
    assert world["mirror"].stats()["entries"] == 0
    assert world["backend"].submits == before
    assert world["owner"]._inflight == 0


def test_receiver_ack_requires_exact_published_snapshot_and_survives_restore(world):
    prepared = batch(world)
    response = inbound(world, prepared["body"])
    assert response.status_code == 200 and response.json()["batch_id"] == prepared["batch_id"]
    entry = world["backend"].head()["snapshots"]["khipu_repl"]
    assert entry["kind"] == "lmdb"
    replica_store = replica(world["root"], "readback", world["objects"], world["backend"], world["clock"])
    replica_store._restore_from_head(world["backend"].head())
    assert routes._received_contains(replica_store.local_path("khipu_repl"), world["mirror"], world["peer"], prepared["body"])
    before = world["mirror"].stats()["entries"]
    replay = inbound(world, prepared["body"])
    assert replay.status_code == 200 and replay.content == response.content
    assert world["mirror"].stats()["entries"] == before == 1
    assert world["owner"]._inflight == 0
    replica_store._close_watchers()


def test_receiver_uncertain_snapshot_never_acknowledges(world, monkeypatch):
    prepared = batch(world)
    real = world["owner"].snapshot_confirmed
    def unavailable(*args, **kwargs):
        raise ss.StorageBlocked("FIXTURE_READBACK_UNAVAILABLE")
    monkeypatch.setattr(world["owner"], "snapshot_confirmed", unavailable)
    response = inbound(world, prepared["body"])
    assert response.status_code == 503
    assert world["mirror"].stats()["entries"] == 1  # committed locally, never acknowledged
    monkeypatch.setattr(world["owner"], "snapshot_confirmed", real)
    replay = inbound(world, prepared["body"])
    assert replay.status_code == 200 and world["mirror"].stats()["entries"] == 1


def test_dispatch_confirms_pending_before_send_and_ack_after(world, monkeypatch):
    prepared = batch(world)
    peer = world["peer"]
    observed = []
    def send(source, configured, *, expected_batch_id):
        assert configured == peer and expected_batch_id == prepared["batch_id"]
        assert world["owner"]._inflight >= 1
        restored = replica(world["root"], "pending-readback", world["objects"], world["backend"], world["clock"])
        restored._restore_from_head(world["backend"].head())
        assert routes._pending_contains(restored.local_path("khipu_lmdb"), source, peer, prepared)
        restored._close_watchers()
        observed.append(expected_batch_id)
        source.acknowledge_replication_batch(peer.peer_id, peer.binding_sha256, expected_batch_id)
        return {"delivered": 1, "batch_id": expected_batch_id}
    monkeypatch.setattr(delivery, "deliver_once", send)
    response = world["client"].post("/api/a11oy/v2/khipu/replicate/dispatch/fixture",
                                    headers={"Authorization": "Bearer " + world["operator"]})
    assert response.status_code == 200 and observed == [prepared["batch_id"]]
    restored = replica(world["root"], "ack-readback", world["objects"], world["backend"], world["clock"])
    restored._restore_from_head(world["backend"].head())
    assert routes._ack_contains(restored.local_path("khipu_lmdb"), world["source"], peer, prepared)
    restored._close_watchers()


def test_dispatch_snapshot_failure_prevents_https(world, monkeypatch):
    batch(world)
    monkeypatch.setattr(delivery, "deliver_once", lambda *args, **kwargs: pytest.fail("must not send"))
    def refuse(*args, **kwargs):
        raise ss.StorageBlocked("FIXTURE_CAS_UNCERTAIN")
    monkeypatch.setattr(world["owner"], "snapshot_confirmed", refuse)
    response = world["client"].post("/api/a11oy/v2/khipu/replicate/dispatch/fixture",
                                    headers={"Authorization": "Bearer " + world["operator"]})
    assert response.status_code == 503 and world["owner"]._inflight == 0


def test_dispatch_unauthorized_and_unknown_peer_do_not_write(world):
    before = world["backend"].submits
    assert world["client"].post("/api/a11oy/v2/khipu/replicate/dispatch/fixture").status_code == 401
    response = world["client"].post("/api/a11oy/v2/khipu/replicate/dispatch/unknown",
                                    headers={"Authorization": "Bearer " + world["operator"]})
    assert response.status_code == 503 and world["backend"].submits == before


def test_unqualified_owner_and_wrong_live_handle_refuse_before_write(world, monkeypatch):
    prepared = batch(world)
    monkeypatch.setattr(ss, "_ACTIVE", None)
    assert inbound(world, prepared["body"]).status_code == 503
    assert world["mirror"].stats()["entries"] == 0
    monkeypatch.setattr(ss, "_ACTIVE", world["owner"])
    monkeypatch.setattr(world["mirror"], "_abspath", str(world["root"] / "unowned"))
    assert inbound(world, prepared["body"]).status_code == 503
    assert world["mirror"].stats()["entries"] == 0


def test_confirmed_lmdb_refuses_missing_or_ambiguous_live_environment(world, monkeypatch):
    batch(world)
    with pytest.raises(ss.StorageBlocked, match="CONTENT_MISMATCH"):
        world["owner"].snapshot_confirmed("khipu_lmdb", lambda path: False)
    import khipu_lmdb.core as core
    real = core._ENV_REGISTRY[world["source"]._abspath]
    monkeypatch.delitem(core._ENV_REGISTRY, world["source"]._abspath)
    with pytest.raises(ss.StorageBlocked, match="LMDB_HANDLE_REQUIRED"):
        world["owner"].snapshot_confirmed("khipu_lmdb", lambda path: True)
    monkeypatch.setitem(core._ENV_REGISTRY, world["source"]._abspath, real)
    import szl_khipu_lmdb as legacy
    monkeypatch.setitem(legacy._ENV_REGISTRY, world["source"]._abspath, object())
    with pytest.raises(ss.StorageBlocked, match="ENVIRONMENT_AMBIGUOUS"):
        world["owner"].snapshot_confirmed("khipu_lmdb", lambda path: True)
