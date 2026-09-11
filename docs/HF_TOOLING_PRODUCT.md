# HF tooling: executed Forge evidence → A11oy product

The existing Forge #216 implementation is an actual installed-library evaluation,
not production model qualification. This slice connects its four verified reports
to a Python API and a responsive product page in the existing A11oy application.
No additional Space, framework, database, publisher, model route or billable job.

## Entry points

- Product view: `/frontier-tooling`, linked from `/frontier-now`.
- API: `/api/a11oy/v1/frontier-tooling`.
- Original report: `/api/a11oy/v1/frontier-tooling/receipts/{lane_id}`.
- Allowed lanes: `hub-linux`, `hub-windows`, `trl`, `tau`.

`routers.frontier_reads.register` mounts the new GET/HEAD-only route group before
the existing API proxy and SPA fallback. The existing Dockerfile already copies
`routers/` and `pages/`; it therefore includes the Python module, evidence bundle
and page assets without a new copy rule or a production dependency upgrade.

## Two deliberately separate observations

**Archived evaluation.** Exact Forge source
`74a8a07ced6c6b8697b31b7d0e482c4241d55880`, GitHub run `34484379349`.
Four original nested receipts and ZIP provenance are committed in
`routers/data/hf-tooling-20260910.json`. The API checks a source-defined whole-file
SHA-256 and the four original receipt hashes on every request. A missing,
modified, incomplete or mismatched archive returns 503; stale pass cards are
removed from the view on any failed refresh. No ZIP is fetched on a public GET.

**Current product process.** Distribution metadata is inspected at request time
for Hub, Transformers, Accelerate, TRL and tau-ai. The handler neither imports nor
installs these libraries. `VERSION_MATCH_ONLY` is not exact-source verification;
`VERSION_DIFFERS`, `NOT_INSTALLED` and `UNAVAILABLE` remain visible. The product
source SHA is reported from canonical `SZL_GIT_SHA` and compatible `A11OY_GIT_SHA`
metadata, with conflicts exposed rather than silently selecting a revision, not inferred
from the archived Forge source. A missing SHA remains null.

A package not installed in A11oy does not invalidate its historical Forge
measurement. Conversely, a passing Forge test does not claim that package is
installed, that production uses the adapter, or that a real model was qualified.

## Security and presentation

Source-defined local files only. Bounded archive parsing with duplicate/non-finite
JSON rejection. No credentials, network access, writes, training, provider calls,
model downloads or tool execution in the new handlers. All six authority fields
are false and `productionDisposition` stays `HOLD`. Hash integrity is relative to
reviewed source, not a digital signature. The archived receipts remain unsigned.

Same-origin CSS/JavaScript under an explicit CSP; no third-party scripts, inline
script policy, `innerHTML`, local storage or dynamic external destinations. The
page offers keyboard-operable filters and native detail disclosure, reduced-motion
and high-contrast support, narrow mobile layout, explicit loading/error states and
raw evidence links. The page includes the existing local Flow Shell and its five
journeys, rather than bypassing the estate navigation contract. Refresh observes;
it does not dispatch evaluation or training.

## Verification

```bash
python -m unittest discover -s tests -p 'test_hf_tooling_evidence.py' -v
python -m playwright install --with-deps chromium
python scripts/test_hf_tooling_browser.py
```

The dedicated read-only workflow runs the real Python HTTP application and browser
together, loading the real shared Flow Shell assets from `console/assets`, at 320×568, 375×812, 768×1024 and 1440×900. Success uses the actual local
API; a simulated 503 is used only to test removal of stale successes and recovery.
Shared mobile navigation is exercised by keyboard, including Escape-to-close.
Loaded-page captures and overflow diagnostics are saved before assertions, so
failures preserve useful evidence. A source/file-bound JSON report is written only
after all assertions pass. Artifacts are retained in GitHub Actions.
This local-application browser test is not a production deployment witness.

The initial development container blocked browser access to loopback by policy.
Its HTTP TestClient/unit tests ran, and separate render-only previews were reviewed;
the full browser transport test is assigned to the hosted workflow without trying
to bypass that local policy. Only an observed successful workflow is acceptance.

## Publication and remaining work

Merge only after exact-head CI and normal repository controls pass. The existing
canonical A11oy publisher, not a new workflow writer or manual HF patch, must publish
the merged source. Verify the new page/API and runtime SHA on the existing HF Space,
then on `a-11-oy.com`. Only observed product readback may be reflected as deployment
proof on `a11oy.net`. This document does not assert that deployment has happened.

Authority order: GitHub → Hugging Face → a-11-oy.com → a11oy.net.

The canonical Hub dependency alignment (#2087 / #2092) remains separately owned.
This change does not mass-upgrade purpose-specific pins or conflate UI deployment
with million-token training, GPU throughput, FSDP2/vLLM qualification, private-memory
admission, or production action authorization. Those unmeasured requirements stay
visible in the original reports. Rollback is an ordinary reviewed revert of this
additive page/API/registration change; existing model routes are unchanged.

## Original sources

- https://github.com/szl-holdings/szl-forge/pull/216
- https://github.com/szl-holdings/szl-forge/actions/runs/34484379349
- https://github.com/szl-holdings/szl-forge/pull/216#issuecomment-5619721571
- https://github.com/szl-holdings/a11oy/pull/2092
