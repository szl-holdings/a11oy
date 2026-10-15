<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Python command-centre renderer workcell

## Plan recorded before implementation

Scope: migrate the existing `/command-centre` and `/a11oy/atelier` page owner from a static HTML asset to escaped, dependency-free Python components. Preserve all existing operator form IDs, browser action behavior, routes, provider and authorization boundaries. Add server-rendered ownership and Ayllu inventory-only/FOLD disclosure from the existing public-estate contract; no new registry, publisher, credential, datastore or action route.

Files: `routers/command_centre.py`, new `routers/command_centre_view.py`, existing command-centre stylesheet if required, route/renderer tests and `docs/ATELIER_COMMAND_CENTRE.md`. Existing `index.html` is retained as a non-serving migration reference. Root integration owns the full-product/browser-witness source-owner change and CI wiring.

Success criteria: deterministic rendered bytes with source/input provenance; no provider, database, signer or network work in page rendering; strict fixed-origin links; hostile strings escaped; malformed/oversized/duplicate public binding fails closed without echoing contents; no private inventory projection; Ayllu remains INVENTORY_ONLY, governedKeep=false, disposition FOLD. Existing controls and all existing navigation entries survive. Bound browser proof remains required before deployment.

## Evidence boundary

Python owns the HTML/component rendering after this slice. CSS and the existing JavaScript action client remain browser assets. This is not an all-Python interaction migration, a new authentication boundary, a council execution integration, model qualification or whole-product production approval. No paid calls, resource creation, repository consolidation or deployment is part of this workcell.

## Verification

- Baseline: `/tmp/owner-preview-review-venv/bin/python -m pytest tests/test_command_centre.py -q` — exit 0, 33 passed, one existing Starlette TestClient deprecation warning. The default `python3` attempt could not run tests because pytest was absent; it is not counted as a test failure or a pass.
- First implementation checkpoint: `/workspace/.venvs/a11oy-production/bin/python -m pytest tests/test_command_centre.py tests/test_command_centre_view.py -q` — exit 0, 111 passed, same warning. One earlier intermediate run retained the old static-asset error-code assertion and failed 1/33; the assertion was updated to the new source-owner failure code while retaining HTTP 503 and adding the same manifest failure check. No source-integrity gate was removed.
- Frozen workcell checkpoint: the same focused command — exit 0, **113 passed**, one existing Starlette warning, after adding inline-script refusal and the canonical contract/renderer Docker source regression. `git diff --check` also exited 0. This is local source verification, not installed-image or live-source proof.
- Coverage includes exact page owner/model digest, all legacy form IDs/control contracts/navigation, every retained JavaScript element lookup, disabled-before-readiness submit controls, escaped text/attributes, rejected inline/foreign script construction, strict origins/paths, duplicate/non-finite/oversized/malformed JSON, inventory-only classification and topology-overlap refusals, public projection minimization, source-file hashes and GET network refusal.
- The existing JavaScript action client is unchanged. No external mutation, authentication, signature, backend inference or production capability is added by the rendered page.
- Independent review identified that `static/shared/public-estate-contract.v1.json` was not an image COPY input. Root integration added the explicit COPY; the renderer suite now uses the existing copy-sync parser to require that explicit public-contract input and image coverage for the Python renderer. Without that integration the ownership section would correctly be UNAVAILABLE in the container.
- Root integration also owns the full-product byte witness update, isolated browser capture and CI wiring. Screenshots, protected-source qualification, publication and live verification remain pending at this checkpoint. No deployment or completed production claim is made here.

## Integration checkpoint

- Canonical public-contract bytes are now included in the existing shared-static Docker COPY layer. Explicit addition/destination tests preserve all historical allowlist baselines and the unchanged 117-layer ceiling.
- The real-product middleware guard compares exact `page_bytes()` output. Renderer and browser-witness tests are included in CI; the new browser job requires a clean exact source revision and retains local evidence.
- Independent local integration run: 308 tests and 183 subtests passed (one existing TestClient warning), before the final two WebSocket refusal regressions. Final witness helper suite: 34 passed. Combined UI/backend/auth/evaluation run earlier passed 666 tests and 483 subtests, with one existing Windows-only skip and six existing deprecation warnings, using the CI-documented isolated database paths.
- Hardened precommit browser witness: 12 combinations, eight screenshots, zero browser errors/traffic violations, Chromium 151.0.7922.34 with Playwright 1.62.0. All evidence is labelled dirty-source/local-presentation only. Final committed-source verification is required separately; no deployed production claim is made by this record.
- Final combined local run on the current base and final implementation: 707 passed, one existing Windows-only skip, 483 subtests passed, six existing deprecation warnings. The retained JUnit report is local setup evidence; it contains no remote deployment or model-execution result.
