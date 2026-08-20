<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Substrate route and action-contract truth packet

**Observed:** 2026-07-25

**Base revision:** `2b3a3dd0254eb37c1a9b17a7c26c015696a18646`

**Scope:** nested 3D asset delivery, undeclared-route refusal, and the operator
action-contract evidence label.

## Outcome

The refreshed base revision already contains the route-order and path-converter
repair. The assembled FastAPI application now proves the complete interaction:

- `GET /static/3d/holographic.html` returns HTML with status 200;
- `HEAD /static/3d/holographic.html` returns an empty body with status 200;
- `GET /static/3d/missing.js` remains a scoped JSON 404;
- an undeclared root file-like path remains a JSON 404 from the soft-404 guard;
- the nested static routes precede the root SPA catch-all.

This branch adds that assembled-app case to protected CI. It does not loosen the
root catch-all detector or permit undeclared SPA fallbacks.

The operator action contract is now labeled **ROADMAP**. The manifest and
receipt-envelope helper are testable, but this repository does not implement an
authenticated, server-side idempotent, durable, operator-approved action
lifecycle. The validator rejects:

- promotion to `verified-runtime` without all four runtime controls;
- author-supplied JUnit or other report-only promotion evidence;
- a qualification program changed in the promotion PR instead of already
  existing byte-for-byte on protected `main`;
- missing, substituted, reordered, or shell-indirected evidence commands;
- removal of the explicit evidence boundary;
- weakened egress, receipt-chain, clean-room, or UDS claim guards.

## Evidence

| Validation | Result |
| --- | --- |
| Action-contract manifest validator | PASS |
| Action-contract negative-fixture self-test | PASS, 24 tests including forged-report, substituted-command, protected-base, pinned-digest, release-payload bypass, and failing-suite cases |
| Runtime-contract and nested-static focused suite | PASS, 21 tests |
| Demo-critical routes and 3D substrate suite | PASS, 57 tests |
| Policy action-envelope test | PASS |
| Focused policy TypeScript check | PASS |
| Changed-file doctrine scan | PASS, 0 hits |
| JSON parsing and Git diff whitespace check | PASS |

The Python suite reports existing FastAPI/Pydantic deprecation warnings. They do
not change the route results above and are not represented as resolved here.

## Evidence boundary

No production deployment, live write, secret use, approval, merge, or receipt
signature claim is part of this packet. No UI changed, so a screenshot is not
applicable. Protected CI and independent authorized review remain required
before merge.
