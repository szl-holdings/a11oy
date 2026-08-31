# Auto-Review Delta — committed comparison

Date: 2026-08-31 · Status: committed positioning, not ad copy.

**Line:** Codex auto-review decides. a11oy proves. The decision does not
survive the vendor, the outage, or the auditor.

| # | Capability | Codex auto-review (shipped) | a11oy GovernedAction/v1 |
|---|---|---|---|
| 1 | Pre-execution evaluation of elevated-permission actions | YES — approval subagent at sandbox boundary | YES — policy evaluation before execution, `evaluated_before_execution` const true |
| 2 | Side-effect classification | sandbox escalation / network / permission prompts / app+MCP calls | four explicit classes, never collapsed: READ_ONLY / REVERSIBLE / IRREVERSIBLE / EXTERNALLY_VISIBLE |
| 3 | Signed tamper-evident receipt per decision | not its stated purpose | YES — ECDSA P-256 over DSSE PAE, hash-chained |
| 4 | Offline verification by a third party | not its stated purpose | YES — stdlib validator + pinned-deps verifier, no network |
| 5 | Evidence obligations with derived completeness | not its stated purpose | YES — missing evidence ⇒ INCOMPLETE, never PASS |
| 6 | Human-principal binding (Art. 12(3)(d) posture) | not its stated purpose | YES — is_service_account const false; api_key auth on a human claim rejected as spoof |
| 7 | Vendor-portable record format | not its stated purpose | YES — in-toto Statement envelope, predicate proposed upstream (ITE-9 draft) |
| 8 | Anti-backdating time anchor | not its stated purpose | YES — ntp_synced + RFC 3161 token required for PASS |
| 9 | Redaction accountability | not its stated purpose | YES — salted-hash redaction commitments |
| 10 | Article 12 logging conformance profile | not its stated purpose | YES — machine-readable, honestly INCOMPLETE at 12(2)(c) |
| 11 | Decision latency / in-line UX | YES — optimized, defaults on for its tier | not our stated purpose — we are the record, not the interlock |
| 12 | Price to the buyer | bundled | control-plane product (pricing: see COMMERCIAL_LEDGER — UNKNOWN, blocks_raise) |

## Discipline
We do NOT claim auto-review "has no logs" or that its decisions "vanish".
We claim record portability and third-party verifiability are not its
stated purpose. Overclaiming against a shipped OpenAI feature is the
fastest way to lose a technical buyer.

## Validation
OpenAI shipping pre-execution review for elevated-permission agent actions
is third-party validation that this control point matters. The gap above
(rows 3–10) is the product.
