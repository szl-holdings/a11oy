"""Experimental orphan-page repair helper for isolated SQLite stores.

``PRAGMA integrity_check`` reports ``Page N: never used`` for a page that no
b-tree and no freelist references. That alone does NOT prove nothing was lost:
if the update to a parent b-tree page is lost or torn (a stale page survives a
FUSE writeback, or two writers overlap), the newly allocated child pages carry
committed rows and are reported exactly the same way. A VACUUM copy keeps only
reachable rows, and a fingerprint over reachable rows is equal by construction,
so neither can detect that loss. This module therefore repairs only when the
orphan pages are positively proven to hold no live data, and nothing else:

1. classify the integrity output with a strict grammar (header line plus
   ``Page N: never used`` lines only); any other line is not repairable;
2. read every orphan page's raw bytes and require proof that it held no live
   data: every orphan page is all-zero, or the orphan set is exactly one
   well-formed former freelist chain (trunk pages linked to the end, every
   listed leaf itself an orphan page, at least one leaf, every page not in the
   chain all-zero). An orphan b-tree page with cells, an overflow page, or
   anything else unexplained is refused and left for an operator;
3. hold a SQLite write reservation (``BEGIN IMMEDIATE``) on the original and
   re-check its sha256 before replacement. This reservation does not protect
   the new inode after ``os.replace``; a second opener can write to that path
   while the reservation remains held. Cross-host writers need a separate
   exclusion proof;
4. open the original read-only and ``VACUUM INTO`` a candidate in a local temp
   directory (never on the storage mount); require candidate
   ``integrity_check == ok``, an empty ``foreign_key_check`` and a logical
   fingerprint equal to the original's;
5. preserve the original byte-for-byte next to the store
   (``<db>.orphan-pages-<utc>.<sha256[:12]>.sqlite3``) with a JSON receipt
   (schema ``szl.gdw-orphan-page-restore/v1``);
6. swap the candidate in through ``<db>.repair-tmp`` + fsync + ``os.replace``
   + directory fsync, then re-verify integrity and the fingerprint.

The runtime does not invoke this helper, even when
``GDW_AUTO_REPAIR_ORPHAN_PAGES`` is true: writer exclusion and rollback after
post-replacement fsync failure remain unproven. The original is never deleted.
This helper is not a qualified production repair procedure.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence
from urllib.parse import quote

RECEIPT_SCHEMA = "szl.gdw-orphan-page-restore/v1"
FINGERPRINT_SCHEMA = "szl.sqlite-logical-fingerprint/v1"
AUTO_REPAIR_ENV = "GDW_AUTO_REPAIR_ORPHAN_PAGES"
INTEGRITY_HEADER = "*** in database main ***"
_ORPHAN_LINE = re.compile(r"Page ([1-9][0-9]{0,9}): never used")
# Upper bound on reported integrity errors. Output that reaches the bound may be
# truncated, so it is treated as not classifiable rather than as orphan-only.
MAX_INTEGRITY_ERRORS = 100_000
_COPY_CHUNK = 1024 * 1024
_TRUE_VALUES = {"1", "true", "yes", "on"}
_SQLITE_MAGIC = b"SQLite format 3\x00"


class OrphanRepairError(RuntimeError):
    """The store could not be proven orphan-page-only or the repair failed."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def auto_repair_enabled(environ: Optional[Mapping[str, str]] = None) -> bool:
    """Default OFF; only an explicit true-like value enables repair.

    Enable it only when a single writer is guaranteed (see the module
    docstring): cross-host writers on a FUSE mount do not see SQLite locks.
    """

    values = os.environ if environ is None else environ
    raw = (values.get(AUTO_REPAIR_ENV) or "").strip().lower()
    return raw in _TRUE_VALUES


def _utc_stamp(now: Optional[datetime] = None) -> str:
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return moment.strftime("%Y%m%dT%H%M%SZ")


def _read_only_uri(path: Path) -> str:
    return "file:" + quote(str(path.resolve()), safe="/:") + "?mode=ro"


