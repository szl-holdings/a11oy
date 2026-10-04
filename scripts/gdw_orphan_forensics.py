#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Bounded forensic observations of source-qualified orphan pages, never repair.

Call only with a disposable inspection copy in a private directory. SQLite sees
an in-memory deserialization of fixed bytes, never a filesystem database path.
The result cannot admit a candidate, discard, restore, or deployment. Local
page layout and whole-page equality do not establish record equivalence.

Format references: https://www.sqlite.org/fileformat.html (sections 1.3, 1.6,
1.7), https://www.sqlite.org/dbstat.html, and SQLite's btree.c minimum cell size:
https://www3.sqlite.org/matrix/ev/src/btree.html .
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import sqlite3
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = "szl.gdw-orphan-page-forensics/v1"
MAX_DATABASE_BYTES = 64 * 1024 * 1024
MAX_ORPHAN_PAGES = 99
MAX_INTEGRITY_FINDINGS = 100
MAX_NATIVE_VALUE_BYTES = 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024
MAX_ANALYSIS_SECONDS = 60
_PAGE_TYPES = {2: "INDEX_INTERIOR", 5: "TABLE_INTERIOR", 10: "INDEX_LEAF", 13: "TABLE_LEAF"}
_SIDECARS = ("-journal", "-wal", "-shm")
_CODES = {
    "FORENSICS_UNAVAILABLE", "FORENSICS_DEADLINE_EXHAUSTED", "INVALID_DEADLINE",
    "INVALID_ORPHAN_PAGE_SET", "INSPECTION_COPY_UNAVAILABLE", "INSPECTION_COPY_NOT_PRIVATE",
    "INSPECTION_COPY_BOUND_EXCEEDED", "INSPECTION_COPY_CHANGED", "SIDECAR_REVIEW_REQUIRED",
    "SQLITE_HEADER_UNQUALIFIED", "SQLITE_WAL_MODE_UNSUPPORTED", "NATIVE_INSPECTION_UNAVAILABLE",
    "ORPHAN_SET_NOT_CONFIRMED", "INTEGRITY_RESULT_INCOMPLETE", "DBSTAT_UNAVAILABLE",
    "DBSTAT_NAME_COLLISION", "DBSTAT_RESULT_INCOMPLETE", "DBSTAT_ORPHAN_CONFLICT",
}


class ForensicsError(RuntimeError):
    def __init__(self, code: str):
        self.code = code if code in _CODES else "FORENSICS_UNAVAILABLE"
        super().__init__(self.code)


def _budget(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise ForensicsError("FORENSICS_DEADLINE_EXHAUSTED")


def _held(code: str = "FORENSICS_UNAVAILABLE") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "HELD", "analysis_state": "UNAVAILABLE",
        "diagnostic_code": code, "hold_reason": "UNREFERENCED_PAGE_CONTENTS_REQUIRE_REVIEW",
        "candidate_created": False, "discard_admitted": False, "restore_admitted": False,
        "deployment_admitted": False, "provider_writes_performed": False,
        "private_payloads_emitted": False, "record_comparison": "UNAVAILABLE",
        "record_equivalence_verified": False, "all_bytes_semantically_explained": False,
    }


def _token(value: os.stat_result) -> tuple:
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _open_parent(path: Path, deadline: float) -> int:
    if not path.is_absolute() or ".." in path.parts or len(os.fsencode(path)) > 4096:
        raise ForensicsError("INSPECTION_COPY_UNAVAILABLE")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        for part in path.parts[1:-1]:
            _budget(deadline)
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK,
                            dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        metadata = os.fstat(descriptor)
        if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077:
            raise ForensicsError("INSPECTION_COPY_NOT_PRIVATE")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _companions(parent: int, name: str, deadline: float) -> tuple:
    observed = []
    for suffix in _SIDECARS:
        _budget(deadline)
        try:
            metadata = os.stat(name + suffix, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            observed.append(None)
            continue
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_uid != os.geteuid() or metadata.st_size != 0):
            raise ForensicsError("SIDECAR_REVIEW_REQUIRED")
        observed.append(_token(metadata))
    return tuple(observed)


def _read(descriptor: int, size: int, deadline: float, *, retain: bool) -> tuple[bytes, str]:
    chunks = []
    digest = hashlib.sha256()
    offset = 0
    while offset < size:
        _budget(deadline)
        chunk = os.pread(descriptor, min(READ_CHUNK_BYTES, size - offset), offset)
        if not chunk:
            raise ForensicsError("INSPECTION_COPY_CHANGED")
        digest.update(chunk)
        if retain:
            chunks.append(chunk)
        offset += len(chunk)
    if os.pread(descriptor, 1, size):
        raise ForensicsError("INSPECTION_COPY_CHANGED")
    result = b"".join(chunks) if retain else b""
    _budget(deadline)
    return result, digest.hexdigest()


