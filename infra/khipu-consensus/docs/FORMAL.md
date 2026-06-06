# Formal model (Lean 4)

The Khipu Consensus safety and liveness properties are formalised in
`szl-holdings/lutar-lean` as `Lutar/KhipuConsensus.lean`.

## Fully proved (no `sorry`)
- `validCount`, `faultyCount`, `honestCount` — decidable witness counting.
- `isCanonical` — the canonicity decision (`validCount ≥ threshold`).
- `validCount_le_n`, `faultyCount_le_n` — counts bounded by `n`.
- `isCanonical_iff` — canonicity ↔ threshold attainment.

## Conjectures (proof-deferred, tracked — NOT theorems)
- **Conjecture 2** `khipu_consensus_safety`:
  `validCount ≥ threshold ∧ faultyCount ≤ 1 → action ∈ canonicalHistory`.
- **Conjecture 3** `khipu_consensus_liveness`:
  `honestCount ≥ threshold → ∃ canonical, validCount canonical ≥ threshold`.

These are deliberate siblings of SZL's Λ Conjecture (Conjecture 1), which is
also never a theorem. The module introduces **no new axioms**
(`canonicalHistory` is an `opaque` definition) and adds exactly **two**
proof-deferred obligations.
