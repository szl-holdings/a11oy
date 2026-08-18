# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11

from pathlib import Path

import pytest

from routers.memory_index_worker import (
    AdapterFailure,
    WorkerConfig,
    WorkerContractError,
    run_once,
)

DIGEST = "a" * 64


class Column:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self.description = None
        self._one = None
        self._all = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params=None) -> None:
        normalized = " ".join(sql.split())
        self.connection.executed.append((normalized, params))
        self.description = None
        self._one = None
        self._all = []
        if "SELECT current_user" in normalized:
            if self.connection.unsafe_principal:
                self._one = ("owner", False, True, True, True, True)
            else:
                self._one = ("worker_login", False, False, True, True, True)
        elif "memory_lease_outbox" in normalized:
            names = [
                "event_id",
                "tenant_id",
                "security_domain",
                "memory_id",
                "generation_id",
                "event_type",
                "payload_json",
                "attempts",
            ]
            self.description = [Column(name) for name in names]
            self._all = [
                (
                    "event-1",
                    "tenant-1",
                    "domain-1",
                    "memory-1",
                    self.connection.event_generation,
                    self.connection.event_type,
                    {"content_uri": "cas://sha256/" + "b" * 64},
                    1,
                )
            ] if self.connection.return_event else []
        elif "FROM memory_index_generations" in normalized:
            self._one = (
                "provider",
                "model",
                "revision",
                8,
                "cosine",
                "l2",
                self.connection.generation_digest,
                self.connection.generation_status,
            )
        elif "memory_complete_outbox" in normalized:
            self.connection.completions.append(params)
            self._one = ("event-1",)

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._all)


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []
        self.completions: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.unsafe_principal = False
        self.return_event = True
        self.event_generation = "generation-1"
        self.event_type = "INDEX_UPSERT"
        self.generation_digest = DIGEST
        self.generation_status = "ACTIVE"

    def cursor(self):
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class SuccessfulAdapter:
    def __init__(self) -> None:
        self.upserts = []
        self.deletes = []

    def upsert(self, event):
        self.upserts.append(event)
        return {"index_revision": "rev-1", "accepted": True}

    def delete(self, event):
        self.deletes.append(event)
        return {"index_revision": "rev-1", "deleted": True}


class RetryAdapter(SuccessfulAdapter):
    def upsert(self, event):
        raise AdapterFailure("TRANSIENT_PROVIDER_FAILURE", retryable=True)


class SecretResultAdapter(SuccessfulAdapter):
    def upsert(self, event):
        return {"authorization": "forbidden"}


def _config(**overrides) -> WorkerConfig:
    values = {
        "worker_id": "worker-1",
        "generation_id": "generation-1",
        "generation_identity_digest": DIGEST,
        "lease_limit": 25,
        "lease_seconds": 30,
        "retry_seconds": 45,
    }
    values.update(overrides)
    return WorkerConfig(**values)


def test_successful_batch_leases_commits_and_settles_exact_worker_event() -> None:
    connection = FakeConnection()
    adapter = SuccessfulAdapter()
    result = run_once(lambda: connection, adapter, _config())
    assert result["state"] == "BATCH_COMPLETE"
    assert result["leased"] == 1
    assert result["done"] == 1
    assert result["retry"] == 0
    assert result["settlement_failed"] == 0
    assert len(adapter.upserts) == 1
    assert adapter.upserts[0].idempotency_key == "event-1"
    assert connection.completions
    completion = connection.completions[0]
    assert completion[0] == "worker-1"
    assert completion[1] == "event-1"
    assert completion[2] is True
    assert connection.commits >= 3
    assert connection.closed is True


def test_generation_identity_mismatch_fails_permanently_without_adapter_call() -> None:
    connection = FakeConnection()
    connection.generation_digest = "c" * 64
    adapter = SuccessfulAdapter()
    result = run_once(lambda: connection, adapter, _config())
    assert result["failed"] == 1
    assert not adapter.upserts
    completion = connection.completions[0]
    assert completion[2] is False
    assert completion[3] is False
    assert completion[5] == "GENERATION_IDENTITY_MISMATCH"


def test_transient_adapter_failure_is_bounded_retry() -> None:
    connection = FakeConnection()
    result = run_once(lambda: connection, RetryAdapter(), _config(retry_seconds=60))
    assert result["retry"] == 1
    completion = connection.completions[0]
    assert completion[2] is False
    assert completion[3] is True
    assert completion[5] == "TRANSIENT_PROVIDER_FAILURE"
    assert completion[6] == 60


def test_secret_shaped_adapter_result_is_not_persisted() -> None:
    connection = FakeConnection()
    result = run_once(lambda: connection, SecretResultAdapter(), _config())
    assert result["retry"] == 1
    completion = connection.completions[0]
    assert completion[2] is False
    assert completion[5] == "WorkerContractError"
    assert "forbidden" not in str(connection.completions)


def test_unsafe_worker_principal_fails_before_leasing() -> None:
    connection = FakeConnection()
    connection.unsafe_principal = True
    with pytest.raises(WorkerContractError, match="unsafe worker principal"):
        run_once(lambda: connection, SuccessfulAdapter(), _config())
    assert not any("memory_lease_outbox" in sql for sql, _ in connection.executed)
    assert connection.closed is True


def test_empty_queue_is_a_real_zero_work_batch() -> None:
    connection = FakeConnection()
    connection.return_event = False
    result = run_once(lambda: connection, SuccessfulAdapter(), _config())
    assert result["leased"] == 0
    assert result["done"] == 0
    assert result["outcomes"] == []


@pytest.mark.parametrize(
    "config",
    [
        _config(worker_id=""),
        _config(generation_identity_digest="bad"),
        _config(lease_limit=0),
        _config(lease_seconds=301),
        _config(retry_seconds=4),
    ],
)
def test_worker_config_fails_closed(config: WorkerConfig) -> None:
    with pytest.raises(WorkerContractError):
        config.validate()


def test_worker_sql_contract_is_bounded_and_not_public() -> None:
    completion = Path("migrations/20260817_memory_covenant_worker_completion.sql").read_text(encoding="utf-8")
    access = Path("migrations/20260817_memory_covenant_worker_generation_access.sql").read_text(encoding="utf-8")
    assert "SECURITY DEFINER" in completion
    assert "lease_owner = p_worker_id" in completion
    assert "p_retry_seconds < 1 OR p_retry_seconds > 3600" in completion
    assert "REVOKE ALL ON FUNCTION memory_complete_outbox" in completion
    assert "TO a11oy_memory_worker" in completion
    assert "GRANT SELECT ON memory_index_generations TO a11oy_memory_worker" in access
