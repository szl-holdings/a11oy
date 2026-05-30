# Formula Gates — 30 New Anchor Policy Gates

**Author:** Lutar, Stephen P. — ORCID 0009-0001-0110-4173 — SZL Holdings  
**Generated:** 2026-05-29 (evening session)  
**Lean commit anchor:** `1dca00032dfc9aa8559cc6c2e4b63192fcf52371`  
**Zenodo concept DOI:** https://doi.org/10.5281/zenodo.20162352

---

## What this deliverable contains

This directory mirrors the `a11oy/packages/policy/src/gates/` target structure and provides
the 30 new policy gate files that extend a11oy#108 (`cursor/policy-gates-hardening-2f18`).

```
formula_gates_30/
├── packages/policy/src/gates/
│   ├── soundnessAxiom_gate.ts            (A1)
│   ├── moralGroundingFloor_gate.ts       (A2)
│   ├── measurabilityHonestyFloor_gate.ts (A3)
│   ├── dualWitnessDisjointness_gate.ts   (A4)
│   ├── deterministicReplay_gate.ts       (A5)
│   ├── hashChainIntegrity_gate.ts        (A6)
│   ├── bekensteinBound_gate.ts           (A7 — STAGED)
│   ├── ingestDiscipline_gate.ts          (A8)
│   ├── doctrineCompleteness_gate.ts      (A9)
│   ├── temporalConsistency_gate.ts       (A10)
│   ├── causalSeparability_gate.ts        (A11)
│   ├── constructiveTransparency_gate.ts  (A12)
│   ├── economicGrounding_gate.ts         (A14)
│   ├── rhoClosureComposition_gate.ts     (T1)
│   ├── lambdaMonotonicity_gate.ts        (T2)
│   ├── merkleDagBatch_gate.ts            (T3)
│   ├── bekensteinEntropyMeasure_gate.ts  (T4)
│   ├── replayDeterminism_gate.ts         (T5)
│   ├── conjunctiveGateCounterexample_gate.ts (T6)
│   ├── privacyMask_gate.ts               (T7)
│   ├── singleWitnessExclusion_gate.ts    (T8)
│   ├── crossRegionPolicy_gate.ts         (T9)
│   ├── doctrineEnforcement_gate.ts       (T10)
│   ├── composability_gate.ts             (TH1)
│   ├── replayDoiDuality_gate.ts          (TH2)
│   ├── anatomyReduction_gate.ts          (TH3)
│   ├── lambdaCategoryComposability_gate.ts (TH4 — STAGED)
│   ├── receiptChainConfluence_gate.ts    (TH5)
│   ├── bekensteinEntropyDpi_gate.ts      (TH6)
│   ├── curryHowardReceiptCalculus_gate.ts (TH7)
│   ├── lambdaUniqueness_gate.ts          (TH_L1)
│   ├── lambdaMinMaxBounds_gate.ts        (TH_L2)
│   ├── bekensteinSoundness_gate.ts       (TH_L3 — STAGED)
│   ├── rhoClosureProduction_gate.ts      (TH_L4)
│   ├── index.ts                          (barrel — all 35 gates)
│   ├── README.md                         (full formula table)
│   └── __tests__/
│       └── policy_gates_extended.test.ts (90 tests for 30 new gates)
└── FORMULA_GATES_30_README.md            (this file)
```

---

## TL;DR

**Gate files written:** 30 new gate files + 1 updated barrel `index.ts` = 31 files total.
The barrel also re-exports the 5 original gates from a11oy#108, for a complete 35-gate surface.

**Tests written:** 90 Vitest-compatible assertions in `policy_gates_extended.test.ts`
(3 per new gate: positive/allow, negative/deny, edge/boundary or throws-on-invalid-input).
The existing `policy_gates.test.ts` from a11oy#108 covers the original 5 gates.
Combined test surface: 90 + existing = complete gate coverage.

**Lean status breakdown (30 new gates):**
- Theorem (0 sorry in gate's own Lean file): 20 gates — A1–A6, A8–A9, A10–A12, A14, T1–T3, T5–T10, TH1–TH3, TH6–TH7, TH_L4
- Conjectured (pending Lean formalization): 4 gates — A7, T4, TH4, TH5
- Measured/empirical: 1 gate — TH_L4 (ρ-closure 100% on 8,000 calls, ouroboros v6.3.0)
- Measured/conjectured: 1 gate — TH_L3 (49.5% fire rate, pending PR #12)
- Theorem with 2 sorrys in wider Lean repo (not in gate file itself): 2 gates — TH_L1, TH_L2

**STAGED advisory labels applied to 4 gates:**

| Gate | Formula ID | Reason |
|---|---|---|
| `bekensteinBound_gate.ts` | A7 | conjectured; TH6 DPI formally discharges it but gate-level Lean file pending |
| `lambdaCategoryComposability_gate.ts` | TH4 | pending `Lutar/LaxFunctor.lean` |
| `bekensteinSoundness_gate.ts` | TH_L3 | pending `lutar-lean` PR #12 |
| `liuHuiPi_gate.ts` (a11oy#108) | Liu Hui | axiom-structured — advisory by original design |

These 4 gates default to `enforced: false` and emit `severity: 'warning'`.
Pass `{ enforced: true }` to promote any gate to blocking.

**How to wire to a11oy#108:**

```bash
# Inside the szl-holdings/a11oy repo, on branch cursor/policy-gates-hardening-2f18:
cp /home/user/workspace/szl/audit_2026-05-29_evening/formula_gates_30/packages/policy/src/gates/*_gate.ts \
   packages/policy/src/gates/

cp /home/user/workspace/szl/audit_2026-05-29_evening/formula_gates_30/packages/policy/src/gates/index.ts \
   packages/policy/src/gates/index.ts

cp /home/user/workspace/szl/audit_2026-05-29_evening/formula_gates_30/packages/policy/src/gates/README.md \
   packages/policy/src/gates/README.md

cp /home/user/workspace/szl/audit_2026-05-29_evening/formula_gates_30/packages/policy/src/gates/__tests__/policy_gates_extended.test.ts \
   packages/policy/src/gates/__tests__/policy_gates_extended.test.ts

# Run the full gate test suite
pnpm vitest run packages/policy/src/gates/__tests__/

# Commit with sign-off (Doctrine v6)
git add packages/policy/
git commit -s -m "feat(policy): add 30 anchor formula gates (A1-A14, T1-T10, TH1-TH7, TH_L1-TH_L4)"
```

**Pattern conformance:** Every gate file matches the `adversarialRobustness_gate.ts` pattern from a11oy#108:
- SPDX + ORCID header
- Named `export function <camelCase>Gate(config)(opts): Decision`
- JSDoc citing Lean theorem name, file, and commit SHA
- `leanCommitSha`, `rationale` (with `Lean:` reference), and `leanFile` in every return value
- TypeScript-strict (no `any` types)
- Under 120 lines per file
- Inline formula comment block

---

Source: `packages/a11oy-knowledge/src/{knowledge.json,theorems.ts,derivations.ts,proposed_axioms.ts}`
from `szl-holdings/a11oy@cursor/policy-gates-hardening-2f18`
