<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Open risks

Primary status: **BLOCKED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

High-severity blockers:

1. No owned staging cluster is available for admission negative-control evidence — owner `@szl-holdings/security-reviewers`.
2. No exact SBOM, scan, signature, and SLSA-native cross-verification output exists from the proposed reusable builder — owner `@szl-holdings/release-maintainers`.
3. No controlled GPU environment is available for paired vLLM/SGLang measurement — owner `@szl-holdings/performance-maintainers`.

Additional blockers are independent Lean statement review, collector/access-control deployment, and complete staging trace evidence. The former Killinchu runtime and web-build findings are closed. Machine-readable detail is in `audit/risk-register.json`.
