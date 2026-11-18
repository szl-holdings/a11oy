<!-- SPDX-License-Identifier: Apache-2.0 -->
# Evidence-bound actions: concept inventory and operational architecture

Status: **SOURCE CANDIDATE + MODELED ROADMAP**, not a production-readiness receipt.

This document separates the implemented Atelier request-binding changes from proposed architecture. It changes no locked formula, theorem, credential, data right, deployment authority, or provider configuration. It creates no new scheduler, graph database, publisher, or control-plane writer.

## 1. Design basis and research scope

Palantir's Ontology architecture organizes operational decisions around data, logic, actions, and security. Its OSDK React documentation treats validation, pending execution, optimistic state, confirmed data, and errors as different concepts. Its API explicitly cautions that HTTP 200 alone does not establish successful action application. Those are useful engineering patterns; installing an OSDK package does not make a non-Foundry backend compatible with it. [1–4]

The 2023 experience report *Concept-centric Software Development* describes a shared concept inventory connected to implementations and ownership. Its particularly relevant distinction is between a ratified design and functionality that has actually been built and released. This is an experience report, not evidence that SZL is faster, safer, equivalent to Palantir, or unique in the market. [5]

Official developer-video descriptions and chapter metadata were located for the OSDK walkthrough and Architecture Speedrun. No full transcript was available through this reading path. Technical conclusions below come from the primary documentation, published SDK examples, and paper—not a claim to have watched or transcribed the full videos. [6–7]

## 2. Use the real serving boundary

The maintained Python command centre is `routers/command_centre.py` and its Python view plus retained browser client. It talks to the existing authenticated Atelier routes in `routers/atelier_grok.py`. Public navigation, artifact inventory, and readiness GETs remain observations, not execution permission.

The separate React application from the admitted `vendor/platform` gitlink expects its own GraphQL, subscription, and Atelier contracts. `docs/architecture.md` identifies those contracts as unavailable in the Python runtime. Restoring a retired frontend mirror, inserting a mock API, or displaying a compatibility shell would not close that gap. The source-owned platform integration must prove those contracts separately before substituting its frontend into this runtime.

Existing authority remains GitHub source admission, then provider artifact publication, then product runtime readback, then independent proof/evaluation disclosure. A matching environment SHA is a declaration, not verification of all served bytes.

## 3. The shared concept inventory

| Concept | Identity and owner | Required relationship | Must not imply |
|---|---|---|---|
| Asset | Typed repository/Space/dataset/kernel identity and immutable revision | Canonical admitted source and declared role | Trained weights from code-only inventory |
| Observation | Source, measurement method, observation window, expiry, scope | The exact asset/revision actually observed | Absence or zero when retrieval fails |
| Intent | Fresh browser correlation ID and exact submitted fields | One immutable request snapshot | Permission, idempotency, or semantic progress |
| Disclosure consent | Exact prompt snapshot, destination, data class | The text being disclosed, not an earlier draft | Authorization to disclose any later edit |
| Decision | Existing authenticated principal, policy result and decision receipt | The intended action and source inputs | Successful provider execution |
| Outcome | Server request ID, client correlation ID, request/answer hashes, receipt and envelope | Its preceding decision and precise operation | Answer correctness or independent remote attestation |
| Release | Exact source/tree, native checks, required review and canonical publication receipt | The specific runtime and artifact revision | Qualification of unrelated capabilities |

One read projection may expose these concepts across Anatomy, Hatun, the command centre, and proof views. Its backing records must remain with their current owners. A new UI must not silently become a second source of truth or an alternate writer.

## 4. Implemented vertical slice

The candidate's flow is:

```text
exact browser draft and explicit consent
    -> unique client_request_id + immutable request snapshot
    -> existing server authentication and doctrine checks
    -> signed/persisted DECISION metadata
    -> existing bounded provider call
    -> signed/persisted OUTCOME metadata
    -> browser checks content, provider, model, source and request bindings
    -> answer display with an explicit verification boundary
```

