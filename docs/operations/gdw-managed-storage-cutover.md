# Canonical GDW captured-state cutover

This source implements the first cutover from the legacy bucket-mounted SQLite
files to local SQLite working copies with acknowledged private snapshots and a
versioned dataset manifest. A schema-valid document or a local test does not
authorize activation. Only the existing `hf-sync.yml` pipeline may acquire and
configure the captured state, publish the exact source, and run the live proofs.

## Evidence and current limits

The native qualification run `37237652697` on source
`2d63e1ded66b6581d57e4c57a148ac691d483350` classified both disposable database
candidates as `LOGICAL_CONTINUITY_VERIFIED`. Its safe qualification report has
SHA-256 `84509026f0ec3cd1c82a035b59138ad8198337622d2e9ed4bbaa9a792a6a1389`.
The report preserves all declared stored values, receipt bytes, and database
generations. It does not admit restore or deployment. The observed legacy Space
was `RUNTIME_ERROR` at revision
`cc9214315db74cd2fe9f546ae777186093e1a9eb`; no `PAUSED` claim follows from that
observation. New acquisition must reproduce qualification using the current
protected source and re-observe the unchanged original identities.

The immutable original capture remains the recovery anchor. Neither acquisition
nor startup opens an original bucket path with SQLite, overwrites it, or promotes
an unqualified repair. The captured state does not establish unobserved later
acknowledged writes. The bucket and dataset are each verified private, but equal
audiences are not asserted. Raw SQLite and retained artifacts stay in the bucket;
the dataset contains bounded manifest, history, and admission metadata only.

## Single canonical sequence

1. The exact protected-main run verifies native source ownership and performs the
   existing preservation and qualification steps. The pure classifier admits
   only a qualified captured pair. This first-cutover workflow deliberately holds
   healthy legacy, missing-evidence, and already-migrated cases; it supplies no
   legacy fallback or automatic replay of a partial migration.
2. The acquisition job validates the same run attempt, active job, successful
   source/qualification producers, and exact bounded artifact digests. It derives
   the complete installed source manifest from the pinned canonical publisher's
   Docker COPY expansion and verifies the exact checkout.
3. A bounded native probe observes the selected immutable `linux/amd64` Python
   3.14 base. Its SQLite value is an **expected** constraint with scope
   `PINNED_BASE_STDLIB_ONLY` and `FINAL_RUNTIME_NOT_OBSERVED`. A separate probe
   executes the exact legacy import/entrypoint closure under the same base and
   verifies that the persistent export guard rejects before database effects.
   This covers source execution after interpreter initialization; it does not
   attest the complete installed dependency or operating-system environment.
4. After qualified evidence and exact source checks, one canonical pause request
   may be submitted. A non-2xx reply or lost acknowledgement holds the attempt.
   Two native reads must confirm actual `PAUSED`, the same legacy revision, and
   unchanged original file identities before any snapshot or bootstrap effect.
5. The private runner reproduces the exact candidates, validates native integrity,
   foreign keys, receipt bindings and generations, and verifies the absent HEAD.
   Retained artifact reconstruction must reproduce the exact stored byte hashes.
   All artifacts and both snapshots are uploaded and read back, then restored to
   fresh private local files. This full-pair round trip is measured, with no
   throughput claim. Current protected source and paused legacy identity are
   checked before every bucket addition and metadata commit.
6. One conditional dataset commit binds the absent-only bootstrap HEAD, immutable
   history, and admission. At most three definite HTTP 412 conflicts may rebase
   while HEAD remains absent. An uncertain submission is never retried or
   acknowledged. Existing HEAD, mismatched bytes, or partial configuration holds
   the attempt for a separately reviewed reconciliation.
7. One managed helper configures the pair. The persistent old-source export guard
   is the first public variable effect and cannot be normalized by a legacy
   helper. Predeploy resume is skipped. Only the existing reusable publisher
   deploys the admitted source and requests restart.
8. Before restoring or claiming ownership, the new process verifies the exact
   admission source, complete installed bytes/absences, existing credentials,
   installed SDK, and actual host SQLite equality. It then restores the exact
   admitted pair, acquires local process ownership and the dataset fence, and
   completes an unchanged-state full-pair acknowledgement within 60 seconds before
   installing the gate or serving routes. Failure leaves reads and writes blocked.
9. Existing native GDW and Series A proof helpers validate signed receipt and
   restart continuity plus immutable managed witnesses. The aggregate requires
   both to bind the same admission, qualification, source, and generations.

## Interpreter and dependency boundaries

Preservation, qualification, and the manual prerequisite job retain
`huggingface_hub==1.23.0`. Acquisition, managed configuration/proofs, and the
runtime require exactly `huggingface_hub==1.31.0` in separate job/process
environments. The acquisition worker has an overall process deadline; individual
SDK socket timeouts are not represented as a total deadline. Credentials stay on
the existing canonical job path, and Docker probes receive only public source,
public variables and secret names. No token values or private database bytes are
included in public reports.

Local offline suites use synthetic provider/Docker boundaries and real native
store/protocol code. They establish source behavior, including lost-reply
failure semantics, but cannot substitute for the required native base probe,
actual pause/readback, private upload/CAS acknowledgement, host version equality,
full-state host acknowledgement, or live restart proofs.
