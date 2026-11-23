"""Exercise the online SQLite backup with an uncheckpointed WAL commit."""
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from a11oy_state_store import sqlite_backup, verify_sqlite

def require(predicate, detail):
    if not predicate:
        raise RuntimeError(detail)


def read_rows(db):
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as c:
        return c.execute("SELECT op,task FROM receipt ORDER BY op").fetchall()


def test_committed_wal_snapshot_restores_exactly(tmp_path):
    folder = tmp_path
    source, snapshot, restored, negative = (folder / name for name in
                                            ("live.db", "snapshot.db", "restored.db", "negative.db"))
    with closing(sqlite3.connect(source)) as c:
        require(c.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal", "WAL unavailable")
        c.execute("PRAGMA wal_autocheckpoint=0")
        c.execute("PRAGMA foreign_keys=ON")
        c.executescript("CREATE TABLE task(id INTEGER PRIMARY KEY);"
                        "CREATE TABLE receipt(op TEXT PRIMARY KEY, task INTEGER NOT NULL REFERENCES task(id));")
        with c:
            c.execute("INSERT INTO task VALUES(1)")
            c.execute("INSERT INTO receipt VALUES('commit-one',1)")
        try:
            with c:
                c.execute("INSERT INTO receipt VALUES('rolled-back',1)")
                raise ValueError("synthetic cancellation")
        except ValueError:
            pass
        with c:
            duplicate = c.execute("INSERT INTO receipt VALUES('commit-one',1) ON CONFLICT(op) DO NOTHING")
            require(duplicate.rowcount == 0, "duplicate accepted")
        require(source.with_name(source.name + "-wal").stat().st_size > 0,
                "test did not retain a WAL")
        guard = verify_sqlite(source, full=True)
        require(guard["ok"] and guard["logical_sha256"], "source integrity missing")
        sqlite_backup(source, snapshot)
    snap = verify_sqlite(snapshot, full=True)
    require(snap["ok"] and snap["logical_sha256"] == guard["logical_sha256"], "snapshot differs")
    shutil.copyfile(snapshot, restored)
    reopen = verify_sqlite(restored, full=True)
    require(reopen["ok"] and reopen["logical_sha256"] == guard["logical_sha256"], "restore digest differs")
    require(read_rows(restored) == [("commit-one", 1)], "restore rows mismatch")
    shutil.copyfile(snapshot, negative)
    with closing(sqlite3.connect(negative)) as c:
        c.execute("PRAGMA foreign_keys=OFF")
        with c:
            c.execute("INSERT INTO receipt VALUES('missing-parent',999)")
    bad = verify_sqlite(negative, full=True)
    require(not bad["ok"] and bad["foreign_key_violations"] == 1, "foreign key defect accepted")
