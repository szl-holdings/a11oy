# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Bounded, provider-neutral Memory Covenant outbox worker.

This is a real queue/authority implementation, not an activated index provider.
The worker leases through the database SECURITY DEFINER contract, verifies the
active immutable index-generation identity, calls an explicitly injected adapter
with the outbox event id as its idempotency key, and settles that exact lease
through ``memory_complete_outbox``.

No adapter is selected from arbitrary environment import paths.  A production
entry point must instantiate a reviewed adapter in code and supply the approved
secret-managed database connection.  Without those bindings, activation remains
BLOCKED rather than falling back to a mock embedding or index.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

HEX64 = re.compile(r"^[0-9a-f]{64}$")
IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
EVENT_TYPES = {
    "INDEX_UPSERT",
    "INDEX_DELETE",
    "REINDEX_UPSERT",
    "REINDEX_DELETE",
}
SECRET_KEYS = {
    "authorization",
    "password",
    "secret",
    "secret_value",
    "token",
    "private_key",
}


class WorkerContractError(ValueError):
    pass


class AdapterFailure(RuntimeError):
    """Adapter failure with an explicit retry policy and no secret-bearing message."""

    def __init__(self, error_class: str, *, retryable: bool = True) -> None:
        super().__init__(error_class)
        self.error_class = _bounded_identity(error_class, "error_class")
        self.retryable = bool(retryable)


class IndexAdapter(Protocol):
    def upsert(self, event: "IndexEvent") -> Mapping[str, Any]: ...

    def delete(self, event: "IndexEvent") -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class WorkerConfig:
    worker_id: str
    generation_id: str
    generation_identity_digest: str
    lease_limit: int = 25
    lease_seconds: int = 30
    retry_seconds: int = 30

    def validate(self) -> None:
        _bounded_identity(self.worker_id, "worker_id")
        _bounded_identity(self.generation_id, "generation_id")
        if not HEX64.fullmatch(self.generation_identity_digest):
            raise WorkerContractError("generation_identity_digest must be lowercase SHA-256")
        if isinstance(self.lease_limit, bool) or not 1 <= self.lease_limit <= 100:
            raise WorkerContractError("lease_limit must be between 1 and 100")
        if isinstance(self.lease_seconds, bool) or not 5 <= self.lease_seconds <= 300:
            raise WorkerContractError("lease_seconds must be between 5 and 300")
        if isinstance(self.retry_seconds, bool) or not 5 <= self.retry_seconds <= 3600:
            raise WorkerContractError("retry_seconds must be between 5 and 3600")


@dataclass(frozen=True)
class IndexEvent:
    event_id: str
    tenant_id: str
    security_domain: str
    memory_id: str
    generation_id: str
    event_type: str
    payload: Mapping[str, Any]
    attempts: int

    @property
    def idempotency_key(self) -> str:
        return self.event_id


@dataclass(frozen=True)
class GenerationIdentity:
    provider: str
    model: str
    revision: str
    dimension: int
    metric: str
    normalization: str
    identity_digest: str
    status: str


def _bounded_identity(value: str, field: str) -> str:
    if not isinstance(value, str) or not IDENTITY.fullmatch(value):
        raise WorkerContractError(f"{field} violates the bounded identity contract")
    return value


