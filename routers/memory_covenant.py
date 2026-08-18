# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Fail-closed PostgreSQL runtime adapter for the A11oy Memory Covenant.

The database schema is authoritative.  This module exposes only bounded status and
read/query operations; it does not create schema, retrieve credentials, write
memory, lease outbox work, sign receipts, or invoke an embedding/index provider.

Runtime activation requires all of the following external facts:

* ``A11OY_MEMORY_DATABASE_URL`` is supplied by an approved secret manager;
* the optional ``psycopg`` runtime dependency is installed;
* the connected principal is neither superuser nor BYPASSRLS;
* the principal is a member of ``a11oy_memory_app``; and
* ``public.memory_records`` exists with RLS and FORCE RLS enabled.

GET remains side-effect free.  The POST query is also database-read-only and does
not manufacture a receipt merely because data was read.
"""

import hashlib
import importlib.util
import json
import math
import os
import re
from datetime import date, datetime
from typing import Any, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

MAX_BODY = 64 * 1024
MAX_LIMIT = 100
IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MEMORY_CLASSES = {
    "working",
    "evidence",
    "policy",
    "decision",
    "outcome",
    "quarantine",
}


class CovenantUnavailable(RuntimeError):
    """Safe runtime-unavailable signal whose message contains no credential data."""

    def __init__(self, code: str, error_class: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.error_class = error_class


def _configured() -> bool:
    return bool((os.environ.get("A11OY_MEMORY_DATABASE_URL") or "").strip())


def _dependency_available() -> bool:
    try:
        return importlib.util.find_spec("psycopg") is not None
    except (ImportError, ValueError):
        return False


def _default_connect():
    dsn = (os.environ.get("A11OY_MEMORY_DATABASE_URL") or "").strip()
    if not dsn:
        raise CovenantUnavailable("DATABASE_NOT_CONFIGURED")
    try:
        import psycopg  # type: ignore
    except ImportError as exc:
        raise CovenantUnavailable("POSTGRES_DRIVER_UNAVAILABLE", type(exc).__name__) from exc
    try:
        return psycopg.connect(dsn, connect_timeout=5)
    except Exception as exc:
        # Never return the provider exception text: libpq errors may echo host/user data.
        raise CovenantUnavailable("DATABASE_CONNECTION_FAILED", type(exc).__name__) from exc


def _close(connection: Any) -> None:
    try:
        connection.rollback()
    except Exception:
        pass
    try:
        connection.close()
    except Exception:
        pass


def _inspect_principal(cursor: Any) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT current_user,
               role.rolsuper,
               role.rolbypassrls,
               pg_has_role(current_user, 'a11oy_memory_app', 'member'),
               to_regclass('public.memory_records') IS NOT NULL,
               COALESCE((
                   SELECT relrowsecurity
                     FROM pg_class
                    WHERE oid = to_regclass('public.memory_records')
               ), false),
               COALESCE((
                   SELECT relforcerowsecurity
                     FROM pg_class
                    WHERE oid = to_regclass('public.memory_records')
               ), false)
          FROM pg_roles AS role
         WHERE role.rolname = current_user
        """
    )
    row = cursor.fetchone()
    if not row:
        raise CovenantUnavailable("DATABASE_PRINCIPAL_NOT_FOUND")
    result = {
        "role": str(row[0]),
        "superuser": bool(row[1]),
        "bypass_rls": bool(row[2]),
        "memory_app_member": bool(row[3]),
        "schema_present": bool(row[4]),
        "rls_enabled": bool(row[5]),
        "force_rls": bool(row[6]),
    }
    result["safe"] = (
        not result["superuser"]
        and not result["bypass_rls"]
        and result["memory_app_member"]
        and result["schema_present"]
        and result["rls_enabled"]
        and result["force_rls"]
    )
    return result


def _require_safe_principal(principal: dict[str, Any]) -> None:
    if principal.get("superuser") or principal.get("bypass_rls"):
        raise CovenantUnavailable("UNSAFE_RUNTIME_PRINCIPAL")
    if not principal.get("memory_app_member"):
        raise CovenantUnavailable("MEMORY_APP_ROLE_REQUIRED")
    if not principal.get("schema_present"):
        raise CovenantUnavailable("MEMORY_COVENANT_SCHEMA_MISSING")
    if not principal.get("rls_enabled") or not principal.get("force_rls"):
        raise CovenantUnavailable("MEMORY_RECORDS_RLS_NOT_ENFORCED")


def _error(status_code: int, code: str, *, error_class: str | None = None) -> JSONResponse:
    payload: dict[str, Any] = {
        "ready": False,
        "accepted": False,
        "state": "BLOCKED" if status_code < 500 else "UNAVAILABLE",
        "code": code,
        "effectors": 0,
        "writes": 0,
        "credentials_exposed": False,
    }
    if error_class:
        payload["error_class"] = error_class
    return JSONResponse(payload, status_code=status_code)


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


