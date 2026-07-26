<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Claim downgrades

Primary status: **DOWNGRADED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

| Surface | Prior text | Corrected label | Evidence |
| --- | --- | --- | --- |
| Series A Putnam row | `PROVED — 0 of 12` and older public `4/12 GREEN` surfaces | **0/12 PROVED** | generated diligence row after pinned Putnam build gate |
| Evidence site Putnam lines | `4/12 GREEN` | **0/12 PROVED** | canonical immutable source labels: 0 REAL / 10 DEMO / 2 OPEN |
| SLSA posture | implied L3 target | **MEASURED Build L2; L3 BLOCKED** | independent attestation plus reusable-boundary gap |
| Killinchu identity | earlier source/runtime mismatch | **DEPLOYED / MEASURED MATCH** | protected main and `/api/build-info` both report `3bafc337446548902ee28086c3c6c17b486e70e9` |
| Killinchu `/code` and `/chat` | earlier unavailable/generic-route finding | **MEASURED HTTP 200** | live endpoint probes |

No public external surface was mutated from this branch.
