<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# GDW and Series-A durable acknowledgement boundary

`gdw_durable_runtime.py` and `gdw_durable_artifacts.py` belong to the **services**
layer. They implement the local boundary for the private dataset fencing coordinator. This source
does not activate storage, upload incident data, deploy, restart, or establish
that the live service has recovered. Actual canonical acquisition and qualified
cutover evidence remain required before activation.

`gdw_durable_startup.py` now implements the startup coordinator, using the
separately reviewed `gdw_durable_storage.py` provider protocol. This is still
source-only work. The later native qualification at admitted source
`2d63e1ded66b6581d57e4c57a148ac691d483350`, run `37237652697`, verified logical
continuity for both captured candidates. It does not supply a private admission
or permit this coordinator to restore without that record. The exact canonical
acquisition and proof sequence is in
[the cutover contract](operations/gdw-managed-storage-cutover.md).

The existing bucket originals remain recovery evidence. SQLite works on new
private local POSIX files restored from the exact qualified remote snapshots.
Neither constructor may create a database, run schema migrations, assign a new
generation, or fall back to another path after activation.

## Startup contract

Before importing route services or starting the outbox supervisor, the startup
coordinator must independently verify:

1. The actual recovery qualification, source revision, private provider identities,
   and immutable snapshot identities, including the existing generations and
   receipt continuity.
2. Source-bound evidence that legacy writers are stopped. Cooperative dataset
   fencing cannot stop an older process that does not check the fence.
3. A complete restore of both closed snapshots to a new private `0700` local
   directory, with `0600` regular files. An existing local working copy is never
   authoritative after a crash or uncertain publication.

The coordinator can then construct
`LocalGate(new_writer, paths, directory, publish, restored_head=verified_head, artifacts=artifact_cache)`.
The gate acquires its process lifetime file lock, checks the restored bytes and
verifies the referenced private artifact objects, then
claims the supplied remote head. `install(gate)` binds the single process before
route imports. A second claim, a forked process, an unknown filesystem, a symlink,
an unexpected sidecar, or a changed generation fails closed.

`GDW_DURABLE_STORAGE=private-dataset-v1` requests this mode; it is not admission
evidence. Without an installed gate, startup fails. Once installed, removing an
environment variable cannot bypass the gate. The exact local database paths,
`DELETE` journal and `FULL` synchronous mode must be configured explicitly;
legacy required-mount variables must be absent. The old provider configuration
scripts reject an existing durable-mode marker before any mutation instead of
moving the database paths back to `/data`.

The canonical entry point is `gdw_runtime.main()`, before `prepare_runtime`,
the outbox supervisor, and the import of `serve.py` that constructs Series-A.
FastAPI startup would be too late. The coordinator never creates the first
remote HEAD. A source-admitted acquisition operation must atomically bind the
initial HEAD, its immutable history, and a digest-named admission record in the
existing private dataset. Runtime reads the exact admission bytes at the
observed immutable HEAD revision; local JSON or an environment value is never
an admission source.

The admission is a strict canonical metadata schema binding capture and
qualifier artifacts, the canonical protected-main workflow/source receipt,
stopped legacy writer inventory and paused Space revision, exact candidate
snapshots, native receipt anchors, retained-artifact identities, and actual
acquisition timing. Its claim is limited to the qualified captured state;
later unobserved acknowledged writes remain `NOT_ESTABLISHED`. All unknown,
missing, duplicate, zero-identity, or loosely typed admission fields fail.

First cutover requires the exact admitted source SHA and the complete installed
source manifest derived from the canonical Docker COPY publisher. The manifest
binds every installed file, all source-known Python paths that must be absent,
Dockerfile, dependency input, installed authority verifier and public-key pin.
The mandatory storage-file floor is an additional constraint, not a substitute
for this complete inventory. Source identity alone is insufficient.
The result is content equality to the admitted source; canonical `hf-sync`
remains deployment authority. A later source revision requires a separately
reviewed admission contract, even if its changes appear unrelated. The native
signing-key loader runs in strict mode and its public half is checked with the
existing two-pin verifier; GDW credentials are parsed by the existing registry.
These local credential checks neither attest source nor create a key/signature,
and they do not probe an old or paused service.

