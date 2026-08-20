# Compliance & Security

SZL's compliance posture is stated **honestly** — what is true today, what is pending, and what
is a roadmap target. Overclaiming a security level is a [Doctrine v11](/doctrine/v11-v12)
sacred-axis violation (measurabilityHonesty, tripwire T02). This page is the authoritative
posture; where a repository badge disagrees, this page is correct.

## Supply-chain integrity

| Control | Status | Note |
|---------|--------|------|
| **SLSA level** | <span class="dot green"></span> **L1 (honest)** | Provenance is generated. **NOT** L3-verified. "SLSA L3" is a banned claim. |
| **cosign signing** | <span class="dot amber"></span> **PENDING** | Sigstore/cosign CI not yet wired. Receipts carry a real SHA-256 Merkle digest; the DSSE envelope is **`PLACEHOLDER`** (unsigned) until signing lands. |
| **SBOM** | <span class="dot green"></span> generated | SBOM workflow runs per repo. |
| **CodeQL** | <span class="dot green"></span> on every push | Security scanning to `main`. |
| **DCO** | <span class="dot green"></span> enforced | Developer Certificate of Origin on commits. |
| **OpenSSF Scorecard** | <span class="dot green"></span> 7.0 (a11oy, 2026-05-28) | [report](https://securityscorecards.dev/viewer/?uri=github.com/szl-holdings/a11oy) |

::: warning The single most important honesty disclosure
**SLSA is L1, not L3. cosign signing is PENDING.** Every Khipu receipt's `signature` field reads
`DSSE-PLACEHOLDER`. The hash *chain* is real and verified; the *signature* is not yet wired. Any
SZL surface claiming otherwise is wrong and violates T02.
:::

## Formal-verification posture

- **Kernel:** [`lutar-lean`](https://github.com/szl-holdings/lutar-lean) — at the v11 lock,
  <span class="locked">749 declarations</span> / <span class="locked">14 unique axioms</span> /
  <span class="locked">163 sorries</span>. Open goals are **`sorry`-tagged, never hidden**.
- **Λ-uniqueness** is [**Conjecture 1**](/doctrine/v11-v12#conjecture-1), *not* a theorem.
- The 13-axis governance score is a **decision aid**, not a proof of safety.

## Certification roadmap (targets, not held)

SZL holds **none** of the following today. They are architecture targets on the Series-A
roadmap; this site states the path, not a badge.

| Framework | Status | Architectural readiness |
|-----------|--------|-------------------------|
| **FedRAMP** | <span class="dot gray"></span> roadmap target | Air-gap + audit-trail design aligns to control families |
| **SOC 2** | <span class="dot gray"></span> roadmap target | Receipt ledger provides the evidence trail |
| **IL5** | <span class="dot gray"></span> roadmap target | Sovereign / air-gapped deployment model |
| **CMMC** | <span class="dot gray"></span> roadmap target | HUKLLA tripwires (T05–T08) map to access/egress controls |

## Security contact

Report vulnerabilities via the `SECURITY.md` of the relevant
[`szl-holdings`](https://github.com/szl-holdings) repository. Each flagship ships a `SECURITY.md`
with the coordinated-disclosure process.
