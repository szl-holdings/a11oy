<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# SLSA Build Level 3 audit

Primary status: **BLOCKED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

Existing evidence is **MEASURED** at Build L2 scope: GitHub attestation verification succeeded for `sha256:5f3f48219d0c74f29ebfd6df6d7b8b68903daf6772cf6483124f458a3beca416` and binds it to source `7ccf04fb65f060115fb01392c739bb4e6c2fe5b8`. The existing builder is not a protected reusable workflow and signed mutable tags, so Build L3 is not claimed.

`.github/workflows/reusable-build.yml` is **PREPARED IN A PR**. It builds internally, accepts only the canonical image name, produces an immutable digest, SBOM and vulnerability report for that digest, attests and keyless-signs the digest, and fails on missing evidence. It is not protected until independent review and merge.

The SLSA-native secondary path is **FAILED** for the existing digest and **BLOCKED** for the proposed builder. The pinned `slsa-verifier v2.7.1` Windows binary (verified digest `sha256:1d8f61ad747ecc3d375d2a563cebf2991748b7da1a9bda9a500804c3c499e3c0`) returned `no matching attestations`. `slsa-github-generator >= v1.10.0` has not produced an artifact from the proposed reusable builder. Generator `v2.1.0` is the identified candidate, not an executed result.