`client_request_id` is an optional lowercase UUID v4 for API compatibility. The command centre always sends a fresh value. The server retains it inside both signed phases, never in the provider's inference request. Existing API clients that omit it keep their previous behavior. Reusing an ID does not deduplicate or authorize a request: no exactly-once guarantee has been added.

CPU-lab disclosure consent is held in page memory and bound to the exact prompt. Input/change events revoke it; submit-time equality also detects programmatic edits that omit an input event. The consent snapshot is cleared after submission and on pagehide. This is accidental-disclosure prevention, not protection against malicious code executing in the same origin and not a replacement for server data-classification policy.

Before displaying a successful answer, the browser checks the completed outcome's correlation ID, server request ID, prompt and answer SHA-256 values, expected provider/model/source, outcome phase, decision reference, server persistence/signature-verification flags, and equality of the envelope payload with the returned receipt payload. CPU-lab upstream output remains explicitly UNSIGNED. An unbound answer is withheld and the outcome remains uncertain; it is not automatically retried.

These are binding and consistency checks. The browser does not establish signer trust, cryptographically verify the DSSE signature, re-prove ledger durability, or establish model quality. Receipt canonicalization and signer admission remain owned by the existing backend/independent verification path. Source badges say they are declared by the process rather than independently observed. Redirects are refused and JSON response bodies are bounded to 1 MiB.

## 5. Mathematical and doctrinal integration

The eight locked formulas F1, F4, F7, F11, F12, F18, F19, and F22 are unchanged. Lambda uniqueness remains Conjecture 1 and the Khipu BFT performance claim remains Conjecture 2. No new Lean theorem or performance result is asserted here.

The core engineering rule is non-compensation: good measurements cannot cancel a denied policy, missing rights, an expired observation, or an unverified source. Eligibility should remain a conjunction of the relevant admitted gates, not a weighted average that paints a partially blocked system green.

Request identity and semantic identity are different. A fresh correlation ID or delivery timestamp must not count as new semantic progress in ORO. The correlation ID belongs to transport/action history; ORO's content-cycle projection and rank controls keep their independent meaning. Any future adapter into ORO must test that adding a fresh request ID to otherwise unchanged content cannot bypass a cycle refusal.

Similarly, a valid software theorem does not establish that a physical GPU ran a workload, that a model improved, or that a customer action succeeded. Each transition needs evidence at its own boundary. A signature attests to the signed statement and signer, not to every assumption behind it.

## 6. State management and concurrency

The UI must distinguish an editable draft, acknowledged draft, pending request, server-observed outcome, independently verified outcome, and uncertain outcome. Editing a draft cannot retrospectively change the identity of a pending request. A response belongs to the submitted snapshot, even if the user has since edited the form.

Palantir's normalized cache and action-driven invalidation illustrate how multiple views can share object identity without maintaining incompatible copies. Its optimistic state is explicitly separate from confirmed data. For SZL, optimistic rendering may improve interaction latency, but must never promote evidence, release approval, remote execution, or payment settlement. [2,8]

Palantir also documents limits: action atomicity does not include arbitrary external side effects, and snapshot isolation can allow write skew when an invariant concerns reads of multiple objects. Copying a transactional label is not sufficient. SZL's admission/resource ownership predicates must be rechecked by the authoritative writer against the correct generation; a read-only visualization or successful preflight cannot grant a future write. [9]

## 7. Proposed frontier: a counterfactual evidence workbench

The following capabilities are **MODELED/ROADMAP**, not installed services and not claims of novelty over all prior work.

### A. Evidence acquisition planner

For a user-selected action, show the smallest safe set of missing observations that could establish its prerequisites. The plan is constrained by rights, quota, cost, scope and observation freshness. A policy denial is not something an observation plan may override. Cost is an optimization criterion only among already permitted plans, never a substitute for safety gates.

