# A11oy

> Governed agentic execution fabric.

[![Docs CI](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml) [![CodeQL](https://github.com/szl-holdings/a11oy/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/szl-holdings/a11oy/actions/workflows/codeql.yml) [![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/szl-holdings/a11oy/badge)](https://securityscorecards.dev/viewer/?uri=github.com/szl-holdings/a11oy)
[![Status](https://img.shields.io/badge/status-alpha-C8B26A?style=flat-square)](#status) [![License](https://img.shields.io/badge/license-Proprietary-1F2937?style=flat-square)](./LICENSE) [![Security policy](https://img.shields.io/badge/security-policy-01696F?style=flat-square&logo=github&logoColor=white)](./SECURITY.md)
[![Runtime](https://img.shields.io/badge/runtime-ouroboros%20v6.3.0-2DA44E?style=flat-square)](https://github.com/szl-holdings/ouroboros) [![Runtime tests](https://img.shields.io/badge/runtime%20tests-218%2F218-2DA44E?style=flat-square)](https://github.com/szl-holdings/ouroboros) [![Thesis](https://img.shields.io/badge/thesis-v13%20published-805AD5?style=flat-square)](https://github.com/szl-holdings/ouroboros-thesis) [![Lean](https://img.shields.io/badge/Lean%204-kernel--verified-2D5BB9?style=flat-square&logo=lean&logoColor=white)](https://github.com/szl-holdings/lutar-lean) [![Runtime DOI](https://img.shields.io/badge/runtime%20DOI-10.5281%2Fzenodo.20162352-3b82f6?style=flat-square)](https://doi.org/10.5281/zenodo.20162352)
[![Thesis v13 DOI](https://img.shields.io/badge/thesis%20v13%20DOI-10.5281%2Fzenodo.20195368-805AD5?style=flat-square)](https://doi.org/10.5281/zenodo.20195368)

<p align="center">
  <img src="https://raw.githubusercontent.com/szl-holdings/.github/main/profile/screenshots/a11oy.jpg" alt="A11oy architecture" width="100%">
</p>


> **Companion to [ouroboros-thesis v13](https://doi.org/10.5281/zenodo.20195368)** — Implementation referenced in thesis v13 (DOI: 10.5281/zenodo.20195368).
A11oy sits between enterprise data and enterprise decisions. It routes every AI recommendation through Covenant Policy, manages approval queues, executes confirmed actions as audited workflows, and seals cryptographic proof records.

## What A11oy does

- **Policy-gated execution** — every action passes Covenant Policy before run.
- **Approval queues** — actor, order, and conditions are configurable per domain.
- **Durable workflows** — executions are recoverable, idempotent, and resumable.
- **Proof chain** — signal → recommendation → approval → execution → outcome, signed.
- **Domain-pack fabric** — the same engine drives every vertical surface.

## Architecture

A11oy is a domain surface on the SZL Holdings platform. Every action is routed through the same governed pipeline:

```
sense → structure → correlate → explain → recommend → approve → execute → proof
```

The execution fabric is [**A11oy**](https://github.com/szl-holdings/a11oy). The bounded-loop kernel underneath every domain pack is [**ouroboros**](https://github.com/szl-holdings/ouroboros) — implementing the [Lutar Invariant](https://github.com/szl-holdings/ouroboros-thesis) for measurable convergence with auditable closure.

## Historical Attribution

The QKAN-FWP sequence memory module in amaru (HEART organ) — integrating
quantum-inspired Kolmogorov-Arnold Networks with Fast Weight Programmers
[Peng et al. 2026, arXiv:2605.06734, DOI:10.48550/arXiv.2605.06734] — stands
in a lineage traceable to Feynman's 1982 proposal that quantum mechanical
systems are most efficiently simulated by quantum computers
[Feynman 1982, Int. J. Theor. Phys. 21:467, DOI:10.1007/BF02650179].

**QKAN-FWP is not a quantum simulator.** It is a quantum-inspired classical
approximator: it uses the mathematical formalism of variational quantum circuits
(rotation gates, data re-uploading) to parameterise sequence memory, and deploys
primarily as a classical computation. Feynman's 1982 intuition — that quantum
mechanical structure has computational implications — motivates the research
direction of quantum-inspired methods, of which QKAN-FWP is one instance.

The SZL governance stack uses QKAN-FWP for temporal context memory in the amaru
(HEART) organ. The Λ-Gate audit verdict is produced by the classical ouroboros
runtime; QKAN-FWP provides the sequence-level memory substrate that HEART
uses to retain governance-relevant state across multi-turn interactions.
This is a classical AI governance system that incorporates quantum-inspired
computational methods — not a quantum simulation system.

## Status

**Alpha.** A11oy is under active development as part of the SZL Holdings platform. Public releases are tagged via [GitHub releases](https://github.com/szl-holdings/a11oy/releases). Security disclosures: see [SECURITY.md](./SECURITY.md).

## Security & governance

- CI on every push and pull request
- CodeQL static analysis on the default branch and every PR
- OpenSSF Scorecard published weekly, score visible in the badge above
- Dependabot updates, weekly cadence, SHA-pinned actions
- Secret scanning and push protection enabled
- Branch protection: signed commits, required reviews, no force push, no deletion
- Reusable workflows pinned to commit SHAs ([szl-holdings/.github](https://github.com/szl-holdings/.github))

Report a security issue privately via [GitHub Security Advisories](https://github.com/szl-holdings/a11oy/security/advisories/new) or [stephen@szlholdings.com](mailto:stephen@szlholdings.com).

## Mechanisms it inherits

The a11oy surface inherits the same six machine-verified mechanisms as every other SZL surface:

| # | Mechanism | Where it's proven |
|---|---|---|
| I | Λ-gate (9-axis Lutar Invariant) | [`lutar-lean/Lutar/Invariant.lean`](https://github.com/szl-holdings/lutar-lean/blob/main/Lutar/Invariant.lean) |
| II | Receipt chain (signed bounded recursion) | [`szl-holdings/ouroboros`](https://github.com/szl-holdings/ouroboros) v6.2 substrate |
| III | Bekenstein gate (information-bounded admit) | Paper v11 §3.3 |
| IV | Dual-witness verdict (MATCH/DIVERGE) | Paper v11 §3.4 |
| V | Witness diversity (Gauss class-number gating) | Paper v12 §4 (in review) |
| VI | Reference-vector parity (bit-exact across runtimes) | [`RefVectors.lean`](https://github.com/szl-holdings/lutar-lean/blob/main/RefVectors.lean) |

Verified test counts: ouroboros runtime **218/218**; full platform monorepo **1,220 tests across 76 packages** (incl. MCP gateway 27/27 e2e). Paper line v1–v11 published on Zenodo (concept DOI [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)); v12 & v13 published (DOIs: [10.5281/zenodo.20173920](https://doi.org/10.5281/zenodo.20173920), [10.5281/zenodo.20195368](https://doi.org/10.5281/zenodo.20195368)).

## Citation

If you reference A11oy academically or in industry research, use the metadata in [`CITATION.cff`](./CITATION.cff).

## License

A11oy is proprietary. See [LICENSE](./LICENSE) and [NOTICE](./NOTICE). The underlying [ouroboros runtime](https://github.com/szl-holdings/ouroboros) is Apache-2.0 and the [Ouroboros Thesis](https://github.com/szl-holdings/ouroboros-thesis) is CC BY 4.0.

---

**[SZL Holdings](https://szlholdings.com)** · Founder & CEO **Stephen P. Lutar** · [stephen@szlholdings.com](mailto:stephen@szlholdings.com)

© 2024–2026 SZL Holdings. All rights reserved.
