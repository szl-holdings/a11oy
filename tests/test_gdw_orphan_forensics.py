#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import stat
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gdw_orphan_forensics", ROOT / "scripts/gdw_orphan_forensics.py")
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
PRIVATE = "SYNTHETIC_PRIVATE_VALUE_MUST_NOT_APPEAR_IN_FORENSICS"


def native_database(directory, *, page_size=512, count=90, payload_size=700, index=True):
    directory.mkdir(mode=0o700)
    database = directory / "inspection.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute(f"PRAGMA page_size={page_size}")
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA secure_delete=OFF")
        connection.execute("CREATE TABLE private_table(id INTEGER PRIMARY KEY, value BLOB)")
        if index:
            connection.execute("CREATE INDEX private_index ON private_table(value)")
        values = [(index, (f"{index:08d}:" + PRIVATE).encode().ljust(payload_size, b"x"))
                  for index in range(1, count + 1)]
        connection.executemany("INSERT INTO private_table VALUES(?,?)", values)
        connection.commit()
        rows = connection.execute(
            "SELECT pageno,pagetype,ncell,payload,unused FROM dbstat('main') WHERE aggregate=0"
        ).fetchall()
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    finally:
        connection.close()
    return database, rows


def append_pages(database, raw_pages):
    data = bytearray(database.read_bytes())
    size = int.from_bytes(data[16:18], "big")
    size = 65536 if size == 1 else size
    original_count = len(data) // size
    assert all(len(page) == size for page in raw_pages)
    for raw in raw_pages:
        data.extend(raw)
    data[28:32] = (original_count + len(raw_pages)).to_bytes(4, "big")
    database.write_bytes(data)
    return list(range(original_count + 1, original_count + len(raw_pages) + 1))


def with_duplicate(tmp_path, *, kind="leaf", page_size=512):
    database, rows = native_database(tmp_path / "inspection", page_size=page_size)
    selected = next(row[0] for row in rows if row[1] == kind and row[0] != 1)
    original = database.read_bytes()
    raw = original[(selected - 1) * page_size:selected * page_size]
    pages = append_pages(database, [raw])
    return database, pages, selected, raw


def inspect(database, pages, **kwargs):
    return f.inspect_orphan_pages(database, pages, deadline=kwargs.get("deadline", time.monotonic() + 30))


def assert_held(report):
    assert report["schema"] == f.SCHEMA
    assert report["state"] == "HELD"
    for key in ("candidate_created", "discard_admitted", "restore_admitted", "deployment_admitted",
                "provider_writes_performed", "private_payloads_emitted", "record_equivalence_verified",
                "all_bytes_semantically_explained"):
        assert report[key] is False
    assert report["record_comparison"] == "UNAVAILABLE"
    assert PRIVATE not in json.dumps(report)
    assert "private_table" not in json.dumps(report)
    assert "private_index" not in json.dumps(report)


def detached_freelist_database(tmp_path, *, page_size=512, graph=None, page_count=2,
                               attached_freelist=False):
    """Owned fixture only: validate SQLite's freelist interpretation, then detach."""
    database, _ = native_database(tmp_path / "inspection", page_size=page_size,
                                  count=15 if attached_freelist else 3,
                                  payload_size=page_size + 200, index=False)
    if attached_freelist:
        with sqlite3.connect(database) as connection:
            connection.execute("PRAGMA secure_delete=OFF")
            connection.execute("DELETE FROM private_table WHERE id>3")
            connection.commit()
            assert connection.execute("PRAGMA freelist_count").fetchone()[0] > 0
    data = database.read_bytes()
    first = len(data) // page_size + 1
    graph = {0: (None, [1])} if graph is None else graph
    raw_pages = [bytearray(page_size) for _ in range(page_count)]
    for index, (next_index, leaves) in graph.items():
        numbers = [0 if next_index is None else first + next_index, len(leaves)]
        numbers.extend(first + leaf for leaf in leaves)
        struct.pack_into(">" + "I" * len(numbers), raw_pages[index], 0, *numbers)
    pages = append_pages(database, raw_pages)
    # On a separate owned control, the exact same pages are a valid attached
    # freelist. The production helper never performs these header edits.
    if not attached_freelist:
        control = bytearray(database.read_bytes())
        struct.pack_into(">II", control, 32, pages[0], len(pages))
        connection = sqlite3.connect(":memory:")
        try:
            connection.deserialize(bytes(control))
            assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            assert connection.execute("PRAGMA freelist_count").fetchone()[0] == len(pages)
        finally:
            connection.close()
    return database, pages


def assert_structural_freelist(report, pages):
    assert_held(report)
    graph = report["freelist_graph"]
    assert graph["state"] == "STRUCTURALLY_ACCOUNTED", report
    assert graph["complete"] is True
    assert graph["whole_database_accounted"] is True
    assert graph["orphan_bytes_structurally_accounted"] is True
    detached = graph["detached_freelist"]
    assert detached["page_count"] == len(pages)
    assert sorted([item["page_number"] for item in detached["trunks"]]
                  + detached["zero_leaf_pages"]) == sorted(pages)
    assert (graph["reachable_page_count"] + graph["attached_freelist"]["page_count"]
            + detached["page_count"]) == graph["page_count"]
    totals = graph["byte_accounting"]
    assert totals["structural_bytes"] + totals["zero_padding_and_leaf_bytes"] == totals["total_bytes"]
    assert totals["structural_nonzero_bytes"] == sum(page["nonzero_byte_count"] for page in report["pages"])


