# UDS Catalog Submission — Status and Requirements

**Status: [STAGED] NOT YET SUBMITTED**
**Last updated:** 2026-05-29
**Doctrine:** v6 (strict) — no fake catalog claims

---

## Summary

This directory contains preparation materials for an eventual UDS Catalog submission.
**SZL is not currently submitted to or accepted by the UDS Catalog.**

Three blockers must be resolved before submission is appropriate:
1. **Andrew Greene sponsor approval** — collaboration endorsement (Option-A, 2026-05-22) is NOT the same as catalog sponsorship. Catalog submission requires a DU catalog maintainer to formally sponsor the package.
2. **Container push to GHCR** — the UDS Catalog requires a pullable container image at `ghcr.io/szl-holdings/vessels:uds-v0.3.1` (or equivalent per-component images). The container has NOT yet been pushed (FA-001 pending).
3. **Cosign signing** — the UDS Package pattern requires signed artifacts. Cosign keys are CI-only; the org dev key has not yet been used to sign release tarballs (FA-001 pending).

---

## What UDS Catalog Acceptance Actually Requires

Based on public Defense Unicorns documentation:

### From the UDS Common Package Guide
Source: https://github.com/defenseunicorns/uds-common/blob/main/docs/uds-packages/guide.md

| Requirement | Description |
|-------------|-------------|
| UDS Package CR | `kind: Package` with `apiVersion: uds.dev/v1alpha1` — configures ingress, SSO, network policy, monitoring |
| Zarf package | `zarf.yaml` that bundles container images for air-gap delivery |
| Package images | All images pullable from a public registry (GHCR) at release time |
| UDS bundle | `uds-bundle.yaml` composing the Zarf package with uds-core |
| tasks.yaml | `uds run` tasks for deploy/update/remove lifecycle |
| SBOM | Software bill of materials attached to release |
| Package documentation | README covering deployment, prerequisites, configuration |
| CI passing | GitHub Actions must be green on main |
| Package tests | Automated tests that validate the deployed package |

### From Defense Unicorns UDS Docs
Source: https://docs.defenseunicorns.com/core/how-to-guides/packaging-applications/create-uds-package/

| Requirement | Description |
|-------------|-------------|
| Networking config | `allow` blocks for ingress/egress in Package CR |
| SSO config | Keycloak client configuration (if applicable) |
| Monitoring config | ServiceMonitor references in Package CR |
| Network policies | Auto-generated from Package CR allow blocks |

---

## What SZL Currently Has

| Requirement | Status | Evidence |
|-------------|--------|----------|
| UDS Package CR | Partial — `szl-uds-deployment#4` added CR for szl-receipts | PR #4 merged |
| NetworkPolicy | Partial — added in PR #4 | PR #4 merged |
| ServiceMonitor | Partial — added in PR #4 | PR #4 merged |
| PSS labels (restricted) | Partial — added in PR #4 | PR #4 merged |
| tasks.yaml | ✓ DONE — `uds run demo:start` works | PR #4 merged |
| SBOM | ✓ DONE — `sbom.yml` CI workflow across all repos | GitHub Actions |
| README / docs | ✓ DONE — OPERATOR_QUICKSTART.md + per-component docs | This PR |
| CI passing | ✓ DONE — all repos green on main | GitHub Actions |
| Zarf package (szl-receipts) | Partial — `zarf.yaml` exists, package not yet created | PR #4 |
| Zarf packages (a11oy, sentra, amaru, rosie) | [STAGED] — not yet created | FA-001 needed |
| Container images at GHCR | [STAGED] — NOT PUSHED | FA-001 needed |
| Cosign-signed assets | [STAGED] — NOT SIGNED | FA-001 needed |
| Formal catalog sponsor | [STAGED] — not confirmed | Requires DU catalog maintainer |
| Package tests (automated) | Partial — validation script in PR #4, full automation pending | Engineering |

---

## What Is Explicitly Missing (Honest)

### 1. Container images NOT in GHCR
```
ghcr.io/szl-holdings/vessels:uds-v0.3.0   — NOT PUSHED (FA-001 blocker)
ghcr.io/szl-holdings/a11oy:uds-v0.3.1     — NOT PUSHED (FA-001 blocker)
ghcr.io/szl-holdings/sentra:uds-v0.3.1    — NOT PUSHED (FA-001 blocker)
ghcr.io/szl-holdings/amaru:uds-v0.3.1     — NOT PUSHED (FA-001 blocker)
ghcr.io/szl-holdings/rosie:uds-v0.3.1     — NOT PUSHED (FA-001 blocker)
```

### 2. Cosign-signed binary assets NOT attached to GitHub releases
All 6 repos (`uds-v0.3.0` tags) have SBOM-only releases.
The 4-asset signed pattern (tarball + .sig + .sha256 + .pub) requires FA-001.

### 3. No DU catalog sponsor confirmed
Andrew Greene's Option-A endorsement (2026-05-22) authorizes SZL to operate within UDS licensing.
It does NOT constitute:
- Catalog package submission approval
- A formal catalog maintainer sponsorship
- Defense Unicorns as customer or product partner

### 4. UDS Package CR incomplete for multi-component stack
The CR in PR #4 covers `szl-receipts` only.
Full stack Package CRs for a11oy-runtime, sentra-gates, amaru-attestation, rosie-replay
require in-cluster services/selectors that don't exist yet.

---

## Path to Catalog Submission

```
Current state (v0.3.0)
       │
       ▼ FA-001 (founder action)
Push containers to GHCR
Sign tarballs with cosign
Upload assets to GitHub releases
       │
       ▼ Engineering (T-6 before Warhacker: 2026-06-10)
Create Zarf packages for all 5 components
Create UDS Package CRs for all 5 components
Wire automated package tests
       │
       ▼ Post-Warhacker (T+14: 2026-07-01)
Approach Andrew Greene for formal catalog sponsor conversation
Submit to UDS Catalog (GitHub issue / PR to catalog registry)
       │
       ▼ DU catalog maintainer review
Acceptance or feedback cycle
```

---

## What Submission Is NOT

This directory is preparation only. Do not:
- Claim SZL is "in the UDS Catalog"
- Claim Andrew Greene's Option-A endorsement = catalog acceptance
- Attach a "UDS Catalog Accepted" badge to any repo
- Submit to the catalog before all three blockers are resolved

---

*Generated: 2026-05-29 | catalog-submission/README.md | Doctrine v6 strict*
*NOT SUBMITTED — see acceptance-criteria-checklist.md for itemized status*
