# Publishing GovernedAction/v1: an open receipt format for what your AI agents did

**Date: 2026-08-30**
**Author: Stephen Lutar, SZL Holdings**
**Post to: dev.to, Hacker News (Show HN), LinkedIn. One dated event, one URL.**

---

Today SZL Holdings is publishing `szl.dev/GovernedAction/v1` as an open
standard: a specification, a reference verifier, an Article 12 logging
conformance profile in YAML, and a signed self-audit receipt — released
together, dated, and verifiable by anyone without our involvement.

## What was published

Four artifacts, one repo, one event:

1. **The specification.** `szl.dev/GovernedAction/v1` is a predicate type for
   in-toto ITE-6 attestations (a CNCF-governed format) with DSSE signing,
   built on the maintained `in-toto-attestation` package. The spec is written
   to RFC 2119 discipline: every field carries MUST/SHOULD/MAY, and the
   normative JSON Schema mirrors the reference implementation exactly.
2. **The reference verifier.** Fully offline. Feed it an envelope and a
   public key; no network, no vendor contact, no account on anything we
   operate.
3. **The Article 12 logging conformance profile.** Eleven mapped entries —
   JSONPath plus named validator, `retention_minimum_days: 180` — from receipt
   fields to the automatic-logging requirements of Article 12 of Regulation
   (EU) 2024/1689.
4. **Our own self-audit receipt. It verifies INCOMPLETE, and we published it
   anyway.** More on that below.

## Receipts, not dashboards

The question this format answers is not "what is my agent fleet doing right
now." Monitoring tools answer that, and that lane is well served and well
funded. The question this format answers is the one that arrives after
something goes wrong, from the people who were not in the room: *what was the
agent authorized to do, what did it actually do, and does the required
evidence exist?*

> IAM says what an identity may access; a11oy proves what an AI agent was
> authorized to do, what it actually did, and whether the required evidence
> exists.

A dashboard is a view rendered by a vendor's running system. It is as good as
the vendor's uptime, retention, and incentive to show you everything. A
receipt is different: a signed, self-contained artifact that survives the
vendor, the outage, and the dispute. The design rules follow from that:

- **Missing evidence means INCOMPLETE, never PASS** — enforced in the
  verifier's code, not in our marketing.
- **Signature is not truth.** A valid signature proves the artifact was not
  altered. It says nothing about whether the claim inside is sound. The
  verifier keeps those ledgers separate and never merges them.
- **Time is recorded, not asserted.** Every receipt carries an RFC 3161 token
  (or the literal `UNAVAILABLE` when the timestamping authority was
  unreachable) and the host's NTP sync state. Backdating resistance is a
  field, not a promise.
- **Receipts name natural persons.** `is_service_account` is pinned to
  `false` in the schema itself, per the Article 12(3)(d) rationale: a record
  of "who verified this" that can be filled by a service account names no
  one. The substitution is structurally unrepresentable, not just unlikely.
- **Redaction cannot destroy exculpatory evidence.** Every redacted field
  carries a salted-hash commitment, so a redacted receipt still binds the
  redactor to a specific plaintext.

## The invitation to verify us

The reference verifier is public and the self-audit receipt is signed. Run
it. Here is what will happen: the signature will verify, and the claim state
will come back **INCOMPLETE** — our own evidence obligations are not fully
met today, and the format we are asking you to trust refuses to say
otherwise.

We could have waited until the receipt came back clean. We published it
anyway, dated, because a standard whose first published artifact is the
issuer's own failure state is a standard that means what it says about
completeness. `INCOMPLETE` is an audited state, not an error page. When our
evidence coverage closes, we will publish the succeeding receipt — and the
old INCOMPLETE one stays up, because the chain is the point.

## The invitation to emit

This is an open standard in the practical sense: **any organization, including
any competitor, can emit conformant receipts today** — no license, no
partnership, no phone call. If your agent platform, your internal tooling, or
your client deliverables produce actions that an auditor will one day ask
about, emit `szl.dev/GovernedAction/v1`. The verifier will check your receipts
the same way it checks ours. A format only becomes the evidence layer if
records written by parties who do not like each other still verify the same
way.

We also ship a conformance harness: point it at your receipts and it reports
schema conformance, completeness semantics, and the Article 12 mappings. On
the timeline question: Gartner projects 40% of enterprise applications will
embed task-specific agents by the end of 2026, up from under 5% in 2025. The
organizations adopting this earliest are the ones who will be asked first.

## The Article 12 conformance profile

Reproduced in full — machine-readable, normative, and deliberately scoped:

```yaml
yaml_subset: SZL-YAML-1
profile: eu-ai-act-article-12-logging
schema_version: 1
regulation: Regulation (EU) 2024/1689
scope_note: Article 12 logging conformance profile. This is NOT a claim of EU AI Act compliance. Applicability, classification, and deployer obligations are customer-specific.
retention_minimum_days: 180
out_of_scope:
  - "Art. 12(3)(b): reference database checks apply to Annex III 1(a) biometric systems only"
  - "Art. 12(3)(c): matched input data applies to Annex III 1(a) biometric systems only"
entries:
  - provision: Art. 12(1)
    requirement: automatic recording of events (logs) over the lifetime of the system
    jsonpath: "$.receipt_id"
    validator: nonempty_string
    status: MAPPED
    note: one receipt per governed action, recorded at execution time, not assembled later
  - provision: Art. 12(2)(a)
    requirement: recording of events relevant to identifying risk situations and substantial modifications
    jsonpath: "$.decision.effective_side_effect_class"
    validator: enum_side_effect_class
    status: MAPPED
    note: blast radius is priced per action in four never-collapsed classes
  - provision: Art. 12(2)(b)
    requirement: facilitating post-market monitoring (Art. 72)
    jsonpath: "$.retention_days"
    validator: gte_180
    status: MAPPED
    note: records persist at or above the retention floor so monitoring can consult them
  - provision: Art. 12(2)(c)
    requirement: monitoring the operation of the system (Art. 26(5))
    jsonpath: "$.decision.decision"
    validator: enum_allow_deny
    status: MAPPED
    note: every action records its allow or deny decision
  - provision: Art. 12(3)(a) start
    requirement: recording of the period of each use, start date and time
    jsonpath: "$.observation_window.start"
    validator: rfc3339_timestamp
    status: MAPPED
    note: governed period opens at a recorded timestamp
  - provision: Art. 12(3)(a) end
    requirement: recording of the period of each use, end date and time
    jsonpath: "$.observation_window.end"
    validator: rfc3339_timestamp
    status: MAPPED
    note: governed period closes at a recorded timestamp
  - provision: Art. 12(3)(d)
    requirement: identification of the natural persons involved in verification of results (Art. 14(5))
    jsonpath: "$.predicate.actor.actor_id"
    validator: nonempty_string
    status: MAPPED
    note: every receipt names the responsible natural person
  - provision: Art. 12(3)(d) constraint
    requirement: service accounts cannot stand in for natural persons
    jsonpath: "$.predicate.actor.is_service_account"
    validator: const_false
    status: MAPPED
    note: "structurally unviolatable: the schema pins is_service_account to false"
  - provision: Art. 12(1) authenticity support
    requirement: recorded events must resist backdating
    jsonpath: "$.predicate.rfc3161_token"
    validator: nonempty_string
    status: MAPPED
    note: RFC 3161 trusted timestamp token, or the literal UNAVAILABLE when the TSA was unreachable
  - provision: Art. 12(1) clock support
    requirement: clock state at record time is disclosed
    jsonpath: "$.predicate.ntp_synced"
    validator: boolean
    status: MAPPED
    note: true only when the host clock was NTP-synced when the receipt was issued
  - provision: Art. 19(1) and Art. 26(6) retention floor
    requirement: Art. 12(1) logs kept at least six months by provider and deployer
    jsonpath: "$.retention_days"
    validator: gte_180
    status: MAPPED
    note: the schema enforces retention_days >= 180 (six months)
```

One discipline note, stated plainly: this profile is an **Article 12 logging
conformance profile**. It is not, and nothing here is, a claim of "EU AI Act
compliance." Applicability, classification, and deployer obligations are
customer-specific. A receipt format can make your logging conformant; it
cannot classify your system.

## Where this sits relative to the market

The monitor/control/police lane for AI agents is heavily capitalized — more
than $330M raised across the five most visible entrants in 2026 alone. That
lane watches agents act. This format records what they were authorized to do
and did, in a form that outlives whoever recorded it. Those are different
problems; the second one starts mattering the day after the first one fails.
For agent platforms with a built-in review feature: such a feature makes a
decision at execution time. Producing a durable, portable, independently
checkable record of that decision is not its stated purpose.

> Codex auto-review decides. a11oy proves. The decision does not survive the
> vendor, the outage, or the auditor.

## What we sell, disclosed

The predicate, the reference verifier, and the conformance profile are open
and free, permanently. SZL sells the control plane above the format:
retention architecture, policy, conformance tooling — the part that makes
receipts cheap to issue and complete. If open formats only ever fed
consulting, we would still publish, because the moat we intend to defend is
*whose receipt an independent auditor trusts after the vendor is gone* — and
that is decided by adoption and conformance, not by secrecy.

Links: specification • reference verifier • conformance YAML • self-audit
receipt (verdict: INCOMPLETE, dated 2026-08-30) • 90-second recorded demo.

---

## Appendix A — Hacker News comment version (5 bullets)

- We published `szl.dev/GovernedAction/v1` today: an open in-toto/DSSE
  receipt format recording what an AI agent was authorized to do, what it
  did, and whether the required evidence exists. Spec, reference verifier,
  Article 12 logging conformance YAML, our own signed self-audit receipt —
  one dated event.
- Two rules do the work: missing evidence evaluates to INCOMPLETE, never
  PASS; and a valid signature proves integrity, not truth. The verifier keeps
  those separate and runs fully offline — no vendor contact, ever.
- Run the verifier against our own self-audit receipt: it returns INCOMPLETE,
  and we published it anyway. A format whose issuer's first receipt is its
  own failure state is the format making the completeness claim in public.
- Any org — including competitors — can emit conformant receipts today; no
  license, no call. The bet: the moat in agent governance is whose receipt an
  independent auditor trusts after the vendor is gone, and that is won by
  adoption, not secrecy.
- We sell the control plane above the format (retention, policy, conformance
  tooling). The format itself is free. IAM says what an identity may access;
  a11oy proves what an AI agent was authorized to do, what it actually did,
  and whether the required evidence exists.

## Appendix B — LinkedIn version (3 sentences)

Today we published GovernedAction/v1 as an open standard: signed,
offline-verifiable receipts proving what an AI agent was authorized to do,
what it actually did, and whether the required evidence exists — spec,
reference verifier, and Article 12 logging conformance profile included. Our
own self-audit receipt verifies INCOMPLETE, and we published it anyway,
because a receipt format that fails upward is not a receipt format. Any
organization, competitor included, can start emitting conformant receipts
today — the format is free; we sell the control plane above it.