def test_incident_page_layout_is_bound_by_complete_known_hashes():
    trunk = bytearray(4096)
    struct.pack_into(">III", trunk, 0, 0, 1, 363)
    assert hashlib.sha256(trunk).hexdigest() == "5c26ffe5a3bd323afcb044bb29873be650603ff02a455413406c11c289844ea1"
    assert hashlib.sha256(bytes(4096)).hexdigest() == "ad7facb2586fc6e966c004d7d1d16b024f5805ff7cb47c7a85dabd8b48892ca7"
    aggregate = hashlib.sha256((362).to_bytes(8, "big") + trunk
                               + (363).to_bytes(8, "big") + bytes(4096)).hexdigest()
    assert aggregate == "7087cd8401554bf5dd4a1a162c2f0753d26457fe04126e66dfbc06f4c0483ba9"


@pytest.mark.parametrize("page_size", [512, 4096, 65536])
@pytest.mark.parametrize("multiple_trunks", [False, True])
def test_native_freelist_graph_with_complete_zero_byte_accounting_stays_held(tmp_path, page_size, multiple_trunks):
    graph = {0: (2, [1]), 2: (None, [3, 4])} if multiple_trunks else None
    database, pages = detached_freelist_database(tmp_path, page_size=page_size,
                                                graph=graph, page_count=5 if multiple_trunks else 2)
    before = database.read_bytes()
    entries = sorted(database.parent.iterdir())
    report = inspect(database, pages[::-1])
    assert_structural_freelist(report, pages)
    assert report["database_header"]["freelist_head"] == 0
    assert report["database_header"]["freelist_page_count"] == 0
    assert report["database_header"]["largest_root_page"] == 0
    assert report["database_header"]["incremental_vacuum"] == 0
    assert report["freelist_graph"]["attached_freelist"]["page_count"] == 0
    assert database.read_bytes() == before
    assert sorted(database.parent.iterdir()) == entries


def test_native_attached_freelist_and_detached_graph_are_fully_disjoint(tmp_path):
    database, pages = detached_freelist_database(tmp_path, attached_freelist=True)
    before = database.read_bytes()
    report = inspect(database, pages)
    assert_structural_freelist(report, pages)
    attached = report["freelist_graph"]["attached_freelist"]
    assert attached["page_count"] > 0 and attached["trunk_count"] > 0
    assert attached["head"] == int.from_bytes(before[32:36], "big")
    assert attached["page_count"] == int.from_bytes(before[36:40], "big")
    assert database.read_bytes() == before


def test_native_secure_delete_freelist_can_be_described_after_owned_header_detachment(tmp_path):
    database, _ = native_database(tmp_path / "inspection", count=20, payload_size=700, index=False)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA secure_delete=ON")
        connection.execute("DELETE FROM private_table WHERE id>3")
        connection.commit()
        free_count = connection.execute("PRAGMA freelist_count").fetchone()[0]
        assert 2 <= free_count <= f.MAX_ORPHAN_PAGES
        active = {row[0] for row in connection.execute("SELECT pageno FROM dbstat('main')")}
    data = bytearray(database.read_bytes())
    page_count = len(data) // 512
    pages = sorted(set(range(1, page_count + 1)) - active)
    assert len(pages) == free_count
    data[32:40] = bytes(8)  # Owned synthetic damage only, never production input.
    database.write_bytes(data)
    report = inspect(database, pages)
    assert_structural_freelist(report, pages)
    assert database.read_bytes() == data


@pytest.mark.parametrize("defect", ["next_self", "next_out_of_range", "next_reachable", "next_leaf",
    "leaf_self", "leaf_zero", "leaf_out_of_range", "leaf_reachable", "duplicate_leaf",
    "capacity", "nonzero_tail", "nonzero_leaf", "undeclared_pointer"])
def test_detached_graph_defects_never_gain_structural_accounting(tmp_path, defect):
    database, pages = detached_freelist_database(tmp_path)
    data = bytearray(database.read_bytes())
    start = (pages[0] - 1) * 512
    if defect.startswith("next_"):
        value = {"next_self": pages[0], "next_out_of_range": pages[-1] + 1,
                 "next_reachable": 1, "next_leaf": pages[1]}[defect]
        struct.pack_into(">I", data, start, value)
    elif defect.startswith("leaf_"):
        value = {"leaf_self": pages[0], "leaf_zero": 0,
                 "leaf_out_of_range": pages[-1] + 1, "leaf_reachable": 2}[defect]
        struct.pack_into(">I", data, start + 8, value)
    elif defect == "duplicate_leaf":
        struct.pack_into(">III", data, start + 4, 2, pages[1], pages[1])
    elif defect == "capacity":
        struct.pack_into(">I", data, start + 4, 2**32 - 1)
    elif defect == "nonzero_tail":
        data[start + 511] = 1
    elif defect == "nonzero_leaf":
        data[-1] = 1
    else:
        struct.pack_into(">I", data, start + 4, 0)
    database.write_bytes(data)
    report = inspect(database, pages)
    assert_held(report)
    assert report["freelist_graph"]["state"] == "UNCLASSIFIED"
    assert report["freelist_graph"]["complete"] is False
    assert database.read_bytes() == data


