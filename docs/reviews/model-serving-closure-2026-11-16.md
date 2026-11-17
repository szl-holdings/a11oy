<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Model serving closure: November 16, 2026

## Scope and evidence

This review joins the model-library audit, public inference service, A11oy operator API,
and user-facing Khipu entry points. It distinguishes repository presence, compatible
artifacts, model serving, and per-request evidence. It does not qualify every downloaded
repository, establish model accuracy, or increase the locked formula count.

A clean worktree began at A11oy commit
`2204f596d1` (`fix(x402): fail closed for unconfigured reference inference (#3573)`).
The operator's existing checkout had unrelated changes and was left intact.

### Observed model-library state

The read-only observation at **6:33 p.m. EST on November 16** established:

| Observation | Evidence and limit |
| --- | --- |
| 208 requested repository IDs | All unique; all 208 corresponding directories were nonempty. |
| 219 directories in the library | Includes additional repositories. This is not a serving count. |
| Original manifest: 147 repositories, 2,192 files | Every listed file was present and matched its expected size. |
| Manifest payload: 156,074,680,642 bytes | Expected and actual sizes agreed; no content-hash verification was performed for all weights. |
| Manifest SHA-256 | `ff37bf9c47256fb1864d8b890e124c88e0924ebdd0db995b875785412682e4d5`; this identifies the manifest, not the weight bytes. |
| Static classification of the 208 trees | 134 contained an adapter configuration somewhere in the tree; 36 had recognized weights without one; 38 lacked a recognized weight filename. Filename classification does not establish compatibility. |
| Adapter dependencies | 91 trees had a top-level adapter configuration. Their base chains reached local weight-containing directories; two bases were GGUF-only without a Transformers configuration/tokenizer. This is not a PEFT load qualification. |
| Advertised running models | Loopback services listed `glm-5.3-flash` and `Bonsai27B`; both health and model-discovery requests returned HTTP 200. |
| Inference on those two services | Not exercised by this read-only audit. No claim of per-request inference proof follows from the health response. |

The downloader's completed log reported 208 successful downloads and zero failures.
That statement is consistent with directory presence; it is not evidence that 208 models
are loaded, compatible, routable, evaluated, or approved. The old 170.4 GB figure included
files beyond the original manifest; it must not be described as the manifest payload.

### Observed public CPU-lab contract

At **6:38 p.m. EST**, public GETs identified:

- Space revision `675d3fb83f0e1b765eeed5374e17faee656ecc6a`.
- Declared Forge source revision `c94e9218093e0815745cbd5dccaddea1797379a3`.
- Model `SZLHOLDINGS/SZL-Khipu-1.5B-GGUF@67d60ec577730747055491640cfb91fc4a4b5d25`.
- Expected and reported loaded GGUF SHA-256
  `13c1a1993063e1dff92f7413ccf48eaca6d48efc8801ae9af35961ae3396623a`.
- Governed health `READY`, with the declared controller, second-brain, and Nemo dependencies.
- Retired legacy `/v1/chat/completions`; active successor `POST /api/v3/governed-infer`.
- Public request shape: `prompt`, `max_new_tokens`, and `k` only. The server fixes public
  scope, requires grounding, forbids tool execution, and returns unsigned public receipts.

These are runtime-reported observations, not independent hardware attestation.
The authoritative retrieved contracts and source are:

