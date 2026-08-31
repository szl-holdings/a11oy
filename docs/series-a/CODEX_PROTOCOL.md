# Series A execution protocol

Zero-Bandaid Law compiled into an agent prompt. Paste unmodified.

## Ten non-negotiables

1. Inventory before abstracting.
2. Never hardcode metrics or maturity. Read `docs/series-a/claims-ledger.yaml`.
3. Never invent integrations, benchmark results, or model performance.
4. Use a safe fixture tool, never a production write connector, for the first vertical slice.
5. Populate `docs/series-a/IP_RISK_REGISTER.md` before implementing anything resembling Bricklayer policy enforcement.
6. Telemetry is not evidence. Flight Recorder never synthesizes a success event.
7. Canonical home is `szl-holdings/a11oy`. Do not mint a 20th repo.
8. Hugging Face is the artifact registry, not the front door. Do not pin factory. Do not remint Warhacker.
9. Local model endpoints that allow code execution stay localhost-bound with a rotating secret.
10. Unknowns stay UNKNOWN. Unfetchable transcripts are not fabricated.

## Six phases

1. Baseline audit → `docs/series-a/FRONTIER_BASELINE_AUDIT.md`
2. Claims ledger with SNAPSHOT/UNKNOWN degradation
3. Constitution + GovernedToolReceipt types
4. One end-to-end fixture call
5. Evidence explorer + coverage graph render INCOMPLETE honestly
6. Narrative last, and only from the ledger

## Eleven validation gates

1. Every public number has source_command + evidence_artifact + freshness_hours.
2. Stale May 12 metrics are not LIVE.
3. Constitution has 90-day expiry.
4. Deny path is exercised (`fixture.deny_demo` or prohibited tool).
5. ALLOW path uses a fixture with sideEffectClass NONE.
6. Receipt has previousReceiptHash and idempotencyKey.
7. Replay returns the original receipt.
8. lakeSync is PENDING_SYNC until a real ACK.
9. Coverage missing evidence is INCOMPLETE, never a pass.
10. Contradiction score is computed separately from claims.
11. Lexicon is one sentence: **a11oy — governed execution fabric**.
