# Changelog

All notable changes across the five SZL flagships are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> Doctrine v11 **LOCKED** — 749/14/163 · kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 honest.
> This page **aggregates** the v1.0.0 release notes published per flagship; each flagship's
> own release is the source of truth (linked below).

---

## [1.0.0] — 2026-06-09

Coordinated v1.0.0 launch of the five flagships. Per-flagship GitHub releases:
[a11oy](https://github.com/szl-holdings/a11oy/releases/tag/v1.0.0) ·
sentra ·
amaru ·
rosie ·
[killinchu](https://github.com/szl-holdings/killinchu/releases/tag/v1.0.0).

### Added
- **a11oy** — policy + receipt substrate; `/v1/policy/evaluate`, `/v1/verify`, `/v1/ledger`, `/v1/honest`, `/v1/version` live.
- **sentra** — 8-gate deny-by-default immune system; `/v1/verdict`, `/v1/inspect`, `/v1/gates` live.
- **amaru** — 7-chakra memory cortex; COSE_Sign1 governance receipts; Cardano hash-anchoring.
- **rosie** — operator console with KhipuReceipt DAG + understudy failover under `/api/rosie/v2/*`.
- **killinchu** — counter-UAS rule engine; real Remote-ID / ADS-B / MAVLink decoders; 13-axis Λ-gate; DSSE Khipu receipts.
- Doctrine v11 compliance across all 5 — kernel `c7c0ba17` (749 declarations / 14 axioms / 163 sorries).
- SBOM (CycloneDX + SPDX) attached to each release; cosign keyless OIDC signing path documented.
- OpenSSF Scorecard, `SECURITY.md`, `SUPPORT.md`, `CODEOWNERS`, Dependabot, Trivy/Grype gates per repo.
- W3C `traceparent` propagated end-to-end (OTel-VSP nerves).
- `CITATION.cff` per flagship for academic citeability.

### Security
- **Section 889** — no covered telecommunications equipment from the 5 named vendors (Huawei, ZTE, Hytera, Hikvision, Dahua).
- No Iron Bank, FedRAMP, CMMC, SWFT, or Mission Owner claims (capability honesty per Anthropic RSP pattern).
- **Λ = Conjecture 1** (never a theorem) — mathematical honesty enforced in every `/v1/honest` payload.
- DSSE/Sigstore receipt signatures labelled `PLACEHOLDER` until CI signing lands — honest SLSA L1.

### Notes
- Warhacker (San Diego) launch window: June 2026.

---

## [Unreleased]

- UDS — Unified Demo Surface public launch (see [/uds](/uds)).
- Sigstore CI signing wired (removes `PLACEHOLDER` receipt labels → SLSA L1 attested).

---

[1.0.0]: https://github.com/szl-holdings
[Unreleased]: https://github.com/szl-holdings

---
*Doctrine v11 LOCKED · 749/14/163 · kernel c7c0ba17 · Λ = Conjecture 1 · SLSA L1 honest*
