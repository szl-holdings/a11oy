"""Tenant-safe SQLite state, idempotency, quota, and outbox storage for GDW."""

import base64
import contextlib
import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

import szl_dsse


SCHEMA_VERSION = 4
_SCHEMA_LOCK = threading.RLock()
_PROCESS_WRITE_LOCK = threading.RLock()
_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_TRUTHY = {"1", "true", "yes", "on"}
_JOURNAL_MODES = {"DELETE", "WAL"}
_SYNCHRONOUS_MODES = {"FULL", "NORMAL"}
_V1_TABLES = (
    "session_state",
    "requests",
    "receipts",
    "proof_outbox",
    "effect_outbox",
)


class GDWWorkspaceError(RuntimeError):
    """Base class for workspace failures that callers may map to safe responses."""


class GDWConfigurationError(GDWWorkspaceError):
    """The persistent workspace was not configured safely."""


class GDWSchemaError(GDWWorkspaceError):
    """The database schema cannot be used without an explicit operator action."""


class GDWLegacyMigrationRequired(GDWSchemaError):
    """Legacy rows cannot be assigned to an owner implicitly."""


class GDWQuotaExceeded(GDWWorkspaceError):
    """A transactional owner or global resource ceiling was reached."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class GDWLifecycleError(GDWWorkspaceError):
    """An expired or tombstoned object cannot be mutated or replayed."""


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise GDWConfigurationError(f"{name} must be an integer") from exc
    if value < minimum:
        raise GDWConfigurationError(f"{name} must be at least {minimum}")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_time(value: Optional[Any] = None) -> datetime:
    if value is None:
        return _utc_now()
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _text_time(value: Optional[Any] = None) -> str:
    return _normalise_time(value).isoformat()


def _json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _byte_len(value: Optional[str]) -> int:
    return len(value.encode("utf-8")) if value is not None else 0


def _checked_identity(value: Optional[str], field: str) -> str:
    candidate = (value or "").strip()
    if not _IDENTIFIER.fullmatch(candidate):
        raise GDWConfigurationError(
            f"{field} must contain 1-128 canonical identifier characters"
        )
    return candidate


@dataclass(frozen=True)
class GDWQuotaPolicy:
    """Hard limits enforced while the same SQLite write transaction is held."""

    owner_active_sessions: int = 1_000
    owner_active_requests: int = 100_000
    owner_pending_effects: int = 10_000
    owner_stored_bytes: int = 256 * 1024 * 1024
    global_active_sessions: int = 10_000
    global_active_requests: int = 1_000_000
    global_pending_effects: int = 100_000
    global_stored_bytes: int = 2 * 1024 * 1024 * 1024

    @classmethod
    def from_environment(cls) -> "GDWQuotaPolicy":
        return cls(
            owner_active_sessions=_env_int(
                "GDW_OWNER_MAX_ACTIVE_SESSIONS", cls.owner_active_sessions
            ),
            owner_active_requests=_env_int(
                "GDW_OWNER_MAX_ACTIVE_REQUESTS", cls.owner_active_requests
            ),
            owner_pending_effects=_env_int(
                "GDW_OWNER_MAX_PENDING_EFFECTS", cls.owner_pending_effects
            ),
            owner_stored_bytes=_env_int(
                "GDW_OWNER_MAX_STORED_BYTES", cls.owner_stored_bytes
            ),
            global_active_sessions=_env_int(
                "GDW_GLOBAL_MAX_ACTIVE_SESSIONS", cls.global_active_sessions
            ),
            global_active_requests=_env_int(
                "GDW_GLOBAL_MAX_ACTIVE_REQUESTS", cls.global_active_requests
            ),
            global_pending_effects=_env_int(
                "GDW_GLOBAL_MAX_PENDING_EFFECTS", cls.global_pending_effects
            ),
            global_stored_bytes=_env_int(
                "GDW_GLOBAL_MAX_STORED_BYTES", cls.global_stored_bytes
            ),
        )


_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE schema_meta (
        schema_name TEXT PRIMARY KEY,
        schema_version INTEGER NOT NULL,
        database_generation_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        upgraded_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE usage (
        namespace TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        active_sessions INTEGER NOT NULL DEFAULT 0 CHECK(active_sessions >= 0),
        active_requests INTEGER NOT NULL DEFAULT 0 CHECK(active_requests >= 0),
        pending_effects INTEGER NOT NULL DEFAULT 0 CHECK(pending_effects >= 0),
        stored_bytes INTEGER NOT NULL DEFAULT 0 CHECK(stored_bytes >= 0),
        updated_at TEXT NOT NULL,
        PRIMARY KEY(namespace, owner_id)
    )
    """,
    """
    CREATE TABLE session_state (
        namespace TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        step INTEGER NOT NULL CHECK(step >= 0),
        state_json TEXT,
        state_hash TEXT NOT NULL,
        lifecycle TEXT NOT NULL
            CHECK(lifecycle IN ('ACTIVE', 'EXPIRING', 'TOMBSTONED')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_accessed_at TEXT NOT NULL,
        expires_at TEXT,
        tombstoned_at TEXT,
        PRIMARY KEY(namespace, owner_id, session_id)
    )
    """,
    """
    CREATE TABLE requests (
        namespace TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        request_id TEXT NOT NULL,
        request_digest TEXT NOT NULL,
        session_id TEXT NOT NULL,
        response_json TEXT,
        response_hash TEXT NOT NULL,
        lifecycle TEXT NOT NULL CHECK(lifecycle IN ('ACTIVE', 'TOMBSTONED')),
        created_at TEXT NOT NULL,
        expires_at TEXT,
        tombstoned_at TEXT,
        PRIMARY KEY(namespace, owner_id, request_id)
    )
    """,
    """
    CREATE TABLE receipts (
        namespace TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        receipt_hash TEXT NOT NULL,
        request_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        step INTEGER NOT NULL,
        receipt_json TEXT,
        created_at TEXT NOT NULL,
        tombstoned_at TEXT,
        PRIMARY KEY(namespace, owner_id, receipt_hash),
        UNIQUE(namespace, owner_id, request_id),
        FOREIGN KEY(namespace, owner_id, request_id)
            REFERENCES requests(namespace, owner_id, request_id)
            DEFERRABLE INITIALLY DEFERRED
    )
    """,
    """
    CREATE TABLE proof_outbox (
        namespace TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        proposal_id TEXT NOT NULL,
        payload_json TEXT,
        payload_sha256 TEXT NOT NULL,
        status TEXT NOT NULL
            CHECK(status IN ('PENDING', 'EXPORTED', 'DEAD_LETTER')),
        artifact_json TEXT,
        created_at TEXT NOT NULL,
        exported_at TEXT,
        tombstoned_at TEXT,
        PRIMARY KEY(namespace, owner_id, proposal_id)
    )
    """,
    """
    CREATE TABLE effect_outbox (
        namespace TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        database_generation_id TEXT NOT NULL,
        request_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('receipt_projection', 'proof_export')),
        receipt_hash TEXT,
        payload_json TEXT,
        payload_sha256 TEXT NOT NULL,
        intent_sha256 TEXT NOT NULL,
        status TEXT NOT NULL
            CHECK(status IN ('PENDING', 'CLAIMED', 'EXPORTED', 'DEAD_LETTER')),
        attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
        max_attempts INTEGER NOT NULL CHECK(max_attempts > 0),
        next_attempt_at TEXT NOT NULL,
        lease_owner TEXT,
        lease_until TEXT,
        claim_generation INTEGER NOT NULL DEFAULT 0
            CHECK(claim_generation >= 0),
        last_error TEXT,
        artifact_json TEXT,
        created_at TEXT NOT NULL,
        exported_at TEXT,
        tombstoned_at TEXT,
        PRIMARY KEY(namespace, owner_id, idempotency_key),
        UNIQUE(namespace, owner_id, request_id, kind),
        FOREIGN KEY(namespace, owner_id, request_id)
            REFERENCES requests(namespace, owner_id, request_id)
            DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY(namespace, owner_id, receipt_hash)
            REFERENCES receipts(namespace, owner_id, receipt_hash)
            DEFERRABLE INITIALLY DEFERRED
    )
    """,
    """
    CREATE TABLE effect_recovery_audit (
        namespace TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        recovery_id TEXT NOT NULL,
        sequence INTEGER NOT NULL CHECK(sequence >= 0),
        credential_key_id TEXT NOT NULL,
        database_generation_id TEXT NOT NULL,
        request_sha256 TEXT NOT NULL,
        outcome_sha256 TEXT NOT NULL,
        governance_sha256 TEXT NOT NULL,
        receipt_sha256 TEXT NOT NULL,
        previous_receipt_sha256 TEXT NOT NULL,
        previous_chain_sha256 TEXT NOT NULL,
        chain_sha256 TEXT NOT NULL,
        dsse_envelope_sha256 TEXT NOT NULL,
        report_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(namespace, owner_id, recovery_id),
        UNIQUE(namespace, owner_id, sequence)
    )
    """,
    """
    CREATE INDEX idx_sessions_lifecycle
        ON session_state(namespace, owner_id, lifecycle, expires_at)
    """,
    """
    CREATE INDEX idx_requests_session
        ON requests(namespace, owner_id, session_id, lifecycle)
    """,
    """
    CREATE INDEX idx_receipts_session
        ON receipts(namespace, owner_id, session_id, step)
    """,
    """
    CREATE INDEX idx_proof_outbox_status
        ON proof_outbox(namespace, owner_id, status, created_at)
    """,
    """
    CREATE INDEX idx_effect_outbox_status
        ON effect_outbox(
            namespace, owner_id, status, next_attempt_at, lease_until, created_at
        )
    """,
)


