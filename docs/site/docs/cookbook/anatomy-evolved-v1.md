# anatomy-evolved-v1

A sealed cookbook recipe documenting per-organ evolution with Lean obligations and Series-A test
evidence.

- **Tag:** `anatomy-evolved-v1`
- **Date sealed:** 2026-05-18
- **Author:** Stephen P. Lutar Jr., SZL Holdings — ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)
- **Source:** [`szl-holdings/szl-cookbook`](https://github.com/szl-holdings/szl-cookbook) → `recipes/anatomy-evolved-v1`

## Contents

| File | Purpose |
|------|---------|
| `thesis_ch9_anatomy_evolved_v1.md` | Chapter 9 — per-organ evolution, Lean obligations, Series-A test evidence |
| `payloads/replit_anatomy_evolved_payload.md` | Operational code payload (3,735 lines, single-file deploy) |
| `payloads/replit_thesis_injection_payload.md` | Formulas + dataset injection layer (2,511 lines) |
| `payloads/replit_explainer_agent_payload.md` | Explainer Agent — explains every formula + organ delta (1,964 lines) |
| `code/` | Extracted TypeScript + Lean tree — `tsc --noEmit` clean, 25/25 smoke tests pass |
| `code/lean/GatedBoundedness.lean` · `TwoWitness.lean` | Lean obligations for the recipe |

## Eight organs covered

`a11oy` · `amaru` · `sentra` · `terra` · `vessels` · `counsel` · `carlota-jo` · `lutar-lean`

## Series-A acceptance evidence

- `tsc --noEmit` exit 0.
- 25/25 smoke tests pass (`code/tests/smoke.ts`).
- Doctrine ban-list runtime guard clean across the tree (`carlota-jo-doctrine-guard.ts`).
- POVM completeness bug found and **real-fixed** — not bandaided — see Chapter 9 §9.3.2.

## Citations

- [arXiv:2605.06734](https://arxiv.org/abs/2605.06734) — Peng et al., Gated QKAN-FWP.
- Bohr (1928), *Nature* 121:580–590.
- [arXiv:quant-ph/9706009](https://arxiv.org/abs/quant-ph/9706009) — Cabello et al., KS-18.
- Preskill (2015), Caltech Ch. 3 — POVMs.
- Fuchs & Schack (2013), *Rev. Mod. Phys.* 85:1693 — QBism.

> This recipe enforces the doctrine ban-list at boot via `carlota-jo-doctrine-guard.ts`. The
> recipe pre-dates the v11 lock and references the then-current doctrine version; the ban-list
> mechanism (no overclaim, no hidden `sorry`) is the same one now formalised as the
> [Sumaq honest-proof factor `S(a)`](/anatomy/#sumaq).
