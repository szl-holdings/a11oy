# Inbound replication origin index integration

Evidence class: MEASURED for the local commands recorded below. Provider
publication and runtime qualification: UNKNOWN. Outbound replication remains
disabled by default; this repair does not qualify sender crash recovery.

## Source boundary

This paired source change starts from A11oy protected main
`5cd4cfe6237cf931753492750857632b348b6c28` and Killinchu protected main
`10fb059a8277ea477b824a41f5f243f9b23581be`.

The currently staged Platform revision is
`eaa4dc867c1e9f8f138c216fe9b040378858aafb`, from
[Platform PR 944](https://github.com/szl-holdings/platform/pull/944).
This is an unmerged candidate used for local integration testing. Final vendor
pins must be replaced with the protected merged source before publication.
Its canonical `packages/khipu-lmdb/khipu_lmdb/core.py` SHA256 is
`4c0087bd9e35cf14e355fe8266ba1e4e2b3e7c4da9562e8f6f9132c011429417`.

Only these vendor entries advance:

- A11oy: `szl_khipu_lmdb.py`, `organs/amaru/szl_khipu_lmdb.py`,
  `organs/sentra/szl_khipu_lmdb.py`.
- Killinchu: `szl_khipu_lmdb.py`.

The default pins remain A11oy
`880fda4f67fd2bbdc3507dce6d81fb782ca64c4c` and Killinchu
`c11291e09702c86f3f8995fffcae6167155c7240`. Other vendor entries are unchanged.
Generated canonical headers attribute each updated entry to its exact source.

## Receiver behavior and migration

The authenticated POST handler calls `append_replicated(origin)` after the
existing payload/envelope verifier. The foreign digest index, local wrapper,
entry counter, chain head and migration cursor commit in one LMDB transaction.
Repeated delivery of the same canonical origin returns the existing wrapper and
is acknowledged without appending another entry. The wire response still uses
`accepted`, `rejected` and `mirror_entries`.

Origin equality includes all canonical receipt bytes. Auxiliary metadata is
not authenticated by the receipt digest, but changing it for an already indexed
digest is a conflict and is rejected. Strict JSON key validation and finite
serialization occur before opening the write transaction.

On the first admitted write after upgrade, the canonical implementation scans
at most 1,000 unindexed historical records and 16 MiB inside the transaction.
It validates the stored wrapper chain and each origin before indexing. Existing
identical historical duplicates stay intact and bind to the first wrapper.
Corruption, collisions or a larger unreconciled history refuse admission and
roll back the whole transaction. There is no automatic deletion, reset or
unbounded reconciliation command. GET requests do not run this migration.

Expected validation/reconciliation failures count as rejected receipts; they
cannot advance a sender acknowledgement. Unexpected storage failures fail the
request. The existing operator check still precedes body parsing and storage.

The mirror remains at its existing `khipu_repl_<namespace>` path. A11oy's existing
state-store inventory covers this environment; this change adds no storage path
or publisher. Local close/reopen replay does not establish provider persistence,
cross-rebuild recovery, or sender crash recovery. No provider write was run.

## Immutable vendor workflow

An entry may declare `revision` as a full lowercase 40-hex commit SHA. Entries
without it use the unchanged global `pin`. `pin <ref>` changes that default only.
Malformed entries, including unselected overrides, are rejected before sync.

Use repeated `sync --only <local-path>` arguments to update just the selected
manifest entries. For example, after declaring the reviewed revisions:

```sh
bash scripts/sync_from_monorepo.sh sync --only szl_khipu_lmdb.py
bash scripts/sync_from_monorepo.sh check --strict-headers
```

`check` always validates the entire manifest and rejects `--only`. The existing
canonical two-line header rules remain in force. With `PLATFORM_DIR`, sources
come from `git show <declared-commit>:<source-path>`, never the current working
tree. Replacement refs are disabled, and
[`GIT_NO_LAZY_FETCH=1`](https://git-scm.com/docs/git) prevents hidden
remote reads from a partial clone. Missing commits or blobs fail without a
network fallback. Without that variable, the source URL contains the immutable
revision.

The vendor CI job runs the stdlib contract suite before its unchanged full
strict check. Contract fixtures create real local Git commits, alter HEAD and
working-tree bytes, add replacement refs, and create a filtered local clone.
They verify immutable selection, target isolation, invalid input refusal,
missing-blob refusal and header behavior without external network calls.

## Local verification receipt

Python 3.12, pytest 9.1.1, lmdb 2.3.0, FastAPI 0.139.0 and httpx 0.28.1.
Pytest plugin autoload and bytecode writes were disabled. Every pytest run used
a fresh explicit `--basetemp`; no existing test directories were removed.
The 12 stdlib vendor contract tests also passed under WSL Ubuntu with Git
2.43.0 (`python3 -B tests/test_vendor_sync_contract.py`), including both immutable
source substitution and partial-clone refusal regressions.

A11oy command, from its consumer checkout:

```text
python -m pytest -q -p no:cacheprovider --basetemp=<fresh isolated directory> tests/test_vendor_sync_contract.py tests/test_unay_write_authorization.py tests/test_khipu_replication_delivery.py tests/test_meter_shared_payload_history.py
122 passed, 9 subtests passed
```

Killinchu command, from its consumer checkout:

```text
python -m pytest -q -p no:cacheprovider --basetemp=<fresh isolated directory> tests/test_vendor_sync_contract.py tests/test_unay_write_authorization.py tests/test_khipu_replication_delivery.py tests/test_shared_operator_boundary.py tests/test_runtime_shared_boundary_peer_sync.py tests/test_shared_observer_operator_gate.py tests/test_space_http_diagnostics.py
227 passed, 9 subtests passed
```

The actual embedded Python CLI from `scripts/sync_from_monorepo.sh` was invoked
with `check --strict-headers` and `PLATFORM_DIR` pointing at the canonical local
Platform Git checkout. Result: A11oy 163/163 entries and Killinchu 15/15 entries,
each with zero failures and zero warnings. This checks immutable Git object
bytes, including entries outside the sparse working tree.

`python .github/shared-file-drift-check.py . <peer-checkout> --self-name=<self>
--sibling-name=<peer>` ran in both directions: 160 candidates, 156 identical,
four existing allowlisted differences and zero blocking differences.

`python .github/validate-shared-payload.py . <peer-checkout>
--expected-manifest-sha256=<active-manifest-sha256>` binds the paired six-file
payload. The preceding integrity manifest is preserved byte-exact at
`.github/shared-source-payloads/replication-payload-integrity-20261017-v1.json`,
SHA256 `1b8a4693d35e342ef47088d9fbebad580d05b8425cf9f3f90d32f0c00466c1cc`.
Historical source hashes remain historical; current-source checks are separate.

The new archive keeps a public authentication-related source digest that the
generic secret heuristic detects. The existing exception now permits its exact
literal row/hash at the active manifest and the one preserved manifest path.
It is still a rule-specific AND condition; no directory or general hexadecimal
exception was added. With the verified Gitleaks 8.21.2 executable configured:

```text
python -I -B tests/test_gitleaks_archived_payload_digest.py -v
6 tests passed in each consumer
```

These actual-scanner tests cover both permitted paths, another path, a changed
value, and adjacent/same-line credentials. Killinchu's existing public-digest
scanner suite also passed its 10 tests. The A11oy broader scanner suite has seven
unchanged Windows stylesheet-path subtest failures; independent Linux execution
of both A11oy scanner suites passed all 35 tests. The archive-specific controls
pass on both operating systems. No unrelated scanner exception was broadened.

Independent review found no remaining actionable findings after replaying the
Git replacement-ref reproduction, all 12 vendor tests, paired payload/drift
validators and actual scanner controls. The reviewer also ran the focused
receiver suites and verified every updated vendor body against the canonical
Platform blob. Exact-head hosted consumer CI is pending. No claim of deployment,
live replication, hardware readiness or AGI is made.
