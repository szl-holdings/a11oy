<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Frontier capability readiness contract

## Purpose and current boundary

The Frontier manifest exposes the backend's existing per-capability readiness decision so the operator interface can explain the same decision used by the summary. The change adds a projection in [szl_frontier_manifest.py](../szl_frontier_manifest.py), consumed by [a11oy_frontier_page.py](../a11oy_frontier_page.py), and isolates malformed producer values. Existing predicate and summary meanings remain unchanged for valid source data.

The existing `GET /api/a11oy/v1/frontier/manifest` remains the API. Composition calls `_tile_operational_readiness(tile)` once per tile, then uses that result both for the capability projection and the existing summary. The projection copies the producer's tile envelope before adding its field. Existing `operational_evidence`, `provenance`, labels, and summary meanings remain intact.

Unsatisfied evidence with blank or non-string reason entries retains an explicit `invalid_operational_evidence_reason` blocker, so the backend cannot emit a reason list that its browser consumer rejects. Valid reason strings remain intact and duplicate codes are removed by the existing evaluator.

The accompanying source-envelope check requires a dictionary that serializes to JSON without nonfinite numbers. A rejected producer uses the existing unavailable-tile fallback, preserving sibling tiles. Four existing count fields (`nodes_reachable`, `reachable_nodes`, `chain_length`, and `length`) now report `invalid_count_<field>` for malformed counts. Booleans and fractional counts are rejected rather than accepted through numeric coercion; conversion failures no longer abort the whole composition. Nonfinite values are rejected earlier by the source-envelope check. Null counts retain the existing empty-count behavior. This is bounded serialization and count validation; it is not universal validation of every producer schema.

This scope adds no endpoint, graph service, external dependency, network probe, signing operation, execution path, or deployment authority. It does not resolve a capability's reported blockers by displaying them. Test results and deployment evidence must accompany a release separately; this document is a contract and architecture note, not a release attestation.

## Versioned API contract

Each object in `capabilities` carries `operational_readiness` with the following fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | string literal | Exactly `szl.frontier.capability-readiness.v1`. |
| `state` | `READY` or `NOT_READY` | Presentation of the backend evaluator's result. |
| `ready` | boolean | The same boolean used for this tile in the summary. |
| `predicate` | nonblank string or null | The explicit bounded predicate from `operational_evidence.predicate`; null when absent or invalid. |
| `reasons` | array of strings | The evaluator's deduplicated reason codes. |
| `source_reachable` | boolean | The existing producer availability convention, `bool(tile.get("ok", True))`; this field performs no independent transport check. |

The backend returns `READY` when the existing evaluator produces no reasons. The evaluator requires explicit evidence, a nonblank predicate, `satisfied is True`, and the existing capability-specific conditions. An honesty label or absence of an error alone does not establish readiness.

**SAMPLE payload:** this illustrates a reachable source with a blocked capability; it is not a live observation.

```json
{
  "operational_readiness": {
    "schema": "szl.frontier.capability-readiness.v1",
    "state": "NOT_READY",
    "ready": false,
    "predicate": "runtime signer health observed + at least one receipt signature cryptographically verified this process",
    "reasons": [
      "signer_not_ready"
    ],
    "source_reachable": true
  }
}
```

The projection is an explanation, not a new evidence record. Detailed observations remain in `operational_evidence` and other producer fields; `provenance` remains a set of source references. A missing predicate is represented as null, not guessed from a capability name, status string, or link.

The existing `summary.source_reachability` continues to describe producer availability. The existing `summary.operational_readiness` continues to describe the roll-up of evaluated tiles. `summary.all_sources_live` remains the deprecated alias for operational readiness, with its existing compatibility explanation. It must not be reinterpreted as transport availability.

## Runtime-verifiability boundary (by-design capabilities)

