To: catalog@defenseunicorns.com (or whatever address DU lists for catalog sponsorship)
CC: stephen@szlholdings.com
From: stephen@szlholdings.com
Subject: UDS Catalog sponsor application — SZL Holdings (governed AI execution, v0.3.1)

Hi DU team,

I'm Stephen Lutar, founder of SZL Holdings. I'm submitting `szl-uds-deployment`
v0.3.1 for the UDS Catalog at STAGED-ADVISORY tier.

The bundle packages our governed-AI execution stack: every inference call
passes through a 9-axis conjunctive AND policy gate (44 anchor formula gates,
35 Lean-proved, 5 STAGED-ADVISORY) and produces a COSE_Sign1 receipt with
dual witnesses. Built on Zarf, Pepr, K3s/EKS-A/RKE2 targets.

What is ready for review today (release tag `v0.3.1` pushed
2026-05-30T11:00 UTC, https://github.com/szl-holdings/szl-uds-deployment/releases/tag/v0.3.1):

- 44 anchor formula gates — see merged a11oy#140 (G1-G35) +
  a11oy#135 (G36-G40)
- `verify_signed_assets.sh` CI gate live — merged szl-uds-deployment#7
- STAGED-ADVISORY banner on Kubernetes artifacts
- SLSA L1 honest disclosure (we found and corrected fake L3 badges on 13
  repos earlier this session — full audit trail at
  https://github.com/szl-holdings/.github/blob/main/SLSA_L3_TRUTH_CORRECTION.md — fake-badge-correction, roadmap)
- Doctrine v7 merged (8 new clauses §9-§16 including human-on-record
  protection-toggle requirement)

What is still pending and what I'm honest about:

- vessels v0.4.0 GHCR image push + cosign sign — owner-side action,
  workflow merged (vessels#62), targeting this week
- SLSA L1 (honest) build provenance — L2 roadmap via slsa-github-generator adoption,
  v0.4.0-rc.1 target 2026-07-15
- DU reviewer sign-off — what I'm asking you for

The full application is at:
https://github.com/szl-holdings/szl-uds-deployment/blob/main/CATALOG_SPONSOR_APPLICATION.md
(I'll PR it into the repo as soon as I send this).

I'm submitting at STAGED-ADVISORY because we are pre-revenue, pre-customer
and I do not want to overclaim. We are not in production anywhere. We are
asking for catalog inclusion so the deployment path becomes legible to
operators who want to evaluate.

Lean 4 kernel state is documented honestly:
- 626 declarations / 15 axioms (14 unique) / 189 sorries (138 baseline + 51 Putnam)
- 2/12 Putnam Lean-discharged (P_A1, P_A3) — Numina-Lean-Agent (arXiv:2601.14027)
  has 12/12, we cite as prior art

Happy to do a screen-share walkthrough at your convenience. I'm in the
Eastern timezone (NYC) and can work any time slot you propose.

Verifiable identity:
- ORCID 0009-0001-0110-4173 (https://orcid.org/0009-0001-0110-4173)
- DOI (concept) 10.5281/zenodo.20162352
- HF org https://huggingface.co/SZLHOLDINGS

Thanks for your time and for what you've built with UDS.

— Stephen P. Lutar Jr.
SZL Holdings · stephen@szlholdings.com
`receipts.in ≡ receipts.out`
