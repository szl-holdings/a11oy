"""Native write guards work in every namespace without the A11oy middleware.

The actual router is registered with isolated store doubles. Producer fixtures
use temporary LMDB stores; no snapshots, signatures, or provider requests run.
"""

from pathlib import Path
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

import szl_unay_routes as subject
from szl_khipu_lmdb import KhipuLMDB
from szl_khipu_replicate import verify_inbound


OPERATOR = "fixture-unay-operator"
WRITE_PATHS = ("unay/remember", "khipu/lmdb/append", "khipu/replicate")


@pytest.fixture(params=("a11oy", "killinchu"))
def native_routes(request, tmp_path, monkeypatch):
    namespace = request.param
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", OPERATOR)
    monkeypatch.delenv("KHIPU_REPLICATION", raising=False)
    monkeypatch.setattr(subject, "_pick_data_dir", lambda: str(tmp_path))
    restore = Mock(return_value=False)
    monkeypatch.setattr(subject, "_restore_snapshot", restore)
    memory = SimpleNamespace(
        backend="fixture", remember=Mock(return_value={"receipt": "fixture-memory"}),
        stats=Mock(return_value={"entries": 0}), recall=Mock(return_value=[]),
        verify_chain=Mock(return_value={"ok": True}),
    )
    stores = {}

    def lmdb_store(*, path, organ, ns):
        assert Path(path).parent == tmp_path and ns == namespace
        store = SimpleNamespace(
            append=Mock(return_value={"receipt": "fixture-khipu"}),
            append_replicated=Mock(return_value={"receipt": {}, "duplicate": False}),
            get_by_receipt=Mock(return_value=None), get_by_seq=Mock(return_value=None),
            stats=Mock(return_value={"entries": 0}), verify=Mock(return_value={"ok": True}),
            tail=Mock(return_value=[]),
        )
        stores[organ] = store
        return store

    memory_factory = Mock(return_value=memory)
    monkeypatch.setattr(subject.szl_unay, "UnayStore", memory_factory)
    monkeypatch.setattr(subject.szl_khipu_lmdb, "KhipuLMDB", lmdb_store)
    inbound = Mock(return_value=True)
    monkeypatch.setattr(subject.szl_khipu_replicate, "verify_inbound", inbound)
    app = FastAPI()
    registration = subject.register(app, ns=namespace)
    assert registration["registered"] is True
    assert app.user_middleware == []
    memory_factory.assert_called_once_with(
        path=str(tmp_path / f"unay_{namespace}.sqlite"), organ="unay", ns=namespace)
    restore.assert_called_once_with(str(tmp_path / f"khipu_lmdb_{namespace}"), namespace)
    return SimpleNamespace(
        client=TestClient(app), prefix=f"/api/{namespace}/v2/", memory=memory,
        primary=stores["khipu"], mirror=stores["khipu-repl"], inbound=inbound,
    )


def assert_no_writes(routes):
    routes.memory.remember.assert_not_called()
    routes.primary.append.assert_not_called()
    routes.mirror.append.assert_not_called()
    routes.mirror.append_replicated.assert_not_called()
    routes.inbound.assert_not_called()
    routes.mirror.get_by_receipt.assert_not_called()


