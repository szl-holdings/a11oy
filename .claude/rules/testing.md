<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Rule: testing

## Rules

- **Run the surface test for any route you touch.** Route surfaces have dedicated
  `test_*_surface.py` suites at the repo root (e.g. `test_governance_surface.py`,
  `test_energy_surface.py`, `test_pnt_surface.py`). Run the one that covers your change.
- **Never delete a demo-critical route registration.** `tests/test_demo_critical_routes.py`
  guards `/console`, `/frontier`, `/governance`, `/orbital` and the `/api/a11oy/v1/*` set.
  If you add a demo-critical route, **extend** that test's list — do not weaken it.
- **Add a golden case for any new governance verdict.** A new deny/allow path needs a test
  asserting the verdict (including a doctrine-violation negative that must be DENIED).
- **Keep CI green honestly.** Do not relax a gate, skip a test, or mock away a real check to go
  green. A truthful failing test that surfaces a real gap beats a fabricated pass.
- Pre-existing failures are documented in `AGENTS.md` → *Running tests*; don't claim a new pass
  count that includes those.

## Build & test commands

See `AGENTS.md` → *Build & Test* for the full per-package command table and the symlink setup
required for `__tests__/`.
</content>
