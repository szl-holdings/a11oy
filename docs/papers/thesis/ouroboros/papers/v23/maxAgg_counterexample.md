# The maxAgg Counterexample — Narrative of the A1–A5 Insufficiency

**SZL Holdings** · v23 draft companion to `cauchy_nd_progress.md` · CC BY 4.0
ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)

> This note tells the story of *why* Λ-uniqueness cannot close from A1–A5 alone. It is the
> mathematical heart of the `FACTORIZATION_AXIOM_GAP`. Λ stays **Conjecture 1**; v11 `749/14/163`
> @ `c7c0ba17` UNTOUCHED.

---

## 1. The hope, and the obstacle

The original program hoped that the five axioms — monotonicity (A1), positive homogeneity (A2),
diagonal normalization (A3), boundedness by the max (A4), and permutation invariance (A5) — would
pin the trust aggregator `Φ : (ℝ≥0)^k → ℝ≥0` to the geometric mean `Λ_k(x) = (∏ xᵢ)^{1/k}`. They do
not. There is a whole family of A1–A5 aggregators, and the geometric mean is only one member.

## 2. The witness: the maximum aggregator

Take `k = 2` and `maxAgg(x₀, x₁) = max(x₀, x₁)`. It passes every algebraic axiom:

- **A2 (homogeneous):** `max(c·x₀, c·x₁) = c·max(x₀, x₁)`. ✓ (`maxAgg_A2`, proven via `mul_sup`)
- **A3 (diagonal):** `max(c, c) = c`. ✓ (`maxAgg_A3`, proven via `sup_idem`)
- **A5 (symmetric):** `max(x₀, x₁) = max(x₁, x₀)`. ✓ (`maxAgg_A5`, proven via `sup_comm`)
- **A1 (monotone)** and **A4 (≤ max)** hold by `sup` monotonicity and reflexivity.

Yet at the single point `x = (4, 1)`:
\[
\mathrm{maxAgg}(4,1) = 4, \qquad \Lambda_2(4,1) = (4\cdot 1)^{1/2} = 2, \qquad 4 \ne 2.
\]
So `maxAgg ≠ Λ₂` (`maxAgg_ne_Lambda`, machine-checked). A second witness is `min` (the lower
idempotent aggregator). **A1–A5 do not force the geometric mean — this is proven, not conjectured.**

## 3. Why max/min evade uniqueness — the structural reason

`max` and `min` are **idempotent** and **non-separable**: they cannot be written as a product
`∏ xᵢ^{αᵢ}` for any exponents, because a product is *multiplicative across axes* while `max`/`min`
are not. They live outside the image of the factorization predicate `Factors`. The geometric mean is
*strictly internal* — it moves whenever any coordinate moves — whereas `max(t, 1)` is frozen at `1`
for all `t ≤ 1`. This is exactly the property captured by `IsCancellative` (each axis slice strictly
increasing on the positives), and it is exactly the property `max`/`min` fail.

## 4. What the missing axiom would be (and why we do not add it)

The classical theory (Aczél 1966; Kolmogorov 1930; Nagumo 1930; Hardy–Littlewood–Pólya 1934 §2.18)
says the property that forces the quasi-arithmetic / geometric form is **bisymmetry / associativity**:
\[
\Phi(\Phi(x_{11},x_{12}),\Phi(x_{21},x_{22})) = \Phi(\Phi(x_{11},x_{21}),\Phi(x_{12},x_{22})).
\]
This would be "A6". `max`/`min` are themselves bisymmetric, so bisymmetry alone is not the whole
story — it is bisymmetry **together with strict internality (cancellativity)** that excludes the
idempotent boundary and lands on the geometric mean once homogeneity (A2) fixes the generator.

**We deliberately do NOT add A6.** Adding it would push the unique-axiom count from 14 to 15 and
change the locked doctrine. Instead (Round 14, lutar-lean PR #183) we condition the theorem on the
*derived* predicate `IsCancellative` — a hypothesis on Φ, not an axiom — and prove
`lambda_unique_on_cancellative`. The axiom count stays **14**, and the maxAgg/min witnesses remain
the honest, machine-checked answer to the unconditional question: **no**.

## 5. Moral

The maxAgg counterexample is not a defect in the formalization — it is the *correct* mathematical
content. It converts a vague "we think Λ is unique" into a precise statement: *Λ is unique exactly on
the cancellative cone; on the idempotent boundary, max and min coexist with it.* Honesty here is the
result.

## References

- Aczél, J. (1966). *Lectures on Functional Equations.* Academic Press. Thm 5.1; §6.
- Burai, Kiss, Szokol (2021). *Characterization of quasi-arithmetic means without regularity condition.* Acta Math. Hungar. 165, 309–326. doi:[10.1007/s10474-021-01185-z](https://doi.org/10.1007/s10474-021-01185-z).
- Hardy, Littlewood, Pólya (1934). *Inequalities.* §2.18.
- Kolmogorov (1930), *Sur la notion de la moyenne*; Nagumo (1930), *Über eine Klasse der Mittelwerte*.
- Lean witnesses: `Lutar/Round13/Lambda_Uniqueness.lean` (`maxAgg_*`, `maxAgg_ne_Lambda`) and
  `Lutar/Round14/Strategy_B.lean` (`maxAgg_not_cancellative`), <https://github.com/szl-holdings/lutar-lean>.

---

Signed-off-by: Cauchy_ND Frontier (PhD-Math) <phd-math@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