@pytest.mark.parametrize("defect", ["disconnected_zero", "disconnected_graph", "cycle", "duplicate_owner"])
def test_detached_graph_must_have_one_complete_acyclic_ownership_graph(tmp_path, defect):
    database, pages = detached_freelist_database(tmp_path, graph={0: (2, [1]), 2: (None, [3])}, page_count=4)
    data = bytearray(database.read_bytes())
    first = (pages[0] - 1) * 512
    second = (pages[2] - 1) * 512
    if defect in {"disconnected_zero", "disconnected_graph"}:
        struct.pack_into(">I", data, first, 0)
        if defect == "disconnected_zero":
            data[second:second + 512] = bytes(512)
    elif defect == "cycle":
        struct.pack_into(">I", data, second, pages[0])
    else:
        struct.pack_into(">I", data, second + 8, pages[1])
    database.write_bytes(data)
    report = inspect(database, pages)
    assert_held(report)
    assert report["freelist_graph"]["state"] == "UNCLASSIFIED"
    assert database.read_bytes() == data


@pytest.mark.parametrize("field", ["largest_root_page", "incremental_vacuum", "reserved_bytes_per_page"])
def test_allocator_modes_outside_the_reviewed_scope_are_not_classified(tmp_path, field):
    database, pages = detached_freelist_database(tmp_path)
    data = database.read_bytes()
    header = f._header(data)
    header[field] = 1
    with sqlite3.connect(database) as connection:
        reachable = {row[0]: row[1] for row in connection.execute("SELECT pageno,pagetype FROM dbstat('main')")}
    result = f._freelist_graph(data, tuple(pages), header, reachable, time.monotonic() + 10)
    assert result["state"] == "UNCLASSIFIED" and result["complete"] is False


@pytest.mark.parametrize("defect", ["missing_reachable", "reachable_orphan", "missing_page_one",
    "attached_count", "attached_cycle", "attached_reachable", "attached_orphan"])
def test_full_database_partition_and_attached_freelist_are_mandatory(tmp_path, defect):
    database, pages = detached_freelist_database(tmp_path, attached_freelist=True)
    data = bytearray(database.read_bytes())
    header = f._header(data)
    with sqlite3.connect(database) as connection:
        reachable = {row[0]: row[1] for row in connection.execute("SELECT pageno,pagetype FROM dbstat('main')")}
    if defect == "missing_reachable": del reachable[next(number for number in reachable if number != 1)]
    elif defect == "reachable_orphan": reachable[pages[0]] = "leaf"
    elif defect == "missing_page_one": del reachable[1]
    elif defect == "attached_count": header["freelist_page_count"] += 1
    elif defect == "attached_reachable": header["freelist_head"] = 2
    elif defect == "attached_orphan": header["freelist_head"] = pages[0]
    else: struct.pack_into(">I", data, (header["freelist_head"] - 1) * 512, header["freelist_head"])
    result = f._freelist_graph(bytes(data), tuple(pages), header, reachable, time.monotonic() + 10)
    assert result["state"] == "UNCLASSIFIED" and result["complete"] is False


def test_unconfirmed_native_scope_cannot_produce_allocator_evidence(tmp_path, monkeypatch):
    database, pages = detached_freelist_database(tmp_path)
    monkeypatch.setattr(f, "_native", lambda *args: ({"complete": False}, {}))
    report = inspect(database, pages)
    assert_held(report)
    assert report["analysis_state"] == "PARTIAL"
    assert report["freelist_graph"]["state"] == "UNAVAILABLE"


def test_zero_pages_alone_do_not_gain_the_new_detached_graph_interpretation(tmp_path):
    database, _ = native_database(tmp_path / "inspection", count=1, payload_size=50, index=False)
    pages = append_pages(database, [bytes(512), bytes(512)])
    report = inspect(database, pages)
    assert_held(report)
    assert report["freelist_graph"]["state"] == "UNCLASSIFIED"


