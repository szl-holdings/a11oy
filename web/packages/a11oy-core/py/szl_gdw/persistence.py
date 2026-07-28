#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

"""Durable, replay-safe storage for the Governed Delta Workspace."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import os
import re
import sqlite3
from threading import RLock
from typing import Any, Mapping
from uuid import uuid4

from .models import Decision, DepthSummary, KernelReceipt, WorkspaceState


SCHEMA_VERSION = 1
APPLICATION_ID = 0x47574457
MAX_JSON_BYTES = 1_048_576
MAX_ID_LENGTH = 128
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class PersistenceError(RuntimeError):
    """Base class for storage failures safe to map at the API boundary."""


class SchemaVersionError(PersistenceError):
    """The database schema is absent, incompatible, or inconsistent."""


class IntegrityViolation(PersistenceError):
    """Persisted or proposed data failed an integrity check."""


class SessionNotFound(PersistenceError):
    """The requested workspace session does not exist."""


class SessionConflict(PersistenceError):
    """A session identifier or optimistic state version conflicts."""


class SessionQuotaExceeded(PersistenceError):
    """The durable global session ceiling has been reached."""


class ReplayConflict(PersistenceError):
    """An idempotency key was reused for a different request."""


@dataclass(frozen=True)
class CommitResult:
    response: Mapping[str, Any]
    replayed: bool
    receipt_id: str
    state_hash: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _canonical_json(value: Any, max_bytes: int = MAX_JSON_BYTES) -> str:
    try:
        encoded = json.dumps(
            _jsonable(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise IntegrityViolation("value is not finite canonical JSON") from exc
    if len(encoded.encode("utf-8")) > max_bytes:
        raise IntegrityViolation("canonical JSON exceeds the configured size limit")
    return encoded


def _digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not _ID_PATTERN.fullmatch(value):
        raise IntegrityViolation(f"{name} has an invalid format")
    return value


def _validate_hash(value: str, name: str) -> str:
    if not isinstance(value, str) or not _HEX_64.fullmatch(value):
        raise IntegrityViolation(f"{name} must be a lowercase SHA-256 digest")
    return value


def state_to_dict(state: WorkspaceState) -> dict[str, Any]:
    if not isinstance(state, WorkspaceState):
        raise IntegrityViolation("state must be a WorkspaceState")
    payload = _jsonable(state.to_dict() if hasattr(state, "to_dict") else state)
    _canonical_json(payload)
    return payload


def state_from_dict(payload: Mapping[str, Any]) -> WorkspaceState:
    if not isinstance(payload, Mapping):
        raise IntegrityViolation("stored state is not an object")
    try:
        depth_summaries = [
            DepthSummary(
                summary_id=str(item["summary_id"]),
                depth=int(item["depth"]),
                vector=tuple(float(value) for value in item["vector"]),
                trust=float(item["trust"]),
                risk=float(item["risk"]),
                provenance=tuple(str(value) for value in item["provenance"]),
            )
            for item in payload.get("depth_summaries", [])
        ]
        state = WorkspaceState(
            session_id=str(payload["session_id"]),
            step=int(payload["step"]),
            yuyay=tuple(payload.get("yuyay", [])),
            unay_refs=tuple(str(value) for value in payload.get("unay_refs", [])),
            broadcast=tuple(payload.get("broadcast", [])),
            delta_memory=tuple(
                float(value) for value in payload.get("delta_memory", [])
            ),
            depth_summaries=tuple(depth_summaries),
            risk_budget=float(payload.get("risk_budget", 1.0)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise IntegrityViolation("stored state does not match the v1 schema") from exc
    _validate_identifier(state.session_id, "session_id")
    if state.step < 0:
        raise IntegrityViolation("stored state step is negative")
    state_to_dict(state)
    return state


def receipt_to_dict(receipt: KernelReceipt | Mapping[str, Any]) -> dict[str, Any]:
    payload = _jsonable(receipt)
    if not isinstance(payload, dict):
        raise IntegrityViolation("receipt must be an object")
    _canonical_json(payload)
    return payload


def receipt_from_dict(payload: Mapping[str, Any]) -> KernelReceipt:
    try:
        return KernelReceipt(
            receipt_id=str(payload["receipt_id"]),
            proposal_id=str(payload["proposal_id"]),
            decision=Decision(str(payload["decision"])),
            policy_results={
                str(key): bool(value)
                for key, value in dict(payload["policy_results"]).items()
            },
            invariant_results={
                str(key): bool(value)
                for key, value in dict(payload["invariant_results"]).items()
            },
            state_before=str(payload["state_before"]),
            state_after=(
                str(payload["state_after"])
                if payload.get("state_after") is not None
                else None
            ),
            reason=str(payload["reason"]),
            created_at=str(payload["created_at"]),
            receipt_hash=str(payload["receipt_hash"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise IntegrityViolation("stored kernel receipt is invalid") from exc


def verify_kernel_receipt(receipt: KernelReceipt | Mapping[str, Any]) -> dict[str, Any]:
    payload = receipt_to_dict(receipt)
    required = {
        "receipt_id",
        "proposal_id",
        "decision",
        "policy_results",
        "invariant_results",
        "state_before",
        "state_after",
        "reason",
        "created_at",
        "receipt_hash",
    }
    if set(payload) != required:
        raise IntegrityViolation("kernel receipt fields do not match the v1 contract")
    _validate_identifier(str(payload["receipt_id"]), "receipt_id")
    _validate_identifier(str(payload["proposal_id"]), "proposal_id")
    _validate_hash(str(payload["state_before"]), "receipt.state_before")
    if payload["state_after"] is not None:
        _validate_hash(str(payload["state_after"]), "receipt.state_after")
    _validate_hash(str(payload["receipt_hash"]), "receipt.receipt_hash")
    if str(payload["decision"]) not in {item.value for item in Decision}:
        raise IntegrityViolation("kernel receipt decision is invalid")
    for result_name in ("policy_results", "invariant_results"):
        results = payload[result_name]
        if (
            not isinstance(results, Mapping)
            or not results
            or not all(
                isinstance(key, str) and isinstance(value, bool)
                for key, value in results.items()
            )
        ):
            raise IntegrityViolation(
                f"kernel receipt {result_name} must contain boolean results"
            )
    body = {
        "proposal_id": payload["proposal_id"],
        "decision": payload["decision"],
        "policy_results": payload["policy_results"],
        "invariant_results": payload["invariant_results"],
        "state_before": payload["state_before"],
        "state_after": payload["state_after"],
        "reason": payload["reason"],
    }
    if _digest(body) != payload["receipt_hash"]:
        raise IntegrityViolation("kernel receipt hash does not verify")
    return payload


def _sign_khipu(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        from szl_dsse import sign_khipu_receipt
    except (ImportError, OSError) as exc:
        raise PersistenceError("canonical Khipu signer is unavailable") from exc
    try:
        signed = sign_khipu_receipt(dict(payload))
    except Exception as exc:
        raise PersistenceError("canonical Khipu signer failed closed") from exc
    if not isinstance(signed, Mapping):
        raise IntegrityViolation("canonical Khipu signer returned an invalid result")
    receipt = signed.get("receipt")
    envelope = signed.get("dsse")
    if not isinstance(receipt, dict) or not isinstance(envelope, dict):
        raise IntegrityViolation("canonical Khipu signer omitted receipt or DSSE")
    _verify_dsse_binding(receipt, envelope)
    return receipt, envelope


def _verify_dsse_binding(
    receipt: Mapping[str, Any], envelope: Mapping[str, Any]
) -> None:
    try:
        payload = base64.b64decode(
            str(envelope["payload"]).encode("ascii"), validate=True
        )
        decoded = json.loads(payload)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IntegrityViolation("DSSE envelope payload is invalid") from exc
    if decoded != dict(receipt):
        raise IntegrityViolation("DSSE envelope does not bind the stored receipt")
    if envelope.get("payloadType") != "application/vnd.szl.khipu+json":
        raise IntegrityViolation("DSSE envelope payload type is invalid")
    signed = envelope.get("signed")
    signatures = envelope.get("signatures")
    if signed is True:
        if not isinstance(signatures, list) or not signatures:
            raise IntegrityViolation("signed DSSE envelope has no signature")
        try:
            from szl_dsse import verify_envelope
        except (ImportError, OSError) as exc:
            raise IntegrityViolation(
                "signed DSSE envelope cannot be verified"
            ) from exc
        verdict = verify_envelope(dict(envelope))
        if not verdict.get("verified"):
            raise IntegrityViolation("signed DSSE envelope did not verify")
    elif signed is False:
        if signatures != [] or "UNSIGNED" not in str(envelope.get("honesty", "")):
            raise IntegrityViolation("unsigned DSSE envelope is not honestly labeled")
    else:
        raise IntegrityViolation("DSSE envelope signed status is invalid")


class SQLiteWorkspaceStore:
    """SQLite repository with atomic state, receipt, and replay records."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_json_bytes: int = MAX_JSON_BYTES,
        timeout_seconds: float = 30.0,
        persistent_required: bool = False,
        required_mount: str | Path | None = None,
        journal_mode: str = "WAL",
        max_sessions: int = 1000,
    ) -> None:
        path_text = str(path)
        if (
            not path_text
            or "\x00" in path_text
            or len(path_text) > 4096
            or path_text == ":memory:"
        ):
            raise PersistenceError("database path must name a bounded filesystem file")
        if not (1_024 <= max_json_bytes <= 16_777_216):
            raise ValueError("max_json_bytes must be between 1 KiB and 16 MiB")
        if not (0.1 <= timeout_seconds <= 120.0):
            raise ValueError("timeout_seconds must be between 0.1 and 120")
        selected_journal_mode = str(journal_mode).strip().upper()
        if selected_journal_mode not in {"DELETE", "WAL"}:
            raise ValueError("journal_mode must be DELETE or WAL")
        if not isinstance(max_sessions, int) or not (1 <= max_sessions <= 1_000_000):
            raise ValueError("max_sessions must be between 1 and 1000000")

        self.path = str(Path(path_text).expanduser().resolve())
        self.max_json_bytes = max_json_bytes
        self.timeout_seconds = timeout_seconds
        self.persistent_required = bool(persistent_required)
        self.journal_mode = selected_journal_mode
        self.max_sessions = max_sessions
        self.required_mount = (
            str(Path(required_mount).expanduser().resolve())
            if required_mount is not None
            else None
        )
        self._lock = RLock()
        if self.persistent_required and self.required_mount is None:
            raise PersistenceError(
                "persistent storage requires an explicit required mount"
            )
        if self.required_mount is not None:
            mount = Path(self.required_mount)
            database = Path(self.path)
            try:
                database.relative_to(mount)
            except ValueError as exc:
                raise PersistenceError(
                    "database path is outside the required storage mount"
                ) from exc
            if self.persistent_required and not os.path.ismount(str(mount)):
                raise PersistenceError("required persistent storage mount is not attached")
        try:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PersistenceError("database parent directory is not writable") from exc
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                self.path,
                timeout=self.timeout_seconds,
                isolation_level=None,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA synchronous=FULL")
            return connection
        except sqlite3.Error as exc:
            raise PersistenceError("unable to open the workspace database") from exc

    def _initialize(self) -> None:
        with self._lock:
            db = self._connect()
            try:
                observed = int(db.execute("PRAGMA user_version").fetchone()[0])
                application_id = int(
                    db.execute("PRAGMA application_id").fetchone()[0]
                )
                if observed not in (0, SCHEMA_VERSION):
                    raise SchemaVersionError(
                        f"unsupported database schema version {observed}"
                    )
                if observed == 0 and application_id not in (0, APPLICATION_ID):
                    raise SchemaVersionError("database belongs to another application")
                if observed == SCHEMA_VERSION and application_id != APPLICATION_ID:
                    raise SchemaVersionError("database application id is invalid")
                if observed == 0:
                    existing = {
                        str(row["name"])
                        for row in db.execute(
                            """
                            SELECT name FROM sqlite_master
                            WHERE type='table' AND name NOT LIKE 'sqlite_%'
                            """
                        ).fetchall()
                    }
                    if existing:
                        raise SchemaVersionError(
                            "unversioned database contains unknown tables"
                        )
                    db.execute("BEGIN IMMEDIATE")
                    try:
                        self._create_schema(db)
                        db.execute(f"PRAGMA application_id={APPLICATION_ID}")
                        db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                        db.commit()
                    except Exception:
                        db.rollback()
                        raise
                journal_mode = str(
                    db.execute(
                        f"PRAGMA journal_mode={self.journal_mode}"
                    ).fetchone()[0]
                ).upper()
                if journal_mode != self.journal_mode:
                    raise SchemaVersionError(
                        "database could not enable the configured journal mode"
                    )
                self._verify_schema(db)
            except sqlite3.Error as exc:
                raise PersistenceError("database initialization failed") from exc
            finally:
                db.close()

    def _create_schema(self, db: sqlite3.Connection) -> None:
        statements = (
            """
            CREATE TABLE metadata(
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE sessions(
              session_id TEXT PRIMARY KEY,
              state_json TEXT NOT NULL,
              state_hash TEXT NOT NULL,
              revision INTEGER NOT NULL CHECK(revision >= 0),
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE receipts(
              receipt_id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL REFERENCES sessions(session_id),
              receipt_type TEXT NOT NULL CHECK(
                receipt_type IN ('session.create', 'kernel.transition')
              ),
              proposal_id TEXT,
              decision TEXT,
              receipt_json TEXT NOT NULL,
              dsse_json TEXT NOT NULL,
              receipt_hash TEXT NOT NULL UNIQUE,
              previous_receipt_hash TEXT NOT NULL,
              signed INTEGER NOT NULL CHECK(signed IN (0,1)),
              created_at TEXT NOT NULL,
              UNIQUE(session_id, proposal_id)
            )
            """,
            """
            CREATE TABLE operations(
              session_id TEXT NOT NULL REFERENCES sessions(session_id),
              idempotency_key TEXT NOT NULL,
              request_hash TEXT NOT NULL,
              response_json TEXT NOT NULL,
              state_hash_after TEXT NOT NULL,
              receipt_id TEXT NOT NULL REFERENCES receipts(receipt_id),
              created_at TEXT NOT NULL,
              PRIMARY KEY(session_id, idempotency_key)
            )
            """,
            """
            CREATE INDEX receipts_session_created
            ON receipts(session_id, created_at)
            """,
        )
        for statement in statements:
            db.execute(statement)
        now = _utc_now()
        db.executemany(
            "INSERT INTO metadata(key,value) VALUES(?,?)",
            (
                ("schema_name", "szl.gdw.sqlite"),
                ("schema_version", str(SCHEMA_VERSION)),
                ("created_at", now),
                ("storage_instance_id", f"gdw_{uuid4().hex}"),
            ),
        )

    def _verify_schema(self, db: sqlite3.Connection) -> None:
        metadata = {
            str(row["key"]): str(row["value"])
            for row in db.execute("SELECT key,value FROM metadata").fetchall()
        }
        if metadata.get("schema_name") != "szl.gdw.sqlite":
            raise SchemaVersionError("database schema name is invalid")
        if metadata.get("schema_version") != str(SCHEMA_VERSION):
            raise SchemaVersionError("database schema metadata is inconsistent")
        required = {"metadata", "sessions", "receipts", "operations"}
        observed = {
            str(row["name"])
            for row in db.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()
        }
        if not required.issubset(observed):
            raise SchemaVersionError("database is missing required v1 tables")
        expected_columns = {
            "metadata": {"key", "value"},
            "sessions": {
                "session_id",
                "state_json",
                "state_hash",
                "revision",
                "created_at",
                "updated_at",
            },
            "receipts": {
                "receipt_id",
                "session_id",
                "receipt_type",
                "proposal_id",
                "decision",
                "receipt_json",
                "dsse_json",
                "receipt_hash",
                "previous_receipt_hash",
                "signed",
                "created_at",
            },
            "operations": {
                "session_id",
                "idempotency_key",
                "request_hash",
                "response_json",
                "state_hash_after",
                "receipt_id",
                "created_at",
            },
        }
        for table, columns in expected_columns.items():
            actual = {
                str(row["name"])
                for row in db.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if actual != columns:
                raise SchemaVersionError(
                    f"database table {table} does not match the v1 schema"
                )

    def create_session(self, state: WorkspaceState) -> Mapping[str, Any]:
        session_id = _validate_identifier(state.session_id, "session_id")
        state_payload = state_to_dict(state)
        state_json = _canonical_json(state_payload, self.max_json_bytes)
        state_hash = _validate_hash(state.canonical_hash(), "state_hash")
        now = _utc_now()
        receipt_id = f"create-{uuid4().hex}"
        receipt_body = {
            "schema": "szl.gdw.khipu/v1",
            "receipt_id": receipt_id,
            "receipt_type": "session.create",
            "session_id": session_id,
            "idempotency_key": session_id,
            "request_digest": _digest(
                {"session_id": session_id, "state": state_payload}
            ),
            "state_before": None,
            "state_after": state_hash,
            "previous_receipt_hash": "0" * 64,
            "kernel_receipt": None,
            "created_at": now,
        }

        with self._lock:
            db = self._connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                if db.execute(
                    "SELECT 1 FROM sessions WHERE session_id=?", (session_id,)
                ).fetchone() is not None:
                    raise SessionConflict("session already exists")
                session_count = int(
                    db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
                )
                if session_count >= self.max_sessions:
                    raise SessionQuotaExceeded(
                        "durable session capacity is exhausted"
                    )
                receipt, envelope = _sign_khipu(receipt_body)
                receipt_hash = _digest(receipt)
                receipt_json = _canonical_json(receipt, self.max_json_bytes)
                dsse_json = _canonical_json(envelope, self.max_json_bytes)
                db.execute(
                    """
                    INSERT INTO sessions(
                      session_id,state_json,state_hash,revision,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    (session_id, state_json, state_hash, 0, now, now),
                )
                db.execute(
                    """
                    INSERT INTO receipts(
                      receipt_id,session_id,receipt_type,proposal_id,decision,
                      receipt_json,dsse_json,receipt_hash,previous_receipt_hash,
                      signed,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        receipt_id,
                        session_id,
                        "session.create",
                        None,
                        None,
                        receipt_json,
                        dsse_json,
                        receipt_hash,
                        "0" * 64,
                        int(envelope["signed"]),
                        now,
                    ),
                )
                db.commit()
            except (SessionConflict, SessionQuotaExceeded):
                db.rollback()
                raise
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise SessionConflict("session already exists") from exc
            except sqlite3.Error as exc:
                db.rollback()
                raise PersistenceError("session creation transaction failed") from exc
            finally:
                db.close()
        return {
            "session_id": session_id,
            "state_hash": state_hash,
            "revision": 0,
            "created_at": now,
            "receipt": {
                "receipt": receipt,
                "dsse": envelope,
                "receipt_hash": receipt_hash,
            },
        }

    def load_session(self, session_id: str) -> WorkspaceState:
        return self.get_session(session_id)["state"]

    def get_session(self, session_id: str) -> dict[str, Any]:
        session_id = _validate_identifier(session_id, "session_id")
        db = self._connect()
        try:
            row = db.execute(
                """
                SELECT state_json,state_hash,revision,created_at,updated_at
                FROM sessions WHERE session_id=?
                """,
                (session_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceError("session read failed") from exc
        finally:
            db.close()
        if row is None:
            raise SessionNotFound("session does not exist")
        try:
            payload = json.loads(str(row["state_json"]))
        except (TypeError, json.JSONDecodeError) as exc:
            raise IntegrityViolation("stored state JSON is invalid") from exc
        state = state_from_dict(payload)
        observed_hash = _validate_hash(state.canonical_hash(), "state_hash")
        if observed_hash != str(row["state_hash"]):
            raise IntegrityViolation("stored state hash does not verify")
        return {
            "state": state,
            "state_hash": observed_hash,
            "revision": int(row["revision"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def lookup_operation(
        self,
        session_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> CommitResult | None:
        session_id = _validate_identifier(session_id, "session_id")
        idempotency_key = _validate_identifier(
            idempotency_key, "idempotency_key"
        )
        request_hash = _validate_hash(request_hash, "request_hash")
        db = self._connect()
        try:
            row = db.execute(
                """
                SELECT request_hash,response_json,state_hash_after,receipt_id
                FROM operations
                WHERE session_id=? AND idempotency_key=?
                """,
                (session_id, idempotency_key),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceError("operation lookup failed") from exc
        finally:
            db.close()
        if row is None:
            return None
        if str(row["request_hash"]) != request_hash:
            raise ReplayConflict("idempotency key is bound to another request")
        try:
            response = json.loads(str(row["response_json"]))
        except (TypeError, json.JSONDecodeError) as exc:
            raise IntegrityViolation("stored operation response is invalid") from exc
        return CommitResult(
            response=response,
            replayed=True,
            receipt_id=str(row["receipt_id"]),
            state_hash=str(row["state_hash_after"]),
        )

    def commit_transition(
        self,
        *,
        session_id: str,
        idempotency_key: str,
        request_hash: str,
        expected_state_hash: str,
        next_state: WorkspaceState,
        receipt: KernelReceipt | Mapping[str, Any],
        response: Mapping[str, Any],
    ) -> CommitResult:
        session_id = _validate_identifier(session_id, "session_id")
        idempotency_key = _validate_identifier(
            idempotency_key, "idempotency_key"
        )
        request_hash = _validate_hash(request_hash, "request_hash")
        expected_state_hash = _validate_hash(
            expected_state_hash, "expected_state_hash"
        )
        if next_state.session_id != session_id:
            raise IntegrityViolation("next state belongs to another session")

        next_state_json = _canonical_json(
            state_to_dict(next_state), self.max_json_bytes
        )
        next_state_hash = _validate_hash(
            next_state.canonical_hash(), "next_state_hash"
        )
        receipt_payload = verify_kernel_receipt(receipt)
        if receipt_payload["state_before"] != expected_state_hash:
            raise IntegrityViolation(
                "kernel receipt is not bound to the persisted parent state"
            )
        decision = str(receipt_payload["decision"])
        if decision == Decision.ACCEPT.value:
            if receipt_payload["state_after"] != next_state_hash:
                raise IntegrityViolation(
                    "accepted receipt state_after does not match next state"
                )
        else:
            if receipt_payload["state_after"] is not None:
                raise IntegrityViolation(
                    "non-accepted receipt must not claim a next-state hash"
                )
            if next_state_hash != expected_state_hash:
                raise IntegrityViolation(
                    "non-accepted transition attempted to change state"
                )

        receipt_id = str(receipt_payload["receipt_id"])
        now = _utc_now()
        committed_response: Mapping[str, Any]

        with self._lock:
            db = self._connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                prior = db.execute(
                    """
                    SELECT request_hash,response_json,state_hash_after,receipt_id
                    FROM operations
                    WHERE session_id=? AND idempotency_key=?
                    """,
                    (session_id, idempotency_key),
                ).fetchone()
                if prior is not None:
                    if str(prior["request_hash"]) != request_hash:
                        raise ReplayConflict(
                            "idempotency key is bound to another request"
                        )
                    try:
                        prior_response = json.loads(str(prior["response_json"]))
                    except (TypeError, json.JSONDecodeError) as exc:
                        raise IntegrityViolation(
                            "stored operation response is invalid"
                        ) from exc
                    db.rollback()
                    return CommitResult(
                        response=prior_response,
                        replayed=True,
                        receipt_id=str(prior["receipt_id"]),
                        state_hash=str(prior["state_hash_after"]),
                    )

                current = db.execute(
                    "SELECT state_hash FROM sessions WHERE session_id=?",
                    (session_id,),
                ).fetchone()
                if current is None:
                    raise SessionNotFound("session does not exist")
                if str(current["state_hash"]) != expected_state_hash:
                    raise SessionConflict("session changed during the governed step")

                head = db.execute(
                    """
                    SELECT receipt_hash FROM receipts
                    WHERE session_id=? ORDER BY rowid DESC LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()
                previous_receipt_hash = (
                    str(head["receipt_hash"]) if head is not None else "0" * 64
                )
                khipu_body = {
                    "schema": "szl.gdw.khipu/v1",
                    "receipt_id": receipt_id,
                    "receipt_type": "kernel.transition",
                    "session_id": session_id,
                    "idempotency_key": idempotency_key,
                    "request_digest": request_hash,
                    "state_before": expected_state_hash,
                    "state_after": next_state_hash,
                    "previous_receipt_hash": previous_receipt_hash,
                    "kernel_receipt": receipt_payload,
                    "created_at": now,
                }
                khipu_receipt, envelope = _sign_khipu(khipu_body)
                receipt_hash = _digest(khipu_receipt)
                receipt_json = _canonical_json(
                    khipu_receipt, self.max_json_bytes
                )
                dsse_json = _canonical_json(envelope, self.max_json_bytes)
                committed_response = {
                    **dict(response),
                    "khipu_receipt": {
                        "receipt_id": receipt_id,
                        "receipt_hash": receipt_hash,
                        "signed": bool(envelope["signed"]),
                    },
                }
                response_json = _canonical_json(
                    committed_response, self.max_json_bytes
                )
                committed_response = json.loads(response_json)
                db.execute(
                    """
                    INSERT INTO receipts(
                      receipt_id,session_id,receipt_type,proposal_id,decision,
                      receipt_json,dsse_json,receipt_hash,previous_receipt_hash,
                      signed,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        receipt_id,
                        session_id,
                        "kernel.transition",
                        receipt_payload["proposal_id"],
                        decision,
                        receipt_json,
                        dsse_json,
                        receipt_hash,
                        previous_receipt_hash,
                        int(envelope["signed"]),
                        now,
                    ),
                )
                db.execute(
                    """
                    UPDATE sessions
                    SET state_json=?,state_hash=?,revision=revision+1,updated_at=?
                    WHERE session_id=? AND state_hash=?
                    """,
                    (
                        next_state_json,
                        next_state_hash,
                        now,
                        session_id,
                        expected_state_hash,
                    ),
                )
                if db.execute("SELECT changes()").fetchone()[0] != 1:
                    raise SessionConflict("session changed during the transaction")
                db.execute(
                    """
                    INSERT INTO operations(
                      session_id,idempotency_key,request_hash,response_json,
                      state_hash_after,receipt_id,created_at
                    ) VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        session_id,
                        idempotency_key,
                        request_hash,
                        response_json,
                        next_state_hash,
                        receipt_id,
                        now,
                    ),
                )
                db.commit()
            except (
                IntegrityViolation,
                PersistenceError,
                ReplayConflict,
                SessionConflict,
                SessionNotFound,
            ):
                db.rollback()
                raise
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise IntegrityViolation(
                    "receipt or operation uniqueness check failed"
                ) from exc
            except sqlite3.Error as exc:
                db.rollback()
                raise PersistenceError("transition transaction failed") from exc
            finally:
                db.close()
        return CommitResult(
            response=committed_response,
            replayed=False,
            receipt_id=receipt_id,
            state_hash=next_state_hash,
        )

    def get_receipt(self, receipt_id: str) -> Mapping[str, Any]:
        receipt_id = _validate_identifier(receipt_id, "receipt_id")
        db = self._connect()
        try:
            row = db.execute(
                """
                SELECT receipt_type,receipt_json,dsse_json,receipt_hash,
                       previous_receipt_hash,signed
                FROM receipts WHERE receipt_id=?
                """,
                (receipt_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceError("receipt read failed") from exc
        finally:
            db.close()
        if row is None:
            raise SessionNotFound("receipt does not exist")
        try:
            payload = json.loads(str(row["receipt_json"]))
            envelope = json.loads(str(row["dsse_json"]))
        except (TypeError, json.JSONDecodeError) as exc:
            raise IntegrityViolation("stored receipt JSON is invalid") from exc
        if not isinstance(payload, dict) or not isinstance(envelope, dict):
            raise IntegrityViolation("stored receipt record is invalid")
        _verify_dsse_binding(payload, envelope)
        if _digest(payload) != str(row["receipt_hash"]):
            raise IntegrityViolation("receipt index hash does not verify")
        if payload.get("previous_receipt_hash") != str(
            row["previous_receipt_hash"]
        ):
            raise IntegrityViolation("receipt chain link does not verify")
        if bool(row["signed"]) is not bool(envelope["signed"]):
            raise IntegrityViolation("receipt signed index is inconsistent")
        if row["receipt_type"] == "kernel.transition":
            kernel_receipt = payload.get("kernel_receipt")
            if not isinstance(kernel_receipt, Mapping):
                raise IntegrityViolation("Khipu receipt omitted its kernel receipt")
            verify_kernel_receipt(kernel_receipt)
        elif payload.get("kernel_receipt") is not None:
            raise IntegrityViolation("session receipt contains a kernel receipt")
        return {
            "receipt": payload,
            "dsse": envelope,
            "receipt_hash": str(row["receipt_hash"]),
            "signed": bool(row["signed"]),
        }

    def recover_session(self, session_id: str) -> Mapping[str, Any]:
        """Recover state only after verifying its complete local receipt chain."""

        session = self.get_session(session_id)
        db = self._connect()
        try:
            rows = db.execute(
                """
                SELECT receipt_id,previous_receipt_hash,receipt_hash
                FROM receipts WHERE session_id=? ORDER BY rowid
                """,
                (session_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError("receipt recovery read failed") from exc
        finally:
            db.close()
        if not rows:
            raise IntegrityViolation("session has no creation receipt")
        expected_previous = "0" * 64
        recovered: list[Mapping[str, Any]] = []
        for row in rows:
            if str(row["previous_receipt_hash"]) != expected_previous:
                raise IntegrityViolation("receipt chain is divergent")
            record = self.get_receipt(str(row["receipt_id"]))
            if record["receipt_hash"] != str(row["receipt_hash"]):
                raise IntegrityViolation("receipt chain index is inconsistent")
            recovered.append(record)
            expected_previous = str(row["receipt_hash"])
        if recovered[-1]["receipt"].get("state_after") != session["state_hash"]:
            raise IntegrityViolation("receipt chain head does not bind recovered state")
        return {
            **session,
            "receipts": recovered,
            "chain_head": expected_previous,
        }

    def snapshot(self) -> Mapping[str, Any]:
        db = self._connect()
        try:
            metadata = {
                str(row["key"]): str(row["value"])
                for row in db.execute(
                    "SELECT key,value FROM metadata ORDER BY key"
                ).fetchall()
            }
            counts = {
                "sessions": int(
                    db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
                ),
                "receipts": int(
                    db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
                ),
                "operations": int(
                    db.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
                ),
                "signed_receipts": int(
                    db.execute(
                        "SELECT COUNT(*) FROM receipts WHERE signed=1"
                    ).fetchone()[0]
                ),
                "unsigned_receipts": int(
                    db.execute(
                        "SELECT COUNT(*) FROM receipts WHERE signed=0"
                    ).fetchone()[0]
                ),
            }
        except sqlite3.Error as exc:
            raise PersistenceError("storage snapshot failed") from exc
        finally:
            db.close()
        return {
            "schema": "szl.gdw.storage-snapshot/v1",
            "schema_version": SCHEMA_VERSION,
            "storage_instance_id": metadata["storage_instance_id"],
            "path": self.path,
            "persistent_required": self.persistent_required,
            "required_mount": self.required_mount,
            "mount_ok": bool(
                self.required_mount and os.path.ismount(self.required_mount)
            ),
            "counts": counts,
        }
