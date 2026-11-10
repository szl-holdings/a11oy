<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Model inference inventory gap, 2026-11-10

The public inventory observed at `2026-11-10T10:33:42Z` lists 86 model repositories. `docs/model-inference-support.json` covered 74 of them, so 12 rows were added. This is a review record: it admits, excludes and routes nothing, and every authority flag stays false.

Each added row records an empty public provider mapping (HTTP 200), the revision it was read at, the artifact class inferred from file names at that revision (not weight bytes), and the README status. No weights were downloaded and no model was run. Every owner decision below is unselected.

| Decision | Repository | Artifact class | Revision matches inventory | README |
|---|---|---|---|---|
| D01 | `SZLHOLDINGS/SZL-AcousticGovernance-0.8B-v1` | `standalone_weight_bundle` | yes | HTTP 200, 4252 bytes |
| D02 | `SZLHOLDINGS/SZL-FreeEnergy-0.8B-DPO-v1` | `standalone_weight_bundle` | yes | HTTP 200, 1111 bytes |
| D03 | `SZLHOLDINGS/SZL-GovernedDistill-0.8B-v1` | `standalone_weight_bundle` | yes | HTTP 200, 3455 bytes |
| D04 | `SZLHOLDINGS/abstain-doctrine-r1` | `standalone_weight_bundle` | yes | HTTP 200, 1842 bytes |
| D05 | `SZLHOLDINGS/doctrine-v2-r2-candidate` | `standalone_weight_bundle` | yes | HTTP 200, 1691 bytes |
| D06 | `SZLHOLDINGS/doctrine1-r1-candidate` | `standalone_weight_bundle` | yes | HTTP 200, 1685 bytes |
| D07 | `SZLHOLDINGS/forge-v3` | `standalone_weight_bundle` | yes | HTTP 200, 1651 bytes |
| D08 | `SZLHOLDINGS/freeenergy-r1-candidate` | `standalone_weight_bundle` | yes | HTTP 200, 1724 bytes |
| D09 | `SZLHOLDINGS/ouroboros-r2-candidate` | `standalone_weight_bundle` | yes | HTTP 200, 1801 bytes |
| D10 | `SZLHOLDINGS/szl-brain` | `non_provider_artifact` | yes | HTTP 404 (empty repository) |
| D11 | `SZLHOLDINGS/willay-r1-candidate` | `standalone_weight_bundle` | yes | HTTP 200, 1662 bytes |
| D12 | `SZLHOLDINGS/willay-r2-candidate` | `standalone_weight_bundle` | yes | HTTP 200, 1662 bytes |

The 74 rows already in the catalog are preserved unchanged; `model-inference-inventory-gap-2026-11-10.json` fingerprints each of them.

Limits: provider mappings are normalized public API fields, not independent attestation. An empty mapping is neither an exclusion record nor a qualification. `SZLHOLDINGS/szl-brain` held only `.gitattributes` when observed.