@pytest.mark.parametrize("kind", ["leaf", "internal", "overflow"])
def test_native_full_page_duplicate_keeps_hold(tmp_path, kind, capsys):
    database, pages, selected, raw = with_duplicate(tmp_path, kind=kind)
    before = database.read_bytes()
    files_before = sorted(database.parent.iterdir())
    report = inspect(database, pages)
    assert_held(report)
    assert report["analysis_state"] == "COMPLETE"
    assert report["inspection_copy_unchanged"] is True
    assert report["inspection_sha256"] == hashlib.sha256(before).hexdigest()
    combined = hashlib.sha256(pages[0].to_bytes(8, "big") + raw).hexdigest()
    assert report["orphan_contents_sha256"] == combined
    assert report["pages"][0]["sha256"] == hashlib.sha256(raw).hexdigest()
    duplicate = report["pages"][0]["reachable_duplicate"]
    assert duplicate["state"] == "EXACT_FULL_PAGE_MATCH"
    assert duplicate["comparison_complete"] is True
    assert duplicate["reachable_match_count"] >= 1
    assert duplicate["reachable_match_page_types"][kind] >= 1
    if kind != "overflow":
        assert report["pages"][0]["structure"]["local_layout_validated"] is True
    else:
        assert report["pages"][0]["structure"]["classification"] == "UNIDENTIFIED_BYTES"
    assert database.read_bytes() == before
    assert sorted(database.parent.iterdir()) == files_before
    assert str(database) not in json.dumps(report)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("page_size", [512, 4096, 65536])
def test_local_parser_agrees_with_native_page_cell_and_payload_counts(tmp_path, page_size):
    database, rows = native_database(tmp_path / "inspection", page_size=page_size, count=160,
                                     payload_size=page_size + 100)
    data = database.read_bytes()
    header = f._header(data)
    seen_kinds = set()
    for number, kind, cells, payload, unused in rows:
        if kind == "overflow":
            continue
        raw = f._page(data, number, page_size)
        result = f._layout(raw, number, header, time.monotonic() + 30)
        assert result["classification"] == "BTREE_LOCAL_LAYOUT_CONSISTENT", (number, kind, result)
        assert result["cell_count"] == cells
        assert result["local_payload_byte_count"] == payload
        regions = result["byte_regions"]
        assert sum(region["byte_count"] for region in regions.values()) == page_size
        assert sum(region["nonzero_byte_count"] for region in regions.values()) == page_size - raw.count(0)
        assert sum(regions[key]["byte_count"] for key in ("unallocated", "freeblocks", "fragments")) == unused
        seen_kinds.add(result["btree_kind"])
    assert {"TABLE_LEAF", "INDEX_LEAF", "INDEX_INTERIOR"} <= seen_kinds


def test_native_deleted_cells_and_minimum_index_cells_are_classified(tmp_path):
    database, _ = native_database(tmp_path / "inspection", payload_size=90, count=150)
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA secure_delete=OFF")
        connection.execute("DELETE FROM private_table WHERE id%3=0")
        connection.execute("CREATE TABLE tiny(value)")
        connection.execute("CREATE INDEX tiny_index ON tiny(value)")
        connection.executemany("INSERT INTO tiny(rowid,value) VALUES(?,?)",
                               [(-1, None), (1, None), (2, 0), (3, 1), (2**63 - 1, None)])
        connection.commit()
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        rows = connection.execute("SELECT pageno,pagetype,ncell,payload,unused FROM dbstat('main')").fetchall()
    finally:
        connection.close()
    data = database.read_bytes()
    header = f._header(data)
    freeblocks = 0
    for number, kind, cells, payload, unused in rows:
        if kind == "overflow":
            continue
        result = f._layout(f._page(data, number, 512), number, header, time.monotonic() + 30)
        assert result["local_layout_validated"] is True
        assert result["cell_count"] == cells
        assert result["local_payload_byte_count"] == payload
        freeblocks += result["freeblock_count"]
    assert freeblocks > 0


def test_mutated_unused_byte_is_not_a_full_page_duplicate(tmp_path):
    database, rows = native_database(tmp_path / "inspection", payload_size=120, count=17, index=False)
    data = database.read_bytes()
    number = next(row[0] for row in rows if row[1] == "leaf" and row[0] != 1)
    raw = bytearray(f._page(data, number, 512))
    count = int.from_bytes(raw[3:5], "big")
    position = 8 + count * 2
    assert position < int.from_bytes(raw[5:7], "big")
    raw[position] ^= 0x5A
    pages = append_pages(database, [raw])
    report = inspect(database, pages)
    assert_held(report)
    observation = report["pages"][0]
    assert observation["structure"]["local_layout_validated"] is True
    assert observation["reachable_duplicate"]["state"] == "NO_FULL_PAGE_MATCH"


@pytest.mark.parametrize("mutation", ["duplicate_cell", "header_pointer", "fragment_count",
                                     "cell_count", "payload_varint", "freeblock_loop"])
def test_malformed_local_layout_does_not_gain_a_valid_btree_label(tmp_path, mutation):
    database, rows = native_database(tmp_path / "inspection", count=20, payload_size=60, index=False)
    number = next(row[0] for row in rows if row[1] == "leaf" and row[0] != 1 and row[2] >= 2)
    raw = bytearray(f._page(database.read_bytes(), number, 512))
    start = int.from_bytes(raw[8:10], "big")
    if mutation == "duplicate_cell":
        raw[10:12] = raw[8:10]
    elif mutation == "header_pointer":
        raw[8:10] = (3).to_bytes(2, "big")
    elif mutation == "fragment_count":
        raw[7] = 61
    elif mutation == "cell_count":
        raw[3:5] = b"\xff\xff"
    elif mutation == "payload_varint":
        raw[start:start + 9] = b"\xff" * 9
    else:
        raw[1:3] = start.to_bytes(2, "big")
        raw[start:start + 2] = start.to_bytes(2, "big")
        raw[start + 2:start + 4] = (4).to_bytes(2, "big")
    pages = append_pages(database, [raw])
    report = inspect(database, pages)
    assert_held(report)
    assert report["analysis_state"] == "COMPLETE"
    structure = report["pages"][0]["structure"]
    assert structure["classification"] == "BTREE_LAYOUT_INVALID"
    assert structure["local_layout_validated"] is False


