<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 -->

# SLSA Build Level — SZL Holdings · a11oy

**Current honest status: SLSA Build L1 (honest)** — images are cosign-signed and independently verifiable via `cosign verify`. L2 (isolated, attested build-service provenance) is roadmap via Wire D; not yet claimed. L3 not claimed.

The published `ghcr.io/szl-holdings/a11oy` container image is cosign-signed on a GitHub Actions runner. SLSA L1 honest: provenance exists (cosign-signed), independently verifiable via `cosign verify`. L2 (isolated, attested build-service provenance via a dedicated signing service) is roadmap via Wire D; not yet claimed. The workflow run that produced the signed image: [26896040944](https://github.com/szl-holdings/a11oy/actions/runs/26896040944).

| SLSA Build level | Requirement | SZL status (a11oy) |
|---|---|---|
| L1 | Provenance exists (may be unsigned) | ✅ Met |
| L2 | Signed provenance from a hosted build platform, verifiable downstream | ⬜ Roadmap via Wire D — not yet claimed (GHCR verification shows cosign-signed L1 only; no provenance attestation tags verified) |
| L3 | Hardened, isolated builder; signing keys inaccessible to build steps | ⬜ Not claimed (requires a hardened, isolated build environment) |

## Evidence

- Build + attest workflow: `.github/workflows/ghcr-build-push.yml`
  (`actions/attest-build-provenance@v2`, `attestations: write`, `id-token: write`,
  `push-to-registry: true`).
- Predicate type: `https://slsa.dev/provenance/v1` (in-toto DSSE).
- Builder: GitHub-hosted Actions runner; OIDC issuer
  `https://token.actions.githubusercontent.com`.

## Verify (downstream)

```bash
# Verify the cosign signature on the published container image (SLSA L1 honest):
cosign verify ghcr.io/szl-holdings/a11oy:uds-v0.2.0 \
  --certificate-identity-regexp="https://github.com/szl-holdings/a11oy" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"

# GitHub attestation check (if attestation tags exist):
gh attestation verify oci://ghcr.io/szl-holdings/a11oy:uds-v0.2.0 --owner szl-holdings
```

Verified image digest: `sha256:7473f3d9eb156b2911170d86d8834d1e8bd8deb06a2aff91c6904fef64ceed71`.
Public Sigstore transparency-log entry (Rekor): log index **1710578865**
(`https://search.sigstore.dev/?logIndex=1710578865`). Offline cryptographic
verification of the DSSE bundle returned **VALID**; predicate
`https://slsa.dev/provenance/v1`; subject digest matches the published image.

SLSA L1 honest = cosign-signed images, verifiable via `cosign verify`. L2 (attested build-service provenance) is roadmap via Wire D; not yet claimed. **L3 is not claimed.**

---

<sub>Doctrine v11 LOCKED 749/14/163 · kernel c7c0ba17 · Λ Conjecture 1 · sovereign-default. Section 889 = exactly 5 banned vendors (Huawei/ZTE/Hytera/Hikvision/Dahua).</sub>
