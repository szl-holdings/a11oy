"""Tenant-safe SQLite state, idempotency, quota, and outbox storage for GDW."""

import contextlib
import hashlib
import json
import os
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple


SCHEMA_VERSION = 2
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
        request_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('receipt_projection', 'proof_export')),
        payload_json TEXT,
        payload_sha256 TEXT NOT NULL,
        status TEXT NOT NULL
            CHECK(status IN ('PENDING', 'CLAIMED', 'EXPORTED', 'DEAD_LETTER')),
        attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
        max_attempts INTEGER NOT NULL CHECK(max_attempts > 0),
        next_attempt_at TEXT NOT NULL,
        lease_owner TEXT,
        lease_until TEXT,
        last_error TEXT,
        artifact_json TEXT,
        created_at TEXT NOT NULL,
        exported_at TEXT,
        tombstoned_at TEXT,
        PRIMARY KEY(namespace, owner_id, idempotency_key),
        UNIQUE(namespace, owner_id, request_id, kind),
        FOREIGN KEY(namespace, owner_id, request_id)
            REFERENCES requests(namespace, owner_id, request_id)
            DEFERRABLE INITIALLY DEFERRED
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
        configured_owner = owner_id or os.environ.get("GDW_OWNER_ID")
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
        self._initialise()

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
    def _create_schema(connection: sqlite3.Connection, timestamp: str) -> None:
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO schema_meta(
                schema_name, schema_version, created_at, upgraded_at
            ) VALUES ('gdw', ?, ?, ?)
            """,
            (SCHEMA_VERSION, timestamp, timestamp),
        )

    @staticmethod
    def _legacy_row_count(connection: sqlite3.Connection, tables: set) -> int:
        return sum(
            int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in _V1_TABLES
            if table in tables
        )

    def _migrate_v1(self, connection: sqlite3.Connection, tables: set) -> None:
        namespace = os.environ.get("GDW_LEGACY_NAMESPACE")
        owner_id = os.environ.get("GDW_LEGACY_OWNER_ID")
        nonempty = self._legacy_row_count(connection, tables) > 0
        if nonempty and (not namespace or not owner_id):
            raise GDWLegacyMigrationRequired(
                "nonempty v1 workspace requires GDW_LEGACY_NAMESPACE and "
                "GDW_LEGACY_OWNER_ID"
            )
        migration_namespace = _checked_identity(
            namespace or self.namespace, "GDW_LEGACY_NAMESPACE"
        )
        migration_owner = _checked_identity(
            owner_id or self.owner_id, "GDW_LEGACY_OWNER_ID"
        )
        timestamp = _text_time()
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        try:
            for index in (
                "idx_requests_session",
                "idx_receipts_session",
                "idx_proof_outbox_status",
                "idx_effect_outbox_status",
            ):
                connection.execute(f"DROP INDEX IF EXISTS {index}")
            for table in _V1_TABLES:
                if table in tables:
                    connection.execute(f"ALTER TABLE {table} RENAME TO {table}_v1")
            self._create_schema(connection, timestamp)

            if "session_state" in tables:
                connection.execute(
                    """
                    INSERT INTO session_state(
                        namespace, owner_id, session_id, step, state_json,
                        state_hash, lifecycle, created_at, updated_at,
                        last_accessed_at
                    )
                    SELECT ?, ?, session_id, step, state_json, state_hash,
                           'ACTIVE', updated_at, updated_at, updated_at
                    FROM session_state_v1
                    """,
                    (migration_namespace, migration_owner),
                )
            if "requests" in tables:
                connection.execute(
                    """
                    INSERT INTO requests(
                        namespace, owner_id, request_id, request_digest,
                        session_id, response_json, response_hash, lifecycle,
                        created_at
                    )
                    SELECT ?, ?, request_id, request_digest, session_id,
                           response_json, response_hash, 'ACTIVE', created_at
                    FROM requests_v1
                    """,
                    (migration_namespace, migration_owner),
                )
            if "receipts" in tables:
                connection.execute(
                    """
                    INSERT INTO receipts(
                        namespace, owner_id, receipt_hash, request_id,
                        session_id, step, receipt_json, created_at
                    )
                    SELECT ?, ?, receipt_hash, request_id, session_id, step,
                           receipt_json, created_at
                    FROM receipts_v1
                    """,
                    (migration_namespace, migration_owner),
                )
            if "proof_outbox" in tables:
                connection.execute(
                    """
                    INSERT INTO proof_outbox(
                        namespace, owner_id, proposal_id, payload_json,
                        payload_sha256, status, artifact_json, created_at,
                        exported_at
                    )
                    SELECT ?, ?, proposal_id, payload_json, payload_sha256,
                           status, artifact_json, created_at, exported_at
                    FROM proof_outbox_v1
                    """,
                    (migration_namespace, migration_owner),
                )
            if "effect_outbox" in tables:
                connection.execute(
                    """
                    INSERT INTO effect_outbox(
                        namespace, owner_id, idempotency_key, request_id, kind,
                        payload_json, payload_sha256, status, attempts,
                        max_attempts, next_attempt_at, lease_owner, lease_until,
                        last_error, artifact_json, created_at, exported_at
                    )
                    SELECT ?, ?, idempotency_key, request_id, kind,
                           payload_json, payload_sha256, status, attempts, ?,
                           created_at, lease_owner, lease_until, last_error,
                           artifact_json, created_at, exported_at
                    FROM effect_outbox_v1
                    """,
                    (
                        migration_namespace,
                        migration_owner,
                        self.effect_max_attempts,
                    ),
                )
            for table in reversed(_V1_TABLES):
                if table in tables:
                    connection.execute(f"DROP TABLE {table}_v1")
            self._reconcile_usage(connection)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.execute("PRAGMA foreign_keys=ON")

    @staticmethod
    def _validate_schema(connection: sqlite3.Connection) -> None:
        row = connection.execute(
            "SELECT schema_version FROM schema_meta WHERE schema_name = 'gdw'"
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
                self._validate_schema(connection)
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
            SELECT request_digest, response_json, lifecycle
            FROM requests
            WHERE namespace = ? AND owner_id = ? AND request_id = ?
            """,
            (ns, owner, request_id),
        ).fetchone()
        if row is None:
            return None
        if row["lifecycle"] != "ACTIVE" or row["response_json"] is None:
            raise GDWLifecycleError("idempotency record is outside its replay window")
        return row["request_digest"], json.loads(row["response_json"])

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
            SELECT step, state_json, state_hash, updated_at, lifecycle,
                   expires_at
            FROM session_state
            WHERE namespace = ? AND owner_id = ? AND session_id = ?
            """,
            (ns, owner, session_id),
        ).fetchone()
        if row is None or row["lifecycle"] != "ACTIVE" or row["state_json"] is None:
            return None
        connection.execute(
            """
            UPDATE session_state SET last_accessed_at = ?
            WHERE namespace = ? AND owner_id = ? AND session_id = ?
            """,
            (_text_time(), ns, owner, session_id),
        )
        return {
            "namespace": ns,
            "owner_id": owner,
            "session_id": session_id,
            "step": int(row["step"]),
            "state": json.loads(row["state_json"]),
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
                response_hash,
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
                receipt_hash,
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

    @classmethod
    def effect_binding_errors(cls, row: Dict[str, Any]) -> list[str]:
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
        canonical_key = self.scoped_effect_key(
            ns,
            owner,
            request_id,
            kind,
            payload_sha256,
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
                namespace, owner_id, idempotency_key, request_id, kind,
                payload_json, payload_sha256, status, attempts, max_attempts,
                next_attempt_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', 0, ?, ?, ?)
            """,
            (
                ns,
                owner,
                key,
                request_id,
                kind,
                payload_text,
                payload_sha256,
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
            connection.execute(
                """
                UPDATE effect_outbox
                SET status = 'PENDING', lease_owner = NULL, lease_until = NULL
                WHERE namespace = ? AND owner_id = ? AND status = 'CLAIMED'
                      AND lease_until <= ?
                """,
                (ns, owner, now_text),
            )
            rows = connection.execute(
                """
                SELECT idempotency_key, request_id, kind, payload_json,
                       payload_sha256, attempts, max_attempts
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
                        attempts = attempts + 1, last_error = NULL
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
                        "request_id": row["request_id"],
                        "kind": row["kind"],
                        "payload": json.loads(row["payload_json"]),
                        "payload_sha256": row["payload_sha256"],
                        "attempt": int(row["attempts"]) + 1,
                        "max_attempts": int(row["max_attempts"]),
                        "lease_owner": worker_id,
                        "lease_until": lease_until,
                    }
                )
        return claimed

    def mark_effect_exported(
        self,
        idempotency_key: str,
        worker_id: str,
        artifact: Dict[str, Any],
        exported_at: str,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> None:
        ns, owner = self._identity(namespace, owner_id)
        artifact_text = _json_text(artifact)
        with self.transaction() as connection:
            updated = connection.execute(
                """
                UPDATE effect_outbox
                SET status = 'EXPORTED', artifact_json = ?, exported_at = ?,
                    lease_owner = NULL, lease_until = NULL, last_error = NULL
                WHERE namespace = ? AND owner_id = ? AND idempotency_key = ?
                      AND status = 'CLAIMED' AND lease_owner = ?
                """,
                (
                    artifact_text,
                    _text_time(exported_at),
                    ns,
                    owner,
                    idempotency_key,
                    worker_id,
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
                """,
                (ns, owner, idempotency_key, worker_id),
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
                """,
                (
                    status,
                    str(error)[:1024],
                    next_attempt,
                    ns,
                    owner,
                    idempotency_key,
                    worker_id,
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
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> None:
        ns, owner = self._identity(namespace, owner_id)
        artifact_text = _json_text(artifact)
        with self.transaction() as connection:
            updated = connection.execute(
                """
                UPDATE proof_outbox
                SET status = 'EXPORTED', artifact_json = ?, exported_at = ?
                WHERE namespace = ? AND owner_id = ? AND proposal_id = ?
                      AND status = 'PENDING'
                """,
                (
                    artifact_text,
                    _text_time(exported_at),
                    ns,
                    owner,
                    proposal_id,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError("proof is absent, exported, or owned elsewhere")
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

    @staticmethod
    def _reconcile_usage(connection: sqlite3.Connection) -> None:
        timestamp = _text_time()
        identities = connection.execute(
            """
            SELECT namespace, owner_id FROM session_state
            UNION SELECT namespace, owner_id FROM requests
            UNION SELECT namespace, owner_id FROM receipts
            UNION SELECT namespace, owner_id FROM proof_outbox
            UNION SELECT namespace, owner_id FROM effect_outbox
            """
        ).fetchall()
        connection.execute("DELETE FROM usage")
        for identity in identities:
            ns, owner = identity["namespace"], identity["owner_id"]
            sessions = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM session_state
                    WHERE namespace = ? AND owner_id = ? AND lifecycle = 'ACTIVE'
                    """,
                    (ns, owner),
                ).fetchone()[0]
            )
            requests = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM requests
                    WHERE namespace = ? AND owner_id = ? AND lifecycle = 'ACTIVE'
                    """,
                    (ns, owner),
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
                    (ns, owner, ns, owner),
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
                                WHERE namespace = ? AND owner_id = ?), 0)
                    """,
                    (ns, owner, ns, owner, ns, owner, ns, owner, ns, owner),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO usage(
                    namespace, owner_id, active_sessions, active_requests,
                    pending_effects, stored_bytes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ns, owner, sessions, requests, pending, stored, timestamp),
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
                            AND e.status != 'EXPORTED'
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
            self._reconcile_usage(connection)
        return result

    def integrity(
        self,
        *,
        namespace: Optional[str] = None,
        owner_id: Optional[str] = None,
        global_scope: bool = False,
    ) -> Dict[str, Any]:
        ns, owner = self._identity(namespace, owner_id)
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
            effect_rows = connection.execute(
                """
                SELECT namespace, owner_id, idempotency_key, request_id, kind,
                       payload_json, payload_sha256
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
            for row in effect_rows:
                try:
                    payload = json.loads(row["payload_json"])
                except (TypeError, json.JSONDecodeError):
                    invalid_effect_bindings += 1
                    continue
                candidate = dict(row)
                candidate["payload"] = payload
                if self.effect_binding_errors(candidate):
                    invalid_effect_bindings += 1
            result = {
                "ok": (
                    check == "ok"
                    and orphan_receipts == 0
                    and invalid_effect_bindings == 0
                ),
                "schema_version": SCHEMA_VERSION,
                "sqlite_integrity": check,
                "orphan_receipts": orphan_receipts,
                "pending_proofs": pending_proofs,
                "pending_effects": pending_effects,
                "claimed_effects": claimed_effects,
                "dead_letter_effects": dead_letter_effects,
                "invalid_effect_bindings": invalid_effect_bindings,
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
            connection.close()
