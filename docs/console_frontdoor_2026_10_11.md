<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Console front door and evidence presentation — 11 October 2026

This change updates the actual `/console` source, `pages/console.html`, its existing
shared header and scoped stylesheet. The local browser checks use labelled fixtures
and intercept all provider and API traffic. They qualify the source presentation;
they do not establish public deployment, provider health, cryptographic policy
coverage, accessibility certification or operational readiness.

## Resulting interface

The Command Center uses a legible opaque graphite hero inside either the dark or
light shell, a restrained atmospheric reflection, a clear pair of actions, and
responsive evidence counters. Secondary catalog navigation follows the receipt
stream. On narrow screens, the existing investor, operator and theme controls move
into the keyboard-operated More menu; their nodes, state and handlers are preserved.
The sidebar uses the approved 24–48 CSS pixel Orbit v2 projection at 40 pixels.

Query deep links and hash subviews survive additive registry loading. Overrides do
not render incomplete registries while the document is still parsing. Ask & Act and
Governed Decision present a local draft editor: a user can prepare, inspect and
approve a local draft, but this neither executes an action nor creates a receipt.
Editing invalidates the review. The independent workspace-health read reports only
what the GDW service states; no authenticated execution UI is implied.

## Evidence and credential behavior

- The energy hero divides the paired cumulative `measured_token_joules` numerator by
  `measured_tokens`. It requires the operator's explicit MEASURED label, a non-stub
  meter, valid paired counts and finite nonnegative joules. Sample aggregates remain
  SAMPLE; incomplete or invalid windows remain UNAVAILABLE. A real numeric zero is
  retained.
- The live-system map keeps anonymous, absent and malformed observations unknown.
  Missing HTTP status and latency are not replaced with 200 or zero. A health score
  is withheld unless its required observations exist.
- Sample receipt verification validates both the transport and decoded SAMPLE
  declarations. It binds the fetched same-origin public key to the sample's stated
  digest and runs the existing DSSE/ECDSA verifier. A verified sample signature does
  not become an operational receipt, an admitted signer policy or verified chain
  inclusion. Unsigned exports, altered payloads and mismatched keys stay explicit.
- The four existing vertical-govern forms take a one-shot credential in a password
  field, clear it before submission, and send it only in an Authorization header to
  a narrow same-origin govern-route allowlist. They do not store it, follow redirects
  or retry a potentially applied action. Network ambiguity directs the user to inspect
  evidence before another attempt.
- Read-only sample-chain observations pass `advance=0`. The draft editor never calls
  the legacy illustrative signing endpoint or the old operator-act route. SLSA copy
  identifies the canonical source declaration as L1; historical evidence does not
  establish current L2/L3 coverage.

## Asset ownership

All five existing KANCHAY consumer roots retain a byte-identical upstream
`SOURCE.json` from the accepted bundle at
[`4309f6fc`](https://github.com/szl-holdings/szl-brand/tree/4309f6fce89179331b0b3ed8c99494e76c5be256/kanchay).
That manifest binds its source to
[`27d12e77`](https://github.com/szl-holdings/szl-brand/commit/27d12e77fc0f9f1a0e5fae8b34adf2380d51d070).
Each local `VENDORED.json` names only the canonical payloads actually installed in
that served root. It does not attest local overlays or uninstalled upstream files.

The independently approved Orbit icon has its own source and SHA-256 record at
`console/assets/szl/orbit-v2/UPSTREAM.json`. It is not retroactively added to the
legacy KANCHAY manifest. Logo geometry and palette primitives are not redrawn.

## Reproducible checks

```sh
python -m pytest -q \
  tests/test_console_surface_scope.py \
  tests/test_console_navigation_accessibility.py \
  tests/test_console_truth_relock.py \
  tests/test_console_governance_truth_contract.py \
  tests/test_landing_audit_fixes.py \
  tests/test_console_evidence_runtime.py \
  tests/test_demo_critical_routes.py
node scripts/test_console_evidence.cjs
CHROME_PATH=/path/to/chromium python scripts/test_console_frontdoor.py --output /tmp/console-frontdoor
CONSOLE_QA_BROWSER=/path/to/chromium python scripts/test_console_focused_theme.py --output /tmp/console-focused
```

The front-door browser suite covers 320, 390, 768, 1280, 1920 and 2560 pixel widths,
both shell themes, text and control containment, 44 pixel hero controls, keyboard
navigation, primary-label contrast in rest/hover/pressed states, hero text contrast
across atmospheric bounds, an opaque reading ground, local draft transitions, editor
contrast, deep links, reduced motion and absence of state-changing requests. It
writes screenshots and file hashes with the observed assertions. The focused shell
suite additionally covers source-labelled empty, malformed and failed responses.

The offline helper tests execute the actual shipped JavaScript, including local
ECDSA signing fixtures and tamper rejection. The test key exists only inside that
process and is never a production identity or a committed key.

## Delivery boundary

The existing `hf-sync.yml` remains the sole automatic writer for the canonical
Space. Its source-admission, maintenance-window, immutable-payload and runtime
checks remain in force. A successful workflow with a skipped deployment is not a
published console. Compare the eventual accepted GitHub source, Space commit,
`/api/build-info` and public asset bytes before recording this interface as live.
