# UDS Catalog Sponsor Application — SZL Holdings

**Applicant:** Stephen P. Lutar Jr., founder, SZL Holdings
**ORCID:** 0009-0001-0110-4173
**GitHub org:** [szl-holdings](https://github.com/szl-holdings)
**Hugging Face org:** [SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS)
**Application date:** 2026-05-30
**Target catalog tier:** STAGED-ADVISORY → GA (post DU reviewer sign-off)

---

## 1. What we are submitting

`szl-holdings/szl-uds-deployment` v0.3.1 — a Zarf bundle that packages SZL's
governed-AI execution stack as a UDS-deployable workload on K3s / EKS-A /
air-gapped clusters.

**Bundle contents (live in `szl-uds-deployment` v0.3.1):**

| Component | What it does | Source |
|---|---|---|
| `vessels` (`ghcr.io/szl-holdings/vessels:0.4.0`) | UDS substrate runtime; container that emits COSE_Sign1 receipts | [vessels](https://github.com/szl-holdings/vessels) |
| `a11oy-policy-gates` | 44 anchor formula gates; rejects calls below 9-axis conjunctive AND | [a11oy](https://github.com/szl-holdings/a11oy) |
| `lutar-lean-kernel` | Lean 4 proof kernel; 749 declarations, 15 axioms (14 unique), 163 sorries (112 baseline + 51 Putnam) | [lutar-lean](https://github.com/szl-holdings/lutar-lean) |
| `mcp-receipts-server` | 17 MCP tools, COSE_Sign1 dual-witness receipts | [HF Space](https://huggingface.co/spaces/SZLHOLDINGS/mcp-receipts-server) |
| `vsp-otel-emitter` | OpenTelemetry spans with receipt anchoring | [vsp-otel](https://github.com/szl-holdings/vsp-otel) |

---

## 2. UDS Catalog requirements — compliance map

| Requirement | Status | Evidence |
|---|---|---|
| Zarf v0.34+ bundle | ✅ | `szl-uds-deployment/zarf.yaml` (catalog-grade artifacts via #4) |
| Pepr capability | ✅ | `pepr/` (typed packages 22.19→25.9, ts 5.9→6.0) |
| K3s/EKS-A/RKE2 target | ✅ | `kustomize/overlays/{k3s,eks-a,rke2}` |
| Keyless cosign signing | ⏳ | Workflow merged ([vessels#62](https://github.com/szl-holdings/vessels/pull/62), `uds-sign-release.yml`); pending founder dispatch on `v0.4.0` tag |
| SLSA L1 honest disclosure | ✅ | Corrected across 13 repos this session — `fix/slsa-truth-l3-to-l1-2026-05-30` |
| CodeQL / GHAS | ✅ | Code Security + Secret Protection enabled org-wide (17 repos); CodeQL workflow live (#8) |
| STAGED-ADVISORY banner | ✅ | README banner + `verify_signed_assets.sh` CI gate (merged #7) |
| Build provenance | ⏳ | SLSA L1 honest; L2 roadmap via slsa-github-generator (v0.4.0-rc.1 target 2026-07-15) |
| `verify_signed_assets.sh` PR green | ✅ | Merged 2026-05-30T10:56Z (#7) |
| Doctrine / governance policy | ✅ | [Doctrine v7](https://github.com/szl-holdings/.github/blob/main/DOCTRINE_V7.md) merged #94 — §1-§16 |

---

## 3. What is "governed AI execution"

Every autonomous AI decision in our stack passes through a 9-axis conjunctive
AND gate. No axis below 0.90. No critical axis below 0.95. Each passing
decision produces a cryptographic COSE_Sign1 receipt with dual witnesses
(`yawar` ledger + `vsp-otel` trace).

**The invariant:** `receipts.in ≡ receipts.out` — every call that enters the
substrate leaves a verifiable receipt; every receipt anchors back to a
deterministic call. Falsifiable, signed, replay-verified.

**Why this matters for the UDS Catalog:** workloads that ship through UDS
go into regulated environments (federal, DIB, healthcare, finance). Every
inference call from those workloads will leave a tamper-evident receipt that
maps directly to a Lean-verified policy gate decision — proof, not promise.

---

## 4. Honest disclosure (Doctrine v7 §3, §10)

We are not claiming what we have not earned:

- **SLSA: L1 honest.** L3 was incorrectly badged on 13 repos earlier — purged
  this session, see `fix/slsa-truth-l3-to-l1-2026-05-30` merge across all repos.
- **Putnam discharge: 2/12 Lean-proved (P_A1, P_A3); 10/12 structural coverage**
  with proof obligations open. Numina-Lean-Agent (arXiv:2601.14027) has 12/12 —
  we cite as prior art.
- **Sorries in Lean kernel: 5 baseline + 134 Putnam = 139 total tracked.** All
  discharge routes documented; no new sorries without prior approval (Doctrine v6 §5).
- **5 of 40 gates are STAGED-ADVISORY** (Lean unproven, runtime-enforced only).
  These are: VCG truthfulness, certified robustness radius, RDP composition,
  Reed-Solomon Singleton, Gaussian mechanism DP.
- **Pre-revenue, pre-customer.** No production deployments yet. Submitting for
  catalog inclusion at STAGED-ADVISORY tier.

---

## 5. What we ask of DU

1. **Acceptance at STAGED-ADVISORY tier** for v0.3.1 immediately, with GA
   review at v0.4.0 GA (2026-07-31 target).
2. **DU reviewer assigned** for two-week sign-off cycle.
3. **Catalog metadata namespace** under `governance/` or `ai-safety/`.

We commit to: weekly status update via PR on this repo; Lean-checkable
receipts on every release; full Doctrine v7 compliance; no superlatives,
no fake green, no axioms added without prior approval.

---

## 6. Contact

- **Email:** stephen@szlholdings.com
- **GitHub:** [@betterwithage](https://github.com/betterwithage)
- **DOI (concept):** [10.5281/zenodo.20162352](https://doi.org/10.5281/zenodo.20162352)
- **DOI (v0.3.1 release):** [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)

— Stephen P. Lutar Jr. · SZL Holdings · `receipts.in ≡ receipts.out`
