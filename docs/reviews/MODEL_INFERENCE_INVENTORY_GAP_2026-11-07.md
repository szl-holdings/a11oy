<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Model inventory gap dossier, 2026-11-07

This is a review record for the 33 model repositories that are in
`docs/huggingface-ecosystem-manifest.json` and absent from
`docs/model-inference-support.json`. It does not add support rows, remove
inventory rows, change the coverage check, or select any of the open decisions.

The machine-readable rows, revisions, and citations are in
[`model-inference-inventory-gap-2026-11-07.json`](model-inference-inventory-gap-2026-11-07.json).

## Counts

| Record | Count | Meaning |
|---|---:|---|
| Inventory model rows | 74 | Public inventory at `2026-11-06T02:04:19Z` |
| Support catalog rows | 41 | Unchanged. All 41 have `NO_PROVIDER_MAPPING` |
| Rows in this dossier | 33 | Inventory minus support, exact set |
| Verified inventory observations | 33 | The inventory row, sha, and stage `inventory` |
| Verified inference-admission authority | 0 | No support row and no release binding |
| Verified exclusion authority | 0 | No exclusion record names these ids |
| Proposed hold | 33 | Proposal only. `selected` is null |
| Unverified support rows | 33 | Assessment and provider observation are absent |
| Unresolved decisions | 33 | D01–D33 |

`docs/MODEL_INFERENCE_SUPPORT.md` says the reviewed source covers 48 public
model-namespace repositories. The support file contains 41 and the inventory
contains 74. Those three figures are left as they are.

## What was read

- Inventory row, stage-matrix row, and revision class for each id.
- `model_release/` text for an exact id match. None of the 33 appear there.
- The support catalog, including `unmatched_prior_requests`. None of the 33 appear there.
- A public Hub model overview on 2026-11-07T10:42:00Z. All 33 ids resolved. The overview did not return `sha` or `inferenceProviderMapping`. No weights were downloaded and no mapping URL was fetched.

A public listing, a README digest, an `endpoints_compatible` tag, or a card tag is not inference admission. The default revision class `SOURCE_TRACKED` is the class for an unlisted row. It is not an exclusion.

Four inventory rows carry card self-labels. The same labels were visible on the public overview. They are cited in the JSON and are not exclusion records:

- `SZLHOLDINGS/chakana-r1-candidate`: `proposal-only`
- `SZLHOLDINGS/khipu-abstain-r3-candidate`: `proposal-only`, `not-promotable`
- `SZLHOLDINGS/miniembed-nano-r1-candidate`: `proposal-only`, `research-memory`
- `SZLHOLDINGS/szl-receiptagent-qwen25-1.5b-experimental-20261104`: `experimental`, `not-canonical`

## Missing proof, same four items for every row

1. A dated assessment bound to the inventory sha and the README blob URL recorded in the JSON.
2. A provider-mapping observation, or a recorded failed lookup, from the mapping URL recorded in the JSON.
3. An explicit source-review decision naming the id before it can be added to the support catalog.
4. An explicit exclusion record naming the id, if the reviewer chooses not to add it.

## Decisions

Each decision is unresolved. The proposal on every row is `PROPOSED_HOLD`: leave the inventory row in place and leave the support catalog at its current 41 rows until one of the other two choices is actually made.