### Complete installed-source binding

`scripts/build_gdw_installed_source_manifest.py` uses the exact public COPY
parser and expander from `szl-holdings/.github` at
`e3ec47ad2e99a535839afe0f30fefbd8973d52da`, script SHA-256
`eecf0ad2095ff345e009a24ba22a574efc974925fc88dd492377628c13b8e663`.
It compiles only the parser, expander and their exception class from the pinned
AST. Publisher mutations, application imports, provider calls and credential
reads are outside this helper. Git reads are bounded to local immutable objects;
replacement objects, lazy fetching and every transport are disabled. A missing
source object fails. COPY inputs must still match the immutable Git blobs, and
each COPY directory's complete membership is checked before and after reading.

The `szl.gdw-installed-source/v1` record describes the final `/app` files in
Docker COPY order, exact overwrites, the two declared build inputs and every
source Python path not installed. Python relocation, unknown RUN commands,
ambiguous destinations, symlinks and untracked COPY inputs fail. No extra
provider object or automatic publisher is added: the canonical record and its
SHA-256 live inside the existing immutable metadata admission.

The manifest cap is 384 KiB, with at most 2,048 installed files, 4,096 source
Python paths, 512 ASCII bytes per relative path, 32 MiB per file and 128 MiB
total installed bytes. COPY has independent limits of 256 instructions and
1,024 source tokens. The enclosing admission is bounded to 512 KiB; its escaped
worker message is bounded to 1 MiB. These bounds cover the complete source
inventory, rather than shortening it to fit the former selected-file record.
At source `ff8f6a1aa739ff2e4f965bfd728b7585f1a939a8`, the actual canonical
manifest measures 323,240 bytes for 1,495 installed files (67,443,439 bytes),
539 installed Python files and 1,268 required Python absences. The derived
payload has 595 source tokens, 1,496 files and 113 COPY instructions. A
synthetic test admission containing this complete real manifest measures
328,817 bytes, and its escaped native worker result measures 354,745 bytes.
Those two enclosing measurements are test fixtures, not recovery admissions.
The manifest has approximately 21 percent bounded headroom; every later
source revision must be derived and measured again.
The native GDW test derives and validates the full real record using a separate
read-only checkout of that exact publisher, then constructs one disposable
image to verify the runtime reader against its output. Test copies are removed
within the test, including after failure.

`gdw_durable_source.py` compares the actual `/app` files and declared
`/tmp/requirements-runtime.txt` input using no-follow regular-file descriptors,
exact sizes and hashes. It checks required absences and scans all application
directories for unlisted Python, Node, native-extension, shell, archive,
bytecode and Node loader-configuration inputs. File and directory identities
are observed again before success; the complete verification has a 30-second
deadline and a 16,384-entry scan bound. The canonical command is
`python -B gdw_runtime.py`, so local bytecode is disabled before the first
application import. Startup repeats source verification around restoration
and again after its full-state acknowledgement, before serving.

In explicit managed mode, the known dynamic import callers validate paths
against that installed inventory. They cannot add `/`, developer sibling
checkouts or arbitrary `SZL_KERNEL_PATHS` / `A11OY_SPINE_DIRS` entries. The voter
file loader verifies its admitted bytes before execution. The embedded
OUROBOROS temporary-program runner is unavailable in this mode because its
generated source has no installed-source admission. Legacy mode retains its
existing path and runner behavior.

This boundary reports `ADMITTED_SOURCE_CONTENT_EQUALITY`. It verifies the
separately named exact Hugging Face SDK version (`1.31.0`) and actual SQLite
version against the admission. It does not attest installed dependency package
contents, Python or Node binaries, the operating system, or the whole process
environment. Preservation and qualification retain SDK `1.23.0`; the canonical
durable acquisition uses a separate exact `1.31.0` environment. Before admission,
the selected pinned Python 3.14 base supplies an explicitly scoped expected SQLite
version and acquisition measures the full-pair round trip. The base observation
retains `PINNED_BASE_STDLIB_ONLY` and `FINAL_RUNTIME_NOT_OBSERVED`. The actual host
must match the admitted SDK/SQLite values before restore or claim, then acknowledge
an unchanged full pair before serving. A runner version cannot supply either
host observation.

