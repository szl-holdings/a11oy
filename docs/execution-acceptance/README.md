<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Offline execution observation bindings

Layer: **provenance / supply-chain tooling**. `tools/execution_acceptance.py`
checks a complete five-case bundle offline. It has no HTTP client, private-key
loader, signing function, provider mutation, environment-secret discovery or
runtime route. It is not wired into CI, the readiness probe, the compact publisher,
the served reader or the canonical deploy workflow.

A successful result has `status: REPORTED` and `binding_checks_passed: true`.
It always has `publication_eligible: false`, `execution_authorized: false` and
`passive_probe_modified: false`. Exit 0 means only that these cryptographic and
structural checks passed. It is **not** a release-gate exit code.

The proposed actual requests and outstanding prerequisites are in
[PROPOSED_PLAN.md](PROPOSED_PLAN.md). No synthetic fixture in the tests represents
production evidence. The test suite generates ephemeral keys only in memory.
Its envelopes are signed over the existing `szl_dsse.canonical_json` and
`szl_dsse.pae` helpers, with `szl_dsse.keyid_for_public_pem` identifiers, to check
wire interoperability without invoking that module's ambient key discovery.

## Trust and wire format

The implementation uses the repository's existing `szl_dsse.py` wire primitive:
DSSEv1 pre-authentication encoding, ECDSA-P256 over SHA-256, and a key identifier
equal to SHA-256 of the normalized SPKI public PEM with surrounding whitespace
removed. It accepts a single explicit signature for each typed record. It does
not call `szl_dsse.verify_envelope`, because that general verifier discovers
ambient/embedded keys and may load private-key sources. This tool's verification
is public-key-only; it adds no new signing algorithm or fallback trust root.

The caller supplies independently admitted public PEM files **and** their pinned
identifiers. Neither public key is read from the evidence bundle. The caller also
supplies independently observed source revision, HF runtime revision, runtime boot
identity and fresh run nonce. Passing values copied out of an untrusted bundle
does not establish independent admission. Key pin provenance and real role
authority remain the integrating caller's responsibility.

Approval and runtime observation roles must use distinct public-key identifiers.
This is role separation, not a claim of independent human review. Runtime bearer
tokens and any second-approver credentials never belong in a bundle or plan.

The outer bundle is exactly:

```json
{"schema":"szl.execution-acceptance-bundle/v1","plan":{},"observations":[]}
```

`plan` is a DSSE envelope with payload type
`application/vnd.szl.execution-acceptance-plan.v1+json`, signed by the independently
pinned approval role. Its decoded JSON binds the schema, fixed origin, exact
source/runtime/boot, nonce, issued/expiry UTC times, operator reference, request
budget and the complete case list. Each case contains its exact ID, POST path,
explicit JSON body, expected successful HTTP status and nonempty response and
readback assertions. Assertions are object-key JSON pointers and compare canonical
JSON values, so `true` and `1` cannot substitute for each other.

Each observation contains exactly `receipt`, `response_b64`, `readback_b64`.
`receipt` uses payload type `application/vnd.szl.execution-observation.v1+json`
and the independently pinned runtime observation role. Its decoded payload binds:

- a unique receipt identity and the exact case identity;
- the canonical approved-plan SHA-256 and operator reference;
- the same origin, source, runtime revision, boot and run nonce;
- SHA-256 of canonical `{method,path,body}`, plus hashes of the actual decoded
  response and readback bytes;
- response status and observation start/completion UTC times.

The validator recomputes these hashes, verifies the actual signatures, checks
the trusted plan's assertions and requires complete, unique coverage of all five
fixed paths. It rejects unknown fields, including self-asserted `authorized` or
`receipt_verified` flags. It rejects stale/future evidence, missing/extra/duplicate
cases, duplicate receipts, changed bytes, malformed/non-finite JSON, duplicate JSON
keys, wrong pins, wrong signatures, and wrong source/runtime/origin/nonce bindings.
Approval validity and observation freshness are bounded to fifteen minutes.