@pytest.mark.parametrize("path", WRITE_PATHS)
@pytest.mark.parametrize("credential", ("absent", "wrong", "unconfigured"))
def test_native_writes_refuse_before_body_or_store_access(
        native_routes, monkeypatch, path, credential):
    if credential == "unconfigured":
        monkeypatch.delenv("A11OY_CODE_ADMIN_KEY")
    headers = {} if credential == "absent" else {
        "Authorization": "Bearer " + (OPERATOR if credential == "unconfigured" else "wrong")}

    async def forbidden_json(self):
        pytest.fail("unauthorized writes must not parse the request body")

    monkeypatch.setattr(Request, "json", forbidden_json)
    response = native_routes.client.post(native_routes.prefix + path, content=b"not-json",
                                         headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["status"] == "BLOCKED"
    assert response.json()["credential_configured"] is (credential != "unconfigured")
    assert OPERATOR not in response.text
    assert_no_writes(native_routes)


def test_authorized_native_writes_reach_the_existing_handlers(native_routes):
    routes = native_routes
    headers = {"Authorization": "Bearer " + OPERATOR}
    response = routes.client.post(routes.prefix + "unay/remember", headers=headers,
                                  json={"text": "fixture", "meta": {"test": True}, "vector": [1]})
    assert response.status_code == 200 and response.json() == {"receipt": "fixture-memory"}
    routes.memory.remember.assert_called_once_with("fixture", meta={"test": True}, vector=[1])
    response = routes.client.post(routes.prefix + "khipu/lmdb/append", headers=headers,
                                  json={"action": "fixture", "payload": {"test": True}})
    assert response.status_code == 200 and response.json() == {"receipt": "fixture-khipu"}
    routes.primary.append.assert_called_once_with("fixture", payload={"test": True})
    receipt = {"digest": "fixture-origin"}
    response = routes.client.post(routes.prefix + "khipu/replicate", headers=headers,
                                  json={"receipts": [receipt]})
    assert response.status_code == 200
    assert response.json() == {"accepted": 1, "rejected": 0, "mirror_entries": 0}
    routes.inbound.assert_called_once_with(receipt)
    routes.mirror.append_replicated.assert_called_once_with(receipt)
    routes.mirror.get_by_receipt.assert_not_called()
    routes.mirror.append.assert_not_called()


def test_authorization_does_not_bypass_inbound_validation(native_routes):
    native_routes.inbound.return_value = False
    response = native_routes.client.post(
        native_routes.prefix + "khipu/replicate", json={"receipts": [{"digest": "invalid"}]},
        headers={"Authorization": "Bearer " + OPERATOR})
    assert response.status_code == 200 and response.json()["rejected"] == 1
    native_routes.mirror.append.assert_not_called()
    native_routes.mirror.append_replicated.assert_not_called()
    native_routes.mirror.get_by_receipt.assert_not_called()


@pytest.mark.parametrize("tampered", [False, True])
def test_authorized_replication_checks_actual_payload_before_store_access(
        native_routes, tmp_path, monkeypatch, tampered):
    producer = KhipuLMDB(str(tmp_path / "producer"))
    try:
        receipt = producer.append("fixture", payload={"nested": {"text": "Khipu \u03bb"}})
    finally:
        producer.close()
    if tampered:
        receipt["payload"]["nested"]["text"] = "substituted"
    monkeypatch.setattr(subject.szl_khipu_replicate, "verify_inbound", verify_inbound)
    response = native_routes.client.post(
        native_routes.prefix + "khipu/replicate", json={"receipts": [receipt]},
        headers={"Authorization": "Bearer " + OPERATOR})
    assert response.status_code == 200
    assert response.json() == {
        "accepted": 0 if tampered else 1, "rejected": 1 if tampered else 0,
        "mirror_entries": 0,
    }
    if tampered:
        native_routes.mirror.append.assert_not_called()
        native_routes.mirror.append_replicated.assert_not_called()
        native_routes.mirror.get_by_receipt.assert_not_called()
    else:
        native_routes.mirror.append_replicated.assert_called_once_with(receipt)
        native_routes.mirror.get_by_receipt.assert_not_called()
        native_routes.mirror.append.assert_not_called()


def test_origin_reconciliation_refusal_is_not_acknowledged(native_routes):
    native_routes.mirror.append_replicated.side_effect = ValueError("REPLICATION_RECONCILE_REQUIRED")
    response = native_routes.client.post(
        native_routes.prefix + "khipu/replicate", json={"receipts": [{"digest": "fixture"}]},
        headers={"Authorization": "Bearer " + OPERATOR})
    assert response.status_code == 200
    assert response.json() == {"accepted": 0, "rejected": 1, "mirror_entries": 0}
    native_routes.mirror.append.assert_not_called()


def test_unexpected_storage_failure_cannot_return_an_acknowledgement(native_routes):
    native_routes.mirror.append_replicated.side_effect = OSError("fixture storage unavailable")
    with pytest.raises(OSError, match="fixture storage unavailable"):
        native_routes.client.post(
            native_routes.prefix + "khipu/replicate", json={"receipts": [{"digest": "fixture"}]},
            headers={"Authorization": "Bearer " + OPERATOR})


@pytest.fixture(params=("a11oy", "killinchu"))
def real_mirror_routes(request, tmp_path, monkeypatch):
    """Run the actual receiver and LMDB implementation; reopen the same store."""
    namespace = request.param
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", OPERATOR)
    monkeypatch.delenv("KHIPU_REPLICATION", raising=False)
    monkeypatch.setattr(subject, "_pick_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(subject, "_restore_snapshot", lambda *_: False)
    monkeypatch.setattr(subject.szl_khipu_replicate, "verify_inbound", verify_inbound)
    monkeypatch.setattr(subject.szl_unay, "UnayStore", lambda **_: SimpleNamespace(backend="fixture"))
    primary = SimpleNamespace(stats=lambda: {"entries": 0})

    @contextmanager
    def open_routes(history=()):
        mirror = KhipuLMDB(str(tmp_path / f"khipu_repl_{namespace}"), organ="khipu-repl", ns=namespace)
        try:
            for origin in history:
                mirror.append("replicated", payload={"origin": origin})
            monkeypatch.setattr(subject.szl_khipu_lmdb, "KhipuLMDB",
                                lambda **kw: mirror if kw["organ"] == "khipu-repl" else primary)
            app = FastAPI()
            result = subject.register(app, ns=namespace)
            assert result["registered"] and result["replication_enabled"] is False
            with TestClient(app) as client:
                yield SimpleNamespace(
                    client=client, mirror=mirror, prefix=f"/api/{namespace}/v2/",
                    post=lambda origins: client.post(
                        f"/api/{namespace}/v2/khipu/replicate", json={"receipts": origins},
                        headers={"Authorization": "Bearer " + OPERATOR}),
                )
        finally:
            mirror.close()

    return open_routes


@pytest.fixture
def produced_origin(tmp_path):
    producer = KhipuLMDB(str(tmp_path / "actual-producer"))
    try:
        return producer.append("fixture", payload={"nested": {"text": "Khipu \u03bb"}})
    finally:
        producer.close()


def mirror_bytes(store):
    with store._env.begin() as txn:
        return list(txn.cursor())


def test_actual_receiver_replay_survives_reopen_with_one_wrapper(real_mirror_routes, produced_origin):
    with real_mirror_routes() as routes:
        first = routes.post([produced_origin, produced_origin])
        assert first.status_code == 200
        assert first.json() == {"accepted": 2, "rejected": 0, "mirror_entries": 1}
        initial = mirror_bytes(routes.mirror)
        wrapper = routes.mirror.get_by_seq(0)
        assert wrapper["payload"]["origin"] == produced_origin
        assert wrapper["digest"] != produced_origin["digest"]
    with real_mirror_routes() as reopened:
        replay = reopened.post([produced_origin])
        assert replay.json() == {"accepted": 1, "rejected": 0, "mirror_entries": 1}
        assert mirror_bytes(reopened.mirror) == initial


def test_actual_receiver_conflicting_metadata_is_rejected_without_writes(real_mirror_routes, produced_origin):
    with real_mirror_routes() as routes:
        first = routes.post([produced_origin])
        assert first.json()["accepted"] == 1
        initial = mirror_bytes(routes.mirror)
        conflict = deepcopy(produced_origin)
        conflict["auxiliary"] = {"changed": True}
        assert verify_inbound(conflict) is True  # Auxiliary metadata is not digest authenticated.
        response = routes.post([conflict])
        assert response.json() == {"accepted": 0, "rejected": 1, "mirror_entries": 1}
        assert mirror_bytes(routes.mirror) == initial


def test_actual_receiver_backfills_historical_duplicate_and_reads_never_migrate(
        real_mirror_routes, produced_origin):
    with real_mirror_routes(history=[produced_origin, produced_origin]) as routes:
        initial = mirror_bytes(routes.mirror)
        response = routes.client.get(routes.prefix + "khipu/replicate/status")
        assert response.status_code == 200
        assert mirror_bytes(routes.mirror) == initial
        response = routes.post([produced_origin])
        assert response.json() == {"accepted": 1, "rejected": 0, "mirror_entries": 2}
        assert routes.mirror.get_by_seq(0)["payload"]["origin"] == produced_origin
        with routes.mirror._env.begin() as txn:
            assert txn.get(("origin:" + produced_origin["digest"]).encode()) == b"0"


def test_actual_receiver_corrupt_history_refuses_without_partial_migration(
        real_mirror_routes, produced_origin):
    corrupt = deepcopy(produced_origin)
    corrupt["payload"]["nested"]["text"] = "tampered historical payload"
    with real_mirror_routes(history=[produced_origin, corrupt]) as routes:
        initial = mirror_bytes(routes.mirror)
        response = routes.post([produced_origin])
        assert response.json() == {"accepted": 0, "rejected": 1, "mirror_entries": 2}
        assert mirror_bytes(routes.mirror) == initial


def test_public_reads_do_not_require_operator_or_write(native_routes, monkeypatch):
    monkeypatch.delenv("A11OY_CODE_ADMIN_KEY")
    for path in ("unay/healthz", "unay/stats", "unay/recall?q=fixture", "unay/verify",
                 "khipu/lmdb/stats", "khipu/lmdb/verify", "khipu/lmdb/tail",
                 "khipu/replicate/status"):
        response = native_routes.client.get(native_routes.prefix + path)
        assert response.status_code == 200, (path, response.text)
    response = native_routes.client.post(native_routes.prefix + "unay/recall", json={"q": "fixture"})
    assert response.status_code == 200
    assert_no_writes(native_routes)