def _connect_read_only(path: Path) -> sqlite3.Connection:
    # mode=ro makes the original file unwritable through this handle. (Not
    # PRAGMA query_only: that also refuses VACUUM INTO's separate output file.)
    return sqlite3.connect(_read_only_uri(path), uri=True, timeout=30)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(_COPY_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def integrity_lines(
    connection: sqlite3.Connection,
    *,
    max_errors: int = MAX_INTEGRITY_ERRORS,
) -> list[str]:
    """Return every ``integrity_check`` message as separate stripped lines.

    SQLite reports b-tree damage as one row whose text is the
    ``*** in database main ***`` header followed by newline-separated messages,
    and index damage as further rows, so rows are split on newlines.
    """

    rows = connection.execute(f"PRAGMA integrity_check({int(max_errors)})").fetchall()
    lines: list[str] = []
    for row in rows:
        for line in str(row[0]).split("\n"):
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
    return lines


def classify_orphan_pages(lines: Sequence[str]) -> Optional[list[int]]:
    """Return orphan page numbers if the output is orphan-page-only, else None.

    The only accepted shape is the exact main-database header followed by one or
    more ``Page N: never used`` lines with distinct page numbers. ``ok``, an
    empty result, any other message, another database's header, or a possibly
    truncated report are all not repairable.
    """

    values = [str(line).strip() for line in lines]
    if len(values) < 2 or values[0] != INTEGRITY_HEADER:
        return None
    pages: list[int] = []
    for line in values[1:]:
        match = _ORPHAN_LINE.fullmatch(line)
        if match is None:
            return None
        pages.append(int(match.group(1)))
    if len(pages) != len(set(pages)) or len(values) >= MAX_INTEGRITY_ERRORS:
        return None
    return sorted(pages)


def _encode_value(value: Any) -> bytes:
    if value is None:
        return b"n"
    if isinstance(value, bool):  # sqlite3 never returns bool; keep it explicit
        return b"i" + str(int(value)).encode("ascii")
    if isinstance(value, int):
        return b"i" + str(value).encode("ascii")
    if isinstance(value, float):
        return b"f" + value.hex().encode("ascii")
    if isinstance(value, str):
        return b"s" + value.encode("utf-8", "surrogatepass")
    if isinstance(value, (bytes, bytearray, memoryview)):
        return b"b" + bytes(value)
    raise OrphanRepairError("FINGERPRINT_UNSUPPORTED_VALUE", type(value).__name__)


def _frame(digest: "hashlib._Hash", value: bytes) -> None:
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def logical_fingerprint(connection: sqlite3.Connection) -> dict[str, Any]:
    """Hash schema SQL plus every row of every table in a stable order.

    Root page numbers are excluded because ``VACUUM`` renumbers them. Rowid
    tables are read in rowid order; WITHOUT ROWID tables in primary-key order
    (all columns as the tiebreak). Virtual-table content is covered through
    its shadow tables, which are ordinary tables.
    """

    digest = hashlib.sha256()
    _frame(digest, FINGERPRINT_SCHEMA.encode("ascii"))
    for pragma in ("user_version", "application_id"):
        value = connection.execute(f"PRAGMA {pragma}").fetchone()[0]
        _frame(digest, f"{pragma}={int(value)}".encode("ascii"))
    schema = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "ORDER BY type, name, tbl_name"
    ).fetchall()
    tables: list[str] = []
    for kind, name, table_name, sql in schema:
        for item in (kind, name, table_name, sql):
            _frame(digest, _encode_value(item))
        if kind == "table" and not str(sql or "").upper().startswith(
            "CREATE VIRTUAL TABLE"
        ):
            tables.append(str(name))
    row_count = 0
    for table in tables:
        quoted = _quote_identifier(table)
        _frame(digest, b"table:" + table.encode("utf-8", "surrogatepass"))
        columns = connection.execute(f"PRAGMA table_xinfo({quoted})").fetchall()
        width = max(1, len(columns))
        try:
            cursor = connection.execute(f"SELECT * FROM {quoted} ORDER BY rowid")
        except sqlite3.OperationalError:
            order = ", ".join(str(index) for index in range(1, width + 1))
            cursor = connection.execute(f"SELECT * FROM {quoted} ORDER BY {order}")
        for row in cursor:
            row_count += 1
            digest.update(b"r")
            for value in row:
                _frame(digest, _encode_value(value))
    return {
        "schema": FINGERPRINT_SCHEMA,
        "sha256": digest.hexdigest(),
        "tables": len(tables),
        "rows": row_count,
    }


