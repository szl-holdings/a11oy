# anatomy-evolved-v1 — SZL Holdings Cookbook Recipe

**Tag:** `anatomy-evolved-v1`
**Date sealed:** May 18, 2026
**Author:** Stephen P. Lutar Jr., SZL Holdings
**ORCID:** [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)

## What this recipe contains

| File | Purpose |
|---|---|
| `thesis_ch9_anatomy_evolved_v1.md` | Chapter 9 — per-organ evolution, Lean obligations, Series A test evidence |
| `payloads/replit_anatomy_evolved_payload.md` | Operational code payload (3,735 lines, single-file Replit deployment) |
| `payloads/replit_thesis_injection_payload.md` | Formulas + dataset injection layer (2,511 lines) |
| `payloads/replit_explainer_agent_payload.md` | Explainer Agent module — explains every formula + organ delta (1,964 lines) |
| `code/` | The extracted TypeScript + Lean tree — `tsc --noEmit` clean, 25/25 smoke tests pass |

## Eight organs

a11oy · amaru · sentra · terra · vessels · counsel · carlota-jo · lutar-lean

## Series A acceptance evidence

- `tsc --noEmit` exit 0
- 25/25 smoke tests pass (see `code/tests/smoke.ts`)
- doctrine v6 ban-list runtime guard clean across the tree
- POVM completeness bug found and real-fixed (not bandaided) — see Chapter 9 §9.3.2

## Citations

- [arXiv:2605.06734](https://arxiv.org/abs/2605.06734) — Peng et al., Gated QKAN-FWP
- Bohr (1928), Nature 121:580–590
- [arXiv:quant-ph/9706009](https://arxiv.org/abs/quant-ph/9706009) — Cabello et al., KS-18
- Preskill (2015) Caltech Ch.3 — POVMs
- Fuchs & Schack (2013), Rev. Mod. Phys. 85:1693 — QBism

## Doctrine v6

This recipe enforces the v6 ban-list at boot via `carlota-jo-doctrine-guard.ts`. See [doctrine v6 DOI](https://doi.org/10.5281/zenodo.20174600).

*Stephen P. Lutar Jr. · SZL Holdings · stephen@szlholdings.com*
