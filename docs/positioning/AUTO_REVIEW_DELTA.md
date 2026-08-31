# Codex auto-review vs a11oy — the delta, committed

Truth state of this document: VERIFIED as of 2026-08-30 for the configuration
facts (OpenAI shipped auto-review; dates as found in-thread); UNKNOWN for any
vendor capability not publicly documented. Competitive-copy discipline per
CANON section 6: we say "not its stated purpose"; we never say "has no logs".

Locked positioning line (CANON section 6, verbatim):

> Codex auto-review decides. a11oy proves. The decision does not survive the
> vendor, the outage, or the auditor.

Codex auto-review real config: `[auto_review]` with `enabled`,
`reviewer_model`, `block_on_severity`; a pre-execution reviewer agent
evaluates elevated-permission actions (sandbox escalations, network requests,
permission prompts, side-effecting app/MCP calls). Defaults: no network,
workspace-write only.

| # | Dimension | Codex auto-review (as shipped) | a11oy | Why it matters |
|---|-----------|-------------------------------|-------|----------------|
| 1 | Stated purpose | Pre-execution review of elevated-permission actions (sandbox escalations, network requests, permission prompts, side-effecting app/MCP calls) | Durable signed evidence of what an agent was authorized to do, what it did, and whether the required evidence exists | Different jobs: a reviewer decides, a recorder proves |
| 2 | Configuration surface | `[auto_review]` with `enabled`, `reviewer_model`, `block_on_severity` | Typed policy rules with evidence obligations and a retention profile | A decision threshold is not an evidence policy |
| 3 | Output artifact | An allow/deny decision at execution time | A signed in-toto ITE-6 attestation carrying the `szl.dev/GovernedAction/v1` predicate | A decision is not a record |
| 4 | Offline verification | Not its stated purpose | Reference verifier runs fully offline; no vendor contact | An auditor must not need the vendor online |
| 5 | Evidence obligations | Not its stated purpose | Obligations accumulate across all matched rules; missing evidence means INCOMPLETE, never PASS | Completeness is enforced in code, not in prose |
| 6 | Retention | Not its stated purpose | Retention architecture with an Article 12 logging conformance profile; 180-day floor | Evidence must outlive the incident |
| 7 | Time integrity | Not its stated purpose | RFC 3161 token field and NTP-sync state recorded on every receipt | Anti-backdating is a receipt field, not a promise |
| 8 | Redaction safety | Not its stated purpose | Salted-hash redaction commitments on every redacted field | Redaction must not destroy exculpatory evidence |
| 9 | Actor model | Reviews agent and tool calls | Receipts name natural persons; `is_service_account` is structurally false | Art. 12(3)(d) posture, enforced by the schema |
| 10 | Side-effect taxonomy | Elevated-permission categories | Four never-collapsed classes; most restrictive wins; IRREVERSIBLE always requires human approval | Blast radius is priced per action |
| 11 | Portability | Vendor-scoped | CNCF-governed envelope; predicate and reference verifier are open | Receipts must verify after the vendor is gone |
| 12 | Failure semantics | `block_on_severity` thresholds | Default DENY; signature is not truth; replay is non-mutating | Failure modes are specified, not implied |

## Seeded gate test (delete in Week 1)

This footnote deliberately contains the banned compliance phrase — "EU AI Act
compliant" — so that tools/lexicon_gate.py fails on a fresh clone and proves
the gate has teeth. The canonical banned-phrase list lives only in
tools/lexicon_gate.py; docs must reference it by pointer, never by quoting.
Week 1 task: delete this footnote; lexicon_gate then goes green. Approved
wording for the concept: "Article 12 logging conformance profile".
