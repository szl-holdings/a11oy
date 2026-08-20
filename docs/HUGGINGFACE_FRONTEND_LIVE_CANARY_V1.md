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
- Device-width viewport metadata and at least one visible primary interaction target.
- No document-level horizontal overflow.
- Primary controls at least 44 × 44 CSS pixels.
- No uncaught page-script errors.
- Organization deployment metadata matches the exact static-deployment schema, source manifest, and `SZLHOLDINGS/README` target while exposing an immutable revision.
- Space and canonical domain report the exact expected protected source through `env:SZL_GIT_SHA`; agreement on any other SHA fails closed.
- Hugging Face repository/runtime revision is immutable and the runtime is `RUNNING`.
- The organization-card API identifies the static `SZLHOLDINGS/README` Space, exposes an immutable repository revision, and reports `RUNNING`. When the API exposes a runtime SHA, it must equal the repository SHA; absence remains explicitly recorded rather than reconstructed.

Console errors are preserved as evidence but are not automatically promoted to a hard failure because browser extensions, optional fonts, and third-party network policy may create non-contract noise. Uncaught page errors remain fail-closed.

## Execution model

Pull requests run deterministic unit and contract tests only. Protected-main browser execution is sequenced from a successful `Sync and Relock Canonical Hugging Face Space` workflow and binds checkout plus live readback to that run's exact `head_sha`. A dedicated trigger-authority job fails the entire canary workflow when the upstream sync is unsuccessful, is not from `main`, or lacks an immutable commit SHA; the live browser job cannot silently skip into a green workflow in those cases. Schedules and explicit dispatches bind to current protected source. The workflow uploads the JSON report and screenshots, synchronizes one deterministic drift issue only after immutable evidence upload succeeds and current main is rechecked, and fails when a hard gate is not satisfied.

The canary is read-only. It does not update any Space, model, dataset, collection, organization card, hardware allocation, secret, signer key, storage mount, visibility setting, or source branch.