@contextmanager
def _snapshot(path: Path, deadline: float):
    parent = descriptor = None
    try:
        parent = _open_parent(path, deadline)
        parent_identity = _token(os.fstat(parent))[:2]
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_uid != os.geteuid() or metadata.st_mode & 0o133):
            raise ForensicsError("INSPECTION_COPY_UNAVAILABLE")
        if not 512 <= metadata.st_size <= MAX_DATABASE_BYTES:
            raise ForensicsError("INSPECTION_COPY_BOUND_EXCEEDED")
        companions = _companions(parent, path.name, deadline)
        data, digest = _read(descriptor, metadata.st_size, deadline, retain=True)
        if _token(os.fstat(descriptor)) != _token(metadata):
            raise ForensicsError("INSPECTION_COPY_CHANGED")
        yield data, digest
        # The same descriptor and path identity must survive all inspection and
        # the final full read; inode/mtime checks alone are not content evidence.
        _, final_digest = _read(descriptor, metadata.st_size, deadline, retain=False)
        reopened = _open_parent(path, deadline)
        try:
            if (_token(os.fstat(reopened))[:2] != parent_identity
                    or _token(os.fstat(descriptor)) != _token(metadata)
                    or _token(os.stat(path.name, dir_fd=reopened, follow_symlinks=False)) != _token(metadata)
                    or final_digest != digest or _companions(reopened, path.name, deadline) != companions):
                raise ForensicsError("INSPECTION_COPY_CHANGED")
        finally:
            os.close(reopened)
        _budget(deadline)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent is not None:
            os.close(parent)


def _header(data: bytes) -> dict[str, int]:
    if data[:16] != b"SQLite format 3\x00":
        raise ForensicsError("SQLITE_HEADER_UNQUALIFIED")
    page_size = int.from_bytes(data[16:18], "big")
    page_size = 65536 if page_size == 1 else page_size
    page_count = int.from_bytes(data[28:32], "big")
    reserved = data[20]
    if (not 512 <= page_size <= 65536 or page_size & (page_size - 1)
            or page_size - reserved < 480 or page_count * page_size != len(data)
            or data[24:28] != data[92:96] or data[21:24] != b"\x40\x20\x20"
            or any(data[72:92]) or int.from_bytes(data[44:48], "big") not in {1, 2, 3, 4}
            or int.from_bytes(data[56:60], "big") not in {1, 2, 3}):
        raise ForensicsError("SQLITE_HEADER_UNQUALIFIED")
    if data[18:20] != b"\x01\x01":
        # Deserialization does not accept WAL images. Never rewrite the header
        # or ignore companion bytes to make an image inspectable.
        raise ForensicsError("SQLITE_WAL_MODE_UNSUPPORTED")
    return {"page_size": page_size, "page_count": page_count, "reserved_bytes_per_page": reserved}


class _LayoutError(Exception):
    pass


def _varint(page: bytes, offset: int, usable: int) -> tuple[int, int]:
    value = 0
    for index in range(9):
        if offset >= usable:
            raise _LayoutError
        byte = page[offset]
        offset += 1
        value = (value << (8 if index == 8 else 7)) | (byte if index == 8 else byte & 127)
        if index == 8 or byte < 128:
            return value, offset
    raise _LayoutError


def _page_reference(page: bytes, offset: int, usable: int, page_count: int, page_number: int) -> int:
    if offset + 4 > usable:
        raise _LayoutError
    value = int.from_bytes(page[offset:offset + 4], "big")
    if not 1 <= value <= page_count or value == page_number:
        raise _LayoutError
    return value


