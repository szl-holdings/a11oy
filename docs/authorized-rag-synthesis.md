<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Authorized RAG answer handoff

Status: **contract implemented and tested; deployed source/provider admission unavailable**.

The agent previously asked a model to answer from file paths and abbreviated
hashes. It discarded the retrieved chunk text. Passing that text straight to
`agent_model_complete` would introduce a second problem: that function can choose
and fall back across local and external providers without a per-source transfer
grant. The operator credential does not identify a tenant or a named principal.

The agent now requires an explicit `answer_synthesizer` capability at FINALIZE.
Without it, the run returns `CONTENT_ADMISSION_UNAVAILABLE`, `i_dont_know=true`
and HALT before calling a model. This is an intentional admission requirement,
not a claim that the deployment has acquired private-corpus or provider authority.
The existing generation, budget and execution gates remain in force.

The actual `/api/a11oy/code/agent/status` route reports content admission as
unavailable and exposes inference-backend readiness separately. A configured
provider cannot turn that route into an available source-answer service.

## Controller contract

`AuthorizedRagSynthesis` lives in the existing shared agent module
`a11oy_agent_loop.py`. Its immutable identity and grant objects are Python
capabilities supplied by the authenticated controller. They are not accepted as
request fields, planner output, document metadata, or model-generated decisions.

| Capability | Required binding |
|---|---|
| `SynthesisSubject` | Authenticated named principal, explicit tenant, immutable policy revision |
| `SynthesisHandle` | Published generation and digest; chunk/node/repository/path/source IDs; full content SHA-256 |
| `SynthesisSourceGrant` | Exact subject and handle, immutable source revision, explicit PUBLIC/PRIVATE visibility, source tenant for private data, strict allow |
| Authorizer | Current source-access verdict for that subject and complete handle; called again immediately before model egress |
| Hydrator | Full original bytes from the exact authorized published generation, preserving complete identity |
| `SynthesisBackend` | One fixed provider ID, model ID and LOCAL/EXTERNAL trust domain, with a callable that cannot fall back to another destination |
| Provider admitter | Explicit strict-True decision for the subject, all source grants, selected destination, task digest and answer-synthesis purpose; rechecked before egress |

The adapter refuses missing or ambiguous identity, mutable revision labels,
unknown visibility, wrong tenant, denied or changed source grants, missing or
changed provider approval, handle-only records, duplicate sources, and invalid
content digests. Private source text can reach only an explicitly admitted LOCAL
backend for the same source tenant. A grant for a public repository name does not
establish the visibility of its indexed documents.

`a11oy_org_rag.hydrate_answer_evidence` is the controller-only SQLite adapter.
It requires an explicit authorization callback before opening its read
transaction, checks the active generation and stored digest, selects exact chunk
identities, rejects duplicate/missing rows, and verifies complete UTF-8 bytes
against their recorded SHA-256. It never registers a route or changes the index.
An independently authorized Second Brain hydrator can implement the same
controller callback; it must preserve these identity and access bindings.

The generic `agent_model_complete` callback remains an API compatibility
parameter. It is not used as a fallback for this source-content handoff. Do not
attach its automatic provider fallback directly to `SynthesisBackend.complete`.
An approved deployment needs a fixed-destination wrapper which enforces the same
provider and model before accepting source bytes.

## Content and output boundaries

The controller snapshots identity fields at retrieval time. It does not add raw
source text to `Evidence`, step events, receipt payloads, public status, or the
Living Anatomy/Ouroboros observation feeds.

RAG trace evidence exposes ordinal source handles only. Arbitrary source paths,
citations, error messages and hash fields cannot pass through that public trace
projection before admission. Full source identities remain in the controller
snapshot and the admitted synthesis prompt. The loop independently validates the
callback's success envelope and refuses empty answers, stubs, provider errors or
attempts to grant voice authority. Agent SSE responses carry the explicit halt
reason and admission state. A known missing-admission halt reports `NOT_INVOKED`;
other failed or ambiguous synthesis attempts report `NOT_CONFIRMED`.

The public query response truncates text at 1,200 characters, while its existing
SHA-256 covers the full stored chunk. Synthesis therefore rehydrates the complete
chunk, verifies that full digest, and only then selects a bounded UTF-8 prefix.
The prompt contains both the full content hash and excerpt hash, exact byte span,
source revision, full source identifiers, and published generation identity.
It permits at most six sources, 32 KiB of hydrated content per source, 2,048 bytes
per excerpt, an 8 KiB task, and a 32 KiB serialized context.

Only the task and admitted source records enter the prompt. Unbound conversation
history is not forwarded. Source records are quoted as untrusted data and cannot
grant tool, training, promotion, merge or provider authority. The returned model
identity must match the fixed backend; malformed/error responses fail closed.
Error surfaces use an allowlist of fixed reason codes rather than exception text.

The adapter returns only answer text, model identity, source count, and a context
digest. Its admission record explicitly says `semantic_support_verified=false`.
Hashes prove byte identity; they do not prove that a generated claim follows from
the source. The pre-existing count-based confidence score is not upgraded into a
calibrated correctness probability by supplying content.

Voice/expression is a separate egress destination. This adapter grants it no
authority, even if the existing optional voice environment switch is enabled.
The authenticated answer response is the only output destination admitted here.

## Exact deployment blockers

Current `szl_operator_auth.principal_from_headers` returns only `operator` and
`two_person_attested`; its own documentation states that it does not identify who
sent the credential. Current org RAG rows have no tenant ownership, visibility or
ACL authority. Several source identifiers also lack a full immutable upstream
revision. `agent_model_complete` can select a different local/remote destination.

No request-body field, operator boolean, environment inference credential, model
label, repository name, or self-reported document attribute can fill those gaps.
This patch intentionally does not create such grants. Before enabling synthesis
on a deployed route, the controller must supply:

1. A verified credential-to-principal and tenant mapping.
2. A revision-bound source registry with ownership, visibility and ACL decisions.
3. A fixed provider/model destination and explicit source-transfer approval.
4. The corresponding controller-bound adapter injected into `run_agent`.
5. Independent answer-support and abstention evaluation before claiming factual
   quality or production qualification.

Because `a11oy_agent_loop.py` is shared byte-for-byte with Killinchu, publication
must include its reciprocal peer payload and updated shared-module manifest.
The default missing-admission behavior applies to both peers. This change is
separate from the read-only Second Brain/Ouroboros/Living Anatomy wiring.

## Verification

`tests/test_authorized_rag_synthesis.py` executes the actual SQLite generation
writer, org retrieval, agent evidence conversion, authorized hydration, prompt
compiler, and FSM with an explicitly local model spy. It includes long Unicode
chunks whose query excerpts do not match the full-chunk hash, wrong identity,
wrong tenant, unknown visibility, private-to-external refusal, missing/revoked
provider and source grants, byte tampering, no raw text in traces/receipts, and
no unadmitted voice egress. No model or network call is performed.

The existing execution-guard suite explicitly simulates its controller admission
boundary to isolate the unchanged DAG/budget/quality gates; the new suite tests
the real content adapter separately. Existing generation tests continue to run.
These tests establish implementation behavior, not a deployed identity registry,
provider approval, semantic accuracy or production readiness.
