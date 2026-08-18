# Hugging Face Frontend Live Canary v1

This canary operationalizes the universal frontend contract against the public organization front door and the canonical A11oy application.

## Surfaces

- `https://szlholdings-readme.static.hf.space/`
- `https://szlholdings-a11oy.hf.space/`
- `https://a-11-oy.com/`

## Viewports

- 360 × 800
- 390 × 844
- 768 × 1024
- 1024 × 900
- 1440 × 1000

## Hard gates

- Reachable HTTP response.
- Safe viewport metadata.
- No document-level horizontal overflow.
- Primary controls at least 44 × 44 CSS pixels.
- No uncaught page-script errors.
- Organization deployment metadata exposes an immutable revision.
- Space and canonical domain report the same GitHub source revision through `env:SZL_GIT_SHA`.
- Hugging Face repository/runtime revision is immutable and the runtime is `RUNNING`.

Console errors are preserved as evidence but are not automatically promoted to a hard failure because browser extensions, optional fonts, and third-party network policy may create non-contract noise. Uncaught page errors remain fail-closed.

## Execution model

Pull requests run deterministic unit and contract tests only. Protected `main`, schedules, and explicit dispatches perform the live browser audit, upload the JSON report and screenshots, synchronize one deterministic drift issue, and fail when a hard gate is not satisfied.

The canary is read-only. It does not update any Space, model, dataset, collection, organization card, hardware allocation, secret, signer key, storage mount, visibility setting, or source branch.
