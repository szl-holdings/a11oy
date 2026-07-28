"""Concurrency-safe SQLite state, idempotency, and receipt storage for GDW."""

import contextlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple


_SCHEMA_LOCK = threading.RLock()
_PROCESS_WRITE_LOCK = threading.RLock()
_INITIALISED_PATHS = set()


class GDWWorkspace:
    def __init__(self, path: Optional[str] = None):
        configured = path or os.environ.get("GDW_DB_PATH", "output/gdw/gdw.sqlite3")
        self.path = Path(configured).resolve()
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
                connection.execute("PRAGMA journal_mode=WAL")
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
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK(status IN ('PENDING', 'CLAIMED', 'EXPORTED')),
                attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
                lease_owner TEXT,
                lease_until TEXT,
                last_error TEXT,
                artifact_json TEXT,
                created_at TEXT NOT NULL,
                exported_at TEXT,
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
            """
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

    @staticmethod
    def cached_request(
        connection: sqlite3.Connection,
        request_id: str,
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        row = connection.execute(
            "SELECT request_digest, response_json FROM requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return row["request_digest"], json.loads(row["response_json"])

    @staticmethod
    def session_state(
        connection: sqlite3.Connection,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
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
        payload: Dict[str, Any],
        payload_sha256: str,
        idempotency_key: str,
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO effect_outbox(
                idempotency_key, request_id, kind, payload_json,
                payload_sha256, status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            (
                idempotency_key,
                request_id,
                kind,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                payload_sha256,
                created_at,
            ),
        )

    def claim_effects(
        self,
        worker_id: str,
        limit: int = 100,
        lease_seconds: int = 300,
    ) -> list:
        if not worker_id or len(worker_id) > 128:
            raise ValueError("worker_id must contain 1-128 characters")
        bounded = max(1, min(int(limit), 10000))
        lease = max(1, min(int(lease_seconds), 3600))
        now = datetime.now(timezone.utc)
        now_text = now.isoformat()
        lease_until = (now + timedelta(seconds=lease)).isoformat()
        claimed = []
        with self.transaction() as connection:
            connection.execute(
                """
                UPDATE effect_outbox
                SET status = 'PENDING', lease_owner = NULL, lease_until = NULL
                WHERE status = 'CLAIMED' AND lease_until <= ?
                """,
                (now_text,),
            )
            rows = connection.execute(
                """
                SELECT idempotency_key, request_id, kind, payload_json,
                       payload_sha256, attempts
                FROM effect_outbox
                WHERE status = 'PENDING'
                ORDER BY created_at, idempotency_key
                LIMIT ?
                """,
                (bounded,),
            ).fetchall()
            for row in rows:
                updated = connection.execute(
                    """
                    UPDATE effect_outbox
                    SET status = 'CLAIMED', lease_owner = ?, lease_until = ?,
                        attempts = attempts + 1, last_error = NULL
                    WHERE idempotency_key = ? AND status = 'PENDING'
                    """,
                    (worker_id, lease_until, row["idempotency_key"]),
                )
                if updated.rowcount != 1:
                    continue
                claimed.append(
                    {
                        "idempotency_key": row["idempotency_key"],
                        "request_id": row["request_id"],
                        "kind": row["kind"],
                        "payload": json.loads(row["payload_json"]),
                        "payload_sha256": row["payload_sha256"],
                        "attempt": int(row["attempts"]) + 1,
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
    ) -> None:
        with self.transaction() as connection:
            updated = connection.execute(
                """
                UPDATE effect_outbox
                SET status = 'EXPORTED', artifact_json = ?, exported_at = ?,
                    lease_owner = NULL, lease_until = NULL, last_error = NULL
                WHERE idempotency_key = ? AND status = 'CLAIMED'
                      AND lease_owner = ?
                """,
                (
                    json.dumps(artifact, sort_keys=True, separators=(",", ":")),
                    exported_at,
                    idempotency_key,
                    worker_id,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError("effect claim is absent, expired, or owned elsewhere")

    def release_effect(
        self,
        idempotency_key: str,
        worker_id: str,
        error: str,
    ) -> None:
        with self.transaction() as connection:
            updated = connection.execute(
                """
                UPDATE effect_outbox
                SET status = 'PENDING', lease_owner = NULL, lease_until = NULL,
                    last_error = ?
                WHERE idempotency_key = ? AND status = 'CLAIMED'
                      AND lease_owner = ?
                """,
                (str(error)[:1024], idempotency_key, worker_id),
            )
            if updated.rowcount != 1:
                raise RuntimeError("effect claim is absent, expired, or owned elsewhere")

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

    def read_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        connection = self._connect()
        try:
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
            return {
                "ok": check == "ok" and orphan_receipts == 0,
                "sqlite_integrity": check,
                "orphan_receipts": orphan_receipts,
                "pending_proofs": pending_proofs,
                "pending_effects": pending_effects,
                "claimed_effects": claimed_effects,
                "counts": counts,
                "path": str(self.path),
                "wal": True,
                "synchronous": "NORMAL",
            }
        finally:
            connection.close()