def _layout(page: bytes, page_number: int, header: dict, deadline: float) -> dict:
    result = {"classification": "UNIDENTIFIED_BYTES", "local_layout_validated": False,
              "overflow_chain_validation": "NOT_PERFORMED", "record_decoding": "NOT_PERFORMED"}
    if not any(page):
        result["classification"] = "ZERO_FILLED"
        return result
    offset = 100 if page_number == 1 else 0
    kind = page[offset]
    if kind not in _PAGE_TYPES:
        # Overflow and freelist pages have no unique magic byte. Their first
        # bytes must never be relabeled as a pointer without traversal evidence.
        return result
    result.update(classification="BTREE_LAYOUT_INVALID", btree_kind=_PAGE_TYPES[kind])
    try:
        usable = len(page) - header["reserved_bytes_per_page"]
        interior = kind in {2, 5}
        end_header = offset + (12 if interior else 8)
        count = int.from_bytes(page[offset + 3:offset + 5], "big")
        content = int.from_bytes(page[offset + 5:offset + 7], "big") or 65536
        fragments = page[offset + 7]
        pointer_end = end_header + count * 2
        first_free = int.from_bytes(page[offset + 1:offset + 3], "big")
        if not pointer_end <= content <= usable or fragments > 60:
            raise _LayoutError
        if count == 0 and (content != usable or first_free or fragments or interior):
            raise _LayoutError
        child_pages = set()
        if interior:
            child_pages.add(_page_reference(page, offset + 8, usable, header["page_count"], page_number))
        regions = [(0, pointer_end, "header_and_pointers"),
                   (pointer_end, content, "unallocated"), (usable, len(page), "reserved")]
        occupied = []
        payload_bytes = local_payload_bytes = overflow_cells = 0
        for index in range(count):
            _budget(deadline)
            start = int.from_bytes(page[end_header + 2 * index:end_header + 2 * index + 2], "big")
            if not content <= start <= usable - 4:
                raise _LayoutError
            cursor = start
            if interior:
                child = _page_reference(page, cursor, usable, header["page_count"], page_number)
                if child in child_pages:
                    raise _LayoutError
                child_pages.add(child)
                cursor += 4
            payload = 0
            if kind != 5:
                payload, cursor = _varint(page, cursor, usable)
                if payload > MAX_DATABASE_BYTES:
                    raise _LayoutError
            if kind in {5, 13}:
                _, cursor = _varint(page, cursor, usable)
            maximum = usable - 35 if kind == 13 else ((usable - 12) * 64 // 255) - 23
            minimum = ((usable - 12) * 32 // 255) - 23
            local = payload
            if payload > maximum:
                local = minimum + (payload - minimum) % (usable - 4)
                if local > maximum:
                    local = minimum
            cursor += local
            if local < payload:
                _page_reference(page, cursor, usable, header["page_count"], page_number)
                cursor += 4
                overflow_cells += 1
            end = max(start + 4, cursor)
            if end > usable:
                raise _LayoutError
            occupied.append((start, end, "cells"))
            payload_bytes += payload
            local_payload_bytes += local
        if first_free and (not occupied or first_free <= min(region[0] for region in occupied)):
            raise _LayoutError
        free_count = 0
        cursor = first_free
        while cursor:
            _budget(deadline)
            if not content <= cursor <= usable - 4 or free_count >= usable // 4:
                raise _LayoutError
            next_free = int.from_bytes(page[cursor:cursor + 2], "big")
            size = int.from_bytes(page[cursor + 2:cursor + 4], "big")
            if size < 4 or cursor + size > usable or next_free and next_free <= cursor + size + 3:
                raise _LayoutError
            occupied.append((cursor, cursor + size, "freeblocks"))
            free_count += 1
            cursor = next_free
        fragment_count = 0
        cursor = content
        for start, end, category in sorted(occupied):
            _budget(deadline)
            gap = start - cursor
            if not 0 <= gap <= 3:
                raise _LayoutError
            regions.append((cursor, start, "fragments"))
            regions.append((start, end, category))
            fragment_count += gap
            cursor = end
        if not 0 <= usable - cursor <= 3 or fragment_count + usable - cursor != fragments:
            raise _LayoutError
        regions.append((cursor, usable, "fragments"))
        totals = {key: {"byte_count": 0, "nonzero_byte_count": 0} for key in (
            "header_and_pointers", "cells", "freeblocks", "fragments", "unallocated", "reserved")}
        for start, end, category in regions:
            _budget(deadline)
            totals[category]["byte_count"] += end - start
            totals[category]["nonzero_byte_count"] += (end - start) - page[start:end].count(0)
        result.update(classification="BTREE_LOCAL_LAYOUT_CONSISTENT", local_layout_validated=True,
                      cell_count=count, declared_payload_byte_count=payload_bytes,
                      local_payload_byte_count=local_payload_bytes, overflow_cell_count=overflow_cells,
                      child_pointer_count=len(child_pages), freeblock_count=free_count,
                      byte_regions=totals)
        return result
    except _LayoutError:
        return result


def _confirm_orphans(connection: sqlite3.Connection, pages: tuple[int, ...], deadline: float) -> None:
    observed = []
    rows = 0
    for row in connection.execute(f"PRAGMA integrity_check({MAX_INTEGRITY_FINDINGS})"):
        _budget(deadline)
        rows += 1
        if rows > MAX_INTEGRITY_FINDINGS or len(row) != 1 or type(row[0]) is not str:
            raise ForensicsError("INTEGRITY_RESULT_INCOMPLETE")
        for line in row[0].splitlines():
            if line == "*** in database main ***":
                continue
            match = re.fullmatch(r"Page ([1-9][0-9]{0,9}): never used", line)
            if match is None:
                raise ForensicsError("ORPHAN_SET_NOT_CONFIRMED")
            observed.append(int(match.group(1)))
            if len(observed) >= MAX_INTEGRITY_FINDINGS:
                raise ForensicsError("INTEGRITY_RESULT_INCOMPLETE")
    if tuple(sorted(observed)) != pages:
        raise ForensicsError("ORPHAN_SET_NOT_CONFIRMED")
    _budget(deadline)


def _dbstat_rows(connection: sqlite3.Connection, header: dict, deadline: float) -> dict[int, str]:
    if connection.execute("SELECT sqlite_compileoption_used('ENABLE_DBSTAT_VTAB')").fetchone() != (1,):
        raise ForensicsError("DBSTAT_UNAVAILABLE")
    if connection.execute("SELECT count(*) FROM main.sqlite_schema WHERE name='dbstat' COLLATE NOCASE").fetchone() != (0,):
        raise ForensicsError("DBSTAT_NAME_COLLISION")
    reachable = {}
    query = ("SELECT pageno,pagetype,ncell,payload,unused,mx_payload,pgsize "
             "FROM dbstat('main') WHERE aggregate=0")
    for row in connection.execute(query):
        _budget(deadline)
        if len(row) != 7:
            raise ForensicsError("DBSTAT_RESULT_INCOMPLETE")
        number, kind, cells, payload, unused, maximum, size = row
        if (any(type(value) is not int for value in (number, cells, payload, unused, maximum, size))
                or kind not in {"internal", "leaf", "overflow"} or not 1 <= number <= header["page_count"]
                or number in reachable or size != header["page_size"]
                or not 0 <= cells <= size // 4 or not 0 <= payload <= size or not 0 <= unused <= size
                or not 0 <= maximum <= MAX_DATABASE_BYTES):
            raise ForensicsError("DBSTAT_RESULT_INCOMPLETE")
        reachable[number] = kind
    if 1 not in reachable or reachable[1] not in {"internal", "leaf"}:
        raise ForensicsError("DBSTAT_RESULT_INCOMPLETE")
    _budget(deadline)
    return reachable


def _native(data: bytes, pages: tuple[int, ...], header: dict, deadline: float) -> tuple[dict, dict[int, str]]:
    connection = None
    result = {"state": "UNAVAILABLE", "scope": "SCHEMA_BTREES_AND_PAYLOAD_OVERFLOW",
              "freelist_pointer_map_and_lock_pages_enumerated": False,
              "orphan_set_reconfirmed": False, "complete": False,
              "diagnostic_code": "NATIVE_INSPECTION_UNAVAILABLE"}
    reachable = {}
    try:
        _budget(deadline)
        connection = sqlite3.connect(":memory:", timeout=0)
        connection.enable_load_extension(False)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_NATIVE_VALUE_BYTES)
        connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 4096)
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
        connection.deserialize(data)
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA cell_size_check=ON")
        if connection.execute("PRAGMA query_only").fetchone() != (1,):
            raise ForensicsError("NATIVE_INSPECTION_UNAVAILABLE")
        _confirm_orphans(connection, pages, deadline)
        result["orphan_set_reconfirmed"] = True
        reachable = _dbstat_rows(connection, header, deadline)
        if set(pages) & reachable.keys():
            raise ForensicsError("DBSTAT_ORPHAN_CONFLICT")
        counts = {kind: sum(value == kind for value in reachable.values())
                  for kind in ("internal", "leaf", "overflow")}
        result.update(state="OBSERVED", complete=True, diagnostic_code="DBSTAT_SCOPE_ENUMERATED",
                      reachable_page_count=len(reachable), reachable_page_types=counts,
                      inspector_sqlite_version=sqlite3.sqlite_version)
    except ForensicsError as error:
        if error.code == "FORENSICS_DEADLINE_EXHAUSTED":
            raise
        result["diagnostic_code"] = error.code
        reachable = {}
    except Exception:
        reachable = {}
    finally:
        if connection is not None:
            connection.close()
    # A progress callback interrupts SQLite with an OperationalError. That
    # error, or slow connection cleanup, must not hide an exhausted deadline.
    _budget(deadline)
    return result, reachable


