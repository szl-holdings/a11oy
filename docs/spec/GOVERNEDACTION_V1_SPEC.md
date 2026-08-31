# szl.dev/GovernedAction/v1

## The Governed Action Attestation Predicate — Version 1.0.0

**Status of this document:** Final standard. Published 2026-08-30.
**Document class:** Public technical specification, in the spirit of an In-Toto
Enhancement (ITE) predicate definition and IETF RFC editorial conventions.
**Authors:** Stephen Lutar, SZL Holdings.
**Maintained at:** `a-11-oy.com` and `a11oy.net` (machine-readable JSON Schema at
`https://a-11-oy.com/schemas/predicate.schema.json`).

---

## Abstract

This document specifies `szl.dev/GovernedAction/v1`, a predicate type for
in-toto ITE-6 attestations that records, for a single governed action taken by
an AI agent, what the agent was authorized to do, what it actually did, and
whether the required evidence exists. The predicate is designed for one load
bearing property: an independent verifier — an auditor, a regulator, a
customer — can evaluate the attestation fully offline, after the issuing
vendor's systems are unavailable or gone, and receive a truthful verdict. A
signed attestation with missing evidence evaluates to INCOMPLETE, never to
PASS. A valid signature is evidence of integrity, not of truth.

This is a technical standard. It makes no commercial claims, and every
statement about products, pricing, or markets is explicitly out of scope
(Section 13).

## 1. Introduction

AI agents now take consequential actions in production: writing to systems of
record, calling external APIs, changing permissions. For any one such action,
four questions must be answerable from durable evidence:

1. What was the agent authorized to do?
2. What did the agent actually do?
3. Does the required evidence exist?
4. Can an external auditor verify the record without entering the issuing
   platform?

Existing access-control infrastructure answers a prior question — what an
identity may access. This specification answers the evidentiary question:

> IAM says what an identity may access; a11oy proves what an AI agent was
> authorized to do, what it actually did, and whether the required evidence
> exists.

`szl.dev/GovernedAction/v1` is the predicate type of an in-toto ITE-6
attestation carried in a DSSE envelope. The in-toto attestation format is
governed by the CNCF; this document governs only the predicate, the
completeness semantics of its evaluation, and the verification rules that
make a conformant receipt checkable by any party with the public key — with no
network and no vendor contact.

### 1.1 Requirements language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
"SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document
are to be interpreted as described in RFC 2119.

## 2. Status, versioning, and conventions

- Predicate type URI: `szl.dev/GovernedAction/v1`
- This version: `v1.0.0` (2026-08-30)
- Envelope: in-toto ITE-6 Statement (`https://in-toto.io/Statement/v1`)
  wrapped in a DSSE envelope.
- Signing: Ed25519 via the DSSE pre-authentication encoding. Implementations
  SHOULD use the maintained `in-toto-attestation` PyPI package (v0.9.3+) and
  MUST NOT hand-roll DSSE or PAE in production code.
- Data model: JSON, constrained by the normative JSON Schema referenced in
  Section 3.

Versioning policy is defined in Section 10.

## 3. Normative data model

The normative JSON Schema is maintained at
`https://a-11-oy.com/schemas/predicate.schema.json` and mirrored exactly by
the reference implementation's code-level models (`src/a11oy/schemas.py`).
No drift between schema and code is tolerated: a discrepancy is a defect in
whichever artifact does not match this document.

An attestation payload (the `subject` + `predicate` of the in-toto Statement)
serializes a **GovernedActionReceipt**: the predicate described here plus the
decision context the signature must also cover. The complete receipt surface
is:

| Field | Type | Requirement | Definition |
|---|---|---|---|
| `receipt_id` | string, minLength 1 | MUST | Unique identifier of this receipt. One receipt per governed action, recorded at execution time — never assembled later. |
| `predicate` | GovernedActionPredicate | MUST | The predicate defined in Section 3.1. |
| `decision` | PolicyDecisionRecord | MUST | The policy engine's decision (Section 3.2). |
| `human_approval` | HumanApproval or null | MUST (conditionally) | Required when the decision was ALLOW and the policy required approval, and ALWAYS required for an ALLOW of an IRREVERSIBLE action (Section 5). |
| `observation_window` | ObservationWindow | MUST | `start` and `end` as RFC 3339 timestamps; `end` MUST be strictly after `start`. The governed period of the action. |
| `retention_days` | integer >= 180 | MUST | How long the receipt and its evidence are retained. The floor is 180 days (six months), per the Article 12 logging conformance profile (Section 8). |
| `issued_at` | RFC 3339 timestamp | MUST | Issue time of the receipt. |
| `generator` | string, minLength 1 | MUST | Name/version of the issuing implementation, verbatim (e.g. `a11oy/1.0`). Consumers MUST NOT infer truth from this string. |