class GDWWorkspace:
    """SQLite workspace bound to one stable owner and namespace by default."""

    def __init__(
        self,
        path: Optional[str] = None,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
        production: Optional[bool] = None,
        quota_policy: Optional[GDWQuotaPolicy] = None,
    ):
        self.production = (
            production
            if production is not None
            else os.environ.get("GDW_PRODUCTION_MODE", "").lower() in _TRUTHY
        )
        explicit_path = path is not None or bool(os.environ.get("GDW_DB_PATH"))
        configured = path or os.environ.get("GDW_DB_PATH", "output/gdw/gdw.sqlite3")
        self.path = Path(configured).resolve()
        if self.production and not explicit_path:
            raise GDWConfigurationError(
                "GDW_DB_PATH must be explicit in production mode"
            )
        if self.production and not self.path.is_file():
            raise GDWConfigurationError(
                "production GDW database must already exist and be provisioned"
            )

        configured_namespace = namespace or os.environ.get("GDW_NAMESPACE")
        configured_owner = (
            owner_id
            or os.environ.get("GDW_OWNER_ID")
            or os.environ.get("GDW_SERVICE_OWNER_ID")
        )
        if self.production and (not configured_namespace or not configured_owner):
            raise GDWConfigurationError(
                "stable GDW_NAMESPACE and GDW_OWNER_ID are required in production"
            )
        self.namespace = _checked_identity(configured_namespace or "a11oy", "namespace")
        self.owner_id = _checked_identity(configured_owner or "local-owner", "owner_id")
        self.journal_mode = os.environ.get("GDW_SQLITE_JOURNAL", "WAL").upper()
        if self.journal_mode not in _JOURNAL_MODES:
            raise GDWConfigurationError(
                "GDW_SQLITE_JOURNAL must be DELETE or WAL"
            )
        self.synchronous_mode = os.environ.get(
            "GDW_SQLITE_SYNCHRONOUS", "NORMAL"
        ).upper()
        if self.synchronous_mode not in _SYNCHRONOUS_MODES:
            raise GDWConfigurationError(
                "GDW_SQLITE_SYNCHRONOUS must be FULL or NORMAL"
            )
        self.quota_policy = quota_policy or GDWQuotaPolicy.from_environment()
        self.retention_seconds = _env_int("GDW_RETENTION_SECONDS", 30 * 24 * 60 * 60)
        self.tombstone_seconds = _env_int("GDW_TOMBSTONE_SECONDS", 90 * 24 * 60 * 60)
        self.effect_max_attempts = _env_int("GDW_EFFECT_MAX_ATTEMPTS", 8)
        self.effect_backoff_seconds = _env_int("GDW_EFFECT_BACKOFF_SECONDS", 5)
        self.database_generation_id = ""
        self._initialise()

    @staticmethod
    def schema_version() -> int:
        return SCHEMA_VERSION

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.path),
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        observed_journal = str(
            connection.execute(
                f"PRAGMA journal_mode={self.journal_mode}"
            ).fetchone()[0]
        ).upper()
        if observed_journal != self.journal_mode:
            connection.close()
            raise GDWConfigurationError(
                "SQLite journal mode does not match GDW_SQLITE_JOURNAL"
            )
        connection.execute(f"PRAGMA synchronous={self.synchronous_mode}")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }

    @staticmethod
    def _create_schema(
        connection: sqlite3.Connection,
        timestamp: str,
        generation_id: Optional[str] = None,
    ) -> str:
        generation = generation_id or uuid.uuid4().hex
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO schema_meta(
                schema_name, schema_version, database_generation_id,
                created_at, upgraded_at
            ) VALUES ('gdw', ?, ?, ?, ?)
            """,
            (SCHEMA_VERSION, generation, timestamp, timestamp),
        )
        return generation

    @staticmethod
    def _legacy_row_count(connection: sqlite3.Connection, tables: set) -> int:
        return sum(
            int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in _V1_TABLES
            if table in tables
        )

    def _migrate_v1(self, connection: sqlite3.Connection, tables: set) -> None:
        del tables
        timestamp = _text_time()
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        try:
            locked_tables = self._table_names(connection)
            nonempty = self._legacy_row_count(
                connection, locked_tables
            ) > 0
            if nonempty:
                raise GDWLegacyMigrationRequired(
                    "nonempty v1 workspace has no durable owner/provenance "
                    "binding; an offline evidence-preserving migration is required"
                )
            for index in (
                "idx_requests_session",
                "idx_receipts_session",
                "idx_proof_outbox_status",
                "idx_effect_outbox_status",
            ):
                connection.execute(f"DROP INDEX IF EXISTS {index}")
            for table in _V1_TABLES:
                if table in locked_tables:
                    connection.execute(f"ALTER TABLE {table} RENAME TO {table}_v1")
            self._create_schema(connection, timestamp)

            for table in reversed(_V1_TABLES):
                if table in locked_tables:
                    connection.execute(f"DROP TABLE {table}_v1")
            self._reconcile_usage(connection)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.execute("PRAGMA foreign_keys=ON")

    def _migrate_v2(self, connection: sqlite3.Connection) -> None:
        """Transactionally bind valid v2 effects to a new database generation."""

        from gdw_proofs import build_proof_payload

        timestamp = _text_time()
        generation = uuid.uuid4().hex
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        try:
            version = connection.execute(
                "SELECT schema_version FROM schema_meta WHERE schema_name = 'gdw'"
            ).fetchone()
            if version is None or int(version[0]) != 2:
                raise GDWSchemaError("GDW v2 migration source changed under lock")
            required = {
                "schema_meta",
                "usage",
                "session_state",
                "requests",
                "receipts",
                "proof_outbox",
                "effect_outbox",
            }
            missing = required - self._table_names(connection)
            if missing:
                raise GDWSchemaError(
                    "GDW v2 schema is incomplete: " + ", ".join(sorted(missing))
                )
            connection.execute("DROP INDEX IF EXISTS idx_effect_outbox_status")
            connection.execute(
                "ALTER TABLE effect_outbox RENAME TO effect_outbox_v2"
            )
            connection.execute(_SCHEMA_STATEMENTS[6])
            connection.execute(_SCHEMA_STATEMENTS[7])
            connection.execute(
                "ALTER TABLE schema_meta "
                "ADD COLUMN database_generation_id TEXT"
            )
            connection.execute(
                """
                UPDATE schema_meta
                SET schema_version = ?, database_generation_id = ?,
                    upgraded_at = ?
                WHERE schema_name = 'gdw'
                """,
                (SCHEMA_VERSION, generation, timestamp),
            )
            self.database_generation_id = generation
            online_migration_blockers = {
                "session_state": connection.execute(
                    "SELECT COUNT(*) FROM session_state "
                    "WHERE state_json IS NOT NULL"
                ).fetchone()[0],
                "receipts": connection.execute(
                    "SELECT COUNT(*) FROM receipts "
                    "WHERE receipt_json IS NOT NULL"
                ).fetchone()[0],
                "proof_outbox": connection.execute(
                    "SELECT COUNT(*) FROM proof_outbox "
                    "WHERE payload_json IS NOT NULL"
                ).fetchone()[0],
                "exported_effects": connection.execute(
                    "SELECT COUNT(*) FROM effect_outbox_v2 "
                    "WHERE status = 'EXPORTED' OR artifact_json IS NOT NULL"
                ).fetchone()[0],
                "receipt_effects": connection.execute(
                    "SELECT COUNT(*) FROM effect_outbox_v2 "
                    "WHERE kind = 'receipt_projection'"
                ).fetchone()[0],
            }
            blocked = sorted(
                name
                for name, count in online_migration_blockers.items()
                if int(count)
            )
            if blocked:
                raise GDWLegacyMigrationRequired(
                    "stateful v2 records require an offline "
                    "evidence-preserving migration: " + ",".join(blocked)
                )
            rows = connection.execute(
                "SELECT * FROM effect_outbox_v2 ORDER BY namespace, owner_id, "
                "created_at, idempotency_key"
            ).fetchall()
            for source in rows:
                if source["payload_json"] is None:
                    raise GDWLegacyMigrationRequired(
                        "compacted v2 effects require an offline "
                        "evidence-preserving migration"
                    )
                try:
                    payload = json.loads(source["payload_json"])
                except (TypeError, json.JSONDecodeError) as exc:
                    raise GDWLegacyMigrationRequired(
                        "v2 effect payload is not canonical JSON"
                    ) from exc
                namespace = str(source["namespace"])
                owner_id = str(source["owner_id"])
                request_id = str(source["request_id"])
                kind = str(source["kind"])
                source_payload_sha256 = self._effect_payload_digest(kind, payload)
                if source["payload_sha256"] != source_payload_sha256:
                    raise GDWLegacyMigrationRequired(
                        "v2 effect payload digest is invalid"
                    )
                source_key = self.scoped_effect_key(
                    namespace,
                    owner_id,
                    request_id,
                    kind,
                    source_payload_sha256,
                )
                if source["idempotency_key"] != source_key:
                    raise GDWLegacyMigrationRequired(
                        "v2 effect idempotency binding is invalid"
                    )
                if kind != "proof_export":
                    raise GDWLegacyMigrationRequired(
                        "v2 receipt effects require an offline "
                        "evidence-preserving migration"
                    )
                request_row = connection.execute(
                    """
                    SELECT request_digest, session_id, response_json,
                           response_hash
                    FROM requests
                    WHERE namespace = ? AND owner_id = ? AND request_id = ?
                    """,
                    (namespace, owner_id, request_id),
                ).fetchone()
                if request_row is None or request_row["response_json"] is None:
                    raise GDWLegacyMigrationRequired(
                        "v2 effect request anchor is unavailable"
                    )
                try:
                    response = json.loads(request_row["response_json"])
                    governance = response["audit"]["governance"]
                except (KeyError, TypeError, json.JSONDecodeError) as exc:
                    raise GDWLegacyMigrationRequired(
                        "v2 effect request anchor is invalid"
                    ) from exc
                if (
                    hashlib.sha256(
                        _json_text(response).encode("utf-8")
                    ).hexdigest()
                    != request_row["response_hash"]
                ):
                    raise GDWLegacyMigrationRequired(
                        "v2 effect request response hash is invalid"
                    )
                principal = response.get("principal")
                if not isinstance(principal, dict):
                    principal = {
                        "namespace": namespace,
                        "owner_id": owner_id,
                        "key_id": "UNAVAILABLE_V2",
                    }
                if (
                    principal.get("namespace") != namespace
                    or principal.get("owner_id") != owner_id
                ):
                    raise GDWLegacyMigrationRequired(
                        "v2 effect principal binding is invalid"
                    )
                legacy_proof = build_proof_payload(
                    proposal_id=response["proposal_id"],
                    request_id=response["request_id"],
                    request_digest=str(request_row["request_digest"]),
                    namespace=namespace,
                    owner_id=owner_id,
                    database_generation_id=str(
                        response.get("database_generation_id") or ""
                    ),
                    step=int(response["step"]),
                    before_hash=response["state_before_hash"],
                    after_hash=response["state_hash"],
                    decision=response["decision"],
                    scheduler_mode=response["scheduler_mode"],
                    receipt_hash=response.get("receipt_hash") or "",
                    dry_run=bool(response["dry_run"]),
                    governance=governance,
                )
                if "database_generation_id" not in payload:
                    for field in (
                        "request_digest",
                        "namespace",
                        "owner_id",
                        "database_generation_id",
                    ):
                        legacy_proof.pop(field, None)
                    legacy_proof.pop("payload_sha256", None)
                    legacy_proof["payload_sha256"] = hashlib.sha256(
                        _json_text(legacy_proof).encode("utf-8")
                    ).hexdigest()
                if payload != legacy_proof:
                    raise GDWLegacyMigrationRequired(
                        "v2 proof effect differs from persisted request"
                    )
                rebound_response = dict(response)
                rebound_response["request_id"] = request_id
                rebound_response["request_digest"] = str(
                    request_row["request_digest"]
                )
                rebound_response["session_id"] = str(request_row["session_id"])
                rebound_response["database_generation_id"] = generation
                rebound_response["principal"] = principal
                rebound_response["proposal_id"] = hashlib.sha256(
                    _json_text(
                        {
                            "schema": "szl.gdw.proposal-identity/v1",
                            "database_generation_id": generation,
                            "namespace": namespace,
                            "owner_id": owner_id,
                            "request_id": request_id,
                            "request_digest": str(
                                request_row["request_digest"]
                            ),
                            "state_before_hash": response[
                                "state_before_hash"
                            ],
                            "governance_evidence_sha256": hashlib.sha256(
                                _json_text(governance).encode("utf-8")
                            ).hexdigest(),
                        }
                    ).encode("utf-8")
                ).hexdigest()
                rebound_response_text = _json_text(rebound_response)
                connection.execute(
                    """
                    UPDATE requests
                    SET response_json = ?, response_hash = ?
                    WHERE namespace = ? AND owner_id = ? AND request_id = ?
                    """,
                    (
                        rebound_response_text,
                        hashlib.sha256(
                            rebound_response_text.encode("utf-8")
                        ).hexdigest(),
                        namespace,
                        owner_id,
                        request_id,
                    ),
                )
                request_anchor = self._request_anchor(
                    connection, namespace, owner_id, request_id
                )
                payload = self._expected_proof_payload(request_anchor)
                payload_sha256 = self._effect_payload_digest(kind, payload)
                canonical_key = self.scoped_effect_key(
                    namespace,
                    owner_id,
                    request_id,
                    kind,
                    payload_sha256,
                )
                receipt_hash = None
                intent_sha256 = self._canonical_effect_intent(
                    request_anchor,
                    namespace=namespace,
                    owner_id=owner_id,
                    request_id=request_id,
                    kind=kind,
                    payload_sha256=payload_sha256,
                    receipt_hash=receipt_hash,
                )
                status = source["status"]
                if status == "CLAIMED":
                    status = (
                        "DEAD_LETTER"
                        if int(source["attempts"]) >= int(source["max_attempts"])
                        else "PENDING"
                    )
                connection.execute(
                    """
                    INSERT INTO effect_outbox(
                        namespace, owner_id, idempotency_key,
                        database_generation_id, request_id, kind, receipt_hash,
                        payload_json, payload_sha256, intent_sha256, status,
                        attempts, max_attempts, next_attempt_at, lease_owner,
                        lease_until, claim_generation, last_error, artifact_json,
                        created_at, exported_at, tombstoned_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        0, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        namespace,
                        owner_id,
                        canonical_key,
                        generation,
                        request_id,
                        kind,
                        receipt_hash,
                        _json_text(payload),
                        payload_sha256,
                        intent_sha256,
                        status,
                        int(source["attempts"]),
                        int(source["max_attempts"]),
                        source["next_attempt_at"],
                        (
                            source["lease_owner"]
                            if status == "CLAIMED"
                            else None
                        ),
                        (
                            source["lease_until"]
                            if status == "CLAIMED"
                            else None
                        ),
                        source["last_error"],
                        source["artifact_json"],
                        source["created_at"],
                        source["exported_at"],
                        source["tombstoned_at"],
                    ),
                )
            connection.execute("DROP TABLE effect_outbox_v2")
            connection.execute(_SCHEMA_STATEMENTS[-1])
            self._reconcile_usage(connection)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.execute("PRAGMA foreign_keys=ON")

    @staticmethod
    def _migrate_v3(connection: sqlite3.Connection) -> None:
        """Add atomically bound recovery audit records without rebinding data."""

        timestamp = _text_time()
        connection.execute("BEGIN IMMEDIATE")
        try:
            version = connection.execute(
                "SELECT schema_version FROM schema_meta WHERE schema_name = 'gdw'"
            ).fetchone()
            if version is None or int(version[0]) != 3:
                raise GDWSchemaError("GDW v3 migration source changed under lock")
            connection.execute(_SCHEMA_STATEMENTS[7])
            connection.execute(
                """
                UPDATE schema_meta
                SET schema_version = ?, upgraded_at = ?
                WHERE schema_name = 'gdw'
                """,
                (SCHEMA_VERSION, timestamp),
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    @staticmethod
    def _validate_schema(connection: sqlite3.Connection) -> str:
        row = connection.execute(
            """
            SELECT schema_version, database_generation_id
            FROM schema_meta WHERE schema_name = 'gdw'
            """
        ).fetchone()
        if row is None or int(row[0]) != SCHEMA_VERSION:
            observed = None if row is None else int(row[0])
            raise GDWSchemaError(
                f"GDW schema version {observed!r} is unsupported; "
                f"expected {SCHEMA_VERSION}"
            )
        required = {
            "schema_meta",
            "usage",
            "session_state",
            "requests",
            "receipts",
            "proof_outbox",
            "effect_outbox",
            "effect_recovery_audit",
        }
        missing = required - GDWWorkspace._table_names(connection)
        if missing:
            raise GDWSchemaError(
                "GDW schema is incomplete: " + ", ".join(sorted(missing))
            )
        expected_columns = {
            "session_state": {"namespace", "owner_id", "lifecycle", "expires_at"},
            "requests": {"namespace", "owner_id", "lifecycle", "expires_at"},
            "effect_outbox": {
                "namespace",
                "owner_id",
                "max_attempts",
                "next_attempt_at",
                "database_generation_id",
                "intent_sha256",
                "claim_generation",
            },
            "effect_recovery_audit": {
                "namespace",
                "owner_id",
                "recovery_id",
                "sequence",
                "credential_key_id",
                "database_generation_id",
                "request_sha256",
                "outcome_sha256",
                "governance_sha256",
                "receipt_sha256",
                "previous_receipt_sha256",
                "previous_chain_sha256",
                "chain_sha256",
                "dsse_envelope_sha256",
                "report_json",
                "created_at",
            },
        }
        for table, expected in expected_columns.items():
            columns = {
                row["name"] for row in connection.execute(f"PRAGMA table_info({table})")
            }
            if not expected.issubset(columns):
                raise GDWSchemaError(
                    f"GDW schema table {table} is missing required columns"
                )
        generation_id = str(row["database_generation_id"] or "")
        if not re.fullmatch(r"[0-9a-f]{32}", generation_id):
            raise GDWSchemaError("GDW database generation id is invalid")
        return generation_id

    def _initialise(self) -> None:
        with _SCHEMA_LOCK:
            if not self.path.exists():
                if self.production:
                    raise GDWConfigurationError(
                        "production GDW database must already exist"
                    )
                self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                str(self.path), timeout=30.0, isolation_level=None
            )
            connection.row_factory = sqlite3.Row
            try:
                connection.execute("PRAGMA busy_timeout=30000")
                selected_journal = str(
                    connection.execute(
                        f"PRAGMA journal_mode={self.journal_mode}"
                    ).fetchone()[0]
                ).upper()
                if selected_journal != self.journal_mode:
                    raise GDWConfigurationError(
                        "SQLite journal mode does not match GDW_SQLITE_JOURNAL"
                    )
                connection.execute(f"PRAGMA synchronous={self.synchronous_mode}")
                connection.execute("PRAGMA foreign_keys=ON")
                tables = self._table_names(connection)
                if not tables:
                    if self.production:
                        raise GDWSchemaError(
                            "production GDW database has no provisioned schema"
                        )
                    connection.execute("BEGIN IMMEDIATE")
                    try:
                        self._create_schema(connection, _text_time())
                        connection.execute("COMMIT")
                    except Exception:
                        connection.execute("ROLLBACK")
                        raise
                elif "schema_meta" not in tables:
                    self._migrate_v1(connection, tables)
                else:
                    version = connection.execute(
                        "SELECT schema_version FROM schema_meta "
                        "WHERE schema_name = 'gdw'"
                    ).fetchone()
                    if version is not None and int(version[0]) == 2:
                        self._migrate_v2(connection)
                        version = (SCHEMA_VERSION,)
                    if version is not None and int(version[0]) == 3:
                        self._migrate_v3(connection)
                self.database_generation_id = self._validate_schema(connection)
            finally:
                connection.close()

    def _identity(
        self,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        return (
            _checked_identity(namespace or self.namespace, "namespace"),
            _checked_identity(owner_id or self.owner_id, "owner_id"),
        )

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with _PROCESS_WRITE_LOCK:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            finally:
                connection.close()

    def _usage_row(
        self, connection: sqlite3.Connection, namespace: str, owner_id: str
    ) -> sqlite3.Row:
        connection.execute(
            """
            INSERT OR IGNORE INTO usage(
                namespace, owner_id, active_sessions, active_requests,
                pending_effects, stored_bytes, updated_at
            ) VALUES (?, ?, 0, 0, 0, 0, ?)
            """,
            (namespace, owner_id, _text_time()),
        )
        return connection.execute(
            "SELECT * FROM usage WHERE namespace = ? AND owner_id = ?",
            (namespace, owner_id),
        ).fetchone()

    def _reserve_usage(
        self,
        connection: sqlite3.Connection,
        namespace: str,
        owner_id: str,
        *,
        sessions: int = 0,
        requests: int = 0,
        pending_effects: int = 0,
        stored_bytes: int = 0,
    ) -> None:
        owner = self._usage_row(connection, namespace, owner_id)
        current = {
            "sessions": int(owner["active_sessions"]),
            "requests": int(owner["active_requests"]),
            "pending_effects": int(owner["pending_effects"]),
            "stored_bytes": int(owner["stored_bytes"]),
        }
        deltas = {
            "sessions": sessions,
            "requests": requests,
            "pending_effects": pending_effects,
            "stored_bytes": stored_bytes,
        }
        owner_limits = {
            "sessions": self.quota_policy.owner_active_sessions,
            "requests": self.quota_policy.owner_active_requests,
            "pending_effects": self.quota_policy.owner_pending_effects,
            "stored_bytes": self.quota_policy.owner_stored_bytes,
        }
        global_limits = {
            "sessions": self.quota_policy.global_active_sessions,
            "requests": self.quota_policy.global_active_requests,
            "pending_effects": self.quota_policy.global_pending_effects,
            "stored_bytes": self.quota_policy.global_stored_bytes,
        }
        totals_row = connection.execute(
            """
            SELECT COALESCE(SUM(active_sessions), 0) AS sessions,
                   COALESCE(SUM(active_requests), 0) AS requests,
                   COALESCE(SUM(pending_effects), 0) AS pending_effects,
                   COALESCE(SUM(stored_bytes), 0) AS stored_bytes
            FROM usage
            """
        ).fetchone()
        for name, delta in deltas.items():
            proposed_owner = current[name] + delta
            if proposed_owner < 0:
                raise GDWSchemaError(f"usage counter underflow: {name}")
            if delta > 0 and proposed_owner > owner_limits[name]:
                raise GDWQuotaExceeded(f"OWNER_{name.upper()}_QUOTA")
            proposed_global = int(totals_row[name]) + delta
            if proposed_global < 0:
                raise GDWSchemaError(f"global usage counter underflow: {name}")
            if delta > 0 and proposed_global > global_limits[name]:
                raise GDWQuotaExceeded(f"GLOBAL_{name.upper()}_QUOTA")
        connection.execute(
            """
            UPDATE usage
            SET active_sessions = active_sessions + ?,
                active_requests = active_requests + ?,
                pending_effects = pending_effects + ?,
                stored_bytes = stored_bytes + ?,
                updated_at = ?
            WHERE namespace = ? AND owner_id = ?
            """,
            (
                sessions,
                requests,
                pending_effects,
                stored_bytes,
                _text_time(),
                namespace,
                owner_id,
            ),
        )

    def cached_request(
        self,
        connection: sqlite3.Connection,
        request_id: str,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        ns, owner = self._identity(namespace, owner_id)
        row = connection.execute(
            """
            SELECT namespace, owner_id, request_id, request_digest, session_id,
                   response_json, response_hash, lifecycle
            FROM requests
            WHERE namespace = ? AND owner_id = ? AND request_id = ?
            """,
            (ns, owner, request_id),
        ).fetchone()
        if row is None:
            return None
        if row["lifecycle"] != "ACTIVE" or row["response_json"] is None:
            raise GDWLifecycleError("idempotency record is outside its replay window")
        try:
            response = json.loads(row["response_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise GDWConfigurationError(
                "idempotency response is not canonical JSON"
            ) from exc
        if not isinstance(response, dict):
            raise GDWConfigurationError("idempotency response is not an object")
        observed_hash = hashlib.sha256(
            _json_text(response).encode("utf-8")
        ).hexdigest()
        expected_identity = {
            "request_id": row["request_id"],
            "request_digest": row["request_digest"],
            "session_id": row["session_id"],
            "database_generation_id": self.database_generation_id,
        }
        if observed_hash != row["response_hash"] or any(
            response.get(field) != expected
            for field, expected in expected_identity.items()
        ):
            raise GDWConfigurationError(
                "idempotency response digest or identity is invalid"
            )
        principal = response.get("principal")
        if not isinstance(principal, dict) or (
            principal.get("namespace") != row["namespace"]
            or principal.get("owner_id") != row["owner_id"]
        ):
            raise GDWConfigurationError(
                "idempotency response principal identity is invalid"
            )
        receipt_hash = response.get("receipt_hash")
        if receipt_hash:
            receipt_anchor = self._receipt_anchor(
                connection,
                row["namespace"],
                row["owner_id"],
                row["request_id"],
            )
            if (
                receipt_anchor["receipt_hash"] != receipt_hash
                or receipt_anchor["receipt"].get("session_id") != row["session_id"]
            ):
                raise GDWConfigurationError(
                    "idempotency response receipt binding is invalid"
                )
        return row["request_digest"], response

    def session_state(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        ns, owner = self._identity(namespace, owner_id)
        row = connection.execute(
            """
            SELECT namespace, owner_id, session_id, step, state_json, state_hash,
                   updated_at, lifecycle, expires_at
            FROM session_state
            WHERE namespace = ? AND owner_id = ? AND session_id = ?
            """,
            (ns, owner, session_id),
        ).fetchone()
        if row is None or row["lifecycle"] != "ACTIVE" or row["state_json"] is None:
            return None
        try:
            state = json.loads(row["state_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise GDWConfigurationError("session state is not canonical JSON") from exc
        if not isinstance(state, dict):
            raise GDWConfigurationError("session state is not an object")
        observed_hash = hashlib.sha256(
            _json_text(state).encode("utf-8")
        ).hexdigest()
        expected_identity = {
            "namespace": row["namespace"],
            "owner_id": row["owner_id"],
            "session_id": row["session_id"],
            "step": int(row["step"]),
            "database_generation_id": self.database_generation_id,
        }
        if observed_hash != row["state_hash"] or any(
            state.get(field) != expected
            for field, expected in expected_identity.items()
        ):
            raise GDWConfigurationError(
                "session state digest or identity is invalid"
            )
        return {
            "namespace": ns,
            "owner_id": owner,
            "session_id": session_id,
            "database_generation_id": self.database_generation_id,
            "step": int(row["step"]),
            "state": state,
            "state_hash": row["state_hash"],
            "updated_at": row["updated_at"],
            "expires_at": row["expires_at"],
            "lifecycle": row["lifecycle"],
        }

    def save_state(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        step: int,
        state: Dict[str, Any],
        state_hash: str,
        updated_at: str,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> None:
        ns, owner = self._identity(namespace, owner_id)
        if state.get("database_generation_id") != self.database_generation_id:
            raise GDWConfigurationError(
                "state database generation does not match workspace"
            )
        state_text = _json_text(state)
        timestamp = _text_time(updated_at)
        expiry = (
            expires_at
            or (
                _normalise_time(timestamp) + timedelta(seconds=self.retention_seconds)
            ).isoformat()
        )
        existing = connection.execute(
            """
            SELECT state_json, lifecycle FROM session_state
            WHERE namespace = ? AND owner_id = ? AND session_id = ?
            """,
            (ns, owner, session_id),
        ).fetchone()
        if existing is not None and existing["lifecycle"] != "ACTIVE":
            raise GDWLifecycleError("session is expired or tombstoned")
        self._reserve_usage(
            connection,
            ns,
            owner,
            sessions=1 if existing is None else 0,
            stored_bytes=_byte_len(state_text)
            - _byte_len(existing["state_json"] if existing else None),
        )
        connection.execute(
            """
            INSERT INTO session_state(
                namespace, owner_id, session_id, step, state_json, state_hash,
                lifecycle, created_at, updated_at, last_accessed_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?)
            ON CONFLICT(namespace, owner_id, session_id) DO UPDATE SET
                step = excluded.step,
                state_json = excluded.state_json,
                state_hash = excluded.state_hash,
                updated_at = excluded.updated_at,
                last_accessed_at = excluded.last_accessed_at,
                expires_at = excluded.expires_at
            """,
            (
                ns,
                owner,
                session_id,
                step,
                state_text,
                state_hash,
                timestamp,
                timestamp,
                timestamp,
                expiry,
            ),
        )

    def save_request(
        self,
        connection: sqlite3.Connection,
        request_id: str,
        request_digest: str,
        session_id: str,
        response: Dict[str, Any],
        response_hash: str,
        created_at: str,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> None:
        ns, owner = self._identity(namespace, owner_id)
        response_text = _json_text(response)
        canonical_response_hash = hashlib.sha256(
            response_text.encode("utf-8")
        ).hexdigest()
        if response_hash != canonical_response_hash:
            raise GDWConfigurationError(
                "request response hash does not match canonical response"
            )
        timestamp = _text_time(created_at)
        expiry = (
            expires_at
            or (
                _normalise_time(timestamp) + timedelta(seconds=self.retention_seconds)
            ).isoformat()
        )
        self._reserve_usage(
            connection,
            ns,
            owner,
            requests=1,
            stored_bytes=_byte_len(response_text),
        )
        connection.execute(
            """
            INSERT INTO requests(
                namespace, owner_id, request_id, request_digest, session_id,
                response_json, response_hash, lifecycle, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
            """,
            (
                ns,
                owner,
                request_id,
                request_digest,
                session_id,
                response_text,
                canonical_response_hash,
                timestamp,
                expiry,
            ),
        )

    def save_receipt(
        self,
        connection: sqlite3.Connection,
        receipt_hash: str,
        request_id: str,
        session_id: str,
        step: int,
        receipt: Dict[str, Any],
        created_at: str,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> None:
        ns, owner = self._identity(namespace, owner_id)
        receipt_text = _json_text(receipt)
        claimed_receipt_hash = str(receipt.get("receipt_hash") or "")
        unsigned_receipt = dict(receipt)
        unsigned_receipt.pop("receipt_hash", None)
        canonical_receipt_hash = hashlib.sha256(
            _json_text(unsigned_receipt).encode("utf-8")
        ).hexdigest()
        if (
            receipt_hash != claimed_receipt_hash
            or receipt_hash != canonical_receipt_hash
        ):
            raise GDWConfigurationError(
                "receipt hash does not match canonical receipt"
            )
        request_anchor = self._request_anchor(
            connection, ns, owner, request_id
        )
        expected_identity = {
            "namespace": ns,
            "owner_id": owner,
            "request_id": request_id,
            "session_id": session_id,
            "step": int(step),
            "database_generation_id": self.database_generation_id,
        }
        for field, expected in expected_identity.items():
            if receipt.get(field) != expected:
                raise GDWConfigurationError(
                    f"receipt {field} does not match persisted identity"
                )
        if request_anchor["session_id"] != session_id:
            raise GDWConfigurationError(
                "receipt session does not match persisted request"
            )
        if request_anchor["response"].get("receipt_hash") != receipt_hash:
            raise GDWConfigurationError(
                "receipt hash does not match persisted response"
            )
        self._reserve_usage(connection, ns, owner, stored_bytes=_byte_len(receipt_text))
        connection.execute(
            """
            INSERT INTO receipts(
                namespace, owner_id, receipt_hash, request_id, session_id,
                step, receipt_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ns,
                owner,
                canonical_receipt_hash,
                request_id,
                session_id,
                step,
                receipt_text,
                _text_time(created_at),
            ),
        )

    def save_proof_outbox(
        self,
        connection: sqlite3.Connection,
        proposal_id: str,
        payload: Dict[str, Any],
        payload_sha256: str,
        created_at: str,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> None:
        ns, owner = self._identity(namespace, owner_id)
        payload_text = _json_text(payload)
        self._reserve_usage(
            connection,
            ns,
            owner,
            pending_effects=1,
            stored_bytes=_byte_len(payload_text),
        )
        connection.execute(
            """
            INSERT INTO proof_outbox(
                namespace, owner_id, proposal_id, payload_json,
                payload_sha256, status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            (
                ns,
                owner,
                proposal_id,
                payload_text,
                payload_sha256,
                _text_time(created_at),
            ),
        )

    @staticmethod
    def scoped_effect_key(
        namespace: str,
        owner_id: str,
        request_id: str,
        kind: str,
        payload_sha256: str,
    ) -> str:
        if (
            len(payload_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in payload_sha256)
        ):
            raise GDWConfigurationError(
                "effect payload digest must be a lowercase SHA-256 value"
            )
        material = (
            f"{namespace}\x1f{owner_id}\x1f{request_id}\x1f"
            f"{kind}\x1f{payload_sha256}"
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _effect_payload_digest(kind: str, payload: Dict[str, Any]) -> str:
        if kind == "proof_export":
            claimed_digest = str(payload.get("payload_sha256") or "")
            unsigned = dict(payload)
            unsigned.pop("payload_sha256", None)
            observed_digest = hashlib.sha256(
                _json_text(unsigned).encode("utf-8")
            ).hexdigest()
            if claimed_digest != observed_digest:
                raise GDWConfigurationError(
                    "proof payload digest does not match canonical payload"
                )
            return claimed_digest
        if kind == "receipt_projection":
            return hashlib.sha256(
                _json_text(payload).encode("utf-8")
            ).hexdigest()
        raise GDWConfigurationError("unsupported effect kind")

    @staticmethod
    def artifact_binding_errors(
        row: Dict[str, Any],
        artifact: Any,
    ) -> list[str]:
        errors = []
        if not isinstance(artifact, dict):
            return ["artifact_not_object"]
        identity = str(row.get("intent_sha256") or "")
        owner_id = str(row.get("owner_id") or "")
        kind = str(row.get("kind") or "")
        if artifact.get("artifact_identity") != identity:
            errors.append("artifact_identity_mismatch")
        if artifact.get("immutable") is not True:
            errors.append("artifact_not_immutable")
        owner_scope = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:32]
        if artifact.get("owner_scope") != owner_scope:
            errors.append("artifact_owner_scope_mismatch")
        configured_root = (
            os.environ.get("GDW_PROOF_DIR", "output/proofs")
            if kind == "proof_export"
            else os.environ.get(
                "GDW_RECEIPT_PROJECTION_DIR",
                "output/gdw/receipts",
            )
        )
        if kind not in {"proof_export", "receipt_projection"}:
            errors.append("artifact_kind_invalid")
            return errors
        expected_path = (
            Path(configured_root).resolve()
            / owner_scope
            / f"{identity}.json"
        )
        try:
            observed_path = Path(str(artifact.get("path") or "")).resolve()
        except (OSError, RuntimeError, ValueError):
            errors.append("artifact_path_invalid")
            return errors
        if observed_path != expected_path:
            errors.append("artifact_path_mismatch")
        if not observed_path.is_file():
            errors.append("artifact_missing")
            return errors
        try:
            observed_sha256 = hashlib.sha256(
                observed_path.read_bytes()
            ).hexdigest()
        except OSError:
            errors.append("artifact_unreadable")
            return errors
        if artifact.get("sha256") != observed_sha256:
            errors.append("artifact_digest_mismatch")
        return errors

    def _request_anchor(
        self,
        connection: sqlite3.Connection,
        namespace: str,
        owner_id: str,
        request_id: str,
    ) -> Dict[str, Any]:
        row = connection.execute(
            """
            SELECT request_digest, session_id, response_json, response_hash,
                   lifecycle
            FROM requests
            WHERE namespace = ? AND owner_id = ? AND request_id = ?
            """,
            (namespace, owner_id, request_id),
        ).fetchone()
        if row is None or row["response_json"] is None:
            raise GDWConfigurationError("effect request anchor is unavailable")
        try:
            response = json.loads(row["response_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise GDWConfigurationError(
                "effect request anchor is not canonical JSON"
            ) from exc
        observed_hash = hashlib.sha256(
            _json_text(response).encode("utf-8")
        ).hexdigest()
        if observed_hash != row["response_hash"]:
            raise GDWConfigurationError("effect request response hash is invalid")
        if response.get("request_digest") != row["request_digest"]:
            raise GDWConfigurationError(
                "effect request digest identity is invalid"
            )
        if response.get("database_generation_id") != self.database_generation_id:
            raise GDWConfigurationError(
                "effect request database generation is invalid"
            )
        try:
            proposal_material = {
                "schema": "szl.gdw.proposal-identity/v1",
                "database_generation_id": self.database_generation_id,
                "namespace": response["principal"]["namespace"],
                "owner_id": response["principal"]["owner_id"],
                "request_id": response["request_id"],
                "request_digest": row["request_digest"],
                "state_before_hash": response["state_before_hash"],
                "governance_evidence_sha256": hashlib.sha256(
                    _json_text(response["audit"]["governance"]).encode("utf-8")
                ).hexdigest(),
            }
        except (KeyError, TypeError) as exc:
            raise GDWConfigurationError(
                "effect request proposal identity is unavailable"
            ) from exc
        expected_proposal_id = hashlib.sha256(
            _json_text(proposal_material).encode("utf-8")
        ).hexdigest()
        if response.get("proposal_id") != expected_proposal_id:
            raise GDWConfigurationError(
                "effect request proposal identity is invalid"
            )
        return {
            "request_digest": row["request_digest"],
            "session_id": row["session_id"],
            "response_hash": row["response_hash"],
            "response": response,
            "lifecycle": row["lifecycle"],
        }

    def _receipt_anchor(
        self,
        connection: sqlite3.Connection,
        namespace: str,
        owner_id: str,
        request_id: str,
    ) -> Dict[str, Any]:
        row = connection.execute(
            """
            SELECT receipt_hash, request_id, session_id, step, receipt_json
            FROM receipts
            WHERE namespace = ? AND owner_id = ? AND request_id = ?
            """,
            (namespace, owner_id, request_id),
        ).fetchone()
        if row is None or row["receipt_json"] is None:
            raise GDWConfigurationError("effect receipt anchor is unavailable")
        try:
            receipt = json.loads(row["receipt_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise GDWConfigurationError(
                "effect receipt anchor is not canonical JSON"
            ) from exc
        claimed = str(receipt.get("receipt_hash") or "")
        unsigned = dict(receipt)
        unsigned.pop("receipt_hash", None)
        observed = hashlib.sha256(
            _json_text(unsigned).encode("utf-8")
        ).hexdigest()
        if claimed != row["receipt_hash"] or observed != row["receipt_hash"]:
            raise GDWConfigurationError("effect receipt anchor hash is invalid")
        expected_identity = {
            "namespace": namespace,
            "owner_id": owner_id,
            "request_id": row["request_id"],
            "session_id": row["session_id"],
            "step": int(row["step"]),
            "database_generation_id": self.database_generation_id,
        }
        for field, expected in expected_identity.items():
            if receipt.get(field) != expected:
                raise GDWConfigurationError(
                    f"effect receipt {field} identity is invalid"
                )
        return {"receipt_hash": row["receipt_hash"], "receipt": receipt}

    @staticmethod
    def _expected_proof_payload(
        request_anchor: Dict[str, Any],
    ) -> Dict[str, Any]:
        from gdw_proofs import build_proof_payload

        response = request_anchor["response"]
        try:
            return build_proof_payload(
                proposal_id=response["proposal_id"],
                request_id=response["request_id"],
                request_digest=request_anchor["request_digest"],
                namespace=response["principal"]["namespace"],
                owner_id=response["principal"]["owner_id"],
                database_generation_id=response["database_generation_id"],
                step=int(response["step"]),
                before_hash=response["state_before_hash"],
                after_hash=response["state_hash"],
                decision=response["decision"],
                scheduler_mode=response["scheduler_mode"],
                receipt_hash=response.get("receipt_hash") or "",
                dry_run=bool(response["dry_run"]),
                governance=response["audit"]["governance"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GDWConfigurationError(
                "persisted request cannot reconstruct proof intent"
            ) from exc

    def _canonical_effect_intent(
        self,
        request_anchor: Dict[str, Any],
        *,
        namespace: str,
        owner_id: str,
        request_id: str,
        kind: str,
        payload_sha256: str,
        receipt_hash: Optional[str],
    ) -> str:
        material = {
            "schema": "szl.gdw.effect-intent/v1",
            "database_generation_id": self.database_generation_id,
            "namespace": namespace,
            "owner_id": owner_id,
            "request_id": request_id,
            "request_digest": request_anchor["request_digest"],
            "session_id": request_anchor["session_id"],
            "response_hash": request_anchor["response_hash"],
            "kind": kind,
            "payload_sha256": payload_sha256,
            "receipt_hash": receipt_hash,
        }
        return hashlib.sha256(_json_text(material).encode("utf-8")).hexdigest()

    @classmethod
    def effect_binding_errors(cls, row: Dict[str, Any]) -> list[str]:
        """Validate row-local bindings; persisted anchors are checked separately."""

        errors = []
        payload = row.get("payload")
        if not isinstance(payload, dict):
            return ["payload_not_object"]
        kind = str(row.get("kind") or "")
        request_id = str(row.get("request_id") or "")
        namespace = str(row.get("namespace") or "")
        owner_id = str(row.get("owner_id") or "")
        if kind == "proof_export":
            claimed_digest = str(payload.get("payload_sha256") or "")
            unsigned = dict(payload)
            unsigned.pop("payload_sha256", None)
            observed_digest = hashlib.sha256(
                _json_text(unsigned).encode("utf-8")
            ).hexdigest()
            if claimed_digest != observed_digest:
                errors.append("proof_payload_digest_invalid")
            payload_digest = claimed_digest
            principal = payload.get("governance", {}).get("principal", {})
        elif kind == "receipt_projection":
            payload_digest = hashlib.sha256(
                _json_text(payload).encode("utf-8")
            ).hexdigest()
            principal = payload
        else:
            return ["unsupported_effect_kind"]
        if row.get("payload_sha256") != payload_digest:
            errors.append("row_payload_digest_mismatch")
        if payload.get("request_id") != request_id:
            errors.append("request_identity_mismatch")
        if payload.get("database_generation_id") != row.get(
            "database_generation_id"
        ):
            errors.append("database_generation_payload_mismatch")
        if not isinstance(principal, dict) or (
            principal.get("namespace") != namespace
            or principal.get("owner_id") != owner_id
        ):
            errors.append("principal_identity_mismatch")
        try:
            expected_key = cls.scoped_effect_key(
                namespace,
                owner_id,
                request_id,
                kind,
                payload_digest,
            )
        except GDWConfigurationError:
            errors.append("payload_digest_invalid")
        else:
            if row.get("idempotency_key") != expected_key:
                errors.append("idempotency_key_mismatch")
        return errors

    def _connection_effect_binding_errors(
        self,
        connection: sqlite3.Connection,
        row: Dict[str, Any],
    ) -> list[str]:
        errors = self.effect_binding_errors(row)
        try:
            request_anchor = self._request_anchor(
                connection,
                str(row.get("namespace") or ""),
                str(row.get("owner_id") or ""),
                str(row.get("request_id") or ""),
            )
        except GDWConfigurationError as exc:
            return sorted(set(errors + [str(exc)]))
        payload = row.get("payload")
        kind = str(row.get("kind") or "")
        receipt_hash = None
        try:
            if kind == "receipt_projection":
                receipt_anchor = self._receipt_anchor(
                    connection,
                    row["namespace"],
                    row["owner_id"],
                    row["request_id"],
                )
                receipt_hash = receipt_anchor["receipt_hash"]
                if payload != receipt_anchor["receipt"]:
                    errors.append("receipt_payload_anchor_mismatch")
            elif kind == "proof_export":
                expected_proof = self._expected_proof_payload(request_anchor)
                if payload != expected_proof:
                    errors.append("proof_payload_anchor_mismatch")
                claimed_receipt_hash = str(
                    expected_proof.get("delta_update_receipt_hash") or ""
                )
                if claimed_receipt_hash:
                    receipt_anchor = self._receipt_anchor(
                        connection,
                        row["namespace"],
                        row["owner_id"],
                        row["request_id"],
                    )
                    receipt_hash = receipt_anchor["receipt_hash"]
                    if receipt_hash != claimed_receipt_hash:
                        errors.append("proof_receipt_anchor_mismatch")
            else:
                errors.append("unsupported_effect_kind")
        except GDWConfigurationError as exc:
            errors.append(str(exc))
        if row.get("receipt_hash") != receipt_hash:
            errors.append("receipt_hash_anchor_mismatch")
        if row.get("database_generation_id") != self.database_generation_id:
            errors.append("database_generation_mismatch")
        expected_intent = self._canonical_effect_intent(
            request_anchor,
            namespace=row["namespace"],
            owner_id=row["owner_id"],
            request_id=row["request_id"],
            kind=kind,
            payload_sha256=str(row.get("payload_sha256") or ""),
            receipt_hash=receipt_hash,
        )
        if row.get("intent_sha256") != expected_intent:
            errors.append("effect_intent_mismatch")
        return sorted(set(errors))

    def effect_binding_errors_for_row(self, row: Dict[str, Any]) -> list[str]:
        connection = self._connect()
        try:
            return self._connection_effect_binding_errors(connection, row)
        finally:
            connection.close()

    def save_effect_outbox(
        self,
        connection: sqlite3.Connection,
        request_id: str,
        kind: str,
        payload: Dict[str, Any],
        payload_sha256: str,
        idempotency_key: Optional[str],
        created_at: str,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
        max_attempts: Optional[int] = None,
    ) -> str:
        ns, owner = self._identity(namespace, owner_id)
        payload_text = _json_text(payload)
        canonical_payload_sha256 = self._effect_payload_digest(kind, payload)
        if payload_sha256 != canonical_payload_sha256:
            raise GDWConfigurationError(
                "effect payload digest does not match canonical payload"
            )
        request_anchor = self._request_anchor(
            connection, ns, owner, request_id
        )
        receipt_hash = None
        if kind == "receipt_projection":
            receipt_anchor = self._receipt_anchor(
                connection, ns, owner, request_id
            )
            receipt_hash = receipt_anchor["receipt_hash"]
            if payload != receipt_anchor["receipt"]:
                raise GDWConfigurationError(
                    "receipt projection differs from persisted receipt"
                )
        elif kind == "proof_export":
            expected_proof = self._expected_proof_payload(request_anchor)
            if payload != expected_proof:
                raise GDWConfigurationError(
                    "proof export differs from persisted request intent"
                )
            claimed_receipt_hash = str(
                expected_proof.get("delta_update_receipt_hash") or ""
            )
            if claimed_receipt_hash:
                receipt_anchor = self._receipt_anchor(
                    connection, ns, owner, request_id
                )
                receipt_hash = receipt_anchor["receipt_hash"]
                if receipt_hash != claimed_receipt_hash:
                    raise GDWConfigurationError(
                        "proof receipt differs from persisted receipt"
                    )
        else:
            raise GDWConfigurationError("unsupported effect kind")
        intent_sha256 = self._canonical_effect_intent(
            request_anchor,
            namespace=ns,
            owner_id=owner,
            request_id=request_id,
            kind=kind,
            payload_sha256=canonical_payload_sha256,
            receipt_hash=receipt_hash,
        )
        canonical_key = self.scoped_effect_key(
            ns,
            owner,
            request_id,
            kind,
            canonical_payload_sha256,
        )
        if idempotency_key and self.production and idempotency_key != canonical_key:
            raise GDWConfigurationError(
                "effect idempotency key is not bound to identity and payload"
            )
        key = canonical_key
        bounded_attempts = max_attempts or self.effect_max_attempts
        if bounded_attempts < 1:
            raise GDWConfigurationError("max_attempts must be positive")
        timestamp = _text_time(created_at)
        self._reserve_usage(
            connection,
            ns,
            owner,
            pending_effects=1,
            stored_bytes=_byte_len(payload_text),
        )
        connection.execute(
            """
            INSERT INTO effect_outbox(
                namespace, owner_id, idempotency_key, database_generation_id,
                request_id, kind, receipt_hash, payload_json, payload_sha256,
                intent_sha256, status, attempts, max_attempts,
                next_attempt_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0, ?, ?, ?)
            """,
            (
                ns,
                owner,
                key,
                self.database_generation_id,
                request_id,
                kind,
                receipt_hash,
                payload_text,
                canonical_payload_sha256,
                intent_sha256,
                bounded_attempts,
                timestamp,
                timestamp,
            ),
        )
        return key

    def claim_effects(
        self,
        worker_id: str,
        limit: int = 100,
        lease_seconds: int = 300,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
        now: Optional[Any] = None,
    ) -> list:
        if not worker_id or len(worker_id) > 128:
            raise ValueError("worker_id must contain 1-128 characters")
        ns, owner = self._identity(namespace, owner_id)
        bounded = max(1, min(int(limit), 10_000))
        lease = max(1, min(int(lease_seconds), 3_600))
        current = _normalise_time(now)
        now_text = current.isoformat()
        lease_until = (current + timedelta(seconds=lease)).isoformat()
        claimed = []
        with self.transaction() as connection:
            expired_terminal = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM effect_outbox
                    WHERE namespace = ? AND owner_id = ? AND status = 'CLAIMED'
                          AND lease_until <= ? AND attempts >= max_attempts
                    """,
                    (ns, owner, now_text),
                ).fetchone()[0]
            )
            if expired_terminal:
                connection.execute(
                    """
                    UPDATE effect_outbox
                    SET status = 'DEAD_LETTER', lease_owner = NULL,
                        lease_until = NULL, last_error = 'LEASE_EXPIRED_FINAL_ATTEMPT'
                    WHERE namespace = ? AND owner_id = ? AND status = 'CLAIMED'
                          AND lease_until <= ? AND attempts >= max_attempts
                    """,
                    (ns, owner, now_text),
                )
                self._reserve_usage(
                    connection,
                    ns,
                    owner,
                    pending_effects=-expired_terminal,
                )
            connection.execute(
                """
                UPDATE effect_outbox
                SET status = 'PENDING', lease_owner = NULL, lease_until = NULL
                WHERE namespace = ? AND owner_id = ? AND status = 'CLAIMED'
                      AND lease_until <= ? AND attempts < max_attempts
                """,
                (ns, owner, now_text),
            )
            rows = connection.execute(
                """
                SELECT idempotency_key, database_generation_id, request_id,
                       kind, receipt_hash, payload_json, payload_sha256,
                       intent_sha256, attempts, max_attempts, claim_generation
                FROM effect_outbox
                WHERE namespace = ? AND owner_id = ? AND status = 'PENDING'
                      AND next_attempt_at <= ? AND attempts < max_attempts
                ORDER BY next_attempt_at, created_at, idempotency_key
                LIMIT ?
                """,
                (ns, owner, now_text, bounded),
            ).fetchall()
            for row in rows:
                updated = connection.execute(
                    """
                    UPDATE effect_outbox
                    SET status = 'CLAIMED', lease_owner = ?, lease_until = ?,
                        attempts = attempts + 1,
                        claim_generation = claim_generation + 1,
                        last_error = NULL
                    WHERE namespace = ? AND owner_id = ?
                          AND idempotency_key = ? AND status = 'PENDING'
                    """,
                    (
                        worker_id,
                        lease_until,
                        ns,
                        owner,
                        row["idempotency_key"],
                    ),
                )
                if updated.rowcount != 1:
                    continue
                claimed.append(
                    {
                        "namespace": ns,
                        "owner_id": owner,
                        "idempotency_key": row["idempotency_key"],
                        "database_generation_id": row["database_generation_id"],
                        "request_id": row["request_id"],
                        "kind": row["kind"],
                        "receipt_hash": row["receipt_hash"],
                        "payload": json.loads(row["payload_json"]),
                        "payload_sha256": row["payload_sha256"],
                        "intent_sha256": row["intent_sha256"],
                        "attempt": int(row["attempts"]) + 1,
                        "max_attempts": int(row["max_attempts"]),
                        "lease_owner": worker_id,
                        "lease_until": lease_until,
                        "claim_generation": int(row["claim_generation"]) + 1,
                    }
                )
        return claimed

    def requeue_legacy_link_failures(
        self,
        *,
        limit: int = 1_000,
        now: Optional[Any] = None,
    ) -> int:
        """Make only legacy unsupported-hard-link failures eligible now."""

        bounded = max(1, min(int(limit), 10_000))
        current = _text_time(now)
        # Before the locked-rename publisher existed, Linux durable mounts
        # stored the exhausted os.link() error with the hidden stage name.
        # The new renameat2 failure path never includes that stage name, so a
        # broken replacement capability retains normal exponential backoff.
        legacy_error = "OSError: [Errno 95]%.gdw-artifact-%"
        with self.transaction() as connection:
            rows = connection.execute(
                """
                SELECT namespace, owner_id, idempotency_key
                FROM effect_outbox
                WHERE status = 'PENDING' AND attempts < max_attempts
                  AND next_attempt_at > ? AND last_error LIKE ?
                ORDER BY next_attempt_at, created_at, idempotency_key
                LIMIT ?
                """,
                (current, legacy_error, bounded),
            ).fetchall()
            requeued = 0
            for row in rows:
                updated = connection.execute(
                    """
                    UPDATE effect_outbox
                    SET next_attempt_at = ?
                    WHERE namespace = ? AND owner_id = ?
                      AND idempotency_key = ? AND status = 'PENDING'
                      AND attempts < max_attempts AND next_attempt_at > ?
                      AND last_error LIKE ?
                    """,
                    (
                        current,
                        row["namespace"],
                        row["owner_id"],
                        row["idempotency_key"],
                        current,
                        legacy_error,
                    ),
                )
                requeued += int(updated.rowcount)
            return requeued

    @staticmethod
    def _recoverable_publication_error(
        value: Any,
        *,
        expected_intent_sha256: str,
    ) -> bool:
        match = re.fullmatch(
            r"OSError: \[Errno 95\] Operation not supported: "
            r"'(?P<stage>[^']*[\\/]\.gdw-artifact-[^'\\/]+\.tmp)' -> "
            r"'(?P<final>[^']*[\\/](?P<digest>[0-9a-f]{64})\.json)'",
            str(value or ""),
        )
        if match is None or match.group("digest") != expected_intent_sha256:
            return False
        stage = match.group("stage").replace("\\", "/")
        final = match.group("final").replace("\\", "/")
        return stage.rsplit("/", 1)[0] == final.rsplit("/", 1)[0]

    @staticmethod
    def _validated_recovery_governance(
        governance: Any,
        *,
        namespace: str,
        owner_id: str,
        credential_key_id: str,
        recovery_id: str,
        source_revision: str,
        database_generation_id: str,
        limit: int,
    ) -> Tuple[Dict[str, Any], str, str]:
        try:
            canonical = json.loads(_json_text(governance))
            if type(canonical) is not dict or set(canonical) != {
                "schema",
                "decision",
                "binding",
                "binding_sha256",
                "policy_gateway",
            }:
                raise ValueError("recovery governance shape mismatch")
            expected_binding = {
                "schema": "szl.gdw.transient-effect-recovery-authorization/v1",
                "action_type": "gdw.transient-effect-recovery",
                "namespace": namespace,
                "owner_id": owner_id,
                "credential_key_id": credential_key_id,
                "recovery_id": recovery_id,
                "source_revision": source_revision,
                "database_generation_id": database_generation_id,
                "limit": limit,
                "failure_class": "hf-hard-link-enotsup/v1",
            }
            binding_sha256 = hashlib.sha256(
                _json_text(expected_binding).encode("utf-8")
            ).hexdigest()
            expected_witnesses = [
                {
                    "id": f"principal:{namespace}:{owner_id}:{credential_key_id}",
                    "role": "operator",
                    "attested": True,
                },
                {
                    "id": f"workload:szl-holdings/a11oy@{source_revision}",
                    "role": "workload",
                    "attested": True,
                },
            ]
            gateway = canonical["policy_gateway"]
            if (
                canonical["schema"]
                != "szl.gdw.transient-effect-recovery-governance/v1"
                or canonical["decision"] != "ALLOW"
                or canonical["binding"] != expected_binding
                or canonical["binding_sha256"] != binding_sha256
                or type(gateway) is not dict
                or set(gateway) != {
                    "decision",
                    "gate",
                    "receipt_hash",
                    "receipt_signed",
                    "receipts_in_eq_out",
                    "action_id",
                    "witnesses",
                }
                or gateway["decision"] != "ALLOW"
                or gateway["gate"] != "ThresholdPolicySeverity"
                or re.fullmatch(
                    r"[0-9a-f]{64}", str(gateway["receipt_hash"] or "")
                )
                is None
                or gateway["receipt_signed"] is not True
                or gateway["receipts_in_eq_out"] is not True
                or gateway["action_id"] != f"gdw-recovery:{binding_sha256}"
                or gateway["witnesses"] != expected_witnesses
            ):
                raise ValueError("recovery governance binding mismatch")
            governance_sha256 = hashlib.sha256(
                _json_text(canonical).encode("utf-8")
            ).hexdigest()
            return canonical, binding_sha256, governance_sha256
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise GDWConfigurationError(
                "transient effect recovery governance is invalid"
            ) from exc

    @staticmethod
    def _validated_recovery_audit(row: sqlite3.Row) -> Dict[str, Any]:
        try:
            report = json.loads(row["report_json"])
            if type(report) is not dict:
                raise ValueError("recovery report must be an object")
            outcome_fields = {
                "schema",
                "status",
                "recovery_id",
                "source_revision",
                "requested_limit",
                "failure_class",
                "database_generation_id",
                "inspected_pending_effects",
                "eligible_effects",
                "rescheduled_effects",
                "attempts_before",
                "attempts_after",
                "selection",
                "selection_sha256",
                "sqlite_integrity",
                "claimed_effects",
                "dead_letter_effects",
                "invalid_effect_bindings",
                "invalid_exported_artifacts",
                "invalid_recovery_audits",
                "credential_values_recorded",
            }
            if set(report) != outcome_fields | {
                "governance",
                "audit_receipt",
                "replayed",
            }:
                raise ValueError("recovery report shape mismatch")
            if (
                type(report["governance"]) is not dict
                or type(report["audit_receipt"]) is not dict
            ):
                raise ValueError("recovery receipt must be an object")
            outcome = {field: report[field] for field in outcome_fields}
            receipt = dict(report["audit_receipt"])
            receipt_payload_fields = {
                "schema",
                "operator",
                "recovery_id",
                "source_revision",
                "database_generation_id",
                "request_sha256",
                "outcome_sha256",
                "governance_sha256",
                "selection_sha256",
                "rescheduled_effects",
                "attempts_before",
                "attempts_after",
                "sequence",
                "previous_receipt_sha256",
                "previous_chain_sha256",
                "atomic_with_mutation",
                "created_at",
                "credential_values_recorded",
            }
            receipt_fields = receipt_payload_fields | {
                "receipt_status",
                "receipt_sha256",
                "dsse_envelope_sha256",
                "chain_sha256",
                "dsse_envelope",
            }
            if set(receipt) != receipt_fields:
                raise ValueError("recovery receipt shape mismatch")
            receipt_payload = {
                field: receipt[field] for field in receipt_payload_fields
            }
            if (
                type(receipt.get("created_at")) is not str
                or _text_time(receipt["created_at"]) != receipt["created_at"]
            ):
                raise ValueError("recovery receipt timestamp mismatch")
            recovery_created_at = _normalise_time(receipt["created_at"])

            def is_digest(value: Any, length: int = 64) -> bool:
                return type(value) is str and re.fullmatch(
                    rf"[0-9a-f]{{{length}}}", value
                ) is not None

            observed_outcome_sha256 = hashlib.sha256(
                _json_text(outcome).encode("utf-8")
            ).hexdigest()
            observed_receipt_sha256 = hashlib.sha256(
                _json_text(receipt_payload).encode("utf-8")
            ).hexdigest()
            envelope = receipt["dsse_envelope"]
            if type(envelope) is not dict:
                raise ValueError("recovery DSSE envelope shape mismatch")
            observed_envelope_sha256 = hashlib.sha256(
                _json_text(envelope).encode("utf-8")
            ).hexdigest()
            decoded_payload = json.loads(
                base64.b64decode(
                    str(envelope.get("payload") or ""),
                    validate=True,
                ).decode("utf-8")
            )
            if (
                envelope.get("payloadType") != szl_dsse.KHIPU_PAYLOAD_TYPE
                or decoded_payload != receipt_payload
            ):
                raise ValueError("recovery DSSE payload binding mismatch")
            signed = envelope.get("signed") is True
            if signed:
                if (
                    receipt["receipt_status"] != "SIGNED_KHIPU_DSSE"
                    or szl_dsse.verify_envelope(envelope).get("verified") is not True
                ):
                    raise ValueError("recovery DSSE signature is invalid")
            elif (
                receipt["receipt_status"] != "UNSIGNED_KHIPU_DSSE"
                or envelope.get("signed") is not False
                or envelope.get("signatures") != []
                or "UNSIGNED" not in str(envelope.get("honesty") or "")
            ):
                raise ValueError("recovery unsigned DSSE evidence is dishonest")
            observed_chain_sha256 = hashlib.sha256(
                _json_text(
                    {
                        "previous_chain_sha256": receipt["previous_chain_sha256"],
                        "receipt_sha256": observed_receipt_sha256,
                        "receipt_status": receipt["receipt_status"],
                        "dsse_envelope_sha256": observed_envelope_sha256,
                    }
                ).encode("utf-8")
            ).hexdigest()
            expected_operator = {
                "namespace": row["namespace"],
                "owner_id": row["owner_id"],
                "credential_key_id": row["credential_key_id"],
            }
            expected_request = {
                "schema": "szl.gdw.transient-effect-recovery-request/v1",
                "namespace": row["namespace"],
                "owner_id": row["owner_id"],
                "credential_key_id": row["credential_key_id"],
                "recovery_id": row["recovery_id"],
                "source_revision": outcome.get("source_revision"),
                "database_generation_id": row["database_generation_id"],
                "limit": outcome.get("requested_limit"),
                "failure_class": outcome.get("failure_class"),
                "governance_binding_sha256": report["governance"].get(
                    "binding_sha256"
                ),
            }
            observed_request_sha256 = hashlib.sha256(
                _json_text(expected_request).encode("utf-8")
            ).hexdigest()
            (
                canonical_governance,
                _,
                observed_governance_sha256,
            ) = GDWWorkspace._validated_recovery_governance(
                report["governance"],
                namespace=row["namespace"],
                owner_id=row["owner_id"],
                credential_key_id=row["credential_key_id"],
                recovery_id=row["recovery_id"],
                source_revision=outcome.get("source_revision"),
                database_generation_id=row["database_generation_id"],
                limit=outcome.get("requested_limit"),
            )
            if canonical_governance != report["governance"]:
                raise ValueError("recovery governance is not canonical")
            selection = outcome["selection"]
            count_fields = (
                "inspected_pending_effects",
                "eligible_effects",
                "rescheduled_effects",
                "attempts_before",
                "attempts_after",
                "claimed_effects",
                "dead_letter_effects",
                "invalid_effect_bindings",
                "invalid_exported_artifacts",
                "invalid_recovery_audits",
            )
            counts = {field: outcome[field] for field in count_fields}
            if (
                type(selection) is not list
                or any(type(value) is not int or value < 0 for value in counts.values())
            ):
                raise ValueError("recovery accounting is invalid")
            selection_fields = {
                "namespace",
                "owner_id",
                "idempotency_key",
                "database_generation_id",
                "request_id",
                "kind",
                "receipt_hash",
                "payload_sha256",
                "intent_sha256",
                "attempts",
                "max_attempts",
                "next_attempt_at",
                "claim_generation",
                "last_error_sha256",
            }
            for item in selection:
                if type(item) is not dict or set(item) != selection_fields:
                    raise ValueError("recovery selection shape mismatch")
                if any(
                    _IDENTIFIER.fullmatch(str(item.get(field) or "")) is None
                    for field in (
                        "namespace",
                        "owner_id",
                        "idempotency_key",
                        "request_id",
                    )
                ):
                    raise ValueError("recovery selection identity mismatch")
                if (
                    item.get("database_generation_id")
                    != row["database_generation_id"]
                    or item.get("kind")
                    not in {"receipt_projection", "proof_export"}
                    or (
                        item.get("receipt_hash") is not None
                        and not is_digest(item.get("receipt_hash"))
                    )
                    or any(
                        not is_digest(item.get(field))
                        for field in (
                            "payload_sha256",
                            "intent_sha256",
                            "last_error_sha256",
                        )
                    )
                    or type(item.get("attempts")) is not int
                    or type(item.get("max_attempts")) is not int
                    or not 0 < item["attempts"] < item["max_attempts"]
                    or type(item.get("claim_generation")) is not int
                    or item["claim_generation"] < 0
                    or type(item.get("next_attempt_at")) is not str
                    or _text_time(item["next_attempt_at"])
                    != item["next_attempt_at"]
                    or _normalise_time(item["next_attempt_at"])
                    <= recovery_created_at
                ):
                    raise ValueError("recovery selection binding mismatch")
            observed_selection_sha256 = hashlib.sha256(
                _json_text(selection).encode("utf-8")
            ).hexdigest()
            status = outcome["status"]
            status_contract = (
                (
                    status == "RESCHEDULED"
                    and counts["rescheduled_effects"] > 0
                    and counts["eligible_effects"]
                    == counts["rescheduled_effects"]
                    and counts["claimed_effects"] == 0
                )
                or (
                    status == "NO_ELIGIBLE_EFFECTS"
                    and counts["eligible_effects"] == 0
                    and counts["rescheduled_effects"] == 0
                    and counts["claimed_effects"] == 0
                )
                or (
                    status == "DEFERRED_ACTIVE_CLAIM"
                    and counts["eligible_effects"] == 0
                    and counts["rescheduled_effects"] == 0
                    and counts["claimed_effects"] > 0
                )
            )
            if (
                report["replayed"] is not False
                or outcome.get("schema")
                != "szl.gdw.transient-effect-recovery/v2"
                or receipt.get("schema")
                != "szl.gdw.transient-effect-recovery-receipt/v2"
                or receipt.get("operator") != expected_operator
                or any(
                    _IDENTIFIER.fullmatch(str(value or "")) is None
                    for value in expected_operator.values()
                )
                or receipt.get("recovery_id") != row["recovery_id"]
                or outcome.get("recovery_id") != row["recovery_id"]
                or re.fullmatch(
                    r"[0-9a-f]{40}",
                    str(outcome.get("source_revision") or ""),
                )
                is None
                or receipt.get("source_revision")
                != outcome.get("source_revision")
                or receipt.get("database_generation_id")
                != row["database_generation_id"]
                or outcome.get("database_generation_id")
                != row["database_generation_id"]
                or outcome.get("failure_class") != "hf-hard-link-enotsup/v1"
                or type(outcome.get("requested_limit")) is not int
                or not 1 <= outcome["requested_limit"] <= 1_000
                or outcome.get("sqlite_integrity") != "ok"
                or outcome.get("credential_values_recorded") is not False
                or receipt.get("credential_values_recorded") is not False
                or receipt.get("atomic_with_mutation") is not True
                or type(receipt.get("sequence")) is not int
                or receipt["sequence"] < 0
                or receipt["sequence"] != row["sequence"]
                or not is_digest(receipt.get("previous_receipt_sha256"))
                or receipt.get("previous_receipt_sha256")
                != row["previous_receipt_sha256"]
                or not is_digest(receipt.get("previous_chain_sha256"))
                or receipt.get("previous_chain_sha256")
                != row["previous_chain_sha256"]
                or counts["inspected_pending_effects"]
                < max(counts["eligible_effects"], counts["claimed_effects"])
                or counts["attempts_before"] != counts["attempts_after"]
                or counts["attempts_before"]
                != sum(item["attempts"] for item in selection)
                or len(selection) != counts["rescheduled_effects"]
                or any(
                    counts[field] != 0
                    for field in (
                        "dead_letter_effects",
                        "invalid_effect_bindings",
                        "invalid_exported_artifacts",
                        "invalid_recovery_audits",
                    )
                )
                or not status_contract
                or observed_selection_sha256 != outcome.get("selection_sha256")
                or receipt.get("created_at") != row["created_at"]
                or receipt.get("request_sha256") != row["request_sha256"]
                or observed_request_sha256 != row["request_sha256"]
                or receipt.get("outcome_sha256") != row["outcome_sha256"]
                or observed_outcome_sha256 != row["outcome_sha256"]
                or receipt.get("governance_sha256")
                != row["governance_sha256"]
                or observed_governance_sha256 != row["governance_sha256"]
                or receipt.get("selection_sha256")
                != outcome.get("selection_sha256")
                or receipt.get("rescheduled_effects")
                != outcome.get("rescheduled_effects")
                or receipt.get("attempts_before")
                != outcome.get("attempts_before")
                or receipt.get("attempts_after")
                != outcome.get("attempts_after")
                or receipt.get("receipt_sha256") != row["receipt_sha256"]
                or observed_receipt_sha256 != row["receipt_sha256"]
                or receipt.get("dsse_envelope_sha256")
                != row["dsse_envelope_sha256"]
                or observed_envelope_sha256 != row["dsse_envelope_sha256"]
                or receipt.get("chain_sha256") != row["chain_sha256"]
                or observed_chain_sha256 != row["chain_sha256"]
            ):
                raise ValueError("recovery audit binding mismatch")
            report["audit_receipt"] = receipt
            report["replayed"] = False
            return report
        except (
            AttributeError,
            KeyError,
            OverflowError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise GDWConfigurationError(
                "transient effect recovery audit is invalid"
            ) from exc

    def _recovery_audit_chain_errors(
        self,
        connection: sqlite3.Connection,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> int:
        predicate = ""
        params: Tuple[Any, ...] = ()
        if namespace is not None or owner_id is not None:
            if namespace is None or owner_id is None:
                raise GDWConfigurationError(
                    "recovery audit chain scope must include namespace and owner"
                )
            predicate = " WHERE namespace = ? AND owner_id = ?"
            params = (namespace, owner_id)
        rows = connection.execute(
            "SELECT * FROM effect_recovery_audit"
            + predicate
            + " ORDER BY namespace, owner_id, sequence",
            params,
        ).fetchall()
        errors = 0
        identity: Optional[Tuple[str, str]] = None
        expected_sequence = 0
        previous_receipt_sha256 = "0" * 64
        previous_chain_sha256 = "0" * 64
        for row in rows:
            row_identity = (row["namespace"], row["owner_id"])
            if row_identity != identity:
                identity = row_identity
                expected_sequence = 0
                previous_receipt_sha256 = "0" * 64
                previous_chain_sha256 = "0" * 64
            row_invalid = False
            try:
                self._validated_recovery_audit(row)
            except GDWConfigurationError:
                row_invalid = True
            if (
                row["sequence"] != expected_sequence
                or row["previous_receipt_sha256"]
                != previous_receipt_sha256
                or row["previous_chain_sha256"] != previous_chain_sha256
            ):
                row_invalid = True
            errors += int(row_invalid)
            expected_sequence += 1
            previous_receipt_sha256 = str(row["receipt_sha256"])
            previous_chain_sha256 = str(row["chain_sha256"])
        return errors

    def recover_retry_scheduled_effects(
        self,
        *,
        recovery_id: str,
        credential_key_id: str,
        expected_source_revision: str,
        expected_database_generation_id: str,
        governance: Dict[str, Any],
        now: Optional[Any] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Make only integrity-bound legacy HF publication failures due now."""

        canonical_recovery_id = _checked_identity(recovery_id, "recovery_id")
        canonical_key_id = _checked_identity(
            credential_key_id,
            "credential_key_id",
        )
        source_revision = str(expected_source_revision or "").strip().lower()
        generation_id = str(
            expected_database_generation_id or ""
        ).strip().lower()
        if re.fullmatch(r"[0-9a-f]{40}", source_revision) is None:
            raise GDWConfigurationError(
                "expected_source_revision must be a full Git SHA"
            )
        if (
            re.fullmatch(r"[0-9a-f]{32}", generation_id) is None
            or generation_id != self.database_generation_id
        ):
            raise GDWConfigurationError(
                "transient effect recovery database generation mismatch"
            )
        if type(limit) is not int or not 1 <= limit <= 1_000:
            raise GDWConfigurationError(
                "transient effect recovery limit must be between 1 and 1000"
            )

        current = _normalise_time(now)
        now_text = current.isoformat()
        (
            canonical_governance,
            governance_binding_sha256,
            governance_sha256,
        ) = self._validated_recovery_governance(
            governance,
            namespace=self.namespace,
            owner_id=self.owner_id,
            credential_key_id=canonical_key_id,
            recovery_id=canonical_recovery_id,
            source_revision=source_revision,
            database_generation_id=generation_id,
            limit=limit,
        )
        request = {
            "schema": "szl.gdw.transient-effect-recovery-request/v1",
            "namespace": self.namespace,
            "owner_id": self.owner_id,
            "credential_key_id": canonical_key_id,
            "recovery_id": canonical_recovery_id,
            "source_revision": source_revision,
            "database_generation_id": generation_id,
            "limit": limit,
            "failure_class": "hf-hard-link-enotsup/v1",
            "governance_binding_sha256": governance_binding_sha256,
        }
        request_sha256 = hashlib.sha256(
            _json_text(request).encode("utf-8")
        ).hexdigest()
        empty_selection_sha256 = hashlib.sha256(b"[]").hexdigest()
        transient_error = (
            "OSError: [Errno 95] Operation not supported: "
            "'%/.gdw-artifact-%.tmp' -> '%"
        )

        with self.transaction() as connection:
            cached = connection.execute(
                """
                SELECT * FROM effect_recovery_audit
                WHERE namespace = ? AND owner_id = ? AND recovery_id = ?
                """,
                (self.namespace, self.owner_id, canonical_recovery_id),
            ).fetchone()
            if cached is not None:
                if cached["request_sha256"] != request_sha256:
                    raise GDWConfigurationError(
                        "recovery_id was already used with different content"
                    )
                report = self._validated_recovery_audit(cached)
                if self._recovery_audit_chain_errors(
                    connection,
                    namespace=self.namespace,
                    owner_id=self.owner_id,
                ):
                    raise GDWConfigurationError(
                        "transient effect recovery audit chain is invalid"
                    )
                report["replayed"] = True
                return report

            before = self.integrity(
                global_scope=True,
                connection=connection,
            )
            if (
                before.get("ok") is not True
                or before.get("sqlite_integrity") != "ok"
                or before.get("dead_letter_effects") != 0
                or before.get("pending_proofs") != 0
                or before.get("invalid_effect_bindings") != 0
                or before.get("invalid_exported_artifacts") != 0
                or before.get("invalid_recovery_audits") != 0
            ):
                raise GDWConfigurationError(
                    "transient effect recovery refused by global integrity"
                )

            def record(outcome: Dict[str, Any]) -> Dict[str, Any]:
                outcome_sha256 = hashlib.sha256(
                    _json_text(outcome).encode("utf-8")
                ).hexdigest()
                previous = connection.execute(
                    """
                    SELECT sequence, receipt_sha256, chain_sha256
                    FROM effect_recovery_audit
                    WHERE namespace = ? AND owner_id = ?
                    ORDER BY sequence DESC
                    LIMIT 1
                    """,
                    (self.namespace, self.owner_id),
                ).fetchone()
                sequence = 0 if previous is None else int(previous["sequence"]) + 1
                previous_receipt_sha256 = (
                    "0" * 64 if previous is None else previous["receipt_sha256"]
                )
                previous_chain_sha256 = (
                    "0" * 64 if previous is None else previous["chain_sha256"]
                )
                receipt_payload = {
                    "schema": "szl.gdw.transient-effect-recovery-receipt/v2",
                    "operator": {
                        "namespace": self.namespace,
                        "owner_id": self.owner_id,
                        "credential_key_id": canonical_key_id,
                    },
                    "recovery_id": canonical_recovery_id,
                    "source_revision": source_revision,
                    "database_generation_id": generation_id,
                    "request_sha256": request_sha256,
                    "outcome_sha256": outcome_sha256,
                    "governance_sha256": governance_sha256,
                    "selection_sha256": outcome["selection_sha256"],
                    "rescheduled_effects": outcome["rescheduled_effects"],
                    "attempts_before": outcome["attempts_before"],
                    "attempts_after": outcome["attempts_after"],
                    "sequence": sequence,
                    "previous_receipt_sha256": previous_receipt_sha256,
                    "previous_chain_sha256": previous_chain_sha256,
                    "atomic_with_mutation": True,
                    "created_at": now_text,
                    "credential_values_recorded": False,
                }
                receipt_sha256 = hashlib.sha256(
                    _json_text(receipt_payload).encode("utf-8")
                ).hexdigest()
                dsse_envelope = szl_dsse.sign_payload(
                    receipt_payload,
                    szl_dsse.KHIPU_PAYLOAD_TYPE,
                )
                signed = dsse_envelope.get("signed") is True
                signatures = dsse_envelope.get("signatures")
                if (
                    type(signatures) is not list
                    or (signed and len(signatures) != 1)
                    or (not signed and signatures != [])
                ):
                    raise GDWConfigurationError(
                        "transient recovery DSSE signer returned invalid evidence"
                    )
                receipt_status = (
                    "SIGNED_KHIPU_DSSE" if signed else "UNSIGNED_KHIPU_DSSE"
                )
                dsse_envelope_sha256 = hashlib.sha256(
                    _json_text(dsse_envelope).encode("utf-8")
                ).hexdigest()
                chain_sha256 = hashlib.sha256(
                    _json_text(
                        {
                            "previous_chain_sha256": previous_chain_sha256,
                            "receipt_sha256": receipt_sha256,
                            "receipt_status": receipt_status,
                            "dsse_envelope_sha256": dsse_envelope_sha256,
                        }
                    ).encode("utf-8")
                ).hexdigest()
                receipt = {
                    **receipt_payload,
                    "receipt_status": receipt_status,
                    "receipt_sha256": receipt_sha256,
                    "dsse_envelope_sha256": dsse_envelope_sha256,
                    "chain_sha256": chain_sha256,
                    "dsse_envelope": dsse_envelope,
                }
                report = {
                    **outcome,
                    "governance": canonical_governance,
                    "audit_receipt": receipt,
                    "replayed": False,
                }
                report_text = _json_text(report)
                self._reserve_usage(
                    connection,
                    self.namespace,
                    self.owner_id,
                    stored_bytes=_byte_len(report_text),
                )
                connection.execute(
                    """
                    INSERT INTO effect_recovery_audit(
                        namespace, owner_id, recovery_id, sequence,
                        credential_key_id, database_generation_id,
                        request_sha256, outcome_sha256, governance_sha256,
                        receipt_sha256, previous_receipt_sha256,
                        previous_chain_sha256, chain_sha256,
                        dsse_envelope_sha256, report_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.namespace,
                        self.owner_id,
                        canonical_recovery_id,
                        sequence,
                        canonical_key_id,
                        generation_id,
                        request_sha256,
                        outcome_sha256,
                        governance_sha256,
                        receipt_sha256,
                        previous_receipt_sha256,
                        previous_chain_sha256,
                        chain_sha256,
                        dsse_envelope_sha256,
                        report_text,
                        now_text,
                    ),
                )
                return report

            if before.get("claimed_effects") != 0:
                return record(
                    {
                        "schema": "szl.gdw.transient-effect-recovery/v2",
                        "status": "DEFERRED_ACTIVE_CLAIM",
                        "recovery_id": canonical_recovery_id,
                        "source_revision": source_revision,
                        "requested_limit": limit,
                        "failure_class": "hf-hard-link-enotsup/v1",
                        "database_generation_id": generation_id,
                        "inspected_pending_effects": before["pending_effects"],
                        "eligible_effects": 0,
                        "rescheduled_effects": 0,
                        "attempts_before": 0,
                        "attempts_after": 0,
                        "selection": [],
                        "selection_sha256": empty_selection_sha256,
                        "sqlite_integrity": before["sqlite_integrity"],
                        "claimed_effects": before["claimed_effects"],
                        "dead_letter_effects": before["dead_letter_effects"],
                        "invalid_effect_bindings": before[
                            "invalid_effect_bindings"
                        ],
                        "invalid_exported_artifacts": before[
                            "invalid_exported_artifacts"
                        ],
                        "invalid_recovery_audits": before[
                            "invalid_recovery_audits"
                        ],
                        "credential_values_recorded": False,
                    }
                )

            eligibility = """
                status = 'PENDING'
                AND attempts > 0
                AND attempts < max_attempts
                AND next_attempt_at > ?
                AND database_generation_id = ?
                AND kind IN ('receipt_projection', 'proof_export')
                AND last_error LIKE ?
                AND lease_owner IS NULL
                AND lease_until IS NULL
                AND artifact_json IS NULL
                AND exported_at IS NULL
                AND tombstoned_at IS NULL
            """
            eligible_total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM effect_outbox WHERE {eligibility}",
                    (now_text, generation_id, transient_error),
                ).fetchone()[0]
            )
            if eligible_total > limit:
                raise GDWConfigurationError(
                    "transient effect recovery exceeds the bounded limit"
                )
            rows = connection.execute(
                f"""
                SELECT * FROM effect_outbox
                WHERE {eligibility}
                ORDER BY next_attempt_at, created_at, idempotency_key
                LIMIT ?
                """,
                (now_text, generation_id, transient_error, limit),
            ).fetchall()
            selection = []
            original_rows = {}
            for row in rows:
                try:
                    payload = json.loads(row["payload_json"])
                except (TypeError, json.JSONDecodeError) as exc:
                    raise GDWConfigurationError(
                        "transient effect recovery found invalid payload"
                    ) from exc
                candidate = dict(row)
                candidate["payload"] = payload
                if not self._recoverable_publication_error(
                    row["last_error"],
                    expected_intent_sha256=row["intent_sha256"],
                ):
                    raise GDWConfigurationError(
                        "transient effect recovery found unknown error"
                    )
                if self._connection_effect_binding_errors(connection, candidate):
                    raise GDWConfigurationError(
                        "transient effect recovery found invalid binding"
                    )
                original_rows[
                    (row["namespace"], row["owner_id"], row["idempotency_key"])
                ] = dict(row)
                selection.append(
                    {
                        "namespace": row["namespace"],
                        "owner_id": row["owner_id"],
                        "idempotency_key": row["idempotency_key"],
                        "database_generation_id": row[
                            "database_generation_id"
                        ],
                        "request_id": row["request_id"],
                        "kind": row["kind"],
                        "receipt_hash": row["receipt_hash"],
                        "payload_sha256": row["payload_sha256"],
                        "intent_sha256": row["intent_sha256"],
                        "attempts": int(row["attempts"]),
                        "max_attempts": int(row["max_attempts"]),
                        "next_attempt_at": row["next_attempt_at"],
                        "claim_generation": int(row["claim_generation"]),
                        "last_error_sha256": hashlib.sha256(
                            str(row["last_error"]).encode("utf-8")
                        ).hexdigest(),
                    }
                )

            selection_sha256 = hashlib.sha256(
                _json_text(selection).encode("utf-8")
            ).hexdigest()
            attempts_before = sum(item["attempts"] for item in selection)
            for row, item in zip(rows, selection):
                updated = connection.execute(
                    """
                    UPDATE effect_outbox
                    SET next_attempt_at = ?
                    WHERE namespace = ? AND owner_id = ?
                          AND idempotency_key = ?
                          AND database_generation_id = ?
                          AND request_id = ? AND kind = ?
                          AND receipt_hash IS ?
                          AND payload_json = ? AND payload_sha256 = ?
                          AND intent_sha256 = ?
                          AND status = 'PENDING'
                          AND attempts = ? AND max_attempts = ?
                          AND next_attempt_at = ? AND claim_generation = ?
                          AND last_error = ?
                          AND lease_owner IS NULL AND lease_until IS NULL
                          AND artifact_json IS NULL AND exported_at IS NULL
                          AND tombstoned_at IS NULL
                    """,
                    (
                        now_text,
                        item["namespace"],
                        item["owner_id"],
                        item["idempotency_key"],
                        item["database_generation_id"],
                        item["request_id"],
                        item["kind"],
                        item["receipt_hash"],
                        row["payload_json"],
                        item["payload_sha256"],
                        item["intent_sha256"],
                        item["attempts"],
                        item["max_attempts"],
                        item["next_attempt_at"],
                        item["claim_generation"],
                        row["last_error"],
                    ),
                )
                if updated.rowcount != 1:
                    raise GDWConfigurationError(
                        "transient effect changed during recovery"
                    )

            after = self.integrity(global_scope=True, connection=connection)
            attempts_after = 0
            for item in selection:
                persisted = connection.execute(
                    """
                    SELECT * FROM effect_outbox
                    WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
                    """,
                    (
                        item["namespace"],
                        item["owner_id"],
                        item["idempotency_key"],
                    ),
                ).fetchone()
                if persisted is None:
                    raise GDWConfigurationError(
                        "transient effect disappeared during recovery"
                    )
                original = original_rows[
                    (
                        item["namespace"],
                        item["owner_id"],
                        item["idempotency_key"],
                    )
                ]
                changed = {
                    field
                    for field in persisted.keys()
                    if field != "next_attempt_at"
                    and persisted[field] != original[field]
                }
                if (
                    changed
                    or persisted["next_attempt_at"] != now_text
                    or persisted["status"] != "PENDING"
                ):
                    raise GDWConfigurationError(
                        "transient effect accounting changed during recovery"
                    )
                attempts_after += int(persisted["attempts"])
            if (
                after.get("ok") is not True
                or after.get("sqlite_integrity") != "ok"
                or after.get("pending_effects") != before.get("pending_effects")
                or after.get("claimed_effects") != 0
                or after.get("dead_letter_effects") != 0
                or after.get("invalid_effect_bindings") != 0
                or after.get("invalid_exported_artifacts") != 0
                or after.get("invalid_recovery_audits") != 0
                or attempts_after != attempts_before
            ):
                raise GDWConfigurationError(
                    "transient effect recovery changed protected accounting"
                )

            return record(
                {
                    "schema": "szl.gdw.transient-effect-recovery/v2",
                    "status": (
                        "RESCHEDULED" if rows else "NO_ELIGIBLE_EFFECTS"
                    ),
                    "recovery_id": canonical_recovery_id,
                    "source_revision": source_revision,
                    "requested_limit": limit,
                    "failure_class": "hf-hard-link-enotsup/v1",
                    "database_generation_id": generation_id,
                    "inspected_pending_effects": before["pending_effects"],
                    "eligible_effects": eligible_total,
                    "rescheduled_effects": len(rows),
                    "attempts_before": attempts_before,
                    "attempts_after": attempts_after,
                    "selection": selection,
                    "selection_sha256": selection_sha256,
                    "sqlite_integrity": after["sqlite_integrity"],
                    "claimed_effects": after["claimed_effects"],
                    "dead_letter_effects": after["dead_letter_effects"],
                    "invalid_effect_bindings": after[
                        "invalid_effect_bindings"
                    ],
                    "invalid_exported_artifacts": after[
                        "invalid_exported_artifacts"
                    ],
                    "invalid_recovery_audits": after[
                        "invalid_recovery_audits"
                    ],
                    "credential_values_recorded": False,
                }
            )

    def assert_effect_claim(
        self,
        idempotency_key: str,
        worker_id: str,
        claim_generation: int,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
        now: Optional[Any] = None,
    ) -> Dict[str, Any]:
        ns, owner = self._identity(namespace, owner_id)
        current = _text_time(now)
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT namespace, owner_id, idempotency_key,
                       database_generation_id, request_id, kind, receipt_hash,
                       payload_json, payload_sha256, intent_sha256,
                       claim_generation, lease_owner, lease_until
                FROM effect_outbox
                WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
                      AND status = 'CLAIMED' AND lease_owner = ?
                      AND claim_generation = ? AND lease_until > ?
                """,
                (
                    ns,
                    owner,
                    idempotency_key,
                    worker_id,
                    int(claim_generation),
                    current,
                ),
            ).fetchone()
            if row is None:
                raise RuntimeError(
                    "effect claim is absent, expired, or owned elsewhere"
                )
            candidate = dict(row)
            try:
                candidate["payload"] = json.loads(row["payload_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError("effect claim payload is invalid") from exc
            errors = self._connection_effect_binding_errors(
                connection, candidate
            )
            if errors:
                raise RuntimeError(
                    "effect claim binding is invalid: " + ",".join(errors)
                )
            return candidate
        finally:
            connection.close()

    def mark_effect_exported(
        self,
        idempotency_key: str,
        worker_id: str,
        claim_generation: int,
        artifact: Dict[str, Any],
        exported_at: str,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> None:
        ns, owner = self._identity(namespace, owner_id)
        completed_at = _text_time(exported_at)
        observed_now = _text_time()
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT namespace, owner_id, idempotency_key,
                       database_generation_id, request_id, kind, receipt_hash,
                       payload_json, payload_sha256, intent_sha256,
                       status, artifact_json
                FROM effect_outbox
                WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
                      AND status = 'CLAIMED' AND lease_owner = ?
                      AND claim_generation = ? AND lease_until > ?
                """,
                (
                    ns,
                    owner,
                    idempotency_key,
                    worker_id,
                    int(claim_generation),
                    observed_now,
                ),
            ).fetchone()
            if row is None:
                raise RuntimeError(
                    "effect claim is absent, expired, or owned elsewhere"
                )
            candidate = dict(row)
            try:
                candidate["payload"] = json.loads(row["payload_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise GDWConfigurationError(
                    "effect claim payload is invalid"
                ) from exc
            binding_errors = self._connection_effect_binding_errors(
                connection,
                candidate,
            )
            artifact_errors = self.artifact_binding_errors(
                candidate,
                artifact,
            )
            errors = sorted(set(binding_errors + artifact_errors))
            if errors:
                raise GDWConfigurationError(
                    "effect completion is invalid: " + ",".join(errors)
                )
            artifact_text = _json_text(artifact)
            updated = connection.execute(
                """
                UPDATE effect_outbox
                SET status = 'EXPORTED', artifact_json = ?, exported_at = ?,
                    lease_owner = NULL, lease_until = NULL, last_error = NULL
                WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
                      AND status = 'CLAIMED' AND lease_owner = ?
                      AND claim_generation = ? AND lease_until > ?
                """,
                (
                    artifact_text,
                    completed_at,
                    ns,
                    owner,
                    idempotency_key,
                    worker_id,
                    int(claim_generation),
                    observed_now,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError(
                    "effect claim is absent, expired, or owned elsewhere"
                )
            self._reserve_usage(
                connection,
                ns,
                owner,
                pending_effects=-1,
                stored_bytes=_byte_len(artifact_text),
            )

    def release_effect(
        self,
        idempotency_key: str,
        worker_id: str,
        claim_generation: int,
        error: str,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
        now: Optional[Any] = None,
    ) -> str:
        ns, owner = self._identity(namespace, owner_id)
        current = _normalise_time(now)
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT attempts, max_attempts
                FROM effect_outbox
                WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
                      AND status = 'CLAIMED' AND lease_owner = ?
                      AND claim_generation = ? AND lease_until > ?
                """,
                (
                    ns,
                    owner,
                    idempotency_key,
                    worker_id,
                    int(claim_generation),
                    current.isoformat(),
                ),
            ).fetchone()
            if row is None:
                raise RuntimeError(
                    "effect claim is absent, expired, or owned elsewhere"
                )
            attempts = int(row["attempts"])
            terminal = attempts >= int(row["max_attempts"])
            status = "DEAD_LETTER" if terminal else "PENDING"
            delay = self.effect_backoff_seconds * (2 ** max(0, attempts - 1))
            delay = min(delay, 24 * 60 * 60)
            next_attempt = (current + timedelta(seconds=delay)).isoformat()
            connection.execute(
                """
                UPDATE effect_outbox
                SET status = ?, lease_owner = NULL, lease_until = NULL,
                    last_error = ?, next_attempt_at = ?
                WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
                      AND status = 'CLAIMED' AND lease_owner = ?
                      AND claim_generation = ? AND lease_until > ?
                """,
                (
                    status,
                    str(error)[:1024],
                    next_attempt,
                    ns,
                    owner,
                    idempotency_key,
                    worker_id,
                    int(claim_generation),
                    current.isoformat(),
                ),
            )
            if terminal:
                self._reserve_usage(connection, ns, owner, pending_effects=-1)
            return status

    def pending_proofs(
        self,
        limit: int = 100,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> list:
        ns, owner = self._identity(namespace, owner_id)
        bounded = max(1, min(int(limit), 10_000))
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT proposal_id, payload_json, payload_sha256
                FROM proof_outbox
                WHERE namespace = ? AND owner_id = ? AND status = 'PENDING'
                ORDER BY created_at, proposal_id
                LIMIT ?
                """,
                (ns, owner, bounded),
            ).fetchall()
            return [
                {
                    "namespace": ns,
                    "owner_id": owner,
                    "proposal_id": row["proposal_id"],
                    "payload": json.loads(row["payload_json"]),
                    "payload_sha256": row["payload_sha256"],
                }
                for row in rows
            ]
        finally:
            connection.close()

    def mark_proof_exported(
        self,
        proposal_id: str,
        artifact: Dict[str, Any],
        exported_at: str,
        *,
        expected_payload: Dict[str, Any],
        expected_payload_sha256: str,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> None:
        ns, owner = self._identity(namespace, owner_id)
        artifact_text = _json_text(artifact)
        expected_payload_text = _json_text(expected_payload)
        with self.transaction() as connection:
            updated = connection.execute(
                """
                UPDATE proof_outbox
                SET status = 'EXPORTED', artifact_json = ?, exported_at = ?
                WHERE namespace = ? AND owner_id = ? AND proposal_id = ?
                      AND status = 'PENDING' AND payload_json = ?
                      AND payload_sha256 = ?
                """,
                (
                    artifact_text,
                    _text_time(exported_at),
                    ns,
                    owner,
                    proposal_id,
                    expected_payload_text,
                    expected_payload_sha256,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError(
                    "proof is absent, changed, exported, or owned elsewhere"
                )
            self._reserve_usage(
                connection,
                ns,
                owner,
                pending_effects=-1,
                stored_bytes=_byte_len(artifact_text),
            )

    def read_session(
        self,
        session_id: str,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        connection = self._connect()
        try:
            return self.session_state(
                connection,
                session_id,
                namespace=namespace,
                owner_id=owner_id,
            )
        finally:
            connection.close()

    def pending_effect_identities(self) -> list[Tuple[str, str]]:
        """Return principals with pending work for the trusted drain supervisor."""

        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT namespace, owner_id FROM effect_outbox
                WHERE status IN ('PENDING', 'CLAIMED')
                UNION
                SELECT namespace, owner_id FROM proof_outbox
                WHERE status = 'PENDING'
                ORDER BY namespace, owner_id
                """
            ).fetchall()
            return [(row["namespace"], row["owner_id"]) for row in rows]
        finally:
            connection.close()

    def lifecycle_identities(self) -> list[Tuple[str, str]]:
        """Return principals whose retained state may need supervised cleanup."""

        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT namespace, owner_id FROM session_state
                UNION SELECT namespace, owner_id FROM requests
                UNION SELECT namespace, owner_id FROM receipts
                UNION SELECT namespace, owner_id FROM proof_outbox
                UNION SELECT namespace, owner_id FROM effect_outbox
                UNION SELECT namespace, owner_id FROM effect_recovery_audit
                ORDER BY namespace, owner_id
                """
            ).fetchall()
            return [(row["namespace"], row["owner_id"]) for row in rows]
        finally:
            connection.close()

    @staticmethod
    def _reconcile_identity_usage(
        connection: sqlite3.Connection,
        namespace: str,
        owner_id: str,
    ) -> None:
        timestamp = _text_time()
        sessions = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM session_state
                WHERE namespace = ? AND owner_id = ? AND lifecycle = 'ACTIVE'
                """,
                (namespace, owner_id),
            ).fetchone()[0]
        )
        requests = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM requests
                WHERE namespace = ? AND owner_id = ? AND lifecycle = 'ACTIVE'
                """,
                (namespace, owner_id),
            ).fetchone()[0]
        )
        pending = int(
            connection.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM effect_outbox
                   WHERE namespace = ? AND owner_id = ?
                     AND status IN ('PENDING', 'CLAIMED')) +
                  (SELECT COUNT(*) FROM proof_outbox
                   WHERE namespace = ? AND owner_id = ? AND status = 'PENDING')
                """,
                (namespace, owner_id, namespace, owner_id),
            ).fetchone()[0]
        )
        stored = int(
            connection.execute(
                """
                SELECT
                  COALESCE((SELECT SUM(LENGTH(CAST(state_json AS BLOB)))
                            FROM session_state
                            WHERE namespace = ? AND owner_id = ?), 0) +
                  COALESCE((SELECT SUM(LENGTH(CAST(response_json AS BLOB)))
                            FROM requests
                            WHERE namespace = ? AND owner_id = ?), 0) +
                  COALESCE((SELECT SUM(LENGTH(CAST(receipt_json AS BLOB)))
                            FROM receipts
                            WHERE namespace = ? AND owner_id = ?), 0) +
                  COALESCE((SELECT SUM(
                              LENGTH(CAST(payload_json AS BLOB)) +
                              COALESCE(LENGTH(CAST(artifact_json AS BLOB)), 0))
                            FROM proof_outbox
                            WHERE namespace = ? AND owner_id = ?), 0) +
                  COALESCE((SELECT SUM(
                              LENGTH(CAST(payload_json AS BLOB)) +
                              COALESCE(LENGTH(CAST(artifact_json AS BLOB)), 0))
                            FROM effect_outbox
                            WHERE namespace = ? AND owner_id = ?), 0) +
                  COALESCE((SELECT SUM(LENGTH(CAST(report_json AS BLOB)))
                            FROM effect_recovery_audit
                            WHERE namespace = ? AND owner_id = ?), 0)
                """,
                (
                    namespace,
                    owner_id,
                    namespace,
                    owner_id,
                    namespace,
                    owner_id,
                    namespace,
                    owner_id,
                    namespace,
                    owner_id,
                    namespace,
                    owner_id,
                ),
            ).fetchone()[0]
        )
        connection.execute(
            """
            INSERT INTO usage(
                namespace, owner_id, active_sessions, active_requests,
                pending_effects, stored_bytes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(namespace, owner_id) DO UPDATE SET
                active_sessions = excluded.active_sessions,
                active_requests = excluded.active_requests,
                pending_effects = excluded.pending_effects,
                stored_bytes = excluded.stored_bytes,
                updated_at = excluded.updated_at
            """,
            (
                namespace,
                owner_id,
                sessions,
                requests,
                pending,
                stored,
                timestamp,
            ),
        )

    @staticmethod
    def _reconcile_usage(connection: sqlite3.Connection) -> None:
        identities = connection.execute(
            """
            SELECT namespace, owner_id FROM session_state
            UNION SELECT namespace, owner_id FROM requests
            UNION SELECT namespace, owner_id FROM receipts
            UNION SELECT namespace, owner_id FROM proof_outbox
            UNION SELECT namespace, owner_id FROM effect_outbox
            UNION SELECT namespace, owner_id FROM effect_recovery_audit
            """
        ).fetchall()
        connection.execute("DELETE FROM usage")
        for identity in identities:
            GDWWorkspace._reconcile_identity_usage(
                connection,
                identity["namespace"],
                identity["owner_id"],
            )

    def reconcile_usage(self) -> Dict[str, int]:
        with self.transaction() as connection:
            self._reconcile_usage(connection)
            row = self._usage_row(connection, self.namespace, self.owner_id)
            return {
                "active_sessions": int(row["active_sessions"]),
                "active_requests": int(row["active_requests"]),
                "pending_effects": int(row["pending_effects"]),
                "stored_bytes": int(row["stored_bytes"]),
            }

    def collect_garbage(
        self,
        *,
        now: Optional[Any] = None,
        limit: int = 100,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """Compact expired objects; unexported effects are never compacted or deleted."""

        ns, owner = self._identity(namespace, owner_id)
        current = _normalise_time(now)
        now_text = current.isoformat()
        purge_before = (current - timedelta(seconds=self.tombstone_seconds)).isoformat()
        exported_before = (
            current - timedelta(seconds=self.retention_seconds)
        ).isoformat()
        bounded = max(1, min(int(limit), 10_000))
        result = {
            "sessions_tombstoned": 0,
            "requests_tombstoned": 0,
            "effects_compacted": 0,
            "proofs_compacted": 0,
            "tombstones_purged": 0,
        }
        with self.transaction() as connection:
            session_rows = connection.execute(
                """
                SELECT session_id FROM session_state
                WHERE namespace = ? AND owner_id = ? AND lifecycle = 'ACTIVE'
                      AND expires_at IS NOT NULL AND expires_at <= ?
                ORDER BY expires_at, session_id LIMIT ?
                """,
                (ns, owner, now_text, bounded),
            ).fetchall()
            for row in session_rows:
                connection.execute(
                    """
                    UPDATE session_state
                    SET lifecycle = 'TOMBSTONED', state_json = NULL,
                        tombstoned_at = ?
                    WHERE namespace = ? AND owner_id = ? AND session_id = ?
                    """,
                    (now_text, ns, owner, row["session_id"]),
                )
            result["sessions_tombstoned"] = len(session_rows)

            effects = connection.execute(
                """
                SELECT idempotency_key FROM effect_outbox
                WHERE namespace = ? AND owner_id = ? AND status = 'EXPORTED'
                      AND tombstoned_at IS NULL AND exported_at <= ?
                ORDER BY exported_at, idempotency_key LIMIT ?
                """,
                (ns, owner, exported_before, bounded),
            ).fetchall()
            for row in effects:
                connection.execute(
                    """
                    UPDATE effect_outbox
                    SET payload_json = NULL, artifact_json = NULL,
                        tombstoned_at = ?
                    WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
                          AND status = 'EXPORTED'
                    """,
                    (now_text, ns, owner, row["idempotency_key"]),
                )
            result["effects_compacted"] = len(effects)

            request_rows = connection.execute(
                """
                SELECT r.request_id
                FROM requests r
                WHERE r.namespace = ? AND r.owner_id = ?
                      AND r.lifecycle = 'ACTIVE' AND r.expires_at IS NOT NULL
                      AND r.expires_at <= ?
                      AND NOT EXISTS (
                          SELECT 1 FROM effect_outbox e
                          WHERE e.namespace = r.namespace
                            AND e.owner_id = r.owner_id
                            AND e.request_id = r.request_id
                            AND (
                                e.status != 'EXPORTED'
                                OR e.payload_json IS NOT NULL
                            )
                      )
                ORDER BY r.expires_at, r.request_id LIMIT ?
                """,
                (ns, owner, now_text, bounded),
            ).fetchall()
            for row in request_rows:
                connection.execute(
                    """
                    UPDATE requests
                    SET lifecycle = 'TOMBSTONED', response_json = NULL,
                        tombstoned_at = ?
                    WHERE namespace = ? AND owner_id = ? AND request_id = ?
                    """,
                    (now_text, ns, owner, row["request_id"]),
                )
                connection.execute(
                    """
                    UPDATE receipts SET receipt_json = NULL, tombstoned_at = ?
                    WHERE namespace = ? AND owner_id = ? AND request_id = ?
                    """,
                    (now_text, ns, owner, row["request_id"]),
                )
            result["requests_tombstoned"] = len(request_rows)

            proofs = connection.execute(
                """
                SELECT proposal_id FROM proof_outbox
                WHERE namespace = ? AND owner_id = ? AND status = 'EXPORTED'
                      AND tombstoned_at IS NULL AND exported_at <= ?
                ORDER BY exported_at, proposal_id LIMIT ?
                """,
                (ns, owner, exported_before, bounded),
            ).fetchall()
            for row in proofs:
                connection.execute(
                    """
                    UPDATE proof_outbox
                    SET payload_json = NULL, artifact_json = NULL,
                        tombstoned_at = ?
                    WHERE namespace = ? AND owner_id = ? AND proposal_id = ?
                          AND status = 'EXPORTED'
                    """,
                    (now_text, ns, owner, row["proposal_id"]),
                )
            result["proofs_compacted"] = len(proofs)

            purged = 0
            purged += connection.execute(
                """
                DELETE FROM proof_outbox
                WHERE namespace = ? AND owner_id = ? AND status = 'EXPORTED'
                      AND tombstoned_at IS NOT NULL AND tombstoned_at <= ?
                """,
                (ns, owner, purge_before),
            ).rowcount
            purged += connection.execute(
                """
                DELETE FROM effect_outbox
                WHERE namespace = ? AND owner_id = ? AND status = 'EXPORTED'
                      AND tombstoned_at IS NOT NULL AND tombstoned_at <= ?
                """,
                (ns, owner, purge_before),
            ).rowcount
            request_ids = [
                row["request_id"]
                for row in connection.execute(
                    """
                    SELECT request_id FROM requests
                    WHERE namespace = ? AND owner_id = ?
                          AND lifecycle = 'TOMBSTONED'
                          AND tombstoned_at <= ?
                          AND NOT EXISTS (
                              SELECT 1 FROM effect_outbox e
                              WHERE e.namespace = requests.namespace
                                AND e.owner_id = requests.owner_id
                                AND e.request_id = requests.request_id
                          )
                    LIMIT ?
                    """,
                    (ns, owner, purge_before, bounded),
                ).fetchall()
            ]
            for request_id in request_ids:
                connection.execute(
                    """
                    DELETE FROM receipts
                    WHERE namespace = ? AND owner_id = ? AND request_id = ?
                    """,
                    (ns, owner, request_id),
                )
                purged += connection.execute(
                    """
                    DELETE FROM requests
                    WHERE namespace = ? AND owner_id = ? AND request_id = ?
                    """,
                    (ns, owner, request_id),
                ).rowcount
            purged += connection.execute(
                """
                DELETE FROM session_state
                WHERE namespace = ? AND owner_id = ?
                      AND lifecycle = 'TOMBSTONED' AND tombstoned_at <= ?
                """,
                (ns, owner, purge_before),
            ).rowcount
            result["tombstones_purged"] = purged
            self._reconcile_identity_usage(connection, ns, owner)
        return result

    def integrity(
        self,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
        global_scope: bool = False,
        connection: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        ns, owner = self._identity(namespace, owner_id)
        owns_connection = connection is None
        if connection is None:
            connection = self._connect()
        try:
            check = connection.execute("PRAGMA integrity_check").fetchone()[0]
            predicate = "" if global_scope else " WHERE namespace = ? AND owner_id = ?"
            params = () if global_scope else (ns, owner)
            counts = {
                table: int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table}{predicate}", params
                    ).fetchone()[0]
                )
                for table in _V1_TABLES
            }
            counts["effect_recovery_audit"] = int(
                connection.execute(
                    "SELECT COUNT(*) FROM effect_recovery_audit" + predicate,
                    params,
                ).fetchone()[0]
            )
            effect_predicate = (
                "status IN ('PENDING', 'CLAIMED')"
                if global_scope
                else "namespace = ? AND owner_id = ? "
                "AND status IN ('PENDING', 'CLAIMED')"
            )
            effect_params = () if global_scope else (ns, owner)
            pending_effects = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM effect_outbox WHERE {effect_predicate}",
                    effect_params,
                ).fetchone()[0]
            )
            claimed_predicate = (
                "status = 'CLAIMED'"
                if global_scope
                else "namespace = ? AND owner_id = ? AND status = 'CLAIMED'"
            )
            claimed_effects = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM effect_outbox WHERE {claimed_predicate}",
                    effect_params,
                ).fetchone()[0]
            )
            dead_letter_predicate = (
                "status = 'DEAD_LETTER'"
                if global_scope
                else "namespace = ? AND owner_id = ? AND status = 'DEAD_LETTER'"
            )
            dead_letter_effects = int(
                connection.execute(
                    "SELECT COUNT(*) FROM effect_outbox "
                    f"WHERE {dead_letter_predicate}",
                    effect_params,
                ).fetchone()[0]
            )
            proof_predicate = (
                "status = 'PENDING'"
                if global_scope
                else "namespace = ? AND owner_id = ? AND status = 'PENDING'"
            )
            pending_proofs = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM proof_outbox WHERE {proof_predicate}",
                    effect_params,
                ).fetchone()[0]
            )
            orphan_predicate = (
                "" if global_scope else "AND r.namespace = ? AND r.owner_id = ?"
            )
            orphan_receipts = int(
                connection.execute(
                    f"""
                    SELECT COUNT(*) FROM receipts r
                    LEFT JOIN requests q
                      ON q.namespace = r.namespace
                     AND q.owner_id = r.owner_id
                     AND q.request_id = r.request_id
                    WHERE q.request_id IS NULL {orphan_predicate}
                    """,
                    params,
                ).fetchone()[0]
            )
            digest_violations = {
                "invalid_state_digests": 0,
                "invalid_request_digests": 0,
                "invalid_receipt_digests": 0,
                "invalid_proof_digests": 0,
                "invalid_recovery_audits": 0,
            }
            scoped_suffix = (
                ""
                if global_scope
                else " WHERE namespace = ? AND owner_id = ?"
            )
            for row in connection.execute(
                "SELECT namespace, owner_id, session_id, step, state_json, "
                "state_hash FROM session_state"
                + scoped_suffix,
                params,
            ):
                if row["state_json"] is None:
                    continue
                try:
                    state = json.loads(row["state_json"])
                    observed = hashlib.sha256(
                        _json_text(state).encode("utf-8")
                    ).hexdigest()
                    expected_identity = {
                        "namespace": row["namespace"],
                        "owner_id": row["owner_id"],
                        "session_id": row["session_id"],
                        "step": int(row["step"]),
                        "database_generation_id": self.database_generation_id,
                    }
                    if (
                        not isinstance(state, dict)
                        or observed != row["state_hash"]
                        or any(
                            state.get(field) != expected
                            for field, expected in expected_identity.items()
                        )
                    ):
                        raise ValueError("state digest mismatch")
                except (TypeError, ValueError, json.JSONDecodeError):
                    digest_violations["invalid_state_digests"] += 1
            for row in connection.execute(
                "SELECT namespace, owner_id, request_id, request_digest, "
                "session_id, response_json, response_hash FROM requests"
                + scoped_suffix,
                params,
            ):
                if row["response_json"] is None:
                    continue
                try:
                    response = json.loads(row["response_json"])
                    observed = hashlib.sha256(
                        _json_text(response).encode("utf-8")
                    ).hexdigest()
                    principal = (
                        response.get("principal")
                        if isinstance(response, dict)
                        else None
                    )
                    expected_identity = {
                        "request_id": row["request_id"],
                        "request_digest": row["request_digest"],
                        "session_id": row["session_id"],
                        "database_generation_id": self.database_generation_id,
                    }
                    if (
                        not isinstance(response, dict)
                        or observed != row["response_hash"]
                        or any(
                            response.get(field) != expected
                            for field, expected in expected_identity.items()
                        )
                        or not isinstance(principal, dict)
                        or principal.get("namespace") != row["namespace"]
                        or principal.get("owner_id") != row["owner_id"]
                    ):
                        raise ValueError("request digest mismatch")
                except (TypeError, ValueError, json.JSONDecodeError):
                    digest_violations["invalid_request_digests"] += 1
            for row in connection.execute(
                "SELECT namespace, owner_id, request_id, session_id, step, "
                "receipt_json, receipt_hash FROM receipts"
                + scoped_suffix,
                params,
            ):
                if row["receipt_json"] is None:
                    continue
                try:
                    receipt = json.loads(row["receipt_json"])
                    if not isinstance(receipt, dict):
                        raise ValueError("receipt must be an object")
                    claimed = str(receipt.pop("receipt_hash", ""))
                    observed = hashlib.sha256(
                        _json_text(receipt).encode("utf-8")
                    ).hexdigest()
                    expected_identity = {
                        "namespace": row["namespace"],
                        "owner_id": row["owner_id"],
                        "request_id": row["request_id"],
                        "session_id": row["session_id"],
                        "step": int(row["step"]),
                        "database_generation_id": self.database_generation_id,
                    }
                    if (
                        claimed != row["receipt_hash"]
                        or observed != row["receipt_hash"]
                        or any(
                            receipt.get(field) != expected
                            for field, expected in expected_identity.items()
                        )
                    ):
                        raise ValueError("receipt digest mismatch")
                except (TypeError, ValueError, json.JSONDecodeError):
                    digest_violations["invalid_receipt_digests"] += 1
            for row in connection.execute(
                "SELECT payload_json, payload_sha256 FROM proof_outbox"
                + scoped_suffix,
                params,
            ):
                if row["payload_json"] is None:
                    continue
                try:
                    payload = json.loads(row["payload_json"])
                    if not isinstance(payload, dict):
                        raise ValueError("proof payload must be an object")
                    observed = self._effect_payload_digest(
                        "proof_export", payload
                    )
                    if observed != row["payload_sha256"]:
                        raise ValueError("proof digest mismatch")
                except (
                    GDWConfigurationError,
                    TypeError,
                    ValueError,
                    json.JSONDecodeError,
                ):
                    digest_violations["invalid_proof_digests"] += 1
            digest_violations["invalid_recovery_audits"] += (
                self._recovery_audit_chain_errors(
                    connection,
                    namespace=None if global_scope else ns,
                    owner_id=None if global_scope else owner,
                )
            )
            effect_rows = connection.execute(
                """
                SELECT namespace, owner_id, idempotency_key,
                       database_generation_id, request_id, kind, receipt_hash,
                       payload_json, payload_sha256, intent_sha256,
                       status, artifact_json
                FROM effect_outbox
                WHERE payload_json IS NOT NULL
                """
                + (
                    ""
                    if global_scope
                    else " AND namespace = ? AND owner_id = ?"
                ),
                params,
            ).fetchall()
            invalid_effect_bindings = 0
            invalid_exported_artifacts = 0
            for row in effect_rows:
                try:
                    payload = json.loads(row["payload_json"])
                except (TypeError, json.JSONDecodeError):
                    invalid_effect_bindings += 1
                    continue
                candidate = dict(row)
                candidate["payload"] = payload
                if self._connection_effect_binding_errors(
                    connection, candidate
                ):
                    invalid_effect_bindings += 1
                if row["status"] == "EXPORTED":
                    try:
                        artifact = json.loads(row["artifact_json"])
                    except (TypeError, json.JSONDecodeError):
                        invalid_exported_artifacts += 1
                    else:
                        if self.artifact_binding_errors(candidate, artifact):
                            invalid_exported_artifacts += 1
                elif row["artifact_json"] is not None:
                    invalid_exported_artifacts += 1
            result = {
                "ok": (
                    check == "ok"
                    and orphan_receipts == 0
                    and not any(digest_violations.values())
                    and invalid_effect_bindings == 0
                    and invalid_exported_artifacts == 0
                ),
                "schema_version": SCHEMA_VERSION,
                "database_generation_id": self.database_generation_id,
                "sqlite_integrity": check,
                "orphan_receipts": orphan_receipts,
                "pending_proofs": pending_proofs,
                "pending_effects": pending_effects,
                "claimed_effects": claimed_effects,
                "dead_letter_effects": dead_letter_effects,
                "invalid_effect_bindings": invalid_effect_bindings,
                "invalid_exported_artifacts": invalid_exported_artifacts,
                **digest_violations,
                "counts": counts,
                "scope": "global" if global_scope else "owner",
                "journal_mode": str(
                    connection.execute("PRAGMA journal_mode").fetchone()[0]
                ).upper(),
                "synchronous": self.synchronous_mode,
            }
            if global_scope:
                result["path"] = str(self.path)
            else:
                result["namespace"] = ns
                result["owner_id"] = owner
            return result
        finally:
            if owns_connection:
                connection.close()
