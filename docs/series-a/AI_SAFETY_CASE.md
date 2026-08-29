# AI safety case (slice)

**Status:** MODELED for the estate. LIVE for this vertical slice.

## Claim

An operator can run one consequential-shaped tool call and observe that governance is inside the execution path.

## Controls in this slice

1. Deny by default.
2. Prohibited list includes production.write, unsloth.codex_bridge, huggingface.push.
3. Write budget is 0.
4. Side effect class NONE for every allowed fixture.
5. Fail-closed demo tool (`fixture.deny_demo`) is denied after listing, so the deny path is visible.
6. Replay of the same idempotency key does not re-invoke.
7. Lake ACK is never synthesized. PENDING_SYNC is the honest state when Hub write is UNAVAILABLE.
8. Calibration plane is proposal-only.

## Out of scope (do not claim)

- Production ATO / FedRAMP
- DSSE-LIVE cosign identity in this browser session
- Λ uniqueness as a theorem
- Universal safety
- Customer adoption