def _safe_json(value: Any, path: str = "$") -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WorkerContractError(f"{path}: non-finite floats are forbidden")
        raise WorkerContractError(f"{path}: floats are forbidden in worker settlement metadata")
    if isinstance(value, list):
        if len(value) > 256:
            raise WorkerContractError(f"{path}: list exceeds the bounded result contract")
        return [_safe_json(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, Mapping):
        if len(value) > 128:
            raise WorkerContractError(f"{path}: object exceeds the bounded result contract")
        result: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                raise WorkerContractError(f"{path}: invalid result key")
            lowered = key.lower()
            if lowered in SECRET_KEYS or any(token in lowered for token in ("password", "private_key", "authorization")):
                raise WorkerContractError(f"{path}.{key}: secret-shaped result field is forbidden")
            result[key] = _safe_json(child, f"{path}.{key}")
        return result
    raise WorkerContractError(f"{path}: unsupported result type {type(value).__name__}")


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(_safe_json(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _description_names(cursor: Any) -> list[str]:
    names: list[str] = []
    for column in cursor.description or ():
        name = getattr(column, "name", None)
        if name is None and isinstance(column, Sequence) and column:
            name = column[0]
        if not isinstance(name, str):
            raise WorkerContractError("database cursor returned an invalid column description")
        names.append(name)
    return names


def _rows(cursor: Any) -> list[dict[str, Any]]:
    names = _description_names(cursor)
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _inspect_worker_principal(cursor: Any) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT current_user,
               role.rolsuper,
               role.rolbypassrls,
               pg_has_role(current_user, 'a11oy_memory_worker', 'member'),
               to_regprocedure('public.memory_lease_outbox(text,integer,integer)') IS NOT NULL,
               to_regprocedure('public.memory_complete_outbox(text,text,boolean,boolean,jsonb,text,integer)') IS NOT NULL
          FROM pg_roles AS role
         WHERE role.rolname = current_user
        """
    )
    row = cursor.fetchone()
    if not row:
        raise WorkerContractError("database worker principal was not found")
    result = {
        "role": str(row[0]),
        "superuser": bool(row[1]),
        "bypass_rls": bool(row[2]),
        "worker_member": bool(row[3]),
        "lease_function": bool(row[4]),
        "completion_function": bool(row[5]),
    }
    if result["superuser"] or result["bypass_rls"]:
        raise WorkerContractError("unsafe worker principal")
    if not result["worker_member"]:
        raise WorkerContractError("a11oy_memory_worker membership is required")
    if not result["lease_function"] or not result["completion_function"]:
        raise WorkerContractError("bounded worker database functions are unavailable")
    return result


def _event_from_row(row: Mapping[str, Any]) -> IndexEvent:
    event_type = str(row.get("event_type") or "")
    if event_type not in EVENT_TYPES:
        raise WorkerContractError("outbox event type is outside the closed contract")
    payload = row.get("payload_json")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise WorkerContractError("outbox payload is not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise WorkerContractError("outbox payload must be one object")
    attempts = row.get("attempts")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        raise WorkerContractError("outbox attempts must be a positive integer")
    return IndexEvent(
        event_id=_bounded_identity(str(row.get("event_id") or ""), "event_id"),
        tenant_id=_bounded_identity(str(row.get("tenant_id") or ""), "tenant_id"),
        security_domain=_bounded_identity(str(row.get("security_domain") or ""), "security_domain"),
        memory_id=_bounded_identity(str(row.get("memory_id") or ""), "memory_id"),
        generation_id=_bounded_identity(str(row.get("generation_id") or ""), "generation_id"),
        event_type=event_type,
        payload=dict(payload),
        attempts=attempts,
    )


def _generation(cursor: Any, event: IndexEvent) -> GenerationIdentity:
    cursor.execute(
        "SELECT set_config('a11oy.tenant_id', %s, true), "
        "set_config('a11oy.security_domain', %s, true)",
        (event.tenant_id, event.security_domain),
    )
    cursor.execute(
        """
        SELECT provider, model, revision, dimension, metric, normalization,
               identity_digest, status
          FROM memory_index_generations
         WHERE tenant_id = %s
           AND security_domain = %s
           AND generation_id = %s
        """,
        (event.tenant_id, event.security_domain, event.generation_id),
    )
    row = cursor.fetchone()
    if not row:
        raise AdapterFailure("GENERATION_NOT_FOUND", retryable=False)
    return GenerationIdentity(
        provider=str(row[0]),
        model=str(row[1]),
        revision=str(row[2]),
        dimension=int(row[3]),
        metric=str(row[4]),
        normalization=str(row[5]),
        identity_digest=str(row[6]),
        status=str(row[7]),
    )


def _verify_generation(config: WorkerConfig, event: IndexEvent, generation: GenerationIdentity) -> None:
    if event.generation_id != config.generation_id:
        raise AdapterFailure("EVENT_GENERATION_MISMATCH", retryable=False)
    if generation.status != "ACTIVE":
        raise AdapterFailure("GENERATION_NOT_ACTIVE", retryable=False)
    if generation.identity_digest != config.generation_identity_digest:
        raise AdapterFailure("GENERATION_IDENTITY_MISMATCH", retryable=False)
    if not HEX64.fullmatch(generation.identity_digest):
        raise AdapterFailure("GENERATION_DIGEST_INVALID", retryable=False)


def _lease(cursor: Any, config: WorkerConfig) -> list[IndexEvent]:
    cursor.execute(
        "SELECT * FROM memory_lease_outbox(%s, %s, %s)",
        (config.worker_id, config.lease_limit, config.lease_seconds),
    )
    return [_event_from_row(row) for row in _rows(cursor)]


def _settle(
    cursor: Any,
    config: WorkerConfig,
    event: IndexEvent,
    *,
    success: bool,
    retryable: bool,
    result: Mapping[str, Any],
    error_class: str | None,
) -> None:
    safe_result = _safe_json(dict(result))
    cursor.execute(
        "SELECT * FROM memory_complete_outbox(%s, %s, %s, %s, %s::jsonb, %s, %s)",
        (
            config.worker_id,
            event.event_id,
            success,
            retryable,
            json.dumps(safe_result, sort_keys=True, separators=(",", ":"), allow_nan=False),
            error_class,
            config.retry_seconds,
        ),
    )
    if cursor.fetchone() is None:
        raise WorkerContractError("database did not return the completed outbox row")


def _dispatch(adapter: IndexAdapter, event: IndexEvent) -> Mapping[str, Any]:
    if event.event_type in {"INDEX_UPSERT", "REINDEX_UPSERT"}:
        return adapter.upsert(event)
    return adapter.delete(event)


def run_once(
    connect_factory: Callable[[], Any],
    adapter: IndexAdapter,
    config: WorkerConfig,
) -> dict[str, Any]:
    """Lease and settle one bounded batch.

    Adapter calls occur after the lease transaction commits. The event id is the
    mandatory adapter idempotency key, so recovery after process interruption can
    safely replay the external operation before the database completion settles.
    """

    config.validate()
    connection = connect_factory()
    leased: list[IndexEvent] = []
    outcomes: list[dict[str, Any]] = []
    try:
        with connection.cursor() as cursor:
            _inspect_worker_principal(cursor)
            leased = _lease(cursor, config)
        connection.commit()

        for event in leased:
            error: AdapterFailure | None = None
            result: Mapping[str, Any] = {}
            try:
                with connection.cursor() as cursor:
                    generation = _generation(cursor, event)
                    _verify_generation(config, event, generation)
                connection.commit()
                adapter_result = _dispatch(adapter, event)
                if not isinstance(adapter_result, Mapping):
                    raise AdapterFailure("ADAPTER_RESULT_NOT_OBJECT", retryable=False)
                result = {
                    "adapter_result": _safe_json(dict(adapter_result)),
                    "event_digest": hashlib.sha256(
                        _canonical({
                            "event_id": event.event_id,
                            "generation_id": event.generation_id,
                            "event_type": event.event_type,
                            "idempotency_key": event.idempotency_key,
                        }).encode("utf-8")
                    ).hexdigest(),
                }
            except AdapterFailure as exc:
                error = exc
                connection.rollback()
            except Exception as exc:
                error = AdapterFailure(type(exc).__name__, retryable=True)
                connection.rollback()

            try:
                with connection.cursor() as cursor:
                    _settle(
                        cursor,
                        config,
                        event,
                        success=error is None,
                        retryable=error.retryable if error else False,
                        result=result,
                        error_class=error.error_class if error else None,
                    )
                connection.commit()
                outcomes.append({
                    "status": "DONE" if error is None else "RETRY" if error.retryable else "FAILED",
                    "event_digest": hashlib.sha256(event.event_id.encode("utf-8")).hexdigest(),
                    "error_class": error.error_class if error else None,
                })
            except Exception:
                connection.rollback()
                outcomes.append({
                    "status": "SETTLEMENT_FAILED",
                    "event_digest": hashlib.sha256(event.event_id.encode("utf-8")).hexdigest(),
                    "error_class": "DATABASE_SETTLEMENT_FAILED",
                })

        return {
            "state": "BATCH_COMPLETE",
            "leased": len(leased),
            "done": sum(1 for item in outcomes if item["status"] == "DONE"),
            "retry": sum(1 for item in outcomes if item["status"] == "RETRY"),
            "failed": sum(1 for item in outcomes if item["status"] == "FAILED"),
            "settlement_failed": sum(1 for item in outcomes if item["status"] == "SETTLEMENT_FAILED"),
            "outcomes": outcomes,
            "provider_activation": "EXPLICIT_INJECTED_ADAPTER_ONLY",
            "credentials_exposed": False,
        }
    finally:
        try:
            connection.rollback()
        except Exception:
            pass
        try:
            connection.close()
        except Exception:
            pass