Startup holds a native parent lock before provider observation, uses a fresh
private local directory, rechecks source bytes around restore, and validates
the original admitted Series-A terminal inside the restored chain. A valid
longer replacement chain cannot discard that original anchor. The initial
retained-artifact count, total bytes, and ordered identity digest must match
before the first epoch claim.

After claim, startup performs one real full-state acknowledgement on that
host before `install`: native backup of both unchanged stores, every retained
artifact readback, private snapshot readback, and conditional metadata commit.
No SQLite row or receipt is modified by this check. It must finish within
60 seconds. A late or uncertain outcome closes/poisons the gate and never
starts either service; the process cannot retry startup. GitHub acquisition
timing is identified separately and never presented as runtime throughput.

## Commit and read behavior

Both stores share one lock from connection acquisition through acknowledgement.
Each connection verifies current ownership. A modifying transaction commits on
local SQLite, creates closed native backups of both stores, checks integrity and
foreign keys, and calls `publish(paths, deadline)`. That adapter must upload to new
private bucket identities and verify exact bytes, Xet identities, generation and
receipt metadata. Returned hashes, sizes and generations must also match the
native backups. Every retained exported artifact is independently prepared and
readback-verified before this database publication. The gate then calls the writer's conditional metadata commit.
Only a verified acknowledgement allows the caller to return success.

An uncertain upload, commit, verification or timeout poisons the local runtime.
It cannot acknowledge a later write or serve stored receipts, idempotent replay,
or database reads. A new process must restore and claim the actual remote head;
it may not retry the local working copy. A rolled-back transaction does not
publish. Reads do not sign receipts or publish snapshots. File cleanup failure
after a proven remote acknowledgement retains private local candidates and sets
`cleanup_pending`; it does not change the known commit outcome or trigger replay.

The real GDW outbox persists its effect claim before exporting an artifact and
persists completion through this same boundary. Series-A persists its one-attempt
execution intent before an action. Existing governance and receipt rules remain
in force.

`ArtifactCache` preserves logical artifact paths in all existing database rows.
Only physical file access moves to a private local cache under reviewed proof and
receipt roots. When a retained artifact is absent locally, the exact historical
JSON serialization can be reconstructed from its retained payload. It must match
the stored SHA-256, size when present, tenant/intent identity, lifecycle, and native
request/receipt bindings. This is labeled `RECONSTRUCTED_FROM_RETAINED_PAYLOAD`,
never originally captured. Missing retained bytes, changed hashes or unsupported
paths fail closed. Compacted rows retain their existing compacted lifecycle.

The artifact provider callback is
`publish_artifact(local_path, object_path, sha256, deadline)`. Its fixed private
object key includes the SHA-256 of the logical path and the SHA-256 of the bytes.
It must readback the exact object or perform one fresh immutable publication and
verify it; uncertainty does not permit an automatic retry or overwrite. Only after
that verification can a database snapshot acknowledging `EXPORTED` become current.

## Operational limits

Every modifying SQLite transaction creates and uploads both complete snapshots
and verifies their retained artifact objects.
Readers wait while this work completes. This prioritizes an auditable persistence
boundary and has a substantial latency and bandwidth cost; no throughput claim
has been measured. Local filesystem access is restricted to an explicit allowlist
from `/proc/self/mountinfo`; object and network mounts are rejected.

Provider operations need the adapter's hard process deadline. The local gate checks
the deadline during SQLite backup, integrity work, publication and acknowledgement.
Legacy restart proofs still expect the former mount-backed contract. The explicit
managed branch instead validates immutable admission witnesses while retaining
native receipt, signature, generation and restart controls. Its actual proof
results and stopped-writer startup evidence remain prerequisites to live recovery.

Offline regressions use real SQLite stores, native backups, actual route handlers,
GDW outbox draining, Series-A receipts and a native competing process file lock.
Only the remote publication boundary is simulated. They establish source behavior,
not a successful live cutover.
