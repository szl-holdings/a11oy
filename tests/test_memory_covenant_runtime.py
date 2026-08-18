# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.memory_covenant import register


class FakeCursor:
    def __init__(self, *, safe: bool = True) -> None:
        self.safe = safe
        self.executed: list[tuple[str, object]] = []
        self._one = None
        self._all = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params=None) -> None:
        normalized = " ".join(sql.split())
        self.executed.append((normalized, params))
        if "SELECT current_user" in normalized:
            if self.safe:
                self._one = ("runtime_login", False, False, True, True, True, True)
            else:
                self._one = ("provider_owner", False, True, True, True, True, True)
        elif "FROM memory_records" in normalized:
            now = datetime(2026, 8, 11, tzinfo=timezone.utc)
            self._all = [
                (
                    "mem-1",
                    "szl-memory/2.0",
                    "evidence",
                    "EPISODIC",
                    "INTERNAL",
                    "INDEXED",
                    False,
                    None,
                    "generation-1",
                    "a" * 64,
                    "b" * 64,
                    1,
                    now,
                    now,
                )
            ]

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._all)


class FakeConnection:
    def __init__(self, *, safe: bool = True) -> None:
        self.cursor_instance = FakeCursor(safe=safe)
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def _client(*, safe: bool = True):
    connection = FakeConnection(safe=safe)
    app = FastAPI()
    result = register(app, connect_factory=lambda: connection)
    assert result["ok"] is True
    return TestClient(app), connection


def test_status_is_read_only_and_requires_safe_non_bypass_principal() -> None:
    client, connection = _client()
    response = client.get("/api/a11oy/v1/memory-covenant/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "READY"
    assert payload["database_authority"] == "POSTGRESQL"
    assert payload["principal"]["bypass_rls"] is False
    assert payload["write_api"].startswith("BLOCKED_")
    assert payload["writes"] == 0
    assert connection.rolled_back is True
    assert connection.closed is True
    assert not any(
        statement.startswith(("INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER "))
        for statement, _ in connection.cursor_instance.executed
    )


def test_status_blocks_provider_owner_bypass_identity() -> None:
    client, _ = _client(safe=False)
    response = client.get("/api/a11oy/v1/memory-covenant/status")
    assert response.status_code == 503
    assert response.json()["code"] == "UNSAFE_RUNTIME_PRINCIPAL"


def test_status_without_database_configuration_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("A11OY_MEMORY_DATABASE_URL", raising=False)
    app = FastAPI()
    register(app)
    response = TestClient(app).get("/api/a11oy/v1/memory-covenant/status")
    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "DATABASE_NOT_CONFIGURED"
    assert payload["credentials_exposed"] is False


def test_query_sets_transaction_local_identity_and_returns_metadata_only() -> None:
    client, connection = _client()
    response = client.post(
        "/api/a11oy/v1/memory-covenant/query",
        headers={
            "x-a11oy-tenant": "tenant-1",
            "x-a11oy-security-domain": "domain-1",
        },
        json={"limit": 5, "memory_class": "evidence"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "READ_ONLY_RESULT"
    assert payload["count"] == 1
    assert payload["content_included"] is False
    assert payload["receipt_policy"] == "NO_RECEIPT_ON_READ"
    assert payload["audit_write"] == "NOT_PERFORMED"
    assert "record_json" not in payload["records"][0]
    statements = [statement for statement, _ in connection.cursor_instance.executed]
    assert any("set_config('a11oy.tenant_id'" in statement for statement in statements)
    assert any("FROM memory_records" in statement for statement in statements)


def test_query_rejects_missing_tenant_scope() -> None:
    client, _ = _client()
    response = client.post(
        "/api/a11oy/v1/memory-covenant/query",
        headers={"x-a11oy-security-domain": "domain-1"},
        json={},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_MEMORY_QUERY"


def test_query_rejects_unbounded_limit_and_unknown_class() -> None:
    client, _ = _client()
    headers = {
        "x-a11oy-tenant": "tenant-1",
        "x-a11oy-security-domain": "domain-1",
    }
    assert client.post(
        "/api/a11oy/v1/memory-covenant/query",
        headers=headers,
        json={"limit": 101},
    ).status_code == 422
    assert client.post(
        "/api/a11oy/v1/memory-covenant/query",
        headers=headers,
        json={"memory_class": "invented"},
    ).status_code == 422


def test_query_rejects_duplicate_fields_and_non_finite_json() -> None:
    client, _ = _client()
    headers = {
        "content-type": "application/json",
        "x-a11oy-tenant": "tenant-1",
        "x-a11oy-security-domain": "domain-1",
    }
    duplicate = client.post(
        "/api/a11oy/v1/memory-covenant/query",
        headers=headers,
        content=b'{"limit":1,"limit":2}',
    )
    non_finite = client.post(
        "/api/a11oy/v1/memory-covenant/query",
        headers=headers,
        content=b'{"limit":NaN}',
    )
    assert duplicate.status_code == 422
    assert non_finite.status_code == 422


def test_registration_is_idempotent() -> None:
    app = FastAPI()
    first = register(app, connect_factory=lambda: FakeConnection())
    second = register(app, connect_factory=lambda: FakeConnection())
    assert first["state"] == "REGISTERED"
    assert second["state"] == "ALREADY_REGISTERED"
