# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""Series-A Live Control Plane for A11oy.

One additive controller combines three previously separate payload families:

* a signed, current estate truth plane;
* a bounded Counterfactual Action Passport; and
* a zero-bandaid, one-attempt local action executor.

It uses real GitHub, Hugging Face, HTTP, SQLite, and ECDSA-P256 boundaries.
GET/HEAD requests never sign or mutate state. Refresh/evaluate/execute operations
are explicit POSTs, append hash-linked receipts, and fail closed.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Mapping
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

SCHEMA_MANIFEST = "szl.estate-manifest/v2"
SCHEMA_PASSPORT = "szl.counterfactual-action-passport/v3"
SCHEMA_RECEIPT = "szl.series-a-receipt/v1"
SCHEMA_STATUS = "szl.series-a-status/v1"
SCHEMA_TRUST = "szl.agent-trust-factor/v1"
PAYLOAD_TYPE = "application/vnd.szl.series-a-receipt.v1+json"
ORG = "szl-holdings"
HF_ORG = "SZLHOLDINGS"
CANONICAL_SPACE = f"{HF_ORG}/a11oy"
FORBIDDEN_CLONES = tuple(f"{HF_ORG}/a11oy-clone-{index}" for index in range(1, 5))
TTL_SECONDS = 300
DEFAULT_REFRESH_INTERVAL_SECONDS = 240
MIN_REFRESH_INTERVAL_SECONDS = 30
MAX_REFRESH_INTERVAL_SECONDS = TTL_SECONDS - 30
MAX_SNAPSHOT_HISTORY = 12
MAX_BODY = 64 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_PAGES = 20
EXECUTION_TIMEOUT_SECONDS = 120
EXECUTION_RECONCILE_AFTER_SECONDS = EXECUTION_TIMEOUT_SECONDS + 30
ALLOWED_ACTIONS = {"estate.refresh", "probe.public_surface"}
ALLOWED_SQLITE_JOURNALS = {"DELETE", "PERSIST", "TRUNCATE", "WAL"}
ALLOWED_PROBE_HOSTS = {
    "a-11-oy.com",
    "a11oy.net",
    "szlholdings-a11oy.hf.space",
    "szlholdings-killinchu.hf.space",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _future(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _refresh_interval_seconds() -> int:
    raw = (
        os.environ.get("A11OY_SERIES_A_REFRESH_INTERVAL_SECONDS")
        or str(DEFAULT_REFRESH_INTERVAL_SECONDS)
    ).strip()
    try:
        requested = int(raw)
    except ValueError:
        requested = DEFAULT_REFRESH_INTERVAL_SECONDS
    return max(
        MIN_REFRESH_INTERVAL_SECONDS,
        min(requested, MAX_REFRESH_INTERVAL_SECONDS),
    )


def _refresh_delay_seconds(interval_seconds: int, elapsed_seconds: float) -> float:
    return max(0.0, float(interval_seconds) - max(0.0, elapsed_seconds))


def _enabled(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _sqlite_journal_mode() -> str:
    requested = (
        os.environ.get("A11OY_SERIES_A_SQLITE_JOURNAL") or "WAL"
    ).strip().upper()
    if requested not in ALLOWED_SQLITE_JOURNALS:
        raise RuntimeError(
            "A11OY_SERIES_A_SQLITE_JOURNAL must be one of "
            + ",".join(sorted(ALLOWED_SQLITE_JOURNALS))
        )
    return requested


def _canonical(value: Any) -> bytes:
    """Narrow deterministic JSON for signed control-plane records."""

    def walk(item: Any, path: str = "$") -> None:
        if isinstance(item, float):
            raise ValueError(f"{path}: floats are forbidden in signed records")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError(f"{path}: keys must be strings")
                lowered = key.lower()
                if any(token in lowered for token in ("password", "secret_value", "private_key", "authorization")):
                    raise ValueError(f"{path}.{key}: secret-shaped field is forbidden")
                walk(child, f"{path}.{key}")
            return
        if isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{path}[{index}]")
            return
        if item is None or isinstance(item, (str, int, bool)):
            return
        raise ValueError(f"{path}: unsupported type {type(item).__name__}")

    walk(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha(value: Any) -> str:
    payload = value if isinstance(value, (bytes, bytearray)) else _canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _pae(payload_type: str, payload: bytes) -> bytes:
    ptype = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(ptype)).encode() + b" " + ptype + b" " + str(len(payload)).encode() + b" " + payload


def _safe_error(exc: Exception) -> dict[str, str]:
    return {"error_class": type(exc).__name__, "error": str(exc)[:240]}


def _git_revision() -> str:
    for key in ("SZL_GIT_SHA", "A11OY_GIT_SHA", "GITHUB_SHA"):
        value = (os.environ.get(key) or "").strip().lower()
        if len(value) == 40 and all(ch in "0123456789abcdef" for ch in value):
            return value
    return "UNKNOWN"


class ReceiptSigner:
    def __init__(self) -> None:
        self.private_key = None
        self.public_pem = ""
        self.source = "unavailable"
        self.error = ""
        try:
            from a11oy_signing_key import load_signing_key

            private_key, public_pem, source, error = load_signing_key()
            self.private_key = private_key
            self.public_pem = public_pem or ""
            self.source = source or "unavailable"
            self.error = error or ""
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {str(exc)[:180]}"

    @property
    def keyid(self) -> str | None:
        return (
            _sha(self.public_pem.strip().encode("utf-8"))
            if self.public_pem
            else None
        )

    def sign(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = _canonical(dict(payload))
        envelope: dict[str, Any] = {
            "payloadType": PAYLOAD_TYPE,
            "payload": base64.b64encode(body).decode("ascii"),
            "signatures": [],
            "pae_sha256": hashlib.sha256(_pae(PAYLOAD_TYPE, body)).hexdigest(),
            "key_source": self.source,
        }
        if self.private_key is None:
            envelope["signature_status"] = "UNSIGNED_UNAVAILABLE"
            envelope["signature_error"] = self.error or "signing key unavailable"
            return envelope
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import ec

            signature = self.private_key.sign(
                _pae(PAYLOAD_TYPE, body), ec.ECDSA(hashes.SHA256())
            )
            envelope["signatures"] = [
                {
                    "keyid": self.keyid,
                    "sig": base64.b64encode(signature).decode("ascii"),
                }
            ]
            envelope["signature_status"] = "SIGNED"
            return envelope
        except Exception as exc:
            envelope["signature_status"] = "UNSIGNED_ERROR"
            envelope["signature_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
            return envelope


class Store:
    def __init__(self, requested_path: str | None = None) -> None:
        self.persistent_required = _enabled(
            "A11OY_REQUIRE_PERSISTENT_STORAGE"
        )
        self.required_mount = (
            os.environ.get("A11OY_SERIES_A_REQUIRE_MOUNT") or ""
        ).strip()
        self.journal_mode = _sqlite_journal_mode()
        self.path = self._resolve_path(requested_path)
        self.lock = threading.RLock()
        self._init()

    def _resolve_path(self, requested: str | None) -> str:
        primary = (
            requested
            or os.environ.get("A11OY_SERIES_A_DB")
            or "/data/series-a/control-plane.sqlite3"
        )
        if self.required_mount:
            mount = Path(self.required_mount).resolve()
            candidate = Path(primary).resolve()
            try:
                candidate.relative_to(mount)
            except ValueError as exc:
                raise RuntimeError(
                    "Series-A database path is outside the required storage mount"
                ) from exc
            if not os.path.ismount(str(mount)):
                raise RuntimeError(
                    "required Series-A storage mount is not attached: "
                    + str(mount)
                )

        candidates = [primary]
        if not self.persistent_required and not self.required_mount:
            candidates.append("/tmp/a11oy_series_a_control_plane.sqlite3")
        for candidate in candidates:
            try:
                path = Path(candidate)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.parent.joinpath(".write-probe").open("w", encoding="utf-8") as probe:
                    probe.write("ok")
                path.parent.joinpath(".write-probe").unlink(missing_ok=True)
                return str(path)
            except Exception:
                continue
        if self.persistent_required or self.required_mount:
            raise RuntimeError("required persistent SQLite location is not writable")
        raise RuntimeError("no writable SQLite location")

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        selected = connection.execute(
            f"PRAGMA journal_mode={self.journal_mode}"
        ).fetchone()[0]
        if str(selected).upper() != self.journal_mode:
            connection.close()
            raise RuntimeError(
                "SQLite journal mode mismatch: requested "
                f"{self.journal_mode}, observed {selected}"
            )
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _init(self) -> None:
        with self.lock, self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS snapshots(
                  digest TEXT PRIMARY KEY,
                  payload TEXT NOT NULL,
                  envelope TEXT NOT NULL,
                  observed_at TEXT NOT NULL,
                  valid_until TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS passports(
                  digest TEXT PRIMARY KEY,
                  payload TEXT NOT NULL,
                  decision TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 1),
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS passport_executions(
                  passport_digest TEXT PRIMARY KEY REFERENCES passports(digest),
                  state TEXT NOT NULL CHECK(state IN ('PENDING','COMPLETED','RECONCILED')),
                  runtime_boot_id TEXT NOT NULL,
                  started_at TEXT NOT NULL,
                  completed_at TEXT,
                  outcome_receipt_hash TEXT
                );
                CREATE TABLE IF NOT EXISTS receipts(
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  receipt_id TEXT NOT NULL UNIQUE,
                  kind TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  envelope TEXT NOT NULL,
                  previous_hash TEXT NOT NULL,
                  receipt_hash TEXT NOT NULL UNIQUE,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  event_id TEXT NOT NULL UNIQUE,
                  kind TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS metadata(
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                );
                """
            )
            db.execute(
                "INSERT OR IGNORE INTO metadata(key,value) VALUES(?,?)",
                ("storage_instance_id", f"store_{uuid.uuid4().hex}"),
            )
            db.execute(
                "INSERT OR IGNORE INTO metadata(key,value) VALUES(?,?)",
                ("storage_created_at", _now()),
            )

    def storage_status(self) -> dict[str, Any]:
        with self.lock, self.connect() as db:
            metadata = {
                row["key"]: row["value"]
                for row in db.execute(
                    "SELECT key,value FROM metadata ORDER BY key"
                ).fetchall()
            }
            receipt = db.execute(
                """SELECT COUNT(*) AS count,
                          COALESCE(MAX(sequence), 0) AS last_sequence
                   FROM receipts"""
            ).fetchone()
            head = db.execute(
                "SELECT receipt_hash FROM receipts ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
        return {
            "persistence_required": self.persistent_required,
            "required_mount": self.required_mount or None,
            "mount_verified": bool(
                self.required_mount
                and os.path.ismount(str(Path(self.required_mount).resolve()))
            ),
            "journal_mode": self.journal_mode,
            "instance_id": metadata.get("storage_instance_id"),
            "created_at": metadata.get("storage_created_at"),
            "receipt_count": int(receipt["count"]),
            "last_receipt_sequence": int(receipt["last_sequence"]),
            "chain_head": head["receipt_hash"] if head else None,
        }

    def append_event(self, kind: str, payload: Mapping[str, Any]) -> None:
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT INTO events(event_id,kind,payload,created_at) VALUES(?,?,?,?)",
                (f"evt_{uuid.uuid4().hex}", kind, json.dumps(dict(payload), sort_keys=True), _now()),
            )

    def events_since(self, sequence: int, limit: int = 100) -> list[dict[str, Any]]:
        with self.lock, self.connect() as db:
            rows = db.execute(
                "SELECT sequence,event_id,kind,payload,created_at FROM events WHERE sequence>? ORDER BY sequence LIMIT ?",
                (max(0, sequence), max(1, min(limit, 500))),
            ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "event_id": row["event_id"],
                "kind": row["kind"],
                "payload": json.loads(row["payload"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def append_receipt(
        self, kind: str, payload: Mapping[str, Any], signer: ReceiptSigner
    ) -> dict[str, Any]:
        with self.lock, self.connect() as db:
            value = self._append_receipt_in_transaction(
                db, kind, payload, signer
            )
        self.append_event(
            kind,
            {
                "receipt_hash": value["receipt_hash"],
                "receipt_id": value["receipt"]["receipt_id"],
            },
        )
        return value

    @staticmethod
    def _append_receipt_in_transaction(
        db: sqlite3.Connection,
        kind: str,
        payload: Mapping[str, Any],
        signer: ReceiptSigner,
    ) -> dict[str, Any]:
        row = db.execute(
            "SELECT receipt_hash FROM receipts ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous = row["receipt_hash"] if row else "0" * 64
        receipt = {
            "schema": SCHEMA_RECEIPT,
            "receipt_id": f"rcpt_{uuid.uuid4().hex}",
            "kind": kind,
            "created_at": _now(),
            "source_revision": _git_revision(),
            "previous_receipt_hash": previous,
            "payload": dict(payload),
        }
        envelope = signer.sign(receipt)
        receipt_hash = _sha(envelope)
        db.execute(
            """INSERT INTO receipts(receipt_id,kind,payload,envelope,previous_hash,receipt_hash,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (
                receipt["receipt_id"],
                kind,
                json.dumps(receipt, sort_keys=True),
                json.dumps(envelope, sort_keys=True),
                previous,
                receipt_hash,
                receipt["created_at"],
            ),
        )
        return {
            "receipt": receipt,
            "envelope": envelope,
            "receipt_hash": receipt_hash,
        }

    def list_receipts(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.lock, self.connect() as db:
            rows = db.execute(
                "SELECT sequence,kind,payload,envelope,receipt_hash,created_at FROM receipts ORDER BY sequence DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "kind": row["kind"],
                "receipt": json.loads(row["payload"]),
                "envelope": json.loads(row["envelope"]),
                "receipt_hash": row["receipt_hash"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def receipt_recovery_snapshot(
        self,
        receipt_hash: str,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        # Keep status and exact-hash lookup in one SQLite read transaction so a
        # restart proof cannot combine evidence from different storage views.
        with self.lock, self.connect() as db:
            db.execute("BEGIN")
            metadata = {
                row["key"]: row["value"]
                for row in db.execute(
                    "SELECT key,value FROM metadata ORDER BY key"
                ).fetchall()
            }
            receipt = db.execute(
                """SELECT COUNT(*) AS count,
                          COALESCE(MAX(sequence), 0) AS last_sequence
                   FROM receipts"""
            ).fetchone()
            head = db.execute(
                "SELECT receipt_hash FROM receipts ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            row = db.execute(
                """SELECT sequence,kind,payload,envelope,receipt_hash,created_at
                   FROM receipts
                   WHERE receipt_hash=?""",
                (receipt_hash,),
            ).fetchone()
        storage = {
            "persistence_required": self.persistent_required,
            "required_mount": self.required_mount or None,
            "mount_verified": bool(
                self.required_mount
                and os.path.ismount(str(Path(self.required_mount).resolve()))
            ),
            "journal_mode": self.journal_mode,
            "instance_id": metadata.get("storage_instance_id"),
            "created_at": metadata.get("storage_created_at"),
            "receipt_count": int(receipt["count"]),
            "last_receipt_sequence": int(receipt["last_sequence"]),
            "chain_head": head["receipt_hash"] if head else None,
        }
        item = (
            {
                "sequence": row["sequence"],
                "kind": row["kind"],
                "receipt": json.loads(row["payload"]),
                "envelope": json.loads(row["envelope"]),
                "receipt_hash": row["receipt_hash"],
                "created_at": row["created_at"],
            }
            if row is not None
            else None
        )
        return storage, item

    def save_snapshot(self, manifest: Mapping[str, Any], envelope: Mapping[str, Any]) -> str:
        digest = _sha(manifest)
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO snapshots(digest,payload,envelope,observed_at,valid_until) VALUES(?,?,?,?,?)",
                (
                    digest,
                    json.dumps(dict(manifest), sort_keys=True),
                    json.dumps(dict(envelope), sort_keys=True),
                    manifest["observed_at"],
                    manifest["valid_until"],
                ),
            )
            db.execute(
                """DELETE FROM snapshots
                   WHERE digest NOT IN (
                     SELECT digest FROM snapshots
                     ORDER BY observed_at DESC, digest DESC
                     LIMIT ?
                   )""",
                (MAX_SNAPSHOT_HISTORY,),
            )
        return digest

    def latest_snapshot(self) -> dict[str, Any] | None:
        with self.lock, self.connect() as db:
            row = db.execute(
                "SELECT digest,payload,envelope,observed_at,valid_until FROM snapshots ORDER BY observed_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return {
            "digest": row["digest"],
            "manifest": json.loads(row["payload"]),
            "envelope": json.loads(row["envelope"]),
            "observed_at": row["observed_at"],
            "valid_until": row["valid_until"],
        }

    def save_passport(self, passport: Mapping[str, Any]) -> str:
        digest = _sha(passport)
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT INTO passports(digest,payload,decision,attempts,created_at) VALUES(?,?,?,?,?)",
                (digest, json.dumps(dict(passport), sort_keys=True), passport["decision"], 0, passport["created_at"]),
            )
        return digest

    def load_passport(self, digest: str) -> dict[str, Any] | None:
        with self.lock, self.connect() as db:
            row = db.execute(
                "SELECT payload,decision,attempts FROM passports WHERE digest=?", (digest,)
            ).fetchone()
        if row is None:
            return None
        value = json.loads(row["payload"])
        value["attempts"] = row["attempts"]
        return value

    def begin_execution(
        self,
        digest: str,
        runtime_boot_id: str,
        started_at: str,
    ) -> None:
        """Consume one attempt and persist its execution intent atomically."""
        with self.lock, self.connect() as db:
            result = db.execute(
                "UPDATE passports SET attempts=1 WHERE digest=? AND attempts=0", (digest,)
            )
            if result.rowcount != 1:
                raise RuntimeError("passport attempt is absent or already consumed")
            db.execute(
                """INSERT INTO passport_executions(
                     passport_digest,state,runtime_boot_id,started_at
                   ) VALUES(?,?,?,?)""",
                (digest, "PENDING", runtime_boot_id, started_at),
            )

    def execution_status(self, digest: str) -> dict[str, Any] | None:
        with self.lock, self.connect() as db:
            row = db.execute(
                """SELECT passport_digest,state,runtime_boot_id,started_at,
                          completed_at,outcome_receipt_hash
                   FROM passport_executions WHERE passport_digest=?""",
                (digest,),
            ).fetchone()
        return dict(row) if row is not None else None

    def next_execution_reconciliation_delay(
        self,
        *,
        stale_after_seconds: int = EXECUTION_RECONCILE_AFTER_SECONDS,
        now: datetime | None = None,
    ) -> float | None:
        """Return the bounded delay before the oldest pending intent is stale."""
        with self.lock, self.connect() as db:
            rows = db.execute(
                """SELECT started_at FROM passport_executions
                   WHERE state='PENDING'
                   ORDER BY started_at"""
            ).fetchall()
        if not rows:
            return None
        current = now or datetime.now(timezone.utc)
        delays: list[float] = []
        for row in rows:
            try:
                started = datetime.fromisoformat(
                    str(row["started_at"]).replace("Z", "+00:00")
                )
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                age = max(0.0, (current - started).total_seconds())
                delays.append(max(0.0, float(stale_after_seconds) - age))
            except (TypeError, ValueError):
                # A malformed persisted timestamp cannot prove a live execution.
                delays.append(0.0)
        return min(delays)

    def complete_execution(
        self,
        digest: str,
        outcome: Mapping[str, Any],
        signer: ReceiptSigner,
    ) -> dict[str, Any]:
        """Persist the terminal outcome and close its intent in one transaction."""
        with self.lock, self.connect() as db:
            row = db.execute(
                "SELECT state FROM passport_executions WHERE passport_digest=?",
                (digest,),
            ).fetchone()
            if row is None or row["state"] != "PENDING":
                raise RuntimeError("execution intent is absent or already terminal")
            value = self._append_receipt_in_transaction(
                db,
                "passport.outcome",
                outcome,
                signer,
            )
            result = db.execute(
                """UPDATE passport_executions
                   SET state='COMPLETED',completed_at=?,outcome_receipt_hash=?
                   WHERE passport_digest=? AND state='PENDING'""",
                (
                    str(outcome.get("completed_at") or _now()),
                    value["receipt_hash"],
                    digest,
                ),
            )
            if result.rowcount != 1:
                raise RuntimeError("execution intent changed before completion")
        self.append_event(
            "passport.outcome",
            {
                "receipt_hash": value["receipt_hash"],
                "receipt_id": value["receipt"]["receipt_id"],
            },
        )
        return value

    def reconcile_interrupted_executions(
        self,
        signer: ReceiptSigner,
        *,
        stale_after_seconds: int = EXECUTION_RECONCILE_AFTER_SECONDS,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Terminalize stale abandoned intents without replaying their actions."""
        current = now or datetime.now(timezone.utc)
        completed_at = current.isoformat().replace("+00:00", "Z")
        reconciled: list[dict[str, Any]] = []
        with self.lock, self.connect() as db:
            rows = db.execute(
                """SELECT passport_digest,runtime_boot_id,started_at
                   FROM passport_executions
                   WHERE state='PENDING'
                   ORDER BY started_at,passport_digest"""
            ).fetchall()
            for row in rows:
                try:
                    started = datetime.fromisoformat(
                        str(row["started_at"]).replace("Z", "+00:00")
                    )
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    age = max(0.0, (current - started).total_seconds())
                except (TypeError, ValueError):
                    age = float(stale_after_seconds)
                if age < stale_after_seconds:
                    continue
                outcome = {
                    "status": "FAILED",
                    "error_class": "ExecutionInterrupted",
                    "error": (
                        "runtime ended before a terminal outcome was persisted"
                    ),
                    "uncertainty": (
                        "the admitted action may have started or partially completed; "
                        "it was not replayed"
                    ),
                    "reconciliation": "INTERRUPTED_EXECUTION_RECONCILED",
                    "previous_runtime_boot_id": row["runtime_boot_id"],
                    "started_at": row["started_at"],
                    "completed_at": completed_at,
                    "attempt": 1,
                    "max_attempts": 1,
                    "passport_digest": row["passport_digest"],
                    "governance": {
                        "allowed": True,
                        "decision": "ALLOW",
                        "reason_codes": [
                            "PREVIOUS_RUNTIME_ADMISSION_PERSISTED"
                        ],
                    },
                }
                value = self._append_receipt_in_transaction(
                    db,
                    "passport.outcome",
                    outcome,
                    signer,
                )
                result = db.execute(
                    """UPDATE passport_executions
                       SET state='RECONCILED',completed_at=?,outcome_receipt_hash=?
                       WHERE passport_digest=? AND state='PENDING'""",
                    (
                        completed_at,
                        value["receipt_hash"],
                        row["passport_digest"],
                    ),
                )
                if result.rowcount != 1:
                    raise RuntimeError(
                        "execution intent changed during reconciliation"
                    )
                reconciled.append(value)
        for value in reconciled:
            self.append_event(
                "passport.outcome",
                {
                    "receipt_hash": value["receipt_hash"],
                    "receipt_id": value["receipt"]["receipt_id"],
                },
            )
        return reconciled

    def consume_denied_attempt(
        self,
        digest: str,
        payload: Mapping[str, Any],
        signer: ReceiptSigner,
    ) -> dict[str, Any]:
        """Consume the single attempt and persist its denial in one transaction."""
        with self.lock, self.connect() as db:
            result = db.execute(
                "UPDATE passports SET attempts=1 WHERE digest=? AND attempts=0",
                (digest,),
            )
            if result.rowcount != 1:
                raise RuntimeError(
                    "passport attempt is absent or already consumed"
                )
            value = self._append_receipt_in_transaction(
                db,
                "passport.execution-denied",
                payload,
                signer,
            )
        self.append_event(
            "passport.execution-denied",
            {
                "receipt_hash": value["receipt_hash"],
                "receipt_id": value["receipt"]["receipt_id"],
            },
        )
        return value

    def outcome_for_passport(self, digest: str) -> dict[str, Any] | None:
        with self.lock, self.connect() as db:
            rows = db.execute(
                """SELECT sequence,kind,payload,envelope,receipt_hash,created_at
                   FROM receipts WHERE kind='passport.outcome'
                   ORDER BY sequence DESC"""
            ).fetchall()
        for row in rows:
            receipt = json.loads(row["payload"])
            outcome = receipt.get("payload")
            if isinstance(outcome, dict) and outcome.get("passport_digest") == digest:
                return {
                    "outcome": outcome,
                    "outcome_receipt": {
                        "sequence": row["sequence"],
                        "kind": row["kind"],
                        "receipt": receipt,
                        "envelope": json.loads(row["envelope"]),
                        "receipt_hash": row["receipt_hash"],
                        "created_at": row["created_at"],
                    },
                }
        return None


@dataclass
class Observation:
    state: str
    value: Any = None
    detail: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        value = {"state": self.state}
        if self.value is not None:
            value["value"] = self.value
        if self.detail:
            value["detail"] = dict(self.detail)
        return value


class Collector:
    def __init__(self) -> None:
        self.github_token = (os.environ.get("GITHUB_TOKEN") or "").strip()
        self.hf_token = (os.environ.get("HF_TOKEN") or "").strip()

    async def _json(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        allowed_host: str,
    ) -> tuple[Any, httpx.Response]:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != allowed_host or parsed.username or parsed.password:
            raise RuntimeError("outbound URL left the fixed HTTPS origin")
        response = await client.get(url, params=params)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise RuntimeError("response exceeded byte limit")
        final = urlsplit(str(response.url))
        if final.scheme != "https" or final.hostname != allowed_host:
            raise RuntimeError("redirect left the fixed HTTPS origin")
        return response.json(), response

    async def github(self) -> Observation:
        headers = {"accept": "application/vnd.github+json", "user-agent": "szl-series-a/1"}
        if self.github_token:
            headers["authorization"] = f"Bearer {self.github_token}"
        try:
            repos: list[dict[str, Any]] = []
            async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=False) as client:
                complete = False
                for page in range(1, MAX_PAGES + 1):
                    values, _ = await self._json(
                        client,
                        f"https://api.github.com/orgs/{ORG}/repos",
                        params={"type": "all", "per_page": 100, "page": page},
                        allowed_host="api.github.com",
                    )
                    if not isinstance(values, list):
                        raise RuntimeError("repository listing was not an array")
                    repos.extend(item for item in values if isinstance(item, dict))
                    if len(values) < 100:
                        complete = True
                        break
                if not complete:
                    raise RuntimeError("repository pagination exceeded bounded window")
                pr_data, _ = await self._json(
                    client,
                    "https://api.github.com/search/issues",
                    params={"q": f"org:{ORG} is:pr is:open", "per_page": 1},
                    allowed_host="api.github.com",
                )
            rows = [
                {
                    "name": str(item.get("name") or ""),
                    "archived": bool(item.get("archived")),
                    "visibility": str(item.get("visibility") or "unknown"),
                    "default_branch": str(item.get("default_branch") or ""),
                    "updated_at": str(item.get("updated_at") or ""),
                }
                for item in repos
            ]
            return Observation(
                "OBSERVED",
                {
                    "repository_count": len(rows),
                    "open_pull_request_count": int((pr_data or {}).get("total_count", 0)),
                    "pagination_complete": True,
                    "repositories": rows,
                },
                {"authenticated": bool(self.github_token)},
            )
        except Exception as exc:
            return Observation("UNAVAILABLE", detail=_safe_error(exc))

    def _hf_list(self, method_name: str, kwargs: Mapping[str, Any]) -> list[Any]:
        from huggingface_hub import HfApi

        api = HfApi(token=self.hf_token or None)
        method = getattr(api, method_name, None)
        if method is None:
            raise AttributeError(f"HfApi.{method_name} unavailable")
        return list(method(**dict(kwargs)))

    async def _hf_kernels(self) -> list[dict[str, Any]]:
        headers = {"accept": "application/json", "user-agent": "szl-series-a/1"}
        if self.hf_token:
            headers["authorization"] = f"Bearer {self.hf_token}"
        output: list[dict[str, Any]] = []
        url: str | None = "https://huggingface.co/api/kernels"
        params: Mapping[str, Any] | None = {"author": HF_ORG, "limit": 1000, "full": "true"}
        async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=False) as client:
            for _ in range(MAX_PAGES):
                if not url:
                    return output
                values, response = await self._json(
                    client, url, params=params, allowed_host="huggingface.co"
                )
                if not isinstance(values, list):
                    raise RuntimeError("kernel listing was not an array")
                output.extend(item for item in values if isinstance(item, dict))
                link = response.links.get("next") or {}
                url = link.get("url") if isinstance(link, dict) else None
                params = None
                if not url:
                    return output
        raise RuntimeError("kernel pagination exceeded bounded window")

    async def huggingface(self) -> Observation:
        categories: dict[str, Any] = {}
        errors: dict[str, Any] = {}
        methods = {
            "models": ("list_models", {"author": HF_ORG}),
            "datasets": ("list_datasets", {"author": HF_ORG}),
            "spaces": ("list_spaces", {"author": HF_ORG}),
            "collections": ("list_collections", {"owner": HF_ORG}),
            "buckets": ("list_buckets", {"namespace": HF_ORG}),
        }
        for name, (method, kwargs) in methods.items():
            try:
                items = await asyncio.to_thread(self._hf_list, method, kwargs)
                rows = []
                for item in items:
                    item_id = None
                    for field in ("id", "repo_id", "name", "slug"):
                        candidate = item.get(field) if isinstance(item, dict) else getattr(item, field, None)
                        if isinstance(candidate, str) and candidate:
                            item_id = candidate
                            break
                    rows.append({"id": item_id})
                categories[name] = {"state": "OBSERVED", "count": len(rows), "items": rows}
            except Exception as exc:
                categories[name] = {"state": "UNAVAILABLE"}
                errors[name] = _safe_error(exc)
        try:
            kernels = await self._hf_kernels()
            categories["kernels"] = {
                "state": "OBSERVED",
                "count": len(kernels),
                "items": [{"id": str(item.get("id") or item.get("repo_id") or "")} for item in kernels],
            }
        except Exception as exc:
            categories["kernels"] = {"state": "UNAVAILABLE"}
            errors["kernels"] = _safe_error(exc)

        space_ids = {
            row.get("id")
            for row in categories.get("spaces", {}).get("items", [])
            if isinstance(row, dict)
        }
        clones_present = sorted(value for value in FORBIDDEN_CLONES if value in space_ids)
        canonical_present = CANONICAL_SPACE in space_ids
        state = "OBSERVED" if categories.get("spaces", {}).get("state") == "OBSERVED" else "PARTIAL"
        return Observation(
            state,
            {
                "categories": categories,
                "canonical_space": CANONICAL_SPACE,
                "canonical_present": canonical_present,
                "forbidden_clones_present": clones_present,
                "singleton_ok": canonical_present and not clones_present,
            },
            {"authenticated": bool(self.hf_token), "errors": errors},
        )

    async def collect(self) -> dict[str, Any]:
        github, hf = await asyncio.gather(self.github(), self.huggingface())
        critical_failures: list[str] = []
        if github.state != "OBSERVED":
            critical_failures.append("github_inventory_unavailable")
        if hf.state not in {"OBSERVED", "PARTIAL"}:
            critical_failures.append("huggingface_inventory_unavailable")
        hf_value = hf.value if isinstance(hf.value, dict) else {}
        if hf_value and not hf_value.get("singleton_ok"):
            critical_failures.append("canonical_a11oy_singleton_failed")
        categories = hf_value.get("categories", {}) if isinstance(hf_value, dict) else {}
        counts = {
            name: value.get("count") if isinstance(value, dict) and value.get("state") == "OBSERVED" else None
            for name, value in categories.items()
        }
        manifest = {
            "schema": SCHEMA_MANIFEST,
            "observed_at": _now(),
            "valid_until": _future(TTL_SECONDS),
            "source_revision": _git_revision(),
            "organization": ORG,
            "huggingface_organization": HF_ORG,
            "status": "BLOCKED" if critical_failures else "OBSERVED",
            "critical_failures": critical_failures,
            "github": github.as_dict(),
            "huggingface": hf.as_dict(),
            "counts": {
                "github_repositories": (
                    github.value.get("repository_count")
                    if isinstance(github.value, dict) and github.state == "OBSERVED"
                    else None
                ),
                "github_open_pull_requests": (
                    github.value.get("open_pull_request_count")
                    if isinstance(github.value, dict) and github.state == "OBSERVED"
                    else None
                ),
                **counts,
            },
            "claim": "CURRENT_OBSERVATION_NOT_ETERNAL_TRUTH",
            "counterfactual_label": "MODELED",
            "private_reasoning_collected": False,
        }
        manifest["manifest_digest"] = _sha(manifest)
        return manifest


class Service:
    def __init__(self, db_path: str | None = None) -> None:
        self.store = Store(db_path)
        self.signer = ReceiptSigner()
        self.collector = Collector()
        self.runtime_boot_id = f"boot_{uuid.uuid4().hex}"
        self.refresh_lock = asyncio.Lock()
        self.execution_tasks: set[asyncio.Task[Any]] = set()
        self.reconciliation_task: asyncio.Task[Any] | None = None
        self.started = False
        self.background_task: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        if self.started:
            return
        self.store.reconcile_interrupted_executions(self.signer)
        if self.store.next_execution_reconciliation_delay() is not None:
            self.reconciliation_task = asyncio.create_task(
                self._reconcile_pending_executions(),
                name="a11oy-series-a-execution-reconciliation",
            )
        self.started = True
        if (os.environ.get("A11OY_SERIES_A_STARTUP_REFRESH") or "1").strip() == "0":
            self.store.append_event("estate.refresh.skipped", {"reason": "explicit test/runtime configuration"})
            return

        self.background_task = asyncio.create_task(
            self._refresh_loop(),
            name="a11oy-series-a-periodic-refresh",
        )

    async def _reconcile_pending_executions(self) -> None:
        """Wait out the live-execution bound, then fail closed without replay."""
        while True:
            delay = self.store.next_execution_reconciliation_delay()
            if delay is None:
                return
            if delay > 0:
                await asyncio.sleep(delay)
            self.store.reconcile_interrupted_executions(self.signer)

    async def _refresh_loop(self) -> None:
        interval_seconds = _refresh_interval_seconds()
        actor = "startup"
        while True:
            cycle_started = time.monotonic()
            try:
                await self.refresh(actor)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.store.append_event(
                    "estate.refresh.failed",
                    {
                        "actor": actor,
                        "retry_in_seconds": interval_seconds,
                        **_safe_error(exc),
                    },
                )
            actor = "periodic"
            elapsed = max(0.0, time.monotonic() - cycle_started)
            await asyncio.sleep(_refresh_delay_seconds(interval_seconds, elapsed))

    async def stop(self) -> None:
        reconciliation = self.reconciliation_task
        self.reconciliation_task = None
        if reconciliation is not None:
            reconciliation.cancel()
            try:
                await reconciliation
            except asyncio.CancelledError:
                pass
        task = self.background_task
        self.background_task = None
        self.started = False
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        executions = list(self.execution_tasks)
        for execution in executions:
            execution.cancel()
        if executions:
            await asyncio.gather(*executions, return_exceptions=True)

    def scheduler_status(self) -> dict[str, Any]:
        task = self.background_task
        enabled = (
            os.environ.get("A11OY_SERIES_A_STARTUP_REFRESH") or "1"
        ).strip() != "0"
        return {
            "enabled": enabled,
            "started": self.started,
            "task_running": bool(task is not None and not task.done()),
            "interval_seconds": _refresh_interval_seconds(),
        }

    async def refresh(
        self,
        actor: str,
        *,
        governance: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        action = {
            "type": "estate.refresh",
            "target": "szl://estate/current",
            "impact": "MODERATE",
            "irreversible": False,
        }
        decision = dict(governance) if governance is not None else self._governance_gate(action)
        authorization = self.store.append_receipt(
            "estate.refresh.authorization",
            {
                "actor": actor,
                "action_digest": _sha(action),
                "decision": decision.get("decision", "DENY"),
                "reason_codes": decision.get(
                    "reason_codes", ["DOCTRINE_GATE_UNAVAILABLE"]
                ),
            },
            self.signer,
        )
        if not decision.get("allowed"):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "GOVERNANCE_DENY",
                    "reason_codes": decision.get(
                        "reason_codes", ["DOCTRINE_GATE_UNAVAILABLE"]
                    ),
                    "receipt_hash": authorization["receipt_hash"],
                    "signature_status": authorization["envelope"][
                        "signature_status"
                    ],
                },
            )
        if self.refresh_lock.locked():
            raise HTTPException(status_code=409, detail="estate refresh already running")
        async with self.refresh_lock:
            manifest = await self.collector.collect()
            envelope = self.signer.sign(manifest)
            digest = self.store.save_snapshot(manifest, envelope)
            receipt = self.store.append_receipt(
                "estate.refresh",
                {
                    "actor": actor,
                    "manifest_digest": digest,
                    "status": manifest["status"],
                    "counts": manifest["counts"],
                },
                self.signer,
            )
            return {"manifest": manifest, "envelope": envelope, "refresh_receipt": receipt}

    def latest_status(self) -> dict[str, Any]:
        latest = self.store.latest_snapshot()
        if latest is None:
            return {
                "schema": SCHEMA_STATUS,
                "state": "PENDING",
                "terminal": True,
                "source_revision": _git_revision(),
                "runtime_boot_id": self.runtime_boot_id,
                "signing_key_source": self.signer.source,
                "database": self.store.path,
                "storage": self.store.storage_status(),
                "refresh_scheduler": self.scheduler_status(),
                "detail": "no completed refresh is persisted yet",
            }
        valid_until = datetime.fromisoformat(latest["valid_until"].replace("Z", "+00:00"))
        stale = datetime.now(timezone.utc) >= valid_until
        manifest = latest["manifest"]
        return {
            "schema": SCHEMA_STATUS,
            "state": "STALE" if stale else manifest["status"],
            "terminal": True,
            "source_revision": _git_revision(),
            "runtime_boot_id": self.runtime_boot_id,
            "manifest_digest": latest["digest"],
            "observed_at": latest["observed_at"],
            "valid_until": latest["valid_until"],
            "counts": manifest.get("counts", {}),
            "critical_failures": manifest.get("critical_failures", []),
            "signature_status": latest["envelope"].get("signature_status"),
            "signing_key_source": self.signer.source,
            "database": self.store.path,
            "storage": self.store.storage_status(),
            "refresh_scheduler": self.scheduler_status(),
        }

    def _governance_gate(self, action: Mapping[str, Any]) -> dict[str, Any]:
        """Run the file-backed doctrine and codename gates, failing closed."""
        try:
            import szl_colang_policy

            policy = szl_colang_policy.get_policy()
            if not policy.loaded:
                raise RuntimeError("no file-backed Colang policy is loaded")
            colang = policy.evaluate(
                {
                    "tool": "execute",
                    "effecting": True,
                    "events": ["gate.evaluate"],
                    "action_type": str(action.get("type") or ""),
                    "target": str(action.get("target") or ""),
                    "high_impact": str(action.get("impact") or "").upper()
                    in {"HIGH", "CRITICAL"},
                    "irreversible": bool(action.get("irreversible", False)),
                }
            )
        except Exception as exc:
            return {
                "allowed": False,
                "decision": "DENY",
                "reason_codes": ["DOCTRINE_GATE_UNAVAILABLE"],
                "detail": _safe_error(exc),
            }

        try:
            import szl_codename_gate

            codename_hits = [
                str(value) for value in szl_codename_gate.scan_text(_canonical(action).decode())
            ]
        except Exception as exc:
            return {
                "allowed": False,
                "decision": "DENY",
                "reason_codes": ["CODENAME_GATE_UNAVAILABLE"],
                "detail": _safe_error(exc),
                "colang": colang,
            }

        reasons: list[str] = []
        if not colang.get("allow"):
            reasons.append("DOCTRINE_POLICY_DENY")
        if codename_hits:
            reasons.append("CODENAME_POLICY_DENY")
        return {
            "allowed": not reasons,
            "decision": "ALLOW" if not reasons else "DENY",
            "reason_codes": reasons or ["FILE_BACKED_GOVERNANCE_PASS"],
            "colang": {
                "decision": colang.get("decision"),
                "fired_flows": colang.get("fired_flows", []),
                "flows_evaluated": colang.get("flows_evaluated", []),
                "policy_files": colang.get("policy_files", []),
            },
            "codename_gate": {
                "clean": not codename_hits,
                "hits": codename_hits,
            },
        }

    def _fresh_evidence_reasons(self, evidence: Any) -> list[str]:
        """Require a current server-signed estate snapshot for executable evidence."""
        if not isinstance(evidence, list) or not evidence:
            return ["EVIDENCE_REQUIRED"]
        latest = self.store.latest_snapshot()
        if latest is None:
            return ["FRESH_SERVER_EVIDENCE_REQUIRED"]
        manifest = latest.get("manifest")
        if not isinstance(manifest, dict) or manifest.get("status") != "OBSERVED":
            return ["OBSERVED_SERVER_EVIDENCE_REQUIRED"]
        critical_failures = manifest.get("critical_failures")
        if not isinstance(critical_failures, list) or critical_failures:
            return ["CRITICAL_FAILURE_FREE_SERVER_EVIDENCE_REQUIRED"]
        try:
            valid_until = datetime.fromisoformat(latest["valid_until"].replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return ["FRESH_SERVER_EVIDENCE_REQUIRED"]
        if datetime.now(timezone.utc) >= valid_until:
            return ["FRESH_SERVER_EVIDENCE_REQUIRED"]
        if latest["envelope"].get("signature_status") != "SIGNED":
            return ["SIGNED_SERVER_EVIDENCE_REQUIRED"]

        reasons: list[str] = []
        for item in evidence:
            if not isinstance(item, dict) or item.get("label") in {"UNKNOWN", "UNAVAILABLE"}:
                reasons.append("NON_ACTIONABLE_EVIDENCE")
                continue
            expected = {
                "label": "OBSERVED",
                "content_digest": latest["digest"],
                "observed_at": latest["observed_at"],
                "valid_until": latest["valid_until"],
            }
            if any(item.get(key) != value for key, value in expected.items()):
                reasons.append("SERVER_OBSERVED_EVIDENCE_REQUIRED")
        return sorted(set(reasons))

    def evaluate_passport(self, body: Mapping[str, Any]) -> dict[str, Any]:
        action = body.get("action")
        if not isinstance(action, dict):
            raise HTTPException(status_code=422, detail="action must be an object")
        action_type = str(action.get("type") or "")
        target = str(action.get("target") or "")
        impact = str(action.get("impact") or "MODERATE").upper()
        irreversible = bool(action.get("irreversible", False))
        if action_type not in ALLOWED_ACTIONS:
            decision = "BLOCK"
            reasons = ["ACTION_TYPE_NOT_ALLOWLISTED"]
        elif not target:
            decision = "BLOCK"
            reasons = ["TARGET_REQUIRED"]
        elif action_type == "estate.refresh" and target != "szl://estate/current":
            decision = "BLOCK"
            reasons = ["TARGET_NOT_ALLOWLISTED"]
        elif action_type == "probe.public_surface":
            parsed_target = urlsplit(target)
            if (
                parsed_target.scheme != "https"
                or parsed_target.hostname not in ALLOWED_PROBE_HOSTS
                or parsed_target.username
                or parsed_target.password
            ):
                decision = "BLOCK"
                reasons = ["TARGET_NOT_ALLOWLISTED"]
            elif impact in {"HIGH", "CRITICAL"} or irreversible:
                decision = "REQUIRE_APPROVAL"
                reasons = ["INDEPENDENT_APPROVAL_REQUIRED"]
            else:
                decision = "ALLOW"
                reasons = ["BOUNDED_REVERSIBLE_ACTION"]
        elif impact in {"HIGH", "CRITICAL"} or irreversible:
            decision = "REQUIRE_APPROVAL"
            reasons = ["INDEPENDENT_APPROVAL_REQUIRED"]
        else:
            decision = "ALLOW"
            reasons = ["BOUNDED_REVERSIBLE_ACTION"]

        evidence = body.get("evidence")
        evidence_reasons = self._fresh_evidence_reasons(evidence)
        governance = self._governance_gate(action)
        if evidence_reasons:
            decision = "BLOCK"
            reasons = sorted(set(reasons + evidence_reasons))
        if not governance["allowed"]:
            decision = "BLOCK"
            reasons = sorted(set(reasons + governance["reason_codes"]))

        no_action = {
            "scenario_id": "no-action",
            "kind": "NO_ACTION",
            "label": "MODELED",
            "outcome": str(body.get("expected_if_withheld") or "current state persists"),
        }
        proposed = {
            "scenario_id": "proposed-action",
            "kind": "PROPOSED_ACTION",
            "label": "MODELED",
            "outcome": str(body.get("expected_if_acted") or "bounded action completes or fails closed"),
        }
        passport = {
            "schema": SCHEMA_PASSPORT,
            "passport_id": f"cap_{uuid.uuid4().hex}",
            "created_at": _now(),
            "source_revision": _git_revision(),
            "subject": {
                "principal_id": str(body.get("principal_id") or "anonymous-proposer"),
                "workload_id": str(body.get("workload_id") or "a11oy-series-a"),
            },
            "action": action,
            "action_digest": _sha(action),
            "evidence": evidence if isinstance(evidence, list) else [],
            "counterfactuals": [no_action, proposed],
            "decision": decision,
            "reason_codes": reasons,
            "governance": governance,
            "max_attempts": 1,
            "private_reasoning_collected": False,
        }
        digest = self.store.save_passport(passport)
        receipt = self.store.append_receipt(
            "passport.evaluate",
            {"passport_digest": digest, "decision": decision, "reason_codes": reasons},
            self.signer,
        )
        return {"passport": passport, "passport_digest": digest, "decision_receipt": receipt}

    async def execute(self, body: Mapping[str, Any]) -> dict[str, Any]:
        digest = str(body.get("passport_digest") or "")
        passport = self.store.load_passport(digest)
        if passport is None:
            raise HTTPException(status_code=404, detail="passport not found")
        if passport["attempts"] != 0:
            raise HTTPException(status_code=409, detail="passport attempt already consumed")
        if passport["decision"] != "ALLOW":
            reasons = [f"PASSPORT_DECISION_{passport['decision']}"]
            try:
                denial_receipt = self.store.consume_denied_attempt(
                    digest,
                    {"passport_digest": digest, "reason_codes": reasons},
                    self.signer,
                )
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=409,
                    detail="passport attempt already consumed",
                ) from exc
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PASSPORT_DECISION_DENY",
                    "reason_codes": reasons,
                    "receipt_hash": denial_receipt["receipt_hash"],
                    "signature_status": denial_receipt["envelope"][
                        "signature_status"
                    ],
                },
            )
        action = passport["action"]
        governance = self._governance_gate(action)
        evidence_reasons = self._fresh_evidence_reasons(passport.get("evidence"))
        if not governance["allowed"] or evidence_reasons:
            reasons = sorted(set(governance["reason_codes"] + evidence_reasons))
            try:
                denial_receipt = self.store.consume_denied_attempt(
                    digest,
                    {"passport_digest": digest, "reason_codes": reasons},
                    self.signer,
                )
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=409,
                    detail="passport attempt already consumed",
                ) from exc
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "GOVERNANCE_DENY",
                    "reason_codes": reasons,
                    "receipt_hash": denial_receipt["receipt_hash"],
                    "signature_status": denial_receipt["envelope"]["signature_status"],
                },
            )
        started = _now()
        try:
            self.store.begin_execution(
                digest,
                self.runtime_boot_id,
                started,
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=409,
                detail="passport attempt already consumed",
            ) from exc
        task = asyncio.create_task(
            self._execute_consumed(digest, passport, governance, started),
            name=f"series-a-execute-{digest[:12]}",
        )
        self.execution_tasks.add(task)

        def finished(value: asyncio.Task[Any]) -> None:
            self.execution_tasks.discard(value)
            if not value.cancelled():
                try:
                    value.exception()
                except Exception:
                    pass

        task.add_done_callback(finished)
        return await asyncio.shield(task)

    async def _execute_consumed(
        self,
        digest: str,
        passport: Mapping[str, Any],
        governance: Mapping[str, Any],
        started: str,
    ) -> dict[str, Any]:
        action = passport["action"]
        try:
            async def run() -> dict[str, Any]:
                if action["type"] == "estate.refresh":
                    result = await self.refresh(
                        str(passport["passport_id"]),
                        governance=governance,
                    )
                    return {
                        "status": "SUCCEEDED",
                        "manifest_digest": result["manifest"]["manifest_digest"],
                        "estate_status": result["manifest"]["status"],
                    }
                if action["type"] == "probe.public_surface":
                    return await self._probe(str(action["target"]))
                raise RuntimeError("action left allowlist after authorization")

            outcome = await asyncio.wait_for(
                run(), timeout=EXECUTION_TIMEOUT_SECONDS
            )
        except Exception as exc:
            outcome = {"status": "FAILED", **_safe_error(exc)}
        outcome.update(
            {
                "started_at": started,
                "completed_at": _now(),
                "attempt": 1,
                "max_attempts": 1,
                "passport_digest": digest,
                "governance": governance,
            }
        )
        receipt = self.store.complete_execution(digest, outcome, self.signer)
        return {"outcome": outcome, "outcome_receipt": receipt}

    async def _probe(self, target: str) -> dict[str, Any]:
        parsed = urlsplit(target)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_PROBE_HOSTS or parsed.username or parsed.password:
            raise RuntimeError("probe target is not in the fixed HTTPS allowlist")
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get(target, headers={"accept": "application/json,text/html;q=0.9"})
        final = urlsplit(str(response.url))
        if final.hostname not in ALLOWED_PROBE_HOSTS:
            raise RuntimeError("probe redirect left the allowlist")
        return {
            "status": "SUCCEEDED" if 200 <= response.status_code < 400 else "FAILED",
            "target": target,
            "http_status": response.status_code,
            "latency_ms": int((time.monotonic() - start) * 1000),
            "bytes": len(response.content),
            "content_type": response.headers.get("content-type", ""),
        }

    def trust_factor(self) -> dict[str, Any]:
        receipts = self.store.list_receipts(200)
        decisions = [
            item["receipt"]["payload"].get("decision")
            for item in receipts
            if item["kind"] == "passport.evaluate"
        ]
        counts = {name: decisions.count(name) for name in ("ALLOW", "BLOCK", "REQUIRE_APPROVAL")}
        total = sum(counts.values())
        penalty = counts["BLOCK"] * 10 + counts["REQUIRE_APPROVAL"] * 3
        score = 100 if total == 0 else max(0, 100 - (penalty * 100 // max(1, total * 10)))
        return {
            "schema": SCHEMA_TRUST,
            "state": "OBSERVED",
            "total_evaluations": total,
            "counts": counts,
            "score_0_to_100": score,
            "basis": "local signed passport decision receipts",
            "not_a_security_certification": True,
        }


async def _bounded_json(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="content-type must be application/json")
    declared = request.headers.get("content-length")
    if declared:
        try:
            if int(declared) > MAX_BODY:
                raise HTTPException(status_code=413, detail="request exceeds 64 KiB")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid content-length") from exc
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(status_code=413, detail="request exceeds 64 KiB")
    try:
        value = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="request must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail="request must be one JSON object")
    return value


def _asset_bytes(name: str) -> bytes:
    path = Path(__file__).resolve().parent / "series_a_web" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"asset missing: {name}")
    return path.read_bytes()


def _asset(name: str) -> str:
    return _asset_bytes(name).decode("utf-8")


def _asset_digest(name: str) -> str:
    return hashlib.sha256(_asset_bytes(name)).hexdigest()


async def start_registered_service(app: FastAPI) -> dict[str, Any]:
    """Start the registered controller from the canonical application lifecycle."""

    service = getattr(app.state, "szl_series_a_service", None)
    if not isinstance(service, Service):
        return {
            "state": "UNAVAILABLE",
            "reason": "Series-A service is not registered",
        }
    await service.start()
    return {
        "state": "RUNNING" if service.scheduler_status()["task_running"] else "DISABLED",
        **service.scheduler_status(),
    }


def _event_cursor(request: Request) -> int:
    raw = request.headers.get("last-event-id")
    if raw is None:
        raw = request.query_params.get("after", "0")
    try:
        cursor = int(raw or 0)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="event cursor must be an integer") from exc
    if cursor < 0 or cursor > 9_223_372_036_854_775_807:
        raise HTTPException(status_code=400, detail="event cursor is outside the supported range")
    return cursor


def _receipt_limit(request: Request) -> int:
    values = request.query_params.getlist("limit")
    if len(values) > 1:
        raise HTTPException(
            status_code=400,
            detail="receipt limit must be supplied at most once",
        )
    raw = values[0] if values else "50"
    try:
        limit = int(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="receipt limit must be an integer",
        ) from exc
    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=422,
            detail="receipt limit must be between 1 and 200",
        )
    return limit


def _asset_cache_control(request: Request, content: bytes) -> str:
    if request.query_params.get("v") == hashlib.sha256(content).hexdigest():
        return "public,max-age=31536000,immutable"
    return "no-store"


def register(app: FastAPI, ns: str = "a11oy", *, db_path: str | None = None) -> dict[str, Any]:
    if any(getattr(route, "path", None) == f"/api/{ns}/v1/series-a/status" for route in app.router.routes):
        return {"ok": True, "state": "ALREADY_REGISTERED", "routes": []}

    service = Service(db_path)
    prefix = f"/api/{ns}/v1/series-a"

    async def page(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(status_code=200, media_type="text/html")
        html = (
            _asset("index.html")
            .replace("__APP_ASSET_DIGEST__", _asset_digest("app.js"))
            .replace("__STYLE_ASSET_DIGEST__", _asset_digest("styles.css"))
        )
        return HTMLResponse(html, headers={"cache-control": "no-store"})

    async def js(request: Request) -> Response:
        content = _asset_bytes("app.js")
        headers = {"cache-control": _asset_cache_control(request, content)}
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="application/javascript",
                headers=headers,
            )
        return Response(
            content,
            media_type="application/javascript",
            headers=headers,
        )

    async def css(request: Request) -> Response:
        content = _asset_bytes("styles.css")
        headers = {"cache-control": _asset_cache_control(request, content)}
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="text/css",
                headers=headers,
            )
        return Response(
            content,
            media_type="text/css",
            headers=headers,
        )

    async def status(request: Request) -> Response:
        payload = service.latest_status()
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        return JSONResponse(payload, headers={"cache-control": "no-store"})

    async def manifest(request: Request) -> Response:
        latest = service.store.latest_snapshot()
        if latest is None:
            payload = {"schema": SCHEMA_MANIFEST, "status": "PENDING", "terminal": True}
        else:
            payload = latest
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        return JSONResponse(payload, headers={"cache-control": "no-store"})

    async def refresh(request: Request) -> Response:
        await _bounded_json(request)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DIRECT_REFRESH_DISABLED",
                "required_flow": [
                    f"{prefix}/passports/evaluate",
                    f"{prefix}/passports/execute",
                ],
            },
        )

    async def evaluate(request: Request) -> Response:
        return JSONResponse(service.evaluate_passport(await _bounded_json(request)))

    async def execute(request: Request) -> Response:
        return JSONResponse(await service.execute(await _bounded_json(request)))

    async def passport_outcome(request: Request) -> Response:
        digest = str(request.path_params.get("passport_digest") or "").lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise HTTPException(
                status_code=422,
                detail="passport digest must be 64 lowercase hex characters",
            )
        value = service.store.outcome_for_passport(digest)
        if value is None:
            raise HTTPException(
                status_code=404,
                detail="passport outcome not persisted yet",
            )
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        return JSONResponse(value, headers={"cache-control": "no-store"})

    async def exact_receipt_response(request: Request, digest: str) -> Response:
        if len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            raise HTTPException(
                status_code=422,
                detail="receipt hash must be 64 lowercase hex characters",
            )
        storage, item = service.store.receipt_recovery_snapshot(digest)
        if item is None:
            return JSONResponse(
                {
                    "schema": "szl.series-a-receipt-recovery-miss/v1",
                    "source_revision": _git_revision(),
                    "runtime_boot_id": service.runtime_boot_id,
                    "database": service.store.path,
                    "storage": storage,
                    "queried_receipt_hash": digest,
                    "item": None,
                },
                status_code=404,
                headers={"cache-control": "no-store"},
            )
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="application/json",
                headers={"cache-control": "no-store"},
            )
        public_key = (service.signer.public_pem or "").encode("utf-8")
        return JSONResponse(
            {
                "schema": "szl.series-a-receipt-recovery/v1",
                "source_revision": _git_revision(),
                "runtime_boot_id": service.runtime_boot_id,
                "signing_key_source": service.signer.source,
                "public_key_sha256": hashlib.sha256(public_key).hexdigest(),
                "database": service.store.path,
                "storage": storage,
                "item": item,
            },
            headers={"cache-control": "no-store"},
        )

    async def receipts(request: Request) -> Response:
        receipt_hashes = request.query_params.getlist("receipt_hash")
        if receipt_hashes:
            if len(receipt_hashes) != 1:
                raise HTTPException(
                    status_code=400,
                    detail="receipt_hash must be supplied at most once",
                )
            if request.query_params.getlist("limit"):
                raise HTTPException(
                    status_code=400,
                    detail="receipt_hash cannot be combined with limit",
                )
            return await exact_receipt_response(request, receipt_hashes[0])

        limit = _receipt_limit(request)
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="application/json",
                headers={"cache-control": "no-store"},
            )
        return JSONResponse(
            {
                "schema": "szl.series-a-receipts/v1",
                "limit": limit,
                "items": service.store.list_receipts(limit),
            },
            headers={"cache-control": "no-store"},
        )

    async def receipt_recovery(request: Request) -> Response:
        digest = str(request.path_params.get("receipt_hash") or "")
        return await exact_receipt_response(request, digest)

    async def trust(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        return JSONResponse(service.trust_factor())

    async def public_key(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="text/plain",
                headers={"cache-control": "no-store"},
            )
        if not service.signer.public_pem:
            return JSONResponse(
                {"state": "UNAVAILABLE", "reason": service.signer.error},
                status_code=503,
                headers={"cache-control": "no-store"},
            )
        return Response(
            service.signer.public_pem,
            media_type="text/plain",
            headers={"cache-control": "no-store"},
        )

    async def events(request: Request) -> StreamingResponse:
        last = _event_cursor(request)

        async def generate() -> AsyncIterator[bytes]:
            cursor = max(0, last)
            for _ in range(120):
                values = service.store.events_since(cursor)
                for event in values:
                    cursor = event["sequence"]
                    yield f"id: {cursor}\nevent: {event['kind']}\ndata: {json.dumps(event, separators=(',', ':'))}\n\n".encode()
                if await request.is_disconnected():
                    break
                yield b": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(generate(), media_type="text/event-stream", headers={"cache-control": "no-store"})

    routes: list[tuple[str, Callable[..., Any], list[str]]] = [
        ("/series-a", page, ["GET", "HEAD"]),
        ("/series-a/app.js", js, ["GET", "HEAD"]),
        ("/series-a/styles.css", css, ["GET", "HEAD"]),
        (f"{prefix}/status", status, ["GET", "HEAD"]),
        (f"{prefix}/manifest", manifest, ["GET", "HEAD"]),
        (f"{prefix}/refresh", refresh, ["POST"]),
        (f"{prefix}/passports/evaluate", evaluate, ["POST"]),
        (f"{prefix}/passports/execute", execute, ["POST"]),
        (
            f"{prefix}/passports/outcomes/{{passport_digest}}",
            passport_outcome,
            ["GET", "HEAD"],
        ),
        (f"{prefix}/receipts", receipts, ["GET", "HEAD"]),
        (
            f"{prefix}/receipts/{{receipt_hash}}",
            receipt_recovery,
            ["GET", "HEAD"],
        ),
        (f"{prefix}/trust", trust, ["GET", "HEAD"]),
        (f"{prefix}/public-key", public_key, ["GET", "HEAD"]),
        (f"{prefix}/events", events, ["GET"]),
    ]
    added: list[str] = []
    for path, endpoint, methods in routes:
        app.add_api_route(path, endpoint, methods=methods, include_in_schema=False)
        added.append(path)

    route_set = set(added)
    selected = [route for route in app.router.routes if getattr(route, "path", None) in route_set]
    selected_ids = {id(route) for route in selected}
    app.router.routes[:] = selected + [route for route in app.router.routes if id(route) not in selected_ids]

    app.state.szl_series_a_service = service
    add_handler = getattr(app, "add_event_handler", None)
    if callable(add_handler):
        add_handler("startup", service.start)
        add_handler("shutdown", service.stop)

    return {
        "ok": True,
        "state": "REGISTERED",
        "namespace": ns,
        "routes": sorted(added),
        "database": service.store.path,
        "storage": service.store.storage_status(),
        "signing_key_source": service.signer.source,
        "sign_on_read": False,
        "effectors": sorted(ALLOWED_ACTIONS),
        "max_attempts": 1,
        "private_reasoning_collected": False,
    }