The first bounded experiment should use a synthetic prerequisite DAG and a finite candidate set. Compare the planner with a full-scan baseline on correct gate classification, unnecessary reads, quota consumption, and refusal under missing data. Return UNKNOWN when the search bound is exceeded. Do not claim an optimum when using a heuristic.

### B. Counterfactual safety map

Let the operator ask: “Which claims and available actions would change if this model revision, right, signer, sensor observation, or runtime lease stopped being valid?” Recompute derived eligibility in an isolated read model. Preserve the original receipts as historical evidence; do not erase them or execute remediation.

An initial civil application is municipal water-maintenance planning: distinguish a reported repair, a technician's signed completion statement, and a subsequent pressure/quality measurement. The system should identify missing corroboration and propose human review, not autonomously close an incident because a form was submitted.

### C. Reciprocal outcome evidence

Where the environment supports it, pair an authorized action receipt with independently observed effect evidence. Examples include a dispatched maintenance request versus a sensor-confirmed recovery, or an approved energy schedule versus separately metered consumption. Agreement must bind the same asset, operation, generation and time window. Disagreement stays visible.

This is intentionally stronger than “the agent said it completed.” It is not universal: some outcomes cannot be safely or cheaply observed. Those remain explicitly uncertain instead of receiving synthetic receipts.

### D. Contract-generated interfaces

Generate form fields, preflight explanations and regression fixtures from admitted action contracts. Keep server-side policy authoritative and preserve explicit uncertainty. Start with one maintained action family, not every repository at once. Reject stale client/server versions before effects and require schema-change reviews.

The candidate in section 4 is the first narrow action family, implemented directly against current contracts; a generator has not been built. Extending it to Hatun and Anatomy requires their source owners and typed interfaces, not an assumed shared API.

## 8. Acceptance ladder

1. Static/source review: no hidden external call, secret handling, new writer, or changed mathematical claim.
2. Negative regression: unchanged source reproduces the defect; tests distinguish schema additions from existing production bugs.
3. Backend contract: ephemeral keys, temporary ledgers, fake provider transport, real authentication/policy/signing code.
4. Browser contract: installed browser, actual local routes, exact served source, phone/tablet/desktop, keyboard focus, reduced motion, no overflow, one permitted fixture submission and no external traffic.
5. Native exact-head CI and source review: including the unchanged Linux symlink control and any required independent approval.
6. Sole canonical publisher adoption: immutable source/artifact bindings and rollback evidence.
7. Authorized live qualification: actual safe journeys, durable receipts, independently verified source/outcome where available, and separate model-quality evidence.

A pass at one level never implies that the subsequent levels ran. A regression suite with fake providers is not a benchmark of model ability or a production inference receipt.

## References

[1] Palantir, The Ontology system: https://www.palantir.com/docs/foundry/architecture-center/ontology-system

[2] Palantir OSDK TypeScript, Actions: https://palantir.github.io/osdk-ts/react/actions/

[3] Palantir, Apply Action API: https://www.palantir.com/docs/foundry/api/v2/ontologies-v2-resources/actions/apply-action

[4] Palantir, AIP architecture: https://www.palantir.com/docs/foundry/architecture-center/aip-architecture

[5] Wilczynski, Gregoire-Wright and Jackson, Concept-centric Software Development, Onward! 2023, DOI 10.1145/3622758.3622894: https://arxiv.org/abs/2304.14975

[6] Palantir Developers, Building with Palantir AIP: the Ontology Software Development Kit (video metadata/chapters only): https://www.youtube.com/watch?v=vSJ5H00V7Es

[7] Palantir, Architecture Speedrun: From Integration to Application (video description only): https://www.youtube.com/watch?v=k88WbxMEvPY

[8] Palantir OSDK TypeScript, Cache Management: https://palantir.github.io/osdk-ts/react/cache-management/

[9] Palantir, Consistency and isolation: https://www.palantir.com/docs/foundry/action-types/consistency-guarantees

[10] Palantir, AIP Evals: https://www.palantir.com/docs/foundry/aip-evals/overview
