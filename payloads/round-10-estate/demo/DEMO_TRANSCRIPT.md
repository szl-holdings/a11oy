# a11oy Proof Surface — Demo Transcript

Generated: 2026-08-30T23:50:00.755313+00:00
Signing scheme used: `ed25519`

| Step | Check | Expected | Got | Result |
|---|---|---|---|---|
| 1 | authority evaluated before execution | True | True | PASS |
| 2 | ungoverned action defaults to DENY | DENY | DENY | PASS |
| 3 | DENY receipt verifies offline | PASS | PASS | PASS |
| 4 | approved receipt (human, irreversible) verifies | PASS | PASS | PASS |
| 5 | tampered receipt (1 byte) fails | FAIL_SIGNATURE | FAIL_SIGNATURE | PASS |
| 6 | missing evidence reads INCOMPLETE | INCOMPLETE | INCOMPLETE | PASS |
| 7 | service-account approval rejected (Art.12 3d) | FAIL_POLICY | FAIL_POLICY | PASS |
| 8 | IRREVERSIBLE without approval refused | REFUSE | REFUSE | PASS |
| 9 | PENDING_SYNC surfaces unacknowledged frames | True | True | PASS |
| 10 | flight-recorder hash chain verifies | True | True | PASS |
| 11 | every receipt verifies fully offline | True | True | PASS |
| 12 | Article 12 fields: human principal, UTC timestamp, completeness | True | True | PASS |

## Receipts emitted

- `demo/receipts/02-deny.json`
- `demo/receipts/04-approved.json`

## Law summary

- Ungoverned actions default to DENY and still leave a receipt.
- Missing evidence reads INCOMPLETE, never PASS.
- A service account can never satisfy a human-principal approval (Art. 12(3)(d)).
- IRREVERSIBLE actions cannot auto-execute; one flipped byte kills the signature.
- Local durability ACKs honestly and PENDING_SYNC is a visible state.
