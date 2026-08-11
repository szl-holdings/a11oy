# A11oy front-door truth and mobile contract

This contract protects the canonical `a11oy_landing.html` front door.

## Invariants

1. Hash-chain integrity and DSSE signing are separate states.
2. `SIGNED` may be rendered only when persistent signer evidence is active and verification passes.
3. Advisory Λ is Conjecture 1. Its relation to the advisory floor is always neutral and never a pass/fail or green signal.
4. Organization totals are not hardcoded into the front door. Current inventory belongs to canonical live Hub sources or a versioned estate endpoint.
5. Touch targets are at least 44 CSS pixels, monospace evidence wraps safely, and mobile call-to-action groups collapse to one column.
6. Read-only routes never mint receipts.

## Promotion design

`frontdoor-burnlight-apply.yml` is intentionally scoped to the single feature branch `fix/frontdoor-truth-mobile-2026-08-11`. It applies the exact-anchor patch, runs the contract tests, and may push only that branch. It never targets `main`, never force-pushes, and becomes inert after the patch is applied.

`a11oy-frontdoor-truth-mobile.yml` is the permanent read-only PR/main regression gate.

The change is additive and does not alter model weights, datasets, visibility, hardware, secrets, storage, signer keys, or branch protection.
