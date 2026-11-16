<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Frontier design: evidence that connects operations, mathematics and the interface

Research date: 2026-11-16. This note distinguishes the implemented Evidence
Inspector slice from proposals. It makes no claim of novelty,
production completeness, or independent verification of observer assertions.

## Decision

Use one inspectable operational model across the API and interface. A status
must expose its source, observation, scope, missing evidence and authority.
The existing CEG is the integration point; a new orchestration framework or
replacement frontend is not required for this slice.

The implemented change provides stable per-process environment observations,
bounded input processing, exact query digests/counts, cached source-witness
binding, explicit temporal assessments and an accessible inspector on
`/frontier`. It introduces no action endpoint, new signing authority,
energy estimate, paid dependency, or additional persistent store.

## What we adapted from primary sources

| Source | Useful pattern | SZL adaptation and limit |
| --- | --- | --- |
| [Palantir Ontology](https://www.palantir.com/docs/foundry/ontology/overview) | Shared objects, properties, links and actions across applications | Keep source revisions, runtime boots, model artifacts and observations in one typed vocabulary. Reading an object never grants the right to perform an action. |
| [Palantir Workflow Lineage](https://www.palantir.com/docs/foundry/workflow-lineage/getting-started) | Inspect connected objects and drill into their details | Display actual CEG parent references and raw records. Do not generate plausible-looking relationships from similar model names. |
| [W3C PROV primer](https://www.w3.org/TR/prov-primer/) | Distinguish entities, activities, agents and derivations | Keep artifacts, observations and observer identity separate. CEG content identity is not authenticated authorship or verified causality. |
| [Palantir AIP Evals](https://www.palantir.com/docs/foundry/aip-evals/overview) | Test cases, evaluator functions and repeated-run comparisons | Version the data, evaluator, source and model, then retain the denominator and trial results. An HTTP success is not an outcome evaluation. |
| [tau-bench paper](https://arxiv.org/abs/2406.12045) | Evaluate resulting state and reliability over repeated trials | Test whether the intended deployment or state transition actually occurred. Include wrong-source, stale-evidence and uncertain-effect cases. |
| [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) and [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | Durable checkpoints plus explicit admission and replay-safe effects | Strengthen the existing controller's intent records, idempotency and provider reconciliation. Checkpointing alone does not promise exactly-once external effects. |
| [OpenTelemetry GenAI agent conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md) | Structured agent, workflow and tool spans | Pin a schema before attaching real trace/span IDs. The conventions are developing; schema validity, measurement meaning and authenticity require separate checks. |
| [NVIDIA migration guide](https://docs.nvidia.com/nemo/agent-toolkit/latest/resources/migration-guide.html) | Separate execution adapters, observation/governance and evaluation | Reuse the separation without adding every vendor dependency. Inventory actual packages before assuming that the SZL NeMo surface depends on the retired toolkit. |
| [Lean axiom reference](https://lean-lang.org/doc/reference/latest/Axioms) | Inspect transitive proof dependencies | Pin theorem statements, repository revisions, Lean versions and accepted axiom policy. Bind theorem assumptions to actual runtime records before claiming applicability. |

NVIDIA's current documentation says NeMo Agent Toolkit was deprecated in
October 2026 and reaches end of life at the end of 2026. Its migration path
names Relay, Helix and Fabric. This is a reason to inspect dependency pins,
not evidence that a repository or page containing the name NeMo needs a rewrite.

The official Palantir Developers video
[Building with Palantir AIP: the Ontology Software Development Kit](https://www.youtube.com/watch?v=vSJ5H00V7Es)
was located and its indexed metadata/chapters inspected. No full transcript was
available; the technical claims here rely on the primary documentation rather
than a claim to have watched or transcribed the video.

## Fit with SZL doctrine

The established locked set remains F1, F4, F7, F11, F12, F18, F19 and F22.
Lambda uniqueness remains Conjecture 1; Khipu BFT remains Conjecture 2.
This work introduces no change to those classifications or formula definitions.

The graph carries claims without silently promoting them. Four independent
questions must remain visible:

1. Is this the same content?
2. Is its asserted origin authenticated?
3. Does the evidence establish the claim under its stated assumptions?
4. Does current policy authorize the proposed action?

A digest answers the first question. An appropriate verifier may answer the
second and third. Authority is a separate decision. A green-looking interface,
a `VERIFIED` string, an invariant label or a theorem name does not answer all four.

Proof applicability needs a manifest identifying the theorem, exact statement
digest, proof revision, Lean version and transitive axioms, followed by an
explicit binding from runtime observations to preconditions. Proof checking
and checking the sensor are different obligations.

Energy claims must use real measurements bound to the execution interval,
meter, workload and runtime boot. Tokens, estimated utilization, or a provider
name must not be converted into invented joules. Unknown energy stays unknown.
Model quality and measured resource use should initially remain separate
metrics so a scalar score cannot hide a regression.

## Next experiments, with acceptance criteria

These are proposed experiments, not capabilities delivered by the inspector.

### 1. Evidence-directed investigation

Given a blocked claim, identify its missing premises and propose the smallest
useful read-only probe. Start with a deterministic rule set and replayed records;
compare it with the current operator investigation sequence before introducing
an autonomous planner.

Example: when deployment source B differs from runtime source A, request build
identity and the provider's deployment observation before running another model
evaluation. Do not schedule expensive inference to answer a source-binding
question.

Accept when it resolves known blockers with fewer unnecessary calls while
preserving correctness, and refuses to invent missing source, time or authority.
Track actual calls, elapsed time and independently measured energy when present.
Unknown costs cannot be silently imputed. Novelty needs separate literature and
patent investigation; none is asserted here.

### 2. Counterfactual release rehearsal

Replay a proposed release against captured runtime and policy evidence.
Ask which claims would change and which assumptions would become invalid.
Keep the rehearsal isolated from provider effects. Produce an explanation of
the failed premises before a deployment is attempted.

Accept when held-out cases correctly identify stale source witnesses, missing
snapshot objects, changed proof inputs and expired grants. A successful replay
does not authorize publication; it provides evidence for the existing gate.

### 3. Outcome and repeated-trial evaluation

Add estate-specific tasks with pinned data and independently observed outcomes:
wrong revision behind a healthy route, unsigned but hash-correct artifact,
empty evaluation set, stale measurement, interrupted provider effect, and
contradictory identities. Keep training and held-out evaluation separate.

Accept when the report preserves trial count, denominator, failures and policy
violations. Report no evidence for an empty denominator. Evaluate consistency
across trials rather than reporting only the best successful run.

### 4. Proof-to-runtime assumption binding

Choose one existing proved invariant and bind every required input to a
specific runtime evidence record. Validate the proof manifest and the runtime
preconditions independently. Keep unsupported assumptions explicit.

Accept when a changed runtime input invalidates the applicability binding
without falsely invalidating the underlying theorem. Conjectures must never
appear as checked proofs.

### 5. Resource-aware execution with measured tradeoffs

Once quality, latency and meter coverage are trustworthy, compare execution
backends on the same pinned task and report a Pareto frontier. Reject adapters
that cannot honor required capabilities before execution. Do not silently drop
configuration and still declare a backend ready.

Accept when every reported measurement has a defined boundary and provenance,
quality regressions remain visible, and missing instrumentation is represented
as missing. This is the foundation for useful ecological optimization.

## Operational completion boundary

Code review, tests, merge, publication, live source parity and live readiness
are separate observations. The canonical deployment workflow remains the only
publisher. Storage handover and object preservation must satisfy the existing
operational procedure before an old writer is replaced. The inspector neither
opens a maintenance window nor converts a release receipt into deploy authority.

## Storage configuration correction found during integration

The canonical configuration helper now explicitly converges the state-store
snapshot cadence to the [ADR-0001](adr/ADR-0001-a11oy-state-store.md) policy: a
30-second debounce, 300-second periodic capture under continuous writes, and a
900-second alert threshold. An external 1,800-second periodic override had been
preserved because the helper did not manage these variables. That mismatch
extended the recovery interval and caused recurring alerts even while the
snapshot worker progressed. The source change corrects the interval instead
of raising the alert threshold. Provider readback must confirm convergence;
source tests alone do not establish the running process configuration.
