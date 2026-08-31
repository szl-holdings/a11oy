# Security Policy

## Trust Tier

**Trust Tier 1** — SZL Holdings is committed to coordinated, responsible disclosure for all SZL Holdings repositories.

## Reporting a Vulnerability

Please report security vulnerabilities to: **security@szlholdings.com**

**Alternate channel:** [Open a private security advisory](https://github.com/szl-holdings/.github/security/advisories/new) on GitHub.

Please include:

- A clear description of the issue and its potential impact.
- Steps to reproduce, including any proof-of-concept code, requests, or payloads.
- The affected version, commit SHA, or environment.
- Your name and contact details for follow-up and credit (optional).

## Disclosure Process

We commit to:
- Acknowledging your report within **72 hours**
- Providing an initial assessment within **7 days**
- Disclosing the resolution within **90 days** of report (industry-standard coordinated-disclosure window)

We ask that you give us a reasonable opportunity to investigate and patch before public disclosure. We do not pursue legal action against good-faith security research.

## Supported Versions

| Version | Supported |
|---------|-----------|
| Current main | ✅ |
| Tagged releases (last 90 days) | ✅ |
| Older tagged releases | Best effort |

## Scope

This policy covers all software published under `szl-holdings/*`. For the upstream Defense Unicorns ecosystem we contribute to (Iron Bank, UDS, Pepr, Zarf), please follow their respective security policies.

In scope:

- Source code in this repository
- Released artifacts (packages, Docker images, Lean builds)
- CI/CD pipelines producing signed attestations

Out of scope:

- Third-party services integrated with SZL products (report to those vendors)
- Issues already publicly known or previously reported

## Governance

All security disclosures are governed by **SZL Doctrine v11**: no fake security claims, STAGED-ADVISORY label for gates not yet machine-checked, DSSE receipts on every governance decision.

## Hall of Thanks

Security researchers who responsibly disclose issues will be credited here (with permission).

Source: https://github.com/szl-holdings/.github
