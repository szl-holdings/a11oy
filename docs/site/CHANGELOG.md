# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.0.0] — 2026-06-09

### Added
- Doctrine v11 compliance — kernel commit `c7c0ba17` (749 declarations / 14 axioms / 163 sorries)
- SLSA Build Level 1 provenance — honest declaration, not overclaimed
- Section 889 attestation — exactly 5 vendors assessed (Huawei, ZTE, Hytera, Hikvision, Dahua)
- DCO `Signed-off-by:` trailers on all commits per Linux Foundation DCO policy
- OpenTelemetry `traceparent` W3C header propagated end-to-end
- `/api/health` endpoint returning structured JSON with `sovereign: true`
- SBOM (CycloneDX) generated and attached to release
- Cosign keyless OIDC signing for container images
- OpenSSF Scorecard GHA workflow
- SECURITY.md with 90-day responsible disclosure policy
- SUPPORT.md with issue triage SLAs
- CODEOWNERS covering all critical paths
- Dependabot weekly dependency updates
- Trivy/Grype container vulnerability scanning gate
- SLO documentation (p50/p95/p99 targets + error budget)
- Threat model (STRIDE format)
- CITATION.cff for academic citeability

### Security
- Section 889 — no covered telecommunications equipment from Huawei, ZTE, Hytera, Hikvision, or Dahua
- No Iron Bank, FedRAMP, CMMC, or SWFT claims (capability honesty per Anthropic RSP)
- Λ = Conjecture 1 (never a theorem) — mathematical honesty enforced

### Notes
- Warhacker June 9, 2026 release

[Unreleased]: https://github.com/szl-holdings/docs-site/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/szl-holdings/docs-site/releases/tag/v1.0.0
