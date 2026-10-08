"""Orphan-page-only SQLite repair: preserves data and the original, refuses
everything it cannot prove safe.

Repairable orphan pages are produced deterministically: free pages are created
by deleting rows, then the header freelist pointer (offset 32) and count
(offset 36) are zeroed so those pages are referenced by nothing. SQLite then
reports exactly "Page N: never used" for each. The same report is produced when
a lost parent-page update strands committed rows (the reverted-parent fixture
below); that shape must be refused, never "repaired" into data loss.
"""

import hashlib
import json
import os
import sqlite3
import struct
import subprocess
import sys
from pathlib import Path

import pytest

import gdw_runtime
import gdw_sqlite_repair as repair


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _populate(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        CREATE TABLE owners(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE receipts(
          id INTEGER PRIMARY KEY,
          owner_id INTEGER NOT NULL REFERENCES owners(id),
          amount REAL,
          body BLOB,
          note TEXT
        );
        CREATE INDEX receipts_owner ON receipts(owner_id);
        CREATE TABLE kv(k TEXT PRIMARY KEY, v TEXT) WITHOUT ROWID;
        CREATE TABLE junk(id INTEGER PRIMARY KEY, payload BLOB);
        PRAGMA user_version=7;
        """
    )
    connection.executemany(
        "INSERT INTO owners(id, name) VALUES(?, ?)",
        [(i, f"owner-{i}") for i in range(1, 6)],
    )
    connection.executemany(
        "INSERT INTO receipts(owner_id, amount, body, note) VALUES(?,?,?,?)",
        [
            (1 + i % 5, i / 3.0, bytes([i % 256]) * 40, None if i % 4 else "n")
            for i in range(200)
        ],
    )
    connection.executemany(
        "INSERT INTO kv(k, v) VALUES(?, ?)",
        [(f"key-{i:03d}", "v" * (i % 17)) for i in range(60)],
    )
    connection.executemany(
        "INSERT INTO junk(payload) VALUES(?)",
        [(os.urandom(3000),) for _ in range(24)],
    )
    connection.commit()
    connection.execute("DELETE FROM junk")
    connection.commit()
    assert connection.execute("PRAGMA freelist_count").fetchone()[0] > 0
    connection.close()


def _orphan_free_pages(path: Path, *, keep_count: bool = False) -> None:
    """Unlink every freelist page: they become 'Page N: never used'."""

    data = bytearray(Path(path).read_bytes())
    data[32:36] = b"\x00" * 4  # first freelist trunk page
    if not keep_count:
        data[36:40] = b"\x00" * 4  # freelist page count
    Path(path).write_bytes(bytes(data))


def _fingerprint(path: Path) -> dict:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return repair.logical_fingerprint(connection)
    finally:
        connection.close()


def _integrity(path: Path) -> list:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return repair.integrity_lines(connection)
    finally:
        connection.close()


def _reverted_parent_store(path: Path) -> dict:
    """Committed rows stranded by a stale parent page: 'never used' only.

    Commit a table whose root is an interior page, snapshot that root, commit
    an append that allocates new leaves, then write the stale root back (a lost
    or torn parent update). The new leaves hold acknowledged rows that are now
    unreachable, and integrity_check reports only 'Page N: never used'.
    """

    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute("CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY, body TEXT)")
    connection.executemany(
        "INSERT INTO ledger(body) VALUES(?)", [("r" * 300,) for _ in range(40)]
    )
    connection.commit()
    root = connection.execute(
        "SELECT rootpage FROM sqlite_master WHERE name='ledger'"
    ).fetchone()[0]
    page_size = connection.execute("PRAGMA page_size").fetchone()[0]
    connection.close()
    data = Path(path).read_bytes()
    stale_root = data[(root - 1) * page_size:root * page_size]
    assert stale_root[0] == 0x05, "fixture needs an interior table root"

    connection = sqlite3.connect(path)
    connection.executemany(
        "INSERT INTO ledger(body) VALUES(?)", [("n" * 300,) for _ in range(24)]
    )
    connection.commit()
    acknowledged = connection.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    connection.close()

    data = bytearray(Path(path).read_bytes())
    data[(root - 1) * page_size:root * page_size] = stale_root
    Path(path).write_bytes(bytes(data))
    lines = _integrity(path)
    pages = repair.classify_orphan_pages(lines)
    assert pages, lines
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        reachable = connection.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    finally:
        connection.close()
    assert reachable < acknowledged
    return {"pages": pages, "acknowledged": acknowledged, "reachable": reachable}


@pytest.fixture
def orphan_store(tmp_path):
    database = tmp_path / "store" / "gdw.sqlite3"
    database.parent.mkdir()
    _populate(database)
    healthy_fingerprint = _fingerprint(database)
    _orphan_free_pages(database)
    return database, healthy_fingerprint


def test_fixture_reproduces_orphan_page_only_damage(orphan_store):
    database, healthy = orphan_store
    lines = _integrity(database)
    assert lines[0] == repair.INTEGRITY_HEADER
    assert all(line.endswith(": never used") for line in lines[1:])
    assert repair.classify_orphan_pages(lines) == sorted(
        int(line.split()[1].rstrip(":")) for line in lines[1:]
    )
    # The damage is physical only: every row is still reachable.
    assert _fingerprint(database) == healthy


@pytest.mark.parametrize(
    "lines",
    [
        ["ok"],
        [],
        [repair.INTEGRITY_HEADER],
        ["Page 4: never used"],
        ["*** in database temp ***", "Page 4: never used"],
        [repair.INTEGRITY_HEADER, "Page 4: never used", "row 3 missing from index i"],
        [repair.INTEGRITY_HEADER, "Freelist: size is 0 but should be 3", "Page 4: never used"],
        [repair.INTEGRITY_HEADER, "Page 4: never used", "Page 4: never used"],
        [repair.INTEGRITY_HEADER, "Page 0: never used"],
        [repair.INTEGRITY_HEADER, "Page 4 is never used"],
        [repair.INTEGRITY_HEADER, " Page 4: never used trailing"],
    ],
)
def test_classifier_rejects_everything_but_orphan_pages(lines):
    assert repair.classify_orphan_pages(lines) is None


def test_classifier_accepts_header_plus_never_used_lines():
    lines = [repair.INTEGRITY_HEADER, "Page 363: never used", "Page 362: never used"]
    assert repair.classify_orphan_pages(lines) == [362, 363]


def test_repair_preserves_logical_content_original_and_receipt(orphan_store, tmp_path):
    database, healthy = orphan_store
    original_bytes = database.read_bytes()
    original_sha = _sha(database)
    damaged_lines = _integrity(database)
    scratch = tmp_path / "local-scratch"

    receipt = repair.repair_orphan_pages(database, work_dir=scratch)

    # Live store is now clean and logically identical.
    assert _integrity(database) == ["ok"]
    assert _fingerprint(database) == healthy
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 7
        assert connection.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 200
    finally:
        connection.close()

    # The original is preserved byte-for-byte next to the store.
    preserved = Path(receipt["original"]["preserved_path"])
    assert preserved.parent == database.parent
    assert preserved.name.startswith(database.name + ".orphan-pages-")
    assert preserved.name.endswith(f".{original_sha[:12]}.sqlite3")
    assert preserved.read_bytes() == original_bytes

    # A durable receipt describes the swap.
    receipt_path = Path(receipt["receipt_path"])
    assert receipt_path == preserved.with_suffix(".json")
    on_disk = json.loads(receipt_path.read_text())
    assert on_disk == receipt
    assert on_disk["schema"] == "szl.gdw-orphan-page-restore/v1"
    assert on_disk["status"] == "APPLIED"
    assert on_disk["original"]["sha256"] == original_sha
    assert on_disk["original"]["size"] == len(original_bytes)
    assert on_disk["original"]["integrity"] == damaged_lines
    assert on_disk["candidate"]["sha256"] == _sha(database)
    assert on_disk["candidate"]["integrity"] == ["ok"]
    assert on_disk["logical_fingerprint"] == healthy
    assert on_disk["post_replace"]["logical_fingerprint_sha256"] == healthy["sha256"]
    assert on_disk["orphan_pages"] == repair.classify_orphan_pages(damaged_lines)
    assert on_disk["orphan_page_evidence"]["proof"] == "FORMER_FREELIST_CHAIN"
    assert on_disk["orphan_page_evidence"]["leaf_pages"] > 0

    # No staging or scratch residue; nothing was deleted except our temp files.
    assert not database.with_name(database.name + ".repair-tmp").exists()
    assert list(scratch.iterdir()) == []
    assert sorted(path.name for path in database.parent.iterdir()) == sorted(
        [database.name, preserved.name, receipt_path.name]
    )


def test_refuses_non_orphan_corruption_without_touching_anything(tmp_path):
    database = tmp_path / "store" / "gdw.sqlite3"
    database.parent.mkdir()
    _populate(database)
    _orphan_free_pages(database, keep_count=True)  # adds a "Freelist: size" error
    lines = _integrity(database)
    assert any(line.startswith("Freelist:") for line in lines)
    before = database.read_bytes()

    with pytest.raises(repair.OrphanRepairError) as raised:
        repair.repair_orphan_pages(database, work_dir=tmp_path / "scratch")

    assert raised.value.code == "NOT_ORPHAN_PAGE_ONLY"
    assert database.read_bytes() == before
    assert [path.name for path in database.parent.iterdir()] == [database.name]


def test_refuses_with_uncheckpointed_journal(orphan_store):
    database, _healthy = orphan_store
    before = database.read_bytes()
    database.with_name(database.name + "-journal").write_bytes(b"\x01" * 512)

    with pytest.raises(repair.OrphanRepairError) as raised:
        repair.repair_orphan_pages(database)

    assert raised.value.code == "UNCHECKPOINTED_SIDECAR_PRESENT"
    assert database.read_bytes() == before


def test_candidate_must_not_be_created_on_the_storage_mount(orphan_store):
    database, _healthy = orphan_store
    before = database.read_bytes()
    mount = database.parent.parent

    with pytest.raises(repair.OrphanRepairError) as raised:
        repair.repair_orphan_pages(
            database,
            work_dir=mount / "scratch-on-mount",
            forbidden_root=mount,
        )

    assert raised.value.code == "CANDIDATE_NOT_LOCAL"
    assert database.read_bytes() == before


def test_post_replace_failure_rolls_back_to_preserved_original(orphan_store, monkeypatch):
    database, healthy = orphan_store
    original_sha = _sha(database)
    real = repair.integrity_lines
    calls = []

    def failing_after_swap(connection, **kwargs):
        calls.append(1)
        if len(calls) == 3:  # original, candidate, then the swapped live store
            return [repair.INTEGRITY_HEADER, "row 1 missing from index receipts_owner"]
        return real(connection, **kwargs)

    monkeypatch.setattr(repair, "integrity_lines", failing_after_swap)

    with pytest.raises(repair.OrphanRepairError) as raised:
        repair.repair_orphan_pages(database)

    assert raised.value.code == "POST_REPLACE_VERIFICATION_FAILED"
    assert _sha(database) == original_sha
    assert _fingerprint(database) == healthy
    receipts = sorted(database.parent.glob("*.json"))
    assert len(receipts) == 1
    on_disk = json.loads(receipts[0].read_text())
    assert on_disk["status"] == "ROLLED_BACK"
    assert Path(on_disk["original"]["preserved_path"]).read_bytes() == database.read_bytes()


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, False), ("", False), ("1", True), ("on", True), ("TRUE", True),
     ("yes", True), ("0", False), ("false", False), ("OFF", False), ("no", False),
     ("maybe", False)],
)
def test_auto_repair_flag_defaults_off(value, expected):
    environ = {} if value is None else {repair.AUTO_REPAIR_ENV: value}
    assert repair.auto_repair_enabled(environ) is expected


def test_reverted_parent_page_is_refused_not_repaired(tmp_path):
    """Orphan-only output is not proof: stranded committed rows are refused."""

    database = tmp_path / "store" / "gdw.sqlite3"
    database.parent.mkdir()
    shape = _reverted_parent_store(database)
    before = database.read_bytes()

    with pytest.raises(repair.OrphanRepairError) as raised:
        repair.repair_orphan_pages(database, work_dir=tmp_path / "scratch")

    assert raised.value.code == "ORPHAN_PAGE_CONTENT_UNPROVEN"
    assert database.read_bytes() == before
    assert [path.name for path in database.parent.iterdir()] == [database.name]
    with pytest.raises(repair.OrphanRepairError):
        repair.orphan_page_evidence(database, shape["pages"])


def test_all_zero_orphan_pages_are_proven_and_repaired(orphan_store, tmp_path):
    database, healthy = orphan_store
    pages = repair.classify_orphan_pages(_integrity(database))
    page_size = 4096
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
    finally:
        connection.close()
    data = bytearray(database.read_bytes())
    for page in pages:
        data[(page - 1) * page_size:page * page_size] = b"\x00" * page_size
    database.write_bytes(bytes(data))
    assert repair.classify_orphan_pages(_integrity(database)) == pages

    receipt = repair.repair_orphan_pages(database, work_dir=tmp_path / "scratch")

    assert receipt["status"] == "APPLIED"
    assert receipt["orphan_page_evidence"]["proof"] == "ALL_ZERO"
    assert _integrity(database) == ["ok"]
    assert _fingerprint(database) == healthy


def test_same_host_writer_cannot_commit_between_preservation_and_swap(orphan_store, monkeypatch):
    database, healthy = orphan_store
    real_write = repair._write_json_durably
    attempts = []

    def concurrent_writer(path, payload):
        real_write(path, payload)
        if payload.get("status") == "PRESERVED_BEFORE_REPLACE" and not attempts:
            other = sqlite3.connect(database, timeout=0.2)
            try:
                other.execute("INSERT INTO owners(id, name) VALUES(999, 'late')")
                other.commit()
                attempts.append("COMMITTED")
            except sqlite3.OperationalError as exc:
                attempts.append(str(exc))
            finally:
                other.close()

    monkeypatch.setattr(repair, "_write_json_durably", concurrent_writer)

    receipt = repair.repair_orphan_pages(database)

    # The write was refused (never acknowledged), so nothing acknowledged is lost.
    assert attempts == ["database is locked"]
    assert receipt["status"] == "APPLIED"
    assert _fingerprint(database) == healthy


def test_original_changed_before_swap_aborts_and_keeps_the_live_store(orphan_store, monkeypatch):
    """A writer that ignores SQLite locks (another host on the mount) is caught."""

    database, _healthy = orphan_store
    real_write = repair._write_json_durably

    def foreign_commit(path, payload):
        real_write(path, payload)
        if payload.get("status") == "PRESERVED_BEFORE_REPLACE":
            with database.open("r+b") as stream:
                stream.seek(60)  # user_version: a header write by someone else
                stream.write(struct.pack(">I", 8))

    monkeypatch.setattr(repair, "_write_json_durably", foreign_commit)

    with pytest.raises(repair.OrphanRepairError) as raised:
        repair.repair_orphan_pages(database)

    assert raised.value.code == "ORIGINAL_CHANGED_DURING_REPAIR"
    assert struct.unpack(">I", database.read_bytes()[60:64])[0] == 8  # not swapped
    receipts = sorted(database.parent.glob("*.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text())["status"] == "ABORTED_ORIGINAL_CHANGED"


# ---- prepare_runtime integration (legacy, non-durable path) ----------------
def _persistent_environment(monkeypatch, tmp_path):
    mount = tmp_path / "data"
    mount.mkdir()
    monkeypatch.setenv("GDW_DB_PATH", str(mount / "a11oy" / "gdw" / "gdw.sqlite3"))
    monkeypatch.setenv("GDW_PROOF_DIR", str(mount / "a11oy" / "gdw" / "proofs"))
    monkeypatch.setenv(
        "GDW_RECEIPT_PROJECTION_DIR", str(mount / "a11oy" / "gdw" / "receipts")
    )
    monkeypatch.setenv("GDW_REQUIRE_PERSISTENT_STORAGE", "1")
    monkeypatch.setenv("GDW_REQUIRED_MOUNT", str(mount))
    monkeypatch.setenv("GDW_SQLITE_JOURNAL", "DELETE")
    monkeypatch.setenv("GDW_SQLITE_SYNCHRONOUS", "FULL")
    monkeypatch.setenv("GDW_PROOF_EXPORT_MODE", "outbox")
    monkeypatch.delenv(repair.AUTO_REPAIR_ENV, raising=False)
    monkeypatch.setattr(gdw_runtime.os.path, "ismount", lambda _path: True)
    monkeypatch.setattr(
        gdw_runtime, "_STATE", json.loads(json.dumps(gdw_runtime._STATE))
    )
    return mount


def _orphan_gdw_store(monkeypatch, tmp_path):
    _persistent_environment(monkeypatch, tmp_path)
    first = gdw_runtime.prepare_runtime()
    database = Path(first["database_path"])
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE incident_filler(id INTEGER PRIMARY KEY, b BLOB)")
    connection.executemany(
        "INSERT INTO incident_filler(b) VALUES(?)",
        [(os.urandom(3000),) for _ in range(16)],
    )
    connection.commit()
    connection.execute("DELETE FROM incident_filler")
    connection.commit()
    assert connection.execute("PRAGMA freelist_count").fetchone()[0] > 0
    connection.close()
    healthy = _fingerprint(database)
    _orphan_free_pages(database)
    assert repair.classify_orphan_pages(_integrity(database))
    return first, database, healthy


def test_prepare_runtime_blocks_orphan_pages_without_replacing_live_store(monkeypatch, tmp_path):
    _first, database, _healthy = _orphan_gdw_store(monkeypatch, tmp_path)
    monkeypatch.setenv(repair.AUTO_REPAIR_ENV, "1")
    damaged_bytes = database.read_bytes()
    monkeypatch.setattr(
        repair,
        "repair_orphan_pages",
        lambda *_a, **_k: pytest.fail("runtime called unsafe live-file replacement"),
    )

    with pytest.raises(gdw_runtime.GDWRuntimeError, match="repair BLOCKED"):
        gdw_runtime.prepare_runtime()

    assert database.read_bytes() == damaged_bytes
    assert not list(database.parent.glob("*.orphan-pages-*"))


@pytest.mark.parametrize("flag", [None, "0"])
def test_prepare_runtime_without_opt_in_runs_the_pre_repair_path(monkeypatch, tmp_path, flag):
    """Default (and the kill switch) bypasses the whole repair gate."""

    _first, database, _healthy = _orphan_gdw_store(monkeypatch, tmp_path)
    if flag is not None:
        monkeypatch.setenv(repair.AUTO_REPAIR_ENV, flag)
    monkeypatch.setattr(
        repair, "inspect", lambda *_a, **_k: pytest.fail("gate ran without opt-in")
    )

    with pytest.raises(gdw_runtime.GDWRuntimeError, match="integrity check failed"):
        gdw_runtime.prepare_runtime()

    assert not list(database.parent.glob("*.orphan-pages-*"))
    assert repair.classify_orphan_pages(_integrity(database))


def test_prepare_runtime_refuses_stranded_rows_even_with_opt_in(monkeypatch, tmp_path):
    _persistent_environment(monkeypatch, tmp_path)
    first = gdw_runtime.prepare_runtime()
    database = Path(first["database_path"])
    _reverted_parent_store(database)
    monkeypatch.setenv(repair.AUTO_REPAIR_ENV, "1")
    before = database.read_bytes()

    with pytest.raises(gdw_runtime.GDWRuntimeError, match="repair BLOCKED") as raised:
        gdw_runtime.prepare_runtime()

    assert "writer quiescence" in str(raised.value)
    assert database.read_bytes() == before
    assert not list(database.parent.glob("*.orphan-pages-*"))


_CRASH_MID_TRANSACTION = """
import os, sqlite3, sys
connection = sqlite3.connect(sys.argv[1])
connection.execute("PRAGMA cache_size=5")
connection.execute("BEGIN")
connection.execute("UPDATE crash_filler SET b = randomblob(2000)")
connection.executemany(
    "INSERT INTO crash_filler(b) VALUES(?)", [(os.urandom(2000),) for _ in range(100)]
)
os._exit(0)  # killed mid-transaction: a hot -journal is left behind
"""


@pytest.mark.parametrize("flag", [None, "1"])
def test_hot_journal_after_crash_is_recovered_and_ready(monkeypatch, tmp_path, flag):
    _persistent_environment(monkeypatch, tmp_path)
    first = gdw_runtime.prepare_runtime()
    database = Path(first["database_path"])
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE crash_filler(id INTEGER PRIMARY KEY, b BLOB)")
    connection.executemany(
        "INSERT INTO crash_filler(b) VALUES(?)", [(os.urandom(2000),) for _ in range(200)]
    )
    connection.commit()
    connection.close()
    committed = _fingerprint(database)

    subprocess.run(
        [sys.executable, "-c", _CRASH_MID_TRANSACTION, str(database)], check=True
    )
    journal = database.with_name(database.name + "-journal")
    assert journal.is_file() and journal.stat().st_size > 0
    if flag is not None:
        monkeypatch.setenv(repair.AUTO_REPAIR_ENV, flag)
    monkeypatch.setattr(
        gdw_runtime, "_STATE", json.loads(json.dumps(gdw_runtime._STATE))
    )

    observed = gdw_runtime.prepare_runtime()

    assert observed["sqlite_integrity"] == "ok"
    assert gdw_runtime.runtime_health()["startup_state"] == "READY"
    assert not journal.exists() or journal.stat().st_size == 0
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        assert connection.execute("SELECT COUNT(*) FROM crash_filler").fetchone()[0] == 200
    finally:
        connection.close()
    assert observed["orphan_page_repair"] is None
    assert committed["tables"] == _fingerprint(database)["tables"]


def test_prepare_runtime_refuses_other_corruption_before_any_writer_opens(monkeypatch, tmp_path):
    _persistent_environment(monkeypatch, tmp_path)
    first = gdw_runtime.prepare_runtime()
    monkeypatch.setenv(repair.AUTO_REPAIR_ENV, "1")
    database = Path(first["database_path"])
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE incident_filler(id INTEGER PRIMARY KEY, b BLOB)")
    connection.executemany(
        "INSERT INTO incident_filler(b) VALUES(?)", [(os.urandom(3000),) for _ in range(8)]
    )
    connection.commit()
    connection.execute("DELETE FROM incident_filler")
    connection.commit()
    connection.close()
    _orphan_free_pages(database, keep_count=True)
    before = database.read_bytes()

    with pytest.raises(gdw_runtime.GDWRuntimeError, match="integrity check failed"):
        gdw_runtime.prepare_runtime()

    assert database.read_bytes() == before
    assert not list(database.parent.glob("*.orphan-pages-*"))
    assert struct.unpack(">I", before[36:40])[0] > 0
