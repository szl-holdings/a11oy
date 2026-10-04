# Preserve the canonical private stores before recovery

The canonical Space failed startup on 2026-10-04 because GDW's SQLite integrity
check reported unreferenced pages. Its current `/data` volume is the private
`SZLHOLDINGS/szl-evidence` bucket. A replacement runtime must not open, migrate,
or initialize these originals before a preservation record exists.

`scripts/preserve_hf_gdw_store.py` is an acquisition and inspection preflight in
the existing canonical `hf-sync.yml`. It runs inside `manual-prerequisites`,
before live signer probes, resume, deployment, or post-deployment configuration.
It uses that job's existing `HF_TOKEN` and the workflow's existing `GH_TOKEN`.
The single canonical publisher and its concurrency group are unchanged.

**Preservation does not restore service or qualify deployment.** The helper
always exits 2 and reports `deployment_admitted: false`. After a complete
capture, the diagnostic is `STORAGE_RECOVERY_REQUIRED`. A later source change
must implement and review the durable storage and restore contract. There is
no skip, repair, overwrite, auto-promote, or empty-database option.

## Exact scope

The source declares two active database paths in one existing private bucket:

| Store | Bucket path |
|---|---|
| GDW | `a11oy/gdw/gdw.sqlite3` |
| Series-A | `a11oy/series-a/control-plane-v2.sqlite3` |

For each, the helper requests exactly the database plus `-journal`, `-wal`, and
`-shm`. Missing sidecars are explicit evidence. Either missing database blocks
the capture; nothing creates replacement state. It does not enumerate unrelated
bucket contents or read Space secrets/variables.

The only remote mutation is the creation of a capture under:

```text
a11oy/incident-preservation/v1/<run>-<attempt>-<source-sha>-<random-capture-id>/
```

It contains exact original objects and a preservation manifest. Originals,
existing evidence, Space code/configuration, hardware, volume definitions, DNS,
models, datasets, and other repositories are outside the helper's effect scope.
No delete, pause, restart, journal conversion, SQL repair, or restore API exists
in the helper.

## Capture sequence and admission boundaries

1. Require canonical GitHub Actions main context and recheck that the exact
   source remains current `szl-holdings/a11oy` main.
2. Require the bucket's metadata to say `private: true`. Require the canonical
   `/data` mount to point to that entire bucket, read-write, with no conflicting
   nested mount. Require provider state `RUNTIME_ERROR` or `PAUSED`.
3. Observe exact object identities, wait five seconds, then observe them again
   while still stopped. Compare path membership, Xet hash, size, modification
   time, and upload time. Any new/removed/changed sidecar blocks the capture.
4. Download the observed `BucketFile` objects into a private temporary directory.
   Passing objects to the pinned SDK binds reads to their Xet hashes. Verify
   local regular-file identity, size, and SHA-256. Recheck original metadata,
   source ownership, and stopped provider state before private copying.
5. Require all capture destinations to be absent, then copy the exact observed
   Xet hashes server-side into the new private prefix. Read back every copy's
   hash/size and download each copy by its observed content identity. The
   independent local SHA-256 values must equal the original capture.
6. Inspect disposable local copies with SQLite opened `mode=ro`,
   `query_only=ON`, extension loading disabled, and `trusted_schema=OFF`.
   No runtime constructor is imported. Record bounded integrity classification,
   foreign-key violation counts, schema digest, known table counts, and a valid
   database generation identifier. Verify captured original bytes again.
7. Recheck ownership, stopped state, and original identities; write a new private
   manifest, then verify its exact content identity and SHA-256 by downloading
   it. Original identities are checked again before declaring preservation
   `VERIFIED`.

The exact path request contains eight entries. Files are capped at 256 MiB each
and 768 MiB total. SQLite inspection is limited to 30 seconds per database,
100 integrity rows, 1,000 reported foreign-key violations, and 1,000 schema
objects. The process has a 420-second deadline inside the existing 10-minute
job timeout. A bound, missing identity, metadata inconsistency, incomplete copy,
unknown provider state, or loss of source ownership remains blocked.
The process checks an authoritative monotonic deadline after SQLite inspection
and before further private writes or a verified result. This also covers SQLite
translating a signal raised inside its progress callback into `SQLITE_INTERRUPT`.

Two stable stopped-state observations are acquisition evidence, **not proof of
a distributed writer fence or a provider flush barrier**. The report never
claims that a captured corrupt file is a valid restore. A provider or another
authorized actor can still change non-versioned bucket paths. Captures use
unpredictable, never-reused names and destination absence checks; the SDK does
not offer atomic create-only writes or WORM immutability. The verified content
hashes and exact manifest permit later detection of changes.

