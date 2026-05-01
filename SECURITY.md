# Security Policy

## Supported Versions

Security updates are issued for the latest minor release on the default branch. Prior versions are not supported.

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| older   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability, please report it privately so we can investigate and remediate before public disclosure.

**Preferred channel:** [security@szlholdings.com](mailto:security@szlholdings.com)

**Alternate channel:** [Open a private security advisory](https://github.com/szl-holdings/.github/security/advisories/new) on GitHub.

Please include:

- A clear description of the issue and its potential impact.
- Steps to reproduce, including any proof-of-concept code, requests, or payloads.
- The affected version, commit SHA, or environment.
- Your name and contact details for follow-up and credit (optional).

## Disclosure Process

1. We acknowledge receipt within **2 business days**.
2. We assess severity using CVSS v3.1 and triage within **5 business days**.
3. We work on a fix and coordinate a release window with you.
4. We publish a security advisory and credit the reporter at their request.

We ask that you give us a reasonable opportunity to investigate and patch before public disclosure. We do not pursue legal action against good-faith security research.

## Scope

In scope:

- Source code, container images, and infrastructure-as-code in this repository.
- Authentication, authorization, data handling, and cryptographic implementations.
- Supply-chain risks affecting build artifacts produced from this repository.

Out of scope:

- Third-party dependencies (please report upstream).
- Social engineering, physical attacks, or denial-of-service against shared infrastructure.
- Findings that require physical access to a user's device.

## Hall of Thanks

Researchers who responsibly disclose vulnerabilities will be acknowledged here.