`additionalProperties` is false at every object level. Unknown fields cause
schema rejection, not silent ignore — an open-field format invites quiet
semantic forks, and a format that forks quietly cannot be audited.

### 3.1 The GovernedAction predicate

| Field | Type | Requirement | Definition |
|---|---|---|---|
| `predicate_type` | `szl.dev/GovernedAction/v1` (const) | MUST | Fixed literal. An attestation declaring any other type is out of scope of this specification. |
| `action_id` | string, minLength 1 | MUST | Unique identifier of the governed action within the issuer's action chain (Section 9 of the reference implementation; chain integrity is a verification rule, Section 7). |
| `actor` | Actor | MUST | The natural person responsible for the action (Section 3.1.1). |
| `action_type` | string, minLength 1 | MUST | The kind of action, in the issuer's vocabulary (e.g. `deploy`, `db.write`, `permission.grant`). Producers SHOULD use a stable, documented vocabulary. |
| `side_effect_class` | enum | MUST | One of the four side-effect classes in Section 4. The recorded class is the most restrictive applicable class. |
| `evidence` | array of EvidenceItem | MUST | The evidence items attached to this action (Section 3.1.2). MAY be an empty array — but an empty array forces `completeness: INCOMPLETE` (Section 6). |
| `completeness` | `COMPLETE` or `INCOMPLETE` | MUST | The producer's asserted completeness state. The verifier re-derives it independently; a false COMPLETE assertion is a verification failure (Section 6). |
| `redaction_commitments` | array of RedactionCommitment | MUST | Salted-hash commitments for every redacted field (Section 3.1.3). MAY be empty when nothing is redacted. |
| `rfc3161_token` | string, minLength 1 | MUST | An RFC 3161 TimeStampToken over the receipt digest, base64-encoded; or the literal string `UNAVAILABLE` when no TSA was reachable at record time (Section 9.2). |
| `ntp_synced` | boolean | MUST | `true` only if the issuing host's clock was NTP-synchronized when the receipt was issued. Recorded truthfully even when `false`; the *strength* of the time proof is judged by the verifier, not asserted here (Section 9.2). |

#### 3.1.1 Actor

| Field | Type | Requirement | Definition |
|---|---|---|---|
| `actor_id` | string, minLength 1 | MUST | Stable identifier of the natural person. |
| `display_name` | string, minLength 1 | MUST | Human-readable name of the natural person. |
| `is_service_account` | `false` (const) | MUST | Pinned to `false` by the schema. See below. |

**`is_service_account` is structurally pinned to `false`.** Article 12(3)(d)
of Regulation (EU) 2024/1689 requires automatic logging capabilities that
enable, at minimum, identification of the natural persons involved in the
verification of results (read with Article 14(5) human oversight). A format
that permits a service account to stand in for the responsible natural person
would allow the actor field to be populated while the person it names is no
person at all. The pin is therefore not a policy preference: it makes the
substitution structurally unrepresentable. A receipt whose actor is a service
account cannot be produced, and any document claiming one is rejected at
schema validation, before any verdict logic runs.

The same Actor shape is used for `human_approval.approver`.

#### 3.1.2 EvidenceItem

| Field | Type | Requirement | Definition |
|---|---|---|---|
| `evidence_id` | string, minLength 1 | MUST | Unique identifier of this evidence item. |
| `kind` | string, minLength 1 | MUST | The evidence kind referenced by the policy's evidence obligations (e.g. `ticket`, `diff`, `approval_record`). Obligations accumulate across every matched policy rule; the verifier checks presence by `kind` (Section 6). |
| `sha256` | lowercase hex, exactly 64 chars | MUST | SHA-256 digest of the evidence artifact. The verifier does not fetch the artifact; the digest binds the claim to specific content, and the retention system MUST be able to produce content matching each digest on demand for `retention_days`. |
| `uri` | string or null | MAY | Retrieval hint. Consumers MUST NOT require its presence and MUST NOT treat link rot as evidence failure — digest mismatch on independently held content is the failure signal. |
| `description` | string or null | MAY | Human-readable note. Non-normative. |

