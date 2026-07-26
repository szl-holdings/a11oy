<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Provenance verification

Primary status: **MEASURED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

Verified subject: `oci://ghcr.io/szl-holdings/a11oy@sha256:5f3f48219d0c74f29ebfd6df6d7b8b68903daf6772cf6483124f458a3beca416`.

`gh attestation verify` succeeded with expected repository `szl-holdings/a11oy`. The statement names source `7ccf04fb65f060115fb01392c739bb4e6c2fe5b8`, workflow `.github/workflows/ghcr-build-push.yml@refs/heads/main`, run `30187276319/attempts/1`, GitHub-hosted runner, and Rekor log index `2255395975`.

This verifies the existing attestation and identity. It does not prove reproducibility, admission enforcement, SLSA Build L3, the proposed reusable workflow, or the availability of a matching SBOM.

The secondary `slsa-verifier v2.7.1 verify-image` check **FAILED** with `no matching attestations`. This is retained evidence that the existing GitHub/cosign path is not the required SLSA-native cross-verification path.
