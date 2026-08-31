<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 -->

# SLSA Build Level — SZL Holdings · a11oy

**Current honest status: SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap** — images are cosign-signed and independently verifiable via `cosign verify` (L1), and a signed SLSA provenance attestation verifies via `cosign verify-attestation --type slsaprovenance` with strict per-organ identity (L2). L3 not claimed.

The published `ghcr.io/szl-holdings/a11oy` container image is cosign-signed on a GitHub Actions runner and carries a keyless (Fulcio+Rekor) SLSA provenance attestation. SLSA L2: the signed provenance from the hosted build platform verifies downstream via `cosign verify-attestation --type slsaprovenance` — independently re-verified across all 5 organ images. The workflow run that produced the signed image: [26896040944](https://github.com/szl-holdings/a11oy/actions/runs/26896040944).

| SLSA Build level | Requirement | SZL status (a11oy) |
|---|---|---|
| L1 | Provenance exists (may be unsigned) | ✅ Met |
| L2 | Signed provenance from a hosted build platform, verifiable downstream | 🛣️ Build-attestation with Rekor evidence present (honest posture); full verified L2 = roadmap
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
# Verify the cosign signature on the published container image (SLSA L1):
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

SLSA L1 = cosign-signed images, verifiable via `cosign verify`. SLSA L2 = signed provenance attestation, verifiable via `cosign verify-attestation --type slsaprovenance` (strict identity) — verified on all 5 organ images. **L3 is not claimed.**

---

<sub>Doctrine v11 LOCKED 749/14/163 · kernel c7c0ba17 · Λ Conjecture 1 · sovereign-default. Section 889 = exactly 5 banned vendors (Huawei/ZTE/Hytera/Hikvision/Dahua).</sub>
