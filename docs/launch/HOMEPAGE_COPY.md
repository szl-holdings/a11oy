# HOMEPAGE COPY — a-11-oy.com and a11oy.net

Replacement copy, dated 2026-08-30. Both domains serve this same page.
House style: no hype adjectives, no emojis, truth states labeled. Every
number on this page is either canonical or labeled a hypothesis.

---

## HERO

**Headline:**

# Four questions. One receipt.

**Subhead:**

When an AI agent takes a consequential action in your business, four
questions follow — from your board, your customer, your auditor, your
regulator:

1. **What was it authorized to do?**
2. **What did it actually do?**
3. **Does the required evidence exist?**
4. **Can an external auditor verify the record without entering your
   platform?**

a11oy answers all four with a signed receipt that verifies offline, without
us, without you, without anyone's systems being up.

**Primary CTA:** Watch the 90-second demo
**Secondary CTA:** Run the five-minute test yourself

---

## SECTION — The boundary, stated once

> **IAM says what an identity may access; a11oy proves what an AI agent was
> authorized to do, what it actually did, and whether the required evidence
> exists.**

Your IAM decides who gets in. Your agent platform decides what runs. Neither
of those is a durable, independently checkable record of what was authorized
and what occurred. That record is the product.

## SECTION — The 90-second demo

A recorded run of twelve steps, start to finish, no narration required:

1. **Deny by default** — an action with no allowing rule is denied.
2. **Signed receipt on allow** — an allowed action emits a signed in-toto
   attestation.
3. **Tamper one byte** — alter the receipt.
4. **Offline verify fails** — the signature check catches it.
5. **Remove evidence** — delete one obligated evidence item.
6. **INCOMPLETE, never PASS** — the verifier refuses to upgrade a
   thin record.
7. **Simulate an outage** — cut the remote sink.
8. **PENDING_SYNC survives** — local durability holds; the gap is visible,
   not silent.
9. **Replay without double-execution** — recovery does not re-fire side
   effects.
10. **Article 12 logging conformance report** — generated from the receipts.
11. **Chain integrity** — a dropped receipt between two known receipts is
    detectable.
12. **Redaction commitment check** — a redacted field still binds its
    plaintext.

Ninety seconds. Every step reproducible on your own machine with the open
reference verifier — no account, no call, no credit card.

## SECTION — What a receipt carries

Each receipt is an in-toto ITE-6 attestation (CNCF-governed format) with DSSE
signing, carrying the `szl.dev/GovernedAction/v1` predicate:

- The decision (ALLOW or DENY), the matched rules, and the evidence
  obligations they imposed — signed, so "the policy allowed it" is a checkable
  claim, not a recollection.
- The side-effect class, from four never-collapsed classes: READ_ONLY,
  REVERSIBLE, EXTERNAL_VISIBLE, IRREVERSIBLE. Most restrictive wins;
  irreversible actions always require human approval.
- The responsible natural person. The schema pins `is_service_account` to
  false — records name people, per the Article 12(3)(d) rationale.
- An RFC 3161 trusted timestamp (or a truthful `UNAVAILABLE`) and the host's
  NTP sync state. Anti-backdating is a field, not a promise.
- Salted-hash redaction commitments, so redaction cannot destroy exculpatory
  evidence.
- A retention floor of 180 days, enforced by the schema.

## SECTION — The delta, with discipline

Agent platforms increasingly ship a pre-execution review feature: a reviewer
model evaluates elevated-permission actions before they run. That is a
decision made at execution time. Producing a durable, portable,
independently verifiable record of it is **not its stated purpose**.

> **Codex auto-review decides. a11oy proves. The decision does not survive
> the vendor, the outage, or the auditor.**

A decision is what happened in the moment. A receipt is what you can still
prove after the moment — after the vendor's outage, after log rotation,
after the vendor is gone. Both have their place. Only one of them answers an
auditor.

## SECTION — Pricing (hypotheses, labeled as such)

These are pricing hypotheses, stated up front and updated from real buyer
conversations. They are not validated prices.

| SKU | Price hypothesis (untested) | What it is |
|---|---|---|
| **Verify** | Open / free | The `szl.dev/GovernedAction/v1` predicate, the reference verifier, and the Article 12 conformance profile. Given away — the format moat is adoption. |
| **Control** | $75–250K ARR | The control plane: retention architecture, policy engine, conformance tooling. |
| **Assurance** | $250–750K+ | Assured conformance operations and auditor-facing evidence packages. |

Value-based pricing: you are buying the ability to answer the four questions
under pressure, not seats or tokens.

**Design partners:** $50–150K, paid, 6 months, testimonial rights. The
control plane deployed against your real agent workflows, a conformance
profile mapped to your obligations, and direct roadmap influence. If you
deploy agents into business workflows with EU Annex III exposure, this
program was built for you.

## SECTION — Trust block (dated)

**We publish our own audit receipt. Its verdict is INCOMPLETE.**

Dated 2026-08-30: SZL's self-audit receipt, signed like any other, is
published alongside the verifier. Run it. The signature verifies; the claim
state is **INCOMPLETE** — our own evidence obligations are not fully met
today, and the format we ship refuses to say otherwise.

We publish it anyway because an INCOMPLETE receipt is an audited state, and
a standard whose issuer hides its own gap is not a standard. When the gap
closes, the succeeding receipt goes up. The INCOMPLETE one stays up. The
chain is the point.

*Truth states on this page: spec, verifier, demo — VERIFIED artifacts, linked.
Pricing — hypotheses, labeled. Self-audit — INCOMPLETE, dated, published
deliberately.*

---

*End of homepage copy. No hype adjectives were used; every quantitative
claim traces to CANON or carries a hypothesis label.*
