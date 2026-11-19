<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Frontier integration research: contracts, evidence, and outcomes

Date: 2026-11-16. Source baseline: a11oy `2204f596d17a854fba12cd204ab86019bc2e0712`.
Working branch: `cto/trust-receipt-binding-20261116`.

**Evidence class:** VERIFIED_SOURCE means inspected code or primary documentation; it does not mean a fresh production measurement. Existing describes source already present. MODELED marks research designs; ROADMAP marks unimplemented integration. This document establishes neither deployment readiness nor model qualification. No benchmark improvement, novel theorem, or superiority claim is made.

Doctrine v11 remains LOCKED: exactly eight locked formulas, `F1, F4, F7, F11, F12, F18, F19, F22`. Lambda uniqueness remains Conjecture 1 and advisory; it cannot authorize execution. Khipu BFT safety remains Conjecture 2. Existing canonical definitions, applicability rules, and verifiers govern; this research adds no formula to that set.

## 1. Existing source map and proposal contracts

The following is a source map, not evidence that every deployment serves the same implementation.

| Surface | Source owner and inspected boundary |
|---|---|
| `/command-centre`, `/a11oy/atelier` | [router](../../routers/command_centre.py), [view](../../routers/command_centre_view.py), and [browser application](../../routers/command_centre_web/app.js). Extend this active path after reconciling parallel work. |
| `/console` | [pages/console.html](../../pages/console.html) is the current source identified in this investigation; `console/index.html` is legacy. |
| `/trust` | [web/trust.html](../../web/trust.html) calls the native `/api/a11oy/v1/govern/infer` path. Its receipt subjects require separate checks. |
| Edge proposal inference | [Cloudflare worker](../../cloudflare/a11oy-governed-inference-worker.mjs) owns its contract, normalization, response, and unsigned receipt. |
| Owned-model proposal inference | [a11oy_governed_cortex.py](../../a11oy_governed_cortex.py) owns a different contract and request model for the local Khipu GGUF path. |

Both proposal implementations declare `/api/v2/governed-contract`, `/api/v2/governed-health`, `/api/v2/governed-infer`, and `/api/v2/anatomy/last`. Sharing paths does not make their wire contracts interchangeable.

| Contract detail | Cloudflare worker | Owned cortex |
|---|---|---|
| Contract schema | `szl.cloudflare-governed-inference-contract/v1` | `szl.a11oy.owned-khipu-cortex-contract/v1` |
| Response schema | `szl.cloudflare-governed-inference-response/v1` | `szl.a11oy.owned-khipu-cortex-response/v1` |
| Receipt schema | `szl.cloudflare-governed-inference-receipt/v1` | `szl.a11oy.owned-khipu-cortex-receipt/v1` |
| Route map field | `endpoint`, singular | `endpoints`, plural |
| Request fields | `prompt`, `effort`, `evidence`, `max_new_tokens` | `prompt`, `max_new_tokens`, `k`; extra fields forbidden |
| Signature label | `UNSIGNED_EDGE` | `UNSIGNED_RUNTIME` |
| Persistence | `NONE` | `EPHEMERAL_PROCESS_MEMORY_ONLY` |
| Authority | Proposal only; tools disabled; action authority `NONE` | Proposal only; tools disabled; action authority `NONE` |

The worker lists `fast`, `frontier`, and `lora` efforts and declares its LoRA evaluation `NOT_RUN`. The cortex request defaults to 64 new tokens and three handles; its limits are source-defined, not inferred from the edge implementation. Clients should select a schema-specific adapter and reject unknown schemas rather than guess field names.

An active, unpublished proposal integration exists in another worktree. Reconcile its diff and ownership before implementing overlapping routes or components; absence from this baseline is not absence from the estate. The older [separate route map](SEPARATE_ROUTE_MAP.md) and [completion boundary](SECOND_BRAIN_COMPLETION_BOUNDARY.md) remain useful evidence boundaries with their own cited revisions. They do not prove one joined runtime.

## 2. Accompanying trust correction

**VERIFIED_SOURCE:** at the inspected baseline, the trust page compared SHA-256 of the complete decoded DSSE payload with `receipt.payload_digest` or `receipt.digest`. These can describe different objects and algorithms. [`_governance_statement`](../../a11oy_vertical_feeds.py) places chain references inside a governance statement; those references are not the whole statement's SHA-256.

