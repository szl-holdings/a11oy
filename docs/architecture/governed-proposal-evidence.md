<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Governed proposals: evidence and capability contract

Date: 2026-11-16. Status: implementation candidate plus explicitly marked ROADMAP.
Taxonomy: services, governance, provenance, and the existing console presentation layer.

## Decision

Use the existing governed edge contract as the shared boundary between the Ask
console and inference. Expose observed evidence and exact model identity alongside
each proposal. Preserve the existing execution gates: a successful model response,
a matching hash, and a populated index do not authorize an action.

This change adds no model framework, storage engine, execution endpoint, signing
key, or alternative HF writer. It connects existing components and makes their
limits testable.

## Observed system and corrected diagnosis

The public proposal route already exists at
`https://a-11-oy.com/api/v2/governed-infer`. Before this change, the actual
`/console` page (`pages/console.html`) had no client for that route. The edge
also read Second Brain counts from the wrong JSON level.

On 2026-11-16 the canonical Second Brain response used
`szl.khipu.compound-second-brain.v1`, with 55 documents and 484 corpus chunks
under `memory`; its separate retrieval-handle count was 9,465. These counts
describe different sets. They must not be added together, called public content,
or described as training authority.

The same response reported `UNAVAILABLE_MODEL_TAG_MISSING`: the profile expected
`khipu:latest` and had no exact served-model observation. An index can be built
while grounded navigation remains unavailable. A generic serving model must not
be renamed to satisfy that identity gate.

Storage was writable during this investigation: its fenced writer held an active
lease, all seven stores were restored, and there were no active errors. An older
`STATE_STORE_RELEASED` response represents the former container releasing its
lease during handover; it is not evidence by itself that durable storage is
missing. The canonical diagnostic remains
`/api/a11oy/v1/storage/status` and ADR-0001.

These observations are dated diagnostics, not permanent health guarantees.

## Implemented contract

### Console and backend

The Ask page mounts a small client using the existing KANCHAY assets. It reads
the governed contract and health first, verifies their schemas and source
revision agreement, and offers the efforts that both surfaces advertise.
Input limits come from the contract. A page view never initiates inference.

An explicit submission issues one proposal POST with the selected effort,
prompt, optional supplied evidence, and output-token bound. The client has no
automatic retry. Stop or timeout ends browser waiting; it does not prove that a
provider computation stopped. A later response cannot overwrite that stopped
state.

The response panel shows the actual selected model, fallback and adapter
metadata, evidence handles, source revision, formula authority, Second Brain
observation, and unsigned receipt state. Model-generated text is inserted as
text, never interpreted as HTML. The LoRA option remains experimental and
requires explicit selection.

The interface checks structural and authority invariants before presenting a
response as a valid governed proposal. It locally recomputes the output hash and
canonical receipt-payload hash before showing a verified digest or enabling a
receipt download. A matching digest establishes content consistency only; it
does not authenticate a signer or establish that the generated prose is true.

### Second Brain projection

The edge accepts known schema versions and projects an allowlist:

- Built-index metadata, with distinct document, corpus-chunk, and retrieval-handle
  counts.
- Explicit public-chunk count only when the source provides that field. It is
  never inferred from the total corpus.
- Profile, expected model, served model, exact-tag observation, and artifact
  binding.
- Explicit `HANDLES_ONLY`, no raw contents, and no training authority.

Counts must be nonnegative safe integers; booleans, numeric strings, fractions,
negative values, and unsafe integers are unavailable. An unbuilt index does not
publish observed counts. Unknown schema versions stay unavailable.

For the canonical compound schema, claimed readiness also requires a built index
and an observed exact model tag. Contradictory input emits
`UNAVAILABLE_INCONSISTENT_READINESS`. The compatibility adapter for the legacy
schema retains that schema's distinct readiness semantics.

### Three identities with different jobs

| Field | Meaning | Limitation |
|---|---|---|
| `attempt_id` | Server-generated UUID for each inference POST, including failed requests | Ephemeral observation; not a durable trace or signed attestation |
| `request_id` | Deterministic request fingerprint | Repeated equivalent requests can share it |
| `receipt_sha256` | Digest of the deterministic receipt payload | Hash integrity is not signer authenticity |

The attempt ID is returned in the response envelope, response header, and Anatomy
event. It is intentionally outside the deterministic receipt digest. The contract
states this explicitly. A downloaded envelope can preserve both identities
without changing their meaning.

The edge continues to report `UNSIGNED_EDGE`, no durable receipt persistence,
no tools, and no action authority. GET paths remain free of signing effects.

