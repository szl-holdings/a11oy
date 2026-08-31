# a11oy OUTREACH PLAYBOOK — 20 conversations, one persona, one offer

**Status:** operating document, dated 2026-08-30. House style: no hype, truth
states only. Every number herein is either canonical (CANON) or labeled a
hypothesis. Target: convert 2 of 20 conversations into paid design partners —
a 10% close rate, demanding but honest.

---

## 1. The single buyer persona

One persona for all 20 conversations. No exceptions, no "just this once."

**VP of Engineering / VP of Platform, or CISO, at a company deploying AI
agents into business workflows with EU Annex III exposure.**

Read that as three gates, all required:

1. **Deploying agents into business workflows** — agents that write to systems
   of record, call external APIs, or change permissions in production. Not
   chatbots, not eval sandboxes, not "exploring use cases."
2. **EU Annex III exposure** — the workflows touch (or plausibly will touch)
   Annex III domains, so Article 12 logging obligations are on their horizon
   whether or not they have mapped them yet.
3. **A person who owns the answer** — the individual who will be asked, by
   their board, their customer, or their regulator: what was the agent
   authorized to do, what did it do, where is the evidence? The VP
   Eng/Platform owns the deployment reality; the CISO owns the audit
   conversation. Either is the buyer; both are welcome on the call.

Disqualifiers (say them to yourself before booking): companies with no agents
in production; companies whose only agents are internal dev tools; companies
shopping for a monitoring dashboard — that lane is well served and we do not
compete in it.

## 2. The sourcing pool

Build the 20-name list from: agent-platform customers in regulated verticals,
MCP/server operators with enterprise deployments, portfolio companies of
funds that backed the monitor/control lane (their agents need receipts
regardless of whose console they appear in), and EU-headquartered or
EU-deploying engineering orgs publishing about agent workflows. Founder-led,
warm where possible, cold but specific where not. Every outreach message
references one concrete fact about *their* deployment — a generic pitch is a
Zero-Bandaid violation with an email address.

## 3. The 12 founder-led discovery questions

Ask in roughly this order. The point is to learn, not to demo. The demo is
the close, not the opener.

1. Walk me through the last consequential action an agent took in your
   production environment. Who authorized it?
2. When something an agent did has gone wrong, how did you reconstruct what
   happened? How long did it take?
3. What was the agent authorized to do — and is that authorization recorded
   anywhere, or does it live in someone's memory and a config diff?
4. Does the evidence for that action exist today, durably? If I asked for it
   in six months, would it still be there?
5. **Can an external auditor verify the record without entering your
   platform?**
6. Who has actually asked you that question so far — a customer, a regulator,
   your own counsel, an insurer? Who is most likely to ask next?
7. What happens to your answer if the vendor whose console you rely on has an
   outage, rotates logs, or deprecates the product?
8. How are you classifying agent actions by blast radius today? Can you tell
   me which of last month's actions were irreversible?
9. Do your records of agent actions name the natural persons involved in
   verifying results — or do they name service accounts?
10. Where does Annex III exposure sit in your agent roadmap — mapped,
    suspected, or not yet scoped?
11. What would a record have to look like for your auditor to accept it
    without calling us?
12. If the record existed and verified offline, what would that unlock —
    which deals, deployments, or approvals are blocked today on exactly this
    gap?

Question 5 is the load-bearing one. If the honest answer is "no, the auditor
has to come inside our platform and trust our dashboards," the gap we sell
against is confirmed in the buyer's own words. If the answer is yes, ask to
see it — you have met either a future emitter of conformant receipts or a
very well-run shop, and both outcomes are useful.

## 4. The anti-question

**Never ask: "Would you use a governed inference platform?"**

Reasons, stated once and held to:

- It asks the buyer to design our product. That is our job, not theirs.
- It is hypothetical, so the answer is unfalsifiable courtesy. Every "yes,
  sounds interesting" goes in the ledger as exactly what it is: nothing.
