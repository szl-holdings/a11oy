<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Model inventory gap observations, 2026-11-07

The 33 model repositories that were in `docs/huggingface-ecosystem-manifest.json`
and absent from `docs/model-inference-support.json` now have a dated assessment
and a provider-mapping observation. The machine-readable record is
[`model-inference-inventory-gap-2026-11-07.json`](model-inference-inventory-gap-2026-11-07.json).

## What the reads returned

Each call used the catalog mapping URL, anonymous GET, no redirect, and the
256 KiB response limit. All 33 returned HTTP 200. Every `inferenceProviderMapping`
was an empty object, recorded as `NO_PROVIDER_MAPPING`. The file list and
`README.md` at the returned revision also returned HTTP 200. No weight file was
downloaded and no model was run.

| Result | Count |
|---|---:|
| Mapping HTTP 200 and empty | 33 |
| Mapping populated or lookup failed | 0 |
| Assessments written | 33 |
| Rows whose returned sha matches the inventory sha | 29 |
| Rows whose returned sha differs from the inventory sha | 4 |
| Inference admission authority | 0 |
| Exclusion authority | 0 |
| Prior support rows left unchanged | 41 |
| Catalog rows after this record | 74 |

Artifact classes come from revision file names: 28 `standalone_weight_bundle`,
1 `adapter_bundle` (`szl-receiptagent-qwen25-1.5b-experimental-20261104`), and
4 `non_provider_artifact` (`khipu-abstain-r3-candidate`, `oac-ops-health-v2`,
`oac-system-health-v1`, `szl-specdecode`). An empty mapping does not make a
weight bundle eligible to serve. Authority flags stay false, and no support
discussion was submitted.

## Sha differences

These four mapping responses returned a revision other than the inventory sha.
The assessment uses the revision that was fetched. The inventory file was not
edited.

- `SZLHOLDINGS/SZL-AncientMath-0.8B-v1`
- `SZLHOLDINGS/SZL-FreeEnergy-0.8B-v1`
- `SZLHOLDINGS/SZL-Reasoning-0.8B-v1`
- `SZLHOLDINGS/szl-specdecode`

## Rows

