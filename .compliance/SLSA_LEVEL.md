<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 -->

# SLSA Build Level — SZL Holdings

**Current honest status: SLSA Build L1 (honest).**

SZL Holdings claims **L1 (honest)** — provenance exists and is signed via Sigstore
(Fulcio keyless + Rekor) using a hosted GitHub Actions builder for every release
tag using the official `slsa-framework/slsa-github-generator` reusable workflow.
L2 requires downstream verifier validation; L3 requires isolated builders.
Both L2 and L3 are on the roadmap (honest). Current claim is L1.

| SLSA Build level | Requirement | SZL status |
|---|---|---|
| L1 | Provenance exists (may be unsigned) | ✅ Met |
| L2 | Signed provenance from a hosted build platform, verified downstream | ⬜ Roadmap — signing is live but downstream verifier validation not yet proven end-to-end |
| L3 | Hardened, isolated builder; signing keys inaccessible to build steps | ⬜ Deferred (roadmap) |

## Evidence

- Hosted-builder provenance workflow: `.github/workflows/slsa-build.yml`
  (reusable `generator_generic_slsa3.yml@v2.0.0`, `id-token: write` keyless signing).
- SBOM + cosign-signed CycloneDX/SPDX pipeline: `.github/workflows/sbom.yml`.
- Signing: cosign ECDSA-P256-SHA256, keyid `szlholdings-cosign`,
  public-key sha256 `b066de4081a3a49dd98d830ee68938facb86ffa5a658e71ddfe27b00b00f5dd2`.

## Verify (downstream)

```bash
# Verify the attached SLSA provenance for a released artifact:
slsa-verifier verify-artifact <artifact>.tar.gz \
  --provenance-path <artifact>.tar.gz.intoto.jsonl \
  --source-uri github.com/szl-holdings/<repo>
```

---

<sub>Doctrine v11 LOCKED 749/14/163 · Λ Conjecture 1 · sovereign-default. No banned vendors (Huawei/ZTE/Hytera/Hikvision/Dahua).</sub>
