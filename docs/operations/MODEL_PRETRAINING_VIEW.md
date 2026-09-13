# Source-first model preparation in the existing product

The operator has explicitly postponed laptop training until frontend/backend and
GitHub/Hugging Face preparation is complete. This change starts no training,
inference, model download, paid job, publisher or new Space.

## Real call path

The existing `routers.frontier_reads` -> `routers.hf_tooling_evidence.register`
path now invokes `routers.model_pretraining.register` before the SPA fallback.
The existing Tooling Observatory page links to the subview at
`/frontier-tooling/models`. Its same-origin JSON API is
`/api/a11oy/v1/models/pretraining`. All new routes are GET/HEAD only.

The HTML, CSS and JavaScript are served by that Python route group, not a mock
API. Search, artifact-category filters, original observation time, recorded Hub
revision links and declared GitHub source pointers are bound to returned rows.
Unavailable inputs clear the list instead of retaining a false successful result.
There are no train buttons, GPU controls, command execution or credential fields.

## One inventory authority, generated presentation input

`docs/huggingface-ecosystem-manifest.json`, produced by the existing estate audit,
remains the source inventory. It was a 46-entry public model-type snapshot dated
2026-09-10 in the inspected source. Counts are derived, not frozen into the page.
The scope is not a current authenticated public/private organization total.

The product Dockerfile already copies `routers/` and `pages/`, but not the whole
docs directory. `scripts/build_model_pretraining_projection.py` derives the
minimal public model fields into `routers/data/model-pretraining-snapshot.json`.
No separate author list is maintained. The existing HF-tooling CI now checks
exact deterministic equality against the canonical manifest, and changes to
either the manifest or this projection trigger the check. Source edits must
regenerate the derived input explicitly; drift is not auto-fixed during CI.

```sh
python scripts/build_model_pretraining_projection.py --write
python scripts/build_model_pretraining_projection.py --check
python -m unittest discover -s tests -p 'test_model_pretraining.py' -v
node --test tests/model-pretraining.test.mjs
python scripts/test_model_pretraining_browser.py
```

The original full source-manifest SHA-256 is build-derived and reported as such.
The request hashes the actual projection bytes, not the absent full manifest.
Neither digest is a signature, authenticated model lineage, or weight-quality
certificate. Runtime validates schema, exact declared counts/IDs, scope, bounded
JSON, duplicate keys, finite numbers, revision shapes and dates on every read.

`a11oy_model_intel.SERIES_A_CARDS` remains the existing source-pointer subset.
This view does not invent a GitHub mapping from a model name. Missing/ambiguous
mappings remain explicitly unresolved. Source URLs are accepted only under the
SZL GitHub organization; the request calls none of the catalog's network getters.
Metadata categories are inspection hints; files, weights, evaluations and runtime
qualification remain unverified here. A kernel or recipe is not converted into
an LLM merely because it resides in the Hub model namespace.

## Preserved owners and boundaries

Forge retains recipe, model evidence and release-binding authority. A11oy retains
the existing product/runtime publisher. The archived/private Forge Lab is not
recreated or exposed by this change, and the existing Model Inference Lab is not
retargeted. The Tooling Observatory's four archived measurements, original hashes,
API bodies and installed-package metadata checks are unchanged.

This subview does not modify Atelier's older walkthrough, model cards, publisher
source pins, weights, formulas, keys, branch protection or production defaults.
The existing GitHub -> Hugging Face -> product -> proof publication order remains.

## Validation and remaining work

Local testing used the actual source-owned inventory and existing route group:
42 new Python tests, 36 existing HF-tooling tests and 39 JavaScript tests passed.
Local Python was 3.13.5, FastAPI 0.128.2, Pydantic 2.13.4, httpx 0.28.1,
uvicorn 0.48.0 and Node 22.16.0. These are not the pinned production CI versions.

The browser harness defines eight viewport tests and real Python response checks.
The attempted local Chromium run was BLOCKED before page load by
`ERR_BLOCKED_BY_ADMINISTRATOR`; no screenshot, rendered UX pass or accessibility
certification is claimed. Browser policy was not disabled or routed around.
Hosted native CI has its own existing browser test environment and must establish
its result separately. No full A11oy application or production image was run here.

Before calling model preparation fully aligned, complete per-artifact source
ownership and release bindings, current same-scope Hub inventory/file observations,
necessary existing card/publisher repairs, the exact source PR's native checks and
review, canonical publication, and independent served-source/behavior verification.
Until those results exist, this feature remains source-stage preparation, NOT
whole-estate alignment or permission to run the laptop training block.
