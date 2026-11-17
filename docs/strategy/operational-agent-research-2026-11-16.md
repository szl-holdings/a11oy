<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Operational agent research and integration decisions

Date: 2026-11-16. Source inspection baseline:
`2204f596d17a854fba12cd204ab86019bc2e0712`.

**Status: RESEARCH / MODELED.** The implementation slice described below repairs
an existing client contract. The larger designs are proposals with explicit
acceptance criteria; this document does not qualify a model, authorize execution,
establish a new theorem, or certify the estate as production-ready.

This extends [the living command strategy](living-command-fabric.v1.json) and
[the architecture](../architecture.md). Existing repository and runtime
authorities remain authoritative. The September inventory in the strategy is a
dated observation, not a current repository count.

## 1. Engineering decision

Develop the existing governed action path into a coherent operational product.
A user should be able to inspect the same decision through five views:

1. What was requested, for which tenant, and against which input state.
2. Which policy and authority admitted or refused it.
3. What execution actually occurred, including an uncertain transport outcome.
4. Which outcome was observed and which claims remain unverified.
5. Which evidence supports the result, with its source, freshness, and scope.

These views should consume one backend contract. A successful HTTP exchange,
a backend acceptance, a provider-reported result, and an independently verified
outcome are separate facts. A signed receipt demonstrates only what its verified
payload and trust chain establish; it does not automatically prove task quality
or a real-world consequence.

The near-term change repairs the currently served governed-agent client rather
than introducing another execution framework. No external framework dependency
is required by this research.

## 2. What the inspected system actually contains

| Boundary | Source evidence | Engineering consequence |
| --- | --- | --- |
| Served Python product | `serve.py`, `szl3d_holographic.py`, `static/3d/holographic.html` | The governed-agent module is an actual user-facing surface. Its request and result contract matters today. |
| Governed-agent client | `static/3d/surfaces/governedagent.js` | At the inspection baseline, the run request omitted required operator/tenant context, and success rendering could overstate unverified completion. |
| Existing execution boundary | `a11oy_code_runloop.py` and the agent-loop backend | Reuse the established Authorization and tenant headers. Preserve separate approvals, model qualification, doctrine gates, and server-side denials. |
| Canonical React build | `vendor/platform`, `scripts/create_canonical_web_artifact.py`, `docs/architecture.md` | Building an artifact does not bind its GraphQL, subscription, or Atelier contracts to the Python runtime. Runtime admission remains blocked until those contracts exist and are tested. |
| Historical web mirror | `web/` and the documented build boundary | This is not the canonical application. Filling unresolved imports with placeholder modules would conceal the integration problem. |
| Durable state | `a11oy_state_store.py`, ADR-0001 | New persistent operational state must use the existing store and lease/snapshot invariants. A second database or writer would create a new consistency problem. |
| Production publication | `.github/workflows/hf-sync.yml` | Retain the canonical publisher and bind source, published artifact, runtime readback, and execution evidence explicitly. |
| Doctrine | `AGENTS.md`, `.claude/rules/doctrine.md` | Preserve the locked-eight set and honest measurement labels. Source presence is not runtime proof. |

The public health and readiness responses observed during this review distinguish
service reachability from operational readiness. A healthy HTTP response cannot
establish signed provenance, qualified inference, reachable hardware, measured
energy, or a completed independently authorized execution. The readiness matrix
also distinguishes a declared endpoint map from actual probe and execution
coverage. Those distinctions must survive every UI aggregation.

## 3. Public prior art and its application

The following is an engineering comparison, not a market ranking. Sources were
reviewed on 2026-11-16. No proprietary code, design assets, or vendor authority are
being imported.