`summary.operational_readiness` additionally reports `not_runtime_verifiable`: a list of `{name, expectation}` rows for capabilities whose bounded predicate this surface cannot satisfy at runtime **by design**. As of #3654 these are the orbital compute tier (no on-orbit hardware exists or is planned; the tile stays MODELED per doctrine v11) and the signed UDS bundle tile (this feed observes source metadata only; attestation verification lives in the `uds-sign-release` workflow and is recorded out-of-band).

These tiles are neither in `ready_tiles` nor in `blocked_tiles`. `blocked_tiles` contains only tiles whose predicate a live runtime can actually satisfy, so `ready` can become true through real operational work alone. This is a reporting split, not an evidence change: per-tile `operational_readiness` states, honesty labels, `satisfied` flags, and reason codes are unchanged, and the by-design tiles remain fully visible in `capabilities` and in `not_runtime_verifiable` with the expectation text explaining why each is reported rather than gated.

The same change removes the unconditional `sovereign_ownership_not_verified` reason from the compute-fabric tile (#3654). A transport probe cannot verify GPU ownership, so ownership stays a documented field (`ownership_verified: false` with `sovereignty_scope`); the fabric tile's predicate is now the runtime-verifiable subset: a configured sovereign GPU transport-reachable, consistent probe counts, and a verified compute-pool/v1 inference receipt bound to that node. A reachable-but-unverified fabric still blocks; ownership is no longer a permanently unsatisfiable requirement inside a runtime gate.

Consumers that partition tiles must account for `not_runtime_verifiable`; the healthz liveness signal's consistency check does. A missing, malformed, or count-mismatched `not_runtime_verifiable` value fails closed: the rollup reports unavailable rather than ok.

## Energy readiness: the bounded-window scope

Before this change, two runtime-satisfiable tiles could never become ready, whatever ran on the live Space:

- The Energy operator predicate required `measured_jobs >= 1`. The operator increments that billable counter only for exclusively attributed job energy, and no NVML host window can establish exclusivity, so the counter is always zero.
- The Energy provenance chain predicate was hard-coded unsatisfied, and nothing appended to the chain in production.

Both tiles are rescoped to the runtime-verifiable subset, following the pattern of the compute-fabric change above. The part a runtime cannot verify stays visible as its own field and is never presented as met.

| Tile | Predicate now | Reported, never promoted |
| --- | --- | --- |
| Energy operator | `running=true` + a configured GPU node answered its latest sweep probe + a job this process was bracketed by a verified NVML counter window no older than `window_max_age_s` | `joules_measured_label`, `joules_measured_reason`: billable per-job energy, unavailable without exclusive attribution. `joules_measured_total` is shown only when that label is MEASURED |
| Energy provenance chain | non-empty chain + computed chain verification + at least one hash-bound MEASURED bounded-window entry | a numeric `joules_est` stays SAMPLE/ESTIMATE; an operator entry makes no estimate (`null`, UNAVAILABLE) |

A verified window means fresh before and after counter samples on the same GPU UUID and continuity epoch that bracket the job interval. The delta includes host work outside the job, so it is labelled MEASURED only within the `BOUNDED_METER_WINDOW` scope (`measurement_scope` on both tiles) and is never billed. The operator tile's label is MEASURED only while the latest window is younger than `A11OY_ENERGY_WINDOW_MAX_AGE_S` (default 900 s, clamped to 60 s .. 1 day): a meter that goes quiet turns the tile UNAVAILABLE with `measured_energy_window_stale`. A window count without a positive total fails closed (`invalid_window_joules_total`), as does a missing, malformed or contradictory billable label.

The provenance chain gains a v2 entry (`szl.energy-provenance.entry/v2`) that binds `schema`, `measurement_label`, `measurement_scope`, `window_joules_measured`, `source`, `source_seq` and `node` into its receipt hash, so promoting a SAMPLE entry after append breaks verification. A v1 entry keeps its historical encoding and never counts, and nothing counts as measured, on the tile or the public read, while any part of the chain fails verification. The operator's completed-job stream is the chain's only production writer: one entry per job the operator dispatched to one of its configured GPU nodes, under the public node name, with no GPU UUID, counter evidence, receipt id or private host. Stub jobs and external submissions (for example governed CPU code cells) are not recorded, `append_receipt()` writes SAMPLE entries only, and a read never appends. The process chain keeps at most `SZL_ENERGY_PROVENANCE_MAX_ENTRIES` entries (default 2000, at most 10000). Every evicted entry is checked the way `verify()` would check it, so tampering stays detected after eviction, and the retention anchor is the last evicted entry's receipt hash. The public read reuses its summary for at most 5 s while the chain is unchanged.

Both counts are process-local and restart at zero, like the other tiles' evidence. The operator also reports `lung_probe` per node (bounded reason codes under public names) and retries its lung-gated autostart every `A11OY_ENERGY_AUTOSTART_RETRY_S` seconds (default 300, `0` disables); an operator's explicit stop holds the retry off until the next explicit start or a process restart, and the hold is checked inside the start transition so a stop that races the retry still wins. The app's shutdown hook stops the retry thread, waiting at most 5 s in total (including for the operator lock, so a slow persist cannot hang shutdown). A retry still probing a lung when it is stopped finishes that probe but cannot start the loop on its own; until it returns, another start in the same process answers `start_in_progress` and is decided by that probe's result.

This change does not alter the governance or composite tiles. Each still needs a real operator-authorized governed write in the current process: a restraint evaluation (`POST /api/a11oy/v1/restraint/evaluate`) and a composite receipt (`POST /api/a11oy/v1/provenance/receipt`). A manifest read never performs either.

## Frontend responsibilities

The UI consumes the supplied decision. It validates the contract's representation rather than recalculating a capability's predicate.

- Require the exact supported schema, boolean `ready` and `source_reachable`, a supported `state`, a string-or-null predicate, and an array containing only string reasons.
- Require state/boolean consistency. A `READY` projection must have a nonblank predicate, no blocking reasons, and `source_reachable: true`.
- Treat an absent, malformed, unsupported, or inconsistent projection as unavailable readiness information. Do not infer `READY` from HTTP 200, `ok`, `MEASURED`, a status label, or an evidence URL.
- Keep producer availability, bounded readiness, honesty label, and evidence references visibly distinct. Reason codes and predicate text should remain inspectable.
- Render producer text as text. A reference may become a link only through the existing safe URL policy; the page must not execute producer-supplied markup or fetch references merely to render a card.
- Handle the existing manifest error envelope, including `ok: false` and absent capabilities, without displaying a healthy roll-up.

These are consumer checks for a well-formed assertion. They do not independently establish that its underlying evidence is true, fresh, complete, or authorized.

### Optional graphics and evidence bootstrap

Browser verification of the deployed `/frontier` observed a `WebGLRenderer` context-creation exception when WebGL was unavailable. The exception occurred before the evidence loaders started, suppressing the manifest, Brain, and surfaces data in that browser. This is a frontend initialization failure; it does not establish that the backend sources were unavailable.

The implementation contract requires dynamically loaded, guarded 3D initialization with evidence bootstrap independent of that optional graphics path. Regression cases must cover both a rejected graphics import and a throwing renderer constructor: manifest, Brain, and surfaces loaders must still start, and the non-3D interface must remain usable. This note records the observed failure and the required behavior; it does not claim that a fix has been deployed or that the regression tests have passed.

### Surface catalog response contract

The capability and surface loaders check the HTTP status before decoding a response, retaining an explicit payment-required explanation for HTTP 402. The capability loader also requires an explicit successful envelope, a capability array, and a matching summary count. The surface loader validates its catalog before rendering. A payment-required response, other non-success response, source error, or malformed envelope is an unavailable catalog with an unknown count. It cannot become a live empty catalog. Search and pagination remain disabled until a valid catalog has loaded; error rendering clears the roll-up and filter tabs instead of showing an `ALL 0` result.

A successful catalog must match the existing producer contract: `ok: true`, a surface array, safe nonnegative integer counts, complete summary fields, unique nonblank identifiers, supported labels, and boolean asset-presence observations. The summary count, label histogram, present count, and unavailable count must agree with the returned entries. A valid observed empty catalog remains distinct from an unavailable source. Valid `UNAVAILABLE` entries remain visible, including both missing assets and present assets without a recognized declaration. These are representation checks, not independent verification of source bytes, runtime capabilities, or execution authority. Existing edge authorization and payment policies remain in force.

## Anatomy transport and mesh observations

The existing [Anatomy data reader](../console/anatomy-map/live-body.js) and [page consumer](../console/anatomy-map/live-body.html) now keep endpoint transport reachability distinct from declared source state and operational readiness. The legacy `live` renderer/CSS token remains compatible, but visible labels explain its transport-only meaning. These probes do not acquire a readiness verdict or invent relationships to Frontier capabilities.

Mesh counters must be nonnegative safe integers with live engines no greater than total engines. Missing or invalid values remain null; a valid partial count is preserved without inventing the missing count. An observed empty mesh (`0/0`) has no health fraction. The page stores unknown intensity as null, renders no particles for that unknown value, and displays the unavailable explanation for failed probes as well as reachable responses. Zero rendered particles are a visual fallback, not a zero measurement or healthy verdict.

## Boundaries that must survive the wiring

| Observation | What it establishes | What still requires separate evidence |
| --- | --- | --- |
| A request returns HTTP 200 | The responding route produced a transport response. | Operational readiness, successful inference, storage durability, signer health, and action authority. |
| A producer tile has `ok: true` | The producer's existing availability condition holds. | The tile's explicit operational predicate and blockers. |
| A signer is ready | Its reported current signing-health condition holds. | A particular artifact was signed and its signature independently verified. |
| A receipt signature verifies | Verification succeeded within the reported artifact, method, and identity scope. | The signer remains available now, broader coverage, or unrelated runtime readiness. |
| `timestamp_utc` or `cached_at` advances | Composition or cache timing changed. | Each underlying observation's freshness, source binding, boot identity, or expiry. |
| A provenance URL or digest is present | There is a reference that a verifier or operator can inspect. | Referenced bytes were fetched, their content matches, authorship is authenticated, or a claim is proven. |
| A hash chain is intact | The stated integrity check succeeded. | Signature authorship, consensus safety, execution authority, or a Lean theorem. |
| A trace reports a call | The instrumented boundary observed that activity. | The observer controlled execution or prevented an unauthorized side effect. |

The existing governance tile separately checks signer observations and receipt-verification observations from the registered runtime. Its aggregate `signature_verified` value reflects that combined readiness condition; the component observations remain necessary to understand why the tile is blocked.

The existing manifest cache can serve an earlier composition. Its runtime governance recheck can invalidate that cache when the observed signing condition or identity changes. This projection adds no general freshness guarantee. Consumers must not substitute cache time for evidence time.

Manifest GETs read existing observations. They do not mint a receipt, produce a signature, repair a failed verifier, or grant permission. An action must still pass the existing server-side governance and authority checks at execution time. These boundaries follow [AGENTS.md](../AGENTS.md), the [provenance rule](../.claude/rules/provenance.md), and the [security rule](../.claude/rules/security.md).

## Existing structures to reuse

The [Canonical Evidence Graph v1](evidence-graph-v1.md) already models content-addressed observer facts, explicit identities, bounded snapshots, parent references, and authority flags. Its documentation explicitly separates a content address or observer verdict from signature authentication, freshness, proof, and execution authority. Bounded snapshots can have omitted parents. A future lineage view must preserve these distinctions.

[ORO](../oro/README.md) already defines bounded roles, obligation-ranked cyclic work, explicit predicate identities, and separate evidence and authority boundaries. Its read-only source-adapter seam accepts already-read snapshots, marks partial source coverage, and leaves projected nodes unverified with execution, promotion, and signing authority false. That seam does not run a graph, fetch sources, or feed the barrier engine.

Further work should extend these existing contracts where needed instead of creating a second evidence graph or a competing readiness engine. This change does not establish a CEG-to-Frontier or ORO-to-Frontier runtime integration merely by documenting the intended reuse.

No new mathematical proof, formula, or novelty claim is introduced. The locked formula count remains eight. Lambda uniqueness remains Conjecture 1; Khipu BFT safety remains Conjecture 2, as specified in [AGENTS.md](../AGENTS.md).

## Primary-source architecture findings

The following are adaptations to the SZL boundary, not claims of equivalent product coverage or independent validation.

| Primary source | Relevant pattern | Bounded SZL application |
| --- | --- | --- |
| [Palantir Workflow Lineage](https://www.palantir.com/docs/foundry/workflow-lineage/overview) | Explain dependencies among operational resources and inspect the relationships behind a workflow. | Surface the existing predicate, blockers, and source references together. A future graph must use declared CEG/ORO relationships and report missing coverage. |
| [Palantir action submission criteria](https://www.palantir.com/docs/foundry/action-types/submission-criteria) and [action permissions](https://www.palantir.com/docs/foundry/action-types/permissions) | Evaluate execution conditions and authorization separately from visibility or definition-edit permissions; expose failure reasons. | Keep readiness descriptive. Recheck authority and constraints in the existing execution path; a readable or ready card grants no permission. |
| [Palantir OSDK overview](https://www.palantir.com/docs/foundry/ontology-sdk/overview) and [official TypeScript repository](https://github.com/palantir/osdk-ts) | Generate typed application access from a central object/action model. | Maintain one versioned backend contract and a strict consumer. This patch does not add generated clients or import the OSDK. |
| [NVIDIA NeMo Relay overview](https://docs.nvidia.com/nemo/relay/latest/about-nemo-relay/overview) and [official repository](https://github.com/NVIDIA/NeMo-Relay) | Managed invocation can run middleware around the actual callback; before/after hooks can observe a lifecycle without controlling execution. | Record the boundary that actually observed or enforced a decision. A trace or lifecycle hook cannot stand in for a governance guard. No Relay dependency is added here. |
| [LangGraph fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) and [checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) | Retries can execute a node again; checkpoints do not make external side effects exactly once. Durable operation identity and idempotency must protect writes. | Future action orchestration must distinguish a refused action, a known failure, and an unknown outcome. Retrying a dashboard read must never repeat a governed write. |
| [Kambhampati et al., ICML 2024 position paper](https://proceedings.mlr.press/v235/kambhampati24a.html) | The LLM-Modulo proposal places candidate generation in a feedback loop with external model-based verification. | A model may propose an explanation or remediation. Existing deterministic predicates and authorized execution boundaries decide acceptance. The paper is a research position, not evidence that this runtime is verified. |
| [Yao et al., tau-bench (2024)](https://arxiv.org/html/2406.12045v1) and [metric implementation](https://github.com/sierra-research/tau-bench/blob/main/tau_bench/run.py) | Compare observed terminal state with an independently specified goal; evaluate consistency across repeated trials. The paper also notes that a matching final state can miss a policy violation in the trajectory. | Evaluate both the resulting state and required execution constraints. Preserve failures, errors, and unparseable results in the declared task inventory. A single complete run does not establish repeated-run reliability. This is an evaluation pattern, not a benchmark result or new locked formula. |

The original [tau-bench repository](https://github.com/sierra-research/tau-bench), reviewed on 2026-11-16, marks its task versions outdated and points to its successor. The 2024 paper and metric code are studied for the evaluation design; this change does not install or execute the old suite, reproduce its results, or import its historical model rankings.

The [NVIDIA migration guide](https://docs.nvidia.com/nemo/agent-toolkit/latest/resources/migration-guide.html), reviewed on 2026-11-16, states that NeMo Agent Toolkit was deprecated in October 2026 and is scheduled for end of life by the end of 2026. This note adapts runtime concepts without adding that dependency.

Official video pointers were located through the [Palantir Workflow Lineage team discussion](https://community.palantir.com/t/ama-workflow-lineage-team-the-story-behind-the-rename-and-whats-next/5575): [DevCon presentation](https://www.youtube.com/watch?v=aH_iNZKXKIY). Direct YouTube retrieval was rate limited; no complete viewing or transcript review is claimed. The architecture findings above rely on the retrieved primary documentation and paper.

## ROADMAP: bounded next work

These are proposed experiments and acceptance boundaries. They are not implemented capabilities, deployment commitments, or claims that the ideas are unique.

| ROADMAP scope | Smallest useful experiment | Evidence needed before promotion |
| --- | --- | --- |
| Source freshness and identity | Add explicit observation time, expiry policy, source revision, and runtime identity for one capability whose producer supplies them. | Missing, expired, future-dated, and wrong-runtime evidence must remain distinguishable; a new snapshot timestamp cannot renew old evidence. |
| Explain a blocking dependency | Project one declared dependency chain using existing CEG edges and the ORO inspection seam. | Explicit edge origin, bounded traversal, missing-parent disclosure, permission checks, and no invented cross-source edges or transitive readiness. |
| Verifier-guided remediation | Let an agent propose a repair for one reason code, then evaluate that proposal against the existing predicate in an isolated fixture. | Reproducible input, independent verdict, negative examples, and a clear boundary between proposal, approval, and authorized execution. The model cannot promote its own proposal. |
| Resumable governed writes | Exercise one existing authorized action through crash, timeout, and retry scenarios using a durable operation identity. | Demonstrate deduplication, explicit unknown outcomes, and recoverable intent/completion records. Reuse ORO and the canonical state store where applicable; dashboard reads remain side-effect free. |
| Useful work per measured energy | Compare two bounded execution choices for the same independently checked task. | Real exporter deltas, the same acceptance criteria, an explicit completed-work denominator, and missing-data labels. A zero or unknown denominator yields no efficiency claim; carbon remains ROADMAP. |
| Repeated operational reliability | Repeat a small fixed set of isolated workflows under controlled interruption and permitted input variation. | Freeze the task and policy versions; check resulting state and trajectory constraints independently; record every planned trial, failure, error, and missing outcome. Report reliability separately from best-of-many success and from one-run benchmark accuracy. No production side effects or paid model runs are introduced by this proposal. |

The design goal is an operator who can follow a decision from visible status to its exact predicate, evidence scope, and authorized next action. The present contribution is the shared readiness explanation. Freshness contracts, dependency analysis, remediation, resilience, and energy comparisons require their own implementation and evidence.

## Acceptance requirements

These are verification requirements, not a report that the checks have passed.

1. For each composed tile, the projection and corresponding summary row agree on `ready` and `reasons`; the evaluator is called once per tile.
2. A reachable producer with unsatisfied evidence remains `NOT_READY`. Missing evidence, modeled or sampled capabilities, missing artifacts, and failed verification retain their existing blockers.
3. Invalid count values block their tile, and non-object, non-JSON, or nonfinite producer envelopes become unavailable without hiding valid siblings. Adding the projection does not mutate the producer's source envelope or change existing summary semantics.
4. GET does not increase receipt depth, mint a signature, add a probe, or authorize execution.
5. Valid ready and blocked fixtures render their supplied predicate and reasons. Missing, unsupported, malformed, or contradictory contracts do not render as ready.
6. Snapshot/cache timestamps are labeled as such; evidence references remain references and unsafe URL schemes are not activated.
7. Route and UI verification use the actual served Frontier surface. Release status is reported only after the relevant tests, runtime observations, and deployment evidence are available.

Backend regression coverage belongs with [tests/test_frontier_manifest_readiness.py](../tests/test_frontier_manifest_readiness.py); surface checks must also follow the repository's [testing rule](../.claude/rules/testing.md).