@pytest.mark.parametrize("invalid_child", [0, 2**32 - 1])
def test_interior_pointer_bounds_are_checked_without_following_them(tmp_path, invalid_child):
    database, pages, _, raw = with_duplicate(tmp_path, kind="internal")
    changed = bytearray(database.read_bytes())
    start = (pages[0] - 1) * 512
    changed[start + 8:start + 12] = invalid_child.to_bytes(4, "big")
    database.write_bytes(changed)
    report = inspect(database, pages)
    assert_held(report)
    assert report["pages"][0]["structure"]["classification"] == "BTREE_LAYOUT_INVALID"


def test_native_empty_65536_byte_page_uses_zero_cell_offset_sentinel(tmp_path):
    database, _ = native_database(tmp_path / "inspection", page_size=65536, count=0, index=False)
    data = database.read_bytes()
    raw = f._page(data, 2, 65536)
    assert raw[5:7] == b"\0\0"
    result = f._layout(raw, 2, f._header(data), time.monotonic() + 30)
    assert result["local_layout_validated"] is True
    assert result["cell_count"] == 0
    assert result["byte_regions"]["unallocated"]["byte_count"] == 65536 - 8


@pytest.mark.parametrize("gap", [0, 1, 2, 3])
def test_freeblocks_that_native_sqlite_requires_coalescing_are_not_called_valid(tmp_path, gap):
    source = sqlite3.connect(":memory:")
    try:
        source.execute("PRAGMA page_size=512")
        source.execute("CREATE TABLE t(x)")
        source.execute("INSERT INTO t VALUES(NULL)")
        source.commit()
        data = source.serialize()
    finally:
        source.close()
    raw = bytearray(512)
    cell = 500 - gap
    first, second = cell + 4, 508
    raw[0] = 13
    raw[1:3] = first.to_bytes(2, "big")
    raw[3:5] = (1).to_bytes(2, "big")
    raw[5:7] = cell.to_bytes(2, "big")
    raw[7] = gap
    raw[8:10] = cell.to_bytes(2, "big")
    raw[cell:cell + 4] = bytes([2, 1, 2, 0])
    raw[first:first + 4] = second.to_bytes(2, "big") + (4).to_bytes(2, "big")
    raw[second:second + 4] = bytes([0, 0, 0, 4])
    native = sqlite3.connect(":memory:")
    try:
        native.deserialize(data[:512] + raw)
        native.execute("PRAGMA cell_size_check=ON")
        findings = native.execute("PRAGMA integrity_check").fetchall()
        assert findings != [("ok",)]
        assert any("free space corruption" in row[0] for row in findings)
    finally:
        native.close()
    directory = tmp_path / "inspection"
    directory.mkdir(mode=0o700)
    database = directory / "copy.sqlite3"
    database.write_bytes(data)
    pages = append_pages(database, [raw])
    report = inspect(database, pages)
    assert_held(report)
    assert report["analysis_state"] == "COMPLETE"
    assert report["pages"][0]["structure"]["classification"] == "BTREE_LAYOUT_INVALID"


def test_coalesced_freeblock_layout_agrees_with_native_sqlite():
    source = sqlite3.connect(":memory:")
    try:
        source.execute("PRAGMA page_size=512")
        source.execute("CREATE TABLE t(x)")
        source.execute("INSERT INTO t VALUES(NULL)")
        source.commit()
        data = source.serialize()
        raw = bytearray(512)
        raw[0] = 13
        raw[1:3] = (504).to_bytes(2, "big")
        raw[3:5] = (1).to_bytes(2, "big")
        raw[5:7] = (500).to_bytes(2, "big")
        raw[8:10] = (500).to_bytes(2, "big")
        raw[500:504] = bytes([2, 1, 2, 0])
        raw[504:508] = bytes([0, 0, 0, 8])
        source.deserialize(data[:512] + raw)
        assert source.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    finally:
        source.close()
    result = f._layout(bytes(raw), 2, f._header(data), time.monotonic() + 30)
    assert result["local_layout_validated"] is True
    assert result["freeblock_count"] == 1


@pytest.mark.parametrize("contents,classification", [
    (b"\0" * 512, "ZERO_FILLED"),
    ((PRIVATE.encode() + b"?").ljust(512, b"!"), "UNIDENTIFIED_BYTES"),
    (b"\x0d" + b"\xff" * 511, "BTREE_LAYOUT_INVALID"),
], ids=["zero", "unknown", "malformed_btree"])
def test_unknown_zero_and_malformed_pages_stay_held(tmp_path, contents, classification):
    database, _ = native_database(tmp_path / "inspection", count=3, index=False)
    pages = append_pages(database, [contents])
    report = inspect(database, pages)
    assert_held(report)
    assert report["analysis_state"] == "COMPLETE"
    assert report["pages"][0]["structure"]["classification"] == classification


