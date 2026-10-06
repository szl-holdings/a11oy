<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# GDW diagnostic-bound continuation: side-effect manifest

This manifest describes every reachable provider mutation in the single
main-push transition introduced after the
accepted read-only diagnostic run
[`37406817882`](https://github.com/szl-holdings/a11oy/actions/runs/37406817882).
It is not a claim that the failed historical acquisition had no provider
effects. Historical provider effects and writer attribution remain
`NOT_ESTABLISHED`.

## Fixed authority and scope

- Accepted diagnostic source and transition predecessor: protected, signed main
  `f4a1a45f153cf5a4c42f768e2dd2e089730358d8`. The effectful source must be
  this commit's signed direct child.
- That predecessor's automatic first-attempt run
  [`37405820542`](https://github.com/szl-holdings/a11oy/actions/runs/37405820542)
  entered artifact publication and stopped after its five-minute publication
  budget. Its closed artifact `11387128425` records
  `ARTIFACT_PROVIDER_CALL_UNAVAILABLE`, `ARTIFACT_PUBLICATION`,
  `BOUNDARY_ENTERED`, and `provider_effects=NOT_ESTABLISHED`; every later
  acquisition, bootstrap, configuration, deployment, and parity job skipped.
- The exact-source read-only diagnostic
  [`37406817882`](https://github.com/szl-holdings/a11oy/actions/runs/37406817882)
  then downloaded and validated every object it found without provider mutation.
  It observed 72 exact retained objects and 152 missing objects from the planned
  224-object set. It did not establish who wrote the 72 objects.
- Diagnostic artifact: `11386978354`, archive SHA-256
  `01ecf2e4c12fa67af581e6563fb84d64371d2c6725cd49fc51cd5583ac1f798a`,
  closed report SHA-256
  `76705ff024fb0e85c101569fc81e25fafe2958805df7bcb9b8f7daf001d867ce`.
- Existing Space: `SZLHOLDINGS/a11oy` only.
- Existing private dataset and bucket: `SZLHOLDINGS/szl-evidence` only. Their
  privacy metadata must read back as private; this transition does not create,
  delete, rename, or change the visibility of a repository, dataset, bucket,
  Space, or volume.
- Existing capture and historical anchors are read in place. No preservation
  copy, capture, acquisition replay, restoration into an incident original,
  deletion, reset, or excluded archive download is admitted. The only restores
  below are disposable acquisition readback and the managed runtime's verified
  restoration of admitted snapshots into its new private local run directory.

## Credential routing boundary

The immutable shared publisher pin is
`szl-holdings/.github@fc71ae973a0f31b8e9ee793fc8545a354448d451`.
Its HF read helper permits an `HF_TOKEN`-derived `Authorization` header only at
the exact `https://huggingface.co:443` Hub origin and rejects that credential at
any other destination. Public `*.hf.space` application smoke probes send only
the reviewed cache-control header and disable redirect following. The separate
GitHub API helper may use `GITHUB_TOKEN` for configured GitHub API reads; this
manifest makes no broader claim about that distinct credential path. The
publisher still reads `HF_TOKEN` for authenticated Hub API and repository
operations that require it, but does not send that credential to the
application origin. No token value is recorded by this manifest or its tests.
A different publisher revision or broader credential destination requires new
source review.

## Required state before the first provider write

The pre-write chain establishes all of these checks before even a Space pause
request. The read-only reconciliation job directly validates and downloads the
fixed historical diagnostic artifact. The later credential-isolated effectful
worker does not redownload that historical artifact: it validates the exact
same-run reconciliation artifact and its fixed producer/report constants, then
independently repeats the live source, capture, HEAD, and object-path checks.
If reconciliation holds, it persists a closed no-write receipt before exiting.
That receipt may expose only the fixed diagnostic code and a fixed,
non-sensitive reconciliation stage; it never includes paths, principals,
tokens, provider error text, or exception text. A held reconciliation never
emits the qualification receipt or an admission output.

1. The executing source is the signed direct successor of the fixed transition
   predecessor, the predecessor is a signed descendant of the accepted
   diagnostic source, the source is still protected main, and it has exactly one
   first-attempt push run.
2. The same-run source-admission job succeeded and the fixed diagnostic-bound
   reconciliation job produced the selected artifact.
3. The fixed diagnostic producer, artifact metadata, archive digest, report
   digest, and closed no-write fields validate exactly.
4. Both captured databases re-qualify with logical continuity, unchanged
   declared values, unchanged generations and receipts, complete SQLite
   integrity checks, and no provider writes during qualification.
5. The fresh private dataset `main` revision has no durable HEAD. Reconciliation
   records that exact observed revision; the effectful worker requires the same
   revision and absent HEAD before its first mutation and throughout every
   pre-bootstrap acquisition write boundary, through the single absent-parent
   HEAD/history/admission bootstrap commit. Unrelated movement of the shared
   evidence dataset before that bootstrap therefore holds the continuation for
   review. Once the acknowledged bootstrap advances the dataset revision,
   downstream reviewed configuration and deployment boundaries use their own
   current-parent and readback contracts.
6. The freshly reproduced candidate derives exactly 224 content-addressed
   retained-artifact paths. The whole owned `a11oy/durable-artifacts/v1` prefix
   must still contain exactly the 72 diagnostic objects, with exact path, size,
   and Xet identities, and no other entry. The accepted observed-set hash is
   `aa01f33429b4311894f6ffd5f1dd083d4fed06381b956c2025269a5011db7b24`;
   the complete planned-set hash is
   `7a28c53fa647e639375c6a90d3e34e89fe74bc2004f8161b5f38ac793301be42`.
   Historical writer attribution for those 72 remains `NOT_ESTABLISHED`.
7. The canonical Space is in `RUNTIME_ERROR` or already `PAUSED`; its revision,
   mount, public variables, secret names, stopped original object identities,
   and native old-runtime rejection guard match the reviewed contract.

The worker binds the complete 224-path set and exact 72-object partial namespace
before the native old-runtime guard, then rechecks both and absent HEAD
immediately before a pause request.
The earlier scan is not reused as pause authority after that bounded guard.

After a successful pause readback, the worker reproduces the candidate again,
recomputes the same 224-path set, and proves the exact partial namespace and
absent HEAD remain unchanged immediately before object publication.

## Allowed effects, in order

1. If the canonical Space is in `RUNTIME_ERROR`, submit one pause request and
   require two `PAUSED` readbacks. If it is already `PAUSED`, submit no pause.
2. Preserve the 72 exact pre-existing retained-artifact objects and add only the
   152 missing candidate-derived objects under `a11oy/durable-artifacts/v1/`.
   Protected main, absent HEAD, and the complete 72-object namespace are
   rechecked immediately before one bounded SDK batch submission. The pinned
   SDK submits these 152 additions in one non-transactional request; an
   exception or lost reply is never retried. After a synchronous response, all
   224 objects are downloaded in one grouped readback, byte-hashed, and checked
   for stable Xet identities. Only the 152 additions can become acknowledged by
   this worker; the 72 remain pre-existing with writer attribution
   `NOT_ESTABLISHED`. The later round-trip pass may only re-read the same 224
   identities and cannot add a second copy.
3. Add exactly two fresh immutable SQLite snapshot objects, one for `gdw` and
   one for `series_a`, under a new operation-scoped
   `a11oy/durable-store/v1/objects/` prefix. Both closed snapshots are fully
   inspected before the first snapshot add, and every add is read back and
   restored into disposable private storage for native verification.
4. Submit one absent-parent dataset commit that adds exactly the durable HEAD,
   its operation history record, and the source/capture/qualification admission
   record. The commit is parent-bound to the still-current dataset revision and
   is acknowledged only after exact readback.
5. After the immutable locator exists, write only the 13 reviewed fixed managed
   public variables declared by `gdw_durable_guard.MANAGED_VARIABLES` on
   `SZLHOLDINGS/a11oy`. These select the existing private-dataset store, clear
   only the two obsolete mount-selector values, and retain the fixed SQLite,
   persistence, signing, proof-directory, and receipt-directory contract. No
   secret value or secret setting is read, written, replaced, or deleted. A
   partial or uncertain variable write stops without retry or compensation.
6. Only after acquisition and managed configuration succeed may the existing
   pinned reusable publisher commit the exact Dockerfile-derived file set to
   the canonical `SZLHOLDINGS/a11oy` Space repository, reconcile/prune only
   files outside that exact source set, bind public variable `SZL_GIT_SHA` to
   the protected source, and request its configured non-factory Space restart.
   This source-tree reconciliation never deletes or resets persistent runtime,
   dataset, bucket, snapshot, retained-artifact, or captured database data.
7. Every successful managed-runtime start, including the publisher restart and
   each later proof restart, restores the two admitted immutable snapshots into
   a new private local run directory. Before serving, `LocalGate` claims the
   exact restored HEAD by incrementing the writer epoch and atomically replacing
   the private dataset HEAD while adding one operation-history record. It then
   acknowledges the unchanged local pair: it makes closed native backups,
   prepares any retained artifacts, publishes two new immutable snapshot
   objects, and atomically replaces HEAD plus adds another history record. Each
   request is current-parent CAS-bound and must pass exact readback; uncertainty
   poisons the writer and authorizes no retry. These are persistent private
   bucket/dataset writes even though no SQLite row changes during startup.
8. The bounded Series-A live proof performs two named stop-the-world phases on
   `SZLHOLDINGS/a11oy` only: `activation` and `durability`. Each phase submits
   one pause, requires `PAUSED`, and submits one non-factory restart. A single
   restart retry is possible only after a lost response and a fresh provider
   read proves the Space is still `PAUSED`; no blind retry is admitted. The
   proof performs no HTTP application write and requires the same protected
   source plus persisted generation/receipt continuity after both restarts.
9. The bounded GDW live proof writes only within `/api/a11oy/v1/gdw/`: one
   source-derived governed `step`, bounded `drain` calls, and at most eight
   source/generation-derived `recovery/transient-effects` calls. The governed
   step has a fixed source-derived request ID; every recovery call has a fixed
   idempotency key and a 100-effect ceiling. Transport retries are limited to
   eight attempts inside ten minutes. The resulting namespace, SQLite
   generation, drain state, and pinned-key DSSE receipt must verify. The
   current workflow entrypoint does not invoke the module's separate restart
   helper; wiring that helper into this transition requires new review. Each
   admitted local SQLite transaction is acknowledged through the installed
   gate: newly materialized retained artifacts may be added, both closed
   snapshots are published under a new operation prefix, and a CAS-bound
   private dataset HEAD/history commit records the pair. Thus application writes
   also cause persistent bucket and dataset writes; they are not merely local
   HTTP effects.
10. After the live proofs pass, the readiness job probes the canonical origin
   and writes only the compact source-bound public variable
   `SZL_PROBE_VERDICT_JSON` on `SZLHOLDINGS/a11oy`.
11. Relock, module-parity, and terminal protected-main authorization are
    read-only provider/source proofs. The six-Space vertical publisher is
    dispatch-only and skipped on this push. The Finance publisher is explicitly
    false-gated and skipped. No other repository, Space, model, dataset, DNS,
    WAF, visibility, hardware, billing, credential, secret, security setting,
    or data-sharing scope is mutated.

## Acknowledgement and partial-failure behavior

- A newly added object is worker-acknowledged only after the one batch returns,
  all 224 private bytes download and pass SHA-256 verification, and the complete
  Xet identity set remains stable. The 72 pre-existing objects are deliberately
  kept in a separate set and never relabelled as writes by this worker.
- A transport timeout, killed worker, malformed response, moved identity,
  changed source, changed original, path collision, dataset-parent conflict, or
  failed readback stops the run. The closed failure record continues to label
  provider effects `NOT_ESTABLISHED`; it never fabricates a no-effect result.
- A managed-runtime restore, claim, startup acknowledgement, or later
  transaction acknowledgement that has an uncertain outcome poisons that
  process. The runtime does not treat a local database write as durable until
  its snapshot pair and private HEAD/history commit have exact readback.
- No ambiguous provider request is retried. There is no deletion, overwrite,
  rollback, compensation, or promotion of an unacknowledged object.
- A failure after some acknowledged objects leaves those immutable objects in
  place and leaves the Space paused. It does not authorize a second continuation.

## Repeat, rerun, push, and concurrency barriers

- The three recovery jobs require `push`, `github.run_attempt == 1`, exact
  protected-source admission, and the preceding same-run success outputs.
  `workflow_dispatch`, partial reruns, and attempt 2 or later cannot enter the
  effect path.
- The reconciliation and acquisition helpers require the current source to be
  the signed direct child of the fixed transition predecessor, whose ancestry is
  bound back to the accepted diagnostic source. Any later main commit has a
  different parent and is denied.
- The workflow concurrency group is serial and does not cancel an in-progress
  run. The native helper additionally requires the unique push run for the exact
  source, the active expected job, and current protected main before reads and
  before every admitted write boundary.
- The old acquisition run and all excluded/private capture archives remain
  untouched. A future recovery after any uncertain outcome requires new
  read-only evidence and a newly reviewed source transition; this source cannot
  be replayed.
- Unrelated estate publishers remain skipped: the vertical publisher requires
  explicit dispatch, and the Finance job is false-gated for this transition.