These typed observation receipts are an adapter contract, not an assertion that
current endpoint receipts already have this payload. Current native DSSE receipts
must be verified using their existing schema and trust model before a real adapter
can attest the captured execution and readback. The five-route producer, adapters,
semantic success verification, durable nonce consumption and live authority
admission are not wired into execution. Internal storage prerequisites are
described below. Re-validating the same offline bundle is permitted; it must never
cause replay of an execution.

## Internal storage prerequisites

`validate_plan` shares the complete signed-plan parser with the offline bundle
validator. It returns verified plan fields against the supplied independent
context; it does not authorize execution. The bundle validator still requires
all five observations. Supplying only the three deterministic route observations
cannot satisfy that requirement.

The existing Series-A `Store` has internal reservation, completion and read-only
SQL helpers for two isolated observation tables. They are created lazily by a
reservation, not by ordinary startup or reads. SQLite transactions and uniqueness
constraints bind each nonce to its source, boot and plan, and consume each case
once across separate connections. A completed or interrupted reservation cannot
be reserved again. Completion stores canonical JSON and its digest, but does not
verify a runtime signature or make the row eligible for export. These helpers
leave existing passports, receipts, events and storage identity unchanged. They
reuse the registered Series-A database; no snapshot label or HEAD schema changes.

`a11oy_state_store.StateStore.snapshot_confirmed` is an explicit acknowledgment
primitive for a trusted owning module. It requires the fenced writer, an active
matching HEAD and a valid fresh heartbeat for that epoch, writer and boot. Even
a newly claimed writer must wait for its own heartbeat. It downloads the selected
immutable snapshot, verifies size, hash, full SQLite integrity, foreign keys and
logical fingerprint, and applies the owner's fixed expected-row predicate. It
then advances HEAD through the existing compare-and-swap implementation and
independently reads back the current HEAD and lease. An uncertain submission is
accepted only if the exact proposal is found remotely. It preserves unrelated
pending snapshots and fails on handover without synchronously draining its own
request. Ordinary periodic snapshot behavior is unchanged.

This primitive observes a storage acknowledgment at that instant. It does not
prove source or HF runtime identity, validate operator custody, admit a request,
or make storage atomic with a later external effect. There is no route, signing
path, automatic call, configuration switch or publisher change in this increment.
A future consumer must verify the actual active manager and Series-A path, admit
the independently identified runtime and signed plan, reserve before dispatch,
recheck identity/expiry/fence after acknowledgment, and refuse export until the
completed record is acknowledged. It must burn attempts on cancellation or
uncertainty and reject old-boot plans after restoration. The local row alone is
never permission to execute or export.

The read helpers use SQLite read-only connections without schema initialization,
DML or journal-mode changes. A WAL database may still require SQLite coordination
sidecars; these helpers alone do not establish a completely inert HTTP GET. The
runtime producer, immutable runtime identity admission, export guard, cancellation
handling and end-to-end crash/replay contract remain **ROADMAP**.

## Local commands

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -B -m pytest tests/test_execution_acceptance.py -q -p no:cacheprovider
python -B -m pytest tests/test_state_store_handover.py tests/test_series_a_control_plane.py -q -p no:cacheprovider
python -I -B tools/execution_acceptance.py --help
```

The CLI requires a bundle plus `--source-revision`, `--runtime-revision`,
`--runtime-boot-id`, `--run-nonce`, `--authority-key`, `--authority-key-id`,
`--runtime-key` and `--runtime-key-id`. It reads only the explicitly named files,
prints a result to stdout and uses the current UTC time; there is no CLI time
override, request executor or publication flag.

## Integration boundary

The passive observer must continue to retain its five required `NOT_PROBED`
records. A future independently reviewed consumer may combine those observations
with qualifying execution evidence, retaining their distinct provenance. It must
not overwrite passive counts or treat this tool's structural success as runtime
readiness. The existing compact publisher, canonical verifier, artifact reader,
auth gate and workflow remain owned by their current lanes.

Related source contracts inspected for this change: `szl_dsse.py`,
`szl_operator_auth.py`, `szl_eval_arena.py`, `szl_agent_loop_governed.py`,
`tools/readiness-harness/README.md`, `probe_runner.mjs`, and the canonical compact
publisher. No endpoint requirement, status allowlist or existing gate changes.
