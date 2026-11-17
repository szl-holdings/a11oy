<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Canonical ORO inspection verification

Date: 2026-11-16; additional verification on 2026-11-17 UTC. Scope: local implementation and integration checks. This record is unsigned and does not attest a production deployment.

## Problem and candidate

At deployed source f6e30e83343674e544af0ad83a03c058d9c9d53b, the existing ORO evidence projection had no canonical runtime caller. The implementation branch began at 2204f596d17a854fba12cd204ab86019bc2e0712. The integration uses the existing canonical Khipu owner and the passive Anatomy v6 summary.

The observation API is /api/a11oy/v1/oro/evidence and its operator view is /oro/evidence. Its schema is szl.oro-evidence-observation/v1. The observation scope is LOCAL_OWNER_INSPECTION; collection time does not establish source evidence freshness. Its status is separate from application readiness, and execution, promotion, and signing authority are false.

## Verified behavior

- Real FastAPI request dispatch resolves the existing owner at request time and performs blocking source reads off the ASGI event loop.
- The Khipu reader emits at most 32 public evidence pointers and explicitly reports a truncated chain boundary. Owner payloads and DSSE signatures do not leave the reader.
- Missing and failed owners are distinguishable from an observed empty owner. Malformed chains discard the projection and return unavailable.
- Anatomy v6 contributes a validated summary, not fabricated v7 topology or signed evidence.
- Repeated reads neither append receipts nor invoke signing. Mutations and unknown descendants stay within the read-only namespace instead of reaching a fallback proxy.
- The browser clears prior handles after HTTP failure, malformed data, HTML fallback, timeout, or display expiry. It checks immutable revision syntax and rejects elevated authority or PROVEN evidence.
- Runtime packaging adds the ORO package while preserving the existing Docker layer ceiling and historical COPY-source baselines.

## Actual backend-to-browser witness

The browser witness served the real oro.evidence_api registrar with Uvicorn. It used a real in-memory Wire F Khipu owner containing two harmless unsigned test receipts, and the actual Anatomy v6 reader against an absent temporary overlay. The JSON response came from collect_observation; there was no intercepted API response.

| Check | Observed result |
| --- | --- |
| Desktop and mobile Chrome | 1440px and 390px passed |
| Successful API state | OBSERVED, two declared handles |
| Direct API reads | Three |
| Successful browser reads | Six |
| Browser reads after removing the real owner | Two; HTTP 503 and cleared handles/counts |
| Khipu node count before and after reads | 2 to 2 |
| Signing calls during reads | 0 |
| Anatomy overlay created by reads | No |
| JavaScript errors / horizontal overflow | None observed |

The fixture proves local integration and read boundaries. It is not evidence of production traffic, signature verification, or estate readiness.

## Regression execution

The final combined run passed 247 tests and 72 parameterized subtests in 91.77 seconds. It includes the assembled canonical application, ORO runtime/API/evidence contracts, Docker packaging, Anatomy read boundaries, v5/v6 page contracts, and the Anatomy loop. The original browser controller suite passed nine tests; the final lifecycle suite described below passes twelve. All processes exited successfully. Existing deprecation and test-return warnings were reported; no tests were skipped or weakened.

The broader run first exposed the Windows invalid-parent-path case, and a source-owner suite exposed an upstream STRUCTURAL-ONLY label outside Anatomy's four-label contract. Both original tests were preserved. The overlay reader now rejects invalid ancestors; the lungs projection preserves source_label while reporting unavailable measurement. Both fixes and their cross-platform regression cases pass in the final combined run.

Commands: python -B -m pytest -q -p no:cacheprovider oro/test_*.py tests/test_oro_operational_v3.py tests/test_dockerfile_layer_budget.py; node --test tests/test_oro_evidence_ui.cjs; python -B -m pytest -q -p no:cacheprovider tests/test_demo_critical_routes.py tests/test_anatomy_read_boundary.py tests/test_anatomy_seed_read_contract.py tests/test_anatomy_v6_page_contract.py tests/test_anatomy_v5_contract.py test_anatomy_loop.py. On the DC Windows host, use a unique explicit pytest basetemp to isolate the session from an unrelated inaccessible shared pytest-current entry.

## Integration with current main

Implementation commit d1d89925abc9562118bd3a2a024ed00059683b1d integrates main revision 6848d7a1f15fe72883cc49bf3172e0e4439a325a. The one packaging-test conflict retained both the existing trace observation addition and the new ORO package addition; neither source baseline nor the layer ceiling was relaxed. After integration, the focused packaging and ORO API rerun passed 26 tests and 33 subtests. Hosted checks validate the final PR revision and remain authoritative for merge.

## Navigation and page lifecycle

The canonical Command Centre manifest and server-rendered page now link to /oro/evidence. Its manifest test preserves the exact surface count and verifies that the added entry grants no execution authority. The focused Command Centre suite passes 34 tests. The combined manifest, renderer and existing browser-witness suite passes 148 tests with one environment failure: Windows raises WinError 1314 while creating the symlink fixture, before product code runs. No test was skipped or weakened. The existing Tests workflow runs that same case on Ubuntu in its GDW authenticated durability and promotion contract job; its Python command-centre local presentation witness job covers the browser tests.

Independent review found that disposing the reader on pagehide left retained DOM evidence without a running expiry or Refresh controller after a back/forward-cache restoration. The view now clears handles when hidden or departed, removes its Refresh listener, and mounts exactly one reader only when the page is active and visible. A disposed pending read cannot repaint or schedule a new expiry after its transport resolves.

The final Node suite passes 12 tests, including repeated persisted pagehide/pageshow events, hidden restoration, listener deduplication, and late transport completion. A real Chromium navigation witness used the actual FastAPI/Khipu/Anatomy path with no intercepted response: returning after owner removal cleared evidence, restored Refresh recovered, node count stayed 2 to 2, signing calls stayed zero, and the overlay remained absent. There were no page errors. This browser run reported persisted=false, so actual browser-cache retention was not observed; the persisted-cache lifecycle is covered by the deterministic event regression.

## Production readback during implementation

At 23:50–23:51 UTC, the live build-info endpoint still reported f6e30e83343674e544af0ad83a03c058d9c9d53b. The service was reachable; the frontier rollup reported NOT_READY with one ready capability and seven blocked capabilities. The storage readback reported an active fenced writer, healthy stores, no active error, and alert=false. These are timestamped observations, not a prediction of later availability.

Production acceptance requires the canonical hf-sync delivery path, a readback of the new page and JSON route at the admitted revision, preserved read-only behavior, and the applicable repository gates. A local or hosted test pass alone does not establish that deployment.

See [the architecture and cited prior art](../architecture/oro-evidence-integration.md) for design sources and the remaining ORO execution contracts.

At 00:12-00:14 UTC on 2026-11-17, a separate canonical publication had advanced the public runtime to e782b24e50c26447a77b8d45ed16f99fc35a6a67. Its copy-set identity was reported through GITHUB_ATTESTED_SOURCE_COPY_SET, storage reported CLEAN with all seven stores OK, and operational readiness remained NOT_READY. The publication workflow was still running at that observation.

Source publication and independently admitted execution are separate contracts. A preceding publisher had completed publication/source checks but refused the subsequent execution handoff because configured HF/boot context referred to an older runtime. The publisher intentionally does not manufacture that admission or replace independently configured execution pins. Follow the established process in [execution readiness](../execution-readiness.md); neither this inspection page nor a Git commit signature supplies execution approval. The separate content-cycle repair in PR #3563 changes barrier hashing and historical reconciliation, not the canonical ORO storage, signer, or admission boundaries.
