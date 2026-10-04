# Private GDW snapshot and fencing protocol

This source defines the provider boundary that replaces SQLite writes on the
managed bucket mount. The canonical acquisition and managed proof integration
is described in [the cutover contract](gdw-managed-storage-cutover.md).
Source implementation does not establish runtime activation or a provider change.
The later native run `37237652697` qualified both captured candidates after the
detached freelist pages were completely accounted for. That result preserves the
captured data and still requires the private restore/admission contract; it does
not establish a successful live cutover.

## Storage contract

Working SQLite files belong on a private local POSIX filesystem. The runtime
gate owns one lifetime local process lock and serializes transactions across
both stores. It commits locally, closes native SQLite backups of both stores,
verifies retained artifacts, publishes and reads back the snapshots, then
conditionally commits the exact snapshot pair to the private evidence dataset.
Only the final verified result permits an acknowledgement. Any uncertain
provider outcome poisons the writer and blocks subsequent reads, replays and
writes until a new process restores a verified current head.

Raw database and artifact bytes stay in the existing private bucket
`SZLHOLDINGS/szl-evidence`. The existing private dataset with the same ID stores
only a strictly validated metadata manifest, its immutable operation history,
and a digest-bound admission record. These are separate provider resources.
The metadata observation does not establish equivalent resource-group audiences.

| Surface | Paths | Allowed effects |
| --- | --- | --- |
| Snapshot objects in the private bucket | `a11oy/durable-store/v1/objects/<uuid>/<label>-<sha256>.sqlite3` | One add to a fresh content-bound identity, then exact Xet/size/SHA readback |
| Retained artifact objects in the private bucket | `a11oy/durable-artifacts/v1/<logical-path-sha256>/<bytes-sha256>.json` | Exact existing-object verification, or one fresh add and readback |
| Current metadata in the private dataset | `a11oy/durable-store/v1/head.json` | Native `parent_commit` conditional commit with operation history |
| Metadata history in the private dataset | `a11oy/durable-store/v1/history/<operation-uuid>.json` | A new immutable operation record in the same conditional commit |
| Initial admission in the private dataset | `a11oy/durable-store/v1/admissions/<sha256>.json` | New strictly validated metadata in the initial conditional commit |

The provider storage adapter never deletes objects, resets a database, creates a
repository, changes visibility, configures or restarts a Space, or reads a secret
value into an artifact or diagnostic. Canonical pause, configuration, and the
existing publisher remain separate gated steps. Failed or ambiguous additions may leave
unreferenced objects. They are never automatically deleted or promoted.

The bucket API has no absent-only conditional add. Fresh UUID/content hashes,
an absence-or-identical check and exact readback constitute a cooperative
protocol for admitted writers. They do not constrain a legacy writer that
ignores the protocol or an arbitrary actor with equivalent credentials. The
initial cutover therefore requires the legacy runtime to be stopped and the
canonical source publisher to be the sole deployment authority.

## Metadata transitions

`BOOTSTRAP` requires an absent HEAD at the exact dataset parent, a fresh history
identity, a fresh admission identity, and the coordinator's strict binding of
the complete admission to the source and initial snapshot pair. HEAD, history
and admission are added atomically by the native dataset commit API. An
existing HEAD is never overwritten by bootstrap.

`CLAIM` restores the complete previous snapshot pair and preserves its data
identities while advancing the epoch under the local lifetime lock. A process
claims once. `COMMIT` keeps that writer and epoch, advances the metadata
sequence, and preserves both database generations. Series A receipt count and
sequence cannot regress. A commit with no new receipt cannot change the native
receipt head, sequence, or ordered receipt-row digest. Native snapshot
inspection additionally locates the previous acknowledged Series A terminal
sequence/hash at the exact previous prefix count. At that point the ordered
prefix must also have the previous `receipt_rows_sha256`. This binds every
SQL receipt sequence and exact stored payload/envelope string; native envelope
chaining alone does not cover those SQL identities or raw serialization bytes.

The mandatory Series A row digest starts with
`szl.series-a-receipt-rows/v1` plus a newline. It then hashes each row, ordered by
sequence, as one compact ASCII JSON array plus newline, with fields
`sequence`, `receipt_id`, `kind`, `payload`, `envelope`, `previous_hash`,
`receipt_hash`, and `created_at`. The JSON string fields preserve their exact
stored values. An empty history uses the domain prefix's SHA256. The digest is
metadata; row values are never published. This extends the unactivated draft
snapshot/admission contract and requires a new exact source admission.