The accompanying implementation corrects those UI evidence scopes: it reports envelope signature verification, recognized statement semantics, chain-reference equality, and request binding separately. Its strongest verdict is `PARTIAL`; it never promotes signature validity into full-chain, answer, freshness, signer-authority, or execution-authority verification. A digest mismatch between unrelated subjects is not evidence of tampering; a valid signature alone is not evidence that the displayed request or action is authorized. Unsupported subjects remain unverified.

The native [`govern_infer`](../../szl_governed_api.py) calls `governed_turn` without an actor. The existing [backend test](../../tests/test_runtime_verifying_key_surfaces.py), `test_govern_infer_receipt_matches_the_assurance_signing_claim`, asserts `dsse is None`, a `DSSE_PLACEHOLDER` signature, and a recomputable SHA3-256 chain digest, even when signing availability is mocked true. This is a source/test contract, not a fresh live signature test.

The correction changes UI interpretation, not backend authorization. It must not add signing to GET requests, fabricate envelopes, or claim chain verification from signature verification. Merge, deployed-byte readback, and browser verification remain separate evidence.

## 3. Prior art to adapt

**Palantir.** Its [Ontology documentation][P1] connects operational objects, logic, actions, and decision lineage. [Action consistency documentation][P2] limits atomicity to Ontology edits; external effects are outside that transaction. Adapt a shared domain model and explicit effect boundaries. The inspected [OSDK action hook][P3] separates validation, application, errors, and pending state. SZL should additionally bind asynchronous UI results to the current proposal identity.

The [AutoResearch whitepaper][P4] organizes datasets, recipes, experiments, evaluations, weights, and outcomes as linked assets. Its example data is explicitly notional; no illustrated gains establish measured performance. Borrow versioned experiment records and outcome feedback. The official [DevCon 7 video][P5] metadata and description were retrieved through DC: title and Palantir authorship were confirmed, but captions were unavailable. No claim here depends on watching the video.

**NVIDIA.** NeMo's [runtime security FAQ][N1] says policy selection and identity enforcement belong to the application and that there is no universal failure policy across integrations. Its [tool-calling rails][N2] structurally validate declared tools, arguments, and result correspondence; they do not execute tools. The documented feature is experimental and engine-specific. Treat it as optional boundary defense; keep SZL admission, authority, and receipts authoritative. Test unavailable controls and malformed results explicitly.

**LangGraph.** [Interrupts][L1] provide pause/resume through persisted graph state, but resumed nodes can repeat earlier work. [Fault-tolerance guidance][L2] requires stable idempotency keys backed by durable state and cooperation from external services. A lost acknowledgement means the outcome is unknown. Adapt durable intent and reconciliation around effectors; checkpointing alone does not prove exactly-once external execution.

**in-toto.** The [Statement specification][I1] binds a predicate to explicit artifact digests. The [validation model][I2] separates recognized attesters, envelope checks, subject matching, and policy. This supports the trust correction: identify exactly which bytes each digest and signature cover. SZL's existing governance statement is not automatically an in-toto Statement.

**Evaluation research.** [Tau-bench][E1] evaluates resulting database state and repeated-trial reliability. [AgentDojo][E2] tests agents exposed to untrusted tool data and adaptive attacks. Adapt state-based outcomes, repeated trials, and adversarial fixtures. These papers supply evaluation methods, not scores for SZL.

## 4. Integration plan without a parallel platform

**ROADMAP:** converge the active proposal work on one typed client contract with schema-specific adapters. Validate responses at runtime; compile-time types cannot establish runtime provenance. Render pending, rejected, proposal delivered, signature unavailable, and outcome unknown as distinct states. Preserve model origin, evaluation status, source revision, and persistence labels.

A release manifest should relate frontend, API, verifier/policy, model artifact, dataset, recipe, evaluation, deployment, and rollback identities. Artifact identities belong in provenance; they must not become exact-SHA storage admission gates. Storage work must target [`a11oy_state_store`](../../a11oy_state_store.py) under [ADR-0001](../adr/ADR-0001-a11oy-state-store.md), using its integrity, fingerprint, and lease invariants. Do not introduce another canonical HF writer or database under the bucket mount.

For eventual authorized effects, record intent before a provider call; use a stable operation identity, bounded retries, and reconciliation. Separate `PROPOSED`, `ADMITTED`, `AUTHORIZED`, `EXECUTING`, `RECONCILED`, `FAILED`, and `OUTCOME_UNKNOWN`. These are proposed lifecycle states, not new authority in current inference.

Previously observed adapter/receipt drift, evaluation absence, and dataset eligibility holds require independent resolution. This document supplies neither artifact reconciliation nor training clearance. Training completion, HTTP success, and a health response cannot substitute for those records.

## 5. Research hypothesis: evidence-aware next-observation planning

