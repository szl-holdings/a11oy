# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Owning-route native receipts in the existing registered Series-A SQLite store.

The observer never constructs this readback from a submitted response. Actual
native producers call the two fixed write methods after their existing signer.
Outside an observer-owned reserved scope those callbacks are inert.
"""
from contextlib import closing, contextmanager
from contextvars import ContextVar
from pathlib import Path
import sqlite3

import a11oy_state_store as state_store
from routers.series_a_control_plane import Service, Store, _git_revision
from tools import execution_acceptance as a
from observer_adapters import HOOK_SCHEMA, READBACK_SCHEMA, native_receipt


class NativeReadbackBlocked(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise NativeReadbackBlocked(code)


class NativeReadbacks:
    schema = HOOK_SCHEMA

    def __init__(self, service, runtime_public_key, runtime_key_id):
        require(isinstance(service, Service), "NATIVE_SERIES_A_SERVICE_REQUIRED")
        self.service = service
        self.key = a.public_key(runtime_public_key, runtime_key_id)
        self.key_id = runtime_key_id
        self._scope = ContextVar("szl_native_execution_readback_scope", default=None)

    @contextmanager
    def case_scope(self, run_nonce, case_id):
        """Internal trusted dispatch scope, never exposed as route parameters."""
        require(type(run_nonce) is str and a.HEX64.fullmatch(run_nonce)
                and case_id in a.CONTRACTS, "INVALID_NATIVE_RECORDING_SCOPE")
        require(self._scope.get() is None, "NATIVE_RECORDING_SCOPE_ALREADY_ACTIVE")
        token = self._scope.set((run_nonce, case_id))
        try:
            yield
        finally:
            self._scope.reset(token)

    def record_eval(self, receipt):
        return self._record("eval-run", receipt)

    def record_agentloop(self, receipt):
        return self._record("agentloop-run", receipt)

    def _record(self, native_kind, receipt):
        scope = self._scope.get()
        if scope is None:
            return None
        nonce, parent_case = scope
        allowed = {"eval-run": {"eval-run"}, "agentloop-run": {"eval-run", "agentloop-run"}}
        require(native_kind in allowed.get(parent_case, set()), "NATIVE_RECORDING_SCOPE_MISMATCH")
        require(type(receipt) is dict and set(receipt) == {"body", "dsse", "signing"},
                "NATIVE_FULL_RECEIPT_REQUIRED")
        # Freeze caller-owned objects before verification or persistence.
        frozen = a.strict_json(a.canonical(receipt))
        signed, digest = native_receipt(frozen, self.key, self.key_id)
        expected_schema = {"eval-run": "szl.eval_arena.receipt/v1",
                           "agentloop-run": "szl.agentloop.receipt/v1"}[native_kind]
        require(signed.get("schema") == expected_schema, "NATIVE_RECEIPT_SCHEMA_MISMATCH")
        value = {"schema": READBACK_SCHEMA, "case_id": native_kind,
                 "payload_sha256": digest, "receipt": frozen}
        raw = a.canonical(value)
        require(len(raw) <= a.MAX_BODY, "NATIVE_READBACK_TOO_LARGE")
        manager = state_store.active()
        require(isinstance(manager, state_store.StateStore)
                and manager.source_revision == _git_revision()
                and Path(self.service.store.path).resolve() == manager.local_path("series_a").resolve(),
                "NATIVE_REGISTERED_STATE_REQUIRED")
        require(manager.begin_write(), "NATIVE_WRITER_UNAVAILABLE")
        try:
            manager.confirmed_writer()
            with self.service.store.lock, closing(self.service.store.connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("""SELECT p.source_revision,p.runtime_boot_id,o.state
                    FROM execution_observation_plans p JOIN execution_observations o
                    ON p.run_nonce=o.run_nonce WHERE p.run_nonce=? AND o.case_id=?""",
                    (nonce, parent_case)).fetchone()
                require(row is not None and tuple(row) ==
                        (manager.source_revision, self.service.runtime_boot_id, "RESERVED"),
                        "NATIVE_RESERVATION_REQUIRED")
                db.execute("""CREATE TABLE IF NOT EXISTS execution_native_receipts(
                    native_kind TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
                    readback_json TEXT NOT NULL, readback_sha256 TEXT NOT NULL,
                    PRIMARY KEY(native_kind,payload_sha256))""")
                db.execute("""CREATE TABLE IF NOT EXISTS execution_native_links(
                    run_nonce TEXT NOT NULL, parent_case TEXT NOT NULL,
                    native_kind TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
                    PRIMARY KEY(run_nonce,parent_case,native_kind),
                    FOREIGN KEY(run_nonce,parent_case) REFERENCES execution_observations(run_nonce,case_id),
                    FOREIGN KEY(native_kind,payload_sha256)
                        REFERENCES execution_native_receipts(native_kind,payload_sha256))""")
                db.execute("INSERT OR IGNORE INTO execution_native_receipts VALUES(?,?,?,?)",
                    (native_kind, digest, raw.decode(), a.digest(raw)))
                stored = db.execute("SELECT readback_json,readback_sha256 FROM execution_native_receipts "
                                    "WHERE native_kind=? AND payload_sha256=?", (native_kind, digest)).fetchone()
                require(tuple(stored) == (raw.decode(), a.digest(raw)), "NATIVE_RECEIPT_ALREADY_BOUND")
                try:
                    db.execute("INSERT INTO execution_native_links VALUES(?,?,?,?)",
                               (nonce, parent_case, native_kind, digest))
                except sqlite3.IntegrityError:
                    raise NativeReadbackBlocked("NATIVE_RECEIPT_ATTEMPT_ALREADY_CONSUMED") from None
        finally:
            manager.end_write()
        return {"state": "LOCAL_NATIVE_RECEIPT_RECORDED", "payload_sha256": digest,
                "durability_acknowledged": False}

    @staticmethod
    def _connect_readonly(path):
        return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)

    def read_eval(self, payload_sha256):
        return self._read("eval-run", payload_sha256)

    def read_agentloop(self, payload_sha256):
        return self._read("agentloop-run", payload_sha256)

    def _read(self, kind, digest):
        require(type(digest) is str and a.HEX64.fullmatch(digest), "NATIVE_PAYLOAD_DIGEST_REQUIRED")
        with closing(self._connect_readonly(self.service.store.path)) as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                "AND name='execution_native_receipts'").fetchone()
            require(exists is not None, "NATIVE_RECEIPT_UNAVAILABLE")
            row = db.execute("SELECT readback_json,readback_sha256 FROM execution_native_receipts "
                             "WHERE native_kind=? AND payload_sha256=?", (kind, digest)).fetchone()
        require(row is not None, "NATIVE_RECEIPT_UNAVAILABLE")
        raw = row[0].encode()
        require(len(raw) <= a.MAX_BODY and a.digest(raw) == row[1], "NATIVE_READBACK_CORRUPT")
        value = a.strict_json(raw)
        _, measured = native_receipt(value["receipt"], self.key, self.key_id)
        require(value["case_id"] == kind and measured == digest == value["payload_sha256"],
                "NATIVE_READBACK_BINDING_MISMATCH")
        return raw

    @classmethod
    def _linked_rows(cls, path, nonce, case_id):
        with closing(cls._connect_readonly(path)) as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                "AND name='execution_native_links'").fetchone()
            if exists is None:
                return []
            return db.execute("""SELECT l.run_nonce,l.parent_case,l.native_kind,l.payload_sha256,
                r.readback_json,r.readback_sha256 FROM execution_native_links l
                JOIN execution_native_receipts r ON r.native_kind=l.native_kind
                AND r.payload_sha256=l.payload_sha256 WHERE l.run_nonce=? AND l.parent_case=?
                ORDER BY l.native_kind""", (nonce, case_id)).fetchall()

    def snapshot_predicate(self, observation_rows):
        """Freeze exact owning native rows before downloading immutable storage.

        Reserved rows intentionally have no expected native result yet. Completed
        model observations require their own native receipts plus nested eval.
        Returned predicate only reads the caller-selected registered snapshot.
        """
        expected = []
        kinds = {"eval-run": {"eval-run"}, "agentloop-run": {"eval-run", "agentloop-run"}}
        for row in observation_rows:
            if row["state"] != "COMPLETED" or row["case_id"] not in kinds:
                continue
            native = self._linked_rows(self.service.store.path, row["run_nonce"], row["case_id"])
            require({item[2] for item in native} == kinds[row["case_id"]]
                    and len(native) == len(kinds[row["case_id"]]), "NATIVE_COMPLETION_READBACK_REQUIRED")
            observation = a.strict_json(row["observation_json"].encode())
            readback = a.strict_json(a.decode(observation["readback_b64"]))
            expected_readbacks = ({"eval-run": readback} if row["case_id"] == "eval-run" else
                                 {"eval-run": readback["eval_record"], "agentloop-run": readback["record"]})
            for item in native:
                require(a.digest(item[4].encode()) == item[5]
                        and item[4].encode() == a.canonical(expected_readbacks[item[2]]),
                        "NATIVE_READBACK_CORRUPT")
            expected.append((row["run_nonce"], row["case_id"], native))
        return lambda path: all(self._linked_rows(path, nonce, case_id) == native
                                for nonce, case_id, native in expected)
