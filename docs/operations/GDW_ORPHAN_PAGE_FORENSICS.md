<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# GDW orphan-page forensic observations

[`scripts/gdw_orphan_forensics.py`](../../scripts/gdw_orphan_forensics.py) adds
inspection evidence to the existing nonzero orphan-page hold. It has no repair,
candidate creation, restoration, deployment, or provider capability. Every
result retains `state: HELD` and false admission fields. A complete inspection
is not a qualified recovery result.

## Input boundary

Call `inspect_orphan_pages(inspected, pages, deadline=deadline)` only with the
disposable inspection copy and page numbers from the complete, source-qualified
integrity result for that same copy. The caller retains capture/source ownership
checks. Before attaching the result, bind `inspection_sha256` to the captured
database SHA256 and `orphan_contents_sha256` to the existing qualifier's selected
page digest. The latter hashes each sorted page number as eight big-endian bytes,
then that complete page's bytes.

The helper accepts at most 64 MiB and 99 distinct orphan pages. It requires an
absolute path through directories without symlinks, an owner-private immediate
parent, and a regular, single-link input file. Files created with mode 644 inside
that private directory are supported. Every observed journal, WAL, or SHM
companion must be an unchanged empty regular file; nonempty companions retain a
separate review requirement. WAL-format database images are unsupported and are
never rewritten to make inspection possible.

Binary reads use bounded, nonblocking, no-follow descriptors. The complete
snapshot is hashed before inspection. The helper rechecks the file and directory
identity, companion observations, and complete content hash afterward. SQLite
opens only `:memory:` and deserializes the unchanged snapshot. It never opens the
input path. Extension loading is disabled, trusted-schema execution is disabled,
and the native connection is restricted to queries.

The caller's monotonic deadline is capped at 60 seconds for this helper. Reads,
page/cell loops, native query progress, comparison, and final verification check
that deadline. A late read, interrupted query, or slow cleanup cannot return a
complete result. These are progress and final-return checks; the enclosing
qualifier retains its process/job execution limits.

## Evidence and its limits

The per-page result contains the source-qualified page number, size, nonzero
byte count, SHA256, and a fixed structural classification. Recognized b-tree
layouts undergo bounded header, cell-pointer, varint, local payload, freeblock,
fragment, and page-reference checks. Byte-region counts distinguish allocated
cell space from unused, free, fragment, and reserved space. This is local layout
evidence; it does not decode records or follow orphan overflow chains. Pages
without a recognizable b-tree layout remain unidentified. A possible pointer in
arbitrary bytes is not sufficient to label an overflow or freelist page.

Native `integrity_check` must reconfirm exactly the supplied orphan set, without
other findings or a saturated result. Native `dbstat`, where available, then
enumerates schema b-tree and associated overflow pages. Its scope excludes
freelist, pointer-map, and lock pages. Missing support, name collisions, invalid
rows, duplicate page numbers, or interrupted enumeration cannot yield a complete
comparison. Object names, schema text, traversal paths, and SQLite error strings
are not included in the report.

### Detached freelist layout

The separate `freelist_graph` observation combines that native scope with a
bounded allocator traversal. It reads the attached freelist head/count and
pointer-map settings from header offsets 32/36/52/64 in the same immutable
snapshot. Its first supported scope requires zero reserved bytes per page,
no pointer-map mode, and no lock-byte page. The 64 MiB input bound is below the
1 GiB lock-byte boundary. Unsupported modes remain unclassified.

The complete attached freelist must match its header count and have no cycles,
duplicate ownership, invalid references or overlap with native reachable/orphan
pages. Reachable, attached-free and orphan sets must form a complete disjoint
partition of the database. Attached free-page payloads are not exported.

For the exact orphan set, the helper considers at most 99 possible roots and
requires one complete connected trunk chain. Every next/leaf pointer must refer
to an exclusively owned orphan page. Trunks must leave their undeclared bytes
zero, including SQLite's six compatibility slots; all detached leaf pages must
be entirely zero. At least one leaf pointer is required. A disconnected graph,
nonzero padding, nonzero leaf, unowned page, cycle or duplicate rejects the
interpretation. The result reports bounded pointer metadata and structural/zero
byte counts. It does not emit the original page contents.

`STRUCTURALLY_ACCOUNTED` describes this layout only. The helper still returns
`HELD` with every candidate/discard/restore/deployment field false. This evidence
does not establish transaction history, pre-capture losslessness, later writes
or record equivalence. The qualifier independently owns candidate policy: its
[reviewed disposable-only exception](GDW_STORE_RECOVERY_QUALIFICATION.md#byte-bound-detached-freelist-exception)
reconstructs and hashes every selected page before permitting any candidate.

Full-page equality is checked against the completely enumerated reachable set.
SHA256 only selects possible matches; the helper then compares every byte,
including unused and reserved bytes. File offsets are derived from the validated
page number and header size, independently of `dbstat` offset metadata. Match
results expose counts, fixed page types, and a digest of sorted matching page
numbers. They do not expose page or row payloads.

`record_comparison` remains `UNAVAILABLE`, `record_equivalence_verified` remains
false, and `all_bytes_semantically_explained` remains false. Even an exact
full-page match cannot release the existing hold or justify discarding an orphan.

## Offline validation

[`tests/test_gdw_orphan_forensics.py`](../../tests/test_gdw_orphan_forensics.py)
uses native synthetic SQLite databases, including 512-, 4096-, and 65536-byte
pages, indexes, overflow, deleted cells, and small/large rowids. It checks local
counts against native `dbstat`, exact and partial page differences, a simulated
hash collision, malformed inputs, incomplete native results, private output,
sidecars, FIFO/symlink/hardlink boundaries, content replacement, and deadlines.
No actual private database or provider access is required.

```sh
PYTHONPATH=tests:scripts:. python -B -m pytest -q tests/test_gdw_orphan_forensics.py
```

## Primary references

- [SQLite database file format](https://www.sqlite.org/fileformat.html), sections
  1.3 through 1.7, including header freelist fields, pointer-map settings,
  lock-byte pages and the complete trunk/leaf format.
- [SQLite DBSTAT virtual table](https://www.sqlite.org/dbstat.html), scope and
  per-page output.
- [SQLite deserialization interface](https://www.sqlite.org/c3ref/deserialize.html),
  in-memory reconstruction and the WAL limitation.
- [SQLite btree.c](https://www3.sqlite.org/matrix/ev/src/btree.html), minimum
  four-byte cell storage.
