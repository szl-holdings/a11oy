<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Estate ledger

Generated at `2026-07-26T08:09:00.789958Z` by `scripts/generate_operation_inventory.py`.

| Estate surface | Status | Evidence |
| --- | --- | --- |
| Current A11oy production source | MEASURED | GitHub main and runtime build-info `af43e4b71529c2bab3227763fdb4b5969c2cd6ce` |
| GitHub protections | MEASURED | Read-only inventory in `repository-rulesets.json`; **no mutations performed** |
| Existing A11oy GHCR attestation | MEASURED | `sha256:5f3f48219d0c74f29ebfd6df6d7b8b68903daf6772cf6483124f458a3beca416`, run 30187276319, Rekor 2255395975 |
| A11oy Hugging Face identity | MEASURED | Runtime build-info matches protected main `af43e4b71529c2bab3227763fdb4b5969c2cd6ce` |
| Killinchu current source bundle | MEASURED | Dockerfile COPY sources exist and exact-source deploy is live |
| Killinchu running image identity | MEASURED | Runtime build-info matches protected main `3bafc337446548902ee28086c3c6c17b486e70e9` |
| Killinchu `/code` and `/chat` | MEASURED | Both routes returned HTTP 200 at observation |
| Canonical web application | MEASURED | Pinned `vendor/platform` source builds and typechecks without stubs |
| Lean T1/T2 | MODELED | Local kernel build passes; public claim remains **0/12 PROVED** |
| Runtime policy refinement | MEASURED | Finite domain plus adversarial receipt tests |
| Reusable build | PREPARED IN A PR | Not protected or deployed until independently reviewed and merged |
| Sigstore warning policy | PREPARED IN A PR | Manifests only; no cluster mutation |
| vLLM/SGLang matrix | BLOCKED | No GPU node, model revision, tokenizer revision, or endpoints |
| OTel GenAI contract | IMPLEMENTED NOT DEPLOYED | Content capture off, redaction and mandatory sampling tests |
| Backup and restoration | MEASURED | Secret-backed immutable Space snapshots and offline byte-for-byte restore |