def test_two_sorted_orphans_use_existing_capture_digest_framing(tmp_path):
    database, _ = native_database(tmp_path / "inspection", count=3, index=False)
    raw = [b"x" * 512, b"y" * 512]
    pages = append_pages(database, raw)
    report = inspect(database, pages[::-1])
    expected = hashlib.sha256()
    for number, contents in zip(pages, raw):
        expected.update(number.to_bytes(8, "big"))
        expected.update(contents)
    assert report["orphan_contents_sha256"] == expected.hexdigest()
    assert [value["page_number"] for value in report["pages"]] == pages
    assert report["orphan_byte_count"] == 1024


def test_sqlite_never_opens_any_filesystem_path(tmp_path, monkeypatch):
    database, pages, _, _ = with_duplicate(tmp_path)
    original = f.sqlite3.connect
    destinations = []
    def memory_only(destination, *args, **kwargs):
        destinations.append(destination)
        assert destination == ":memory:"
        return original(destination, *args, **kwargs)
    monkeypatch.setattr(f.sqlite3, "connect", memory_only)
    report = inspect(database, pages)
    assert report["analysis_state"] == "COMPLETE"
    assert destinations == [":memory:"]


@pytest.mark.parametrize("pages", [[], [True], [1], [0], [-1], [2, 2], [2.0], ["2"], [2**256],
                                    [2] * 100, {2}, None])
def test_invalid_orphan_input_is_bounded(tmp_path, pages):
    report = inspect(tmp_path / "missing", pages)
    assert_held(report)
    assert report["diagnostic_code"] == "INVALID_ORPHAN_PAGE_SET"