def _fsync_file(path: Path) -> None:
    with Path(path).open("rb+") as stream:
        stream.flush()
        os.fsync(stream.fileno())


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        handle = os.open(str(directory), flags)
    except OSError:
        if os.name == "nt":  # directories cannot be opened for fsync on Windows
            return
        raise
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def _copy_durably(source: Path, target: Path) -> None:
    """Copy bytes to a new file, fsync it, and fail if the target exists."""

    with Path(source).open("rb") as reader, Path(target).open("xb") as writer:
        shutil.copyfileobj(reader, writer, _COPY_CHUNK)
        writer.flush()
        os.fsync(writer.fileno())


def _write_json_durably(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.unlink(missing_ok=True)
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _sidecars_with_content(database: Path) -> list[str]:
    present = []
    for suffix in ("-journal", "-wal"):
        sidecar = database.with_name(database.name + suffix)
        try:
            if sidecar.stat().st_size > 0:
                present.append(sidecar.name)
        except FileNotFoundError:
            continue
    return present


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def recover_hot_journal(database: Path) -> bool:
    """Let SQLite run normal crash recovery before any read-only inspection.

    A process killed mid-transaction in DELETE journal mode leaves a hot
    ``-journal``. A ``mode=ro`` connection cannot roll it back
    (SQLITE_READONLY_ROLLBACK), so a read-write connection takes and releases
    a write reservation, which plays the journal back exactly as the regular
    writer open would. No page is written by this function itself.
    """

    database = Path(database)
    if not _sidecars_with_content(database):
        return False
    connection = sqlite3.connect(str(database), timeout=30, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("ROLLBACK")
    finally:
        connection.close()
    return True


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 4], "big")


def orphan_page_evidence(database: Path, pages: Sequence[int]) -> dict[str, Any]:
    """Prove from raw page bytes that the orphan pages held no live data.

    Accepted proofs: every orphan page is all-zero (``ALL_ZERO``), or the
    orphan set is one well-formed former freelist chain plus all-zero pages
    (``FORMER_FREELIST_CHAIN``). Anything else raises
    ``ORPHAN_PAGE_CONTENT_UNPROVEN``: such pages may be b-tree or overflow
    pages carrying committed rows that a lost parent update made unreachable.
    """

    database = Path(database)
    orphans = sorted(set(int(page) for page in pages))
    if not orphans:
        raise OrphanRepairError("ORPHAN_PAGE_CONTENT_UNPROVEN", "no orphan pages")
    with database.open("rb") as stream:
        header = stream.read(100)
        if len(header) < 100 or header[:16] != _SQLITE_MAGIC:
            raise OrphanRepairError("ORPHAN_PAGE_CONTENT_UNPROVEN", "not a SQLite file")
        page_size = int.from_bytes(header[16:18], "big")
        page_size = 65536 if page_size == 1 else page_size
        usable = page_size - header[20]
        if page_size < 512 or usable < 480:
            raise OrphanRepairError("ORPHAN_PAGE_CONTENT_UNPROVEN", "bad page size")
        file_pages = database.stat().st_size // page_size
        content: dict[int, bytes] = {}
        for page in orphans:
            if page < 2 or page > file_pages:
                raise OrphanRepairError(
                    "ORPHAN_PAGE_CONTENT_UNPROVEN", f"page {page} out of range"
                )
            stream.seek((page - 1) * page_size)
            content[page] = stream.read(page_size)
    orphan_set = set(orphans)
    zero = {page for page, data in content.items() if data.count(0) == len(data)}
    nonzero = orphan_set - zero
    evidence: dict[str, Any] = {
        "page_size": page_size,
        "orphan_pages": len(orphans),
        "zero_pages": len(zero),
    }
    if not nonzero:
        return {**evidence, "proof": "ALL_ZERO"}

    max_leaves = usable // 4 - 2
    trunks: dict[int, tuple[int, list[int]]] = {}
    for page in nonzero:
        data = content[page]
        count = _u32(data, 4)
        if count > max_leaves:
            continue
        trunks[page] = (
            _u32(data, 0),
            [_u32(data, 8 + 4 * index) for index in range(count)],
        )
    for head in sorted(trunks):
        explained: set[int] = set()
        chain: list[int] = []
        leaf_total = 0
        current = head
        valid = True
        while current:
            if current in explained or current not in trunks:
                valid = False
                break
            explained.add(current)
            chain.append(current)
            next_trunk, leaves = trunks[current]
            for leaf in leaves:
                if leaf not in orphan_set or leaf in explained:
                    valid = False
                    break
                explained.add(leaf)
            if not valid:
                break
            leaf_total += len(leaves)
            current = next_trunk
        if valid and leaf_total > 0 and nonzero <= explained:
            return {
                **evidence,
                "proof": "FORMER_FREELIST_CHAIN",
                "trunk_pages": chain,
                "leaf_pages": leaf_total,
            }
    raise OrphanRepairError(
        "ORPHAN_PAGE_CONTENT_UNPROVEN",
        f"{len(nonzero)} non-zero orphan page(s) not explained by a former freelist",
    )