| Decision | Model id | Observed sha | Inventory sha | Class |
|---|---|---|---|---|
| D01 | `SZLHOLDINGS/KHIPU-R2-estate-sft-v1` | `79c0efc23dbdb7f0a394125f811d0a3bb602b36f` | same | `standalone_weight_bundle` |
| D02 | `SZLHOLDINGS/Nemotron-Mini-4B-Instruct-st` | `2939ccd8e30d19c8209086893b75379dbf3c27b4` | same | `standalone_weight_bundle` |
| D03 | `SZLHOLDINGS/SZL-AncientMath-0.8B-v1` | `382e9c263b568b68967972d28803bf567746e1de` | DIFFERS | `standalone_weight_bundle` |
| D04 | `SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent-estate-sft-v1` | `d5e1d0722eeda4a2e0f8a4e5cdadeecf1b53bea4` | same | `standalone_weight_bundle` |
| D05 | `SZLHOLDINGS/SZL-FreeEnergy-0.8B-v1` | `c4c6ee13bf05aaaedf3c40a125b6ad317ac549e0` | DIFFERS | `standalone_weight_bundle` |
| D06 | `SZLHOLDINGS/SZL-Khipu-1.5B-estate-sft-v1` | `b4ae083265f2f0a6749af4111162d3582dc4dace` | same | `standalone_weight_bundle` |
| D07 | `SZLHOLDINGS/SZL-Khipu-1.5B-sft-v2` | `15c112a8171b4d6aa6eef09c57d92b35bfd3d9ab` | same | `standalone_weight_bundle` |
| D08 | `SZLHOLDINGS/SZL-Nemotron-Mini-4B-Doctrine-v1` | `decebd8be9255239c1507ebc61159099d38ba6bc` | same | `standalone_weight_bundle` |
| D09 | `SZLHOLDINGS/SZL-Nemotron-Mini-4B-Estate-DPO-v1` | `3b330741a7ecee572a7a51c5a3dd023788da8973` | same | `standalone_weight_bundle` |
| D10 | `SZLHOLDINGS/SZL-Nemotron-Mini-4B-Estate-DPO-v2` | `edd649ffcfae89d0a5b5cc889b5cbe0848336e01` | same | `standalone_weight_bundle` |
| D11 | `SZLHOLDINGS/SZL-Nemotron-Mini-4B-Estate-v1` | `8dd86a98a71d52d24ee23b51ef75ed9b6213c69f` | same | `standalone_weight_bundle` |
| D12 | `SZLHOLDINGS/SZL-Reasoning-0.8B-v1` | `4caa36a0fdeb4d54fabe13079cceb031ecfa3471` | DIFFERS | `standalone_weight_bundle` |
| D13 | `SZLHOLDINGS/SZL-Showcase-Systems-v1` | `31d82d6133f20ad26403d21abfd16950d8e19b11` | same | `standalone_weight_bundle` |
| D14 | `SZLHOLDINGS/SZL-Specialized-Domains-v1` | `f0293f28d7ec45a01c59e40daa93af38e20c308b` | same | `standalone_weight_bundle` |
| D15 | `SZLHOLDINGS/WILLAY-estate-sft-v1` | `4c2430a4f0c4d9459591019dac73ba4c235ceeb8` | same | `standalone_weight_bundle` |
| D16 | `SZLHOLDINGS/brain-navigator-r2-estate-sft-v1` | `f774b4b0b7e3d2a0a640543c95527e932a4e8301` | same | `standalone_weight_bundle` |
| D17 | `SZLHOLDINGS/chakana-r1-candidate` | `73219a8ada0e73ab4216d9e70d730e38455f2425` | same | `standalone_weight_bundle` |
| D18 | `SZLHOLDINGS/chaski-5050-estate-sft-v1` | `0278ef6fb06c622748a1043fa4c7efb9bccc716b` | same | `standalone_weight_bundle` |
| D19 | `SZLHOLDINGS/chaski-estate-sft-v1` | `4ab0cd0b31fa1ec83e3f2ebc7adf4a532514e21d` | same | `standalone_weight_bundle` |
| D20 | `SZLHOLDINGS/chaski-r2-estate-sft-v1` | `6e1f8b6a4461b5a5c3563d207a8a79ea76e5e6c5` | same | `standalone_weight_bundle` |
| D21 | `SZLHOLDINGS/khipu-abstain-r3-candidate` | `492c4a177bf0b4b856aa4d656ff8c561ab1d5f4d` | same | `non_provider_artifact` |
| D22 | `SZLHOLDINGS/khipu-r3-estate-sft-v1` | `b3c240a8540254ef294d9fbc320ff442ef31f393` | same | `standalone_weight_bundle` |
| D23 | `SZLHOLDINGS/miniembed-nano-r1-candidate` | `40e0c6ab9511586014457d354c00f05777b34fd1` | same | `standalone_weight_bundle` |
| D24 | `SZLHOLDINGS/oac-ops-health-v2` | `90df75bf58d91ea723128a86d7ed9af57535dbd8` | same | `non_provider_artifact` |
| D25 | `SZLHOLDINGS/oac-system-health-v1` | `a99c3ec1157af351fa24da64f3b413620cae07fe` | same | `non_provider_artifact` |
| D26 | `SZLHOLDINGS/szl-receiptagent-qwen25-1.5b-experimental-20261104` | `b2ec04727f46314b680ee26366159243924c1f67` | same | `adapter_bundle` |
| D27 | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-dpo-v1` | `4c1a8691e8b6c54b1ab07f55bfd78f627d6a9295` | same | `standalone_weight_bundle` |
| D28 | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-dpo-v2` | `af519f265ff552dd4c47ae3a61b5f62a6f3827d5` | same | `standalone_weight_bundle` |
| D29 | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-sft-v3` | `0340c300052e248367a3407aa493ef72a0da79fe` | same | `standalone_weight_bundle` |
| D30 | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2m-estate-sft-v1` | `8419537ecad5930f022eb89720e92ba18ed6605d` | same | `standalone_weight_bundle` |
| D31 | `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3-estate-sft-v1` | `9bde1943e8d60c461391bbcd86ffca340da321a8` | same | `standalone_weight_bundle` |
| D32 | `SZLHOLDINGS/szl-specdecode` | `31e589422ceb33461fe0f8d57208ccedccbcf387` | DIFFERS | `non_provider_artifact` |
| D33 | `SZLHOLDINGS/szl1-experimental-estate-sft-v1` | `e821e660b5940cd988307bba4b5c9a29a09605ec` | same | `standalone_weight_bundle` |

Admission was not granted for any row. `selected` remains null. Card
self-labels on four repositories are unchanged and are still not exclusion
records.
