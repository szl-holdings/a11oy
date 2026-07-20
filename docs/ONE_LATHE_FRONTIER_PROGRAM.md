# SZL One Lathe Frontier Program

**Document class:** Normative estate-control program specification

**Schema:** `schemas/lathe/program-snapshot.v1.schema.json`

**Tracked work:** [GitHub issue #962](https://github.com/szl-holdings/a11oy/issues/962)

**Specification maturity:** `MODELED`
**Operational state:** `NOT_EVALUATED`

## 1. Purpose and boundary

The One Lathe program defines how SZL Holdings produces one bounded,
machine-readable snapshot of the authorized software and research estate. The
snapshot records what was inspected, which revision was inspected, when it was
collected, how complete the collection was, what evidence supports each
property, and which facts remain unknown or stale.

This specification is not evidence that an asset is healthy, deployed,
licensed, secure, current, or live verified. It does not add or claim a model,
kernel, user interface, API endpoint, physical lathe controller, CAM system,
CNC safety function, digital twin, or shop-floor control capability.

The name "One Lathe" describes the program's consolidation discipline: recover
existing work, admit evidence, remove unsupported duplication through approved
migrations, and keep one canonical record for each capability.

## 2. Governing rules

The repository doctrine in [`AGENTS.md`](../AGENTS.md) remains authoritative.
The program adds the following snapshot-specific rules:

1. Discovery is bounded by explicit inputs, queries, organization names,
   revisions, and pagination evidence. An open-ended crawl is invalid.
2. Every record carries `source`, `revision`, `collectedAt`, `coverage`, and
   `evidence`.
3. Every claim identifies the exact property it describes. Evidence for one
   property cannot establish another property.
4. Missing, conflicting, inadmissible, or stale evidence blocks promotion.
5. A null operational state is never converted to success for display,
   scoring, aggregation, or publication.
6. Collection is read-only. Merge, release, deployment, training, publication,
   DNS, billing, visibility, archival, deletion, and hardware changes require
   separate governed actions and receipts.
7. A generated snapshot is not canonical until its bytes and source revision
   have been independently verified and bound to an approved DSSE/Lake receipt.

## 3. Claim maturity

Maturity belongs to one property claim, never to an entire asset by inference.

| Maturity | Required meaning |
| --- | --- |
| `PROVEN` | A non-vacuous formal proof establishes the exact formal property named by the claim. It does not establish runtime health, licensing, security, deployment, freshness, or performance. |
| `MEASURED` | A reproducible observation or experiment measured the exact property under recorded conditions, revision, time, inputs, and instrumentation. |
| `MODELED` | A declared model, design, simulation, or uncalibrated estimate describes the property. It is not a live observation. |
| `CONJECTURE` | The property is explicitly proposed but is neither proven nor measured sufficiently. |
| `OPEN` | The property has not been resolved from admissible evidence. |

`PROVEN` is valid only for a formal property. A service, model, deployment,
license, or security posture cannot be blanket-labeled `PROVEN`.

## 4. Operational states and null states

Operational state is orthogonal to claim maturity.

Non-null operational states are:

- `AVAILABLE`: admissible, current evidence establishes availability for the
  exact declared boundary.
- `DEGRADED`: the boundary operates with a documented impairment.
- `BLOCKED`: a known dependency or policy gate prevents the declared operation.
- `FAILED`: an attempted operation failed and the failure evidence is retained.

The exact operational null states are:

- `UNKNOWN`
- `NOT_EVALUATED`
- `UNAVAILABLE`
- `OFFLINE_UNTIL_KEYED`
- `QUARANTINED`
- `STALE_EVIDENCE`

Null states are first-class results. They require `promotionEligible: false`,
cannot use `SUFFICIENT` evidence state, and must retain at least one blocker or
missing-evidence reason. `UNKNOWN` is not a degraded success.

## 5. Property-specific evidence

Each claim selects one property kind from the schema. The initial kinds include
identity, provenance, formal property, runtime health, licensing, security,
freshness, deployment, live verification, performance, data rights, model
qualification, and coverage.

Evidence substitution is forbidden:

| Evidence held | It may support | It must not substitute for |
| --- | --- | --- |
| Formal proof | The named formal invariant | Runtime health, deployment, license, security, performance |
| Unit or integration test | Behavior exercised at the tested revision | Production deployment or live verification |
| Runtime probe | The observed endpoint or process at the recorded revision and time | Source provenance, licensing, or broad security posture |
| License file or registry response | The recorded license assertion and source | Data rights, consent, export control, or legal advice |
| Benchmark receipt | The named metric under recorded conditions | General capability, safety, or another hardware/software configuration |
| DSSE/Lake receipt | Integrity and signer-bound assertions in the receipt | Truth of an unsupported assertion inside the receipt |

Every evidence item records its own source, revision, collection time, digest
when bytes are available, property kind, evidence kind, and admission state.
Evidence admission states are `ADMISSIBLE`, `PARTIAL`, `ABSENT`, `CONFLICTING`,
`STALE`, or `INADMISSIBLE`.

## 6. Bounded coverage

Coverage describes the collection boundary rather than implying completeness.
Every coverage object must:

- set `bounded` to `true`;
- declare one of `EXPLICIT_INPUT_SET`, `BOUNDED_MANIFEST`, or `BOUNDED_QUERY`;
- list the included scope and explicit bounds;
- retain exclusions and missing items;
- state whether collection was complete inside those bounds; and
- record expected and observed counts when those counts are known.

Unknown expected counts remain `null`; they must not be replaced by zero.
Pagination, API limits, permission failures, timeouts, and excluded private
assets belong in `missing` or `excluded`.

## 7. Snapshot contract

A conforming program snapshot contains:

- schema and program identifiers;
- a unique snapshot identifier;
- a generator timestamp and a canonical `sha256:` digest;
- generator name, version, source, and revision;
- top-level source, revision, and collection time;
- bounded estate coverage;
- the snapshot's property-specific maturity and operational state;
- one or more asset or evidence records;
- explicit risks and blockers;
- an approval decision; and
- a receipt binding state.

Each record repeats source, revision, collection time, bounded coverage,
evidence, claims, promotion eligibility, blockers, and risk notes. This
intentional repetition makes a record independently auditable after export.
The root and record `maturity` fields describe only the evidence maturity of
that snapshot or record as a collection artifact; they do not confer blanket
maturity on the asset. Capability assertions live only in property claims.

The JSON Schema is closed with `additionalProperties: false` at every governed
object boundary. Out-of-schema fields fail validation rather than silently
surviving as unreviewed claims.

## 8. First snapshot input lanes

The first generator wave may read only existing authorized evidence for:

1. Lake and DSSE receipt integrity and verification state.
2. Brain source, canonicalization, freshness, and evidence-admission state.
3. Formula registry revision, digest, reconciliation, and admission state.
4. Lean/mathlib linkage and exact theorem state.
5. MATLAB/Octave engine availability, isolation, version, and license state.
6. Sovereign inference and model-qualification evidence.
7. GitHub, Hugging Face, and deployment revision evidence.

These are input lanes, not capability claims. If a lane lacks admissible
evidence, it must remain in an operational null state.

## 9. Deterministic generation

For a fixed ordered input set and generator revision, generation must produce
the same canonical snapshot bytes apart from fields explicitly supplied as
fixed inputs, including `snapshotId` and `collectedAt`. Canonical ordering and
the digest input exclude `generatedAt` and `digest`; both fields remain in the
published envelope for audit and transport.

The future generator must:

1. accept an explicit input manifest;
2. refuse unbounded discovery;
3. normalize ordering before serialization;
4. preserve unknown and stale states;
5. validate against the strict schema before writing;
6. write atomically without mutating source systems; and
7. emit the canonical `sha256:` content digest for independent verification.

Collection time must be supplied by the caller or captured once and reused. A
fresh clock read per record would make the same input nondeterministic.

## 10. Promotion and receipt gate

`promotionEligible` may be true only when all properties required by the target
promotion policy have `SUFFICIENT` admissible evidence and no required property
is in a null state. The schema prevents a null state from being marked eligible,
forces promotion ineligible while the receipt is unbound, and forces promotion
ineligible unless `approvalDecision.decision` is `APPROVED`. Policy remains
responsible for defining the required property set and requiring independent
receipt verification before publication.

Publication requires a separately verified receipt binding that includes:

- canonical snapshot digest;
- snapshot schema version;
- source commit and generator revision;
- generator version;
- approval decision, scope, actor, and time;
- signer identity and verification policy; and
- independent verification result.

A SHA-256 digest without a verified signature proves content identity only; it
does not establish approval or truth.

The checked-in snapshot is an immutable, non-promoted subject. Its
`receiptBinding` remains explicitly unbound in that source artifact. After a
protected merge, `.github/workflows/one-lathe-receipt.yml` regenerates the
snapshot byte for byte, validates the schema and digest, and signs a canonical
receipt subject containing the snapshot plus the exact repository, merged git
revision, workflow identity, and artifact path. GitHub OIDC supplies the signer
identity; Fulcio issues the certificate; Rekor records the event. A separate
verifier pins the main-branch workflow identity and issuer, checks the
certificate chain and Rekor inclusion, rejects outer/bundle splicing, and
compares the signed subject with the canonical snapshot. The verified envelope
is then written to the append-only `governance-receipts` branch and read back by
exact git blob SHA. Any signing, verification, publication, or readback failure
fails the workflow.

This binding is external by design. Mutating `receiptBinding` inside the signed
snapshot would change the subject digest and create a circular in-band binding.
The receipt proves that the exact bytes and merged revision were signed; it does
not alter approval, maturity, runtime health, safety, or promotion eligibility.

## 11. Fail-closed acceptance rules

Reject a snapshot when any of the following is true:

- discovery is unbounded;
- a record omits provenance, revision, collection time, coverage, or evidence;
- a claim omits its property kind or uses evidence from another property;
- evidence is stale but the operational state is not `STALE_EVIDENCE`;
- a null state is marked promotion eligible;
- an expected count is unknown but encoded as a fabricated zero;
- a source or receipt digest does not match;
- a receipt is tampered, unsigned, untrusted, revoked, or bound to different
  snapshot bytes;
- a field is outside the strict schema; or
- a snapshot claims runtime, deployment, model, UI, manufacturing, or safety
  behavior that was not independently observed for that exact boundary.

## 12. Delivery sequence

The bounded issue #962 sequence is:

1. land this canonical specification and strict schema;
2. add the read-only deterministic generator;
3. add strict schema, stale-evidence, bounded-discovery, provenance, and receipt
   tamper tests;
4. generate candidate outputs under `artifacts/lathe/` from explicit inputs;
5. independently verify the bytes, source revisions, and evidence admission;
6. bind the verified snapshot to a governed DSSE/Lake receipt; and
7. publish only after the approval and receipt gates pass.

No stage may be skipped by relabeling `MODELED`, `OPEN`, or a null state as a
successful runtime result.

## 13. Optional manufacturing lane

A future physical-lathe lane remains `OPEN`. It requires a separate hazard
analysis, qualified real-time CNC controller, and independent hardware safety
boundary. A11oy must remain outside the servo and emergency-stop loops and may
consume only read-only machine evidence until that separate program is
qualified.

## 14. Related repository guidance

- [`AGENTS.md`](../AGENTS.md) - doctrine and honest-status rules.
- [`docs/PROVENANCE.md`](PROVENANCE.md) - repository provenance guidance.
- [`docs/PUBLIC_PATTERN_SYNTHESIS.md`](PUBLIC_PATTERN_SYNTHESIS.md) - clean-room
  research and synthesis boundary.
- [`docs/BRAIN_HONESTY.md`](BRAIN_HONESTY.md) - Brain evidence and trust limits.
- [`docs/SUBSTRATE_REALITY_MAP.md`](SUBSTRATE_REALITY_MAP.md) - substrate claim
  boundaries.
