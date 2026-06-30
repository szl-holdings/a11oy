<!-- szl-investor-header -->
<div align="center">

# szl-doctrine

### The single source of truth for SZL's governance doctrine and the org-wide automation that keeps every repository honest and in compliance.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](LICENSE) [![Build](https://github.com/szl-holdings/szl-doctrine/actions/workflows/secret-health.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-doctrine/actions/workflows/secret-health.yml) [![Doctrine v11](https://img.shields.io/badge/Doctrine-v11_LOCKED-3b82f6?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine) [![SLSA](https://img.shields.io/badge/SLSA-L1_honest-22c55e?style=flat-square)](https://slsa.dev/spec/v1.0/levels)

[Docs](https://szl-holdings.github.io/docs-site) · [Quickstart](https://szl-holdings.github.io/docs-site/quickstart) · [SZL Holdings](https://a-11-oy.com)

</div>

## 💡 Why it matters

It locks the doctrine version every product builds against and runs the org-wide checks (secret health, governance workflows) so that no repo can silently drift from the published security and compliance posture.

## ▶️ Live demo

_Internal / private repository — no public demo surface. See [docs.szlholdings.com](https://szl-holdings.github.io/docs-site) for the public product walkthrough._

## ⚡ Quick start (30 seconds)

```bash
git clone https://github.com/szl-holdings/szl-doctrine.git
cd szl-doctrine
make quickstart   # or: see docs.szlholdings.com/quickstart
```

## 🔍 How it works

In two sentences: this component is part of SZL's governed-AI mesh — it enforces policy and emits signed, replayable audit receipts so every AI action can be verified after the fact. The full mathematical foundation, formal proofs, and protocol details are documented below and in the [technical docs](https://szl-holdings.github.io/docs-site).

---

<details>
<summary><strong>📐 Full technical detail, math, and proofs (the proof, not the pitch)</strong></summary>

# szl-doctrine — the org's governance contract + automation

`szl-doctrine` is the **single source of truth** for the version every SZL repository builds
against, plus the org-wide automation that keeps each repo honest. It is deliberately small,
auditable, and machine-enforced.

## What it pins

| Constant | Value | Why it is frozen |
|---|---|---|
| Doctrine version | **v11 LOCKED** | the published security/compliance contract |
| Locked kernel commit | [`c7c0ba17`](https://github.com/szl-holdings/lutar-lean/commit/c7c0ba17) | the exact Lean 4 kernel state the locked numbers were measured against |
| Locked numbers | **749 declarations / 14 unique axioms / 163 sorries** | a frozen contract — never edited to track live corpus drift |
| Λ status | **Conjecture 1 (NOT a theorem)** | unconditional uniqueness is machine-checked *false*; only conditional uniqueness is proven |
| Section 889 | exactly **5** banned vendors (Huawei, ZTE, Hytera, Hikvision, Dahua) | no inflation, no omission |
| Supply chain | **SLSA L1 honest**; L2 verified-provenance on roadmap | L3 / FedRAMP / Iron Bank / CMMC are **never** claimed |

> The *locked* numbers are a contract and do not move. The **experimental `main` corpus**
> (≈1323 decls / 23 axioms / CI-green) is reported **separately** and is **never folded into
> the 8 locked-proven formulas** {F1, F4, F7, F11, F12, F18, F19, F22}.

## What it automates (org-wide)

- **Secret-health workflow** (`.github/workflows/secret-health.yml`) — scheduled checks that no
  repo has leaked or expired credentials; fails loud rather than silently.
- **Governance / doctrine-drift checks** — verify that every product repo cites the *same*
  locked version, kernel commit, and honest SLSA posture, so no repository can quietly diverge
  from the published contract.
- **DCO enforcement** — every commit carries `Signed-off-by:` per the Developer Certificate
  of Origin.

## How a downstream repo consumes it

Product repos reference the locked constants in their README footers and `/healthz` payloads.
When the doctrine is re-locked at a new version, the constants are bumped **here first**, then
propagated; nothing downstream invents its own numbers.

## Honesty boundary

- Λ uniqueness is **Conjecture 1** — the unconditional claim is *false* by machine-checked
  counterexample; only the conditional CUT-2 slice-multiplicativity uniqueness
  (`lambda_unique_of_separable`, axiom-free, 0 sorry) is proven.
- Proved PURIQ formulas = **exactly 5**; the rest are roadmap.
- **No fabricated metrics, no inflated proof counts, no L2/L3/FedRAMP/Iron Bank/CMMC claims.**

</details>

<!-- szl-doctrine-footer -->

---

### Citation & doctrine

Cite this work via [`CITATION.cff`](CITATION.cff). Math foundations: [szl-papers](https://github.com/szl-holdings/szl-papers) · [lutar-lean](https://github.com/szl-holdings/lutar-lean) (kernel `c7c0ba17`).

<sub>Λ Conjecture 1 (not a theorem) · 749/14/163 v11 LOCKED (kernel `c7c0ba17`) · SLSA L1 honest · Section 889 = 5 vendors · [SZL Holdings](https://a-11-oy.com) · Apache-2.0 code · CC-BY-4.0 papers</sub>
