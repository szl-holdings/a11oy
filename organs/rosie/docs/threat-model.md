# Threat Model — rosie Flagship
**Doctrine v11 LOCKED 749/14/163 | STRIDE/DREAD | Generated: 2026-06-03**  
**Review cadence:** Quarterly  
**Next review:** 2026-09-01

## Scope

The rosie HuggingFace Space and its GitHub-hosted source code under `szl-holdings/rosie`.

## Assets

| Asset | Sensitivity |
|-------|-------------|
| Doctrine parameters (749/14/163/c7c0ba17) | Critical |
| DSSE receipt signing keys | High |
| API endpoint contract | High |
| HF_TOKEN / GitHub PAT | Critical |
| User query inputs | Medium |

## Threat Categories (STRIDE)

### Spoofing
- **T-01**: Attacker impersonates doctrine endpoint → Return falsified doctrine version
  - *Mitigation*: DSSE-signed receipts on responses; Doctrine v11 hardcoded in source
  - *DREAD*: Damage=8, Reproducibility=5, Exploitability=4, Affected=7, Discoverability=6 → **DREAD=6.0**

### Tampering
- **T-02**: Commit that modifies DOCTRINE constant to a non-v11 value
  - *Mitigation*: Branch protection requires CI pass; doctrine-grep.yml blocks stale-version patterns
  - *DREAD*: D=9, R=4, E=3, A=9, D=5 → **DREAD=6.0**
- **T-03**: HF Space race condition overwrites correct serve.py
  - *Mitigation*: Lesson learned — use 5-min wait between same-Space pushes; git pull before commit
  - *DREAD*: D=7, R=6, E=6, A=8, D=4 → **DREAD=6.2**

### Repudiation
- **T-04**: Agent denies which commit introduced a doctrine violation
  - *Mitigation*: DCO trailers on every commit; GitHub audit log; Sigstore transparency log
  - *DREAD*: D=5, R=5, E=3, A=6, D=4 → **DREAD=4.6**

### Information Disclosure
- **T-05**: Secrets (HF_TOKEN, PAT) leaked in logs or responses
  - *Mitigation*: TruffleHog in HF repo; GitHub secret scanning enabled; tokens never logged
  - *DREAD*: D=9, R=3, E=4, A=8, D=3 → **DREAD=5.4**

### Denial of Service
- **T-06**: HF Space overwhelmed by requests → rate limit triggers cold restart
  - *Mitigation*: HF free-tier has built-in rate limiting; honest disclosure in SLO (cold start ≤ 120s)
  - *DREAD*: D=5, R=7, E=7, A=7, D=7 → **DREAD=6.6**

### Elevation of Privilege
- **T-07**: GHA workflow with write:packages scope runs attacker-controlled PR
  - *Mitigation*: Least-privilege GHA permissions (contents:read, security-events:write only for scan jobs)
  - *DREAD*: D=8, R=3, E=3, A=7, D=3 → **DREAD=4.8**

## Accepted Risks

| Risk | Reason Accepted |
|------|-----------------|
| SLSA L1 (not L2+) | Honest disclosure; keyless Sigstore signing is roadmap (Series-A) |
| No HSM for DSSE key | Founder decision; key rotation documented; ephemeral Fulcio certs cover builds |
| HF cold-start unavailability | Free-tier constraint; honest in SLO and HONEST_DISCLOSURE.md |

## Mitigations in Place

- Doctrine-grep CI blocks overclaims (higher SLSA tiers, restricted-program, compliance-cert)
- Branch protection on main (1 reviewer required on PRs)
- DCO enforcement via dco.yml
- TruffleHog on HF Space
- Section 889 compliance verified (5 vendors listed, no prohibited components)

**Signed-off-by: Yachay <yachay@szlholdings.ai>**  
**Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>**