- [Governed API contract](https://szlholdings-szl-model-inference-lab.hf.space/.well-known/szl-governed-inference-contract.json)
- [Governed health](https://szlholdings-szl-model-inference-lab.hf.space/api/v2/governed-health)
- [Pinned governed handler](https://huggingface.co/spaces/SZLHOLDINGS/szl-model-inference-lab/blob/675d3fb83f0e1b765eeed5374e17faee656ecc6a/app_governed.py)
- [Pinned public projection and receipt contract](https://huggingface.co/spaces/SZLHOLDINGS/szl-model-inference-lab/blob/675d3fb83f0e1b765eeed5374e17faee656ecc6a/public_transcript_export.py)

## Concrete break and repair

A11oy's authenticated CPU-lab route, legacy anonymous chat proxy, brainserve probe,
and Khipu voter still targeted the retired OpenAI-compatible endpoint. The old
authenticated route's 57 offline tests passed against a simulated old contract.
Those tests established internal behavior, not compatibility with the current service.

The repair has one supported operator entry point:
`/command-centre#cpu-work`, backed by
`POST /api/a11oy/v1/atelier/cpu-lab/turn`.

The request retains operator authentication, exact public-disclosure acknowledgment,
PUBLIC classification, deterministic policy admission, input limits, and a persisted
signed decision before outbound inference. It reads the pinned identity, governed
contract, and health; a disagreement stops before the inference POST. It sends only
the three supported public fields and never forwards the operator credential.

The response adapter validates the exact public schema, model identity, hashes,
receipt-to-result equality, public export hash, observer fields, and applicable
policy-witness fields. A usable proposal must be complete rather than truncated.
The adapter forwards the bounded answer and validated public source handles and citations.
The signed local outcome retains hashes of that public source metadata.
Unknown fields, private continuation fields, invalid receipts, identity drift, and
partial output cannot become a displayed answer.

| Upstream decision | Operator result |
| --- | --- |
| PROPOSAL / HTTP 200 | Completed local operation with proposal-only answer; no action authority. |
| ABSTAIN / HTTP 422 | Explicit abstention and signed local outcome metadata; no answer. |
| REVIEW / HTTP 409 | Explicit review state and signed local outcome metadata; no answer. |
| BLOCKED / HTTP 503 | Explicit blocked state and signed local outcome metadata; no answer. |
| Unknown schema, HOLD export, malformed body, or inconsistent receipt | Unavailable; no answer or automatic retry. |
| Timeout after dispatch | Outcome uncertain; no automatic retry. |

The local DSSE receipt records A11oy's decision and observed outcome.
It does not convert the provider's `UNSIGNED_LOCAL` output into an authenticated
model assertion. Hash consistency does not prove that a claim follows from a cited
source. The reviewed generator labels its claims MODELED and can attach its first
retrieved handle even when the answer contains no explicit citation. The UI must
not label that behavior semantic verification.

The legacy console panel now navigates to the operator form. Retired generation
routes return an explicit retirement result; GET metadata does not generate.
The retired voter is unavailable rather than always available by construction.

The shared HTTP transport preserves explicitly requested bounded JSON error bodies
without converting HTTP errors into success. It also makes only one address attempt
for a POST: a lost acknowledgment must not cause a second inference on another IP.
This is a consistency fix across provider callers, not an exactly-once guarantee.
Callers can require an exact success status; an unexpected 202 or 206 does not become
a completed proposal. An absolute socket deadline also bounds slow response headers,
bodies, and chunk framing, including TLS handshake time. The operator form's 90-second
request allowance covers three four-second preflights and the 60-second inference
budget with response grace.

The historical fabrication monitor remains unavailable because its evaluator depended
on the retired endpoint. It now returns an explicit RETIRED/UNAVAILABLE artifact and
exit code 2 instead of silently treating unavailable evaluation as a passing skip.
The scheduled workflow retains its failure gate. It files a fabrication finding only
for an actual FAIL + MEASURED + FABRICATION-DETECTED result; unavailability cannot
masquerade as measured fabrication. A qualified governed evaluator remains required.

Taxonomy: the new pure contract adapter belongs to **services/provenance**.
It performs no networking, signing, storage, training, or action execution.
Its deployment file is explicitly copied by the existing Dockerfile.
The canonical HF synchronization remains the only automatic Space writer.

## Validation observations

The following are local integration observations against the real public service.
Each live canary used the authenticated local Atelier route with real policy,
transport, and contract validation, a new local ledger, and an ephemeral validation
signer. These signatures are not production-signer or deployment evidence. Each live
invocation made three metadata GETs and exactly one inference POST.

| Observation, UTC | Result and limit |
| --- | --- |
| Live canary 1: November 16, 23:54:51-23:55:09 | Local HTTP 502; no answer released. It exposed the controller's lowercase adapter_revision normalization. After that correction, the unchanged provider response still correctly failed INCOMPLETE_OUTPUT: 32 output tokens and finish_reason=length. Decision and unavailable-outcome records both verified. |
| Live canary 2: November 17, 00:08:10-00:08:25 | Provider returned a structurally valid PROPOSAL, 493 prompt tokens, 17 completion tokens, and finish_reason=stop. Local HTTP 503 exposed a missing validator-return field before outcome append. Only its signed decision was retained; this was not a completed local operation. |
| Offline exact-capture replay: November 17, 00:14:02-00:14:03 | After returning copied validated source metadata from the adapter, the same captured documents produced local HTTP 200 / COMPLETED. Both local signatures and the decision/outcome chain verified. Three public handles and zero explicit citations matched the UI contract. Actual network calls: zero. |

All four replayed documents matched the second live canary's original raw-byte
SHA-256 observations. The response body hash remained
38e1518b0f9f02ddf8952cd95604a194a4b5751f18c4344959f025f1eb2645f8;
its original inference receipt hash remained
e86ef4a1abe7f279f6b8f475151eb43bf50a14ae3423bc6fd9b541aa69fdfa02;
its public export hash remained
9662d3d5ec1fc31e5f35fcda6603355c785798a0c08e9adac8a5cbf2fe97ac27.
Replay verifies the corrected integration against observed bytes; it is not a
second live success or evidence that the provider's unsigned assertion is authentic.

After rebasing onto main at ca2bd11de639ceef437f30634ebc98934d3900df, the
combined relevant suite passed **484 tests and 54 subtests** in 56.32 seconds.
It covered the adapter, authenticated routes, transport, shipped CPU JavaScript,
retired callers, fabrication workflow, Docker packaging, demo-critical routes, and
formula boundaries. During integration, explicit packaging coverage for the new
module and UTF-8 Node-test input corrected the failures those checks exposed.

A wider Windows run also exercised the existing command-centre-view suite. Its
symlink fixture cannot be created under this user's privileges (WinError 1314).
That test remains unchanged and is included in the Linux CI job; it was not
represented as a successful local check or disabled to obtain a green run.

The doctrine scan checked **4,915 files with zero banned-token hits**. The absolute
transport deadline suite passed 22 tests and 16 subtests, including slow headers,
bodies, chunk framing, TLS handshake cleanup, and POST replay prevention; those
checks are included in the combined result, not an additional success count.
An independent six-request concurrency check observed ordinary responses succeed
and slow responses time out without cross-request interruption or leaked watchdogs.

## What the primary research changes

These are engineering adaptations, with attribution. They do not transfer another
system's performance or proof claims to SZL.

| Source | Relevant lesson | Application here or next gate |
| --- | --- | --- |
| [Palantir Workflow Lineage](https://www.palantir.com/docs/foundry/workflow-lineage/overview) | Make objects, actions, model lifecycle, and dependencies inspectable together. | Bind the UI result to the exact API contract, source revision, model artifact, policy decision, and receipt. Extend this join to the private model-library inventory next. |
| [Palantir action submission criteria](https://www.palantir.com/docs/foundry/action-types/submission-criteria) | Action eligibility depends on parameters, object state, and execution context. | Keep backend admission authoritative. Recheck the live contract before dispatch and preserve the reason an action cannot proceed. |
| [NVIDIA Dynamo health checks](https://docs.nvidia.com/dynamo/latest/reference/observability/health-checks) | Frontend health, per-model readiness, and an active inference canary are different observations. | Do not infer a usable model from HTTP 200 or a discovered name. Show the scope and age of each observation. |
| [NVIDIA Triton metrics](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/metrics.html) | Requests, inference items, and backend executions count different things. | Define units, model identity, interval, and evidence source for telemetry. Missing joules remain unavailable, not zero. |
| [LangGraph fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) | Retrying a node can repeat external effects; missing acknowledgment is an unknown outcome. | Preserve intent and outcome separately. Stop implicit POST replay; require reconciliation before any future automatic retry. |
| [NVIDIA Dynamo repository](https://github.com/ai-dynamo/dynamo) | Distributed serving coordinates multiple engines and workloads; simpler deployments may need only their engine. | Measure the current two-GPU workload before adding a distributed serving platform. |
| [DistServe, OSDI 2024](https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf) | Prefill/decode placement should be evaluated against latency constraints and communication cost. | Compare candidate deployments on SZL hardware using time to first token, output-token latency, and goodput. Published speedups are not local measurements. |
| [Palantir DevCon 6 Agent Engine video](https://www.youtube.com/watch?v=mDGjptFvePY) | Official demonstration reference located. | A usable transcript was not retrieved. Technical conclusions above come from retrieved documentation and source, not inferred video content. |

## Mathematics and authority boundaries

Execution admission remains a deterministic backend policy decision.
Model output is proposal-only. Lambda remains advisory **Conjecture 1** and cannot
override a denial. Khipu BFT safety remains **Conjecture 2**.

The locked set is exactly **F1, F4, F7, F11, F12, F18, F19, F22**.
Its applicability must come from the compiled claim map in
`lutar-lean/claims/locked-formulas.v1.json`, its named Lean declarations, and the
corresponding kernel/runtime evidence. These claims do not establish HTTP retry
safety, arbitrary serving identity, distributed consensus, or answer quality.

The public admission contract remains:
`G = exp(sum(w_i log(x_i)) / sum(w_i))`, with
`admit iff G >= 0.80 and min(x) > 0`.
A model score, HTTP 200, arithmetic mean, or unsigned receipt does not authorize
execution. This integration does not alter those formulas or claim a new theorem.

## Remaining work and experimental direction

The following items remain explicit gaps or ROADMAP, not completed capabilities:

1. **Model-library qualification.** Join each requested repository to an immutable
   revision, verified content manifest, artifact type, base dependency, tokenizer,
   engine configuration, and bounded inference/evaluation result. Presence alone
   cannot make the 208 repositories operational.
2. **Cross-repository consumer migration.** The reviewed szl-serve recipe still refers
   to the historical OpenAI route. Its qualification result must be treated as
   divergent until it adopts the governed contract or an explicitly supported
   engine-specific contract.
3. **Current operational evidence.** Health and model discovery do not establish
   successful inference on the two GPU services. Model or revision changes must
   invalidate old inference evidence rather than inherit a permanent green status.
4. **End-to-end deployment proof.** A local test or merged source change is not a
   production rollout. Confirm canonical HF synchronization, build identity, and
   the actual frontend request after deployment.
5. **Grounding quality.** Evaluate claim entailment and citation accuracy separately
   from structural receipt validation. Record abstention and unsupported-claim
   rates on representative, independently held-out tasks.
6. **Durable operation reconciliation.** Extend operation IDs across downloads,
   deployments, and remote receipts; make timeout recovery inspect remote state
   before repeating an effect. This requires explicit idempotency support.
7. **Energy and latency experiments.** Use real exporter deltas and workload-specific
   service targets. No fabricated joules, carbon, speedups, or generalized SLO claim.

Current main also contains the per-capability Frontier readiness projection described
in [the readiness contract](../frontier-readiness-contract.md). This integration must
preserve that backend-derived predicate and reason contract. The existing Canonical
Evidence Graph and ORO inspection seam are the structures to extend; a second graph
or competing readiness engine is unnecessary.

A useful next extension is a deterministic explanation of the smallest
missing evidence set that prevents a requested action. The operator could see
which artifact, permission, runtime observation, or policy witness would change
the decision, with provenance for each requirement. This is a proposed software
capability, not a novelty claim or a proof of autonomous correctness.

A second direction is constrained scheduling across quality, latency, and measured
energy, with policy eligibility applied before optimization. Start with public
source retrieval and reproducible scientific workflows; expand only after the
evaluation and failure-recovery behavior is demonstrated. Applications such as
disaster-resource coordination and accessibility need dependable provenance and
clear uncertainty before they benefit from more autonomous execution.
