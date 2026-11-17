<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# From research to an evidence-grounded operating interface

Research date: 2026-11-16. Source review base: `2204f596d17a854fba12cd204ab86019bc2e0712`.
Scope: primary-source architecture review and the legacy seven-page Anatomy 3D read/action boundary.
Status: engineering design and source repair; this document does not attest deployment, production readiness, novelty, or mathematical proof.

## Decision

Make each operational claim inspectable: what was observed, when, under which namespace and source, with what verification, and whether any effect was authorized. The frontend should render this contract and its refusal reasons. It should never create work merely to animate an apparently live interface.

The concrete repair starts in `szl_anatomy_3d.py`, which is already registered by `serve.py` and copied by the Dockerfile. This is a complete vertical boundary through registered API routes, shared authorization, all seven pages, and offline browser verification. It adds no new service or production persistence layer.

At the reviewed base, an isolated execution with fake dependencies found five append attempts and four signing attempts from a single body GET. A lambda GET attempted two of each. Missing dependencies still produced favorable live/chain flags; page-load polling also issued POSTs. These are observations about this source revision and harness, not claims about requests made against production. The repair removes those paths and tests their absence.

## What the primary sources teach

| System or research | Established behavior and limit | Decision for this estate |
| --- | --- | --- |
| Palantir Ontology and OSDK | Typed objects, links, and actions give clients a common domain contract. OSDK action validation and action application are separate operations. A validation result must be interpreted in its permission and state context. [OSDK](https://www.palantir.com/docs/foundry/ontology-sdk/overview), [React action source](https://github.com/palantir/osdk-ts/blob/main/docs/react/actions.md) | Bind views to backend contracts. Keep reads, validation, and effects distinct. A graph edge or enabled button does not establish execution authority. |
| Palantir action transactions | Atomicity covers Ontology edits, not external calls or webhooks. Retry policy must account for repeatable external effects. [Consistency guarantees](https://www.palantir.com/docs/foundry/action-types/consistency-guarantees) | Explicitly record an external effect's identity and acknowledgement. Do not claim a distributed operation is atomic merely because a local record is transactional. |
| Palantir action history | The action log covers successful action submissions; failure metrics and edits outside that path require separate coverage. [Action log](https://www.palantir.com/docs/foundry/action-types/action-log/index.html) | Preserve attempted, refused, failed, ambiguous, and completed outcomes. A history containing successes alone cannot establish system reliability. |
| LangGraph fault tolerance | Nodes can run more than once. External effects are outside checkpoints. An idempotency identity must be durable before dispatch, and a missing acknowledgement can leave the outcome unknown. [Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) | Future workflow integration must reuse the existing durable state authority, bind a stable operation identity before dispatch, and reconcile uncertain outcomes before retry. A refreshed page must never replay an operation. |
| NVIDIA NIM | Liveness can mean only that the container is running; readiness means the model is loaded and available for inference. [API reference](https://docs.nvidia.com/nim/large-language-models/2.1.5/reference/api-reference.html) | Represent service health, loaded-model readiness, observed inference, and measured energy separately. None can substitute for another. |
| NVIDIA agent tooling | The current NeMo Agent Toolkit repository says it was deprecated in October 2026, with end of life at the end of 2026; it directs users toward Relay, Helix, and Fabric by need. [Official repository](https://github.com/NVIDIA/NeMo-Agent-Toolkit/blob/develop/README.md) | Learn from instrumentation and evaluation patterns without adding a new deprecated runtime dependency. Any later migration needs a separately scoped compatibility decision. |
| OpenTelemetry GenAI | The dedicated GenAI semantic conventions currently have Development status and distinguish inference, tool, retrieval, and agent signals. [Convention source](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/README.md) | Version any adapter. Trace metadata is observation, not independent signature proof, policy authorization, or proof of a theorem. |
| tau-bench | The original paper evaluates outcomes and repeated-trial reliability with pass^k. It also notes that a correct final state can miss a policy violation such as absent confirmation. [Paper](https://arxiv.org/html/2406.12045v1), [reference code](https://github.com/sierra-research/tau-bench) | Evaluate both effects and the path that authorized them. A useful regression matrix contains repeated attempts, refusals, wrong namespace, stale context, and crashes, alongside final-state checks. |

Two earlier papers supply useful foundations for the longer-term design. [ReAct](https://arxiv.org/abs/2210.03629) interleaves reasoning, actions, and environmental observations; the architecture lesson is to retain explicit tool outcomes and failure observations, without interpreting a model's explanation as proof. [Reflexion](https://arxiv.org/abs/2303.11366) uses textual feedback and episodic memory across trials rather than updating model weights. Its [reference implementation](https://github.com/noahshinn/reflexion) grounds the distinction between learning from feedback and changing a trained model. The estate-specific proposal below is to turn reviewed failures into executable regressions, with independent release gates. These sources do not establish that the proposed combination is unique or production-safe.

The video review was limited to official indexed descriptions and chapter metadata. Full transcripts were not available; no claim here depends on unseen video content. The relevant listings are Palantir Developers' [Ontology Foundations, DevCon 5](https://www.youtube.com/watch?v=dz20P3j3GMc) and NVIDIA Developer's [Agent Toolkit Profiler](https://www.youtube.com/watch?v=yrqdvBLAI3k). The latter is historical context; current deprecation guidance takes precedence over its installation-era assumptions.

## Fit to the existing math and doctrine

The locked formula set remains `F1, F4, F7, F11, F12, F18, F19, F22`. Lambda remains Conjecture 1; Khipu BFT remains Conjecture 2. A renderer, passing Python test, valid hash link, or working signature does not change those statuses.

The existing admission contract uses the weighted geometric mean and the minimum component constraint:

```text
G = exp(sum(w_i * log(x_i)) / sum(w_i))
admit iff G >= 0.80 and min(x_i) > 0
```

Its hidden-weak example distinguishes arithmetic mean from geometric mean. That admission contract is separate from a displayed Yuyay minimum over sample votes. Neither a favorable sample value nor an HTTP 200 can grant production admission. See the repository's [admission rule](../../.claude/rules/admit-contract.md).

The existing source chain remains GitHub → governed Hugging Face publication → a-11-oy.com → a11oy.net. Read repair does not create another deployment authority. Persistent records belong in the existing state-store architecture; an in-process display cache must be clearly bounded, disposable, and nonauthoritative.

## The repaired observation boundary

The accompanying [observation contract](../architecture/ANATOMY_OBSERVATION_CONTRACT.md) defines route behavior and field meaning. Its core constraints are:

- Public GETs and page generation do not call evaluators, signers, key resolvers, DAG constructors, or append operations.
- Existing effect-bearing POSTs require the operator gate before body parsing, with middleware and handler coverage.
- A last authorized sample can be displayed only within its namespace and bounded age. Reading it does not renew it.
- Missing, expired, malformed, or failed reads clear favorable presentation. Fixed geometry and historical theorem snapshots remain labeled modeled or historical.
- Hash-link integrity, cryptographic signature verification, actual execution, and operational admission remain separate claims.
- Browser tests run the real vendored Three.js revision 128 with mocked APIs and blocked external traffic. They exercise success-to-failure transitions and resource cleanup, not only the first screenshot.
- API responses never insert active markup into evidence cards. A fixed DOI link is constructed only from the intended destination.
- The test workflow uses the repository's existing hash-locked dependencies and pinned actions. The browser runtime is required.

This repair is intentionally limited to the legacy seven-page surface. It is not an attestation that every estate endpoint shares the new envelope, nor that sampled routing has become verified inference.

## Product direction: an evidence planner

This is a design hypothesis, not a deployed feature or a novelty claim.

An operator should be able to select a desired claim, such as “this model can serve this approved workload on this host within this measured energy budget,” and see the exact unsatisfied evidence dependencies. The planner would use typed facts already present in the estate: source revision, runtime identity, approval scope, model artifact, workload, receipt, and measurement.

For a claim C, let M(C) be its missing required witnesses. A candidate experiment e has a bounded cost, explicit authorization requirements, and an expected set of observations. The planner can rank experiments by expected information gained per resource cost, but it cannot replace hard admission predicates with that score. The output is a reviewable plan; only the existing authorization path can dispatch it.

Three evaluation questions make this concrete:

1. Does the planner identify all missing required witnesses on a held-out set of refusal cases without inventing a witness?
2. Does a bounded sequence of approved experiments reduce unnecessary probes compared with a fixed checklist?
3. Under unavailable hardware, stale approval, contradictory receipts, or timeout, does it retain the correct refusal or unknown state?

The first implementation should be an offline replay over sanitized existing evidence. It should not allocate GPUs, alter production configuration, or run model training. Any later durable state belongs in the existing state store, with an operation identity persisted before effect dispatch.

## Product direction: reusable failure evidence

Turn a real incident into a sanitized, source-bound regression fixture: the request context, relevant state, expected refusal or effect, and the allowed observation surface. A candidate patch must pass that fixture and relevant earlier failures before human-reviewed release.

This gives the estate a cumulative engineering advantage that can be measured: fewer repeated incident classes, stable refusal behavior, reduced recovery time, and no increase in unauthorized effects. The design should preserve confidential data boundaries and record how the fixture was derived. It does not imply autonomous production self-modification or automatic training on user data.

## Product direction: measured quality and energy tradeoffs

Use a fixed workload and pinned model/source/runtime identities to compare task quality, latency, reliability, and measured energy. Keep modeled cost estimates separate from meter-derived measurements. Prefer an explicit set of admissible tradeoffs to a single attractive score that hides a failing requirement.

Before comparing options, establish meter scope, sampling interval, calibration assumptions, and whether idle consumption is included. Report missing measurements as unavailable. A low forecast, a zero initialized counter, or an online GPU does not establish a measured energy result.

## Release evidence and remaining boundaries

The source repair requires route tests, browser tests, and independent diff review. Production claims additionally require human-reviewed merge, the existing governed publication path, and a readback tied to the deployed source and runtime. Passing offline fixtures establishes those tested contracts only.

| Claim | Required witness |
| --- | --- |
| Public inspection has no write effect | Registered-route dependency traps plus all seven pages' captured request methods |
| Failure does not leave a favorable interface | Browser success-to-error transitions for HTTP, transport, JSON, and payload-shape failures |
| Operator boundary is effective | Unauthenticated malformed-body refusal before parsing, shared middleware patterns, and standalone handler checks |
| A chain segment is internally consistent | Bounded, explicitly scoped hash-link verification; never a substitute for DSSE verification |
| A runtime matches reviewed code | Native deployment/readback evidence for the exact revision and boot |
| An approved workload actually ran | Authorized dispatch, acknowledged result, bound receipt, and required independent verification |
| An energy comparison is measured | Workload-bound meter evidence and declared measurement scope |

The next implementation sequence should follow this dependency order: complete and review this observation boundary; integrate a common typed contract into existing active command/action lanes; replay incidents against those contracts; then evaluate the evidence planner offline. Each step has a separate claim and acceptance criterion. None requires changing the locked formulas or relabeling a conjecture.