| Source | Relevant public design | Application to SZL | Evidence |
| --- | --- | --- | --- |
| Palantir Ontology | Objects, logic, actions, and security form an operational model. Action access remains contextual. | Connect domain objects to the existing action gate and evidence record; keep permissions at the actual write boundary. | [Ontology architecture](https://www.palantir.com/docs/foundry/architecture-center/ontology-system) |
| Palantir OSDK | Typed application interfaces expose data and actions, including validation and cache behavior. | Generate or validate client contracts against the real backend. Use runtime schemas for network responses, not optimistic assumptions about `ok`. | [Official TypeScript source](https://github.com/palantir/osdk-ts), [React/API guides](https://palantir.github.io/osdk-ts/) |
| Palantir Agent Stack | Sessions, typed context, events, and state transitions connect work across participants and interfaces. | Carry a stable decision identity through the UI, policy, execution, and evidence views. Preserve the reason a session is blocked or waiting. | [Agent Stack](https://www.palantir.com/docs/foundry/aip/agent-stack) |
| Temporal | Durable workflow execution depends on deterministic replay; external effects need deliberate retry and idempotency semantics. | Persist intent and observed outcome separately. A browser timeout must not automatically repeat a consequential request. | [Workflow definitions and determinism](https://docs.temporal.io/workflow-definition), [Temporal architecture source](https://github.com/temporalio/documentation) |
| Cedar | Verification-guided development combines an executable formal model, production implementation, differential testing, and property-based tests. | Compare concrete policy decisions and boundary behavior with an explicit reference model. Keep proof assumptions and runtime observations separate. | [Research paper](https://arxiv.org/abs/2407.01688), [Cedar authorization paper](https://arxiv.org/abs/2403.04651) |
| MLflow | Tracing, evaluation, feedback, prompt versions, and governance support a continuous evaluation process. | Turn sanitized operational failures into versioned regression cases before promoting a model or workflow. | [Official evaluation guidance](https://mlflow.org/blog/structured-ai-eval) |
| Sierra tau-bench | Evaluation compares resulting system state with the intended state and measures consistency across repeated trials. | Test that admitted actions produce the expected state and evidence, including refusals and partial outcomes. Report repeatability, not only one successful demonstration. | [Paper](https://arxiv.org/abs/2406.12045), [Author repository](https://github.com/sierra-research/tau-bench) |

### Video research boundary

The official [Palantir Ontology Overview](https://www.youtube.com/watch?v=YDAxITCNcko)
was identified and its public player metadata confirmed the title and Palantir
channel. The public caption request returned no caption content in this
environment. No claim is made to have reviewed the complete talk or transcript.
The implementation decisions above are supported by the accessible primary
documentation, source repositories, and papers. Video discovery is a reading
lead, not additional implementation evidence.

## 4. Apply the research to the existing client

The accompanying client repair has a deliberately bounded contract:

- Collect the already-supported operator token and tenant for a single request.
  Keep credentials out of URLs, browser persistence, logs, and rendered results.
  Clear the password field when the request starts and when the view is removed.
- Validate required inputs before sending. Refuse missing model or evaluation
  identifiers when the chosen task requires them. The backend retains authority
  over model qualification and separate approvals.
- Allow one in-flight request. Do not automatically repeat a POST after a timeout,
  lost response, redirect, or malformed response. An aborted browser request does
  not prove that backend execution stopped.
- Inspect HTTP status, media type, response shape, and completion evidence.
  A fallback HTML page with status 200 is not a valid API response.
- Present refusal, incomplete execution, uncertain outcome, and
  `UPSTREAM_REPORTED_UNVERIFIED` distinctly. Do not turn a top-level `ok` flag,
  a model name, or a receipt identifier into verified completion.
- Keep request retry settings and provider behavior distinct. A client request
  with zero retries does not prove that an upstream provider never retried or
  incurred additional cost.
- Reject stale results after unmount or a newer request. Do not retain a success
  state from a previous tenant, model, or task.

The regression suite exercises the actual served JavaScript request path with
controlled responses. It must cover missing identity, tenant refusal, unavailable
model/suite, malformed content, partial completion, unverified completion,
duplicate clicks, timeout uncertainty, and teardown. Backend authorization and
completion regressions provide the other side of the contract.

This is an operational correctness repair. It is not a new inference engine,
new signer, production credential provisioning, or independent execution approval.

## 5. Close the canonical frontend/runtime boundary

The canonical React artifact needs a real integration program. Acceptance
requires each of the following; a stub that returns an empty successful response
does not satisfy any of them.

1. **Inventory the exact pinned client.** Enumerate every GraphQL operation,
   subscription, REST action, expected response, authentication path, and error
   branch from the pinned platform revision. Historical mirrors are excluded.
2. **Choose an explicit runtime owner.** For each operation, name the existing
   Python service or an intentionally admitted service that owns its semantics.
   Keep a single authority for state, policy, and execution.
3. **Define typed boundaries.** Specify nullability, units, freshness, tenant
   scope, pagination, authorization errors, and completion states. Generate the
   client or validate it against these contracts in CI.
4. **Bind identity at every transport.** HTTP and WebSocket handshakes need
   equivalent tenant and operator controls. Credentials must not become URL
   parameters. Define revocation, expiry, and reconnect behavior.
5. **Define subscription behavior.** Bind events to the same tenant and decision
   identity, handle gaps and backpressure, and establish how a client obtains
   authoritative current state after reconnecting.
6. **Run a real journey locally and in an admitted environment.** Start with one
   bounded Atelier journey from input through policy, execution, observation,
   and evidence. Verify both allowed and denied paths. Then expand coverage.
7. **Publish through the existing owner.** Bind the static manifest and the
   backend contract version to the source and runtime readback. Admit deployment
   only when the exact artifact passes its runtime contract.

A completed frontend build, route table, or screenshot is supporting evidence.
The acceptance target is a working, correctly authorized user journey.

### Exact canonical contract inventory

The additional read-only review used platform revision
`f2f8df6f89056e9104587674ccec0855dd5b177a`, the gitlink pinned by the inspected
A11oy source. The canonical application is `artifacts/a11oy`.

| Transport | Declared operations at that revision |
| --- | --- |
| GraphQL queries (10) | `alloyDashboard`, `alloySignals`, `alloySignal`, `alloyWorkflows`, `alloyWorkflow`, `alloyWorkflowRuns`, `alloyApprovals`, `alloyActions`, `alloyArtifacts`, `alloyAuditLog` |
| GraphQL mutations (8) | `createAlloyWorkflow`, `submitAlloyWorkflow`, `cancelAlloyWorkflow`, `retryAlloyWorkflow`, `requestAlloyApproval`, `reviewAlloyApproval`, `runAlloyWorkflow`, `recordAlloyAction` |
| GraphQL subscriptions (3) | `alloyWorkflowRunUpdated`, `alloyApprovalRequired`, `alloyWorkflowStatusChanged` |
| Atelier HTTP | Health plus `POST /api/a11oy/v1/atelier/ask`, carrying prompt, provider, reasoning effort, session and idempotency identifiers, with explicit capability settings |

At this pinned revision, the referenced canonical GraphQL schema/resolver module
is absent. The client uses same-origin cookies for HTTP and empty WebSocket
connection parameters. A working transport cannot be presumed to provide a
working principal or tenant binding.

The mutation fields `reviewerUserId` and `overrideApproval` are caller input.
They must never become proof of an approver's identity or permission.
Existing Python principal, workspace, outbox, governance and receipt modules
can supply building blocks, but their lifecycles are not interchangeable with
the canonical workflow and approval objects.

The Atelier contract also carries provider, session, idempotency, disclosure,
persistence and receipt semantics. Mapping its prompt to the existing Python
operator question endpoint would discard those semantics. The integration must
bind an authenticated user to a tenant server-side; a caller-selected tenant
header plus a shared service key does not establish that relationship.

The pinned `NowBoard.tsx` and `CommandSurface.tsx` also contain fallback
demonstration data and fixed metrics that can be presented alongside apparent
live status. A successful empty response must remain empty. Loading, error,
empty, observed data, and explicitly requested demonstration data require
separate rendering states before canonical promotion.

## 6. Math and doctrine integration

The locked set remains exactly
`{F1, F4, F7, F11, F12, F18, F19, F22}`.
Formula meanings and executable bindings come from the declared formula
authority and Lean kernel, not from this document or a UI label.

For any formula applied to an operational decision, retain:

- Formula identifier and authoritative version.
- Inputs, units, admissible domain, and assumptions.
- The exact computation or proof artifact used.
- The limits of what the result establishes.
- The observation that connects the calculation to the actual system.

The living command strategy's organ map is a presentation and integration map.
It must not silently redefine formulas. Lambda uniqueness remains Conjecture 1
and cannot independently authorize actions; Khipu BFT safety remains Conjecture 2.
A numerical quorum calculation is not a distributed-system safety proof.

Energy is MEASURED only when an actual fresh exporter delta supports it.
Otherwise retain SAMPLE or DEGRADED. Carbon remains ROADMAP. These labels belong
to the evidence record and should be rendered consistently across every client.

## 7. Three designs to explore

These are **MODELED proposals**, informed by the prior art above and the existing
SZL architecture. These proposals require implementation and evaluation before
any claim about novelty or benefit.

### A. Rehearse a decision against a frozen world state

Let an operator compare candidate plans using a fixed, authorized input snapshot,
policy version, formula versions, and explicit constraints. A rehearsal produces
predicted outcomes and assumptions; it cannot invoke production writes.

The operator can see which input change would reverse a recommendation and which
constraint caused a refusal. For example, a logistics team could compare
alternative supply allocations before requesting an actual change. Predictions,
synthetic data, and observed outcomes remain visibly distinct.

An approved execution must recheck freshness, authority, and resource limits
against current state. A rehearsal is never a reusable permission.

**Acceptance:** identical inputs reproduce the deterministic portion; changing
one relevant assumption produces a traceable difference; unauthorized data is
excluded; no production mutation occurs during rehearsal; execution requires
current admission.

### B. Compute the smallest missing evidence needed for a claim

Represent a readiness claim as dependencies on specific observations, identities,
contracts, and trust checks. Calculate the missing or failed dependencies and
show the smallest actionable repair set, with ownership and evidence needed.

This would turn a broad NOT_READY status into a precise work queue. For example,
a healthy route and deployed source may still require a qualified model,
an independently approved plan, and a verified outcome. None should be inferred
from another.

Begin with deterministic dependency analysis. Do not add a confidence number
that hides an unknown trust boundary. Cycle detection, contradictory evidence,
and expired observations must be explicit.

**Acceptance:** removing a required observation withdraws the dependent claim;
unrelated failures do not block independent claims; every proposed repair links
to an actual failed dependency; no missing fact is treated as false or true by
default.

### C. Learn from the difference between predicted and observed outcomes

Connect the rehearsal, admitted action, observed outcome, and operator feedback
using one decision identity. Create sanitized regression cases from deviations.
Compare candidate models and workflows on these cases before promotion.

Useful objectives include task completion, policy adherence, repeated-run
consistency, latency, and resource use where it is genuinely measured. The
objective weights and prohibited tradeoffs must be declared by the domain owner.

This is a proposed evaluation loop. It does not authorize automatic retraining,
external export of private data, production experiments, or model promotion.

**Acceptance:** the evaluation set is versioned and inspectable; contaminated or
private examples are handled under existing data policy; failures remain visible;
improvements generalize to held-out cases; model qualification and deployment
remain separate decisions.

## 8. Delivery order and proof required

| Order | Work | Evidence required before claiming completion |
| --- | --- | --- |
| 1 | Repair served client contracts | Actual JavaScript and backend boundary tests; reviewed source; normal protected merge; exact published bytes/readback. |
| 2 | Close operational provider failures | Correlated provider traces and a bounded real delivery result; no timeout inflation presented as a repair. |
| 3 | Admit one independent execution | Existing approval custodian, exact current context, real qualified model/suite, declared limits, valid authority, fenced state, and retained verified outcome. |
| 4 | Bind the canonical frontend | Exact pinned operation inventory, implemented semantics, equivalent transport authorization, denied-path tests, and a complete admitted user journey. |
| 5 | Build decision rehearsal | Deterministic fixtures, side-effect isolation, assumption visibility, and current admission before any real action. |
| 6 | Add evidence dependency diagnosis | Correctness tests for missing, stale, contradictory, and cyclic evidence; actionable owners and repair conditions. |
| 7 | Introduce outcome-driven improvement | Versioned evaluations, held-out cases, repeatability evidence, resource measurements where available, and controlled promotion. |

Repository tests prove the behavior they exercise. Publication proves that an
artifact was delivered. Operational qualification requires the corresponding
live evidence. The engineering program is complete only when those layers agree.
