<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Operational evidence integration and research decisions

Date: 2026-11-16. Audited source baseline: `8e31409245f6223dda6bb9784fbcbefd5f9892de`.

## Scope and current implementation

Command v2 now consumes the existing evidence graph and storage status alongside
build identity and the operational receipt window. This is an observation surface.
It does not authorize execution, sign receipts, verify cryptographic signatures,
replay Lean proofs, establish model quality, or certify a deployment.

The implementation reuses `pages/command-v2.html`, its existing 60-second client
observation lifetime, literal-text source inspector, and same-origin GET batch.
It adds no backend, store, publisher, credential, or alternate execution path.

| Existing contract | UI meaning |
| --- | --- |
| `/api/a11oy/v1/ledger` | Recent returned receipts, with source-provided `count_scope`; not total receipts minted |
| `/api/build-info` | Explicit Git source revision reported by this process |
| `/api/a11oy/v1/evidence/graph` | Reported relationships and their verdicts; bounded rendering and inspectable source |
| `/api/a11oy/v1/storage/status` | Storage mode, writer role, access, alerts, pending publication, errors, and per-store observations |

A source-reported identity match compares the explicit Git source revision on
runtime edges with build-info. A distinct HF runtime revision is legitimate.
Historical artifact edges do not participate in this comparison. Missing,
expired, malformed, unavailable, conflicting, and different observations remain
distinct from a match. Two matching reads are not an atomic deployment witness.

The graph's digest remains a reported content identity. The browser does not
validate it cryptographically. `receipt_head` is not used as a chronological
chain head. Rendered rows are capped at 12, while returned and input counts remain
visible. Inconsistent counts or truncation flags are refused.

Storage `mode=FENCED` describes lease enforcement; it is not equivalent to
`role=FENCED`. A reported writable service can have a blocked individual store,
and disabled persistence can also report writable. The UI exposes those facts
without deriving a durability badge. Null ages and error maps remain unavailable;
they never become zero. Source-provided text is rendered as text, not markup.

## Observed baseline, not a release attestation

Read-only probes at approximately 18:25 America/New_York on 2026-11-16 found:

- Product and HF build-info both reported Git source
  `f6e30e83343674e544af0ad83a03c058d9c9d53b`.
- Both basic `/api/readyz` responses reported READY.
- Product storage reported FENCED mode, WRITER role, writable true, no pending
  publication, and an empty active-error map.
- Product graph contained one OBSERVED environment identity relationship and no
  VERIFIED relationships.
- The ledger returned 32 recent receipts, explicitly scoped to the returned
  window. Its chain verification was NOT_EVALUATED_BY_THIS_ROUTE.

These observations are time-bound and cover their stated endpoint semantics.
They do not establish complete product readiness, end-to-end inference quality,
all-store recovery, or deployment of this candidate.

