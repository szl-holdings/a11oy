<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- (c) 2026 Lutar, Stephen P. - SZL Holdings -->

# Anatomy observation validation

The adjacent [record](offline-validation.json) retains the final local validation result for the legacy seven-page Anatomy repair. It binds the tested source and tests by file SHA-256. It is an offline test observation, not a runtime attestation, deployment approval, signature verification, or operational-readiness claim.

The backend suite passed 74 tests, including real registered routes, authorization before body consumption, namespaces, bounded expiry, unchanged read-side state, and two AST-isolated actual-source compatibility cases. The browser suite passed 107 tests in Playwright-managed Chromium 156.0.8078.4. Its 632 intercepted requests were all GET; no unexpected requests or page JavaScript errors were observed.

The browser cases cover all seven current server-default envelopes, prior-success to failure transitions, resource bounds, hostile text, page restoration, desktop and 360px layouts, real picking after scroll, and all 16 routes in the maximum permitted response. Root visually inspected refreshed desktop body and narrow 16-route screenshots. The local capture produced 15 screenshots; their hashes are retained in the record.

Reproduce from the repository root with the existing dependency locks and an installed Playwright Chromium:

```bash
python -m pip install --require-hashes -r .github/requirements/ci-rag.txt -r .github/requirements/platform-candidate-browser.txt
python -m playwright install chromium
python -m pytest -q tests/test_anatomy_3d_observation_contract.py tests/test_anatomy_3d_browser_contract.py
```

Set `SZL_ANATOMY_BROWSER_ARTIFACT_DIR` to retain screenshots and the detailed fixture report. The [focused workflow](../../.github/workflows/anatomy-observation-contract.yml) retains its own JUnit and browser artifacts and checks the existing source-wiring assertion without starting production modules. Its results bind a native CI commit and runtime separately from this local record.

The API and browser contract is documented in [ANATOMY_OBSERVATION_CONTRACT.md](../../docs/architecture/ANATOMY_OBSERVATION_CONTRACT.md). Research, attribution, and future design hypotheses are in [the architecture review](../../docs/frontier/2026-11-16-observation-action-architecture.md).
