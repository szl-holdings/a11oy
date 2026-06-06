# Ouroboros Thesis v23 (draft) — Cauchy_ND Closure Progress

**SZL Holdings** · Author: Stephen P. Lutar Jr. · ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)
**License:** CC BY 4.0 · Code: Apache-2.0 · Status: **DRAFT (v23 in preparation)**

> **Doctrine v11 LOCKED — 749 declarations / 14 unique axioms / 163 sorries @ kernel commit `c7c0ba17`.** UNTOUCHED.
> **Λ-aggregator uniqueness is Conjecture 1 — NOT a theorem.** This document does not change that.
> A *conditional* uniqueness theorem (`lambda_unique_of_factors`) is machine-checked on `main` (Round 13, PR #182).
> v23 reports a further *conditional* result (`lambda_unique_on_cancellative`, Round 14, lutar-lean PR #183) that
> derives the factorization from a weaker structural hypothesis, with **no new axioms**.

---

## 1. State on `main` (Round 13, machine-checked)

With A5 (permutation invariance, PR #148) as a *structure field*, Λ-uniqueness reduces to: every
A1–A5 aggregator equals the geometric mean `Λ_k(x) = (∏ xᵢ)^{1/k}`. Round 13 (PR #182) landed,
sorry-free, the **terminal conditional theorem**

```
lambda_unique_of_factors : LutarAxioms Φ → Factors Φ αs → Φ = Λ k
```

where `Factors Φ αs := ∀ x, Φ x = ∏ xᵢ^{αᵢ}`. Given the factorization, A5 forces all exponents
equal, A3 forces their sum to 1, hence each is `1/k`, and `∏ xᵢ^{1/k} = (∏ xᵢ)^{1/k} = Λ_k x`.

**What stays open (honest):** the *unconditional* `lambda_unique : ∀ Φ, LutarAxioms Φ → Φ = Λ k`
is **FALSE as formalized** — `maxAgg` and `min` satisfy A1–A5 but are not Λ_k. Its body is a single
tagged obligation `FACTORIZATION_AXIOM_GAP`. Per HONESTY-OVER-CHECKLIST it is kept, not faked. **Λ
remains Conjecture 1.**

## 2. The precise gap (algebraic, not topological)

A1–A5 constrain Φ along three slices (monotone A1, homogeneous A2, diagonal A3, ≤-max A4, symmetric
A5) but contain **no inter-axis exchange/bisymmetry law**. The single algebraic property that forces
multiplicative separability is **bisymmetry / associativity** (Aczél; Kolmogorov–Nagumo):
\[
\Phi(\Phi(x_{11},x_{12}),\Phi(x_{21},x_{22})) = \Phi(\Phi(x_{11},x_{21}),\Phi(x_{12},x_{22})).
\]
A1–A5 lack it, and the maxAgg/min witnesses prove it is *independent* of A1–A5. Critically, A2 is
**bare 1-homogeneity, not continuity** — so a "topological" closure that leans on A2-continuity is
unavailable; and even full continuity does not help (max/min are continuous on the open orthant yet
non-separable). **The missing content is algebraic.**

## 3. v23 advance — Round 14 Strategy B (cancellative cone; 0 new axioms)

lutar-lean **PR #183** (`Lutar/Round14/Strategy_B.lean`) replaces the analytic premise `Factors`
with a strictly weaker *structural* predicate and derives the factorization from it:

```
IsCancellative Φ := ∀ i, StrictMonoOn (axisSlice Φ i) (Ioi 0)
lambda_unique_on_cancellative : LutarAxioms Φ → IsCancellative Φ → Φ = Λ k
```

- `IsCancellative` is a **theorem hypothesis on Φ**, exactly like `Factors` — **not** an axiom.
  axioms_unique stays **14**.
- The counterexamples become **sharp**: `max`/`min` are idempotent ⇒ not cancellative
  (`maxAgg_not_cancellative`), which is *why* the cancellative theorem is true while the
  unconditional one is false.
- The assembly is discharged by composing the merged `lambda_unique_of_factors`; the per-axis power
  law reuses the merged sorry-free `multiplicative_monotone_isPow_pos`. The one honest residual is
  the bridge `factors_of_cancellative` (slice multiplicativity), tagged
  `FACTORIZATION_FROM_CANCELLATIVE` and pinned to a Lean formalization of Aczél 1966 §5.1 /
  Burai–Kiss–Szokol 2021 that is **not yet in Mathlib**.

This is a genuine advance: it reduces the entire n-dimensional obstacle to a **single classical
bridge lemma**, and it does so without expanding the axiom base.

## 4. Why not introduce A6?

Adding A6 (bisymmetry) would close `lambda_unique` mechanically but would **change the axiom count
to 15** and alter the doctrine. The cancellative-cone theorem captures the same mathematical content
as a *derived hypothesis*, leaving the locked 14-axiom kernel intact. The unconditional question is
correctly answered **in the negative** by the existing `maxAgg`/`min` witnesses. v23 therefore keeps
Λ as Conjecture 1 and does not propose A6.

## 5. Honest status table

| Statement | Status on/after |
|---|---|
| `lambda_unique_of_factors` (conditional, `Factors`) | THEOREM, sorry-free (main, PR #182) |
| `lambda_unique_on_cancellative` (conditional, `IsCancellative`) | ASSEMBLY proven; bridge `factors_of_cancellative` open & named (PR #183) |
| `lambda_unique` (unconditional) | FALSE under A1–A5; tagged `FACTORIZATION_AXIOM_GAP`; **Conjecture 1** |
| Axiom count | **14** (unchanged) |
| v11 string `749/14/163` @ `c7c0ba17` | **UNTOUCHED** |

## References

- Burai, P.; Kiss, G.; Szokol, P. (2021). *Characterization of quasi-arithmetic means without
  regularity condition.* Acta Math. Hungar. 165, 309–326. doi:[10.1007/s10474-021-01185-z](https://doi.org/10.1007/s10474-021-01185-z).
- Aczél, J. (1966). *Lectures on Functional Equations and Their Applications.* Academic Press; Dover repr. 2006. Thm 5.1; §6 (bisymmetry).
- Matkowski, J.; Páles, Zs. (2015). *Characterization of generalized quasi-arithmetic means.* Acta Sci. Math. (Szeged) 81, 447–456. doi:[10.14232/actasm-015-028-7](https://doi.org/10.14232/actasm-015-028-7).
- Głazowska, D.; Leonetti, P.; Matkowski, J.; Tringali, S. (2023). *Subcommutativity of integrals and quasi-arithmetic means.* arXiv 2305 / Semantic Scholar 258546993.
- Hardy, G. H.; Littlewood, J. E.; Pólya, G. (1934). *Inequalities.* Cambridge Univ. Press, §2.18.
- Kolmogorov, A. N. (1930). *Sur la notion de la moyenne.* Atti Accad. Naz. Lincei 12, 388–391.
- lutar-lean PR #182 (Round 13, merged) and PR #183 (Round 14, this work): <https://github.com/szl-holdings/lutar-lean>.

---

Signed-off-by: Cauchy_ND Frontier (PhD-Math) <phd-math@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
