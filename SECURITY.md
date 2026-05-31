# Security Policy

This policy is governed by [SZL Doctrine v7](https://github.com/szl-holdings/.github/blob/main/doctrine/DOCTRINE_V7.md),
including §2 (No Hallucinations / No Fake Green) and §7 (Every Claim Citable).
We do not publish security claims we cannot back with a verifiable source.

## Reporting a vulnerability

Report security vulnerabilities to **security@szlholdings.com**.
If you do not receive a response, use **stephen@szlholdings.com** as a fallback.

Please do NOT open a public issue for security reports.

## PGP

PGP key: TBD — request the current key at security@szlholdings.com.

We do not publish a fingerprint here until a key is in place, to avoid asserting
a key that cannot be verified.

## Doctrine v7

All vulnerability disclosures are governed by SZL Doctrine v7 (canonical, supersedes v6):
- No fake security claims
- STAGED-ADVISORY label for gates not yet machine-checked
- DSSE receipts on every governance decision

## Response timeline

- Acknowledgment SLA: within 5 business days of receipt.
- Disclosure window: 90 days. We aim to remediate and coordinate public
  disclosure within 90 days of acknowledgment. We will keep you informed if a
  fix requires longer and will agree on a revised timeline with you.

## Scope

In scope:

- Code on the current default branch (`main`) of this repository (szl-holdings/a11oy).

Out of scope:

- Third-party dependencies that run their own disclosure or bug-bounty programs
  (report those upstream).
- Denial-of-service (DoS) and volumetric attacks.
- Social engineering of staff, contractors, or users.
- Physical attacks against infrastructure or personnel.

## Coordinated disclosure

We follow coordinated disclosure. We will not pursue action against good-faith
research that respects this scope and the 90-day window, and that avoids privacy
violations, data destruction, and service degradation.