def inspect(database: Path) -> dict[str, Any]:
    """Read-only integrity classification of an existing store."""

    connection = _connect_read_only(Path(database))
    try:
        lines = integrity_lines(connection)
    finally:
        connection.close()
    ok = lines == ["ok"]
    pages = None if ok else classify_orphan_pages(lines)
    return {
        "ok": ok,
        "integrity": lines,
        "orphan_pages": pages,
        "repairable": pages is not None,
    }


def _replace_live(source: Path, database: Path, expected_sha256: str) -> None:
    staging = database.with_name(database.name + ".repair-tmp")
    staging.unlink(missing_ok=True)
    try:
        _copy_durably(source, staging)
        if file_sha256(staging) != expected_sha256:
            raise OrphanRepairError("STAGED_COPY_MISMATCH")
        os.replace(staging, database)
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    _fsync_directory(database.parent)


def repair_orphan_pages(
    database: Path,
    *,
    label: str = "gdw",
    work_dir: Optional[Path] = None,
    forbidden_root: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Repair an orphan-page-only store in place and return the receipt.

    ``work_dir`` is the local scratch parent for the VACUUM candidate (default:
    the process temp dir). ``forbidden_root`` is the storage mount; the
    candidate is refused if it would be created inside it.
    """

    database = Path(database).resolve()
    if not database.is_file():
        raise OrphanRepairError("STORE_MISSING", str(database))
    sidecars = _sidecars_with_content(database)
    if sidecars:
        raise OrphanRepairError("UNCHECKPOINTED_SIDECAR_PRESENT", ",".join(sidecars))

    # This reserves the original inode only. It cannot exclude a writer that
    # opens the new inode after os.replace; production runtime blocks this path.
    guard = sqlite3.connect(str(database), timeout=30, isolation_level=None)
    try:
        guard.execute("BEGIN IMMEDIATE")
        return _repair_reserved(
            database,
            label=label,
            work_dir=work_dir,
            forbidden_root=forbidden_root,
            now=now,
        )
    finally:
        try:
            guard.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        guard.close()


def _repair_reserved(
    database: Path,
    *,
    label: str,
    work_dir: Optional[Path],
    forbidden_root: Optional[Path],
    now: Optional[datetime],
) -> dict[str, Any]:
    sidecars = _sidecars_with_content(database)
    if sidecars:
        raise OrphanRepairError("UNCHECKPOINTED_SIDECAR_PRESENT", ",".join(sidecars))
    original_sha256 = file_sha256(database)
    original_size = database.stat().st_size
    connection = _connect_read_only(database)
    try:
        original_integrity = integrity_lines(connection)
        pages = classify_orphan_pages(original_integrity)
        if pages is None:
            raise OrphanRepairError(
                "NOT_ORPHAN_PAGE_ONLY",
                "; ".join(original_integrity[:4])[:240],
            )
        page_evidence = orphan_page_evidence(database, pages)
        original_fingerprint = logical_fingerprint(connection)
        scratch_parent = Path(work_dir) if work_dir else Path(tempfile.gettempdir())
        scratch_parent.mkdir(parents=True, exist_ok=True)
        scratch = Path(tempfile.mkdtemp(prefix="gdw-orphan-repair-", dir=str(scratch_parent)))
        if _within(scratch, database.parent) or (
            forbidden_root is not None and _within(scratch, Path(forbidden_root))
        ):
            shutil.rmtree(scratch, ignore_errors=True)
            raise OrphanRepairError("CANDIDATE_NOT_LOCAL", str(scratch))
        try:
            candidate = scratch / "candidate.sqlite3"
            connection.execute("VACUUM INTO ?", (str(candidate),))
        except BaseException:
            shutil.rmtree(scratch, ignore_errors=True)
            raise
    finally:
        connection.close()
    # A read-only open of a WAL store may materialise an empty -wal; anything
    # with content now means another writer appeared, so stop.
    sidecars = _sidecars_with_content(database)
    if sidecars:
        shutil.rmtree(scratch, ignore_errors=True)
        raise OrphanRepairError("UNCHECKPOINTED_SIDECAR_PRESENT", ",".join(sidecars))

    try:
        if file_sha256(database) != original_sha256:
            raise OrphanRepairError("ORIGINAL_CHANGED_DURING_REPAIR")
        check = _connect_read_only(candidate)
        try:
            candidate_integrity = integrity_lines(check)
            foreign_keys = check.execute("PRAGMA foreign_key_check").fetchall()
            candidate_fingerprint = logical_fingerprint(check)
        finally:
            check.close()
        if candidate_integrity != ["ok"]:
            raise OrphanRepairError("CANDIDATE_INTEGRITY_FAILED", "; ".join(candidate_integrity[:4]))
        if foreign_keys:
            raise OrphanRepairError("CANDIDATE_FOREIGN_KEYS_FAILED", str(len(foreign_keys)))
        if candidate_fingerprint != original_fingerprint:
            raise OrphanRepairError("LOGICAL_FINGERPRINT_MISMATCH")
        candidate_sha256 = file_sha256(candidate)
        candidate_size = candidate.stat().st_size

        stamp = _utc_stamp(now)
        base = f"{database.name}.orphan-pages-{stamp}.{original_sha256[:12]}"
        preserved = database.with_name(base + ".sqlite3")
        receipt_path = database.with_name(base + ".json")
        if preserved.exists():
            if file_sha256(preserved) != original_sha256:
                raise OrphanRepairError("PRESERVATION_PATH_OCCUPIED", preserved.name)
        else:
            partial = preserved.with_name(preserved.name + ".partial")
            partial.unlink(missing_ok=True)
            _copy_durably(database, partial)
            if file_sha256(partial) != original_sha256:
                partial.unlink(missing_ok=True)
                raise OrphanRepairError("PRESERVED_COPY_MISMATCH")
            os.replace(partial, preserved)
            _fsync_directory(database.parent)
        receipt: dict[str, Any] = {
            "schema": RECEIPT_SCHEMA,
            "label": label,
            "status": "PRESERVED_BEFORE_REPLACE",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_path": str(database),
            "orphan_pages": pages,
            "orphan_page_evidence": page_evidence,
            "original": {
                "sha256": original_sha256,
                "size": original_size,
                "integrity": original_integrity,
                "preserved_path": str(preserved),
            },
            "candidate": {
                "sha256": candidate_sha256,
                "size": candidate_size,
                "integrity": candidate_integrity,
                "foreign_key_violations": 0,
                "method": "VACUUM INTO (read-only source, local scratch)",
            },
            "logical_fingerprint": original_fingerprint,
        }
        _write_json_durably(receipt_path, receipt)

        # Last check before the swap: the original must still be the bytes
        # that were verified and preserved (a writer that ignores the SQLite
        # reservation, e.g. on another host of the mount, is caught here).
        if file_sha256(database) != original_sha256 or _sidecars_with_content(database):
            receipt["status"] = "ABORTED_ORIGINAL_CHANGED"
            _write_json_durably(receipt_path, receipt)
            raise OrphanRepairError("ORIGINAL_CHANGED_DURING_REPAIR", "before swap")
        _replace_live(candidate, database, candidate_sha256)
        try:
            live = _connect_read_only(database)
            try:
                post_integrity = integrity_lines(live)
                post_fingerprint = logical_fingerprint(live)
            finally:
                live.close()
            if post_integrity != ["ok"] or post_fingerprint != original_fingerprint:
                raise OrphanRepairError("POST_REPLACE_VERIFICATION_FAILED")
        except BaseException as exc:
            # Put the logically identical original back; it stays preserved too.
            _replace_live(preserved, database, original_sha256)
            receipt["status"] = "ROLLED_BACK"
            receipt["rollback_reason"] = type(exc).__name__
            _write_json_durably(receipt_path, receipt)
            if isinstance(exc, OrphanRepairError):
                raise
            raise OrphanRepairError("POST_REPLACE_VERIFICATION_FAILED", type(exc).__name__) from exc

        receipt["status"] = "APPLIED"
        receipt["applied_at"] = datetime.now(timezone.utc).isoformat()
        receipt["post_replace"] = {
            "sha256": file_sha256(database),
            "integrity": post_integrity,
            "logical_fingerprint_sha256": post_fingerprint["sha256"],
        }
        receipt["receipt_path"] = str(receipt_path)
        _write_json_durably(receipt_path, receipt)
        return receipt
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
