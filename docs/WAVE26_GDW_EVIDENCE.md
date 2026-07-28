<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Wave 26 GDW evidence and upgrade gates

This ledger separates implemented contracts from claims that still need
measurement. A green check is permitted only after the named command is
executed against the exact reviewed source and its output is retained.

## Release-gate evidence

| Gate | Command or observation | Required result |
|---|---|---|
| Python contracts | `python -m pytest -q web/packages/a11oy-core/py/szl_gdw/tests tests/test_gdw_surface.py` | all selected tests pass |
| Registry parity | `python tools/check_surface_registry_sync.py` | identical ordered registries |
| Operator JavaScript | `node --check web/packages/a11oy-core/py/szl_gdw/static/app.js` | exit 0 |
| 3D surface JavaScript | `node --check static/3d/surfaces/gdw.js` | exit 0 |
| Lean endpoint/disposal hooks | `lake env lean Lutar/LambdaAttnRes.lean` and `lake env lean Lutar/GovernedWorkspace.lean` | both compile with no `sorry` |
| Assembled routes | `pytest -q tests/test_demo_critical_routes.py tests/test_gdw_surface.py` | `/gdw` and every GDW API route precede catch-alls |
| Docker source completeness | repository Docker COPY guard | package and `gdw.js` are in the image |
| Protected delivery | required GitHub checks on the exact PR head | terminal success; no bypass |

## Persistence proof obligations

The suite must observe:

1. session creation writes state plus a `session.create` receipt atomically;
2. an accepted step advances exactly once and binds `state_before` and
   `state_after`;
3. rejection and kernel exceptions preserve the prior state;
4. replay of the same idempotency key returns the stored response without a
   second receipt;
5. reuse of that key with a different request is rejected;
6. reopening the database recovers the same state and verifies the receipt
   chain;
7. tampered state, DSSE, receipt hashes, or chain links fail verification;
8. status/session/receipt/telemetry GETs do not alter state or receipt counts;
9. an absent required mount exposes honest `UNAVAILABLE` state and refuses
   writes.

Signing follows the shared `szl_dsse.sign_khipu_receipt` contract. When no
configured private key exists, the envelope must say `signed: false`, contain
no signature, and carry the canonical `UNSIGNED` honesty text. An unsigned
receipt remains an auditable hash-chain record, not cryptographic identity
proof.

## Experimental claim upgrade plan

No performance claim is authorized by this change. A future upgrade from
`MODELED` requires a separate, preregistered experiment:

1. pin dataset snapshot, model, optimizer, scheduler, seeds, code SHA,
   environment, and hardware;
2. compare the baseline aggregator and Λ-AttnRes with parameter-matched runs;
3. retain raw loss curves, evaluation outputs, wall-clock data, peak memory,
   and energy-meter provenance;
4. run at least five seeds and report uncertainty and failed runs;
5. publish exact-source receipts and independent reproduction instructions;
6. review public wording separately from the code PR.

Until that sequence closes, the UI and API must keep training, quality,
hardware, energy, and performance as `UNAVAILABLE`.
