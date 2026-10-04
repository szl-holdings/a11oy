# GDW private capture qualification

This is an acquisition and analysis step. It does not restore a database, admit a
runtime, change an original object, or add a Space publisher. The canonical
`hf-sync.yml` prerequisite remains failed even when the analysis succeeds.

## Incident and immutable input

The first preservation run is GitHub Actions run `37223162231`, attempt `1`, at
protected A11oy source `67e87fc69c310507f84733bead09109100203a68`. Its safe report
records two private bucket copies and a verified private manifest. The canonical
Space was already `PAUSED`; preservation did not change its provider state.

The GDW copy retains generation `aa2f2a616a214103b1f9566321c80e5b`, schema version
`4`, and 448 receipt rows. Its SQLite integrity result reports unreferenced
pages. The Series-A copy retains instance
`store_9c9e2d337fb340cf930037a276463d99` and 46,693 receipt rows, with a successful
SQLite integrity check. Neither database has a captured journal, WAL, or SHM
companion. These observations establish the captured state, not completeness of
all writes that might have been acknowledged before the incident.

The source-pinned capture report contains only identities, digests, counts,
generation IDs and safe classifications. The raw SQLite files and private
manifest remain in the original private `SZLHOLDINGS/szl-evidence` **bucket**.
The same-named private **dataset** is a separate resource and is not used to store
or retrieve capture or candidate bytes.

## Read-only acquisition

`scripts/qualify_gdw_store_recovery.py` checks that it is running from current
protected A11oy main with the existing canonical GitHub and Hugging Face
credentials. It uses `bucket_info`, `get_bucket_paths_info` and
`download_bucket_files` through an explicitly read-only wrapper. A separate
`dataset_info` request observes only the existing private evidence dataset's
immutable revision, privacy and a digest of its resource-group metadata. It does
not fetch dataset files or test writes. Missing metadata leaves that independent
storage boundary unqualified; a null group value does not prove equal audiences.

Every download uses the preserved copy's observed Xet identity, with exact size
and independent SHA-256 readback. The private manifest must bind the same capture,
source, file list and generation evidence as the source-pinned safe reference.
The helper rechecks remote identities and original local hashes after analysis.
It never resolves an active database path as a replacement input and never opens
the preserved originals with SQLite.

## Disposable candidate evaluation

Only another local copy is opened with SQLite. Nonempty `-journal`, `-wal` or
`-shm` companions stop evaluation, including companions that SQLite would silently
ignore. Absent or zero-byte companions are recorded explicitly.

A healthy database is evaluated using SQLite's native backup API. A database
whose **complete, bounded** integrity result contains only unreferenced pages is
eligible for a separate `VACUUM INTO` evaluation only if every referenced orphan
page is present, within the file's declared page bounds, and entirely zero.
Nonzero orphan pages require further review because they may contain otherwise
unaccounted data. A saturated integrity result, a foreign-key violation, a schema
outside the known store, or an invalid receipt binding stops evaluation.

Canonical run `37226932409`, at source
`ada55417536f43af6ed0a32304774910a50fb42b`, observed that the two GDW orphan
pages contain nonzero bytes. The safe qualification report has SHA-256
`31a14b1079e398272bd19361e3970c4d03d927d8caef36093bebeec2adff7909`.
It therefore produced no GDW candidate. Reachable GDW receipt bindings and the
exact historical signed audit remained verifiable; Series A passed logical
continuity checks. Those observations do not explain the orphan bytes.

The source-owned orphan forensic helper adds bounded descriptive evidence on
that existing hold branch. It reads only the disposable inspection copy,
deserializes fixed bytes into an in-memory SQLite connection, reconfirms the
orphan set, and uses native `dbstat` reachability when available. It reports
local page-layout classifications, counts and digests, and compares every byte
of selected orphan pages with fully enumerated reachable pages. It never emits
page bytes, row values, schema names or arbitrary SQLite diagnostics. The
qualifier binds the helper's full-input and selected-page hashes to the same
captured bytes before attaching that evidence to its existing safe report.

Even an exact full-page duplicate remains a descriptive observation: record
equivalence and permission to discard are false. Unavailable or incomplete
native reachability is labeled explicitly. Every nonzero-page result retains
the existing no-candidate, no-restore and no-deployment hold; this extension
cannot enable `VACUUM`, `.recover`, object publication or a runtime restart.

The candidate must pass SQLite integrity and foreign-key checks. Its schema,
declared column metadata, every declared stored value, duplicate-row multiplicity,
`sqlite_sequence`, generation, receipt bytes and checked receipt bindings must
match the disposable source view. Type and length framing distinguishes text,
blobs, integers, floating-point bit patterns and NULL. This comparison excludes
physical page layout and hidden rowids; every application table must have a
declared primary key, or evaluation stops. It does not establish the contents of inaccessible or historically
lost rows.

Historical source-bound receipts add a separate continuity anchor: the previous
successful runtime proof at source
`5e014855a274825f4d46ce91cb3396cabd20f99a` observed the same generations, GDW audit
sequence `87`, and Series-A receipt sequence `46686`. The qualifier checks that
these exact anchors remain in the captured and candidate views. Retaining those
anchors does not prove that every subsequent acknowledgement was persisted.

## Privacy and limits

The private temporary directory is mode `0700`. SDK caches, downloaded objects,
inspection copies and candidate databases remain inside it and are removed when
the helper finishes. SDK output, native descriptor output and exception prose are
suppressed while private material is handled. Public output is a bounded metadata
report: fixed diagnostic codes, hashes, row counts, generations and scoped
verification results. It contains no database pages, SQL statements, row
payloads, raw provider errors, signing keys or credential values.

The helper enforces per-file and aggregate byte bounds, row and schema bounds,
bounded report reads, SQLite progress checks, and a process deadline. The final
deadline check occurs after the final hash and provider readback, before any
qualified state is emitted. The Actions artifact allowlist adds only
`gdw-store-recovery-qualification.json`; no private directory or broad glob is
eligible for upload.

## Meaning of success

`LOGICAL_CONTINUITY_VERIFIED` means the exact captured reachable logical state
survived the documented disposable transformation and retained the checked
historical anchors. The report still declares `restore_admitted: false`,
`deployment_admitted: false` and `durable_storage_qualified: false`.

The exact historical GDW audit signature is reverified against the pinned public
key without loading a signer or private key. Full historical signature verification and external outbox artifact verification
are separate qualifications. A later reviewed change must restore only a
qualified existing generation onto local POSIX storage, prove acknowledged
immutable snapshot publication, and fence every runtime writer. Bucket mount
`fsync`, journal mode, an elapsed sleep or a successful provider restart is not a
remote transaction commit acknowledgement.

## Primary implementation references

- [SQLite online backup API](https://www.sqlite.org/backup.html)
- [SQLite recovery limitations](https://www.sqlite.org/recovery.html)
- [SQLite database files over a network](https://www.sqlite.org/useovernet.html)
- [Hugging Face bucket access and managed Space mounts](https://huggingface.co/docs/hub/en/storage-buckets-access)
- [Pinned Hugging Face SDK source](https://github.com/huggingface/huggingface_hub/tree/0c92853b8e07bc50ee0817e307e9fd88194dd4f3)
- [Canonical preservation run](https://github.com/szl-holdings/a11oy/actions/runs/37223162231)
- [Previous runtime proof run](https://github.com/szl-holdings/a11oy/actions/runs/37216172576)
