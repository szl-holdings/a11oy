"""Native write guards work in every namespace without the A11oy middleware.

The actual router is registered with isolated store doubles. These tests do not
open databases, restore snapshots, sign receipts, or send provider requests.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

import szl_unay_routes as subject


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
    assert subject.register(app, ns=namespace)["registered"] is True
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
    routes.mirror.get_by_receipt.assert_called_once_with("fixture-origin")
    routes.mirror.append.assert_called_once_with("replicated", payload={"origin": receipt})


def test_authorization_does_not_bypass_inbound_validation(native_routes):
    native_routes.inbound.return_value = False
    response = native_routes.client.post(
        native_routes.prefix + "khipu/replicate", json={"receipts": [{"digest": "invalid"}]},
        headers={"Authorization": "Bearer " + OPERATOR})
    assert response.status_code == 200 and response.json()["rejected"] == 1
    native_routes.mirror.append.assert_not_called()
    native_routes.mirror.get_by_receipt.assert_not_called()


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
