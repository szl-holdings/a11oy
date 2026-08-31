# PRESS ONE-PAGER — GovernedAction/v1

**For immediate release — 2026-08-30**
**Contact: [[stephen@…]] | SZL Holdings | a-11-oy.com / a11oy.net**

---

## What happened

SZL Holdings today published `szl.dev/GovernedAction/v1` as an open standard:
a receipt format recording, for each action an AI agent takes, what the agent
was authorized to do, what it actually did, and whether the required evidence
exists. Published together, as one dated and independently verifiable event:

- the specification (written to RFC 2119 discipline, normative JSON Schema);
- an open reference verifier that runs fully offline — no vendor contact;
- an Article 12 logging conformance profile in machine-readable YAML
  (11 mapped entries, 180-day retention floor);
- SZL's own signed self-audit receipt — **whose verdict is INCOMPLETE,
  published deliberately**.

The format is built on the in-toto ITE-6 attestation framework (a
CNCF-governed project) with DSSE signing.

## One-line position

> IAM says what an identity may access; a11oy proves what an AI agent was
> authorized to do, what it actually did, and whether the required evidence
> exists.

## Who it is for

- VP of Engineering / VP of Platform and CISOs at companies deploying AI
  agents into business workflows — especially those with EU Annex III
  exposure, where automatic-logging obligations under Article 12 of
  Regulation (EU) 2024/1689 apply. (The format ships an *Article 12 logging
  conformance profile*; it is not, and is not described as, "EU AI Act
  compliance" — applicability and classification are customer-specific.)
- External auditors and regulators who need to check a record without
  entering the platform that produced it.
- Any organization — **including SZL's competitors** — that wants to emit
  conformant, independently verifiable receipts. No license, no partnership,
  no phone call required.

## Why now

Gartner projects **40% of enterprise applications will embed task-specific
agents by the end of 2026, up from under 5% in 2025**. The volume of
consequential agent actions is outgrowing any process built on screenshots,
log exports, and vendor consoles — all of which depend on the vendor's
systems being up, retained, and trusted on the day the question arrives.

## How it works, in four rules

1. **Missing evidence means INCOMPLETE, never PASS** — enforced in verifier
   code, not marketing copy.
2. **Signature is not truth** — a valid signature proves integrity of the
   artifact, not correctness of the claim; the two are never merged.
3. **Receipts name natural persons** — `is_service_account` is pinned to
   false in the schema itself (Article 12(3)(d) rationale).
4. **Records resist backdating and redaction abuse** — every receipt carries
   an RFC 3161 trusted timestamp (or a truthful `UNAVAILABLE`), NTP sync
   state, and salted-hash commitments for every redacted field.

Side effects are classified into four never-collapsed classes — READ_ONLY,
REVERSIBLE, EXTERNAL_VISIBLE, IRREVERSIBLE — with the most restrictive class
winning and irreversible actions always requiring human approval.

## The competitive map

| Company | Round | Date | Scope |
|---|---|---|---|
| Zenity | $125M Series C | Aug 4, 2026 | monitor/control/police AI agents across business environments |
| Obsidian Security | $85M Series D @ **$1.1B** | Aug 4, 2026 | SaaS + AI-agent attack surface |
| Hush Security | $30M Series A ($41M total) | Aug 2026 | machine-identity governance for AI agent credentials |
| WitnessAI | $58M strategic (on $27.5M A) | Jan 2026 | agent/tool inventory, MCP visibility, runtime control, single console |
| JetStream Security | $34M oversubscribed seed | Mar 2026 | ex-CrowdStrike CPO; MCP sprawl, "visibility, design control, enforcement" |
| Braintrust | $124M total ($80M B) | 2026 | AI eval/observability |

The monitor/control/police lane is capitalized roughly 10x beyond a new
entrant's reach. SZL does not compete there. The open question this launch
addresses is different: **whose receipt format an independent auditor trusts
after the vendor is gone.** That question is not answered by better
dashboards; durable, portable, offline-verifiable evidence of agent action
is, for monitoring platforms, not their stated purpose.

Related, on agent-platform review features now shipping (e.g. Codex
auto-review):

> Codex auto-review decides. a11oy proves. The decision does not survive the
> vendor, the outage, or the auditor.

## The open-standard invitation

SZL gives away the predicate, the reference verifier, and the conformance
profile — permanently free — and invites any organization to emit conformant
receipts. SZL sells the control plane above the format: retention
architecture, policy, and conformance tooling. A design-partner program
($50–150K, paid, 6 months, testimonial rights) is open to organizations
deploying agents into workflows with EU Annex III exposure.

**Verification challenge, stated plainly:** download the reference verifier
and run it against SZL's own self-audit receipt. It returns INCOMPLETE — and
that receipt stays public as the standard's first published artifact.

## About SZL Holdings

SZL Holdings is the independent venture of founder Stephen Lutar
(Poughkeepsie, NY), building a11oy, the governed-AI evidence layer: signed,
offline-verifiable receipts for AI agent action.

**Media contact: [[stephen@…]]**

*Assets available: specification text, normative JSON Schema, reference
verifier source, conformance YAML, the 90-second recorded demo, the signed
self-audit receipt, and this fact sheet. All dated 2026-08-30.*