### Provider-specific token limits

The LoRA model's documented parameter is `max_tokens`; fast and frontier use
`max_completion_tokens`. The worker now maps the common
`max_new_tokens` input to the documented field for each model family.
The prior worker sent the newer field to every model, so the smoke run's
requested 128-token limit cannot be assumed to have been enforced by the LoRA
provider. Offline tests cover minimum, intermediate, and maximum bounds for all
three efforts. This corrects the request contract, not the observed arithmetic
failure.

Cloudflare also instructs clients to use the chat template used in LoRA training
[12]. The exact training serializer/tokenizer revision has not been established
from the inspected canonical source. Repeated template markers support a
compatibility hypothesis, not a proven cause. No speculative template rewrite
or claim of improved model quality is included.

## Evaluation evidence

See [the authored live smoke baseline](../evidence/governed-edge-smoke-20261116.md).

Four authored cases, three efforts, and two trials produced 24 HTTP 200 JSON
responses with valid governance envelopes and recomputable output/receipt
digests. This confirms the tested transport and envelope behavior only.

The supplied arithmetic was 14 x 6 - 9 = 75. Fast and frontier produced 75 in
both trials; LoRA produced 45 in both trials. LoRA also emitted chat-template
markers in a missing-evidence case. The strict format predicate required a final
period and penalized otherwise correct fast/frontier arithmetic outputs. That
original predicate remains visible, with a separately labeled post-run numeric
diagnostic.

All paired outputs were identical under the configured seed and request budget.
These repeats do not establish independent statistical samples; caching was not
observed or excluded. Some outputs appeared truncated at the 128-token request
budget. No provider finish reason was available in these observations.

The smoke dataset is authored and small. It is not a held-out qualification
benchmark, a proof of model correctness, or authority to change production
`eval_status`. No promotion status was changed.

## Prior art and adaptation

| Primary source | Mechanism studied | Decision for SZL |
|---|---|---|
| Palantir OSDK and its React starter [1, 2] | Typed objects, queries, actions, and shared client contracts | Use the existing governed contract to drive the console; avoid separate UI assumptions |
| Palantir submission criteria [3] | Validate an action against the user and current object state at submission | Execution must revalidate server-side; a visible button or earlier successful check grants no authority |
| Palantir ontology-edit evaluations [4] | Evaluate proposed edits inside isolated simulations | Build future mutation evaluations against isolated state, with explicit expected effects |
| Palantir DevCon Orchestrator material [5] | Durable agent execution and coordinated versioning | Study the design while retaining the existing single release and storage authority |
| LangGraph persistence documentation [6] | Distinguish per-thread checkpoints from cross-thread knowledge | Keep execution recovery, retrieval knowledge, and receipt retention as separate contracts |
| NVIDIA evaluation documentation [7] | Repeated cases, bounded concurrency, custom evaluators | Adopt the measurement methods; add no NeMo Agent Toolkit dependency |
| GraphRAG paper and repository [8, 9] | Community summaries for questions spanning a corpus | Evaluate against existing hybrid retrieval before adding graph-summary complexity |
| OpenTelemetry Trace API [10] | Fresh root trace identity | Separate per-attempt identity from deterministic content identity; this change does not install OTel |
| Proof-carrying code research [11] | A consumer checks evidence against an explicit policy before accepting code | Bind any future proof claim to its proposition, assumptions, checker, and artifact |

NVIDIA's documentation states that NeMo Agent Toolkit was deprecated in October
2026 and is scheduled to reach end of life at the end of 2026. Microsoft's
GraphRAG repository states that it is largely in maintenance mode and is a
research demonstration, not an officially supported offering. These current
conditions favor adapting methods instead of adding either dependency.

The Palantir YouTube source was examined through its official title, description,
and related written material. No unavailable transcript or unobserved video
content is used as evidence.

## ROADMAP: evidence dependencies for operational capabilities

A useful next design is an explicit graph linking a capability to the evidence
required to use it. This is a proposed synthesis of existing ideas, not a claim
of global novelty or a deployed theorem.

A capability record would contain:

- Exact source, model, adapter, dataset, and policy identities.
- Evidence handles, access scope, observation time, expiration, and independent
  validity state.
- Evaluation-suite identity and outcomes, separated from serving availability.
- Proof artifact, theorem/proposition, assumptions, checker version, and checking
  result, when applicable.
- Signer identity and signature verification result, separately from hashes.
- Permitted effect types, target scope, budget, and required approvals.