#### 3.1.3 RedactionCommitment

Receipts circulate to auditors and may pass through intermediaries. Some
fields must be redacted for privacy or security. Uncontrolled redaction has
a known failure mode: a party redacts the very evidence that would have
exculpated it, and the resulting document says less than the truth while
appearing to say all of it. Salted-hash commitments close that hole: the
receipt proves a specific plaintext existed for each redacted field without
revealing the plaintext, and any holder of the plaintext (the auditor after
disclosure, the regulator under compulsion) can verify the binding.

For each redacted field:

| Field | Type | Requirement | Definition |
|---|---|---|---|
| `commitment_id` | string, minLength 1 | MUST | Unique identifier of this commitment. |
| `field_path` | string, minLength 1 | MUST | The JSON path of the redacted field within the original record. |
| `salt_b64` | canonical base64 | MUST | The salt, at least 16 bytes, base64-encoded. The salt is carried on the receipt because the security property is binding-plus-revealability, not key secrecy; low-entropy plaintexts would otherwise be dictionary-attackable. |
| `sha256_b64` | canonical base64 | MUST | `base64(SHA-256(salt \|\| 0x00 \|\| plaintext))` — the 0x00 separator prevents ambiguous concatenation. Canonical base64 only (RFC 4648, with padding, length divisible by 4). |

### 3.2 PolicyDecisionRecord

The signature covers the decision, not only the action. A receipt that
recorded what happened without recording what was decided would let an
allowed action be presented as an act of policy when it was an act of
omission.

| Field | Type | Requirement | Definition |
|---|---|---|---|
| `decision` | `ALLOW` or `DENY` | MUST | The policy engine's verdict, recorded before execution. Default is DENY unless a rule explicitly allows (Section 5.1). |
| `reason` | string, minLength 1 | MUST | The human-legible reason for the decision. |
| `first_match_rule` | string or null | MUST (may be null) | The rule that determined the outcome, when one exists. |
| `matched_rules` | array of string | MUST | Every rule the action matched. MAY be empty (implying default DENY). |
| `evidence_obligations` | array of string | MUST | Evidence kinds required by the union of every matched rule. These are the obligations the verifier enforces in Section 6. |
| `effective_side_effect_class` | enum | MUST | The most restrictive side-effect class across all matched rules. MUST be consistent with `predicate.side_effect_class`. |
| `requires_human_approval` | boolean | MUST | Whether policy required approval for this action. When true and decision is ALLOW, `human_approval` MUST be present. |

## 4. Side-effect classes

Every governed action is classified into exactly one of four side-effect
classes. The classes are ordered by blast radius and are never collapsed,
merged, or re-labeled:

| Class | Ordering | Definition |
|---|---|---|
| `READ_ONLY` | 0 (least restrictive) | The action reads state and writes nothing outside its own ephemeral context. |
| `REVERSIBLE` | 1 | The action changes state that can be fully restored to its prior value by a compensating action. |
| `EXTERNAL_VISIBLE` | 2 | The action is observable by parties outside the issuing organization (external API calls, customer-visible changes), even if technically revertible. |
| `IRREVERSIBLE` | 3 (most restrictive) | The action cannot be undone by any action available to the system: fund transfers, deletions of sole copies, published statements, credential rotations against third parties. |

Normative rules:

1. When multiple classifications are plausibly applicable, or when matched
   policy rules assign different classes, the **most restrictive class wins**
   (ordering above). Producers MUST implement this ordering with no escape
   hatch.
2. **`IRREVERSIBLE` actions always require human approval.** An ALLOW receipt
   for an IRREVERSIBLE action without a `human_approval` record is invalid at
   schema validation — the document cannot be parsed into a valid receipt —
   and is a hard FAIL at claim evaluation (Section 6).
3. Producers MUST NOT introduce additional classes in a v1 predicate.

## 5. Policy semantics recorded by the receipt

### 5.1 Default DENY

The policy engine denies unless a rule explicitly allows. `matched_rules`
empty with `decision: ALLOW` is a contradiction and MUST be treated as a
verification failure.

### 5.2 Signature is not truth

Verification keeps two ledgers and never merges them:

- **Signature validity** answers: was this artifact altered after signing?
- **Claim state** answers: is the recorded claim sound?

A valid signature over a false claim is a false claim with a valid
signature. Verdicts are constructed to keep this visible (Section 7).

### 5.3 Replay is non-mutating

