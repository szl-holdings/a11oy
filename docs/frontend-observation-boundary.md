# Command-bar observation boundary

Scope: the existing `static/shared/szl_command_bar.js` read path, already shipped
by the Dockerfile and mirrored by the canonical HF publisher. No new backend,
controller, publication path, credential, execution route or framework is added.

## Why this repair exists

The previous transport cleared its timeout when response headers arrived, before
`response.json()` completed. A stalled response body could keep a batch pending
while the previously rendered ONLINE state remained visible. The 20-second
interval could then start more overlapping seven-request batches. Those are
observation-lifecycle defects, not evidence that the underlying service failed.

The original-source regression also accepted JSON-looking bodies under HTML or
incorrect media types, replacement-decoded invalid UTF-8, and unbounded bodies.
Tests distinguish those behaviors from actual production incidents.

## Implemented contract

- Reads are explicitly GET, same-origin, no-store, with redirect refusal and the
  existing same-origin credential boundary. Off-origin endpoint strings are
  rejected before network activity. No credentials are extracted or displayed.
- One deadline covers headers, streamed body bytes, strict UTF-8 decoding and JSON
  parsing. The maximum body is one MiB, including chunked responses whose declared
  length is absent or misleading. This cap also covers the existing inventory
  reader; an oversized inventory is UNAVAILABLE, never silently truncated.
- Deadline failure settles the observation even when a supplied transport ignores
  abort. Native transport cancellation is requested without waiting indefinitely
  for cancellation itself. Backend response bodies are not surfaced as errors.
- One batch per mounted bar may be pending. Repeated refresh triggers coalesce.
  Previous live styling and revision metadata are cleared while OBSERVING.
- Completed browser observations have a 30-second presentation lifetime. Expiry
  clears the old live state and marks the evidence region STALE. This is a UI
  freshness policy, not a backend receipt TTL, proof validity interval or lease.
- Hidden documents make no new scheduled reads. Returning to visibility checks
  expiry before reading. Detached bars stop their observation timer. Results that
  arrive while hidden or detached are not published as fresh visible evidence.
- ONLINE means the process-health read succeeded. Revision, process health,
  inventory, conjecture, formula count and receipt labels remain separate. No
  readiness, signature verification or authority is inferred from HTTP success.

The displayed `Observed at` is explicitly the time a browser read completed,
**not** the backend's update time, immutable deployment identity, or receipt
verification time. A backend that repeatedly reports stale data still needs its
own source-specific validity contract; this UI lifetime cannot certify it fresh.
Timers can be throttled or execution suspended by a browser/OS. The visibility
handler rechecks the wall and monotonic ages; the implementation does not claim a
hard-real-time guarantee during suspension.

The locked-eight catalog and Conjecture 1 remain unchanged. This repair creates
no new proven formula and changes no action-admission rule.

## Reproduction and regression

Run from the repository root:

```sh
node --test scripts/test_command_bar_observation.cjs
python -m pytest -q tests/test_holographic_command_bar.py \
  tests/test_command_bar_hit_target_contract.py \
  tests/test_console_evidence_runtime.py \
  tests/test_console_navigation_accessibility.py \
  tests/test_console_probe_fail_closed.py
node --test tests/test_console_source_runtime_evidence.mjs
```

The new Node suite executes the shipped transport and polling implementation,
not a parallel reimplementation. The existing holographic-command-bar Python
suite invokes it, so the pre-existing native test job discovers the checks without
changing a workflow. Tests use synthetic transport/body/clock conditions, including
positive controls for zero values and unchanged process-health semantics.

Isolated Edge qualification uses the exact JS/CSS bytes with a real loopback HTTP
server and clearly labelled synthetic responses. It exercises partial-body
stalling/cancellation, single-flight reads, failure/recovery, empty/error inventory,
phone/tablet/desktop containment, keyboard evidence controls and reduced motion.
It does not establish production browser, provider, model-quality, WCAG-wide or
whole-estate qualification.

## Primary references and adaptation boundaries

- Palantir OSDK React cache management documents normalized identity, query
  sharing, action-driven invalidation and optimistic layers separated from server
  truth: https://github.com/palantir/osdk-ts/blob/main/docs/react/cache-management.md
  The general invalidation principle is relevant; SZL does not install OSDK or
  borrow an optimistic-success policy for evidence or authority.
- Palantir Workshop Data Freshness ties a displayed update time to the configured
  datasource's indexing history:
  https://www.palantir.com/docs/foundry/workshop/widgets-data-freshness
  SZL instead labels its browser observation clock explicitly because the existing
  endpoint is not a datasource-index freshness attestation.
- Palantir's developer toolchain separates object/action/query interfaces and
  compute integration: https://www.palantir.com/docs/foundry/dev-toolchain/overview
  The official `Build with AIP: Compute Modules` video is linked there. Its title
  and description were inspected; no transcript or full-video review is claimed.
- *Auditable Agents*, arXiv:2604.05485v1, distinguishes lifecycle coverage, policy
  checkability and evidence integrity from mere observability:
  https://arxiv.org/html/2604.05485v1
  Its authors disclose the absence of a single end-to-end deployment audit and
  other limits. No results, latency figures or completeness claims are transferred
  to SZL by this repair.

These references motivate state separation and explicit bounds. They do not
supply SZL's numeric UI lifetime, prove deployment readiness, or grant execution
permission. No proprietary vendor implementation is copied.
