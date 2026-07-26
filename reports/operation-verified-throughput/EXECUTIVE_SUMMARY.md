<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Executive summary

Primary status: **PREPARED IN A PR**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

The branch establishes a deny-by-default agent-action boundary, strict schemas, signed expiring authorization receipts, a public-key-only execution verifier, a pinned Lean 4.18.0 model for T1/T2, a proposed reusable build boundary, warning-mode Sigstore manifests, secret-safe GenAI telemetry, a fail-closed serving benchmark harness, and a generated Phase 0 inventory.

Verified results:

- **MEASURED:** 27 focused Python tests pass, including five strict schemas, 168 exhaustive runtime-refinement cases, adversarial receipt checks, cross-platform manifest determinism, and report-package integrity.
- **MODELED:** Lean T1 default denial and T2 rejected-implies-non-executable compile with positive, negative, mutation, and premise-removal controls.
- **DOWNGRADED:** Putnam is corrected from stale `4/12 GREEN` text to **0/12 PROVED**.
- **MEASURED:** existing GHCR artifact `sha256:5f3f48219d0c74f29ebfd6df6d7b8b68903daf6772cf6483124f458a3beca416` independently verifies to source `7ccf04fb65f060115fb01392c739bb4e6c2fe5b8`, run 30187276319, Rekor 2255395975.
- **DEPLOYED / MEASURED:** A11oy runtime build-info matches protected main `af43e4b71529c2bab3227763fdb4b5969c2cd6ce`.
- **DEPLOYED / MEASURED:** Killinchu runtime build-info matches protected main `3bafc337446548902ee28086c3c6c17b486e70e9`; `/code`, `/chat`, and the honest endpoint return HTTP 200.
- **MEASURED:** the canonical web application builds and typechecks from the immutable `vendor/platform` gitlink without no-op package stubs.
- **MEASURED:** Both immutable Space snapshots were archived, restored into fresh directories, and matched their original path/size/SHA-256 manifests byte-for-byte.
- **BLOCKED:** cloud identity, an owned staging cluster, admission negative controls, controlled GPU benchmarks, exact new-builder evidence, and an end-to-end staging release.

Owner authorization was received. Production enforcement and traffic cutover are still blocked by unavailable infrastructure and independent evidence gates, not by missing consent.

No GitHub ruleset, branch-protection, review, check-context, bypass, or approval mutation was performed.
The separately owned canonical governance implementation is PR #317 with zero human approvals and App-owned required attestation; this branch does not modify or reinterpret it.