| Decision | Model id | Inventory sha |
|---|---|---|
| D01 | `SZLHOLDINGS/KHIPU-R2-estate-sft-v1` | `79c0efc23dbdb7f0a394125f811d0a3bb602b36f` |
| D02 | `SZLHOLDINGS/Nemotron-Mini-4B-Instruct-st` | `2939ccd8e30d19c8209086893b75379dbf3c27b4` |
| D03 | `SZLHOLDINGS/SZL-AncientMath-0.8B-v1` | `344fac66fa7c469b6c2779cbaffca38240a995c2` |
| D04 | `SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent-estate-sft-v1` | `d5e1d0722eeda4a2e0f8a4e5cdadeecf1b53bea4` |
| D05 | `SZLHOLDINGS/SZL-FreeEnergy-0.8B-v1` | `cba180bb76d8880b4098ff458dda4cddb859ce90` |
| D06 | `SZLHOLDINGS/SZL-Khipu-1.5B-estate-sft-v1` | `b4ae083265f2f0a6749af4111162d3582dc4dace` |
| D07 | `SZLHOLDINGS/SZL-Khipu-1.5B-sft-v2` | `15c112a8171b4d6aa6eef09c57d92b35bfd3d9ab` |
| D08 | `SZLHOLDINGS/SZL-Nemotron-Mini-4B-Doctrine-v1` | `decebd8be9255239c1507ebc61159099d38ba6bc` |
| D09 | `SZLHOLDINGS/SZL-Nemotron-Mini-4B-Estate-DPO-v1` | `3b330741a7ecee572a7a51c5a3dd023788da8973` |
| D10 | `SZLHOLDINGS/SZL-Nemotron-Mini-4B-Estate-DPO-v2` | `edd649ffcfae89d0a5b5cc889b5cbe0848336e01` |
| D11 | `SZLHOLDINGS/SZL-Nemotron-Mini-4B-Estate-v1` | `8dd86a98a71d52d24ee23b51ef75ed9b6213c69f` |
| D12 | `SZLHOLDINGS/SZL-Reasoning-0.8B-v1` | `10fb28afe427a988af2e10cafa8dd1c2e555ea63` |
| D13 | `SZLHOLDINGS/SZL-Showcase-Systems-v1` | `31d82d6133f20ad26403d21abfd16950d8e19b11` |
| D14 | `SZLHOLDINGS/SZL-Specialized-Domains-v1` | `f0293f28d7ec45a01c59e40daa93af38e20c308b` |
| D15 | `SZLHOLDINGS/WILLAY-estate-sft-v1` | `4c2430a4f0c4d9459591019dac73ba4c235ceeb8` |
| D16 | `SZLHOLDINGS/brain-navigator-r2-estate-sft-v1` | `f774b4b0b7e3d2a0a640543c95527e932a4e8301` |
| D17 | `SZLHOLDINGS/chakana-r1-candidate` | `73219a8ada0e73ab4216d9e70d730e38455f2425` |
| D18 | `SZLHOLDINGS/chaski-5050-estate-sft-v1` | `0278ef6fb06c622748a1043fa4c7efb9bccc716b` |
| D19 | `SZLHOLDINGS/chaski-estate-sft-v1` | `4ab0cd0b31fa1ec83e3f2ebc7adf4a532514e21d` |
| D20 | `SZLHOLDINGS/chaski-r2-estate-sft-v1` | `6e1f8b6a4461b5a5c3563d207a8a79ea76e5e6c5` |
| D21 | `SZLHOLDINGS/khipu-abstain-r3-candidate` | `492c4a177bf0b4b856aa4d656ff8c561ab1d5f4d` |
| D22 | `SZLHOLDINGS/khipu-r3-estate-sft-v1` | `b3c240a8540254ef294d9fbc320ff442ef31f393` |
| D23 | `SZLHOLDINGS/miniembed-nano-r1-candidate` | `40e0c6ab9511586014457d354c00f05777b34fd1` |
| D24 | `SZLHOLDINGS/oac-ops-health-v2` | `90df75bf58d91ea723128a86d7ed9af57535dbd8` |
| D25 | `SZLHOLDINGS/oac-system-health-v1` | `a99c3ec1157af351fa24da64f3b413620cae07fe` |
| D26 | `SZLHOLDINGS/szl-receiptagent-qwen25-1.5b-experimental-20261104` | `b2ec04727f46314b680ee26366159243924c1f67` |
| D27 | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-dpo-v1` | `4c1a8691e8b6c54b1ab07f55bfd78f627d6a9295` |
| D28 | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-dpo-v2` | `af519f265ff552dd4c47ae3a61b5f62a6f3827d5` |
| D29 | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-sft-v3` | `0340c300052e248367a3407aa493ef72a0da79fe` |
| D30 | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2m-estate-sft-v1` | `8419537ecad5930f022eb89720e92ba18ed6605d` |
| D31 | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3-estate-sft-v1` | `9bde1943e8d60c461391bbcd86ffca340da321a8` |
| D32 | `SZLHOLDINGS/szl-specdecode` | `eaf60eed9e7c385154be9cd63278c161ee1fe18c` |
| D33 | `SZLHOLDINGS/szl1-experimental-estate-sft-v1` | `e821e660b5940cd988307bba4b5c9a29a09605ec` |

Choices for each decision, none selected:

- `ADMIT_AFTER_ASSESSMENT_AND_PROVIDER_OBSERVATION`
- `EXCLUDE_BY_EXPLICIT_RECORD`
- `KEEP_HOLD`
