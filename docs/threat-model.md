# Threat Model — STRIDE Analysis

**Service:** a11oy  
**Version:** v1.0.0  
**Framework:** STRIDE  
**Last reviewed:** 2026-06-09  
**Next review:** 2026-09-09 (quarterly)

---

## Scope

This threat model covers the a11oy service as deployed on HuggingFace Spaces (free-tier Docker container) and GitHub Actions CI/CD pipeline. It does not cover the underlying HuggingFace infrastructure.

**Trust boundaries:**
1. External internet → HuggingFace Space (public endpoint)
2. GitHub Actions → GHCR (container registry)
3. GitHub Actions → GitHub API (deployments, releases)
4. Operator browser → HuggingFace Space (admin UI)

---

## STRIDE Analysis

### S — Spoofing

| Threat | Component | Mitigation | Status |
|---|---|---|---|
| Forged commit author | Git history | DCO `Signed-off-by:` on all commits | DONE |
| Container image tampering | GHCR | Cosign keyless OIDC signing + Rekor transparency log | DONE |
| Fake release artifacts | GitHub Releases | SBOM attached; SHA256 checksums in release notes | DONE |

### T — Tampering

| Threat | Component | Mitigation | Status |
|---|---|---|---|
| Supply-chain action injection | GHA workflows | All `uses:` steps pinned to commit SHA | DONE |
| Dependency substitution | pip/npm/go | Dependabot weekly; lock files committed | DONE |
| Branch history rewrite | GitHub repo | Branch protection: no force-push on main | DONE |
| Dockerfile `COPY . .` wildcard | Container build | Per-file Dockerfile COPY enforced (doctrine requirement) | DONE |

### R — Repudiation

| Threat | Component | Mitigation | Status |
|---|---|---|---|
| Unverifiable build provenance | CI artifacts | SLSA L1 provenance; GHA run ID in release notes | DONE |
| Untracked security disclosures | Issue tracker | `SECURITY.md` with 90-day SLA; email audit trail | DONE |

### I — Information Disclosure

| Threat | Component | Mitigation | Status |
|---|---|---|---|
| Secrets in git history | Repository | Gitleaks + TruffleHog in CI; no `.env` committed | PARTIAL |
| Long-lived credentials | GitHub Actions | Secrets stored as GHA encrypted secrets; OIDC preferred | PARTIAL |
| Verbose error responses | API endpoints | All endpoints return 200 or 404; no 405/500 detail leak | DONE |

### D — Denial of Service

| Threat | Component | Mitigation | Status |
|---|---|---|---|
| HF Space cold-start | Hosting | Free-tier spaces may sleep (48h inactivity) — upgrade to paid tier recommended | OPEN |
| Rate-limit bypass | API | HuggingFace platform-level rate limiting | EXTERNAL |

### E — Elevation of Privilege

| Threat | Component | Mitigation | Status |
|---|---|---|---|
| GHA token privilege escalation | Workflows | Least-privilege `permissions:` block on all workflows | DONE |
| CODEOWNERS bypass | GitHub | Branch protection requires CODEOWNERS review | DONE |
| Doctrine kernel modification | Lean files | DO NOT MODIFY `.lean` files; commit `c7c0ba17` locked | LOCKED |

---

## Open Risks (Accepted)

| Risk | Severity | Acceptance Rationale |
|---|---|---|
| HF free-tier sleep | High | Upgrade requires payment (founder action); acceptable pre-Warhacker |
| No Vault integration | Medium | K8s secrets sufficient for current scale; Vault is post-v1.0 |
| No PagerDuty/Opsgenie | Low | Small team; manual on-call acceptable pre-Warhacker |

---

## Sources

- [NIST SP 800-154 — Data-Centric Threat Modeling](https://csrc.nist.gov/publications/detail/sp/800-154/draft)
- [Anthropic RSP — Threat Modeling](https://www.anthropic.com/responsible-scaling-policy)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [STRIDE methodology](https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats)

*Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>*