GDW has no global receipt sequence. Its summary uses sequence zero and a
deterministic digest of ordered receipt identities, including tombstones. That
digest is a snapshot summary, not an invented native chain. Native authorized
GDW compaction may reduce retained row counts; previous complete immutable
snapshots remain available. The protocol does not reinterpret retention policy.

Only a definite HTTP 412 rejection permits a bounded rebase. Before another
attempt, ordinary commits must observe their exact prior HEAD unchanged;
bootstrap must still observe no HEAD. A timeout, connection loss, malformed
response, cleanup failure or expired deadline cannot cause a second submission
or an acknowledgement. A returned commit SHA alone is insufficient: HEAD,
history, admission when applicable, and current ownership are read back.

This matters because the pinned SDK removes no-op additions and can return the
latest repository SHA without submitting `parent_commit`. Fresh operation bytes
and history identities plus exact immutable readback are required.

## Provider and runtime interfaces

The runtime client is exactly `huggingface_hub==1.31.0`, already declared by the
runtime dependency manifest. The SDK worker validates that installed version.
It receives the existing canonical `HF_TOKEN` through its inherited process
environment. Credentials never appear in process arguments, protocol messages,
diagnostics or metadata.

- `WorkerFenceBackend` supplies observe/read/conditional metadata operations.
- `WorkerSnapshotStore.publish(paths, deadline)` accepts two closed native
  backups and requires a callback to the current acknowledged `Head`.
- `WorkerSnapshotStore.restore(head, deadline)` downloads both exact snapshots
  to absent private working paths; it never adopts an old local file or creates
  an empty database.
- `WorkerSnapshotStore.publish_artifact(path, key, digest, deadline)` implements
  the artifact cache's exact private-object callback.
- `load_admitted_head(directory, deadline)` performs only reads, returning the
  immutable Head, its exact admission bytes and observed private dataset
  resource-group digest. An environment-provided hash cannot grant admission.
- `bootstrap(...)` uses the startup module's schema-only `parse_admission` and
  `validate_bootstrap_binding` before any metadata mutation. Missing or
  unqualified coordinator code fails closed.

Each provider operation runs in a separate process with a parent-enforced total
deadline, capped at 120 seconds and also bounded by the caller's shorter budget.
An overdue process group is killed. The parent removes its exact private
staging directory and checks the deadline again before returning success.
Individual HTTP timeouts alone are not treated as an operation deadline.

Private local files must be owned single-link regular files, mode 0600 or 0400,
under owned mode-0700 directories without symlink components. Files are frozen
before native uploads. Their size, SHA, inode and change metadata are checked;
the SDK's upload return is not treated as a content digest. Only observed
`BucketFile` identities are used for downloads, followed by full byte hashing
and remote identity/private-bucket re-observation.

Snapshot inspection uses a closed private copy in read-only immutable mode,
requires DELETE-format headers and no sidecars, and checks native integrity,
foreign keys, expected application tables with declared keys, schema version,
generation and receipt digest/binding/chain fields. It imports no signing key
loader and does not claim full historical signature verification.

## Activation prerequisites and evidence limits

Activation additionally requires a source-reviewed recovery candidate, complete
retained-artifact disposition, a real protected-main acquisition/admission,
exact bootstrap source and installed critical-file/dependency bytes, stopped
legacy writer evidence, and the reviewed startup coordinator before any store
constructor. Every critical storage/admission/import/lock dependency is part of
that source contract. A nonzero environment SHA or a signing-key observation
alone does not prove source provenance.

The canonical acquisition records real full-state roundtrip timing and its
runner identity without claiming HF-host throughput. Before serving, the
runtime must pass a bounded unchanged-data snapshot/artifact/conditional-commit
roundtrip on the actual host. Failure closes and poisons the gate before it is
installed. No application data is reset to make that check pass.

Offline tests exercise real native SQLite schemas, receipt and generation
preservation, native backup identities, source/payload rejection, object
collisions, exact Xet readback, ambiguous outcomes, process termination,
conditional parent races, no-op response rejection, previous receipt anchors,
and absence-only bootstrap. The separate SDK boundary review uses actual SDK
1.31 with a mock HTTP transport and mocked native Xet upload; it makes no
provider request. Neither source tests nor that harness establish a successful
live recovery, admission, CAS test or deployment.
