# Civilian Observatory interface

FACT: This is an isolated React interface for the services-layer civilian observatory, not the parent `web/` application's build. It uses the existing a11oy Python runtime through GET-only same-origin endpoints.

PROPOSAL: Reproduce the shipped interface with:

```sh
npm ci --ignore-scripts
npm run check
npm test
VITE_OBSERVATORY_API_ROOT=/api/a11oy/v1/civilian npm run build
```

FACT: The output is `dist/public`; the canonical runtime copy is `civilian_observatory/static` at the repository root. The dedicated CI contract requires byte parity between that copy and a fresh source build.

DECLARED: This isolated interface requires Safari 16.4+, Chrome 111+, or Firefox 128+, following the [Tailwind CSS v4 browser floor](https://tailwindcss.com/docs/upgrade-guide#browser-requirements). Older browsers are unsupported; this is not a claim that all browser/version combinations were tested. The parent application is outside this interface's scope.

DECLARED: [tailwind-merge v3](https://github.com/dcastil/tailwind-merge) follows v4 utility syntax. Explicit `@source` limits utility discovery to the interface, and PostCSS is a development dependency for emitted-CSS regression parsing, not the Tailwind build integration. The tests retain forced-color focus outlines and the tooltip's variable transform origin.

DECLARED: After rebuilding, copy the exact `dist/public` output into `civilian_observatory/static`, removing only superseded content-hashed files, then regenerate and check `python scripts/build_civilian_manifest.py` from the repository root. Run `python tests/browser_civilian_styles.py` when Playwright and an installed Chromium runtime are available. This optional local regression uses software fixtures only and makes no provider requests.

DECLARED: The contract workflow is configured to run that Chromium regression after source-build byte parity, using Playwright 1.57.0 in a fresh job-local environment following [Playwright's CI setup](https://playwright.dev/python/docs/ci). It retains the screenshot, actual browser version, setup log and test log. An exact-head hosted result is still required; this offline-fixture check is not deployment, provider readiness or qualification of every supported browser.

FACT: The original interface concept takes layout inspiration from [BOb](https://bob.bzzzbx.com/dashboard.html), but copies no BOb code, assets, branding, or business data. Fonts and UI libraries retain their respective package licenses; application dependency versions are pinned in the lockfile.

FACT: The interface does not keep secrets in browser storage, load model weights, or confer action authority through its simulated reviewer switch. Evidence export is unsigned checksum consistency, not identity or truth verification.
