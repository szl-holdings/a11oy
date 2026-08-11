from __future__ import annotations

"""SQLite-backed content-addressed State Bus with append-only hash-chain events."""

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .canonical import (
    b64url_decode,
    canonical_json_bytes,
    canonical_json_text,
    digest_bytes,
    digest_object,
    isoformat_utc,
    parse_utc,
    require_digest,
    require_identifier,
    utc_now,
)
from .enums import WorkflowState
from .errors import IdempotencyConflict, IntegrityError, StateTransitionError, ValidationError
from .merkle import InclusionProof, inclusion_proof, merkle_root, verify_inclusion

GENESIS_HASH = digest_bytes(b"szl-council-state-bus-genesis/v1")

_ALLOWED_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.CREATED: {WorkflowState.RESEARCHING, WorkflowState.DELIBERATING, WorkflowState.BLOCKED, WorkflowState.FAILED},
    WorkflowState.RESEARCHING: {WorkflowState.DELIBERATING, WorkflowState.BLOCKED, WorkflowState.FAILED},
    WorkflowState.DELIBERATING: {WorkflowState.GATED, WorkflowState.BLOCKED, WorkflowState.FAILED},
    WorkflowState.GATED: {WorkflowState.EXECUTING, WorkflowState.BLOCKED, WorkflowState.FAILED},
    WorkflowState.EXECUTING: {WorkflowState.VERIFYING, WorkflowState.ROLLED_BACK, WorkflowState.FAILED},
    WorkflowState.VERIFYING: {WorkflowState.SETTLED, WorkflowState.ROLLED_BACK, WorkflowState.FAILED},
    WorkflowState.SETTLED: set(),
    WorkflowState.ROLLED_BACK: set(),
    WorkflowState.BLOCKED: set(),
    WorkflowState.FAILED: set(),
}


@dataclass(frozen=True, slots=True)
class IdempotencyReservation:
    state: str
    action_digest: str
    receipt_digest: str | None

    @property
    def replay(self) -> bool:
        return self.state == "SETTLED" and self.receipt_digest is not None


