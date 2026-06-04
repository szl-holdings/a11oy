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

## Evidence (L1 earned)

- The published image is cosign-signed keyless on a GitHub-hosted Actions runner;
  signature + Rekor inclusion are independently verifiable via `cosign verify`.
- Builder: GitHub-hosted Actions runner; OIDC issuer
  `https://token.actions.githubusercontent.com`.

## L2 status (NOT yet earned — roadmap via Wire D)

The build workflow `.github/workflows/ghcr-build-push.yml` includes
`actions/attest-build-provenance@v2` (pinned by SHA) with `push-to-registry: true`
and `permissions: { id-token: write, attestations: write, packages: write }`.
**However, a live check against the deployed image returns no attestation:**

```text
$ cosign verify-attestation --type slsaprovenance ghcr.io/szl-holdings/a11oy:uds-v0.2.0 \
    --certificate-identity-regexp="^https://github.com/szl-holdings/" \
    --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
Error: no matching attestations
```

Until this command returns a valid attestation, **L2 is NOT claimed anywhere**.
The likely remaining blocker is org-level permission (`attestations: write`); if a
workflow run fails with "Resource not accessible by integration," that is a
**founder action** (enable attestations at the org level) — see the team report.

## Verify (downstream)

```bash
# 1. Verify the cosign signature on the published image (SLSA L1 honest — PASSES today):
cosign verify ghcr.io/szl-holdings/a11oy:uds-v0.2.0 \
  --certificate-identity-regexp="^https://github.com/szl-holdings/" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"

# 2. SLSA L2 provenance attestation (roadmap — currently "no matching attestations"):
cosign verify-attestation --type slsaprovenance ghcr.io/szl-holdings/a11oy:uds-v0.2.0 \
  --certificate-identity-regexp="^https://github.com/szl-holdings/" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
```

Public Sigstore transparency-log entry (Rekor): log index **1710578865**
(`https://search.sigstore.dev/?logIndex=1710578865`).

SLSA L1 honest = cosign-signed images, verifiable via `cosign verify`. L2 (attested build-service provenance) is roadmap via Wire D; **not yet claimed because `cosign verify-attestation` does not yet pass on the deployed image.** **L3 is not claimed.**

---

<sub>Doctrine v11 LOCKED 749/14/163 · kernel c7c0ba17 · Λ Conjecture 1 · sovereign-default. Section 889 = exactly 5 banned vendors (Huawei/ZTE/Hytera/Hikvision/Dahua).</sub>
