# Λ specification — source of truth

**Status:** canonical. Supersedes any prior or differing definition in code.
**Authority:** Thesis v14 §3.3 (Definition 2 + Theorem 1); `lutar-lean/Lutar/Invariant.lean`; `lutar-lean/Lutar/Uniqueness.lean`.
**Concept DOI:** [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926).

This document resolves the dual-definition inconsistency in which
`ouroboros/runtime/lambda-gate/src/gate.ts` computed `lambda = min(axes)`
while `platform/packages/ouroboros-guardrails/src/lambda.ts` computed
`lambda = (∏ aᵢ)^(1/k)`. The two are different functions; both cannot be Λ.

## 1. The Lutar Invariant Λ — definition

For an axes vector `x = (x₁, …, x_k) ∈ [0,1]^k`,

```
Λ_k(x) = (∏_{i=1..k} x_i)^(1/k)
```

i.e. the **unweighted geometric mean** (equivalent to the weighted geomean
with all weights equal to the Egyptian unit fraction `1/k`).

This is the function defined in `lutar-lean/Lutar/Invariant.lean:21` as
`noncomputable def Λ (k : ℕ) (x : Axes k) : NNReal`.

**Boundary cases:**

- If any `x_i = 0` then `Λ_k(x) = 0`.
- If every `x_i = 1` then `Λ_k(x) = 1`.
- For `k = 0` the convention `Λ_0 = 0` is taken (no axes means no signal).

## 2. The Λ-gate verdict (separate from Λ)

The thesis §3.3 Definition 2 defines the **gate verdict** as a Boolean
`{0,1}` predicate, not as the scalar Λ. The verdict is the conjunctive AND:

```
gateVerdict(x) = 1   iff   ∀ i ∈ {1..k}.  x_i ≥ θ_i
```

where the per-axis thresholds are

- `θ_i = 0.95` for `i ∈ {moralGrounding, measurabilityHonesty}` (critical axes)
- `θ_i = 0.90` for all other axes.

The scalar Λ and the verdict are **distinct artefacts**. Both ship in
every receipt. The gate verdict is what admits or refuses; Λ is the
interpretable scalar that lives in the receipt, ranks decisions, and
participates in monotonicity / bound theorems.

A receipt is admitted if and only if **both**:

1. `gateVerdict(axes) = 1` (every axis meets its threshold), and
2. `Λ_k(axes) ≥ Λ_threshold` (composite threshold; default `0.90`).

These two conditions are not equivalent. Either alone is insufficient:

- Condition (1) alone admits axes-vectors with a near-zero composite Λ if
  thresholds are tuned loose; condition (2) alone admits a vector where
  one critical axis dips below its `θ_i` but the others compensate in
  the geomean.

## 3. Why geomean (not MIN) is the canonical Λ scalar

Both prior implementations made internally consistent local choices but
disagreed on the *name*. The Lean uniqueness theorem
(`Lutar.Uniqueness.lutar_is_geomean`) commits the codebase to the
geomean as the unique function satisfying A1–A4. The argument:

- **A1 (monotonicity).** Both `min` and geomean are monotone. ✓ for both.
- **A2 (homogeneity).** `Λ(λx) = λ Λ(x)` requires
  `(∏ λx_i)^(1/k) = λ^(k/k) (∏ x_i)^(1/k) = λ · (∏ x_i)^(1/k)`. ✓ for geomean.
  `min(λx) = λ · min(x)`. ✓ for min (when λ ≥ 0).
- **A3 (Egyptian-exactness).** Λ is expressible as a sum of distinct unit
  fractions of weight: geomean uses `w_i = 1/k` for all `i`, which is the
  trivial Egyptian decomposition (single repeated unit fraction). MIN is
  not weighted at all — it discards (k−1) of k axes — so it does not
  satisfy A3 in any non-trivial sense.
- **A4 (bounded).** `0 ≤ Λ ≤ 1` for both.

A3 is the discriminating axiom. The thesis Theorem 1 (Uniqueness)
states: under A1+A2+A3+A4, Λ is the weighted geomean. MIN fails A3.
Therefore MIN is not Λ.

