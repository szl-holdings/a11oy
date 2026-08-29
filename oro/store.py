# SPDX-License-Identifier: Apache-2.0
"""Strict SQLite evidence store for ORO v1."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import (
    BarrierDecision,
    OROContractError,
    OROStateError,
    canonical_json,
    receipt_digest,
    utc_now,
)

SCHEMA_VERSION = 1


class OROStore:
    """Durable, transaction-bound ORO evidence ledger.

    Production requires an absolute on-disk path. SQLite foreign keys, WAL,
    bounded busy waits, strict tables, and an integrity probe are enabled. The
    store is safe for FastAPI's threadpool through a process-local re-entrant
    lock; multi-process serialization remains SQLite's responsibility.
    """

    def __init__(self, path: str | Path, *, production: bool) -> None:
        raw = str(path)
        self.production = bool(production)
        if self.production:
            if raw == ":memory:":
                raise OROContractError("production ORO cannot use an in-memory database")
            resolved = Path(raw)
            if not resolved.is_absolute():
                raise OROContractError("production ORO database path must be absolute")
        self.path = Path(raw) if raw != ":memory:" else Path(raw)
        if raw != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock = threading.RLock()
        try:
            self.connection = sqlite3.connect(
                raw,
                timeout=10.0,
                isolation_level=None,
                check_same_thread=False,
            )
        except sqlite3.Error as exc:
            raise OROStateError("ORO database could not be opened") from exc
        self.connection.row_factory = sqlite3.Row
        self._configure()
        self._migrate()
        if raw != ":memory:":
            try:
                os.chmod(self.path, 0o600)
            except OSError as exc:
                if self.production:
                    raise OROStateError("ORO database permissions could not be hardened") from exc

    def _configure(self) -> None:
        with self._lock:
            self.connection.execute("PRAGMA foreign_keys=ON")
            self.connection.execute("PRAGMA busy_timeout=10000")
            self.connection.execute("PRAGMA trusted_schema=OFF")
            if str(self.path) != ":memory:":
                mode = str(self.connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
                if self.production and mode != "wal":
                    raise OROStateError("production ORO requires SQLite WAL mode")
                self.connection.execute("PRAGMA synchronous=FULL")

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def _migrate(self) -> None:
        with self._lock:
            version = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
            if version not in (0, SCHEMA_VERSION):
                raise OROStateError(f"unsupported ORO schema version: {version}")
            if version == SCHEMA_VERSION:
                return
            try:
                self.connection.executescript(
                    """
                    BEGIN IMMEDIATE;
                    CREATE TABLE metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    ) STRICT;
                    CREATE TABLE plans (
                        plan_id TEXT PRIMARY KEY,
                        plan_digest TEXT NOT NULL UNIQUE,
                        orbit_kind TEXT NOT NULL CHECK(orbit_kind IN ('discovery','evolution','task')),
                        objective TEXT NOT NULL,
                        body_json TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('ADMITTED','RUNNING','COMPLETE','REFUSED')),
                        candidate_author TEXT NOT NULL,
                        evaluator_author TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        CHECK(candidate_author <> evaluator_author)
                    ) STRICT;
                    CREATE TABLE orbit_runs (
                        orbit_id TEXT PRIMARY KEY,
                        plan_id TEXT NOT NULL REFERENCES plans(plan_id),
                        generation INTEGER NOT NULL CHECK(generation >= 0),
                        current_rank_json TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('RUNNING','COMPLETE','REFUSED')),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    ) STRICT;
                    CREATE TABLE arrivals (
                        orbit_id TEXT NOT NULL REFERENCES orbit_runs(orbit_id),
                        generation INTEGER NOT NULL CHECK(generation >= 0),
                        participant_id TEXT NOT NULL,
                        payload_digest TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        received_at TEXT NOT NULL,
                        PRIMARY KEY (orbit_id, generation, participant_id)
                    ) STRICT;
                    CREATE TABLE barriers (
                        barrier_id TEXT PRIMARY KEY,
                        orbit_id TEXT NOT NULL REFERENCES orbit_runs(orbit_id),
                        generation INTEGER NOT NULL CHECK(generation >= 0),
                        decision TEXT NOT NULL CHECK(decision IN ('CONTINUE','COMPLETE','REFUSE')),
                        reason TEXT NOT NULL,
                        semantic_hash TEXT NOT NULL,
                        rank_before_json TEXT NOT NULL,
                        rank_after_json TEXT NOT NULL,
                        objective_converged INTEGER NOT NULL CHECK(objective_converged IN (0,1)),
                        codex_digest TEXT NOT NULL,
                        receipt_digest TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL
                    ) STRICT;
                    CREATE TABLE rank_allocations (
                        allocation_digest TEXT PRIMARY KEY,
                        orbit_id TEXT NOT NULL REFERENCES orbit_runs(orbit_id),
                        receipt_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    ) STRICT;
                    CREATE TABLE invariant_results (
                        barrier_id TEXT NOT NULL REFERENCES barriers(barrier_id),
                        invariant_id TEXT NOT NULL,
                        version TEXT NOT NULL,
                        passed INTEGER NOT NULL CHECK(passed IN (0,1)),
                        blocking INTEGER NOT NULL CHECK(blocking IN (0,1)),
                        detail TEXT NOT NULL,
                        source_blob_digest TEXT NOT NULL,
                        implementation_digest TEXT NOT NULL,
                        golden_vectors_digest TEXT NOT NULL,
                        PRIMARY KEY (barrier_id, invariant_id, version)
                    ) STRICT;
                    CREATE TABLE semantic_hashes (
                        orbit_id TEXT NOT NULL REFERENCES orbit_runs(orbit_id),
                        semantic_hash TEXT NOT NULL,
                        generation INTEGER NOT NULL CHECK(generation >= 0),
                        created_at TEXT NOT NULL,
                        PRIMARY KEY (orbit_id, semantic_hash)
                    ) STRICT;
                    CREATE TABLE negative_results (
                        negative_id INTEGER PRIMARY KEY,
                        orbit_id TEXT REFERENCES orbit_runs(orbit_id),
                        plan_id TEXT REFERENCES plans(plan_id),
                        barrier_id TEXT,
                        reason TEXT NOT NULL,
                        evidence_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    ) STRICT;
                    CREATE TABLE comparisons (
                        comparison_id TEXT PRIMARY KEY,
                        orbit_id TEXT NOT NULL REFERENCES orbit_runs(orbit_id),
                        candidate_digest TEXT NOT NULL,
                        baseline_digest TEXT NOT NULL,
                        evaluator_digest TEXT NOT NULL,
                        outcome TEXT NOT NULL CHECK(outcome IN ('NOMINATE','REJECT','INCONCLUSIVE')),
                        evidence_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    ) STRICT;
                    CREATE TABLE approvals (
                        barrier_id TEXT NOT NULL REFERENCES barriers(barrier_id),
                        approver TEXT NOT NULL,
                        approval_digest TEXT NOT NULL,
                        approval_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY (barrier_id, approver)
                    ) STRICT;
                    CREATE TABLE receipts (
                        receipt_digest TEXT PRIMARY KEY,
                        barrier_id TEXT NOT NULL UNIQUE REFERENCES barriers(barrier_id),
                        body_json TEXT NOT NULL,
                        envelope_json TEXT NOT NULL,
                        signer_identity_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    ) STRICT;
                    CREATE TABLE certificates (
                        certificate_id TEXT PRIMARY KEY,
                        orbit_id TEXT NOT NULL REFERENCES orbit_runs(orbit_id),
                        kind TEXT NOT NULL CHECK(kind IN ('intent','completion','refusal')),
                        body_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    ) STRICT;
                    INSERT INTO metadata(key, value) VALUES ('schema', 'szl.oro.sqlite/v1');
                    PRAGMA user_version=1;
                    COMMIT;
                    """
                )
            except sqlite3.Error as exc:
                try:
                    self.connection.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise OROStateError("ORO database migration failed") from exc

    @staticmethod
    def _decode(row: sqlite3.Row | None, *json_columns: str) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        for column in json_columns:
            if column in result:
                result[column.removesuffix("_json")] = json.loads(result.pop(column))
        return result

    def integrity(self) -> Mapping[str, Any]:
        with self._lock:
            try:
                result = str(self.connection.execute("PRAGMA integrity_check").fetchone()[0])
                foreign = self.connection.execute("PRAGMA foreign_key_check").fetchall()
                version = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
                journal = str(self.connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            except sqlite3.Error as exc:
                return {
                    "ready": False,
                    "state": "UNAVAILABLE",
                    "error_class": type(exc).__name__,
                }
        ready = result == "ok" and not foreign and version == SCHEMA_VERSION
        if self.production:
            ready = ready and journal == "wal" and str(self.path) != ":memory:"
        return {
            "ready": ready,
            "state": "READY" if ready else "DEGRADED",
            "integrity_check": result,
            "foreign_key_violations": len(foreign),
            "schema_version": version,
            "journal_mode": journal,
            "durable": str(self.path) != ":memory:",
            "path_exposed": False,
        }

    def create_plan(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        plan_id = str(body["plan_id"])
        digest = str(body["plan_digest"])
        encoded = canonical_json(body).decode("utf-8")
        now = utc_now()
        with self._lock:
            existing = self.connection.execute(
                "SELECT plan_digest, body_json FROM plans WHERE plan_id=?", (plan_id,)
            ).fetchone()
            if existing is not None:
                if existing["plan_digest"] != digest or existing["body_json"] != encoded:
                    raise OROStateError("plan ID already exists with different content")
                return self.get_plan(plan_id) or {}
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                self.connection.execute(
                    """INSERT INTO plans
                       (plan_id, plan_digest, orbit_kind, objective, body_json, status,
                        candidate_author, evaluator_author, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 'ADMITTED', ?, ?, ?, ?)""",
                    (
                        plan_id,
                        digest,
                        body["orbit_kind"],
                        body["objective"],
                        encoded,
                        body["candidate_author"],
                        body["evaluator_author"],
                        now,
                        now,
                    ),
                )
                self.connection.execute("COMMIT")
            except sqlite3.Error as exc:
                self.connection.execute("ROLLBACK")
                raise OROStateError("plan persistence failed") from exc
        return self.get_plan(plan_id) or {}

    def get_plan(self, plan_id: str) -> Mapping[str, Any] | None:
        with self._lock:
            row = self.connection.execute("SELECT * FROM plans WHERE plan_id=?", (plan_id,)).fetchone()
        return self._decode(row, "body_json")

    def list_plans(self, *, limit: int = 100) -> list[Mapping[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM plans ORDER BY created_at DESC, plan_id LIMIT ?", (limit,)
            ).fetchall()
        return [self._decode(row, "body_json") or {} for row in rows]

    def create_orbit(
        self,
        *,
        orbit_id: str,
        plan_id: str,
        generation: int,
        rank: Rank,
    ) -> Mapping[str, Any]:
        now = utc_now()
        encoded_rank = canonical_json(rank.as_dict()).decode("utf-8")
        with self._lock:
            existing = self.connection.execute(
                "SELECT * FROM orbit_runs WHERE orbit_id=?", (orbit_id,)
            ).fetchone()
            if existing is not None:
                if (
                    existing["plan_id"] != plan_id
                    or int(existing["generation"]) != generation
                    or existing["current_rank_json"] != encoded_rank
                    or existing["status"] != "RUNNING"
                ):
                    raise OROStateError("orbit ID already exists with a different durable frontier")
                return self._decode(existing, "current_rank_json") or {}
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                self.connection.execute(
                    "INSERT INTO orbit_runs "
                    "(orbit_id, plan_id, generation, current_rank_json, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 'RUNNING', ?, ?)",
                    (orbit_id, plan_id, generation, encoded_rank, now, now),
                )
                self.connection.execute(
                    "UPDATE plans SET status='RUNNING', updated_at=? WHERE plan_id=?",
                    (now, plan_id),
                )
                self.connection.execute("COMMIT")
            except sqlite3.Error as exc:
                self.connection.execute("ROLLBACK")
                raise OROStateError("orbit persistence failed") from exc
        return self.get_orbit(orbit_id) or {}

    def get_orbit(self, orbit_id: str) -> Mapping[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM orbit_runs WHERE orbit_id=?", (orbit_id,)
            ).fetchone()
        return self._decode(row, "current_rank_json")

    def list_orbits(self, *, plan_id: str | None = None, limit: int = 100) -> list[Mapping[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._lock:
            if plan_id:
                rows = self.connection.execute(
                    "SELECT * FROM orbit_runs WHERE plan_id=? ORDER BY created_at DESC LIMIT ?",
                    (plan_id, limit),
                ).fetchall()
            else:
                rows = self.connection.execute(
                    "SELECT * FROM orbit_runs ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._decode(row, "current_rank_json") or {} for row in rows]

    def seen_semantic_hash(self, orbit_id: str, digest: str) -> bool:
        with self._lock:
            row = self.connection.execute(
                "SELECT 1 FROM semantic_hashes WHERE orbit_id=? AND semantic_hash=?",
                (orbit_id, digest),
            ).fetchone()
        return row is not None

    def persist_barrier(
        self,
        *,
        plan_id: str,
        arrivals: Sequence[Mapping[str, Any]],
        allocation_receipt: Mapping[str, Any] | None,
        decision: BarrierDecision,
    ) -> Mapping[str, Any]:
        encoded_body = canonical_json(decision.receipt).decode("utf-8")
        encoded_envelope = canonical_json(decision.envelope).decode("utf-8")
        signer_identity = decision.envelope.get("signer", {})
        encoded_signer = canonical_json(signer_identity).decode("utf-8")
        digest = str(decision.receipt["receipt_digest"])
        now = utc_now()
        status_by_decision = {
            "CONTINUE": "RUNNING",
            "COMPLETE": "COMPLETE",
            "REFUSE": "REFUSED",
        }
        status = status_by_decision[decision.decision]
        next_generation = (
            decision.generation + 1 if decision.decision == "CONTINUE" else decision.generation
        )
        encoded_rank_after = canonical_json(decision.rank_after.as_dict()).decode("utf-8")
        with self._lock:
            existing = self.connection.execute(
                "SELECT receipt_digest FROM barriers WHERE barrier_id=?",
                (decision.barrier_id,),
            ).fetchone()
            if existing is not None:
                if existing["receipt_digest"] != digest:
                    raise OROStateError("barrier ID already exists with different receipt")
                return self.get_barrier(decision.barrier_id) or {}
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                for item in arrivals:
                    prior = self.connection.execute(
                        """SELECT payload_digest FROM arrivals
                           WHERE orbit_id=? AND generation=? AND participant_id=?""",
                        (
                            decision.orbit_id,
                            decision.generation,
                            item["participant_id"],
                        ),
                    ).fetchone()
                    if prior is not None and prior["payload_digest"] != item["payload_digest"]:
                        raise OROStateError("conflicting durable duplicate arrival")
                    self.connection.execute(
                        """INSERT OR IGNORE INTO arrivals
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            decision.orbit_id,
                            decision.generation,
                            item["participant_id"],
                            item["payload_digest"],
                            canonical_json(item["payload"]).decode("utf-8"),
                            item["received_at"],
                        ),
                    )
                if allocation_receipt is not None:
                    allocation_digest = str(allocation_receipt.get("digest", ""))
                    if not allocation_digest:
                        raise OROContractError("allocation receipt has no digest")
                    self.connection.execute(
                        "INSERT OR IGNORE INTO rank_allocations VALUES (?, ?, ?, ?)",
                        (
                            allocation_digest,
                            decision.orbit_id,
                            canonical_json(allocation_receipt).decode("utf-8"),
                            now,
                        ),
                    )
                self.connection.execute(
                    """INSERT INTO barriers
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        decision.barrier_id,
                        decision.orbit_id,
                        decision.generation,
                        decision.decision,
                        decision.reason,
                        decision.semantic_digest,
                        canonical_json(decision.rank_before.as_dict()).decode("utf-8"),
                        canonical_json(decision.rank_after.as_dict()).decode("utf-8"),
                        1 if decision.objective_converged else 0,
                        decision.receipt["codex_digest"],
                        digest,
                        now,
                    ),
                )
                for result in decision.invariant_results:
                    self.connection.execute(
                        """INSERT INTO invariant_results
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            decision.barrier_id,
                            result["invariant_id"],
                            result["version"],
                            1 if result["passed"] else 0,
                            1 if result["blocking"] else 0,
                            result["detail"],
                            result["source_blob_digest"],
                            result["implementation_digest"],
                            result["golden_vectors_digest"],
                        ),
                    )
                self.connection.execute(
                    "INSERT OR IGNORE INTO semantic_hashes VALUES (?, ?, ?, ?)",
                    (decision.orbit_id, decision.semantic_digest, decision.generation, now),
                )
                self.connection.execute(
                    "INSERT INTO receipts VALUES (?, ?, ?, ?, ?, ?)",
                    (digest, decision.barrier_id, encoded_body, encoded_envelope, encoded_signer, now),
                )
                cursor = self.connection.execute(
                    "UPDATE orbit_runs "
                    "SET generation=?, current_rank_json=?, status=?, updated_at=? "
                    "WHERE orbit_id=? AND generation=? AND status='RUNNING'",
                    (
                        next_generation,
                        encoded_rank_after,
                        status,
                        now,
                        decision.orbit_id,
                        decision.generation,
                    ),
                )
                if cursor.rowcount != 1:
                    raise OROStateError("barrier does not match the durable orbit frontier")
                self.connection.execute(
                    "UPDATE plans SET status=?, updated_at=? WHERE plan_id=?",
                    (status, now, plan_id),
                )
                self.connection.execute("COMMIT")
            except (sqlite3.Error, OROContractError, OROStateError) as exc:
                self.connection.execute("ROLLBACK")
                if isinstance(exc, (OROContractError, OROStateError)):
                    raise
                raise OROStateError("barrier evidence transaction failed") from exc
        return self.get_barrier(decision.barrier_id) or {}

    def get_barrier(self, barrier_id: str) -> Mapping[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                """SELECT b.*, r.body_json, r.envelope_json, r.signer_identity_json
                   FROM barriers b JOIN receipts r ON r.barrier_id=b.barrier_id
                   WHERE b.barrier_id=?""",
                (barrier_id,),
            ).fetchone()
        return self._decode(
            row,
            "rank_before_json",
            "rank_after_json",
            "body_json",
            "envelope_json",
            "signer_identity_json",
        )

    def list_barriers(self, orbit_id: str, *, limit: int = 200) -> list[Mapping[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            rows = self.connection.execute(
                """SELECT b.*, r.signer_identity_json
                   FROM barriers b JOIN receipts r ON r.barrier_id=b.barrier_id
                   WHERE b.orbit_id=? ORDER BY b.generation, b.created_at LIMIT ?""",
                (orbit_id, limit),
            ).fetchall()
        return [
            self._decode(row, "rank_before_json", "rank_after_json", "signer_identity_json") or {}
            for row in rows
        ]

    def record_negative(
        self,
        *,
        reason: str,
        evidence: Mapping[str, Any],
        plan_id: str | None = None,
        orbit_id: str | None = None,
        barrier_id: str | None = None,
    ) -> int:
        with self._lock:
            cursor = self.connection.execute(
                """INSERT INTO negative_results
                   (orbit_id, plan_id, barrier_id, reason, evidence_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    orbit_id,
                    plan_id,
                    barrier_id,
                    reason,
                    canonical_json(evidence).decode("utf-8"),
                    utc_now(),
                ),
            )
        return int(cursor.lastrowid)

    def list_negative_results(self, *, orbit_id: str | None = None, limit: int = 200) -> list[Mapping[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            if orbit_id:
                rows = self.connection.execute(
                    """SELECT * FROM negative_results WHERE orbit_id=?
                       ORDER BY negative_id DESC LIMIT ?""",
                    (orbit_id, limit),
                ).fetchall()
            else:
                rows = self.connection.execute(
                    "SELECT * FROM negative_results ORDER BY negative_id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._decode(row, "evidence_json") or {} for row in rows]

    def create_certificate(
        self,
        *,
        certificate_id: str,
        orbit_id: str,
        kind: str,
        body: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        encoded = canonical_json(body).decode("utf-8")
        with self._lock:
            existing = self.connection.execute(
                "SELECT * FROM certificates WHERE certificate_id=?", (certificate_id,)
            ).fetchone()
            if existing is not None:
                decoded = self._decode(existing, "body_json") or {}
                if canonical_json(decoded["body"]).decode("utf-8") != encoded:
                    raise OROStateError("certificate ID already exists with different content")
                return decoded
            self.connection.execute(
                "INSERT INTO certificates VALUES (?, ?, ?, ?, ?)",
                (certificate_id, orbit_id, kind, encoded, utc_now()),
            )
        return self.get_certificate(certificate_id) or {}

    def get_certificate(self, certificate_id: str) -> Mapping[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM certificates WHERE certificate_id=?", (certificate_id,)
            ).fetchone()
        return self._decode(row, "body_json")

    def list_certificates(self, orbit_id: str, *, limit: int = 200) -> list[Mapping[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            rows = self.connection.execute(
                """SELECT * FROM certificates WHERE orbit_id=?
                   ORDER BY created_at, certificate_id LIMIT ?""",
                (orbit_id, limit),
            ).fetchall()
        return [self._decode(row, "body_json") or {} for row in rows]

    def approve(
        self,
        *,
        barrier_id: str,
        approver: str,
        approval: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        with self._lock:
            row = self.connection.execute(
                """SELECT p.candidate_author, p.evaluator_author
                   FROM barriers b
                   JOIN orbit_runs o ON o.orbit_id=b.orbit_id
                   JOIN plans p ON p.plan_id=o.plan_id
                   WHERE b.barrier_id=?""",
                (barrier_id,),
            ).fetchone()
            if row is None:
                raise OROStateError("barrier does not exist")
            if approver in {row["candidate_author"], row["evaluator_author"]}:
                raise OROContractError(
                    "approver must be independent of candidate and evaluator authors"
                )
            digest = receipt_digest(approval)
            existing = self.connection.execute(
                "SELECT approval_digest FROM approvals WHERE barrier_id=? AND approver=?",
                (barrier_id, approver),
            ).fetchone()
            if existing is not None and existing["approval_digest"] != digest:
                raise OROStateError("approver already submitted a different decision")
            self.connection.execute(
                "INSERT OR IGNORE INTO approvals VALUES (?, ?, ?, ?, ?)",
                (
                    barrier_id,
                    approver,
                    digest,
                    canonical_json(approval).decode("utf-8"),
                    utc_now(),
                ),
            )
        return {
            "barrier_id": barrier_id,
            "approver": approver,
            "approval_digest": digest,
            "idempotent": existing is not None,
        }

    def counts(self) -> Mapping[str, int]:
        tables = (
            "plans", "orbit_runs", "barriers", "rank_allocations", "invariant_results",
            "semantic_hashes", "negative_results", "comparisons", "approvals", "receipts",
            "certificates",
        )
        with self._lock:
            return {
                table: int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in tables
            }
