<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 -->

# SLSA Build Level — SZL Holdings · a11oy

**Current source-declared posture: SLSA L1. L2/L3 are not established.**
The canonical implementation is `szl_provenance.SLSA_LEVEL = "L1"`; the public
`/api/a11oy/provenance` and `/api/a11oy/v1/honest` responses expose that posture.
This source declaration does not verify the current running image, every build,
or any particular artifact signature.

The evidence below records a historical image and a historical workflow run
([26896040944](https://github.com/szl-holdings/a11oy/actions/runs/26896040944)).
Re-verify the exact digest, expected signer identity, issuer and provenance before
relying on it. An image signature or a historical attestation does not by itself
establish complete current L2 coverage.

| SLSA Build level | Requirement | SZL status (a11oy) |
|---|---|---|
| L1 | Provenance exists (may be unsigned) | Source-declared by the canonical provenance service |
| L2 | Signed provenance from a hosted build platform, verifiable downstream | Not established; review historical evidence per artifact |
| L3 | Hardened, isolated builder; signing keys inaccessible to build steps | Not established |

## Historical evidence

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

Historically recorded image digest: `sha256:7473f3d9eb156b2911170d86d8834d1e8bd8deb06a2aff91c6904fef64ceed71`.
Public Sigstore transparency-log entry (Rekor): log index **1710578865**
(`https://search.sigstore.dev/?logIndex=1710578865`). The historical record reports that offline cryptographic
verification of the DSSE bundle returned **VALID**; predicate
`https://slsa.dev/provenance/v1`; subject digest matches the published image.

A successful `cosign verify` authenticates an image signature under its verification policy. It is separate from validating provenance and assessing a SLSA level. **The current canonical posture remains L1; L2/L3 are not established.**

---

<sub>Doctrine v11 LOCKED 749/14/163 · kernel c7c0ba17 · Λ Conjecture 1 · sovereign-default. Section 889 = exactly 5 banned vendors (Huawei/ZTE/Hytera/Hikvision/Dahua).</sub>
