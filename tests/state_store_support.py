#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline fakes for the a11oy state store: CAS dataset, clock, replicas."""

import sqlite3
from pathlib import Path
from typing import Callable, Optional

import a11oy_state_store as ss
import gdw_sqlite_repair


class FakeHeadBackend:
    """In-memory dataset with create_commit(parent_commit=...) semantics."""

    def __init__(self):
        self.commits: list[tuple[str, Optional[bytes]]] = [(self._rev(1), None)]
        self.fail_next_submit: Optional[str] = None
        self.unreachable = False
        self.submits = 0
        self.before_submit: Optional[Callable[[], None]] = None

    @staticmethod
    def _rev(number: int) -> str:
        return f"{number:040x}"

    def _append(self, body: Optional[bytes]) -> str:
        revision = self._rev(len(self.commits) + 1)
        self.commits.append((revision, body))
        return revision

    def unrelated_commit(self) -> None:
        """Another automation commit: new revision, same HEAD bytes."""
        self._append(self.commits[-1][1])

    def observe(self) -> ss.Observation:
        if self.unreachable:
            raise ss.StorageBlocked("STATE_DATASET_UNREACHABLE")
        revision, body = self.commits[-1]
        return ss.Observation(revision, body)

    def read_at(self, revision: str) -> Optional[bytes]:
        for known, body in self.commits:
            if known == revision:
                return body
        raise ss.StorageBlocked("STATE_HEAD_UNREADABLE")

    def submit(self, parent: str, body: bytes, operation_id: str) -> str:
        self.submits += 1
        if self.before_submit is not None:
            hook, self.before_submit = self.before_submit, None
            hook()
        if parent != self.commits[-1][0]:
            raise ss.ParentConflict()
        mode, self.fail_next_submit = self.fail_next_submit, None
        if mode == "uncertain_lost":
            raise ss.StorageBlocked("STATE_HEAD_OUTCOME_UNCERTAIN")
        revision = self._append(body)
        if mode == "uncertain_landed":
            raise ss.StorageBlocked("STATE_HEAD_OUTCOME_UNCERTAIN")
        return revision

    def head(self) -> dict:
        return ss.parse_head(self.commits[-1][1])


class FakeClock:
    def __init__(self, start: float = 1_790_000_000.0):
        self.now = start
        self.on_sleep: list[Callable[[], None]] = []

    def time(self) -> float:
        return self.now

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        for hook in list(self.on_sleep):
            hook()

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _local_root(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def replica(tmp_path: Path, name: str, objects, backend, clock: FakeClock,
            environ: Optional[dict] = None, **overrides) -> ss.StateStore:
    values = dict(root=tmp_path / name / "state", bucket="TEST/bucket", dataset="TEST/state",
                  legacy_root=tmp_path / "legacy", poll_s=3.0, stale_s=120.0, heartbeat_s=15.0,
                  debounce_s=30.0, periodic_s=300.0, boot_deadline_s=600.0, drain_s=1.0)
    values.update(overrides)
    return ss.StateStore(settings=ss.Settings(**values), objects=objects, head_backend=backend,
                         environ=environ or {}, clock=clock.time, monotonic=clock.monotonic,
                         sleep=clock.sleep, local_root_check=_local_root,
                         source_revision="a" * 40)


def make_db(path: Path, rows: int, *, start: int = 0) -> None:
    """Parent/child tables with a foreign key, in DELETE journal mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS owners(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS receipts(
              id INTEGER PRIMARY KEY,
              owner_id INTEGER NOT NULL REFERENCES owners(id),
              body TEXT NOT NULL);
            """
        )
        connection.execute("INSERT OR IGNORE INTO owners(id, name) VALUES(1, 'a11oy')")
        connection.executemany(
            "INSERT INTO receipts(id, owner_id, body) VALUES(?, 1, ?)",
            [(start + index, f"receipt-{start + index}") for index in range(rows)])
        connection.commit()
    finally:
        connection.close()


def count(path: Path) -> int:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return connection.execute("SELECT count(*) FROM receipts").fetchone()[0]
    finally:
        connection.close()


def fingerprint(path: Path) -> str:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return gdw_sqlite_repair.logical_fingerprint(connection)["sha256"]
    finally:
        connection.close()
