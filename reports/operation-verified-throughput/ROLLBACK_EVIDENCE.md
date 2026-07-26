<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Rollback evidence

Primary status: **MEASURED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

Both immutable Space snapshots were archived, restored into fresh directories, and matched their original path/size/SHA-256 manifests byte-for-byte.

This is offline source restoration evidence, not a live platform rollback or recovery-time measurement. A production traffic cutover still requires an owned staging/production target, an immutable deploy digest, a tested service rollback procedure, and independent release gates.