class StateBus:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.exists() and (self.path.is_symlink() or not self.path.is_file()):
            raise ValidationError("State Bus path must be a regular file")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.parent.is_symlink():
            raise ValidationError("State Bus parent directory must not be a symbolic link")
        self._lock = threading.RLock()
        self._initialize()
        os.chmod(self.path, 0o600)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS objects (
                    digest TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    canonical_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    case_id TEXT,
                    event_type TEXT NOT NULL,
                    payload_digest TEXT NOT NULL REFERENCES objects(digest),
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_case_seq ON events(case_id, seq);
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    case_digest TEXT NOT NULL REFERENCES objects(digest),
                    envelope_digest TEXT NOT NULL REFERENCES objects(digest),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    action_digest TEXT NOT NULL,
                    state TEXT NOT NULL,
                    receipt_digest TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_digest TEXT PRIMARY KEY REFERENCES objects(digest),
                    case_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    signed_envelope_digest TEXT REFERENCES objects(digest),
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS receipts_case ON receipts(case_id, created_at);
                CREATE TABLE IF NOT EXISTS transparency (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload_digest TEXT NOT NULL REFERENCES objects(digest),
                    leaf_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS negative_capabilities (
                    entry_id TEXT PRIMARY KEY,
                    task_class TEXT NOT NULL,
                    tool TEXT,
                    domain TEXT,
                    condition_code TEXT NOT NULL,
                    epoch_digest TEXT NOT NULL,
                    status TEXT NOT NULL,
                    evidence_digest TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                );
                CREATE INDEX IF NOT EXISTS negative_lookup ON negative_capabilities(task_class, tool, domain, status);
                CREATE TABLE IF NOT EXISTS outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    contract_digest TEXT NOT NULL REFERENCES objects(digest),
                    settlement_digest TEXT REFERENCES objects(digest),
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute("INSERT OR IGNORE INTO metadata(key, value) VALUES('schema', 'szl.state-bus/v1')")
            conn.execute("INSERT OR IGNORE INTO metadata(key, value) VALUES('genesis_hash', ?)", (GENESIS_HASH,))

    def _begin(self, conn: sqlite3.Connection) -> None:
        conn.execute("BEGIN IMMEDIATE")

    def _store_object(self, conn: sqlite3.Connection, kind: str, value: Any, created_at: str) -> str:
        digest = digest_object(value)
        encoded = canonical_json_text(value)
        existing = conn.execute("SELECT canonical_json, kind FROM objects WHERE digest=?", (digest,)).fetchone()
        if existing is not None:
            if existing["canonical_json"] != encoded:
                raise IntegrityError("content-addressed object collision")
            if existing["kind"] != kind:
                raise IntegrityError(
                    f"content-addressed object kind mismatch: existing={existing['kind']} requested={kind}"
                )
            return digest
        conn.execute(
            "INSERT INTO objects(digest, kind, canonical_json, created_at) VALUES(?,?,?,?)",
            (digest, kind, encoded, created_at),
        )
        return digest

    def store_object(self, kind: str, value: Any, *, created_at: str | datetime | None = None) -> str:
        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                digest = self._store_object(conn, kind, value, timestamp)
                conn.execute("COMMIT")
                return digest
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def get_object(self, digest: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT canonical_json FROM objects WHERE digest=?", (digest,)).fetchone()
        if row is None:
            raise KeyError(digest)
        return json.loads(row["canonical_json"])

    def _append_event(
        self,
        conn: sqlite3.Connection,
        *,
        event_id: str,
        case_id: str | None,
        event_type: str,
        payload: Any,
        created_at: str,
    ) -> dict[str, Any]:
        if not event_id or len(event_id) > 256:
            raise ValidationError("event_id must be bounded")
        payload_digest = self._store_object(conn, f"event:{event_type}", payload, created_at)
        prior = conn.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        previous_hash = prior["event_hash"] if prior else GENESIS_HASH
        next_seq = conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM events").fetchone()["next_seq"]
        body = {
            "schema": "szl.state-event/v1",
            "seq": next_seq,
            "event_id": event_id,
            "case_id": case_id,
            "event_type": event_type,
            "payload_digest": payload_digest,
            "previous_hash": previous_hash,
            "created_at": created_at,
        }
        event_hash = digest_object(body)
        conn.execute(
            """INSERT INTO events(seq,event_id,case_id,event_type,payload_digest,previous_hash,event_hash,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (next_seq, event_id, case_id, event_type, payload_digest, previous_hash, event_hash, created_at),
        )
        return {**body, "event_hash": event_hash}

    def append_event(
        self,
        *,
        event_id: str,
        case_id: str | None,
        event_type: str,
        payload: Any,
        created_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                event = self._append_event(
                    conn,
                    event_id=event_id,
                    case_id=case_id,
                    event_type=event_type,
                    payload=payload,
                    created_at=timestamp,
                )
                conn.execute("COMMIT")
                return event
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def create_case(
        self,
        *,
        case_id: str,
        case_value: Any,
        envelope_value: Any,
        created_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                if conn.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone():
                    raise ValidationError(f"case already exists: {case_id}")
                case_digest = self._store_object(conn, "council-case", case_value, timestamp)
                envelope_digest = self._store_object(conn, "autonomy-envelope", envelope_value, timestamp)
                conn.execute(
                    "INSERT INTO cases(case_id,state,case_digest,envelope_digest,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (case_id, WorkflowState.CREATED.value, case_digest, envelope_digest, timestamp, timestamp),
                )
                event = self._append_event(
                    conn,
                    event_id=f"{case_id}:created",
                    case_id=case_id,
                    event_type="CASE_CREATED",
                    payload={"case_digest": case_digest, "envelope_digest": envelope_digest, "state": WorkflowState.CREATED.value},
                    created_at=timestamp,
                )
                conn.execute("COMMIT")
                return {"case_id": case_id, "state": WorkflowState.CREATED.value, "case_digest": case_digest, "envelope_digest": envelope_digest, "event": event}
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def begin_attempt_and_case(
        self,
        *,
        case_id: str,
        case_value: Any,
        envelope_value: Any,
        idempotency_key: str,
        action_digest: str,
        created_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        """Atomically reserve one governed attempt and create its case.

        This closes the crash window between case creation and idempotency
        reservation. A caller either obtains both durable records, observes an
        existing exact reservation, or obtains neither.
        """

        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                existing = conn.execute(
                    "SELECT * FROM idempotency WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if existing is not None:
                    if existing["action_digest"] != action_digest:
                        raise IdempotencyConflict(
                            "idempotency key was previously bound to a different action"
                        )
                    conn.execute("COMMIT")
                    return {
                        "reservation": IdempotencyReservation(
                            existing["state"], existing["action_digest"], existing["receipt_digest"]
                        ),
                        "case": None,
                    }
                if conn.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone():
                    raise IntegrityError(
                        "case exists without the exact idempotency reservation; operator recovery is required"
                    )
                conn.execute(
                    "INSERT INTO idempotency(idempotency_key,action_digest,state,receipt_digest,created_at,updated_at) "
                    "VALUES(?,?,'IN_FLIGHT',NULL,?,?)",
                    (idempotency_key, action_digest, timestamp, timestamp),
                )
                case_digest = self._store_object(conn, "council-case", case_value, timestamp)
                envelope_digest = self._store_object(conn, "autonomy-envelope", envelope_value, timestamp)
                conn.execute(
                    "INSERT INTO cases(case_id,state,case_digest,envelope_digest,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        case_id,
                        WorkflowState.CREATED.value,
                        case_digest,
                        envelope_digest,
                        timestamp,
                        timestamp,
                    ),
                )
                event = self._append_event(
                    conn,
                    event_id=f"{case_id}:created",
                    case_id=case_id,
                    event_type="CASE_CREATED",
                    payload={
                        "case_digest": case_digest,
                        "envelope_digest": envelope_digest,
                        "state": WorkflowState.CREATED.value,
                        "idempotency_key_digest": digest_object(
                            {"schema": "szl.idempotency-key-reference/v1", "key": idempotency_key}
                        ),
                        "governed_attempt_digest": action_digest,
                    },
                    created_at=timestamp,
                )
                conn.execute("COMMIT")
                return {
                    "reservation": IdempotencyReservation("NEW", action_digest, None),
                    "case": {
                        "case_id": case_id,
                        "state": WorkflowState.CREATED.value,
                        "case_digest": case_digest,
                        "envelope_digest": envelope_digest,
                        "event": event,
                    },
                }
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def transition_case(
        self,
        case_id: str,
        target: WorkflowState | str,
        *,
        reason_codes: Sequence[str] = (),
        evidence: Mapping[str, Any] | None = None,
        created_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        target_state = target if isinstance(target, WorkflowState) else WorkflowState(target)
        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                row = conn.execute("SELECT state FROM cases WHERE case_id=?", (case_id,)).fetchone()
                if row is None:
                    raise KeyError(case_id)
                current = WorkflowState(row["state"])
                if target_state not in _ALLOWED_TRANSITIONS[current]:
                    raise StateTransitionError(f"illegal case transition: {current.value} -> {target_state.value}")
                payload = {
                    "from": current.value,
                    "to": target_state.value,
                    "reason_codes": list(reason_codes),
                    "evidence": dict(evidence or {}),
                }
                event = self._append_event(
                    conn,
                    event_id=f"{case_id}:transition:{current.value}:{target_state.value}",
                    case_id=case_id,
                    event_type="CASE_TRANSITION",
                    payload=payload,
                    created_at=timestamp,
                )
                conn.execute("UPDATE cases SET state=?, updated_at=? WHERE case_id=?", (target_state.value, timestamp, case_id))
                conn.execute("COMMIT")
                return {"case_id": case_id, "from": current.value, "to": target_state.value, "event_hash": event["event_hash"]}
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def get_case(self, case_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
            if row is None:
                raise KeyError(case_id)
            events = conn.execute("SELECT * FROM events WHERE case_id=? ORDER BY seq", (case_id,)).fetchall()
            receipts = conn.execute("SELECT * FROM receipts WHERE case_id=? ORDER BY created_at", (case_id,)).fetchall()
        return {
            "case": dict(row),
            "case_object": self.get_object(row["case_digest"]),
            "envelope_object": self.get_object(row["envelope_digest"]),
            "events": [dict(item) for item in events],
            "receipts": [dict(item) for item in receipts],
        }

    def list_cases(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1 or limit > 1000:
            raise ValidationError("case list limit must be 1..1000")
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM cases ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def lookup_idempotency(self, idempotency_key: str) -> IdempotencyReservation | None:
        """Return the exact reservation without mutating it.

        The kernel uses this before creating workflow state so a previously
        settled request can replay without re-running council transitions or
        effects.  IN_FLIGHT and FAILED reservations remain explicit operator
        states; they are never silently retried.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state, action_digest, receipt_digest FROM idempotency WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
        if row is None:
            return None
        return IdempotencyReservation(row["state"], row["action_digest"], row["receipt_digest"])

    def reserve_idempotency(
        self,
        idempotency_key: str,
        action_digest: str,
        *,
        created_at: str | datetime | None = None,
    ) -> IdempotencyReservation:
        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                row = conn.execute("SELECT * FROM idempotency WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO idempotency(idempotency_key,action_digest,state,receipt_digest,created_at,updated_at) VALUES(?,?, 'IN_FLIGHT', NULL, ?, ?)",
                        (idempotency_key, action_digest, timestamp, timestamp),
                    )
                    conn.execute("COMMIT")
                    return IdempotencyReservation("NEW", action_digest, None)
                if row["action_digest"] != action_digest:
                    raise IdempotencyConflict("idempotency key was previously bound to a different action")
                conn.execute("COMMIT")
                return IdempotencyReservation(row["state"], row["action_digest"], row["receipt_digest"])
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def settle_idempotency(
        self,
        idempotency_key: str,
        action_digest: str,
        receipt_digest: str,
        *,
        created_at: str | datetime | None = None,
    ) -> None:
        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                row = conn.execute("SELECT * FROM idempotency WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if row is None or row["action_digest"] != action_digest:
                    raise IdempotencyConflict("cannot settle an unreserved or mismatched idempotency key")
                if row["state"] == "SETTLED" and row["receipt_digest"] != receipt_digest:
                    raise IdempotencyConflict("idempotency key is already settled to another receipt")
                conn.execute(
                    "UPDATE idempotency SET state='SETTLED', receipt_digest=?, updated_at=? WHERE idempotency_key=?",
                    (receipt_digest, timestamp, idempotency_key),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def abandon_idempotency(self, idempotency_key: str, action_digest: str, *, created_at: str | datetime | None = None) -> None:
        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                row = conn.execute("SELECT * FROM idempotency WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if row is None or row["action_digest"] != action_digest:
                    raise IdempotencyConflict("cannot abandon an unreserved or mismatched idempotency key")
                if row["state"] != "SETTLED":
                    conn.execute("UPDATE idempotency SET state='FAILED', updated_at=? WHERE idempotency_key=?", (timestamp, idempotency_key))
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def add_receipt(
        self,
        *,
        receipt: Mapping[str, Any],
        case_id: str,
        action_id: str,
        signed_envelope: Mapping[str, Any] | None,
        created_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                receipt_digest = self._store_object(conn, "action-receipt", receipt, timestamp)
                signed_digest = None
                if signed_envelope is not None:
                    signed_digest = self._store_object(conn, "signed-action-receipt", signed_envelope, timestamp)
                conn.execute(
                    "INSERT OR IGNORE INTO receipts(receipt_digest,case_id,action_id,signed_envelope_digest,created_at) VALUES(?,?,?,?,?)",
                    (receipt_digest, case_id, action_id, signed_digest, timestamp),
                )
                event = self._append_event(
                    conn,
                    event_id=f"{case_id}:receipt:{action_id}:{receipt_digest.split(':', 1)[1][:16]}",
                    case_id=case_id,
                    event_type="RECEIPT_RECORDED",
                    payload={"receipt_digest": receipt_digest, "signed_envelope_digest": signed_digest},
                    created_at=timestamp,
                )
                conn.execute("COMMIT")
                return {"receipt_digest": receipt_digest, "signed_envelope_digest": signed_digest, "event_hash": event["event_hash"]}
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def get_receipt(self, receipt_digest: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM receipts WHERE receipt_digest=?",
                (receipt_digest,),
            ).fetchone()
        if row is None:
            raise KeyError(receipt_digest)
        receipt = self.get_object(receipt_digest)
        signed = None
        if row["signed_envelope_digest"] is not None:
            signed = self.get_object(row["signed_envelope_digest"])
        return {
            "receipt": receipt,
            "receipt_digest": receipt_digest,
            "signed_receipt": signed,
            "case_id": row["case_id"],
            "action_id": row["action_id"],
            "created_at": row["created_at"],
        }

    def previous_receipt_digest(self, case_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT receipt_digest FROM receipts WHERE case_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1", (case_id,)).fetchone()
        return None if row is None else row["receipt_digest"]

    def _append_transparency_in_transaction(
        self,
        conn: sqlite3.Connection,
        payload: Mapping[str, Any],
        *,
        created_at: str,
    ) -> dict[str, Any]:
        payload_digest = self._store_object(conn, "transparency-leaf", payload, created_at)
        leaf = digest_bytes(b"\x00" + canonical_json_bytes(payload))
        conn.execute(
            "INSERT INTO transparency(payload_digest,leaf_digest,created_at) VALUES(?,?,?)",
            (payload_digest, leaf, created_at),
        )
        row = conn.execute("SELECT last_insert_rowid() AS seq").fetchone()
        seq = int(row["seq"])
        rows = conn.execute("SELECT payload_digest FROM transparency ORDER BY seq").fetchall()
        leaves = [
            canonical_json_bytes(
                json.loads(
                    conn.execute(
                        "SELECT canonical_json FROM objects WHERE digest=?",
                        (item["payload_digest"],),
                    ).fetchone()["canonical_json"]
                )
            )
            for item in rows
        ]
        proof = inclusion_proof(leaves, seq - 1)
        return {
            "schema": "szl.local-transparency-registration/v1",
            "assurance_scope": "LOCAL_MERKLE_REFERENCE_ONLY",
            "sequence": seq,
            "payload_digest": payload_digest,
            "tree_size": len(leaves),
            "root_hash": proof.root_hash,
            "inclusion_proof": proof.to_dict(),
            "verified": verify_inclusion(leaves[seq - 1], proof),
        }

    def settle_attempt_receipt(
        self,
        *,
        idempotency_key: str,
        action_digest: str,
        receipt: Mapping[str, Any],
        case_id: str,
        action_id: str,
        signed_envelope: Mapping[str, Any],
        created_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        """Atomically record proof, transparency inclusion, and idempotent settlement."""

        timestamp = isoformat_utc(created_at or utc_now())
        receipt_digest = digest_object(receipt)
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                reservation = conn.execute(
                    "SELECT * FROM idempotency WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if reservation is None or reservation["action_digest"] != action_digest:
                    raise IdempotencyConflict(
                        "cannot settle an unreserved or mismatched governed attempt"
                    )
                if reservation["state"] == "FAILED":
                    raise IdempotencyConflict("failed governed attempt requires explicit recovery")
                if reservation["state"] == "SETTLED":
                    if reservation["receipt_digest"] != receipt_digest:
                        raise IdempotencyConflict(
                            "idempotency key is already settled to another receipt"
                        )
                    receipt_row = conn.execute(
                        "SELECT signed_envelope_digest,case_id,action_id FROM receipts WHERE receipt_digest=?",
                        (receipt_digest,),
                    ).fetchone()
                    if receipt_row is None:
                        raise IntegrityError(
                            "settled idempotency reservation references a missing receipt row"
                        )
                    if receipt_row["case_id"] != case_id or receipt_row["action_id"] != action_id:
                        raise IntegrityError(
                            "settled receipt metadata does not match the replay request"
                        )
                    conn.execute("COMMIT")
                    return {
                        "receipt_digest": receipt_digest,
                        "signed_envelope_digest": receipt_row["signed_envelope_digest"],
                        "event_hash": None,
                        "transparency": None,
                        "replayed": True,
                    }

                stored_receipt_digest = self._store_object(
                    conn, "action-receipt", dict(receipt), timestamp
                )
                if stored_receipt_digest != receipt_digest:
                    raise IntegrityError("receipt content address changed during settlement")
                signed_digest = self._store_object(
                    conn, "signed-action-receipt", dict(signed_envelope), timestamp
                )
                existing_receipt = conn.execute(
                    "SELECT * FROM receipts WHERE receipt_digest=?",
                    (receipt_digest,),
                ).fetchone()
                if existing_receipt is None:
                    conn.execute(
                        "INSERT INTO receipts(receipt_digest,case_id,action_id,signed_envelope_digest,created_at) "
                        "VALUES(?,?,?,?,?)",
                        (receipt_digest, case_id, action_id, signed_digest, timestamp),
                    )
                elif (
                    existing_receipt["case_id"] != case_id
                    or existing_receipt["action_id"] != action_id
                    or existing_receipt["signed_envelope_digest"] != signed_digest
                ):
                    raise IntegrityError("receipt digest is rebound to different settlement metadata")

                event = self._append_event(
                    conn,
                    event_id=(
                        f"{case_id}:receipt:{action_id}:"
                        f"{receipt_digest.split(':', 1)[1][:16]}"
                    ),
                    case_id=case_id,
                    event_type="RECEIPT_RECORDED",
                    payload={
                        "receipt_digest": receipt_digest,
                        "signed_envelope_digest": signed_digest,
                        "governed_attempt_digest": action_digest,
                    },
                    created_at=timestamp,
                )
                transparency_payload = {
                    "schema": "szl.action-receipt-transparency-leaf/v1",
                    "receipt_digest": receipt_digest,
                    "signed_envelope_digest": signed_digest,
                    "case_id": case_id,
                    "action_id": action_id,
                    "governed_attempt_digest": action_digest,
                }
                transparency = self._append_transparency_in_transaction(
                    conn, transparency_payload, created_at=timestamp
                )
                if not transparency["verified"]:
                    raise IntegrityError("local transparency inclusion failed self-verification")
                conn.execute(
                    "UPDATE idempotency SET state='SETTLED', receipt_digest=?, updated_at=? "
                    "WHERE idempotency_key=?",
                    (receipt_digest, timestamp, idempotency_key),
                )
                conn.execute("COMMIT")
                return {
                    "receipt_digest": receipt_digest,
                    "signed_envelope_digest": signed_digest,
                    "event_hash": event["event_hash"],
                    "transparency": transparency,
                    "replayed": False,
                }
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def append_transparency(
        self,
        payload: Mapping[str, Any],
        *,
        created_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                result = self._append_transparency_in_transaction(
                    conn, payload, created_at=timestamp
                )
                conn.execute("COMMIT")
                return result
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def verify_transparency(self) -> dict[str, Any]:
        errors: list[str] = []
        leaves: list[bytes] = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT seq,payload_digest,leaf_digest,created_at FROM transparency ORDER BY seq"
            ).fetchall()
            expected_seq = 1
            for row in rows:
                seq = int(row["seq"])
                if seq != expected_seq:
                    errors.append(f"NON_CONTIGUOUS_SEQ:{seq} expected={expected_seq}")
                expected_seq += 1
                try:
                    require_digest(row["payload_digest"], field="payload_digest")
                    require_digest(row["leaf_digest"], field="leaf_digest")
                    parse_utc(row["created_at"])
                except ValidationError as exc:
                    errors.append(f"ROW_INVALID:{seq}:{type(exc).__name__}")
                obj = conn.execute(
                    "SELECT kind,canonical_json FROM objects WHERE digest=?",
                    (row["payload_digest"],),
                ).fetchone()
                if obj is None:
                    errors.append(f"MISSING_OBJECT:{row['payload_digest']}")
                    continue
                if obj["kind"] != "transparency-leaf":
                    errors.append(f"OBJECT_KIND_MISMATCH:{seq}:{obj['kind']}")
                try:
                    payload = json.loads(obj["canonical_json"])
                    encoded = canonical_json_bytes(payload)
                except (json.JSONDecodeError, ValidationError):
                    errors.append(f"PAYLOAD_INVALID:{seq}")
                    continue
                if encoded.decode("utf-8") != obj["canonical_json"]:
                    errors.append(f"PAYLOAD_NONCANONICAL:{seq}")
                if digest_object(payload) != row["payload_digest"]:
                    errors.append(f"PAYLOAD_DIGEST_MISMATCH:{seq}")
                observed_leaf = digest_bytes(b"\x00" + encoded)
                if observed_leaf != row["leaf_digest"]:
                    errors.append(f"LEAF_MISMATCH:{seq}")
                leaves.append(encoded)
        return {
            "schema": "szl.local-transparency-verification/v1",
            "status": "PASS" if not errors else "FAIL",
            "tree_size": len(rows),
            "valid_leaf_count": len(leaves),
            "root_hash": merkle_root(leaves) if len(leaves) == len(rows) else None,
            "errors": errors,
            "assurance_scope": "LOCAL_MERKLE_REFERENCE_ONLY",
        }

    def add_negative_capability(
        self,
        entry: Mapping[str, Any],
        *,
        created_at: str | datetime | None = None,
    ) -> str:
        """Record or resolve a negative-capability fact without rebinding its identity.

        Entry identity is immutable. Re-registering an exact record is idempotent;
        the only allowed update is ``ACTIVE`` → ``RESOLVED`` with the same task,
        tool, domain, condition, and cognitive epoch.
        """

        timestamp = isoformat_utc(created_at or utc_now())
        required = {"entry_id", "task_class", "condition_code", "epoch_digest", "status"}
        missing = required - set(entry)
        if missing:
            raise ValidationError(f"negative capability entry missing: {sorted(missing)}")
        entry_id = require_identifier(str(entry["entry_id"]), field="entry_id")
        task_class = require_identifier(str(entry["task_class"]), field="task_class")
        condition_code = require_identifier(str(entry["condition_code"]), field="condition_code")
        epoch_digest = require_digest(str(entry["epoch_digest"]), field="epoch_digest")
        status = str(entry["status"])
        if status not in {"ACTIVE", "RESOLVED"}:
            raise ValidationError("negative capability status must be ACTIVE or RESOLVED")
        tool = entry.get("tool")
        domain = entry.get("domain")
        if tool is not None:
            tool = require_identifier(str(tool), field="tool")
        if domain is not None:
            domain = require_identifier(str(domain), field="domain")
        evidence_digest = entry.get("evidence_digest")
        if evidence_digest is not None:
            evidence_digest = require_digest(str(evidence_digest), field="evidence_digest")
        expires_at = entry.get("expires_at")
        if expires_at is not None:
            expires_at = isoformat_utc(str(expires_at))
            if parse_utc(expires_at) <= parse_utc(timestamp):
                raise ValidationError("negative capability expiry must be after creation time")

        normalized = {
            "entry_id": entry_id,
            "task_class": task_class,
            "tool": tool,
            "domain": domain,
            "condition_code": condition_code,
            "epoch_digest": epoch_digest,
            "status": status,
            "evidence_digest": evidence_digest,
            "expires_at": expires_at,
        }
        digest = digest_object(normalized)
        immutable = (task_class, tool, domain, condition_code, epoch_digest)
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                existing = conn.execute(
                    "SELECT * FROM negative_capabilities WHERE entry_id=?", (entry_id,)
                ).fetchone()
                if existing is not None:
                    observed = (
                        existing["task_class"],
                        existing["tool"],
                        existing["domain"],
                        existing["condition_code"],
                        existing["epoch_digest"],
                    )
                    if observed != immutable:
                        raise IntegrityError(
                            "negative capability entry_id cannot be rebound to another condition"
                        )
                    if existing["status"] == "RESOLVED" and status != "RESOLVED":
                        raise StateTransitionError(
                            "resolved negative capability cannot become active again; issue a new entry_id"
                        )
                    if existing["status"] == status:
                        stored = {
                            "entry_id": existing["entry_id"],
                            "task_class": existing["task_class"],
                            "tool": existing["tool"],
                            "domain": existing["domain"],
                            "condition_code": existing["condition_code"],
                            "epoch_digest": existing["epoch_digest"],
                            "status": existing["status"],
                            "evidence_digest": existing["evidence_digest"],
                            "expires_at": existing["expires_at"],
                        }
                        if stored != normalized:
                            raise IntegrityError(
                                "same-state negative capability update would rewrite evidence or expiry"
                            )
                        conn.execute("COMMIT")
                        return digest
                    if existing["status"] != "ACTIVE" or status != "RESOLVED":
                        raise StateTransitionError("invalid negative capability state transition")
                    conn.execute(
                        "UPDATE negative_capabilities SET status='RESOLVED', evidence_digest=?, expires_at=? "
                        "WHERE entry_id=?",
                        (evidence_digest, expires_at, entry_id),
                    )
                else:
                    conn.execute(
                        """INSERT INTO negative_capabilities
                           (entry_id,task_class,tool,domain,condition_code,epoch_digest,status,evidence_digest,created_at,expires_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (
                            entry_id,
                            task_class,
                            tool,
                            domain,
                            condition_code,
                            epoch_digest,
                            status,
                            evidence_digest,
                            timestamp,
                            expires_at,
                        ),
                    )
                stored_digest = self._store_object(
                    conn, "negative-capability", normalized, timestamp
                )
                if stored_digest != digest:
                    raise IntegrityError("negative capability content address changed")
                self._append_event(
                    conn,
                    event_id=f"negative:{entry_id}:{status}",
                    case_id=None,
                    event_type="NEGATIVE_CAPABILITY_RECORDED",
                    payload={
                        "entry_digest": digest,
                        "entry_id": entry_id,
                        "status": status,
                    },
                    created_at=timestamp,
                )
                conn.execute("COMMIT")
                return digest
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def query_negative_capabilities(
        self,
        *,
        task_class: str,
        tool: str | None = None,
        domain: str | None = None,
        now: str | datetime | None = None,
    ) -> list[dict[str, Any]]:
        task_class = require_identifier(task_class, field="task_class")
        if tool is not None:
            tool = require_identifier(tool, field="tool")
        if domain is not None:
            domain = require_identifier(domain, field="domain")
        timestamp = isoformat_utc(now or utc_now())
        query = (
            "SELECT * FROM negative_capabilities "
            "WHERE task_class=? AND status='ACTIVE' "
            "AND (expires_at IS NULL OR expires_at>?)"
        )
        args: list[Any] = [task_class, timestamp]
        if tool is not None:
            query += " AND (tool IS NULL OR tool=?)"
            args.append(tool)
        if domain is not None:
            query += " AND (domain IS NULL OR domain=?)"
            args.append(domain)
        with self._connect() as conn:
            rows = conn.execute(query + " ORDER BY created_at,entry_id", args).fetchall()
        return [dict(row) for row in rows]

    def register_outcome(self, outcome_id: str, case_id: str, contract: Mapping[str, Any], *, created_at: str | datetime | None = None) -> str:
        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                digest = self._store_object(conn, "outcome-contract", contract, timestamp)
                conn.execute(
                    "INSERT INTO outcomes(outcome_id,case_id,contract_digest,settlement_digest,status,created_at,updated_at) VALUES(?,?,?,NULL,'OPEN',?,?)",
                    (outcome_id, case_id, digest, timestamp, timestamp),
                )
                self._append_event(
                    conn,
                    event_id=f"{case_id}:outcome:{outcome_id}:open",
                    case_id=case_id,
                    event_type="OUTCOME_CONTRACT_OPENED",
                    payload={"outcome_id": outcome_id, "contract_digest": digest},
                    created_at=timestamp,
                )
                conn.execute("COMMIT")
                return digest
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def settle_outcome(self, outcome_id: str, settlement: Mapping[str, Any], *, created_at: str | datetime | None = None) -> str:
        timestamp = isoformat_utc(created_at or utc_now())
        with self._lock, self._connect() as conn:
            self._begin(conn)
            try:
                row = conn.execute("SELECT * FROM outcomes WHERE outcome_id=?", (outcome_id,)).fetchone()
                if row is None:
                    raise KeyError(outcome_id)
                if row["status"] != "OPEN":
                    raise StateTransitionError("outcome is already settled")
                digest = self._store_object(conn, "outcome-settlement", settlement, timestamp)
                conn.execute("UPDATE outcomes SET settlement_digest=?,status='SETTLED',updated_at=? WHERE outcome_id=?", (digest, timestamp, outcome_id))
                self._append_event(
                    conn,
                    event_id=f"{row['case_id']}:outcome:{outcome_id}:settled",
                    case_id=row["case_id"],
                    event_type="OUTCOME_SETTLED",
                    payload={"outcome_id": outcome_id, "settlement_digest": digest},
                    created_at=timestamp,
                )
                conn.execute("COMMIT")
                return digest
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def verify_chain(self) -> dict[str, Any]:
        """Replay the event chain and cross-check all durable indexes.

        This is an offline consistency verifier for the local reference State Bus.
        It proves byte-level and relational consistency inside one SQLite database;
        it does not establish an independent transparency operator or external
        witness quorum.
        """

        errors: list[str] = []
        previous = GENESIS_HASH
        rows: list[sqlite3.Row] = []
        object_rows: list[sqlite3.Row] = []
        with self._connect() as conn:
            quick = conn.execute("PRAGMA quick_check").fetchone()[0]
            if quick != "ok":
                errors.append(f"SQLITE_QUICK_CHECK:{quick}")
            for item in conn.execute("PRAGMA foreign_key_check").fetchall():
                errors.append(
                    "FOREIGN_KEY:" + ":".join(str(value) for value in tuple(item))
                )

            metadata = {
                row["key"]: row["value"]
                for row in conn.execute("SELECT key,value FROM metadata ORDER BY key")
            }
            if metadata.get("schema") != "szl.state-bus/v1":
                errors.append("METADATA_SCHEMA_MISMATCH")
            if metadata.get("genesis_hash") != GENESIS_HASH:
                errors.append("METADATA_GENESIS_MISMATCH")

            object_rows = conn.execute(
                "SELECT digest,kind,canonical_json,created_at FROM objects ORDER BY digest"
            ).fetchall()
            objects: dict[str, tuple[str, Any]] = {}
            for row in object_rows:
                digest = row["digest"]
                try:
                    require_digest(digest, field="object_digest")
                    parse_utc(row["created_at"])
                except ValidationError as exc:
                    errors.append(f"OBJECT_METADATA_INVALID:{digest}:{type(exc).__name__}")
                if not isinstance(row["kind"], str) or not row["kind"] or len(row["kind"]) > 256:
                    errors.append(f"OBJECT_KIND_INVALID:{digest}")
                try:
                    value = json.loads(row["canonical_json"])
                except json.JSONDecodeError:
                    errors.append(f"OBJECT_JSON_INVALID:{digest}")
                    continue
                try:
                    canonical = canonical_json_text(value)
                except ValidationError:
                    errors.append(f"OBJECT_PROTOCOL_VALUE_INVALID:{digest}")
                    continue
                if canonical != row["canonical_json"]:
                    errors.append(f"OBJECT_NONCANONICAL:{digest}")
                if digest_object(value) != digest:
                    errors.append(f"OBJECT_DIGEST_MISMATCH:{digest}")
                objects[digest] = (row["kind"], value)

            rows = conn.execute("SELECT * FROM events ORDER BY seq").fetchall()
            expected_seq = 1
            case_event_payloads: dict[str, list[tuple[str, Any]]] = {}
            for row in rows:
                seq = int(row["seq"])
                if seq != expected_seq:
                    errors.append(f"NON_CONTIGUOUS_SEQ:{seq} expected={expected_seq}")
                if row["previous_hash"] != previous:
                    errors.append(f"PREVIOUS_HASH_MISMATCH:{seq}")
                try:
                    require_identifier(row["event_id"], field="event_id")
                    require_identifier(row["event_type"], field="event_type")
                    require_digest(row["payload_digest"], field="payload_digest")
                    require_digest(row["previous_hash"], field="previous_hash")
                    require_digest(row["event_hash"], field="event_hash")
                    parse_utc(row["created_at"])
                except ValidationError as exc:
                    errors.append(f"EVENT_METADATA_INVALID:{seq}:{type(exc).__name__}")
                payload_entry = objects.get(row["payload_digest"])
                if payload_entry is None:
                    errors.append(f"MISSING_PAYLOAD:{seq}")
                    payload = None
                else:
                    kind, payload = payload_entry
                    expected_kind = f"event:{row['event_type']}"
                    if kind != expected_kind:
                        errors.append(
                            f"EVENT_PAYLOAD_KIND_MISMATCH:{seq}:{kind} expected={expected_kind}"
                        )
                body = {
                    "schema": "szl.state-event/v1",
                    "seq": seq,
                    "event_id": row["event_id"],
                    "case_id": row["case_id"],
                    "event_type": row["event_type"],
                    "payload_digest": row["payload_digest"],
                    "previous_hash": row["previous_hash"],
                    "created_at": row["created_at"],
                }
                if digest_object(body) != row["event_hash"]:
                    errors.append(f"EVENT_HASH_MISMATCH:{seq}")
                previous = row["event_hash"]
                expected_seq += 1
                if row["case_id"] is not None and payload is not None:
                    case_event_payloads.setdefault(row["case_id"], []).append(
                        (row["event_type"], payload)
                    )

            case_rows = conn.execute("SELECT * FROM cases ORDER BY case_id").fetchall()
            cases_by_id = {row["case_id"]: row for row in case_rows}
            for row in case_rows:
                case_id = row["case_id"]
                try:
                    require_identifier(case_id, field="case_id")
                    state = WorkflowState(row["state"])
                    parse_utc(row["created_at"])
                    parse_utc(row["updated_at"])
                except (ValidationError, ValueError) as exc:
                    errors.append(f"CASE_METADATA_INVALID:{case_id}:{type(exc).__name__}")
                    continue
                for field_name, expected_kind in (
                    ("case_digest", "council-case"),
                    ("envelope_digest", "autonomy-envelope"),
                ):
                    entry = objects.get(row[field_name])
                    if entry is None:
                        errors.append(f"CASE_OBJECT_MISSING:{case_id}:{field_name}")
                        continue
                    kind, value = entry
                    if kind != expected_kind:
                        errors.append(
                            f"CASE_OBJECT_KIND_MISMATCH:{case_id}:{field_name}:{kind}"
                        )
                    if isinstance(value, Mapping):
                        bound_case_id = value.get("case_id")
                        if bound_case_id is not None and bound_case_id != case_id:
                            errors.append(
                                f"CASE_OBJECT_BINDING_MISMATCH:{case_id}:{field_name}"
                            )
                reconstructed = WorkflowState.CREATED
                events_for_case = case_event_payloads.get(case_id, [])
                if not events_for_case or events_for_case[0][0] != "CASE_CREATED":
                    errors.append(f"CASE_CREATED_EVENT_MISSING:{case_id}")
                for event_type, payload in events_for_case:
                    if event_type != "CASE_TRANSITION":
                        continue
                    if not isinstance(payload, Mapping):
                        errors.append(f"CASE_TRANSITION_PAYLOAD_INVALID:{case_id}")
                        continue
                    try:
                        source = WorkflowState(str(payload.get("from")))
                        target = WorkflowState(str(payload.get("to")))
                    except ValueError:
                        errors.append(f"CASE_TRANSITION_STATE_INVALID:{case_id}")
                        continue
                    if source != reconstructed:
                        errors.append(
                            f"CASE_TRANSITION_SOURCE_MISMATCH:{case_id}:{source.value} expected={reconstructed.value}"
                        )
                    if target not in _ALLOWED_TRANSITIONS.get(source, set()):
                        errors.append(
                            f"CASE_TRANSITION_ILLEGAL:{case_id}:{source.value}->{target.value}"
                        )
                    reconstructed = target
                if reconstructed != state:
                    errors.append(
                        f"CASE_STATE_MISMATCH:{case_id}:{state.value} expected={reconstructed.value}"
                    )

            receipt_rows = conn.execute(
                "SELECT rowid,* FROM receipts ORDER BY case_id,created_at,rowid"
            ).fetchall()
            receipts_by_digest = {row["receipt_digest"]: row for row in receipt_rows}
            prior_by_case: dict[str, str | None] = {}
            terminal_by_status = {
                "VERIFIED": WorkflowState.SETTLED.value,
                "ROLLED_BACK": WorkflowState.ROLLED_BACK.value,
                "BLOCKED": WorkflowState.BLOCKED.value,
                "FAILED": WorkflowState.FAILED.value,
            }
            for row in receipt_rows:
                digest = row["receipt_digest"]
                entry = objects.get(digest)
                if entry is None:
                    errors.append(f"RECEIPT_OBJECT_MISSING:{digest}")
                    continue
                kind, receipt = entry
                if kind != "action-receipt":
                    errors.append(f"RECEIPT_OBJECT_KIND_MISMATCH:{digest}:{kind}")
                if not isinstance(receipt, Mapping):
                    errors.append(f"RECEIPT_PAYLOAD_INVALID:{digest}")
                    continue
                if receipt.get("case_id") != row["case_id"]:
                    errors.append(f"RECEIPT_CASE_BINDING_MISMATCH:{digest}")
                if receipt.get("action_id") != row["action_id"]:
                    errors.append(f"RECEIPT_ACTION_BINDING_MISMATCH:{digest}")
                expected_prior = prior_by_case.get(row["case_id"])
                if receipt.get("previous_receipt_digest") != expected_prior:
                    errors.append(f"RECEIPT_CHAIN_MISMATCH:{digest}")
                prior_by_case[row["case_id"]] = digest
                signed_digest = row["signed_envelope_digest"]
                if signed_digest is not None:
                    signed_entry = objects.get(signed_digest)
                    if signed_entry is None:
                        errors.append(f"SIGNED_RECEIPT_OBJECT_MISSING:{digest}")
                    else:
                        signed_kind, signed = signed_entry
                        if signed_kind != "signed-action-receipt":
                            errors.append(
                                f"SIGNED_RECEIPT_KIND_MISMATCH:{digest}:{signed_kind}"
                            )
                        if isinstance(signed, Mapping):
                            envelope = signed.get("envelope")
                            if not isinstance(envelope, Mapping) or digest_object(envelope) != signed.get("envelope_digest"):
                                errors.append(f"SIGNED_RECEIPT_ENVELOPE_INVALID:{digest}")
                            else:
                                try:
                                    payload = json.loads(
                                        b64url_decode(str(envelope.get("payload", ""))).decode("utf-8")
                                    )
                                except (ValidationError, UnicodeDecodeError, json.JSONDecodeError):
                                    errors.append(f"SIGNED_RECEIPT_PAYLOAD_INVALID:{digest}")
                                else:
                                    if canonical_json_text(payload) != canonical_json_text(receipt):
                                        errors.append(f"SIGNED_RECEIPT_PAYLOAD_MISMATCH:{digest}")
                case_row = cases_by_id.get(row["case_id"])
                if case_row is None:
                    errors.append(f"RECEIPT_CASE_MISSING:{digest}")
                else:
                    expected_terminal = terminal_by_status.get(str(receipt.get("status")))
                    if expected_terminal and case_row["state"] != expected_terminal:
                        errors.append(
                            f"RECEIPT_TERMINAL_STATE_MISMATCH:{digest}:{case_row['state']} expected={expected_terminal}"
                        )

            idempotency_rows = conn.execute(
                "SELECT * FROM idempotency ORDER BY idempotency_key"
            ).fetchall()
            for row in idempotency_rows:
                try:
                    require_identifier(row["idempotency_key"], field="idempotency_key")
                    require_digest(row["action_digest"], field="action_digest")
                    parse_utc(row["created_at"])
                    parse_utc(row["updated_at"])
                except ValidationError as exc:
                    errors.append(
                        f"IDEMPOTENCY_METADATA_INVALID:{row['idempotency_key']}:{type(exc).__name__}"
                    )
                state = row["state"]
                if state not in {"IN_FLIGHT", "SETTLED", "FAILED"}:
                    errors.append(f"IDEMPOTENCY_STATE_INVALID:{row['idempotency_key']}:{state}")
                if state == "SETTLED":
                    receipt_digest = row["receipt_digest"]
                    if receipt_digest is None:
                        errors.append(f"IDEMPOTENCY_RECEIPT_MISSING:{row['idempotency_key']}")
                    elif receipt_digest not in objects:
                        errors.append(
                            f"IDEMPOTENCY_RECEIPT_OBJECT_MISSING:{row['idempotency_key']}"
                        )
                    elif receipt_digest not in receipts_by_digest:
                        errors.append(
                            f"IDEMPOTENCY_RECEIPT_INDEX_MISSING:{row['idempotency_key']}"
                        )
                elif row["receipt_digest"] is not None:
                    errors.append(
                        f"IDEMPOTENCY_NONTERMINAL_HAS_RECEIPT:{row['idempotency_key']}"
                    )

            negative_rows = conn.execute(
                "SELECT * FROM negative_capabilities ORDER BY entry_id"
            ).fetchall()
            for row in negative_rows:
                try:
                    require_identifier(row["entry_id"], field="entry_id")
                    require_identifier(row["task_class"], field="task_class")
                    require_identifier(row["condition_code"], field="condition_code")
                    require_digest(row["epoch_digest"], field="epoch_digest")
                    parse_utc(row["created_at"])
                    if row["evidence_digest"] is not None:
                        require_digest(row["evidence_digest"], field="evidence_digest")
                    if row["expires_at"] is not None:
                        parse_utc(row["expires_at"])
                except ValidationError as exc:
                    errors.append(
                        f"NEGATIVE_CAPABILITY_INVALID:{row['entry_id']}:{type(exc).__name__}"
                    )
                if row["status"] not in {"ACTIVE", "RESOLVED"}:
                    errors.append(
                        f"NEGATIVE_CAPABILITY_STATUS_INVALID:{row['entry_id']}:{row['status']}"
                    )

            outcome_rows = conn.execute("SELECT * FROM outcomes ORDER BY outcome_id").fetchall()
            for row in outcome_rows:
                if row["contract_digest"] not in objects:
                    errors.append(f"OUTCOME_CONTRACT_MISSING:{row['outcome_id']}")
                if row["status"] == "OPEN" and row["settlement_digest"] is not None:
                    errors.append(f"OUTCOME_OPEN_HAS_SETTLEMENT:{row['outcome_id']}")
                elif row["status"] == "SETTLED":
                    if row["settlement_digest"] not in objects:
                        errors.append(f"OUTCOME_SETTLEMENT_MISSING:{row['outcome_id']}")
                else:
                    if row["status"] not in {"OPEN", "SETTLED"}:
                        errors.append(f"OUTCOME_STATUS_INVALID:{row['outcome_id']}")

        transparency = self.verify_transparency()
        if transparency["status"] != "PASS":
            errors.extend(f"TRANSPARENCY:{item}" for item in transparency["errors"])
        return {
            "schema": "szl.state-bus-verification/v2",
            "status": "PASS" if not errors else "FAIL",
            "event_count": len(rows),
            "object_count": len(object_rows),
            "case_count": len(case_rows),
            "receipt_count": len(receipt_rows),
            "idempotency_count": len(idempotency_rows),
            "head_hash": previous,
            "genesis_hash": GENESIS_HASH,
            "transparency": transparency,
            "errors": errors,
            "assurance_scope": "LOCAL_SQLITE_AND_MERKLE_CONSISTENCY_ONLY",
        }

    def export_evidence(self) -> dict[str, Any]:
        with self._connect() as conn:
            metadata = {row["key"]: row["value"] for row in conn.execute("SELECT * FROM metadata ORDER BY key")}
            cases = [dict(row) for row in conn.execute("SELECT * FROM cases ORDER BY case_id")]
            events = [dict(row) for row in conn.execute("SELECT * FROM events ORDER BY seq")]
            receipts = [dict(row) for row in conn.execute("SELECT * FROM receipts ORDER BY created_at")]
            transparency = [dict(row) for row in conn.execute("SELECT * FROM transparency ORDER BY seq")]
            negative = [dict(row) for row in conn.execute("SELECT * FROM negative_capabilities ORDER BY entry_id")]
            outcomes = [dict(row) for row in conn.execute("SELECT * FROM outcomes ORDER BY outcome_id")]
            objects = [dict(row) for row in conn.execute("SELECT digest,kind,canonical_json,created_at FROM objects ORDER BY digest")]
        bundle = {
            "schema": "szl.state-bus-evidence-export/v1",
            "metadata": metadata,
            "cases": cases,
            "events": events,
            "receipts": receipts,
            "transparency": transparency,
            "negative_capabilities": negative,
            "outcomes": outcomes,
            "objects": objects,
            "verification": self.verify_chain(),
        }
        return {**bundle, "bundle_digest": digest_object(bundle)}
