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

Set `SZL_ANATOMY_BROWSER_ARTIFACT_DIR` to retain screenshots and the detailed fixture report. The [focused workflow](../../.github/workflows/anatomy-observation-contract.yml) retains its own JUnit and browser artifacts and checks the existing source-wiring assertion without starting production modules. It retains native CI run metadata and runtime observations separately from this local record.

## Native CI observation

[Run 43987910345, job 133720730345](https://github.com/szl-holdings/a11oy/actions/runs/43987910345/job/133720730345) completed successfully at 2026-11-17T00:30:09Z. GitHub records candidate head `733b717a523e146f7fb9db33cfb5fdc34400c22a`. Its JUnit records 181 passing cases (74 backend and 107 browser), zero failures/errors/skips, and 53.750 seconds. The browser was Chromium 151.0.7922.34; the report records 632 intercepted GET requests, zero unexpected requests, and zero page JavaScript errors.

[Artifact 14286032747](https://github.com/szl-holdings/a11oy/actions/runs/43987910345/artifacts/14286032747), `anatomy-observation-43987910345-1`, contains JUnit, the browser report, and 15 screenshots. The downloaded 1,016,425-byte ZIP independently hashed to `0433f92c41c7b2cfdff8df217b984e52713c4d710d8561e88bcd879d5c0ab1b2`, matching the artifact metadata and upload log.

The report binds application module `e1c562c63ce0a3d53008912887954215e014974e419f38ac78484ae447d89f56` and vendored Three.js `521c5b5716a83cdd8eeed7aa861d7ff2c5e1ed65e3f83a11a4b4752e276aa284`. It does not bind every checkout or test file. The workflow uses the pull-request checkout default; GitHub's candidate-head metadata is not a separate assertion that this was the checked-out merge commit. This is historical offline fixture evidence for that run; subsequent candidate heads and deployment still require their own checks.

The API and browser contract is documented in [ANATOMY_OBSERVATION_CONTRACT.md](../../docs/architecture/ANATOMY_OBSERVATION_CONTRACT.md). Research, attribution, and future design hypotheses are in [the architecture review](../../docs/frontier/2026-11-16-observation-action-architecture.md).