Changing a dependency would invalidate only dependent capabilities. A model
upgrade could invalidate qualification evidence without claiming the storage
lease had failed. A lease transition could pause writes without deleting the
retrieval index. An expired sensor observation could remove a measured-energy
claim while allowing a proposal that explicitly reports unavailable energy.

The execution controller would revalidate this record at the commit boundary,
under the current principal, policy, object revision, and storage lease.
Idempotency and durable checkpoints would protect externally visible effects
during retries and crash recovery. These execution semantics must be tested with
actual failover scenarios before being described as operational.

This design could support practical projects such as resource-allocation plans
that carry their assumptions, environmental interventions that expose missing
measurements, and maintenance proposals that explain which evidence changed.
Their impact would need project-specific evaluation; none is claimed shipped.

## Mathematical and operational boundaries

The locked formula set remains exactly
`F1, F4, F7, F11, F12, F18, F19, F22`. Lambda uniqueness remains advisory
Conjecture 1, and Khipu BFT remains Conjecture 2. This change adds no formula to the
locked set and invokes no Lean proof checker.

A checked proof establishes its formal proposition under stated assumptions.
It does not establish that a model generated a true answer, that a sensor was
calibrated, or that production is running the referenced artifact. Those require
different observations and controls.

No measured joules are inferred from model/token counts or wall-clock latency.
No raw graph contents or private corpus documents are exposed to this proposal
client. Public index metadata does not expand content rights.

## Release and verification

The Cloudflare workflow now checks the UI client as part of the same source
boundary as the edge and rollback controller. Its path drift guard includes
the console entry, client assets, and client contract tests. Canonical
`hf-sync.yml` remains the only automatic HF writer; the existing
`COPY console/ ./static/` ships the assets and the existing pages deployment
ships `pages/console.html`.

Focused checks:

```text
node --check cloudflare/a11oy-governed-inference-worker.mjs
node --test tests/test_cloudflare_governed_inference_worker.mjs
node --check console/assets/szl-governed-proposal.js
python -m unittest tests.test_governed_proposal_client -v
python -m unittest tests.test_cloudflare_governed_inference_deploy -v
python scripts/check_banned_tokens.py --root . --allowlist .doctrine-allowlist
git diff --check
```

After a permitted merge, observe the exact deployed GitHub source, canonical HF
build, Cloudflare contract/health agreement, and the actual Ask page. Exercise one
explicit proposal and verify the attempt ID, output, evidence, and receipt
labels. A passing source test or completed CI run alone is not a live deployment
claim. Browser QA with fixtures demonstrates client behavior, not production
availability.

Open blockers remain explicit: missing exact Khipu model binding, no qualifying
LoRA evaluation, no durable edge receipt or trace persistence, and no action
execution capability on this public route.

## Sources

1. [Palantir OSDK React overview](https://www.palantir.com/docs/foundry/ontology-sdk-react-applications/overview)
2. [Palantir ontology-starter-react-app](https://github.com/palantir/ontology-starter-react-app)
3. [Palantir submission criteria](https://www.palantir.com/docs/foundry/action-types/submission-criteria)
4. [Palantir ontology-edit evaluations](https://www.palantir.com/docs/foundry/aip-evals/ontology-edits)
5. [Palantir DevCon](https://www.palantir.com/devcon/) and [official Orchestrator video](https://www.youtube.com/watch?v=ZTw66mjYATo)
6. [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
7. [NVIDIA evaluation documentation](https://docs.nvidia.com/nemo/agent-toolkit/latest/improve-workflows/evaluate.html)
8. [Edge et al., From Local to Global, arXiv:2404.16130v2](https://arxiv.org/html/2404.16130v2)
9. [Microsoft GraphRAG repository](https://github.com/microsoft/graphrag)
10. [OpenTelemetry Trace API](https://opentelemetry.io/docs/specs/otel/trace/api/)
11. [Necula, Proof-Carrying Code, POPL 1997](https://doi.org/10.1145/263699.263712)

12. [Cloudflare LoRA prompting](https://developers.cloudflare.com/workers-ai/features/fine-tunes/loras/), [Mistral LoRA parameter schema](https://developers.cloudflare.com/workers-ai/models/mistral-7b-instruct-v0.2-lora/), [DeepSeek parameter schema](https://developers.cloudflare.com/workers-ai/models/deepseek-v4.1-flash-1017/), and [GLM parameter schema](https://developers.cloudflare.com/workers-ai/models/glm-5.3/)