def _page(data: bytes, number: int, size: int) -> bytes:
    # Derive file offsets from the validated page size/number. dbstat's offset
    # metadata is not used as authority for the bytes selected for comparison.
    return data[(number - 1) * size:number * size]


def _duplicates(data: bytes, pages: tuple[int, ...], reachable: dict[int, str],
                size: int, deadline: float) -> dict[int, dict]:
    candidates = {}
    matches = {number: [] for number in pages}
    for number in pages:
        _budget(deadline)
        candidates.setdefault(hashlib.sha256(_page(data, number, size)).digest(), []).append(number)
    for number in sorted(reachable):
        _budget(deadline)
        raw = _page(data, number, size)
        digest = hashlib.sha256(raw).digest()
        for orphan in candidates.get(digest, ()):
            _budget(deadline)
            # Hashes shortlist pages only; equality is checked over every byte,
            # including freeblocks, fragments, unused and reserved space.
            if raw == _page(data, orphan, size):
                matches[orphan].append(number)
    result = {}
    for number, matched in matches.items():
        _budget(deadline)
        digest = hashlib.sha256()
        kinds = {kind: 0 for kind in ("internal", "leaf", "overflow")}
        for reachable_number in matched:
            digest.update(reachable_number.to_bytes(8, "big"))
            kinds[reachable[reachable_number]] += 1
        result[number] = {"state": "EXACT_FULL_PAGE_MATCH" if matched else "NO_FULL_PAGE_MATCH",
                          "comparison_complete": True, "reachable_match_count": len(matched),
                          "reachable_match_page_numbers_sha256": digest.hexdigest(),
                          "reachable_match_page_types": kinds}
    _budget(deadline)
    return result