async def _body(request: Request) -> dict[str, Any]:
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise ValueError("content-type must be application/json")
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            declared_size = int(declared)
        except ValueError as exc:
            raise ValueError("content-length must be a non-negative integer") from exc
        if declared_size < 0 or declared_size > MAX_BODY:
            raise ValueError("request body exceeds 64 KiB")
    raw = await request.body()
    if len(raw) > MAX_BODY:
        raise ValueError("request body exceeds 64 KiB")
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_closed_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("request body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("request body must be one JSON object")
    return payload


def _identity(value: str | None, field: str) -> str:
    candidate = (value or "").strip()
    if not IDENTITY_PATTERN.fullmatch(candidate):
        raise ValueError(f"{field} must match the bounded identity contract")
    return candidate


def _limit(value: Any) -> int:
    if value is None:
        return 25
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("limit must be an integer")
    if not 1 <= value <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    return value


def _memory_class(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in MEMORY_CLASSES:
        raise ValueError("memory_class is outside the closed contract")
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _query_digest(tenant_id: str, security_domain: str, memory_class: str | None, limit: int) -> str:
    body = json.dumps(
        {
            "tenant_id": tenant_id,
            "security_domain": security_domain,
            "memory_class": memory_class,
            "limit": limit,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def register(
    app: Any,
    ns: str = "a11oy",
    *,
    connect_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    prefix = f"/api/{ns}/v1/memory-covenant"
    if any(getattr(route, "path", None) == f"{prefix}/status" for route in app.router.routes):
        return {"ok": True, "state": "ALREADY_REGISTERED", "routes": []}
    connector = connect_factory or _default_connect

    @app.get(f"{prefix}/status", include_in_schema=False)
    async def status() -> JSONResponse:
        if connect_factory is None and not _configured():
            return _error(503, "DATABASE_NOT_CONFIGURED")
        if connect_factory is None and not _dependency_available():
            return _error(503, "POSTGRES_DRIVER_UNAVAILABLE")
        connection = None
        try:
            connection = connector()
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                principal = _inspect_principal(cursor)
            _require_safe_principal(principal)
            return JSONResponse(
                {
                    "ready": True,
                    "accepted": True,
                    "state": "READY",
                    "implementation": "REAL",
                    "database_authority": "POSTGRESQL",
                    "principal": principal,
                    "query_api": "READ_ONLY",
                    "write_api": "BLOCKED_SIGNER_AND_IDEMPOTENCY_BINDING_REQUIRED",
                    "index_worker": "BLOCKED_GENERATION_AND_WORKER_AUTHORITY_REQUIRED",
                    "receipt_policy": "NO_RECEIPT_ON_READ",
                    "effectors": 0,
                    "writes": 0,
                }
            )
        except CovenantUnavailable as exc:
            return _error(503, exc.code, error_class=exc.error_class)
        except Exception as exc:
            return _error(503, "MEMORY_COVENANT_STATUS_FAILED", error_class=type(exc).__name__)
        finally:
            if connection is not None:
                _close(connection)

    @app.post(f"{prefix}/query", include_in_schema=False)
    async def query(request: Request) -> JSONResponse:
        try:
            payload = await _body(request)
            tenant_id = _identity(request.headers.get("x-a11oy-tenant"), "x-a11oy-tenant")
            security_domain = _identity(
                request.headers.get("x-a11oy-security-domain"),
                "x-a11oy-security-domain",
            )
            limit = _limit(payload.get("limit"))
            memory_class = _memory_class(payload.get("memory_class"))
        except (TypeError, ValueError) as exc:
            return _error(422, "INVALID_MEMORY_QUERY", error_class=type(exc).__name__)

        if connect_factory is None and not _configured():
            return _error(503, "DATABASE_NOT_CONFIGURED")
        if connect_factory is None and not _dependency_available():
            return _error(503, "POSTGRES_DRIVER_UNAVAILABLE")

        connection = None
        try:
            connection = connector()
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                principal = _inspect_principal(cursor)
                _require_safe_principal(principal)
                cursor.execute(
                    "SELECT set_config('a11oy.tenant_id', %s, true), "
                    "set_config('a11oy.security_domain', %s, true)",
                    (tenant_id, security_domain),
                )
                cursor.execute(
                    """
                    SELECT memory_id,
                           schema_version,
                           memory_class,
                           compatibility_type,
                           classification,
                           lifecycle_state,
                           legal_hold,
                           expires_at,
                           active_index_generation,
                           content_sha256,
                           record_sha256,
                           version,
                           created_at,
                           updated_at
                      FROM memory_records
                     WHERE lifecycle_state IN ('ACTIVE', 'INDEXED')
                       AND (%s IS NULL OR memory_class = %s)
                     ORDER BY updated_at DESC, memory_id
                     LIMIT %s
                    """,
                    (memory_class, memory_class, limit),
                )
                rows = cursor.fetchall()
            keys = (
                "memory_id",
                "schema_version",
                "memory_class",
                "compatibility_type",
                "classification",
                "lifecycle_state",
                "legal_hold",
                "expires_at",
                "active_index_generation",
                "content_sha256",
                "record_sha256",
                "version",
                "created_at",
                "updated_at",
            )
            records = [
                {key: _json_value(value) for key, value in zip(keys, row)}
                for row in rows
            ]
            return JSONResponse(
                {
                    "ready": True,
                    "accepted": True,
                    "state": "READ_ONLY_RESULT",
                    "query_digest": _query_digest(
                        tenant_id, security_domain, memory_class, limit
                    ),
                    "count": len(records),
                    "records": records,
                    "content_included": False,
                    "receipt_policy": "NO_RECEIPT_ON_READ",
                    "audit_write": "NOT_PERFORMED",
                    "effectors": 0,
                    "writes": 0,
                }
            )
        except CovenantUnavailable as exc:
            return _error(503, exc.code, error_class=exc.error_class)
        except Exception as exc:
            return _error(503, "MEMORY_COVENANT_QUERY_FAILED", error_class=type(exc).__name__)
        finally:
            if connection is not None:
                _close(connection)

    return {
        "ok": True,
        "state": "REGISTERED",
        "routes": [f"{prefix}/status", f"{prefix}/query"],
        "effectors": 0,
        "writes": 0,
    }
