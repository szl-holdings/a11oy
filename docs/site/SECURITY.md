<!-- VENDORED FROM szl-holdings/platform@e87ad75ec8e280e2fe3a3e8f49c5c0b6c2eec4ea — SECURITY.md -->
<!-- DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync. -->
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Please report security vulnerabilities via email to **security@szlholdings.ai** with:

1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact assessment
4. Any suggested mitigations

### Response SLA

| Severity | Initial Response | Resolution Target |
|---|---|---|
| Critical | 24 hours | 7 days |
| High | 48 hours | 30 days |
| Medium | 5 business days | 90 days |
| Low | 10 business days | 180 days |

We follow a **90-day responsible disclosure** policy. After 90 days from initial report, details may be published regardless of patch status (with appropriate notice to reporter).

## Supply-Chain Security

- **SLSA Build Level 1** — build provenance generated per release (honest; not L2/L3)
- **DCO required** — all commits carry `Signed-off-by:` trailers per [Linux Foundation DCO](https://developercertificate.org/)
- **Cosign keyless signing** — containers signed via Sigstore OIDC keyless mode; verify with `cosign verify ghcr.io/szl-holdings/<repo>:<tag>`
- **SBOM** — CycloneDX SBOM attached to each GitHub Release

## Section 889 Attestation

SZL Holdings attests that no covered telecommunications equipment or services from the following vendors are used in this software:

1. Huawei Technologies Company
2. ZTE Corporation
3. Hytera Communications Corporation
4. Hangzhou Hikvision Digital Technology Company
5. Dahua Technology Company

Per NDAA Section 889, 41 U.S.C. § 4713.

## Doctrine

- Doctrine v11 LOCKED — kernel commit `c7c0ba17` (749 declarations / 14 axioms / 163 sorries)
- Λ = Conjecture 1 (never a theorem)
- No Iron Bank, FedRAMP, CMMC, or SWFT claims

## Contact

- **Security disclosures:** security@szlholdings.ai
- **General:** hello@szlholdings.ai
- **Website:** https://szlholdings.ai

*This policy follows [OpenSSF Vulnerability Disclosure Guide](https://github.com/ossf/oss-vulnerability-guide).*