def inspect_orphan_pages(inspection_copy: Path | str, orphan_pages: list[int] | tuple[int, ...],
                         *, deadline: float) -> dict[str, Any]:
    """Return safe observations; the caller retains the existing recovery hold.

    ``orphan_pages`` must come from the complete source-qualified integrity
    result for this same disposable copy. Native inspection reconfirms the set.
    No source path, schema name, row, SQLite diagnostic, or page bytes are emitted.
    """
    try:
        if type(deadline) not in {int, float} or not math.isfinite(deadline):
            raise ForensicsError("INVALID_DEADLINE")
        deadline = min(deadline, time.monotonic() + MAX_ANALYSIS_SECONDS)
        _budget(deadline)
        if (type(orphan_pages) not in {list, tuple} or not 1 <= len(orphan_pages) <= MAX_ORPHAN_PAGES
                or any(type(number) is not int or not 2 <= number <= MAX_DATABASE_BYTES // 512
                       for number in orphan_pages)
                or len(set(orphan_pages)) != len(orphan_pages)):
            raise ForensicsError("INVALID_ORPHAN_PAGE_SET")
        pages = tuple(sorted(orphan_pages))
        with _snapshot(Path(inspection_copy), deadline) as (data, digest):
            header = _header(data)
            if pages[-1] > header["page_count"]:
                raise ForensicsError("INVALID_ORPHAN_PAGE_SET")
            report = _held("FORENSIC_EVIDENCE_REQUIRES_REVIEW")
            combined = hashlib.sha256()
            observations = []
            for number in pages:
                _budget(deadline)
                raw = _page(data, number, header["page_size"])
                combined.update(number.to_bytes(8, "big"))
                combined.update(raw)
                observations.append({"page_number": number, "byte_count": len(raw),
                                     "nonzero_byte_count": len(raw) - raw.count(0),
                                     "sha256": hashlib.sha256(raw).hexdigest(),
                                     "structure": _layout(raw, number, header, deadline),
                                     "reachable_duplicate": {"state": "NOT_PERFORMED", "comparison_complete": False}})
            native, reachable = _native(data, pages, header, deadline)
            if native["complete"]:
                duplicates = _duplicates(data, pages, reachable, header["page_size"], deadline)
                for observation in observations:
                    observation["reachable_duplicate"] = duplicates[observation["page_number"]]
            report.update(analysis_state="COMPLETE" if native["complete"] else "PARTIAL",
                          inspection_sha256=digest, database_header=header, orphan_page_count=len(pages),
                          orphan_byte_count=len(pages) * header["page_size"],
                          orphan_contents_sha256=combined.hexdigest(), pages=observations,
                          native_reachability=native, companions="ABSENT_OR_EMPTY_VERIFIED")
            _budget(deadline)
        report["inspection_copy_unchanged"] = True
        _budget(deadline)
        return report
    except ForensicsError as error:
        return _held(error.code)
    except Exception:
        if type(deadline) in {int, float} and time.monotonic() >= deadline:
            return _held("FORENSICS_DEADLINE_EXHAUSTED")
        return _held("FORENSICS_UNAVAILABLE")
