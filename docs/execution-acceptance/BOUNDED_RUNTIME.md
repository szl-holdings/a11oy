<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Bounded model requests

The existing Python evaluation and agent-loop handlers accept an explicit
`execution_limits` object. This opts into a restricted client execution path;
it does not qualify a model, authorize a release, or produce the five-case
execution-acceptance bundle. Existing operator and tenant admission still apply.

```json
{
  "max_model_requests": 9,
  "max_output_tokens": 1152,
  "max_elapsed_seconds": 120
}
```

All three fields are required positive integers, excluding booleans. The server
ceilings are 32 model requests, 32768 total requested output tokens, and 300
seconds. Output reservations are consumed before dispatch and never refunded.
The deadline is checked before dispatch and while consuming results; late results
are rejected. It is not a guarantee that a remote provider stops work or that
local cancellation interrupts an outstanding network read immediately. No
monthly dollar ceiling or provider-internal retry bound is inferred from these
request limits.

The strict transport sends at most one HTTP request for each reserved call,
disables redirects, requires the selected response model, rejects tool calls,
and never moves to another model or retries an ambiguous result. Missing or
invalid output-usage accounting ends the budget; it cannot fund another request.
Model identity
must resolve to one explicit entry in an existing open-weight catalog. Catalog
membership is a declaration, not immutable-weight verification, license review,
or task qualification. Credentials remain server-side; neither request bodies
nor receipts carry them.

For `POST /api/a11oy/v1/eval/run`, supply the explicit `suite`, `model_id`,
`execution_mode: "live"`, and limits. The entire fixed suite and its resource
requirements are checked before generation. Governance must allow each prompt
and its egress classification before its model request. Restricted or air-gapped
input cannot use this network lane. The strict path uses the same single-request transport
as the engine instead of a router that may select additional providers. The
response retains every case, including unavailable or unexecuted cases; failure
does not become a passing score.

For `POST /api/a11oy/v1/agentloop/run`, also supply `mode: "chat"`,
`max_retries: 0`, `sandbox: false`, `consult_brain: false`, and
`allocate_energy: false`, with an explicit task and evaluation suite. This lane
has one chat step followed by that suite, sharing a single budget. It admits no
code execution, tool execution, behavior profile, embedded approval, or hidden
planning steps. Operator authentication and the configured tenant header remain
required. It does not confer second-approver authority.

`core_honest_v1` contains eight cases. A standalone evaluation therefore needs
capacity for eight model requests; one strict chat step and its self-evaluation
need nine. Running both contracts in an eventual acceptance plan needs capacity
for seventeen, even though they are only two top-level HTTP requests. The sample
limits above describe a bounded request, not approved production execution.

The budget recorded in native receipts reports client request reservations and
provider-reported output usage. It is not independent model evidence, metered
energy, verified billing, or an execution-observation signature. Existing
completion and model-qualification labels retain those distinctions.

The offline plan validator requires explicit limits on both model cases and
binds them into the approved request hashes. Runtime admission and enforcement
remain separate checks. The full acceptance producer, distinct approval-key
admission, process-to-HF identity binding, durable observation export, and
combined passive/execution release artifact remain outstanding. Preserve all
five passive `NOT_PROBED` records until those actual observations are verified.

## Shared engine rollout

The shared engine change is reviewed with
[A11oy #2855](https://github.com/szl-holdings/a11oy/pull/2855) and
[Killinchu #538](https://github.com/szl-holdings/killinchu/pull/538).
Both repositories bind the same engine bytes through the existing
`.github/shared-source-payload-manifest.json` contract. Killinchu retains its
existing callers; its absent strict-path companions cause an explicit refusal
before inference. A paired source review does not establish deployed parity.

Killinchu's existing main publisher restarts its live Space. A retained public
receipt-chain export can preserve captured evidence, but cannot establish
continuity for writes accepted after capture. Resolve that transition before
merging the peer change; neither this interface nor the paired manifest changes
the live ledger's durability.
