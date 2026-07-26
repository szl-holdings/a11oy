<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Deployed identities

Primary status: **MEASURED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

| Service | Source identity | Runtime identity | Result |
| --- | --- | --- | --- |
| A11oy Hugging Face | protected GitHub main `af43e4b71529c2bab3227763fdb4b5969c2cd6ce` | `/api/build-info` reported `af43e4b71529c2bab3227763fdb4b5969c2cd6ce` | DEPLOYED / MEASURED MATCH |
| Killinchu Hugging Face | protected GitHub main `3bafc337446548902ee28086c3c6c17b486e70e9` | `/api/build-info` and honest endpoint reported `3bafc337446548902ee28086c3c6c17b486e70e9` | DEPLOYED / MEASURED MATCH |
| A11oy GHCR | source `7ccf04fb65f060115fb01392c739bb4e6c2fe5b8` | `sha256:5f3f48219d0c74f29ebfd6df6d7b8b68903daf6772cf6483124f458a3beca416` | MEASURED attestation match |

Killinchu's Dockerfile COPY inventory is complete in protected source, the exact-source reusable deployment is live, and `/code`, `/chat`, and `/api/killinchu/v1/honest` returned HTTP 200. The live platform image digest is not exposed, so digest-level runtime identity remains unavailable.
