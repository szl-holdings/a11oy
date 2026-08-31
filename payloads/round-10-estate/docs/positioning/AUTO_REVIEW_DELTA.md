# Codex Auto-Review vs a11oy — the committed comparison

Third-party validation of your control point, gap drawn explicitly.
Replaces paraphrase with verifiable claims. Refresh quarterly.

| # | Property | Codex Auto-Review | a11oy GovernedAction/v1 |
|---|---|---|---|
| 1 | Pre-execution evaluation of elevated actions | Yes — `[auto_review]` config, reviewer model at the sandbox boundary | Yes — TypedPolicyEngine evaluates before execution |
| 2 | Default posture on network + workspace | No network; workspace-write only | Configurable per side-effect class |
| 3 | Approval recorded for elevated actions | Yes — routes through reviewer agent | Yes — execution_gate requires named human for IRREVERSIBLE |
| 4 | Signed receipt per decision | Not its stated purpose | Yes — in-toto Statement + DSSE-style signature |
| 5 | Offline verification by an external party | Not its stated purpose | Yes — OfflineVerifier, no network |
| 6 | Evidence-obligation model per action | Not its stated purpose | Yes — obligations accumulate across all matched rules |
| 7 | Retention tier | Not its stated purpose | Local durability, PENDING_SYNC visible, Article-12 180-day floor |
| 8 | Article 12 field set (human principal, UTC, completeness) | Not its stated purpose | Yes — structurally enforced |
| 9 | Portability across vendors | Not its stated purpose | Yes — open predicate, reference verifier in stdlib Python |
| 10 | Tamper evidence | N/A (decision layer) | One flipped byte kills the signature |
| 11 | Missing-evidence posture | N/A | INCOMPLETE, never PASS |
| 12 | Service-account posing as human approver | N/A | FAIL_POLICY, enforced in code |

## Deck line
**Codex auto-review decides. a11oy proves. The decision does not survive
the vendor, the outage, or the auditor.**

## Sources (update when they change)
- Codex auto-review config: https://developers.openai.com/codex/ (see `[auto_review]` `enabled` / `reviewer_model` / `block_on_severity`)
- Trusted Access for Cyber / Daybreak: https://openai.com/index/trusted-access-for-cyber/
- in-toto: https://in-toto.io/