- It presumes the category from the vendor side. The buyer does not buy a
  platform; the buyer buys the ability to answer an auditor. Sell the answer
  to their question, not our architecture.
- It leaks the roadmap. The open standard says everything that needs saying
  about the format; the control plane's shape is learned from discovery, not
  pitched into it.

## 5. The paid design-partner offer

The only commercial instrument in these conversations. One offer, stated
identically every time:

| Term | Value |
|---|---|
| Price | **$50–150K, paid.** Not a free pilot. Money changes the information content of everything the partner says afterward. |
| Duration | **6 months.** Long enough for a real deployment against real agent workflows; short enough that both sides learn the truth quickly. |
| Reference | **Testimonial rights.** Secured in the agreement, not hoped for after. |
| Scope | Control plane deployed against the partner's real workflows; a conformance profile mapped to their obligations; direct roadmap influence. |
| Program exit | **80% conversion AND 3 zero-config use cases.** The program succeeds when at least 80% of design partners convert to paying customers at exit, AND the deployments collectively prove three use cases that work with zero configuration. Both conditions, not either. |

The SKU pricing hypotheses (Verify open/free; Control $75–250K ARR; Assurance
$250–750K+) are stated to buyers as hypotheses and updated from what these
conversations return. Design partners pay under a known scope precisely
because the SKU numbers are untested.

## 6. Conversation mechanics

- **Founder-led, all 20.** No SDR layer, no delegation. The learning is the
  asset; it cannot be intermediated.
- **The 5-minute test, offered live:** run, deny, approve, download,
  disconnect, verify, alter a byte (watch verification fail), remove evidence
  (watch INCOMPLETE, never PASS), inspect the chain — without ever using the
  phrase "governed substrate." If the buyer runs it on their own machine
  after the call, the call worked.
- **Log every conversation** with truth states: persona confirmed
  (VERIFIED/UNKNOWN), question-5 answer, current evidence posture, Annex III
  status, next step. A conversation that produced no learning is marked
  INCOMPLETE, and that is fine — it is an audited state.

## 7. Follow-up cadence

| Touch | When | Content |
|---|---|---|
| 0 | Within 24h | The artifact pack: spec, reference verifier link, self-audit receipt (verdict INCOMPLETE, dated). No deck. The artifacts are the pitch. |
| 1 | Day 7 | One question only: "Did your auditor question survive the five-minute test?" Plus the recorded 90-second demo link. |
| 2 | Day 21 | The design-partner offer, stated in full, with the two remaining slots framed honestly. If the answer is no, ask for the reason in their words — it goes in the ledger. |
| 3 | Day 45 | Close the loop: what we heard, what we changed, and an open door. Then stop. A stopped follow-up is a signal of discipline; a dripping one is spam. |

## 8. The engagement-spacing rule (category creation)

Category creation is not a funnel; it is a metronome. **Plan 3–6 substantive
engagements per cycle, spaced roughly 6 months apart.** Each engagement is
one dated, verifiable event in the open: a publication, a conformance
report, a named design partner going live, a receipt upgrade. Between
engagements, do the work; do not fill the gap with noise. The category is
built by the accumulation of checkable claims over time — the same property
the receipts themselves have. Six months is also long enough for each event
to be independently discovered and cited before the next one lands, which is
what makes a category legible to outsiders rather than loud to insiders.

## 9. What "success" means at conversation 20

- 2 of 20 converted to paid design partners ($50–150K, 6 months,
  testimonial rights) — the immediate commercial target.
- 20 logged question-5 answers — the market map of who can and cannot
  survive an external audit of agent action today.
- Pricing-hypothesis updates from real buyer reactions, replacing
  hypothesis with evidence in the commercial ledger.
- Every rejection reason recorded verbatim. The nos are data; the ledger
  treats them as such.

*End of playbook. One persona, twelve questions, one offer, one cadence, one
spacing rule. Deviate from any of them in writing, with the reason logged —
or not at all.*