(`Lutar.Uniqueness` currently postulates this via an `axiom` declaration
rather than discharging the full deductive proof — see the file's
honesty note. That is a separate open task; it does not affect which
definition is canonical, only the formalisation strength of the
characterisation.)

## 4. Gate predicate vs MIN

The MIN-fold formerly in `gate.ts` corresponds to the **strongest
single-axis lower bound** `m(x) = min_i x_i`. It satisfies the trivial
identity `gateVerdict(x) = 1 iff m(x) ≥ θ_*` only when all axes share a
common threshold `θ_*`. In our system thresholds differ across axes (0.95
for critical, 0.90 otherwise), so `m(x) ≥ θ_*` is neither necessary nor
sufficient for `gateVerdict = 1` — concretely, if `moralGrounding = 0.93`
and every other axis is `0.91`, then `m(x) = 0.91 ≥ 0.90` but the
critical-axis threshold fails.

Therefore the MIN-fold is **not** a substitute for either:

- the gate verdict (which respects per-axis thresholds), or
- the Λ scalar (which carries the geomean's interpretability and the
  uniqueness theorem).

It is, however, useful as a **diagnostic**: `min_axis = m(x)` reports
the weakest axis and helps explain a refusal. The unified API exposes
it under that name.

## 5. Bound theorem (TH11)

For all `x ∈ [0,1]^k` and `k ≥ 1`:

```
min_i x_i  ≤  Λ_k(x)  ≤  max_i x_i
```

This is the AM-GM corollary in `Lutar.Bound.lean` (`min_le_Λ`, `Λ_le_max`,
currently postulated; see the file's status note). The bound is
non-trivial: it says the geomean is *interpretable* — never above the
best axis, never below the worst.

For MIN this would degenerate (`min(x) ≤ min(x) ≤ max(x)`), which is
why MIN does not carry the same theorem.

## 6. ρ-closure

ρ-closure (thesis §3.5) is the dual-witness equivariance relation. It is
*defined over the gate verdict*, not over the Λ scalar: two witnesses
must produce the same `{0,1}` admit/refuse decision on the same
canonicalised input. The 8,000/8,000 closure result
([zenodo.20119582](https://doi.org/10.5281/zenodo.20119582)) is therefore
**unaffected** by the unification — both witnesses run the same
`evaluateAxes` predicate, which now exposes both `lambda` (geomean) and
`gateVerdict` (per-axis AND) on its result; ρ-equivalence checks the
verdict, which is the same Boolean it always was.

## 7. Implementations after unification

Both implementations now return the geomean as the scalar Λ:

| Repo / module                                              | Λ scalar              | Gate verdict                          |
|------------------------------------------------------------|-----------------------|---------------------------------------|
| `ouroboros/runtime/lambda-gate/src/gate.ts`                | geomean (`computeLambda`) | `evaluateAxes` per-axis AND (was already correct) |
| `platform/packages/ouroboros-guardrails/src/lambda.ts`     | geomean (`lambdaScore`)   | unchanged                              |
| `platform/packages/ouroboros-invariant/src/lutar-invariant-9.ts` | geomean (`lutarInvariant9`) | n/a (pure invariant)                   |

The previous MIN-fold is retained inside `gate.ts` as `weakestAxis()`, a
diagnostic helper, so callers that want to display "the failing axis"
can still get it. The semantic gate verdict is unchanged: it remains the
conjunctive AND over per-axis thresholds.

## 8. References

- Thesis v14 §3.3, Definition 2 + Theorem 1: `arxiv_pkg_v14/main.tex.md` lines 165–177.
- Lean canonical Λ definition: `lutar-lean/Lutar/Invariant.lean:21`.
- Lean uniqueness postulate: `lutar-lean/Lutar/Uniqueness.lean:44`.
- Lean bound postulates: `lutar-lean/Lutar/Bound.lean:37`.
- Egyptian unit-fraction inspectability (A3): `Lutar.Egyptian.lean`, fully closed.
- ρ-closure operational semantics: `ouroboros/runtime/closure/src/closure.ts`.
- 8,000/8,000 closure measurement: [zenodo.20119582](https://doi.org/10.5281/zenodo.20119582).