**MODELED; implementation ROADMAP.** When evidence is insufficient, a planner could recommend the next permitted observation that would most improve a specific decision. Examples include checking a component identifier, requesting a fresh sensor reading, or locating the applicable manual revision.

Each candidate observation would carry its purpose, required permission, expected decision relevance, cost, latency, privacy implications, and expiration. A scoring heuristic could rank expected uncertainty reduction subject to those constraints. Its estimates would remain MODELED until calibrated against outcomes; they would not be probabilities of safety or additional locked formulas. The planner proposes observations and cannot authorize the repair itself.

Acceptance tests and experiment design:

- With no useful permitted observation, abstain and identify the missing evidence rather than invent a reading.
- A stale or mismatched asset identifier must prevent its evidence from satisfying another asset's requirement.
- Instructions embedded in retrieved manuals must not alter authority or the permitted observation set.
- Compare against a fixed checklist on a versioned, held-out task set. Predeclare the denominator, budget, and success criteria.
- Measure unnecessary observations, unresolved cases, invalid recommendations, and human review effort separately. Count failures and overrides.
- Accept the hypothesis only if it improves the chosen outcome under the same resource limits without increasing forbidden transitions. Report uncertainty and negative results.

## 6. Research hypothesis: counterfactual replay before promotion

**MODELED; implementation ROADMAP.** Replay an archived decision against a frozen evidence snapshot, policy revision, and model identity. Compare the existing system and candidate on the same inputs, then inspect proposed state transitions and witness differences.

A replay is a simulation, not an intervention in the physical world. Observational records cannot by themselves establish causal effects. External write connectors should be disabled or replaced with explicitly labeled simulation adapters; preview environment identity must propagate through every call.

Acceptance tests:

- Replaying the same deterministic verifier inputs reproduces its verdict; stochastic model trials record seeds/configuration where supported and report variation.
- Changing evidence bytes invalidates their prior binding. A stale authorization cannot authorize a changed proposal.
- Injected timeouts, duplicate messages, and lost acknowledgements cannot silently create a second authorized operation.
- Baseline and candidate see equivalent case snapshots; future outcomes cannot leak into their input context.
- A plausible response that violates the target state or admission rule fails.
- No simulated result changes a live asset, production receipt, training eligibility, or promotion status.
- Promotion requires recorded thresholds and independent review of failures; replay success alone does not establish field effectiveness.

## 7. Illustrative civilian workflow and completion criteria

**MODELED:** a repair-and-reuse service for community equipment could connect an asset, symptoms, permitted documentation, an operator's observations, a proposed repair, the operator's chosen action, and the subsequent functional test. The observation planner could reduce unnecessary inspections; replay could expose regressions before a model change reaches operators. Expected benefits include less discarded equipment and clearer maintenance records, but neither benefit is measured here.

Complete one bounded journey before expanding: load an asset, retrieve attributable evidence, create a proposal, show the applicable checks, retain human authority, and record an observed outcome through an authorized path. UI and API must agree about unavailable evidence, unsigned receipts, and unknown results.

Release evidence should include contract compatibility, subject-binding negative tests, environment isolation, retry/restart behavior, and the actual browser journey. Preserve existing required checks and parallel-work ownership. A successful source test is evidence for that tested boundary; deployment, durable recovery, model quality, and public benefit each require their own verification.

[P1]: https://www.palantir.com/docs/foundry/ontology/why-ontology
[P2]: https://www.palantir.com/docs/foundry/action-types/consistency-guarantees
[P3]: https://github.com/palantir/osdk-ts/blob/main/packages/react/src/new/useOsdkAction.ts
[P4]: https://www.palantir.com/assets/xrfr7uokpv1b/71GBpNOzMizxDnonP5d7ea/67a9967e58df7b8703269d0b60a33401/AutoResearch_and_the_Fine-Tuning_Ontology.pdf
[P5]: https://www.youtube.com/watch?v=qxeQQFSyY6k
[N1]: https://docs.nvidia.com/nemo/guardrails/resources/runtime-security-faq
[N2]: https://docs.nvidia.com/nemo/guardrails/configure-guardrails/guardrail-catalog/tool-calling
[L1]: https://docs.langchain.com/oss/python/langgraph/interrupts
[L2]: https://docs.langchain.com/oss/python/langgraph/fault-tolerance
[I1]: https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md
[I2]: https://github.com/in-toto/attestation/blob/main/docs/validation.md
[E1]: https://arxiv.org/abs/2406.12045
[E2]: https://arxiv.org/abs/2406.13352