Recovery and replay of recorded actions MUST NOT double-execute side effects;
the reference implementation enforces an idempotency-key scan before
re-execution. This is a producer obligation that the receipt surface supports
but cannot itself prove; verifiers MUST NOT treat replay safety as attested.

### 5.4 Deployment-drift gate

A record that a system was `RUNNING` is never evidence that a specific
reviewed revision was deployed. Reviewed-revision vs executed-revision drift
is a first-class gate in the reference implementation. Producers SHOULD
record revision identifiers as evidence when deployment actions are
governed; verifiers MUST NOT infer revision identity from runtime state.

## 6. Completeness rules

Completeness is evaluated by the verifier, not trusted from the producer.

1. **Missing evidence means INCOMPLETE, never PASS.** If any evidence
   obligation in `decision.evidence_obligations` has no corresponding
   `evidence` item of the required `kind`, the claim state is INCOMPLETE.
2. A predicate with an empty `evidence` array MUST carry
   `completeness: INCOMPLETE`. The JSON Schema enforces this with a
   conditional (`if`/`then`) and the reference model enforces it with a
   validator; a producer emitting an empty-evidence COMPLETE receipt emits an
   unparseable document.
3. A predicate that declares `completeness: INCOMPLETE` evaluates to
   INCOMPLETE even if all obligations appear satisfied — the producer's own
   declaration is authoritative in the conservative direction only. A
   declared INCOMPLETE can never be talked "up" to PASS by the verifier, and
   a declared COMPLETE can always be talked "down" to INCOMPLETE by missing
   evidence. This asymmetry is deliberate.
4. `is_service_account` not equal to `false`, or any schema validation
   failure, is a hard FAIL, not an INCOMPLETE: the document is not a
   GovernedAction receipt at all.
5. The verifier reports every detected problem. Verdicts and their inputs
   are separate fields in the result; consumers SHOULD surface the problem
   list, not just the verdict.

## 7. Verification rules and verdicts

A conformant verifier MUST:

1. Validate the DSSE envelope: exactly one signature per the producer's
   backend, signature verifies against the PAE-encoded payload with the
   registered public key identified by `keyid`. Failure ⇒ `INVALID`.
2. Parse the payload as a GovernedActionReceipt against the normative
   schema. Failure ⇒ `INVALID` (documented as schema rejection).
3. Evaluate the claim independently of the signature per Section 6,
   producing `PASS`, `INCOMPLETE`, or `FAIL` with a problem list.
4. Combine, never merge:

| Signature valid | Claim state | Verdict |
|---|---|---|
| yes | PASS | **VALID** |
| yes | INCOMPLETE | **INCOMPLETE** |
| (any) | FAIL | **INVALID** |
| no | (any) | **INVALID** |

A one-byte alteration anywhere in the signed payload breaks the signature
and yields `INVALID`. A perfectly-signed receipt missing one obligated
evidence item yields `INCOMPLETE`. The two outcomes never share a verdict.

Verification MUST NOT require network access to, or any system operated by,
the issuing vendor. An offline verifier with the public key and the envelope
MUST reach the same verdict as an online one.

## 8. Article 12 logging conformance profile

A separate machine-readable profile,
`evidence/conformance/eu-ai-act-article-12.yaml`, maps fields of the
conformant receipt to the automatic-logging requirements of Article 12 of
Regulation (EU) 2024/1689: 11 mapped entries, each a JSONPath plus a named
validator, with `retention_minimum_days: 180`.

This specification and that profile together constitute an **Article 12
logging conformance profile** — nothing more. Producers and publishers MUST
NOT describe conformance to this specification as being "EU AI Act
compliant." Applicability, high-risk classification, and deployer
obligations are customer-specific determinations that a receipt format
cannot make.

## 9. Anti-backdating

### 9.1 Why this is normative

A receipt backdated by its issuer is more dangerous than a missing receipt:
it is a false record wearing the costume of proof. The format therefore makes
time integrity a recorded field pair whose strength is judged at verification
time, rather than an asserted property.

### 9.2 The time record

- `rfc3161_token`: an RFC 3161 TimeStampToken from a trusted timestamping
  authority over the receipt digest. If no TSA was reachable, the producer
  MUST emit the literal `UNAVAILABLE` — a disclosed gap, not an empty field.
  An omitted or fabricated token is not representable: the field is required
  and minimum-length, and a fabricated value fails TSA signature checks.
