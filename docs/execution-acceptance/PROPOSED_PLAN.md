<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Five required execution contracts: proposed bounded plan

Evidence class: **DECLARED**. Execution status: **BLOCKED**. No request has been
executed by this change. This document is a reviewable proposal, not an approved
or signed plan. It contains no usable credentials or fabricated observations.

Source inspected: `d0decc4f6b51145a9bebb735ad13f135403687b6`. Any later admission
must inspect the exact deployed source and regenerate the source-bound plan.
The only proposed origin is `https://szlholdings-a11oy.hf.space`.

The proposed producer would perform at most one request for each of these five
contracts, with no automatic retry. Reads for an explicit effect readback must
be admitted separately; their route, authorization, bounds and privacy contract
are not implied by this proposal. Unexpected response, authority, source, boot
or receipt identity stops the producer, retaining the failed evidence.

| Case | Explicit proposed input | Effects to review before admission | Required positive observation |
|---|---|---|---|
| `policy-decide` | `{"agent":"execution-acceptance","request_id":"<approved-run-nonce>:policy-decide","action":{"operation":"inspect-synthetic-record","record_id":"acceptance-only"}}` | The handler appends a verdict to its in-memory audit ring. Its current short `receipt_hash` is not by itself a verified DSSE receipt. | Expected allow/deny decision from the approved request, matching request ID and audit readback; no claim that an advisory Lambda value is authorization. |
| `policy-compliance` | `{"framework":"NIST"}` | Current handler selects the declared framework record. No external certification or live compliance validation is implied. | The selected framework and expected response schema; an authenticated observation receipt bound to this response, with the proposed readback adapter reviewed first. |
| `operator-ask` | `{"question":"Which eight formula identifiers are locked under Doctrine v11?"}` | Inspect the exact answer route, grounding behavior and possible model/provider call before allowing it. | Exactly F1, F4, F7, F11, F12, F18, F19, F22 with attributable grounding; a refusal or unavailable answer remains uncovered. |
| `eval-run` | `{"suite":"core_honest_v1","model_id":null,"execution_mode":"live"}` | `model_id` is intentionally unresolved. A real admitted model, provider/budget, existing operator identity and suite hash must be selected. The endpoint signs a receipt and ingests into the forum. | Actual selected-model execution, per-case accounting, valid outcome evidence, response and receipt verification/readback. A reference or MODELED run does not qualify live evaluation. |
| `agentloop-run` | `{"task":"Return the integer result of 2 + 2 without tools, code execution or external actions.","mode":"chat","model_id":null,"eval_suite":"core_honest_v1","max_retries":0,"sandbox":false,"consult_brain":false,"allocate_energy":false}` | `model_id` is unresolved. The exact planner, model/self-eval calls, approval gate, signer and forum effects must be bounded before execution. Request flags must be honored by the actual implementation, not merely present in JSON. | A completed bounded chat loop and self-eval with verifiable receipt/readback. A MODELED plan alone, blocked step, missing model, or unsupported side effect does not qualify. |

Both proposed model request bodies must also include an explicit
`execution_limits` object: `max_model_requests`, `max_output_tokens`, and
`max_elapsed_seconds`. For the current eight-case suite, the separate eval and
single-chat-step loop require capacity for eight and nine client model requests,
respectively. Values must be selected with the real provider, model and approved
task; they are intentionally not supplied as approved defaults in the table.
The [bounded runtime path](BOUNDED_RUNTIME.md) enforces these client limits but
does not establish a provider billing ceiling or complete acceptance evidence.

The current standalone validator rejects missing limits or model identifiers, MODELED eval
requests and agent plans that request sandbox execution, retries, brain context,
energy allocation or an embedded approval object. Supporting those effects would
need its own review and actual existing authority. No second approver identity
is inferred or created. The first proposed lane deliberately does not request
code execution; this is not proof of code-execution readiness.

## Inputs still required before any execution

1. Exact protected GitHub SHA, immutable HF runtime revision and boot identity,
   observed independently of the submitted bundle. Generate a fresh run nonce.
2. A reviewed real model/provider and its accepted resource bound for the two
   unresolved model IDs. The null values above are not defaults and must not run.
3. Actual existing operator credential admission. The source resolver uses
   `A11OY_CODE_ADMIN_KEY`; the validator never reads it. An owner delegate's
   instruction is not a substitute for a missing runtime credential.
4. Independently admitted public-key pins for approval and runtime observation
   roles. The proposal supplies no keys. Their separation prevents a runtime
   observation signer from approving its own plan; it does not claim two human
   reviewers. Existing distinct-second-approver requirements remain in force for
   any future code-execution scope.
5. Endpoint-specific response and readback JSON-pointer assertions, and adapters
   that prove receipt identities rather than relabeling current short hashes or
   unsigned records. Those adapters are absent from this change.
6. A signed plan binding every payload, origin, source, runtime, boot, nonce,
   operator reference, short validity window, request count and zero retries.
   The plan must come from admitted authority before any effect.

The producer and a readback adapter are **not implemented** here. The offline
validator prepares their binding contract; it cannot turn this proposal into
authority, qualify a runtime, or modify a passive readiness verdict.
