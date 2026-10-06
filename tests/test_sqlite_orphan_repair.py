"""Orphan-page-only SQLite auto-repair: preserves data and the original, refuses
everything else.

Orphan pages are produced deterministically: free pages are created by deleting
rows, then the header freelist pointer (offset 32) and count (offset 36) are
zeroed so those pages are referenced by nothing. SQLite then reports exactly
"Page N: never used" for each, which is the 2026-10-04 incident's shape.
"""

import hashlib
import json
import os
import sqlite3
import struct
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
    [(None, True), ("", True), ("1", True), ("on", True), ("0", False),
     ("false", False), ("OFF", False), ("no", False)],
)
def test_auto_repair_flag_defaults_on(value, expected):
    environ = {} if value is None else {repair.AUTO_REPAIR_ENV: value}
    assert repair.auto_repair_enabled(environ) is expected


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


def test_prepare_runtime_auto_repairs_orphan_pages_and_stays_ready(monkeypatch, tmp_path):
    first, database, healthy = _orphan_gdw_store(monkeypatch, tmp_path)
    damaged_sha = _sha(database)

    observed = gdw_runtime.prepare_runtime()

    assert observed["sqlite_integrity"] == "ok"
    assert observed["database_generation_id"] == first["database_generation_id"]
    summary = observed["orphan_page_repair"]
    assert summary["status"] == "APPLIED"
    assert summary["original_sha256"] == damaged_sha
    assert summary["logical_sha256"] == healthy["sha256"]
    assert Path(summary["preserved_path"]).is_file()
    assert _sha(Path(summary["preserved_path"])) == damaged_sha
    health = gdw_runtime.runtime_health()
    assert health["startup_state"] == "READY"
    assert health["storage_repair"]["receipt_path"] == summary["receipt_path"]


def test_prepare_runtime_refuses_orphan_pages_when_auto_repair_disabled(monkeypatch, tmp_path):
    _first, database, _healthy = _orphan_gdw_store(monkeypatch, tmp_path)
    monkeypatch.setenv(repair.AUTO_REPAIR_ENV, "0")
    before = database.read_bytes()

    with pytest.raises(gdw_runtime.GDWRuntimeError, match="auto-repair|AUTO_REPAIR"):
        gdw_runtime.prepare_runtime()

    assert database.read_bytes() == before
    assert not list(database.parent.glob("*.orphan-pages-*"))


def test_prepare_runtime_refuses_other_corruption_before_any_writer_opens(monkeypatch, tmp_path):
    _persistent_environment(monkeypatch, tmp_path)
    first = gdw_runtime.prepare_runtime()
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
