<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Series-A writes across storage release: 2026-11-17

## Status and scope

**Historical preservation gap: unresolved. Repair regressions pass locally; live qualification is pending.**

A released Series-A process reported a receipt-chain head that was absent from
its successor's live store. The successor restored the released snapshot set and
acquired a `CLEAN` storage epoch. These observations can coexist: lease succession
and snapshot integrity do not establish that every producer stopped writing
before the final snapshot.

This record separates the historical incident, the reproduced local write-fence
failure, and qualification of a prospective repair. A future passing test or
successful deployment does not erase the earlier observation. No restore,
receipt replay, chain rewrite, or recovery attempt is recorded here. The evidence
does not establish irrecoverable loss or the complete set of missing receipts.

All times below are UTC. Public source revisions and workflow references are
included; private provider HEAD identifiers, object locations, full receipt or
snapshot digests, receipt payloads, and credentials are excluded. Exact evidence
is retained in restricted operator records.

## Observed transition

The prior application source was
[`4d724ba`](https://github.com/szl-holdings/a11oy/tree/4d724ba783500d6fbe06638853bafa8f3f2a38e2).
The successor source was
[`b3bed6e`](https://github.com/szl-holdings/a11oy/tree/b3bed6e294eb49ed3f20c4fe8379e29ce126a68e),
published through canonical [HF Sync run 43995318192](https://github.com/szl-holdings/a11oy/actions/runs/43995318192).

| Time | Evidence | Bounded conclusion |
|---|---|---|
| Before release | Epoch 279 retained `UNCLEAN_HANDOVER` from its acquisition history. | Later healthy checks do not change that history. |
| 01:21:24 | Epoch 279 recorded release. The released Series-A snapshot had actual SQLite `COUNT(*)` and maximum sequence of **72,977**. | This is the preserved snapshot's receipt boundary, not the later old process's counter. |
| Release verification | All seven released objects passed byte and SQLite/LMDB verification. | The examined released objects were internally consistent under those checks. |
| 01:26:54 | Epoch 280 acquired `CLEAN` and restored the exact seven-entry released snapshot map. | The successor consumed the released object set; this does not establish coverage of later writes in the old process. |
| 01:26:49 and 01:27:19 | The old process reported `RELEASED`, `writable=false`, **72,981** receipts, maximum sequence 72,981, and chain-head prefix `58d4aff6`. | Its live receipt view was ahead of the released snapshot. |
| 01:27:42 and 01:28:29 | The successor reported epoch 280, `CLEAN`, `WRITER`, **72,979** receipts, and chain-head prefix `a75651c2`. | Counts alone cannot establish which earlier receipts survived. |
| 01:29:15 | Exact-hash GET for the old head returned HTTP **404**, `szl.series-a-receipt-recovery-miss/v1`. The new head returned HTTP **200**, sequence 72,979. | The old observed head was absent from that live successor store. |
| 01:34:49 | The successor reached **72,981** receipts with a different head, prefix `cd3972b3`. All seven stores remained healthy. | Count equality and healthy storage do not resolve the missing old head. |

The old process's saved status also reported a latest persisted manifest with
`observed_at=2026-11-17T01:26:27.113Z` and a running 240-second refresh scheduler.
This is evidence to investigate background activity after release. The saved
status responses do not contain recent receipt items, so they do not identify the
final receipt kinds or their creation times.

The exact-hash checks were GET-only reads. They did not sign, mint, recover, or
replay a receipt.

## Why the comparison is meaningful

Both counter observations used the same
[`/api/a11oy/v1/series-a/status`](https://szlholdings-a11oy.hf.space/api/a11oy/v1/series-a/status)
endpoint and `storage` fields. The store instance identity and database path were
unchanged. The route is a current read, not an immutable historical artifact; the
restricted records retain the original responses and their file digests.

In the deployed
[`Store.storage_status()` implementation](https://github.com/szl-holdings/a11oy/blob/b3bed6e294eb49ed3f20c4fe8379e29ce126a68e/routers/series_a_control_plane.py),
receipt count is a fresh SQLite `COUNT(*)`, maximum sequence is `MAX(sequence)`,
and chain head is selected from the latest receipt. These are not cached manifest
counts. That source file did not change between the two application revisions.

The existing `GET /api/a11oy/v1/series-a/receipts/{receipt_hash}` handler obtains
storage status and exact-hash lookup in one SQLite read transaction. Its 404
therefore supplies stronger evidence than a counter decrease alone. The result
still does not identify a complete missing set, establish permanent loss, or
justify a reconstruction of historical receipts.

## Reproduced failure and candidate repair

A local regression against deployed source `b3bed6e` demonstrated that a Series-A
append could succeed after the storage owner had entered `RELEASED`. The expected
write-fence exception was not raised (`DID NOT RAISE`). This reproduces the class
of failure that allows an old process's local database to advance beyond its
released snapshot. It does not independently attribute every historical receipt
to that mechanism.

The candidate repair remains within the existing storage owner,
[`a11oy_state_store.py`](../../a11oy_state_store.py), and its Series-A consumers.
The implementation and bounded regressions establish these properties:

- A central write permit counts admitted work until the actual operation,
  transaction, and connection have finished.
- Same-task nested writes can finish during a handover drain. A copied context in
  another task or thread does not inherit write authority.
- Managed Series-A writes use explicit write connections and recheck admission
  at commit. Read connections are read-only and do not initialize missing stores.
- Receipt and corresponding event insertion share one transaction.
- Background refresh and asynchronous operations retain admission across their
  work; new writes after release or fencing are refused.
- Observer and native readback consumers use the managed Series-A connection
  boundary without granting new execution or signing authority. Serialized
  workers acquire the manager lock before admission; an event-loop callback
  refuses lock contention immediately.
- Canonical shutdown stops Series-A producers before storage finalization.
  Service shutdown cancels and joins all captured tasks before reporting any
  prior task failure, so one failed reconciliation cannot leave siblings live.

These are local implementation results, not claims of deployed qualification.
The final DML commit check and lease fencing share a local lock. The helper
also counts the entire connection scope across initialization and DDL; it does
not interpose on every explicit SQLite commit a trusted caller could issue.
Clean release waits for admitted scopes, and failed admission or commit prevents
a successful operation acknowledgment. A new local receipt must not be reported
as durably acknowledged solely because its SQLite transaction committed.

## Validation record

Results below are separate runs with overlapping coverage; do not add them into
a single pass count. The pull request and hosted checks bind the final source.

| Check | Current recorded status |
|---|---|
| Exact `b3bed6e` baseline | Actual released-owner append succeeded; expected rejection did not occur (`DID NOT RAISE`). |
| Final managed-store, service and shutdown regressions | **33 passed**: 24 new fence cases, seven ASGI hook cases including actual SIGTERM, and two existing service lifecycle cases, on WSL Linux / Python 3.12.3. |
| Existing storage, restoration, ASGI shutdown, wiring, provenance | **159 passed, 11 subtests passed**; includes the real POSIX SIGTERM process. |
| Observer, native readbacks, registration, adapters | **108 passed** on Linux. |
| Existing Series-A / estate / investor selection | **99 passed**, seven Node-dependent cases could not run in the minimal Linux environment. |
| Full investor UI file on Windows with actual Node | **12 passed**, including those seven Node-dependent cases. |
| Exact updated Series-A CI command before the final shutdown-order addition | **337 passed, 151 subtests passed, one existing skip**, using verified official Linux Node 22.23.5. Final lifecycle validation is recorded in the pull request. |
| Full doctrine scan | **4,948 files, zero hits**; later changed files are rescanned before publication. |
| Hosted deployment gates | Pending final result. |
| Candidate live publication and bounded readback | Not yet qualified. |
| Historical receipt preservation gap | Unresolved; independent of candidate validation. |

The regression suite is
[`tests/test_series_a_state_store_fence.py`](../../tests/test_series_a_state_store_fence.py).
Record its actual command, result, exact candidate revision, and relevant CI run
when available. Do not substitute the older deployment's passing checks for
validation of this repair.

For the already deployed `b3bed6e` source, the
[exact runtime job](https://github.com/szl-holdings/a11oy/actions/runs/43995318192/job/133746445309)
verified **1,572 files**, zero mismatches, zero missing files, and **21** declared
smoke routes returning HTTP 200. Runtime configuration verification also passed.
The workflow then failed at `SOURCE_OWNERSHIP_BEFORE` because protected main had
advanced. It did not freeze independent execution context or collect an
execution export; downstream qualification gates were skipped. Those deployment
results neither validate this candidate repair nor resolve persistence history.

## Runbook for retaining evidence and qualifying the repair

1. Retain the original old-process responses, exact-hash miss, released snapshot
   verification, and successor snapshot-map comparison independently of the
   patch. Keep exact private identifiers and payloads in their existing
   restricted evidence location.
2. Preserve epoch 279's historical `UNCLEAN_HANDOVER` and epoch 280's observed
   `CLEAN` acquisition. Interpret each label within its recorded lease history.
3. Establish the failing baseline and passing candidate on the same regression
   case, then exercise work already admitted when drain starts, new work refused
   during drain, cancellation, and loss of admission before commit.
4. Verify every affected Series-A writer, including background tasks and native
   execution readbacks, uses the central admission boundary. Check that reads
   remain available without writing, signing, or initializing missing databases.
5. Establish one canonical publisher. The first remediation rollout still
   starts from the unpatched producer: do not manually release it early and
   assume it has stopped. No Series-A quiesce endpoint exists in that source.
   Preserve its captured receipt heads and envelopes for exact successor lookup;
   this verifies the captured baseline, not every later unobserved write. Once
   the patched lifecycle is deployed, use the existing
   [state-store handover procedure](../operations/state-store-deploy-handover.md).
   If a request outcome is uncertain, observe its existing receipt; do not create
   a replacement request to manufacture a cleaner history.
6. Verify the released snapshot objects and their logical contents with the
   existing [snapshot rehearsal tool](../../scripts/rehearse_current_state_snapshots.py).
   Bind the successor's restoration to that exact released entry map. Keep
   counter checks and exact receipt membership checks distinct.
7. Publish only through the canonical workflow. Record the actual source, HF
   revision, process boot, storage epoch, and checks that completed. A skipped
   or superseded gate remains unqualified.
8. Update this validation record with bounded outcomes. Keep the historical gap
   open until independently retained evidence establishes what happened to the
   old receipts. A repair prevents a class of future writes; it does not recover
   or authenticate missing history.

Storage ownership and the meaning of clean and unclean acquisition remain those
of [ADR-0001](../adr/ADR-0001-a11oy-state-store.md). This incident introduces no
new storage authority, automatic recovery path, or execution qualification.
