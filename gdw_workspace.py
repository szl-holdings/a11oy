"""Concurrency-safe SQLite state, idempotency, and receipt storage for GDW."""

import contextlib
import hashlib
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple


_SCHEMA_LOCK = threading.RLock()
_PROCESS_WRITE_LOCK = threading.RLock()
_INTEGRITY_CACHE_LOCK = threading.RLock()
_INITIALISED_PATHS = set()
_RUNTIME_INTEGRITY_CACHE: Dict[str, Dict[str, Any]] = {}
_OBJECT_TYPES = {"request", "session"}
_EFFECT_KINDS = {"receipt_projection", "proof_export"}
_REQUIRED_RUNTIME_TABLES = {
    "effect_outbox",
    "evidence_intents",
    "object_owners",
    "receipts",
    "requests",
    "session_state",
    "workspace_meta",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _effect_identity_key(
    *,
    generation_id: str,
    owner_id: str,
    request_id: str,
    request_digest: str,
    kind: str,
    canonical_identity: str,
    payload_sha256: str,
) -> str:
    return hashlib.sha256(
        (
            f"{generation_id}:{owner_id}:{request_id}:{request_digest}:"
            f"{kind}:{canonical_identity}:{payload_sha256}"
        ).encode("utf-8")
    ).hexdigest()


class GDWWorkspace:
    def __init__(self, path: Optional[str] = None):
        configured = path or os.environ.get("GDW_DB_PATH", "output/gdw/gdw.sqlite3")
        self.path = Path(configured).resolve()
        self.journal_mode = os.environ.get("GDW_SQLITE_JOURNAL", "WAL").strip().upper()
        if self.journal_mode not in {"DELETE", "WAL"}:
            raise RuntimeError("GDW_SQLITE_JOURNAL must be DELETE or WAL")
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
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialise(self) -> None:
        key = str(self.path)
        if key in _INITIALISED_PATHS:
            return
        with _SCHEMA_LOCK:
            if key in _INITIALISED_PATHS:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(str(self.path), timeout=30.0)
            try:
                observed_journal = str(
                    connection.execute(
                        f"PRAGMA journal_mode={self.journal_mode}"
                    ).fetchone()[0]
                ).upper()
                if observed_journal != self.journal_mode:
                    raise RuntimeError(
                        "configured SQLite journal mode did not converge"
                    )
                connection.execute("PRAGMA synchronous=NORMAL")
                connection.execute("PRAGMA foreign_keys=ON")
                self._ensure_schema(connection)
                connection.commit()
                _INITIALISED_PATHS.add(key)
            finally:
                connection.close()

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS session_state (
                session_id TEXT PRIMARY KEY,
                step INTEGER NOT NULL CHECK(step >= 0),
                state_json TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS requests (
                request_id TEXT PRIMARY KEY,
                request_digest TEXT NOT NULL,
                session_id TEXT NOT NULL,
                response_json TEXT NOT NULL,
                response_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_hash TEXT PRIMARY KEY,
                request_id TEXT NOT NULL UNIQUE,
                session_id TEXT NOT NULL,
                step INTEGER NOT NULL,
                receipt_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(request_id) REFERENCES requests(request_id)
                    DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TABLE IF NOT EXISTS proof_outbox (
                proposal_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDING', 'EXPORTED')),
                artifact_json TEXT,
                created_at TEXT NOT NULL,
                exported_at TEXT
            );
            CREATE TABLE IF NOT EXISTS effect_outbox (
                idempotency_key TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                kind TEXT NOT NULL
                    CHECK(kind IN ('receipt_projection', 'proof_export')),
                generation_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                canonical_identity TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK(status IN ('PENDING', 'CLAIMED', 'EXPORTED')),
                attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
                lease_owner TEXT,
                lease_until TEXT,
                claim_token TEXT,
                last_error TEXT,
                artifact_json TEXT,
                created_at TEXT NOT NULL,
                exported_at TEXT,
                UNIQUE(request_id, kind),
                FOREIGN KEY(request_id) REFERENCES requests(request_id)
                    DEFERRABLE INITIALLY DEFERRED
            );
            CREATE TABLE IF NOT EXISTS workspace_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS object_owners (
                object_type TEXT NOT NULL
                    CHECK(object_type IN ('request', 'session')),
                object_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                PRIMARY KEY(object_type, object_id)
            );
            CREATE TABLE IF NOT EXISTS evidence_intents (
                canonical_identity TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                kind TEXT NOT NULL
                    CHECK(kind IN ('receipt_projection', 'proof_export')),
                generation_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(request_id, kind),
                FOREIGN KEY(request_id) REFERENCES requests(request_id)
                    DEFERRABLE INITIALLY DEFERRED
            );
            CREATE INDEX IF NOT EXISTS idx_requests_session ON requests(session_id);
            CREATE INDEX IF NOT EXISTS idx_receipts_session ON receipts(session_id, step);
            CREATE INDEX IF NOT EXISTS idx_proof_outbox_status
                ON proof_outbox(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_effect_outbox_status
                ON effect_outbox(status, lease_until, created_at);
            CREATE INDEX IF NOT EXISTS idx_object_owners_owner
                ON object_owners(owner_id, object_type, expires_at);
            """
        )
        # Forward-only compatibility for a local database first opened by the
        # unmerged predecessor. Legacy rows remain visibly unbound and make
        # integrity fail closed; only the table shape is migrated.
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(effect_outbox)")
        }
        migrations = {
            "generation_id": "TEXT",
            "owner_id": "TEXT",
            "canonical_identity": "TEXT",
            "claim_token": "TEXT",
        }
        for name, declaration in migrations.items():
            if name not in columns:
                connection.execute(
                    f"ALTER TABLE effect_outbox ADD COLUMN {name} {declaration}"
                )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_effect_outbox_owner "
            "ON effect_outbox(owner_id, status, created_at)"
        )
        connection.execute(
            "INSERT OR IGNORE INTO workspace_meta(key, value) VALUES (?, ?)",
            ("generation_id", secrets.token_hex(16)),
        )

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        preserve_verified_cache = self._cached_integrity_is_current()
        with _PROCESS_WRITE_LOCK:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.execute("COMMIT")
                if preserve_verified_cache:
                    self._mark_integrity_preserved()
            except Exception:
                connection.execute("ROLLBACK")
                raise
            finally:
                connection.close()

    def generation_id(self) -> str:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT value FROM workspace_meta WHERE key = 'generation_id'"
            ).fetchone()
            if row is None or len(row["value"]) != 32:
                raise RuntimeError("workspace generation identity is unavailable")
            return str(row["value"])
        finally:
            connection.close()

    def readiness(self) -> Dict[str, Any]:
        """Run bounded startup checks; exhaustive evidence checks stay explicit."""
        violations = []
        observed_journal = "UNKNOWN"
        generation_id = ""
        try:
            with self._connect() as connection:
                observed_journal = str(
                    connection.execute("PRAGMA journal_mode").fetchone()[0]
                ).upper()
                if observed_journal != self.journal_mode:
                    violations.append("JOURNAL_MODE_MISMATCH")
                placeholders = ",".join("?" for _ in _REQUIRED_RUNTIME_TABLES)
                rows = connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name IN (" + placeholders + ")",
                    tuple(sorted(_REQUIRED_RUNTIME_TABLES)),
                ).fetchall()
                present = {str(row["name"]) for row in rows}
                missing = sorted(_REQUIRED_RUNTIME_TABLES - present)
                if missing:
                    violations.append("MISSING_RUNTIME_TABLES:" + ",".join(missing))
                row = connection.execute(
                    "SELECT value FROM workspace_meta WHERE key = 'generation_id'"
                ).fetchone()
                generation_id = str(row["value"]) if row is not None else ""
                if not generation_id:
                    violations.append("GENERATION_ID_UNAVAILABLE")
        except Exception as exc:
            violations.append("READINESS_ERROR:" + type(exc).__name__)
        return {
            "ok": not violations,
            "journal_mode": observed_journal,
            "generation_id": generation_id,
            "violations": violations,
            "scope": "BOUNDED_RUNTIME_READINESS",
        }

    def _storage_signature(self) -> Tuple[Tuple[str, int, int], ...]:
        signature = []
        for candidate in (self.path, Path(str(self.path) + "-wal")):
            try:
                stat = candidate.stat()
            except FileNotFoundError:
                continue
            signature.append((candidate.name, stat.st_size, stat.st_mtime_ns))
        for variable in ("GDW_PROOF_DIR", "GDW_RECEIPT_PROJECTION_DIR"):
            configured = os.environ.get(variable, "").strip()
            if not configured:
                continue
            root = Path(configured).resolve()
            try:
                root_stat = root.stat()
            except FileNotFoundError:
                signature.append((variable + ":MISSING", 0, 0))
                continue
            signature.append(
                (variable + ":.", root_stat.st_size, root_stat.st_mtime_ns)
            )
            for candidate in sorted(root.rglob("*.json")):
                try:
                    stat = candidate.stat()
                except FileNotFoundError:
                    signature.append(
                        (
                            variable + ":" + candidate.relative_to(root).as_posix(),
                            -1,
                            -1,
                        )
                    )
                    continue
                signature.append(
                    (
                        variable + ":" + candidate.relative_to(root).as_posix(),
                        stat.st_size,
                        stat.st_mtime_ns,
                    )
                )
        return tuple(signature)

    def _cached_integrity_is_current(self) -> bool:
        key = str(self.path)
        signature = self._storage_signature()
        with _INTEGRITY_CACHE_LOCK:
            cached = _RUNTIME_INTEGRITY_CACHE.get(key)
            return bool(
                cached
                and cached.get("ok") is True
                and cached.get("storage_signature") == signature
            )

    def _mark_integrity_preserved(self) -> None:
        key = str(self.path)
        with _INTEGRITY_CACHE_LOCK:
            cached = _RUNTIME_INTEGRITY_CACHE.get(key)
            if cached and cached.get("ok") is True:
                cached["storage_signature"] = self._storage_signature()

    def runtime_integrity(self) -> Dict[str, Any]:
        """Cache a full verified result until storage changes outside a write."""
        key = str(self.path)
        signature = self._storage_signature()
        with _INTEGRITY_CACHE_LOCK:
            cached = _RUNTIME_INTEGRITY_CACHE.get(key)
            if cached and cached.get("storage_signature") == signature:
                result = dict(cached["result"])
                result["cache_hit"] = True
                result["scope"] = "CACHED_FULL_INTEGRITY"
                return result

        result = dict(self.integrity())
        result["cache_hit"] = False
        result["scope"] = "FULL_INTEGRITY_REFRESH"
        with _INTEGRITY_CACHE_LOCK:
            _RUNTIME_INTEGRITY_CACHE[key] = {
                "ok": result.get("ok") is True,
                "storage_signature": self._storage_signature(),
                "result": dict(result),
            }
        return result

    @staticmethod
    def object_owner(
        connection: sqlite3.Connection,
        object_type: str,
        object_id: str,
    ) -> Optional[str]:
        if object_type not in _OBJECT_TYPES:
            raise ValueError("unsupported object owner type")
        row = connection.execute(
            "SELECT owner_id FROM object_owners "
            "WHERE object_type = ? AND object_id = ?",
            (object_type, object_id),
        ).fetchone()
        return None if row is None else str(row["owner_id"])

    @classmethod
    def require_object_owner(
        cls,
        connection: sqlite3.Connection,
        object_type: str,
        object_id: str,
        owner_id: str,
    ) -> None:
        persisted = cls.object_owner(connection, object_type, object_id)
        if persisted is None or persisted != owner_id:
            raise PermissionError(f"{object_type} is not owned by this principal")

    @classmethod
    def claim_object_owner(
        cls,
        connection: sqlite3.Connection,
        object_type: str,
        object_id: str,
        owner_id: str,
        created_at: str,
        expires_at: str,
    ) -> None:
        persisted = cls.object_owner(connection, object_type, object_id)
        if persisted is not None:
            if persisted != owner_id:
                raise PermissionError(
                    f"{object_type} is not owned by this principal"
                )
            connection.execute(
                "UPDATE object_owners SET expires_at = ? "
                "WHERE object_type = ? AND object_id = ?",
                (expires_at, object_type, object_id),
            )
            return
        connection.execute(
            "INSERT INTO object_owners("
            "object_type, object_id, owner_id, created_at, expires_at"
            ") VALUES (?, ?, ?, ?, ?)",
            (object_type, object_id, owner_id, created_at, expires_at),
        )

    @staticmethod
    def reclaim_expired(
        connection: sqlite3.Connection,
        now_text: str,
    ) -> Dict[str, int]:
        reclaimed = {"requests": 0, "sessions": 0}
        requests = connection.execute(
            "SELECT object_id FROM object_owners "
            "WHERE object_type = 'request' AND expires_at <= ?",
            (now_text,),
        ).fetchall()
        for row in requests:
            request_id = str(row["object_id"])
            pending = int(
                connection.execute(
                    "SELECT COUNT(*) FROM effect_outbox "
                    "WHERE request_id = ? AND status != 'EXPORTED'",
                    (request_id,),
                ).fetchone()[0]
            )
            if pending:
                continue
            connection.execute(
                "DELETE FROM effect_outbox WHERE request_id = ?", (request_id,)
            )
            connection.execute(
                "DELETE FROM evidence_intents WHERE request_id = ?", (request_id,)
            )
            connection.execute(
                "DELETE FROM receipts WHERE request_id = ?", (request_id,)
            )
            connection.execute(
                "DELETE FROM requests WHERE request_id = ?", (request_id,)
            )
            connection.execute(
                "DELETE FROM object_owners "
                "WHERE object_type = 'request' AND object_id = ?",
                (request_id,),
            )
            reclaimed["requests"] += 1

        sessions = connection.execute(
            "SELECT object_id FROM object_owners "
            "WHERE object_type = 'session' AND expires_at <= ?",
            (now_text,),
        ).fetchall()
        for row in sessions:
            session_id = str(row["object_id"])
            retained_requests = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM requests r
                    JOIN object_owners o
                      ON o.object_type = 'request'
                     AND o.object_id = r.request_id
                    WHERE r.session_id = ?
                      AND (
                        o.expires_at > ?
                        OR EXISTS (
                          SELECT 1 FROM effect_outbox e
                          WHERE e.request_id = r.request_id
                            AND e.status != 'EXPORTED'
                        )
                      )
                    """,
                    (session_id, now_text),
                ).fetchone()[0]
            )
            if retained_requests:
                continue
            connection.execute(
                "DELETE FROM session_state WHERE session_id = ?", (session_id,)
            )
            connection.execute(
                "DELETE FROM object_owners "
                "WHERE object_type = 'session' AND object_id = ?",
                (session_id,),
            )
            reclaimed["sessions"] += 1
        return reclaimed

    @classmethod
    def admit_request(
        cls,
        connection: sqlite3.Connection,
        *,
        owner_id: str,
        request_id: str,
        session_id: str,
        mutates: bool,
        created_at: str,
        expires_at: str,
        limits: Dict[str, int],
    ) -> None:
        cls.reclaim_expired(connection, created_at)
        if connection.execute(
            "SELECT 1 FROM requests WHERE request_id = ?", (request_id,)
        ).fetchone():
            cls.require_object_owner(
                connection, "request", request_id, owner_id
            )
            return

        owner_requests = int(
            connection.execute(
                "SELECT COUNT(*) FROM object_owners "
                "WHERE object_type = 'request' AND owner_id = ?",
                (owner_id,),
            ).fetchone()[0]
        )
        global_requests = int(
            connection.execute(
                "SELECT COUNT(*) FROM object_owners "
                "WHERE object_type = 'request'"
            ).fetchone()[0]
        )
        if owner_requests >= limits["owner_requests"]:
            raise OverflowError("per-owner request quota exceeded")
        if global_requests >= limits["global_requests"]:
            raise OverflowError("global request quota exceeded")

        existing_session = connection.execute(
            "SELECT 1 FROM session_state WHERE session_id = ?", (session_id,)
        ).fetchone()
        if existing_session is not None:
            cls.claim_object_owner(
                connection,
                "session",
                session_id,
                owner_id,
                created_at,
                expires_at,
            )
        elif mutates:
            owner_sessions = int(
                connection.execute(
                    "SELECT COUNT(*) FROM object_owners "
                    "WHERE object_type = 'session' AND owner_id = ?",
                    (owner_id,),
                ).fetchone()[0]
            )
            global_sessions = int(
                connection.execute(
                    "SELECT COUNT(*) FROM object_owners "
                    "WHERE object_type = 'session'"
                ).fetchone()[0]
            )
            if owner_sessions >= limits["owner_sessions"]:
                raise OverflowError("per-owner session quota exceeded")
            if global_sessions >= limits["global_sessions"]:
                raise OverflowError("global session quota exceeded")
            cls.claim_object_owner(
                connection,
                "session",
                session_id,
                owner_id,
                created_at,
                expires_at,
            )

        cls.claim_object_owner(
            connection,
            "request",
            request_id,
            owner_id,
            created_at,
            expires_at,
        )

    @staticmethod
    def cached_request(
        connection: sqlite3.Connection,
        request_id: str,
        owner_id: str,
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        row = connection.execute(
            "SELECT request_digest, response_json FROM requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        GDWWorkspace.require_object_owner(
            connection, "request", request_id, owner_id
        )
        return row["request_digest"], json.loads(row["response_json"])

    @staticmethod
    def session_state(
        connection: sqlite3.Connection,
        session_id: str,
        owner_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if owner_id is not None:
            GDWWorkspace.require_object_owner(
                connection, "session", session_id, owner_id
            )
        row = connection.execute(
            "SELECT step, state_json, state_hash, updated_at "
            "FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "session_id": session_id,
            "step": int(row["step"]),
            "state": json.loads(row["state_json"]),
            "state_hash": row["state_hash"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def save_state(
        connection: sqlite3.Connection,
        session_id: str,
        step: int,
        state: Dict[str, Any],
        state_hash: str,
        updated_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO session_state(session_id, step, state_json, state_hash, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                step = excluded.step,
                state_json = excluded.state_json,
                state_hash = excluded.state_hash,
                updated_at = excluded.updated_at
            """,
            (
                session_id,
                step,
                json.dumps(state, sort_keys=True, separators=(",", ":")),
                state_hash,
                updated_at,
            ),
        )

    @staticmethod
    def save_request(
        connection: sqlite3.Connection,
        request_id: str,
        request_digest: str,
        session_id: str,
        response: Dict[str, Any],
        response_hash: str,
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO requests(
                request_id, request_digest, session_id, response_json,
                response_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                request_digest,
                session_id,
                json.dumps(response, sort_keys=True, separators=(",", ":")),
                response_hash,
                created_at,
            ),
        )

    @staticmethod
    def save_receipt(
        connection: sqlite3.Connection,
        receipt_hash: str,
        request_id: str,
        session_id: str,
        step: int,
        receipt: Dict[str, Any],
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO receipts(
                receipt_hash, request_id, session_id, step, receipt_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_hash,
                request_id,
                session_id,
                step,
                json.dumps(receipt, sort_keys=True, separators=(",", ":")),
                created_at,
            ),
        )

    @staticmethod
    def save_proof_outbox(
        connection: sqlite3.Connection,
        proposal_id: str,
        payload: Dict[str, Any],
        payload_sha256: str,
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO proof_outbox(
                proposal_id, payload_json, payload_sha256, status, created_at
            ) VALUES (?, ?, ?, 'PENDING', ?)
            """,
            (
                proposal_id,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                payload_sha256,
                created_at,
            ),
        )

    @staticmethod
    def save_effect_outbox(
        connection: sqlite3.Connection,
        request_id: str,
        kind: str,
        generation_id: str,
        owner_id: str,
        canonical_identity: str,
        payload: Dict[str, Any],
        payload_sha256: str,
        idempotency_key: str,
        created_at: str,
    ) -> None:
        if kind not in _EFFECT_KINDS:
            raise ValueError("unsupported effect kind")
        canonical_payload = _canonical_json(payload)
        actual_payload_sha256 = hashlib.sha256(
            canonical_payload.encode("utf-8")
        ).hexdigest()
        if payload_sha256 != actual_payload_sha256:
            raise ValueError("effect payload_sha256 does not match payload")
        expected_identity = (
            payload.get("receipt_hash")
            if kind == "receipt_projection"
            else payload.get("payload_sha256")
        )
        if canonical_identity != expected_identity:
            raise ValueError("effect canonical identity does not match payload")
        request = connection.execute(
            "SELECT request_digest FROM requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if request is None:
            raise ValueError("effect request is missing")
        if (
            payload.get("request_id") != request_id
            or payload.get("request_digest") != request["request_digest"]
            or payload.get("owner_id") != owner_id
            or payload.get("generation_id") != generation_id
        ):
            raise ValueError("effect payload identity is not request-bound")
        if GDWWorkspace.object_owner(
            connection, "request", request_id
        ) != owner_id:
            raise ValueError("effect owner is not request-bound")
        expected_key = _effect_identity_key(
            generation_id=generation_id,
            owner_id=owner_id,
            request_id=request_id,
            request_digest=request["request_digest"],
            kind=kind,
            canonical_identity=canonical_identity,
            payload_sha256=payload_sha256,
        )
        if idempotency_key != expected_key:
            raise ValueError("effect idempotency identity mismatch")
        connection.execute(
            """
            INSERT INTO evidence_intents(
                canonical_identity, request_id, kind, generation_id, owner_id,
                payload_json, payload_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                canonical_identity,
                request_id,
                kind,
                generation_id,
                owner_id,
                canonical_payload,
                payload_sha256,
                created_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO effect_outbox(
                idempotency_key, request_id, kind, generation_id, owner_id,
                canonical_identity, payload_json, payload_sha256, status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            (
                idempotency_key,
                request_id,
                kind,
                generation_id,
                owner_id,
                canonical_identity,
                canonical_payload,
                payload_sha256,
                created_at,
            ),
        )

    def claim_effects(
        self,
        worker_id: str,
        limit: int = 100,
        lease_seconds: int = 300,
        max_attempts: Optional[int] = None,
    ) -> list:
        if not worker_id or len(worker_id) > 128:
            raise ValueError("worker_id must contain 1-128 characters")
        bounded = max(1, min(int(limit), 10000))
        lease = max(1, min(int(lease_seconds), 3600))
        attempt_ceiling = max(
            1,
            min(
                int(
                    max_attempts
                    if max_attempts is not None
                    else os.environ.get("GDW_MAX_EFFECT_ATTEMPTS", "20")
                ),
                100,
            ),
        )
        now = datetime.now(timezone.utc)
        now_text = now.isoformat()
        lease_until = (now + timedelta(seconds=lease)).isoformat()
        claimed = []
        with self.transaction() as connection:
            connection.execute(
                """
                UPDATE effect_outbox
                SET status = 'PENDING', lease_owner = NULL, lease_until = NULL,
                    claim_token = NULL
                WHERE status = 'CLAIMED' AND lease_until <= ?
                """,
                (now_text,),
            )
            rows = connection.execute(
                """
                SELECT idempotency_key, request_id, kind, generation_id,
                       owner_id, canonical_identity, payload_json,
                       payload_sha256, attempts
                FROM effect_outbox
                WHERE status = 'PENDING' AND attempts < ?
                      AND generation_id IS NOT NULL
                      AND owner_id IS NOT NULL
                      AND canonical_identity IS NOT NULL
                ORDER BY created_at, idempotency_key
                LIMIT ?
                """,
                (attempt_ceiling, bounded),
            ).fetchall()
            for row in rows:
                claim_token = secrets.token_hex(16)
                updated = connection.execute(
                    """
                    UPDATE effect_outbox
                    SET status = 'CLAIMED', lease_owner = ?, lease_until = ?,
                        claim_token = ?, attempts = attempts + 1,
                        last_error = NULL
                    WHERE idempotency_key = ? AND status = 'PENDING'
                    """,
                    (
                        worker_id,
                        lease_until,
                        claim_token,
                        row["idempotency_key"],
                    ),
                )
                if updated.rowcount != 1:
                    continue
                claimed.append(
                    {
                        "idempotency_key": row["idempotency_key"],
                        "request_id": row["request_id"],
                        "kind": row["kind"],
                        "generation_id": row["generation_id"],
                        "owner_id": row["owner_id"],
                        "canonical_identity": row["canonical_identity"],
                        "payload": json.loads(row["payload_json"]),
                        "payload_sha256": row["payload_sha256"],
                        "attempt": int(row["attempts"]) + 1,
                        "lease_owner": worker_id,
                        "lease_until": lease_until,
                        "claim_token": claim_token,
                    }
                )
        return claimed

    @staticmethod
    def _validate_effect_binding(
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> None:
        payload = json.loads(row["payload_json"])
        payload_json = _canonical_json(payload)
        payload_sha256 = hashlib.sha256(
            payload_json.encode("utf-8")
        ).hexdigest()
        if payload_sha256 != row["payload_sha256"]:
            raise ValueError("effect outbox payload digest mismatch")
        expected_identity = (
            payload.get("receipt_hash")
            if row["kind"] == "receipt_projection"
            else payload.get("payload_sha256")
        )
        if expected_identity != row["canonical_identity"]:
            raise ValueError("effect outbox canonical identity mismatch")

        intent = connection.execute(
            """
            SELECT request_id, kind, generation_id, owner_id, payload_json,
                   payload_sha256
            FROM evidence_intents WHERE canonical_identity = ?
            """,
            (row["canonical_identity"],),
        ).fetchone()
        if intent is None:
            raise ValueError("canonical evidence intent is missing")
        expected = (
            row["request_id"],
            row["kind"],
            row["generation_id"],
            row["owner_id"],
            payload_json,
            row["payload_sha256"],
        )
        actual = (
            intent["request_id"],
            intent["kind"],
            intent["generation_id"],
            intent["owner_id"],
            intent["payload_json"],
            intent["payload_sha256"],
        )
        if actual != expected:
            raise ValueError("effect outbox diverges from canonical intent")

        owner = GDWWorkspace.object_owner(
            connection, "request", row["request_id"]
        )
        if owner != row["owner_id"]:
            raise ValueError("effect owner diverges from request owner")
        request = connection.execute(
            "SELECT request_digest, response_json FROM requests "
            "WHERE request_id = ?",
            (row["request_id"],),
        ).fetchone()
        if request is None:
            raise ValueError("effect request is missing")
        response = json.loads(request["response_json"])
        if (
            payload.get("request_id") != row["request_id"]
            or payload.get("request_digest") != request["request_digest"]
            or payload.get("owner_id") != row["owner_id"]
            or payload.get("generation_id") != row["generation_id"]
        ):
            raise ValueError("effect payload identity diverges from request")
        expected_key = _effect_identity_key(
            generation_id=row["generation_id"],
            owner_id=row["owner_id"],
            request_id=row["request_id"],
            request_digest=request["request_digest"],
            kind=row["kind"],
            canonical_identity=row["canonical_identity"],
            payload_sha256=row["payload_sha256"],
        )
        if row["idempotency_key"] != expected_key:
            raise ValueError("effect idempotency identity mismatch")
        generation = connection.execute(
            "SELECT value FROM workspace_meta WHERE key = 'generation_id'"
        ).fetchone()
        if generation is None or generation["value"] != row["generation_id"]:
            raise ValueError("effect generation identity mismatch")

        if row["kind"] == "receipt_projection":
            receipt = connection.execute(
                "SELECT receipt_json FROM receipts "
                "WHERE receipt_hash = ? AND request_id = ?",
                (row["canonical_identity"], row["request_id"]),
            ).fetchone()
            if receipt is None or receipt["receipt_json"] != payload_json:
                raise ValueError("receipt projection diverges from receipt ledger")
            if response.get("receipt_hash") != row["canonical_identity"]:
                raise ValueError("receipt projection diverges from response")
        else:
            unsigned_payload = dict(payload)
            embedded_digest = unsigned_payload.pop("payload_sha256", None)
            if (
                embedded_digest != row["canonical_identity"]
                or _sha256_json(unsigned_payload) != embedded_digest
                or response.get("proof", {}).get("canonical_identity")
                != row["canonical_identity"]
                or response.get("proof", {}).get("idempotency_key")
                != row["idempotency_key"]
            ):
                raise ValueError("proof export diverges from canonical response")

    def validate_claimed_effect(self, claim: Dict[str, Any]) -> None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM effect_outbox WHERE idempotency_key = ?",
                (claim["idempotency_key"],),
            ).fetchone()
            if row is None:
                raise ValueError("effect outbox row is missing")
            if (
                row["status"] != "CLAIMED"
                or row["lease_owner"] != claim["lease_owner"]
                or row["claim_token"] != claim["claim_token"]
                or row["lease_until"] <= datetime.now(timezone.utc).isoformat()
            ):
                raise RuntimeError("effect claim is stale or fenced")
            self._validate_effect_binding(connection, row)
        finally:
            connection.close()

    def mark_effect_exported(
        self,
        idempotency_key: str,
        worker_id: str,
        claim_token: str,
        artifact: Dict[str, Any],
        exported_at: str,
    ) -> None:
        if artifact.get("artifact_identity") != idempotency_key:
            raise ValueError("artifact identity does not match effect key")
        if artifact.get("immutable") is not True:
            raise ValueError("artifact is not marked immutable")
        path = Path(str(artifact.get("path") or "")).resolve()
        if not path.is_file():
            raise ValueError("exported artifact is missing")
        artifact_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if artifact_sha256 != artifact.get("sha256"):
            raise ValueError("exported artifact digest mismatch")
        now_text = datetime.now(timezone.utc).isoformat()
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM effect_outbox WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                raise RuntimeError("effect claim is absent")
            self._validate_effect_binding(connection, row)
            owner_scope = hashlib.sha256(
                row["owner_id"].encode("utf-8")
            ).hexdigest()[:32]
            configured_root = (
                os.environ.get("GDW_PROOF_DIR", "output/proofs")
                if row["kind"] == "proof_export"
                else os.environ.get(
                    "GDW_RECEIPT_PROJECTION_DIR", "output/gdw/receipts"
                )
            )
            expected_parent = (Path(configured_root).resolve() / owner_scope)
            if (
                artifact.get("owner_scope") != owner_scope
                or path.parent != expected_parent
                or path.name != f"{idempotency_key}.json"
            ):
                raise ValueError("artifact path is not owner- and effect-bound")
            updated = connection.execute(
                """
                UPDATE effect_outbox
                SET status = 'EXPORTED', artifact_json = ?, exported_at = ?,
                    lease_owner = NULL, lease_until = NULL, claim_token = NULL,
                    last_error = NULL
                WHERE idempotency_key = ? AND status = 'CLAIMED'
                      AND lease_owner = ? AND claim_token = ?
                      AND lease_until > ?
                """,
                (
                    json.dumps(artifact, sort_keys=True, separators=(",", ":")),
                    exported_at,
                    idempotency_key,
                    worker_id,
                    claim_token,
                    now_text,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError("effect claim is absent, expired, or owned elsewhere")

    def release_effect(
        self,
        idempotency_key: str,
        worker_id: str,
        claim_token: str,
        error: str,
    ) -> bool:
        with self.transaction() as connection:
            updated = connection.execute(
                """
                UPDATE effect_outbox SET status = 'PENDING',
                    lease_owner = NULL, lease_until = NULL, claim_token = NULL,
                    last_error = ?
                WHERE idempotency_key = ? AND status = 'CLAIMED'
                      AND lease_owner = ? AND claim_token = ?
                """,
                (
                    str(error)[:1024],
                    idempotency_key,
                    worker_id,
                    claim_token,
                ),
            )
            return updated.rowcount == 1

    def pending_proofs(self, limit: int = 100) -> list:
        bounded = max(1, min(int(limit), 10000))
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT proposal_id, payload_json, payload_sha256
                FROM proof_outbox
                WHERE status = 'PENDING'
                ORDER BY created_at, proposal_id
                LIMIT ?
                """,
                (bounded,),
            ).fetchall()
            return [
                {
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
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                UPDATE proof_outbox
                SET status = 'EXPORTED', artifact_json = ?, exported_at = ?
                WHERE proposal_id = ? AND status = 'PENDING'
                """,
                (
                    json.dumps(artifact, sort_keys=True, separators=(",", ":")),
                    exported_at,
                    proposal_id,
                ),
            )

    def read_session(
        self,
        session_id: str,
        owner_id: str,
    ) -> Optional[Dict[str, Any]]:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT 1 FROM session_state WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            self.require_object_owner(
                connection, "session", session_id, owner_id
            )
            return self.session_state(connection, session_id)
        finally:
            connection.close()

    def integrity(self) -> Dict[str, Any]:
        connection = self._connect()
        try:
            check = connection.execute("PRAGMA integrity_check").fetchone()[0]
            counts = {}
            for table in (
                "session_state",
                "requests",
                "receipts",
                "proof_outbox",
                "effect_outbox",
                "object_owners",
                "evidence_intents",
            ):
                counts[table] = int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
            pending_proofs = int(
                connection.execute(
                    "SELECT COUNT(*) FROM proof_outbox WHERE status = 'PENDING'"
                ).fetchone()[0]
            )
            pending_effects = int(
                connection.execute(
                    "SELECT COUNT(*) FROM effect_outbox "
                    "WHERE status IN ('PENDING', 'CLAIMED')"
                ).fetchone()[0]
            )
            claimed_effects = int(
                connection.execute(
                    "SELECT COUNT(*) FROM effect_outbox WHERE status = 'CLAIMED'"
                ).fetchone()[0]
            )
            orphan_receipts = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM receipts r
                    LEFT JOIN requests q ON q.request_id = r.request_id
                    WHERE q.request_id IS NULL
                    """
                ).fetchone()[0]
            )
            violations = {
                "orphan_receipts": orphan_receipts,
                "unowned_sessions": int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM session_state s
                        LEFT JOIN object_owners o
                          ON o.object_type = 'session'
                         AND o.object_id = s.session_id
                        WHERE o.object_id IS NULL
                        """
                    ).fetchone()[0]
                ),
                "unowned_requests": int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM requests r
                        LEFT JOIN object_owners o
                          ON o.object_type = 'request'
                         AND o.object_id = r.request_id
                        WHERE o.object_id IS NULL
                        """
                    ).fetchone()[0]
                ),
                "legacy_pending_proofs": pending_proofs,
                "state_digest_mismatches": 0,
                "response_digest_mismatches": 0,
                "receipt_digest_mismatches": 0,
                "intent_digest_mismatches": 0,
                "effect_binding_mismatches": 0,
                "artifact_mismatches": 0,
                "dead_effects": 0,
            }

            for row in connection.execute(
                "SELECT state_json, state_hash FROM session_state"
            ):
                try:
                    if _sha256_json(json.loads(row["state_json"])) != row["state_hash"]:
                        violations["state_digest_mismatches"] += 1
                except Exception:
                    violations["state_digest_mismatches"] += 1

            for row in connection.execute(
                "SELECT response_json, response_hash FROM requests"
            ):
                try:
                    if (
                        _sha256_json(json.loads(row["response_json"]))
                        != row["response_hash"]
                    ):
                        violations["response_digest_mismatches"] += 1
                except Exception:
                    violations["response_digest_mismatches"] += 1

            for row in connection.execute(
                "SELECT receipt_hash, receipt_json FROM receipts"
            ):
                try:
                    payload = json.loads(row["receipt_json"])
                    embedded = payload.pop("receipt_hash")
                    if (
                        embedded != row["receipt_hash"]
                        or _sha256_json(payload) != row["receipt_hash"]
                    ):
                        violations["receipt_digest_mismatches"] += 1
                except Exception:
                    violations["receipt_digest_mismatches"] += 1

            for row in connection.execute("SELECT * FROM evidence_intents"):
                try:
                    payload = json.loads(row["payload_json"])
                    full_digest = _sha256_json(payload)
                    identity = (
                        payload.get("receipt_hash")
                        if row["kind"] == "receipt_projection"
                        else payload.get("payload_sha256")
                    )
                    if (
                        full_digest != row["payload_sha256"]
                        or identity != row["canonical_identity"]
                    ):
                        violations["intent_digest_mismatches"] += 1
                except Exception:
                    violations["intent_digest_mismatches"] += 1

            attempt_ceiling = max(
                1,
                min(int(os.environ.get("GDW_MAX_EFFECT_ATTEMPTS", "20")), 100),
            )
            for row in connection.execute("SELECT * FROM effect_outbox"):
                try:
                    self._validate_effect_binding(connection, row)
                except Exception:
                    violations["effect_binding_mismatches"] += 1
                if (
                    row["status"] != "EXPORTED"
                    and int(row["attempts"]) >= attempt_ceiling
                ):
                    violations["dead_effects"] += 1
                if row["status"] == "EXPORTED":
                    try:
                        artifact = json.loads(row["artifact_json"])
                        path = Path(str(artifact["path"])).resolve()
                        owner_scope = hashlib.sha256(
                            row["owner_id"].encode("utf-8")
                        ).hexdigest()[:32]
                        configured_root = (
                            os.environ.get("GDW_PROOF_DIR", "output/proofs")
                            if row["kind"] == "proof_export"
                            else os.environ.get(
                                "GDW_RECEIPT_PROJECTION_DIR",
                                "output/gdw/receipts",
                            )
                        )
                        if (
                            artifact.get("immutable") is not True
                            or artifact.get("owner_scope") != owner_scope
                            or artifact.get("artifact_identity")
                            != row["idempotency_key"]
                            or path.parent
                            != Path(configured_root).resolve() / owner_scope
                            or path.name
                            != f"{row['idempotency_key']}.json"
                            or not path.is_file()
                            or hashlib.sha256(path.read_bytes()).hexdigest()
                            != artifact.get("sha256")
                        ):
                            violations["artifact_mismatches"] += 1
                    except Exception:
                        violations["artifact_mismatches"] += 1

            generation = connection.execute(
                "SELECT value FROM workspace_meta WHERE key = 'generation_id'"
            ).fetchone()
            generation_id = str(generation["value"]) if generation else ""
            if len(generation_id) != 32:
                violations["effect_binding_mismatches"] += 1
            observed_journal = str(
                connection.execute("PRAGMA journal_mode").fetchone()[0]
            ).upper()
            if observed_journal != self.journal_mode:
                violations["effect_binding_mismatches"] += 1
            violation_count = sum(int(value) for value in violations.values())
            return {
                "ok": check == "ok" and violation_count == 0,
                "sqlite_integrity": check,
                "orphan_receipts": orphan_receipts,
                "pending_proofs": pending_proofs,
                "pending_effects": pending_effects,
                "claimed_effects": claimed_effects,
                "counts": counts,
                "violations": violations,
                "generation_id": generation_id,
                "path": str(self.path),
                "journal_mode": observed_journal,
                "wal": observed_journal == "WAL",
                "synchronous": "NORMAL",
            }
        finally:
            connection.close()