- `ntp_synced`: the host clock's synchronization state at issue time, recorded
  truthfully. The producer MUST NOT assert `true` when synchronization state
  is unknown; unknown state is recorded as `false`.

### 9.3 Time strength at verification

| `rfc3161_token` | `ntp_synced` | Time strength |
|---|---|---|
| valid token | `true` | **STRONG** |
| `UNAVAILABLE` or `ntp_synced: false` | (recorded) | **WEAK** |

WEAK is an audited state, not a violation: a receipt recorded during a TSA
outage records the truth. Verification profiles MAY require STRONG time; such
a requirement MUST be stated by the consuming profile, never assumed.

## 10. Versioning policy

- The predicate URI carries a major version: `/v1`.
- Within v1, only clarifications and strict tightenings (adding rejections)
  are permitted, as patch revisions of this document (`v1.0.1`, …).
  Tightenings MUST NOT invalidate receipts previously VALID.
- Any relaxation — a field becoming optional, a new enum value, a new class —
  requires a new major version URI (`szl.dev/GovernedAction/v2`).
- Producers MUST NOT extend v1 predicates with custom fields
  (`additionalProperties: false` exists to make this enforceable).

## 11. Security considerations

1. **Signature scope.** The signature covers the full receipt: predicate,
   decision, approval, observation window, retention. Truly: anything the
   signature does not cover is not claimed.
2. **Key management.** Producers are responsible for key custody and
   rotation. Key compromise invalidates trust in that key's receipts; a
   key-disclosure mechanism (transparency log, published rotation) is
   RECOMMENDED. Sigstore keyless signing is out of scope of v1.
3. **Trusted time depends on the TSA.** The RFC 3161 guarantee inherits the
   TSA's trustworthiness. Deployments SHOULD use a TSA under their own or a
   neutral party's control where evidentiary weight matters.
4. **Evidence retention is the load-bearing operational duty.** The format
   binds claims to digests; only a retention system that can produce
   digest-matching content for `retention_days` makes the binding meaningful
   against an auditor. Local durability (fsync before acknowledge) and remote
   durability (a visible `PENDING_SYNC` state until confirmed) are separate
   states and MUST NOT be conflated: local durability is not remote
   durability.
5. **Redaction commitments bind but do not conceal against brute force** for
   low-entropy plaintexts; the salt requirement (>= 16 bytes) and the
   separated digest construction mitigate but, as with any commitment to
   guessable content, do not eliminate guessing. Fields foreseeable to be
   low-entropy SHOULD be retained rather than redacted where policy allows.
6. **Chain integrity.** Receipts from one issuer are ordered in an action
   chain; the reference verifier checks chain linkage so a silently dropped
   receipt between two known receipts is detectable. Gaps are reportable;
   they are not forgivable.
7. **`UNAVAILABLE` and `UNKNOWN` are states, not decorations.** An audited
   gap in the record is a first-class outcome. A silent gap is a defect. Any
   tool processing conformant receipts MUST preserve this distinction.

## 12. Relationship to identity and access management

This specification does not alter, replace, or evaluate what an identity may
access. IAM systems make access decisions; policy engines make allow/deny
decisions. This specification defines the durable, independently checkable
record of what was authorized, what occurred, and whether the required
evidence exists. The boundary is drawn deliberately and verbatim:

> IAM says what an identity may access; a11oy proves what an AI agent was
> authorized to do, what it actually did, and whether the required evidence
> exists.

## 13. Non-goals and out of scope

This specification explicitly does not define, prescribe, or claim:

1. **A decision mechanism.** How policy is authored or evaluated is
   implementation territory; only the recording of its output is normative.
2. **MCP servers, an agent framework, new UI surfaces, a multi-tenant SaaS
   control plane, billing, or AQL.** These are v1 exclusions of the
   reference system.
3. **Sigstore keyless signing.** Deferred to a later version.
4. **EU AI Act compliance.** Conformance support is limited to the Article 12
   logging conformance profile (Section 8). The phrases "EU AI Act compliant"
   and equivalent marketing claims are prohibited descriptors of this format.
5. **Commercial claims of any kind.** Pricing, market size, competitive
   positioning, customer obligations, and product roadmaps are out of scope.
   This is a technical standard; nothing in it is a sales statement.

---

*End of specification. The machine-readable normative schema, the reference
verifier, the Article 12 conformance YAML, and a signed self-audit receipt
evaluating to INCOMPLETE are published together with this document as one
dated event: 2026-08-30.*