Sources: [product build](https://a-11-oy.com/api/build-info),
[HF build](https://szlholdings-a11oy.hf.space/api/build-info),
[storage](https://a-11-oy.com/api/a11oy/v1/storage/status),
[graph](https://a-11-oy.com/api/a11oy/v1/evidence/graph),
[ledger](https://a-11-oy.com/api/a11oy/v1/ledger).

## The larger frontend and backend boundary

The audited [architecture document](../architecture.md) identifies the pinned
`vendor/platform` application as the canonical React build. The Python image
ships the tracked `console/` and `pages/` surfaces. The canonical React artifact
still lacks complete runtime binding for `/api/graphql`, `/api/graphql/ws`, and
the Atelier request contract. That deployment remains BLOCKED.

Editing the retired root `web/` application would not close this boundary.
The Command change improves the currently shipping Python surface. It is one
completed source integration, not closure of the canonical React deployment.

## Primary research and adaptations

The following are architectural lessons, not assertions that external products
satisfy SZL doctrine or that SZL already implements every proposed capability.

| Primary source | Finding | SZL decision |
| --- | --- | --- |
| [Palantir SuperRepo](https://www.palantir.com/docs/foundry/superrepo/overview) and [November 10 remote-preview release](https://www.palantir.com/docs/foundry/announcements) | Co-develop domain definitions, functions, and applications; remote preview is read-only and refuses schema mismatches. SuperRepo remains Beta. | Reuse canonical schemas and bind compatible frontend/backend releases. Preserve an explicit no-write preview. |
| [Palantir OSDK repository](https://github.com/palantir/osdk-ts) | Domain SDK generation is separate from authenticated client construction. | Adopt the contract discipline through existing SZL APIs; adding a Foundry-specific dependency is not required. |
| [Palantir action permissions](https://www.palantir.com/docs/foundry/action-types/permissions) | Read filtering alone does not constrain downstream action writes. | Existing ORO/server authorization remains authoritative; UI state is never an authorization grant. |
| [Palantir evaluation of ontology edits](https://www.palantir.com/docs/foundry/aip-evals/ontology-edits) | Cases can evaluate actual created, changed, and deleted objects in isolated simulations. | Evaluate intended postconditions and invariant preservation, not only generated prose. |
| [LangGraph fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) | Retryable nodes have at-least-once execution; external effects need durable idempotency and reconciliation. | Missing acknowledgement means UNKNOWN. Use existing Khipu/operation identities before a side effect. |
| [NVIDIA jailbreak protection](https://docs.nvidia.com/nemo/guardrails/latest/configure-guardrails/guardrail-catalog/jailbreak-protection) | Detector outages fail open for this rail. | A detector result cannot replace deterministic authorization or mandatory evidence verification. |
| [Lean proof validation](https://lean-lang.org/doc/reference/latest/ValidatingProofs/) | Kernel acceptance and intended theorem meaning are separate questions; stronger checking is needed for unreviewed generated proofs. | Freeze intended statements and dependencies; separate unavailable checks, rejection, and accepted proofs. |
| [SLSA verification summaries](https://slsa.dev/spec/v1.2/verification_summary) | Verification binds artifact, verifier, policy, and evidence. | Reuse existing receipt verification and exact artifact binding. Do not label generic operational evidence as a SLSA build level. |

### Papers and technical video

Palantir's [Connecting AI and Machine Learning with Operations (2022)](https://www.palantir.com/assets/xrfr7uokpv1b/4mSNoWcwpgo5G8lRmBSnbk/2d33af8f6c717377197aae56d683f82d/Connecting_AI___Machine_Learning_with_Operations.pdf)
describes a common operational model, feedback, lineage, and governed writeback.
It is a vendor whitepaper with notional examples, not independent empirical
validation.

[Defeating Prompt Injections by Design](https://arxiv.org/abs/2503.18813)
(Debenedetti et al., revised June 2025) separates trusted control flow from
untrusted data and uses capabilities to constrain data flow.
Its [official code](https://github.com/google-research/camel-prompt-injection)
is a research artifact, not an assumed production security boundary.

The official [OSDK technical video](https://www.youtube.com/watch?v=vSJ5H00V7Es)
has a [written walkthrough](https://blog.palantir.com/building-with-palantir-aip-the-ontology-software-development-kit-823fe5ac7aae)
dated February 16, 2024. The research read the written walkthrough and verified
the video link; no full transcript was available, so no claim is made that the
video was watched. The useful material covers SDK generation, app types,
permission scopes, and a React integration.

## Doctrine and mathematical boundaries

The eight locked formula identifiers remain exactly
`F1,F4,F7,F11,F12,F18,F19,F22`. Lambda uniqueness remains Conjecture 1 and Khipu
BFT safety remains Conjecture 2. This work neither changes those definitions nor
expands the scope of their proofs.

The existing ORO sequence remains:
observe, diagnose, retrieve, propose, verify, simulate, authorize, execute,
independently validate, record. Observations do not authorize actions.
Signatures do not establish empirical correctness. A formal theorem establishes
its stated modeled property under its assumptions; runtime correspondence needs
separate evidence. Receipts are produced for state changes, not ordinary reads.

## Proposed frontier experiments — MODELED

### Evidence dependency invalidation

Extend the existing evidence graph so a capability claim records exactly which
observations, model revision, evaluation, policy, and proof support it. Expiration
or replacement of a dependency should make that claim stale across the UI and API.

Acceptance: replace an artifact behind a stable name, expire an observation, and
revoke an evaluation. Only dependent claims lose eligibility. The graph records
why, while unrelated claims remain unchanged. The current client expiry is a
small implemented step; cross-service invalidation is not delivered here.

### An operational replay workspace

Freeze one failed ORO operation's inputs, revisions, evidence, authorization
scope, and observed result. Compare alternative plans in an isolated execution
context using the same transition rules and existing executor interfaces.

Acceptance: replay must make zero production writes. It must distinguish failure,
unknown outcome, rejected permission, and invalid postcondition. Recovering after
a committed external effect must not duplicate that effect.

### Plan the next useful observation

Given a blocked or unknown claim, propose the smallest useful next check:
artifact digest, provider state, inference probe, evaluation, or formal replay.
The existing authorization and budget rules govern any execution.

Acceptance: ambiguous historical cases resolve with fewer redundant checks while
preserving UNKNOWN when necessary. Absence of local evidence must never establish
that an external action did not happen.

These are testable design proposals, not world-first claims or released features.
Initial beneficial applications include infrastructure maintenance, scientific
reproducibility, and transparent allocation of limited compute. Domain-specific
qualification and authorization remain necessary.

## Verification and release boundary

The existing Command observation workflow owns automated validation. Relevant
commands include the Node observation suite, Python preview and route tests,
and pinned Playwright browser tests at 1280, 390, and 320 pixel widths.

A local preview may read public production GETs while serving candidate UI bytes.
That establishes client/backend compatibility for observed responses. It is not
proof of candidate publication. The separate exact-source release witness checks
deployed source identity, candidate script bytes, and vendored assets after
canonical publication.

Use the existing protected review and single HF publisher. A successful local
test, source-reported match, or basic READY response does not close the remaining
requirements in [the production roadmap](../PYTHON_PRODUCTION_ROADMAP.md).

## Candidate validation snapshot

The [unsigned compatibility observation](command-evidence-live-preview-2026-11-16.json) binds the tested page bytes to a read-only live preview. It records 35 Node cases, 58 Python cases plus 36 subtests, six Chromium cases, and 13 independent adverse-input review checks. The final mobile CSS change also passed its targeted three-viewport browser case. These results are local software validation, not a GitHub approval or release attestation.

At 18:38:56 America/New_York, the candidate consumed the live graph, build, and storage contracts successfully. Twelve of thirteen source requests returned observed JSON; Hatun evidence returned HTTP 403 and remained unavailable. Every browser request was GET, source inspection made no additional request, and no horizontal overflow appeared at 1280, 390, or 320 pixels. The candidate was not deployed by this test.
