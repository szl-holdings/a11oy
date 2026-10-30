#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Paired adapter boundary tests; ASGI transport and snapshot owners are fixtures."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import secrets
import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from khipu_lmdb import KhipuLMDB, delivery, outbox
import szl_khipu_delivery_routes as routes
import szl_operator_auth as auth


def app_for(source, mirror, monkeypatch, configs, namespace="a11oy"):
    monkeypatch.setenv(routes.CONFIG_ENV, json.dumps(configs))
    app = FastAPI()
    result = routes.register(app, ns=namespace, source=source, mirror=mirror)
    auth.install_gate(app)
    return TestClient(app), result


def config(peer, direction):
    return dict(direction=direction, **vars(peer))


def test_unconfigured_default_never_opens_state_or_dispatches(monkeypatch):
    monkeypatch.delenv(routes.CONFIG_ENV, raising=False)
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", secrets.token_urlsafe(32))
    monkeypatch.setattr(routes, "_state", lambda *_: pytest.fail("unconfigured must not open state"))
    app = FastAPI()
    result = routes.register(app, ns="a11oy", source=None, mirror=None)
    assert result == {"configured_peers": 0, "configuration_valid": True,
                      "mode": "EXPLICIT_DISPATCH_ONLY", "execution_authorized": False}
    with TestClient(app) as client:
        assert client.post("/api/a11oy/v2/khipu/replicate/batch/unknown").status_code == 503
        assert client.post("/api/a11oy/v2/khipu/replicate/dispatch/unknown").status_code == 401


def test_authenticated_stream_is_bounded_before_owner_or_lmdb(monkeypatch):
    token = secrets.token_urlsafe(32)
    monkeypatch.setenv("SZL_TEST_DELIVERY_PEER", token)
    peer = delivery.Peer("fixture", "https://localhost/api/a11oy/v2/khipu/replicate/batch/fixture",
                         "khipu", "a11oy", "SZL_TEST_DELIVERY_PEER")
    client, _ = app_for(None, None, monkeypatch, [config(peer, "inbound")])
    monkeypatch.setattr(routes, "_state", lambda *_: pytest.fail("oversized body must not write"))
    async def stream(_request):
        yield b" " * outbox.MAX_BATCH_BYTES
        yield b" "
    monkeypatch.setattr(Request, "stream", stream)
    with client:
        response = client.post("/api/a11oy/v2/khipu/replicate/batch/fixture",
                               headers={"Authorization": "Bearer " + token})
    assert response.status_code == 413


@pytest.mark.parametrize("namespace", ("a11oy", "killinchu"))
def test_peer_bearer_is_checked_before_stream_or_store(monkeypatch, namespace):
    operator, token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", operator)
    monkeypatch.setenv("SZL_TEST_DELIVERY_PEER", token)
    peer = delivery.Peer("fixture", f"https://localhost/api/{namespace}/v2/khipu/replicate/batch/fixture",
                         "khipu", namespace, "SZL_TEST_DELIVERY_PEER")
    client, _ = app_for(None, None, monkeypatch, [config(peer, "inbound")], namespace)
    assert auth.protected_action("POST", f"/api/{namespace}/v2/khipu/replicate/batch/fixture") is None
    assert auth.protected_action("POST", f"/api/{namespace}/v2/khipu/replicate/dispatch/fixture")
    async def forbidden_stream(_request):
        pytest.fail("unauthorized peer must not read the body")
        yield b""
    monkeypatch.setattr(Request, "stream", forbidden_stream)
    monkeypatch.setattr(routes, "_state", lambda *_: pytest.fail("unauthorized peer must not open state"))
    monkeypatch.setattr(delivery, "accept_batch", lambda *_args, **_kwargs: pytest.fail("must not write"))
    with client:
        for headers in ({}, {"Authorization": "Bearer " + operator},
                        {"Authorization": "Bearer wrong"}, {"Authorization": "Basic " + token}):
            response = client.post(f"/api/{namespace}/v2/khipu/replicate/batch/fixture", headers=headers, content=b"{")
            assert response.status_code == 401
        for headers in ({}, {"Authorization": "Bearer " + token}):
            response = client.post(f"/api/{namespace}/v2/khipu/replicate/dispatch/fixture", headers=headers, content=b"{")
            assert response.status_code == 401


