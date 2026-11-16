<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Hugging Face inventory source reconciliation candidate

**SOURCE_REVIEW_REQUIRED ? unaccepted draft source.** This patch makes the previously documented reconciliation reviewable and testable. It grants no qualification or production authority and performs no provider, visibility or support-discussion write.

Protected-main base: `ac68b78415eecd21cf47f09fa725ed8a6e72fc78`. Branch: `review/hf-inventory-source-reconciliation-20261116`.

The immutable evidence remains [PR #3575](https://github.com/szl-holdings/a11oy/pull/3575), specifically [the dossier at 014d436ce7e0e3cd7b03fa6ac5a13dbafb95ab15](https://github.com/szl-holdings/a11oy/blob/014d436ce7e0e3cd7b03fa6ac5a13dbafb95ab15/docs/reviews/hf-inventory-reconciliation-2026-11-16.json). Its JSON SHA-256 is `093817340533b712e866ea44b889d22c99e4aa4ac3afde4ade6a78fb6ca73efa`. That dossier and branch are unchanged by this candidate.

Candidate record: [hf-inventory-source-candidate-2026-11-16.json](hf-inventory-source-candidate-2026-11-16.json), exact SHA-256 `ca735c76760630ffb991a0b01ff2882a973f118ba17bb0c49d0868989b0f631c`. It includes source-file byte bindings, the guarded collection report, exact governed transitions, invariants and validation results.

## What the candidate changes

The native collector wrote a fresh candidate to a temporary output first. Before any canonical candidate file was replaced, every governed/gated difference was checked against the three exact old/new transitions in the immutable dossier. The set matched exactly; no unreviewed governed change was accepted. No count or repository revision was hand-edited into the generated manifest.

Native observation: `2026-11-16T23:22:14Z`. Counts: **147 public model repositories, 88 datasets, 23 Spaces and 14 native kernels**. The native live check subsequently returned `CURRENT` with no changed rows or top-level fields. These are repository membership observations, not trained-model totals or serving qualification.

| Source area | Proposed behavior |
| --- | --- |
| Canonical keep policy | Adds a bounded observational pending-hold section for Constellation only; all ten keepers and all prior text remain unchanged. |
| Public contract | Removes twelve verified-private stale public classifications, retains Sentra as observed public, and adds Constellation as inventory-only with a pending-owner-decision disposition. All history, topology, truth, authority and version fields remain unchanged. |
| Renderer | Requires the exact canonical hold identity/state/source, its matching historical record, its inventory-only row and false keeper status. Renders pending hold separately from FOLD and org-card classifications. |
| Command-centre consumer | Accepts only that narrow held disposition and source history while rejecting promotion through public bodies, supporting systems, laboratories or internal-engine bindings. Continues to project only canonical origins and README, with no hold or private metadata exposure. |
| Model support | Adds exactly the sixteen published proposed rows: thirteen weight-bundle and three adapter-bundle metadata assessments. All report NO_PROVIDER_MAPPING; all 131 existing rows, unmatched prior requests and authority fields are preserved. |
| Derived outputs | Regenerates the native manifest, stage matrix, all three public fragments and model pretraining projection through the existing generators. |
| CI | Adds the pending-hold regression module to existing public-estate and reviewed-inventory checks; no permission or publication trigger expansion. |

## Governed revision boundary

The revision-class policy, release/qualification records and routine refresh guard are byte-unchanged. Only the following dossier-reviewed observed heads advance in the unaccepted candidate:

| Model | Before | Candidate |
| --- | --- | --- |
| `SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent` | `d3c0b7e7a3a7242e6cd279bcd8e0bc67c16d7ce2` | `aa357f2a7849bc5f42991d7382f3ae2cffadca53` |
| `SZLHOLDINGS/szl-lambda-gate` | `083d760878a3bd2e77cff5ab5c3c348327b0de47` | `613c4a3e28c72c182399b888ffca6693fab3dc8e` |
| `SZLHOLDINGS/szl-nemo` | `37890b4504cdb11590f7a9fb9ee5054261206e30` | `130cce3ae8c7a047b065749c2604aa37e751c041` |

All three remain `GOVERNED_EXACT` and preserve their gating. Existing model assessments and release qualifications are not refreshed or promoted by these inventory pins. The unchanged routine preparer still returns `SOURCE_REVIEW_REQUIRED` when comparing protected-main source to this candidate. A synthetic subsequent head change for each model also remains rejected. Acceptance of this source review is separate from those routine checks.

## Held-public boundary

The pending-hold parser admits exactly the structured Constellation identity, `OWNER_VISIBILITY_DECISION_PENDING` state and recorded November 15 batch-2 hold source. Plain/quoted duplicate keys, malformed/nested keys, unsupported IDs, extra holds, altered states and alternate historical sources fail closed. Comments cannot supply authorization.

The held row is mandatory and cannot be labeled FOLD, KEEP, ORG_CARD or generic HOLD. It cannot become a keeper or topology binding, even by deleting the inventory-only row and moving the identity to a different category. Unknown observed Spaces and missing public membership still fail exact coverage. The three public fragments explicitly state that the inventory hold grants no runtime qualification or authority to change visibility.

The twelve private rows are removed only from the measured public classification. Historical folds are retained exactly. The older IMMUNE hold is not reused as current authority. Sentra remains represented as public because it was observed public.

## Verification

| Suite/check | Result |
| --- | --- |
| `public_estate_workflow_exact_suite` | PASS ? 49 tests, exit 0 |
| `native_collector_offline` | PASS ? 36 tests, exit 0 |
| `gated_inventory_boundaries` | PASS ? 14 tests, exit 0 |
| `public_membership` | PASS ? 52 tests, exit 0 |
| `wsl_revision_classes` | PASS ? 26 tests, exit 0 |
| `wsl_routine_refresh_gates` | PASS ? 101 tests, exit 0 |
| `wsl_command_centre_and_model_sources` | PASS ? 152 tests, exit 0 |
| `stage_check` | PASS ? check, exit 0 |
| `alignment_check` | PASS ? check, exit 0 |
| `model_projection_check` | PASS ? check, exit 0 |
| `catalog_check` | PASS ? check, exit 0 |
| `native_live_inventory_check` | PASS ? check, exit 0 |

The Linux suites ran without skips in an isolated WSL Ubuntu environment using repository-pinned pytest/FastAPI/Starlette/httpx/jsonschema dependencies. This resolved host limitations in the initial Windows symlink tests. The final 152-test pytest run emitted one upstream Starlette TestClient/httpx deprecation warning. No test or guard was disabled to obtain a passing result.

Independent source invariants compare against exact protected-main Git object bytes. They establish equality of every existing catalog row and unmatched request, unchanged catalog authority, unchanged contract history/topology/authority/version, exact preservation of all prior keep-policy text outside the new bounded section, and unchanged Unicode lines in renderer/consumer source. All sixteen additions also compare equal to the exact published proposed rows, beyond schema validity alone.

## Remaining gates

This remains an unaccepted source candidate. Required review and CI, source merge, canonical publication and external profile/proof binding verification remain separate steps. Organization profile regeneration must bind exact merged manifest bytes, source revision and Git blob; the candidate does not publish that external binding.

Constellation public/private ownership remains pending. The existing `hf_consolidate_fleet.py` is unchanged and does not enforce inventory-only holds; if separately run it would still treat Constellation as a non-keeper. The candidate introduces no operational hold guarantee and does not dispatch consolidation. That behavior needs its own reviewed change before relying on this hold during a fold operation.

Protected-main publication lag is tracked separately by the root task. Local source parity and `CURRENT` inventory evidence do not establish live runtime publication, model inference or deployment readiness.

The preparation phase creates only this isolated source diff and local review commit. It does not approve or merge the patch and performs no provider publication.