## Pinned SDK semantics

The helper uses the controller's existing `huggingface_hub==1.23.0`, whose
official release tag resolves to commit
`0c92853b8e07bc50ee0817e307e9fd88194dd4f3`.

The relevant primary implementation is
[the pinned HfApi source](https://github.com/huggingface/huggingface_hub/blob/0c92853b8e07bc50ee0817e307e9fd88194dd4f3/src/huggingface_hub/hf_api.py):

- `get_bucket_paths_info(bucket_id, paths)` requests exact file paths, omits
  absent paths, and returns each file's Xet identity and size.
- `download_bucket_files(..., files=[(BucketFile, local_path)])` downloads the
  supplied content identity; passing a string instead re-resolves the path.
- `batch_bucket_files(copy=[("bucket", source_bucket, xet_hash, destination)])`
  performs a server-side copy of the given content hash.
- Bucket batches are explicitly nontransactional. A failed response can leave
  some or all files copied. The helper performs readback, never retries the
  mutation blindly, and never removes partial evidence.

The SDK normally retries bucket batch requests internally. The helper installs
the SDK's public HTTP client factory and makes only the exact canonical bucket
batch POST a single attempt. A transport error or non-success status becomes a
fixed, non-retryable exception; the helper then resolves the outcome through
identity and byte verification. It retains normal SDK behavior for read calls.

The helper refuses a different SDK version or endpoint. It does not upgrade
the runtime or alter any existing provider's configuration.

## Public evidence and private bytes

The existing canonical prerequisite artifact includes only these exact files:

```text
manual-prerequisites.json
gdw-store-preservation.json
```

When acquisition blocks the job, the former may be absent and the preservation
report is retained. Captured databases, journal companions, inspection copies,
SDK caches, and raw provider responses are never uploaded to Actions. They live
in a private temporary directory and are removed when the process exits. Exact
preservation objects remain in the already private bucket.

The public report contains canonical paths, hashes, sizes, bounded counts,
validated generation identifiers, fixed diagnostics, and source/provider
identities. It contains no SQL, row payloads, raw SQLite error text, provider
exception strings, token values, or secret readback. A private manifest is also
a preservation record; it never becomes a `latest` pointer or restore selector.

SQLite header metadata records read/write format versions and the SQLite
version number that last modified the file. The inspector's SQLite version is
reported separately. The deployed runtime's actual version remains
`UNAVAILABLE` until observed independently. This distinction matters because
multiple mechanisms can produce corruption; an on-disk journal format alone
does not establish the runtime build or a unique cause.

## Follow-on recovery

A reviewed recovery procedure must retain these exact originals and inspect
their row/schema/receipt continuity before proposing a candidate. Native SQLite
backup creates a consistent snapshot of a readable database; successful backup
does not prove that a previously corrupt database has been repaired. Any
`VACUUM INTO`, reconstruction, or `.recover` evaluation must create a separate
candidate and account for original rows, tombstones, receipt chains, generation,
and outbox state. This preflight performs none of those operations and cannot
promote their result.

The durable architecture must put the live database and its engine on storage
with appropriate SQLite synchronization and locking semantics. Closed immutable
backup generations can be transferred to a bucket through explicit API calls,
but periodic snapshots alone do not preserve every acknowledged write. The
follow-on design needs a durable acknowledgement boundary and writer fencing,
plus startup selection of an explicitly verified existing generation.

Primary storage references:

- [HF bucket access and managed Space mounts](https://huggingface.co/docs/hub/en/storage-buckets-access)
- [HF mount consistency model](https://github.com/huggingface/hf-mount)
- [SQLite network filesystem requirements](https://www.sqlite.org/useovernet.html)
- [SQLite backup API](https://www.sqlite.org/backup.html)
- [SQLite recovery limitations](https://www.sqlite.org/recovery.html)
- [SQLite WAL documentation and version-specific caveats](https://www.sqlite.org/wal.html)

## Qualification and review

The existing GDW CI job runs `tests/test_hf_gdw_preservation.py`. Its real SQLite
fixtures cover healthy state, an unreferenced-page defect, malformed headers,
sidecar preservation, private-output boundaries, unstable object membership,
state/source changes, partial batches, lost successful responses, destination
collisions, and byte mismatches. Workflow negative controls reject moving the
preflight after runtime qualification or widening the public artifact paths.

The existing exact-main admission, strict job/dependency graph, and canonical
concurrency checks remain active. Workflow changes retain the existing
CODEOWNERS reviewers, `@szl-holdings/devops` and `@szl-holdings/core-team`; no new
review bypass or approval policy is introduced.