@pytest.mark.parametrize("raw", ['[{"direction":"inbound","direction":"outbound"}]',
                                 '[{}]', '{}', '[' * 2000 + ']' * 2000])
def test_malformed_config_fails_closed_at_registration(monkeypatch, raw):
    monkeypatch.setenv(routes.CONFIG_ENV, raw)
    app = FastAPI()
    assert routes.register(app, ns="a11oy", source=None, mirror=None)["configuration_valid"] is False


def test_missing_qualified_state_owner_keeps_killinchu_disabled(monkeypatch):
    token = secrets.token_urlsafe(32)
    monkeypatch.setenv("SZL_TEST_DELIVERY_PEER", token)
    peer = delivery.Peer("fixture", "https://localhost/api/a11oy/v2/khipu/replicate/batch/fixture",
                         "khipu", "a11oy", "SZL_TEST_DELIVERY_PEER")
    client, _ = app_for(None, None, monkeypatch, [config(peer, "inbound")])
    def unavailable(*_):
        raise ImportError("qualified managed owner is absent")
    monkeypatch.setattr(routes, "_state", unavailable)
    monkeypatch.setattr(delivery, "accept_batch", lambda *_args, **_kwargs: pytest.fail("must not write"))
    with client:
        response = client.post("/api/a11oy/v2/khipu/replicate/batch/fixture", content=b"{}",
                               headers={"Authorization": "Bearer " + token})
    assert response.status_code == 503


def test_bidirectional_dispatch_can_receive_while_waiting(tmp_path, monkeypatch):
    """Both senders must enter their incoming handlers before either can ACK."""
    operator, token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", operator)
    monkeypatch.setenv("SZL_TEST_DELIVERY_PEER", token)
    stores = [KhipuLMDB(str(tmp_path / name), organ=organ, ns="a11oy", map_size=8*1024*1024)
              for name, organ in (("as", "a"), ("am", "mirror"), ("bs", "b"), ("bm", "mirror"))]
    a_source, a_mirror, b_source, b_mirror = stores
    ab = delivery.Peer("ab", "https://b.invalid/api/a11oy/v2/khipu/replicate/batch/ab",
                       "a", "a11oy", "SZL_TEST_DELIVERY_PEER")
    ba = delivery.Peer("ba", "https://a.invalid/api/a11oy/v2/khipu/replicate/batch/ba",
                       "b", "a11oy", "SZL_TEST_DELIVERY_PEER")

    class FixtureOwner:
        def __init__(self, source, mirror):
            self.stores = {"khipu_lmdb": source, "khipu_repl": mirror}
            self.lock = threading.Lock()
            self.inflight = 0
        def begin_write(self):
            with self.lock:
                self.inflight += 1
            return True
        def end_write(self):
            with self.lock:
                self.inflight -= 1
        def confirmed_writer(self):
            return {"fixture": True}
        def snapshot_confirmed(self, label, predicate):
            path = tmp_path / ("snapshot-" + secrets.token_hex(8))
            path.mkdir()
            self.stores[label]._env.copy(str(path), compact=True)
            assert predicate(path) is True

    owners = {id(a_source): FixtureOwner(a_source, a_mirror),
              id(b_source): FixtureOwner(b_source, b_mirror)}
    monkeypatch.setattr(routes, "_state", lambda source, mirror: owners[id(source)])
    a_client, _ = app_for(a_source, a_mirror, monkeypatch, [config(ab, "outbound"), config(ba, "inbound")])
    b_client, _ = app_for(b_source, b_mirror, monkeypatch, [config(ba, "outbound"), config(ab, "inbound")])
    a_source.append("fixture", {"node": "a"})
    b_source.append("fixture", {"node": "b"})
    barrier = threading.Barrier(2, timeout=5)
    receiver_pool = ThreadPoolExecutor(max_workers=2)
    pending_receivers = []
    def send(source, peer, *, expected_batch_id):
        prepared = source.prepare_replication_batch(peer.peer_id, peer.binding_sha256)
        assert prepared["batch_id"] == expected_batch_id
        barrier.wait()
        target = b_client if peer == ab else a_client
        future = receiver_pool.submit(target.post,
            f"/api/a11oy/v2/khipu/replicate/batch/{peer.peer_id}", content=prepared["body"],
            headers={"Authorization": "Bearer " + token})
        pending_receivers.append(future)
        response = future.result(timeout=5)
        assert response.status_code == 200
        assert response.json()["batch_id"] == expected_batch_id
        source.acknowledge_replication_batch(peer.peer_id, peer.binding_sha256, expected_batch_id)
        return {"delivered": 1, "batch_id": expected_batch_id}
    monkeypatch.setattr(delivery, "deliver_once", send)
    try:
        with a_client, b_client, ThreadPoolExecutor(max_workers=2) as dispatch_pool:
            responses = [dispatch_pool.submit(client.post,
                f"/api/a11oy/v2/khipu/replicate/dispatch/{peer.peer_id}",
                headers={"Authorization": "Bearer " + operator})
                for client, peer in ((a_client, ab), (b_client, ba))]
            assert [future.result(timeout=12).status_code for future in responses] == [200, 200]
        assert a_mirror.stats()["entries"] == b_mirror.stats()["entries"] == 1
        assert all(owner.inflight == 0 for owner in owners.values())
    finally:
        receiver_pool.shutdown(wait=True)
        for store in stores:
            store.close()