def test_out_of_range_orphan_is_rejected(tmp_path):
    database, _, _, _ = with_duplicate(tmp_path)
    report = inspect(database, [len(database.read_bytes()) // 512 + 1])
    assert report["diagnostic_code"] == "INVALID_ORPHAN_PAGE_SET"


@pytest.mark.parametrize("mode", ["reachable", "omitted_orphan", "extra_error", "saturated"])
def test_native_orphan_set_must_be_complete_and_exact(tmp_path, mode):
    database, rows = native_database(tmp_path / "inspection", count=6, index=False)
    if mode == "reachable":
        pages = [2]
    elif mode == "omitted_orphan":
        pages = append_pages(database, [b"x" * 512, b"y" * 512])[:1]
    elif mode == "saturated":
        pages = append_pages(database, [b"x" * 512] * 100)[:99]
    else:
        pages = append_pages(database, [b"x" * 512])
        data = bytearray(database.read_bytes())
        data[512] = 255
        database.write_bytes(data)
    report = inspect(database, pages)
    assert_held(report)
    assert report["analysis_state"] == "PARTIAL"
    assert report["native_reachability"]["complete"] is False
    assert report["native_reachability"]["orphan_set_reconfirmed"] is False
    assert all(value["reachable_duplicate"]["state"] == "NOT_PERFORMED" for value in report["pages"])


@pytest.mark.parametrize("missing", ["dbstat", "deserialize"])
def test_missing_native_feature_never_claims_complete_comparison(tmp_path, monkeypatch, missing):
    database, pages, _, _ = with_duplicate(tmp_path)
    if missing == "dbstat":
        def unavailable(*args):
            raise f.ForensicsError("DBSTAT_UNAVAILABLE")
        monkeypatch.setattr(f, "_dbstat_rows", unavailable)
    else:
        def unavailable(*args, **kwargs):
            raise RuntimeError(PRIVATE)
        monkeypatch.setattr(f.sqlite3, "connect", unavailable)
    report = inspect(database, pages)
    assert_held(report)
    assert report["analysis_state"] == "PARTIAL"
    assert report["native_reachability"]["complete"] is False
    assert report["pages"][0]["reachable_duplicate"]["comparison_complete"] is False


def test_user_schema_cannot_impersonate_native_dbstat(tmp_path):
    database, _ = native_database(tmp_path / "inspection", count=3)
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE dbstat(pageno,pagetype,ncell,payload,unused,mx_payload,pgoffset,pgsize)")
        connection.commit()
    finally:
        connection.close()
    pages = append_pages(database, [b"x" * 512])
    report = inspect(database, pages)
    assert_held(report)
    assert report["native_reachability"]["diagnostic_code"] == "DBSTAT_NAME_COLLISION"


class NativeRows:
    def __init__(self, rows):
        self.rows = rows
    def execute(self, sql):
        if "sqlite_compileoption" in sql:
            return OneRow((1,))
        if "count(*)" in sql:
            return OneRow((0,))
        return iter(self.rows)


class OneRow:
    def __init__(self, value):
        self.value = value
    def fetchone(self):
        return self.value


@pytest.mark.parametrize("rows", [
    [(1, "leaf", 0, 0, 400, 0, 512)] * 2,
    [(1, "corrupted", 0, 0, 400, 0, 512)],
    [(1, "leaf", -1, 0, 400, 0, 512)],
    [(True, "leaf", 0, 0, 400, 0, 512)],
    [(1, "leaf", 0, 0, 400, 0, 4096)],
    [(1, "leaf", 0, 513, 400, 0, 512)],
    [(3, "leaf", 0, 0, 400, 0, 512)],
    [(2, "leaf", 0, 0, 400, 0, 512)], [],
])
def test_malformed_duplicate_or_incomplete_dbstat_rows_are_rejected(rows):
    with pytest.raises(f.ForensicsError, match="DBSTAT_RESULT_INCOMPLETE"):
        f._dbstat_rows(NativeRows(rows), {"page_count": 2, "page_size": 512}, time.monotonic() + 30)


def test_native_iteration_error_discards_partial_reachability(tmp_path, monkeypatch):
    database, pages, _, _ = with_duplicate(tmp_path)
    original = f._dbstat_rows
    def incomplete(*args):
        original(*args)
        raise sqlite3.OperationalError(PRIVATE)
    monkeypatch.setattr(f, "_dbstat_rows", incomplete)
    report = inspect(database, pages)
    assert_held(report)
    assert report["native_reachability"]["complete"] is False
    assert report["pages"][0]["reachable_duplicate"]["comparison_complete"] is False


def test_page_hash_collision_does_not_replace_byte_comparison(monkeypatch):
    class Collision:
        def update(self, value):
            pass
        def digest(self):
            return b"d" * 32
        def hexdigest(self):
            return "d" * 64
    monkeypatch.setattr(f.hashlib, "sha256", lambda *args: Collision())
    result = f._duplicates(b"a" * 512 + b"b" * 512, (2,), {1: "leaf"}, 512, time.monotonic() + 30)
    assert result[2]["state"] == "NO_FULL_PAGE_MATCH"


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_nonempty_sidecar_blocks_before_native_inspection(tmp_path, monkeypatch, suffix):
    database, pages, _, _ = with_duplicate(tmp_path)
    database.with_name(database.name + suffix).write_bytes(PRIVATE.encode())
    monkeypatch.setattr(f.sqlite3, "connect", lambda *a, **k: pytest.fail("native database opened"))
    report = inspect(database, pages)
    assert_held(report)
    assert report["diagnostic_code"] == "SIDECAR_REVIEW_REQUIRED"


def test_empty_sidecars_remain_unchanged(tmp_path):
    database, pages, _, _ = with_duplicate(tmp_path)
    for suffix in f._SIDECARS:
        database.with_name(database.name + suffix).write_bytes(b"")
    report = inspect(database, pages)
    assert report["analysis_state"] == "COMPLETE"
    assert all(database.with_name(database.name + suffix).read_bytes() == b"" for suffix in f._SIDECARS)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory", "ancestor_symlink", "public_parent"])
def test_copy_boundary_rejects_unsafe_paths(tmp_path, kind, monkeypatch):
    database, pages, _, _ = with_duplicate(tmp_path)
    target = database
    if kind == "symlink":
        target = database.parent / "link.sqlite"
        target.symlink_to(database)
    elif kind == "hardlink":
        os.link(database, database.parent / "second.sqlite")
    elif kind == "directory":
        target = database.parent / "directory.sqlite"
        target.mkdir()
    elif kind == "ancestor_symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(database.parent, target_is_directory=True)
        target = alias / database.name
    else:
        database.parent.chmod(0o755)
    monkeypatch.setattr(f.sqlite3, "connect", lambda *a, **k: pytest.fail("unsafe path reached SQLite"))
    report = inspect(target, pages)
    assert_held(report)
    assert report["analysis_state"] == "UNAVAILABLE"


def test_fifo_without_writer_returns_without_blocking(tmp_path):
    directory = tmp_path / "inspection"
    directory.mkdir(mode=0o700)
    fifo = directory / "copy.sqlite"
    os.mkfifo(fifo, mode=0o600)
    code = ("import json,sys,time; sys.path.insert(0,sys.argv[1]); "
            "from gdw_orphan_forensics import inspect_orphan_pages; "
            "print(json.dumps(inspect_orphan_pages(sys.argv[2],[2],deadline=time.monotonic()+1)))")
    result = subprocess.run([sys.executable, "-B", "-c", code, str(ROOT / "scripts"), str(fifo)],
                            capture_output=True, text=True, timeout=2, check=True)
    report = json.loads(result.stdout)
    assert_held(report)
    assert report["diagnostic_code"] == "INSPECTION_COPY_UNAVAILABLE"
    assert result.stderr == ""


def test_size_bound_rejects_before_read_or_sqlite(tmp_path, monkeypatch):
    database, pages, _, _ = with_duplicate(tmp_path)
    monkeypatch.setattr(f, "MAX_DATABASE_BYTES", 1024)
    monkeypatch.setattr(f, "_read", lambda *a, **k: pytest.fail("oversized read"))
    report = inspect(database, [2])
    assert report["diagnostic_code"] == "INSPECTION_COPY_BOUND_EXCEEDED"


@pytest.mark.parametrize("mutation", ["size", "counter", "page_size", "reserved", "header_magic", "wal_mode"])
def test_inconsistent_or_unsupported_header_is_not_rewritten(tmp_path, mutation):
    database, pages, _, _ = with_duplicate(tmp_path)
    raw = bytearray(database.read_bytes())
    if mutation == "size":
        raw.extend(b"x")
    elif mutation == "counter":
        raw[24] ^= 1
    elif mutation == "page_size":
        raw[16:18] = (513).to_bytes(2, "big")
    elif mutation == "reserved":
        raw[20] = 255
    elif mutation == "header_magic":
        raw[0] = 0
    else:
        raw[18:20] = b"\x02\x02"
    database.write_bytes(raw)
    report = inspect(database, pages)
    assert_held(report)
    assert report["analysis_state"] == "UNAVAILABLE"
    assert database.read_bytes() == raw


@pytest.mark.parametrize("mutation", ["bytes", "replacement", "sidecar"])
def test_copy_or_sidecar_change_during_native_inspection_discards_result(tmp_path, monkeypatch, mutation):
    database, pages, _, _ = with_duplicate(tmp_path)
    original = f._native
    def change(*args):
        result = original(*args)
        if mutation == "bytes":
            raw = bytearray(database.read_bytes())
            raw[-1] ^= 1
            database.write_bytes(raw)
        elif mutation == "replacement":
            replacement = database.with_suffix(".replacement")
            replacement.write_bytes(database.read_bytes())
            replacement.replace(database)
        else:
            database.with_name(database.name + "-wal").write_bytes(b"x")
        return result
    monkeypatch.setattr(f, "_native", change)
    report = inspect(database, pages)
    assert_held(report)
    assert report["analysis_state"] == "UNAVAILABLE"
    assert report["diagnostic_code"] in {"INSPECTION_COPY_CHANGED", "SIDECAR_REVIEW_REQUIRED"}
    assert "pages" not in report


@pytest.mark.parametrize("value", [True, None, "1", float("nan"), float("inf"), -float("inf")])
def test_invalid_deadline_never_opens_input(tmp_path, value, monkeypatch):
    monkeypatch.setattr(f.os, "open", lambda *a, **k: pytest.fail("invalid deadline opened a path"))
    report = inspect(tmp_path / "missing", [2], deadline=value)
    assert report["diagnostic_code"] == "INVALID_DEADLINE"


def test_expired_deadline_never_opens_input(tmp_path, monkeypatch):
    monkeypatch.setattr(f.os, "open", lambda *a, **k: pytest.fail("expired deadline opened a path"))
    report = inspect(tmp_path / "missing", [2], deadline=time.monotonic() - 1)
    assert report["diagnostic_code"] == "FORENSICS_DEADLINE_EXHAUSTED"


def test_native_progress_interrupt_is_not_swallowed_as_unavailable(tmp_path, monkeypatch):
    database, pages, _, _ = with_duplicate(tmp_path)
    data = database.read_bytes()
    calls = 0
    def clock():
        nonlocal calls
        calls += 1
        return calls
    monkeypatch.setattr(f.time, "monotonic", clock)
    with pytest.raises(f.ForensicsError, match="FORENSICS_DEADLINE_EXHAUSTED"):
        f._native(data, tuple(pages), f._header(data), 8)
    assert calls >= 8


@pytest.mark.parametrize("phase", ["last_hash", "close"])
def test_last_read_and_cleanup_deadlines_cannot_return_complete(tmp_path, monkeypatch, phase):
    database, pages, _, _ = with_duplicate(tmp_path)
    now = [0]
    monkeypatch.setattr(f.time, "monotonic", lambda: now[0])
    if phase == "last_hash":
        original = f._read
        def delayed(*args, **kwargs):
            value = original(*args, **kwargs)
            if not kwargs["retain"]:
                now[0] = 11
            return value
        monkeypatch.setattr(f, "_read", delayed)
    else:
        original = f.os.close
        def delayed(descriptor):
            is_file = stat.S_ISREG(os.fstat(descriptor).st_mode)
            original(descriptor)
            if is_file:
                now[0] = 11
        monkeypatch.setattr(f.os, "close", delayed)
    report = inspect(database, pages, deadline=10)
    assert_held(report)
    assert report["diagnostic_code"] == "FORENSICS_DEADLINE_EXHAUSTED"
    assert report["analysis_state"] == "UNAVAILABLE"


def test_private_exception_text_is_not_returned_or_logged(tmp_path, monkeypatch, capsys):
    database, pages, _, _ = with_duplicate(tmp_path)
    def failure(*args, **kwargs):
        raise sqlite3.DatabaseError(PRIVATE)
    monkeypatch.setattr(f, "_snapshot", failure)
    report = inspect(database, pages)
    assert_held(report)
    assert report["diagnostic_code"] == "FORENSICS_UNAVAILABLE"
    assert capsys.readouterr() == ("", "")