def test_image_contains_exact_package_and_adapter():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "vendor.manifest.json").read_text())
    docker = (root / "Dockerfile").read_text()
    assert "COPY khipu_lmdb/ ./khipu_lmdb/" in docker
    assert "szl_khipu_delivery_routes.py" in docker
    for name in ("__init__", "core", "outbox", "delivery"):
        relative = f"khipu_lmdb/{name}.py"
        item = manifest["files"][relative]
        assert item["source"] == f"packages/khipu-lmdb/{relative}"
        assert item["revision"] == "a7071642fc902e0aa4af075cddb71626104ab6b1"
        assert (root / relative).read_text().startswith(
            "# VENDORED FROM szl-holdings/platform@" + item["revision"])


@pytest.mark.parametrize("namespace", ("a11oy", "killinchu"))
def test_parent_register_wires_child_with_sole_live_handles(tmp_path, monkeypatch, namespace):
    import szl_unay_routes as parent
    operator, token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", operator)
    monkeypatch.setenv("SZL_TEST_DELIVERY_PEER", token)
    peer = delivery.Peer("fixture", f"https://localhost/api/{namespace}/v2/khipu/replicate/batch/fixture",
                         "khipu", namespace, "SZL_TEST_DELIVERY_PEER")
    monkeypatch.setenv(routes.CONFIG_ENV, json.dumps([config(peer, direction) for direction in ("inbound", "outbound")]))
    monkeypatch.setattr(parent, "_pick_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(parent, "_restore_snapshot", lambda *_: False)
    monkeypatch.setattr(parent.szl_unay, "UnayStore", lambda **_: SimpleNamespace(backend="fixture"))
    opened, observed = [], []
    def open_store(**kwargs):
        store = KhipuLMDB(**kwargs, map_size=8 * 1024 * 1024)
        opened.append(store)
        return store
    monkeypatch.setattr(parent.szl_khipu_lmdb, "KhipuLMDB", open_store)
    def unavailable(source, mirror):
        assert opened == [source, mirror]
        observed.append((source, mirror))
        raise routes.StateOwnerUnavailable("qualified owner absent in fixture")
    monkeypatch.setattr(routes, "_state", unavailable)
    app = FastAPI()
    parent.register(app, ns=namespace)
    auth.install_gate(app)
    try:
        assert len(opened) == 2
        with TestClient(app) as client:
            for route, bearer in (("dispatch", operator), ("batch", token)):
                response = client.post(f"/api/{namespace}/v2/khipu/replicate/{route}/fixture",
                    content=b"{}", headers={"Authorization": "Bearer " + bearer})
                assert response.status_code == 503
                assert response.json()["reason"] == "QUALIFIED_STATE_OWNER_UNAVAILABLE"
        assert len(observed) == 2
        assert all(store.stats()["entries"] == 0 for store in opened)
    finally:
        for store in opened:
            store.close()
