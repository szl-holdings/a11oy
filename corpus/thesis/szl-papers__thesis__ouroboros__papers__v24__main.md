# The Ouroboros Thesis

### Axiom-Free Conditional Uniqueness of the Lutar Invariant: A Machine-Verified Trust Foundation for Governed Agentic AI

**Thesis v24.1 "Axiom-Free Conditional Uniqueness" — SZL Holdings**

**Author:** Stephen P. Lutar Jr. · SZL Holdings · ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)

**Concept DOI (always-latest):** [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)

> This markdown file is a faithful rendering of `main.tex`. The typeset PDF (`main.pdf`) is the canonical presentation; `main.tex` is the authoritative LaTeX source. v24.1 refreshes v24 to the current proof state. Pinned commits: `main` @ `ba1050b7` (Waves 11–22 merged, CI-green); locked kernel @ `c7c0ba17`. Repository: [github.com/szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean).

---

## Abstract

Governed deployment of agentic artificial intelligence in regulated and defense settings requires more than benchmark accuracy: it requires *checkable* guarantees about what a system did, why it was permitted to do it, and whether the record can be tampered with after the fact. This is **v24** of the Ouroboros thesis program of SZL Holdings, a DOI-pinned lineage (v1–v23) whose subject is a machine-verified trust substrate resting on three pillars: (i) the *Ouroboros loop*, a bounded, well-founded self-governing computation in which "the loop is the product"; (ii) the *Lutar invariant* Λ_k(x) = (∏_{i=1}^k x_i)^{1/k}, an equal-weight geometric-mean trust aggregator; and (iii) a *proof-trail / receipt architecture* formalized in Lean 4.

The headline advance of v24 is an **axiom-free conditional Λ-uniqueness theorem**. In v23 the conditional uniqueness of Λ was gated on a *declared* project axiom (A6′ block-consistency). Here we report `Lutar.Round13.lambda_unique_of_separable`: under {A1, A2, A3, A5} together with *slice-multiplicativity* (separability), Λ is the unique aggregator, with `#print axioms = {propext, Classical.choice, Quot.sound}` — i.e. **no project axiom**, kernel-clean, CI-green, present at `main` `ba1050b7` (originally merged at `b910c276`). This strictly strengthens v23: the extra hypothesis is now a *checkable property of* Φ (weaker than the old *Factors* premise) discharged through Mathlib and already-proved in-tree lemmas, rather than a declared idealization.

The further advance reported in this revision (**v24.1**) is that **CUT-1 — the Aczél quasi-arithmetic *representation* theorem — is now fully closed on its stated, checkable hypotheses** (§4.7). Across Waves 18–22 the forward representation is constructed end to end: a Burai–Kiss–Szokol (BKS) density engine (Wave 19), the perfect-set/uncountability residual closed via monotone extension (Wave 21), and — decisively — the (C-order) gap-shift ordering *derived* rather than assumed (Wave 22; BKS arXiv:2208.07083, Fourth-step eqs. 8–9). The consequence is `cut1_sharp_conditional_lambda`: the *conditional* Λ-uniqueness chain is now axiom-clean end to end on its stated checkable hypotheses {A1–A5} + separability + slice-multiplicativity + slice-monotonicity (bisymmetry dropped as redundant; unit-normalization dropped). This **strengthens the conditional result**; it does **not** make Λ unconditional.

Crucially, the *unconditional* uniqueness of Λ under {A1–A5} remains machine-checked **false** (in-tree `maxAgg_ne_Lambda`; `maxAgg` and `min` are A1–A5 counterexamples), so Λ stays **Conjecture 1** unconditionally — never a theorem; CUT-1 does not, and cannot, change that. We also report a separate *experimental, CI-green* tier of ~185 kernel-clean frontier theorems across Waves 11–22 (CF-13, CF-17, Wave-13 results, the Wave-14 pack CF-18/19/20/21, the CF-22/23/24/25/26/27/28 advances, and the Wave 18–22 CUT-1 construction), all `#print axioms`-clean, that is never folded into the locked-five. The honesty doctrine is binding throughout: locked-proven = exactly five {F1, F11, F12, F18, F19}; declared axioms disclosed; supply-chain posture SLSA L1 honest with L2 build-attestation present (L2-verified, L3, FedRAMP, Iron Bank, CMMC remain roadmap; correcting a v23 overstatement); nothing fabricated. We argue that replacing a declared axiom with a checkable property is an *epistemic upgrade*, and that this calibrated honesty is what makes every positive claim credible to an auditor.

**Honesty note (verbatim).** The Lutar invariant Λ is **Conjecture 1** unconditionally and is *never* claimed proven unconditionally; unconditional uniqueness under A1–A5 is machine-checked *false*. The v24 conditional uniqueness theorem `lambda_unique_of_separable` holds under {A1,A2,A3,A5} + slice-multiplicativity with **no project axiom** (`#print axioms = {propext, Classical.choice, Quot.sound}`). **CUT-1 is fully closed on its stated hypotheses**: this means the quasi-arithmetic *representation* theorem is complete and it *strengthens the conditional* Λ-uniqueness result — it does **not** make Λ unconditional; the unconditional conjecture stays open/false. Locked/proven = exactly five formulas {F1,F11,F12,F18,F19} at `c7c0ba17`. The experimental CI-green tier (~185 kernel-clean thms; drift 1323 decl / 23 axioms / 307 sorries at `ba1050b7`) is a *separate* tier and is never folded into the locked-five. SLSA **L1 honest, L2 build-attestation present** — L2-verified, L3, FedRAMP, Iron Bank, and CMMC remain roadmap. No fabricated results; no fake citations; 0 runtime CDN.

**Keywords:** governed agentic AI, trust aggregation, Lutar invariant, geometric mean, slice-multiplicativity, functional-equation uniqueness, Lean 4, Mathlib, axiom-free verification, `#print axioms`, receipt chain, SLSA, Byzantine consensus, philosophy of mathematics.

---

## 1. Introduction

The deployment of agentic AI into regulated industries (finance, healthcare) and defense settings has exposed a gap that benchmark performance cannot close: a *trust* gap. A regulator, an auditor, or a defense customer does not principally ask "how accurate is the model?"; they ask "what did the system do, under what authority, and can you prove the record has not been altered?" Answering those questions requires an artifact distinct from a model — a **trust substrate**: machinery that (a) governs what the agent is permitted to do, (b) aggregates evidence of trustworthiness into an auditable verdict, and (c) maintains a tamper-evident record of every governed decision.

This paper is v24 of a DOI-pinned thesis program SZL Holdings has developed across versions v1–v23, refreshed in this revision (**v24.1**) to the *current* proof state at `main` `ba1050b7`. The defining commitment is an **honesty doctrine** (§2): we never let an engineering aspiration masquerade as a theorem. The headline of v24 is a single, sharp advance over v23; v24.1 adds the **CUT-1 closure** (§4.7). v23's strongest Λ-uniqueness result was *conditional* and *gated on a declared project axiom*: `lambda_unique_under_block`, which assumed a named `A6'_block_consistent` idealization. The headline of v24 is that this gate can be removed. The in-tree theorem

```
Lutar.Round13.lambda_unique_of_separable
```

proves Λ-uniqueness *conditional* on {A1, A2, A3, A5} together with *slice-multiplicativity* (separability), and its trusted base is exactly the Lean core: `#print axioms = {propext, Classical.choice, Quot.sound}` — **no project axiom**. It is kernel-clean, CI-green, and present at `main` `ba1050b7` (originally merged at `b910c276`). This *strictly strengthens* v23: the extra hypothesis is now a *checkable structural property of* the candidate aggregator Φ — and one weaker than the old *Factors* premise — discharged through Mathlib and already-proved in-tree lemmas, rather than a disclosed-but-unprovable idealization. We characterize this as an *epistemic upgrade* (§9).

**What does *not* change.** The single most important honest statement in this program is unchanged and we repeat it without softening: the *unconditional* uniqueness of Λ under {A1–A5} is machine-checked **false**. The in-tree witness `maxAgg_ne_Lambda` exhibits concrete A1–A5 aggregators (`maxAgg` and `min`) that differ from Λ. We therefore label Λ **Conjecture 1** unconditionally — never a theorem — exactly as v23 did. v24 does not, and never will, claim otherwise, and the v24.1 CUT-1 closure (§4.7) — which completes the quasi-arithmetic *representation* theorem and sharpens the *conditional* uniqueness chain — does not change this verdict either.

---

## 2. The honesty doctrine

The doctrine is load-bearing and is preserved verbatim across all SZL artifacts. It defines epistemic tiers, and every claim in this paper is tagged with exactly one:

- **[locked / kernel-verified]** — proven in Lean 4 with only the trusted core axioms {propext, Classical.choice, Quot.sound}; sorry-free; pinned at a fixed commit and part of the *locked* count. Locked-proven = exactly five.
- **[experimental, axiom-free, CI-green]** — proven sorry-free with only the trusted core axioms, CI-green at the recorded commit, but residing in the *experimental* tier and **never folded into the locked count**.
- **[axiom-gated]** — sorry-free *given* an explicitly declared, disclosed idealizing axiom (e.g. hash collision-resistance), with the axiom appearing in the `#print axioms` ledger.
- **[CI-pending]** — signature-checked but not reproducibly green in the wired build; **not** claimed proven.
- **[machine-checked FALSE]** — the statement is refuted by a machine-checked counterexample.
- **[Conjecture 1 — NOT a theorem]** — a research hypothesis. Λ's unconditional uniqueness lives here.

**Non-negotiable rules.**
1. **Λ is Conjecture 1 unconditionally** — never claimed proven unconditionally. Unconditional uniqueness under A1–A5 is machine-checked **false**.
2. **Locked-proven = exactly five** {F1, F11, F12, F18, F19} at `c7c0ba17` (749 decl / 14 axioms / 163 sorries). The experimental CI-green tier (~185 kernel-clean thms; drift 1323/23/307 at `ba1050b7`) is a separate tier, never folded in.
3. **All axioms are disclosed** via `#print axioms`. No fabricated results; no fake citations; 0 runtime CDN.
4. **SLSA L1 honest, L2 build-attestation present** — L2-verified, L3, FedRAMP, Iron Bank, and CMMC remain roadmap (correcting a v23 overstatement; see §7.4).
5. **CUT-1 is precisely scoped.** "Fully closed on its stated hypotheses" means the quasi-arithmetic *representation* theorem is complete and it *strengthens the conditional* Λ-uniqueness result. It does **not** make Λ unconditional; the unconditional conjecture stays open/false (Conjecture 1).
6. Open sorries are disclosed; only kernel-verified results are stated as proven, everything else is explicitly tiered.

---

## 3. The Ouroboros loop: bounded self-governance

The first pillar is a self-referential governed computation — the *Ouroboros loop* — in which the system's output feeds its own governance input under a bounded, well-founded recursion. "The loop is the product": the governed loop, not a single inference, is the unit of value. Termination is guaranteed by a well-founded measure; self-reference is rendered coherent by **Tarskian stratification** (a governed object-level computation is audited by a strictly higher meta-level), avoiding the self-verification paradoxes of Gödel/Tarski. The bottom turtle — the Lean kernel, the cryptographic idealizations, and human sign-off — is finite and disclosed (Appendix A.3).

---

## 4. The Lutar invariant Λ and its uniqueness boundary

### 4.1 Definition and the aggregation axioms

**Definition (Λ).** For x ∈ [0,1]^k, the Lutar invariant is the equal-weight geometric mean Λ_k(x) = (∏_{i=1}^k x_i)^{1/k}.

The candidate aggregators Φ : [0,1]^k → [0,1] are constrained by five axioms:

- **(A1) Monotonicity** — Φ is nondecreasing in each argument.
- **(A2) Positive homogeneity** — on the ratio scale, Φ(λx) = λ Φ(x) for λ > 0.
- **(A3) Idempotence** — Φ(c, …, c) = c.
- **(A4) Boundedness** — min_i x_i ≤ Φ(x) ≤ max_i x_i.
- **(A5) Permutation-invariance** — Φ is symmetric in its arguments.

### 4.2 The unconditional refutation: FALSE, machine-checked

It is tempting to claim Λ_k is the *unique* Φ satisfying A1–A5. **This is false, and we prove it false.**

**Theorem 4.2 (Refutation of unconditional uniqueness). [machine-checked FALSE] [CI-green]** There exists Φ ≠ Λ_k satisfying A1–A5. In particular the max-aggregator maxAgg(x) = max_i x_i satisfies A1–A5 yet differs from Λ_k: at (4, 1) (on the ratio scale) one has maxAgg = 4 while Λ_2(4, 1) = 2. The minimum aggregator min_i x_i is a second witness.

*Lean reference.* The in-tree witness is `Round13.maxAgg_ne_Lambda`. The max function is monotone (A1), positively homogeneous (A2), idempotent (A3), bounded by itself hence ≤ max (A4), and symmetric (A5); evaluation at (4, 1) separates it from the geometric mean by `decide`. `#print axioms maxAgg_ne_Lambda` reports Lean-core axioms only. `min` is an analogous `decide`-checked companion.

This is the epistemic heart of the program: we did not merely *fail* to prove unconditional uniqueness; we proved its **negation**. Consequently Λ remains Conjecture 1 unconditionally (§4.5).

### 4.3 The old route: uniqueness given factorization, and the A6′ gate

The maximal honestly-true uniqueness statement of the prior lineage was conditional on factorization, fully proved in-tree.

**Theorem 4.3 (Uniqueness given factorization). [experimental, axiom-free, CI-green]** Let Φ satisfy A1–A5 and suppose Φ *factors*: there exist exponents α_1, …, α_k ≥ 0 with Φ(x) = ∏_i x_i^{α_i} for all x. Then Φ = Λ_k.

*Lean reference and sketch.* The Lean term is `lambda_unique_of_factors` (Round-13). Given factorization, idempotence (A3) forces ∑_i α_i = 1 and symmetry (A5) forces all α_i equal, whence α_i = 1/k and Φ = Λ_k. The exponent collapse uses `NNReal.rpow` arithmetic and a `Finset` induction; the companion `lambda_factors` (axiom-free, CI-green) shows Λ_k itself factors with exponents 1/k, so the hypothesis is non-vacuous.

In v23 the substrate's recommended route turned the opaque factorization hypothesis into a governance-legible declared axiom.

**Axiom 6 (Block-consistency / aggregation-invariance, A6′).** Aggregating evidence within independent blocks and then across the block results equals aggregating the flattened collection; equivalently, the verdict is invariant to how the auditor partitions evidence into review blocks (after Csátó 2018).

**Theorem 4.4 (v23 conditional uniqueness under declared A6′). [axiom-gated] [CI-green]** Under {A1–A5} together with the single declared axiom `A6'_block_consistent`, Λ_k is the unique normalized aggregator. Its disclosed base is `#print axioms lambda_unique_under_block = [A6'_block_consistent, propext, Quot.sound, Classical.choice]` — *one declared, non-core project axiom* plus the Lean core.

Theorem 4.4 was honest but carried a cost: the trusted base included a *project axiom* that could not itself be discharged in-kernel. v24 removes that cost.

### 4.4 The v24 advance: axiom-free conditional uniqueness (CUT-2)

The v24 headline replaces the declared A6′ idealization with a *checkable structural property* of the candidate aggregator: *slice-multiplicativity* (separability). Informally, Φ is slice-multiplicative if it factors as a product of per-axis slice functions, each of which is multiplicative, normalized, and monotone — properties one can in principle *verify* of a concrete Φ, rather than postulate.

**Definition 4.5 (Slice-multiplicativity / separability).** Φ : [0,1]^k → [0,1] is *slice-multiplicative* if there exist slice functions f_i : ℝ_{≥0} → ℝ_{≥0} such that **(sep)** Φ(x) = ∏_i f_i(x_i), **(mul)** f_i(s t) = f_i(s) f_i(t), **(one)** f_i(1) = 1, and **(mono)** each f_i is monotone.

**Theorem 4.6 (Axiom-free conditional uniqueness of Λ — the v24 advance). [experimental, axiom-free, CI-green]** Let k > 0 and let Φ satisfy the Lutar axioms {A1, A2, A3, A5}. If Φ is slice-multiplicative (Definition 4.5) then Φ = Λ_k. The Lean term is `lambda_unique_of_separable` (namespace `Lutar.Round13`); its trusted base is exactly

```
#print axioms lambda_unique_of_separable = {propext, Classical.choice, Quot.sound},
```

i.e. **no project axiom**. It is kernel-clean, CI-green, and present at `main` `ba1050b7` (originally merged at `b910c276`).

The exact Lean signature is:

```lean
theorem lambda_unique_of_separable {k : ℕ} (hk : 0 < k)
    (Φ : Aggregator k) (hL : LutarAxioms Φ)
    (f : Fin k → (NNReal → NNReal))
    (hsep  : ∀ x, Φ x = ∏ i, f i (x i))
    (hmul  : ∀ i s t, f i (s * t) = f i s * f i t)
    (hone  : ∀ i, f i 1 = 1)
    (hmono : ∀ i, Monotone (f i)) :
    Φ = Λ k
```

**Proof sketch and the in-tree lemma chain.** The proof reduces slice-multiplicativity to factorization and then discharges via Theorem 4.3. Concretely:

1. **Per-axis power law.** For each axis i, the slice f_i is multiplicative (mul), monotone (mono), and normalized (one). The in-tree lemma `multiplicative_monotone_isPow_pos` yields an exponent α_i with f_i(t) = t^{α_i} for all t ≠ 0:
   ```
   multiplicative_monotone_isPow_pos {f} (hf_mul) (hf_mono) (hf_one)
     : ∃ α, ∀ t ≠ 0, f t = t^(α : ℝ)
   ```
   Boundary value f_i(0) = 0^{α_i} follows from the idempotent dichotomy (`slice_zero_idem`, `slice_const_one_of_zero_one`).
2. **Exponent equality across axes.** The chosen exponents α_i are forced equal by permutation invariance (A5): applying `Equiv.swap i j` to a two-hot test vector and using the in-tree injectivity lemma `rpow_left_inj_one_lt` (c^a = c^b ⇒ a = b for c > 1) gives α_i = α_j.
3. **Assemble factorization.** Collecting the per-axis power laws yields the `Factors` predicate (Φ(x) = ∏_i x_i^{α_i}).
4. **Discharge.** Apply `lambda_unique_of_factors` (Theorem 4.3); idempotence (A3) and symmetry (A5) collapse the exponents to 1/k and conclude Φ = Λ_k.

The added hypothesis (slice-multiplicativity) is *weaker* than the old `Factors` premise — a slice-multiplicative Φ provably factors, but factorization alone does not exhibit the per-slice structure — and it is, unlike A6′, a property one can check by inspecting the definition of a concrete Φ.

### 4.5 Λ is Conjecture 1 — the precise claim structure

We state the claim structure without ambiguity. **Conjecture 1 (unconditional).** Λ is the correct unique governed aggregator under A1–A5 alone. This is **machine-checked false** as stated (Theorem 4.2), and so "Conjecture 1" denotes the open, *refined* hypothesis that, for the *governance-relevant* class of aggregators, the natural additional structural assumption (such as slice-multiplicativity or block-consistency) always holds. We never claim Λ proven unconditionally. What *is* proven is the conditional Theorem 4.6 (axiom-free) and Theorem 4.4 (axiom-gated, v23).

### 4.6 Worked examples

- **Λ is slice-multiplicative.** Take f_i(t) = t^{1/k}: it is multiplicative, normalized (1^{1/k} = 1), monotone, and ∏_i t_i^{1/k} = Λ_k. Hence Theorem 4.6's antecedent is non-vacuous.
- **maxAgg is not slice-multiplicative.** No product of per-axis slices reproduces max; consistent with maxAgg being an A1–A5 counterexample (Theorem 4.2) outside the slice-multiplicative class.
- **Separation at (4,1).** maxAgg(4,1) = 4 ≠ 2 = Λ_2(4,1), the `decide`-checked witness.

### 4.7 CUT-1: the Aczél quasi-arithmetic representation, closed on its stated hypotheses (the v24.1 advance)

Theorem 4.6 discharges slice-multiplicativity through a per-axis power-law step. That step is the shadow of a deeper classical result — the *Aczél quasi-arithmetic representation theorem*: a sufficiently regular bisymmetric mean F admits a continuous strictly-monotone generator φ with F(x,y) = φ⁻¹((φx + φy)/2) (Aczél 1948/1966; Burai–Kiss–Szokol arXiv:2107.07391, arXiv:2208.07083). Internally we call the formalization of this representation **CUT-1**. The v24.1 advance is that **CUT-1 is now fully closed on its stated, checkable hypotheses**, kernel-clean, across Waves 18–22.

**Theorem 4.7 (CUT-1: quasi-arithmetic representation, forward direction). [experimental, axiom-free, CI-green]** Let F be reflexive, symmetric, partially strictly monotone, and quasi-arithmetic (admitting strictly-monotone φ, ψ with the dyadic midpoint recursion F(fa)(fb) = f((a+b)/2), ψ continuous). Then the BKS dyadic generator f has dense range and extends to a *continuous* strictly monotone generator — the conclusion of the BKS forward construction. Every declaration in the Wave 18–22 chain has `#print axioms ⊆ {propext, Classical.choice, Quot.sound}`, with no `sorry` and no new axiom token.

The classical forward proof decomposes into a dyadic recursion, a strict-monotonicity / well-definedness step, an additive "generator collapse," a *density of the dyadic image* step, a continuous extension, and the homogeneity endpoint that pins the geometric mean. Each is now discharged kernel-clean:

| Step | Wave | What closed it (kernel-clean) |
|------|------|-------------------------------|
| Forward fragment | 18 | `AczelRepresentation`/`Cut1Chain`: soundness of the quasi-arithmetic axioms; the analytic generator-collapse (`generator_unique_up_to_affine`, a monotone-additive rational squeeze); the `expMidpoint` witness pinning the geometric mean. |
| Density engine | 19 | `DisjointOpens`/`Density`: the BKS Step-2 contradiction — "uncountably many pairwise-disjoint open intervals cannot live on a separable line" (`false_of_uncountable_pairwiseDisjoint_Ioo`). |
| Primitives | 20 | countable-disjoint-opens and perfect⇒uncountable bridges (standalone, also present in Mathlib). |
| (B) residual | 21 | the perfect-set obligation *avoided*: a strictly monotone generator is injective, so its image is a continuum and the accumulation set is uncountable (`range_not_countable_of_strictMono`) — the BKS parent-paper Theorem 8 *First step*, no Cantor–Bendixson. |
| (C-order) residual | 22 | the BKS *Fourth-step* gap-shift ordering R s ≤ L t for s < t — previously carried as a stated hypothesis — is now *derived* from the discrete midpoint chain + monotone limit + continuity of ψ (`corder_gapshift`, `corder_data`). |

The assembled chain is: `StrictMono f` + quasi-arithmetic + ψ continuous → (Wave 22 derives (C-order)) the exact `hC` of `dyadic_image_dense_complete` → (Wave 21, (B) internal) `DenseRange f` → (Wave 18 = Mathlib `Monotone.continuous_of_denseRange`) `Continuous f`. The topological density engine (the disjoint-opens contradiction, the gap extraction) was closed in Waves 19/21; Wave 22 closed the last residual (C-order). **Every residual is now closed on the stated, checkable hypotheses** (bisymmetry / quasi-arithmetic structure + partial strict monotonicity + reflexivity + symmetry — all *properties*, no axioms).

#### How CUT-1 sharpens the conditional Λ result

Closing CUT-1 lets us *drop* hypotheses from the conditional Λ-uniqueness theorem of §4.4. The previous frontier (`cut1_conditional_lambda`) carried five slice hypotheses; Wave 22 proves two of them redundant:

- `bisymmetry_is_redundant` — the slice-induced operation (s,t) ↦ f(s·t) *is* bisymmetric whenever the slice is multiplicative, so slice-bisymmetry is a theorem, not an assumption.
- `slice_one_eq_one_of_sep` — unit-normalization f_i(1) = 1 is *derivable* from A3 diagonal normalization lifted through separability plus multiplicative idempotency, so it need not be assumed.

**Theorem 4.8 (Sharpest conditional Λ-uniqueness). [experimental, axiom-free, CI-green]** Under {A1–A5} together with separability (Φx = ∏_i f_i(x_i)), slice-multiplicativity (f_i(s·t) = f_i(s)·f_i(t)), and slice-monotonicity (f_i monotone), Φ = Λ_k. The Lean term is `cut1_sharp_conditional_lambda`; it discharges axiom-free through the in-tree `lambda_unique_of_separable` (`#print axioms = {propext, Classical.choice, Quot.sound}`). This is strictly weaker than the prior bisymmetric frontier (two fewer hypotheses).

**Why this is the sharp boundary.** Slice-multiplicativity is the irreducible Cauchy-type input the false unconditional statement lacks; dropping it re-admits the `maxAgg`/`min` counterexamples and makes the conclusion FALSE. So the hypothesis set cannot be weakened further within the separable family.

#### What "closed on its stated hypotheses" means — precisely

This is the claim most easily misread, so we are explicit.

- **What CUT-1 closure *is*:** the quasi-arithmetic *representation* theorem (Theorem 4.7) is complete on its stated, checkable hypotheses — the BKS forward construction is built end to end, with the (B) and (C-order) residuals *derived*, not assumed and not axiomatised. It *sharpens* the conditional Λ-uniqueness theorem (Theorem 4.8) to its weakest checkable hypothesis set.
- **What CUT-1 closure is *not*:** it does *not* make Λ unconditional. The closure is for the quasi-arithmetic class — precisely the class the conditional-Λ chain inhabits — and it presupposes that structure. The *unconditional* uniqueness of Λ under {A1–A5} alone stays **Conjecture 1** and is machine-checked **false** (Theorem 4.2, `maxAgg_ne_Lambda`); that counterexample is untouched. CUT-1 strengthens a *conditional* result; it does not, and cannot, discharge the false unconditional one.
- **Tier.** All Wave 18–22 work is *experimental, axiom-free, CI-green* and is never folded into the locked-five.

**Sources.** The construction follows Burai–Kiss–Szokol arXiv:2107.07391 (Theorem 8, Fourth-step eqs. (8)–(9)), arXiv:2208.07083 (Lemma 6, Step 2), the n-ary regularity-free treatment arXiv:2606.05221, and Aczél–Dhombres (1989) pp. 287–290. No source code is imported; all cited references are mathematical literature.

---

## 5. The proof-trail / receipt architecture

### 5.1 Structural correctness (sorry-free)

The receipt layer is a hash-chain of governed-decision entries with a Merkle commitment `root` per batch. Replay determinism (F1) — re-executing the recorded inputs reproduces the recorded root — is *locked* and kernel-verified (§6.1). Append-only structure and ordering invariants are sorry-free, with `#print axioms` reporting `propext` only over the log.

### 5.2 Security under declared idealizations (axiom-gated)

Hash-chain *binding* (you cannot alter a past entry without breaking the root) is proven **[axiom-gated]** under an explicitly declared `sha256_collision_resistant` axiom and the Merkle collision-resistance / domain-separation axioms — these are disclosed in the `#print axioms` ledger, never silently assumed, and are *not* a proof of cryptographic hardness. The DPO `klDivergence`/`pinsker` results remain **false-as-stated** for lack of a simplex hypothesis and are not claimed.

---

## 6. The locked kernel and the frontier theorem families

### 6.1 The locked five (kernel-verified at `c7c0ba17`)

The locked kernel proves **exactly five** governance formulas, sorry-free, with only the trusted core axioms, at the fixed commit `c7c0ba17` (749 declarations / 14 axioms / 163 sorries):

- **F1 — replay determinism.** Re-executing recorded inputs reproduces the recorded root.
- **F11 — Ayni reciprocity.** The reciprocity-balance invariant of the trust ledger.
- **F12 — Kuramoto additive (scaffolding only).** The additive coupling decomposition; the scaffolding, not the synchronization theorem.
- **F18 — Reed–Solomon.** The encoding/decoding correctness fact used by the receipt layer.
- **F19 — Bekenstein additive (scaffolding only, NOT the bound).** The additive bookkeeping scaffold; explicitly *not* the Bekenstein bound itself.

### 6.2 The experimental CI-green tier (at `ba1050b7`)

A *separate* corpus of ~185 kernel-clean theorems across Waves 11–22 (drift baseline 1323 declarations / 23 axioms (22 unique) / 307 sorries at `ba1050b7`) is CI-green and `#print axioms`-clean. **It is never folded into the locked-five.** Every theorem below is `#print axioms`-clean (⊆ core) and resides in this experimental tier.

### 6.3 CF-13 — DEQ input-Lipschitz well-posedness margin

**[experimental, axiom-free, CI-green]** File `Lutar/Innovations/round5/OuroLoopInputLipschitz.lean` (7 declarations). For a contraction with input-Lipschitz constant L_x and contraction modulus K < 1, the equilibrium map z⋆ satisfies dist(z⋆(x), z⋆(y)) ≤ (L_x / (1−K)) · dist(x, y) (`equilibrium_dist_le`, `equilibrium_lipschitz`). Built on Mathlib `ContractingWith`; the result is the well-posedness margin of a deep equilibrium model (Bai–Kolter–Koltun, arXiv:1909.01377). `#print axioms = {propext, Classical.choice, Quot.sound}`.

### 6.4 CF-17 — floating-point summation error bound

**[experimental, axiom-free, CI-green]** File `Lutar/Khipu/NumericStability.lean` (8 declarations). Under the standard per-step rounding model, the recursive-summation forward error is bounded (`recSum_error_le`), following Higham's analysis. `#print axioms = {propext, Classical.choice, Quot.sound}`.

### 6.5 Wave-13 — replay completeness, quorum shadow, HM bottleneck

**[experimental, axiom-free, CI-green]**

- `findReplayRoot_complete` (via Lean core `List.find?_isSome`): if a replay-root candidate is a member of the candidate list and validates, the search returns `some`. `#print axioms = {propext, Quot.sound}`.
- `quorum_agreement_single_valued_vote`: for n ≥ 3f+1 and two quorums of size ≥ n−f, single-valued votes agree (v_1 = v_2), by nonempty quorum intersection. `#print axioms = {propext, Classical.choice, Quot.sound}`. **Honesty:** this assumes each organ votes via a *total function* (a non-Byzantine shadow); it is **NOT** the Byzantine BFT result — that remains the open **Khipu Conjecture 2**.
- `hm_bottleneck_clean`: the harmonic-mean bottleneck bound (contrapositive; pure order/field reasoning). `#print axioms = {propext, Classical.choice, Quot.sound}`.

### 6.6 Wave-14 — CF-18/19/20/21 (nine kernel-clean theorems)

**[experimental, axiom-free, CI-green]** All nine compile clean with `#print axioms = {propext, Classical.choice, Quot.sound}`.

- **CF-18 — Mādhava/Leibniz alternating-series remainder** (`Lutar/Wave14/LeibnizRemainder.lean`). For an antitone nonnegative a with alternating partial sums tending to L, one has |∑_{i<N}(−1)^i a_i − L| ≤ a_N (the Lean terms `leibniz_remainder_bound` and `madhava_alt_series_bound_clean`), via Mathlib `Antitone.alternating_series_le_tendsto` even/odd bracketing (Plofker 2009).
- **CF-19 — Reed–Solomon MDS distance lower bound** (`Lutar/Wave14/ReedSolomonDistance.lean`). Two distinct polynomials of degree < k agree on fewer than k points (`agreement_card_lt_of_degree_lt`); lifting via injectivity of the evaluation points gives the bound n − k + 1 ≤ #{i : p(pts_i) ≠ q(pts_i)} (`rs_distance_lower_bound`). This is the *achievability / lower-distance half* of Singleton; the upper bound and full MDS equality remain honest sorries (Reed–Solomon 1960, Singleton 1964).
- **CF-20 — VCG efficiency + truthfulness core** (`Lutar/Wave14/VCGEfficiency.lean`). An efficient outcome exists and maximizes social welfare (`exists_efficient_outcome`, `efficientOutcome_maximises`); the truthfulness core is the marginal-contribution monotonicity consequence (`vcg_truthfulness_core`) (Vickrey–Clarke–Groves; Nisan et al. 2007). **Honesty:** the in-tree `MechanismDesign/VCG.lean` references a nonexistent `Finset.argmax` and is unwired; CF-20 is a clean companion, not a patch.
- **CF-21 — Cover–Thomas log-sum + Gibbs** (`Lutar/Wave14/LogSumInequality.lean`). The log-sum inequality (`log_sum_inequality`) and Gibbs' inequality (`gibbs_inequality`) via log x ≤ x − 1 (Cover–Thomas Thm 2.7.1 and 2.6.3). **Honesty:** this is the *correctly-stated* DPI core; it does **not** repair the in-tree DPO `klDivergence`/`pinsker`, which remain false-as-stated for lack of a simplex hypothesis.

### 6.7 Waves 15–17 — CF-22 through CF-28

**[experimental, axiom-free, CI-green]** All compile clean with `#print axioms ⊆ {propext, Classical.choice, Quot.sound}`; the drift baseline is unchanged.

- **CF-22 (Wave 15) — conditional DPO KL repair.** `dpo_klDivergence_nonneg_on_simplex` gives a *conditional* repair of the false-as-stated DPO KL-nonnegativity claim — valid *on the probability simplex only*. **Honesty:** the unrestricted claim remains false; CF-22 adds the missing simplex hypothesis and proves the restricted statement, it does not rehabilitate the original.
- **CF-23 (Wave 17) — full binary Pinsker inequality.** `binary_pinsker`: the complete binary Pinsker inequality (KL ≥ (1/2 ln 2)·(total-variation)² in the two-point case), kernel-clean — a genuine strengthening over the earlier false-as-stated `pinsker`.
- **CF-24 (Wave 16) — geoBin Aczél axioms.** The Aczél-style axiom soundness for the geometric-binary mean (`geoBin`).
- **CF-25 (Wave 16/17) — Λ scale-invariance.** Machine-checked scale-invariance of Λ.
- **CF-26 — abacus.** The positional-abacus carry/representation correctness fact.
- **CF-27 — monDEQ uniqueness.** Uniqueness of the monotone deep-equilibrium fixed point under the contraction hypothesis.
- **CF-28 — recurrent-depth Lipschitz.** A recurrent-depth Lipschitz bound for the unrolled equilibrium iteration.

### 6.8 Waves 18–22 — the CUT-1 construction

**[experimental, axiom-free, CI-green]** The Aczél quasi-arithmetic representation theorem, closed on its stated hypotheses (full account in §4.7). Wave 18 (PR #208, 19 thms: `generator_unique_up_to_affine`, `expMidpoint`, `gen_continuous_of_denseRange`); Wave 19 (PR #209, 21 thms: `false_of_uncountable_pairwiseDisjoint_Ioo`, `dyadic_image_dense`); Wave 20 (PR #210, 17 thms: primitives); Wave 21 (PR #211, 13 thms: `range_not_countable_of_strictMono`, `dyadic_image_dense_complete`); Wave 22 (PR #212, 15 thms: `gapShift_ordering`, `corder_gapshift`, `corder_data`, `cut1_sharp_conditional_lambda`, `bisymmetry_is_redundant`, `slice_one_eq_one_of_sep`). All `#print axioms ⊆ {propext, Classical.choice, Quot.sound}`, no `sorry`, no new axiom; drift unchanged.

---

## 7. Verification status, in detail

### 7.1 The wave ledger (Waves 11–22)

| Wave | PR | Headline content | Status |
|------|-----|------------------|--------|
| 11 | — | Locked-kernel consolidation | locked @ `c7c0ba17` |
| 12 | #202 | CUT-2 axiom-free Λ-uniqueness (`lambda_unique_of_separable`) | merged, CI-green |
| 13 | #203 | replay completeness, quorum shadow, HM bottleneck | merged, CI-green |
| 14 | #204 | CF-18/19/20/21 (nine kernel-clean theorems) | merged, CI-green |
| 15 | — | CF-22 conditional DPO KL repair (`dpo_klDivergence_nonneg_on_simplex`) | merged, CI-green |
| 16 | — | CF-24/25/26 (geoBin Aczél axioms, Λ scale-invariance, abacus) | merged, CI-green |
| 17 | — | CF-23 full binary Pinsker (`binary_pinsker`); CF-27/28 (monDEQ uniqueness, recurrent-depth Lipschitz) | merged, CI-green |
| 18 | #208 | CUT-1 forward fragment (19 thms) | merged, CI-green |
| 19 | #209 | CUT-1 BKS density engine (21 thms) | merged, CI-green |
| 20 | #210 | CUT-1 primitives (17 thms) | merged, CI-green |
| 21 | #211 | CUT-1 (B) residual closed (13 thms) | merged, CI-green |
| 22 | #212 | CUT-1 (C-order) derived; `cut1_sharp_conditional_lambda` (15 thms) | merged, CI-green |

All Waves 11–22 are merged into `main` at `ba1050b7` (originally Waves 11–14/15 at `b910c276`, now superseded).

### 7.2 The drift gate and the canonical numbers

A numbers-drift gate guards four quantities and the axiom-name set: declarations, axioms_raw, axioms_unique, sorries_raw. At `main` `ba1050b7` the canonical figures are **1323 / 23 / 22 / 307** — *unchanged* since `b910c276`: every Wave 15–22 module is registered under `EXPERIMENTAL_SCOPES`, so its declarations are additive and do not move the locked baseline. The gate is green and drift-clean across all of Waves 11–22. The locked kernel at `c7c0ba17` is **749 / 14 / 163**, locking {F1, F11, F12, F18, F19}. These tiers are reported separately and the experimental count (~185 kernel-clean theorems) is never folded into the locked-five.

### 7.3 The `#print axioms` discipline

Every claimed-proven theorem is accompanied by its `#print axioms` ledger. The axiom-free results report `#print axioms ⊆ {propext, Classical.choice, Quot.sound}` — the trusted Lean core only — with the sole exception of the explicitly axiom-gated cryptographic results (§5), whose declared idealizations appear in their ledgers. No theorem is stated as proven that CI has not verified at the recorded commit.

### 7.4 SLSA supply-chain posture — correcting a v23 overstatement

v23 wrote "SLSA L1+L2 attested". **This badge was wrong and is corrected here.** The honest posture is **SLSA L1, with L2 build-attestation present**. We do *not* claim L2-*verified*, L3, FedRAMP authorization, Iron Bank accreditation, or CMMC certification — these remain roadmap items. The container build pipeline meets L1 provenance expectations and emits an L2 build attestation; full L2 verification (hosted, authenticated build service with independently verified signed provenance) and everything above it are reported as roadmap rather than current state.

---

## 8. Why this is groundbreaking — the honest case

**Axiom elimination as a first-class result.** The standard way to "strengthen" a conditional theorem is to weaken its hypothesis. v24 does something sharper: it *removes a project axiom from the trusted base entirely*. v23's conditional uniqueness depended on `A6'_block_consistent`, a declared idealization that the kernel had to *trust*. v24's `lambda_unique_of_separable` depends on no project axiom at all (`#print axioms = {propext, Classical.choice, Quot.sound}`); the only added hypothesis is a *checkable property of* Φ. To our knowledge, exhibiting a governed-AI aggregator uniqueness result whose trusted base is exactly the bare Lean core is new.

**A machine-checked boundary, not just a conditional.** We did not merely prove a conditional theorem; we proved the *negation* of the unconditional claim (Theorem 4.2). Establishing exactly which extra assumption is required — and that without it the claim fails — converts a routine conditional into a *boundary* result: Theorem 4.6 is demonstrably close to the maximal true statement of its kind, and the boundary itself is machine-checked.

**Disclosed-axiom discipline at scale.** Formal verification of security-critical systems is well established (seL4 is the canonical machine-checked OS kernel); applying a disclosed-axiom, kernel-checked discipline to an AI governance aggregator and its receipt architecture — with a `#print axioms` ledger for *every* claim and a hard separation between a locked five and an experimental tier — is, as far as we can determine, new.

### 8.1 Honest comparison to prior art

| Prior art | What it provides | How v24 differs (honestly) |
|-----------|------------------|----------------------------|
| Verifiable-claims governance | The argument that AI claims should be externally verifiable. | A concrete substrate with a kernel-checked core; does not claim to solve verifiability in general. |
| seL4 / formal OS | Machine-checked OS-kernel correctness; the gold standard. | Verifies a governance aggregator + receipt layer; far smaller in scope and maturity; no seL4-level coverage claimed. |
| Certificate Transparency | Merkle-based tamper-evident logs in production. | Reuses the Merkle discipline; formalizes the binding property in Lean under declared axioms. |
| Functional-equation aggregation | Uniqueness characterizations of the geometric mean. | Formalizes an *axiom-free* conditional uniqueness (slice-multiplicativity) and machine-checks the unconditional refutation. |
| SLSA framework | A supply-chain integrity ladder (L1–L4). | Honestly attests L1; L2 is a roadmap item; L3 / FedRAMP / Iron Bank / CMMC explicitly *not* claimed. |

**Honest summary.** The individual mathematical facts (geometric-mean characterizations, Kraft, Shannon, Byzantine quorums, Reed–Solomon, VCG, log-sum) are classical. The contribution of v24 is their unification into a governed-AI trust substrate, their kernel-checked instantiation, and above all the *axiom elimination* on the central uniqueness result combined with the *honesty architecture* — locked counts, disclosed axioms, and a machine-checked refutation guarding the one tempting overclaim.

---

## 9. Philosophical foundations: slice-multiplicativity as an epistemic upgrade

### 9.1 From a declared axiom to a checkable property

A trusted base that contains a project axiom asks the auditor to *believe* something the kernel cannot check. A6′ (block-consistency) was such an axiom: governance-legible, published, and defensible, but ultimately *postulated*. Slice-multiplicativity is different in kind. It is a structural *property of the candidate aggregator* Φ — of the form "Φ factors into multiplicative, normalized, monotone slices" — that one can in principle *verify* of a concrete Φ by inspecting its definition. Replacing a postulate the auditor must trust with a property the auditor can check is, on any reliabilist account of justification, an *epistemic upgrade*: the warrant for the conclusion no longer routes through an unverifiable idealization.

### 9.2 When is a conditional legitimate?

Four conditions, all met by Theorem 4.6: (i) *independently-motivated antecedent* — separability is the standard hypothesis under which multiplicative aggregators are characterized; (ii) *non-vacuous instantiation* — Λ itself is slice-multiplicative (§4.6), so the conditional is not vacuously true; (iii) *boundary established* — without the hypothesis, uniqueness fails (Theorem 4.2); (iv) *disclosed at point of use* — the `#print axioms` ledger shows the bare core only, so the cost of the conditional is fully visible.

### 9.3 Slice-multiplicativity vs. block-consistency

Both pick out Λ within the A1–A5 class, but they differ epistemically. Block-consistency (A6′) is an *axiom about the world* (how evidence partitions behave) the auditor must accept. Slice-multiplicativity is a *property of the object* (the aggregator's functional form) the auditor can confirm. The latter is strictly preferable for governance, because the trusted base shrinks to the bare Lean core.

### 9.4 Steelman objections (with honest rebuttals)

- *"Slice-multiplicativity is just factorization renamed."* No — it is weaker than the old `Factors` premise and exposes the per-axis multiplicative/monotone/normalized structure that the proof actually consumes; factorization is *derived*, not assumed.
- *"A conditional theorem is weaker than an unconditional one."* True, but the unconditional statement is machine-checked **false**; the conditional is the maximal true statement, and we say so.
- *"You still rely on Classical.choice."* Yes — these are Lean-*core* axioms, disclosed in every ledger, and identical to the foundations of Mathlib itself; no *project* axiom is added.

---

## 10. Empirical posture (measured, not proven)

The following figures are **measured engineering numbers, not theorems**. They describe a reference deployment and are reported for context only; nothing in this section is a kernel-verified claim.

| Metric (reference deployment) | Value | Note |
|-------------------------------|-------|------|
| Median governed-loop latency | (measured) | end-to-end, single organ |
| Receipt append + root update | (measured) | per governed decision |
| `lake build` (full kernel check) | (measured) | at `ba1050b7`, CI-green |
| Runtime CDN dependencies | 0 | by construction |

These are operational characteristics, explicitly outside the honesty doctrine's "proven" tier.

---

## 11. Limitations and honesty

- **Λ is Conjecture 1 unconditionally.** Unconditional uniqueness under A1–A5 is machine-checked false; only conditional results are theorems.
- **Byzantine BFT is open (Khipu Conjecture 2).** The Wave-13 quorum result is a non-Byzantine shadow under a total-function voting assumption, not the BFT theorem.
- **307 open sorries** remain in the experimental tier at `ba1050b7`; they are disclosed, never claimed proven.
- **Cryptographic security is axiom-gated**, resting on declared collision-resistance idealizations, not proofs of hardness.
- **DPO `klDivergence`/`pinsker` are false-as-stated** for lack of a simplex hypothesis; CF-21 is a correctly-stated companion, not a repair.
- **Reed–Solomon CF-19** proves only the lower-distance half of Singleton; the upper bound and full MDS equality remain sorries.
- **SLSA L1 honest, L2 build-attestation present** — L2-verified, L3, FedRAMP, Iron Bank, and CMMC remain roadmap.
- **CUT-1 is a representation-theorem closure on its stated hypotheses**, sharpening the *conditional* Λ chain; it does **not** make Λ unconditional (which stays Conjecture 1, machine-checked false).

---

## 12. Conclusion

v24 advanced the Ouroboros program by a single, sharp, honest step: the conditional uniqueness of the Lutar invariant Λ is proved **axiom-free**. `Lutar.Round13.lambda_unique_of_separable` shows that, under {A1, A2, A3, A5} together with the *checkable* property of slice-multiplicativity, Φ = Λ_k, with `#print axioms = {propext, Classical.choice, Quot.sound}` (no project axiom), kernel-clean and CI-green at `ba1050b7`. This strictly strengthens v23, whose conditional uniqueness was gated on the declared axiom A6′, by replacing a postulate the auditor must trust with a property the auditor can check — an epistemic upgrade. This revision (v24.1) adds the **CUT-1 closure** (§4.7): the Aczél quasi-arithmetic *representation* theorem is now fully closed on its stated, checkable hypotheses across Waves 18–22, which sharpens the *conditional* Λ-uniqueness chain to be axiom-clean end to end on {A1–A5} + separability + slice-multiplicativity + slice-monotonicity (`cut1_sharp_conditional_lambda`).

The honesty doctrine is unchanged and binding: Λ remains **Conjecture 1** unconditionally (its unconditional uniqueness is machine-checked false via `maxAgg_ne_Lambda`, and CUT-1 does not, and cannot, change that); locked-proven = exactly five {F1, F11, F12, F18, F19} at `c7c0ba17`; the experimental CI-green tier (~185 kernel-clean thms; drift 1323/23/307 at `ba1050b7`) is never folded in; declared axioms are disclosed in every `#print axioms` ledger; SLSA **L1 honest, L2 build-attestation present**; nothing fabricated; 0 runtime CDN. Calibrated honesty is not a weakness of the program — it is the feature that makes every positive claim credible to an auditor.

---

## Appendix A. Reproducibility and artifact manifest

### A.1 Pinned commits and artifacts

| Component | Pin | Contents / status |
|-----------|-----|-------------------|
| `main` (Waves 11–22 merged) | `ba1050b7` | 1323 decl / 23 axioms (22 unique) / 307 sorries; ~185 experimental kernel-clean thms; CI-green |
| Prior pin (Waves 11–14/15) | `b910c276` | superseded by `ba1050b7`; same drift baseline |
| Locked kernel | `c7c0ba17` | 749 / 14 / 163; locks {F1,F11,F12,F18,F19} |
| CUT-2 axiom-free Λ | in `ba1050b7` | `Round13/LambdaSeparable.lean` |
| CUT-1 representation (Waves 18–22) | in `ba1050b7` | `AczelRepresentation/`; closed on stated hypotheses |
| Concept DOI (always-latest) | — | [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926) |
| Repository | — | [github.com/szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean) |

### A.2 How to verify

```bash
# 1. Kernel-check the merged library at the pinned commit
$ git checkout ba1050b7 && lake build        # expect: green, no errors

# 2. Disclose the trusted axiom base of the v24 headline theorem
$ #print axioms Lutar.Round13.lambda_unique_of_separable
=> [propext, Classical.choice, Quot.sound]   # NO project axiom

# 3. Confirm the unconditional claim is refuted
$ #print axioms maxAgg_ne_Lambda             # Lean-core axioms only

# 4. Verify the locked kernel separately
$ git checkout c7c0ba17 && lake build        # locks F1,F11,F12,F18,F19
```

### A.3 Trusted computing base

The bottom turtles, stated once: (i) soundness of the Lean 4 kernel and its core axioms {propext, Classical.choice, Quot.sound}; (ii) the declared cryptographic idealizations (`sha256_collision_resistant` and the Merkle collision-resistance / domain-separation axioms), used only in the receipt-security theorems; and (iii) human sign-off gating CI. The v24 headline theorem `lambda_unique_of_separable` depends on *none* of the cryptographic idealizations and on *no* project axiom — only on (i).

---

## Appendix B. Notation and glossary

| Symbol / term | Meaning |
|---------------|---------|
| Λ_k(x) | The Lutar invariant: equal-weight geometric mean (∏_i x_i)^{1/k} on [0,1]^k |
| Φ | A generic candidate aggregator [0,1]^k → [0,1] satisfying some subset of A1–A5 |
| maxAgg, min | The machine-checked A1–A5 witnesses that A1–A5 do not pin Λ (Thm 4.2) |
| A1–A5 | Monotonicity, positive homogeneity, idempotence, boundedness, permutation-invariance |
| A6′ | Block-consistency: the v23 declared axiom (replaced in v24) |
| slice-multiplicativity | The v24 checkable hypothesis: Φ = ∏_i f_i(x_i) with each f_i multiplicative, normalized, monotone |
| `lambda_unique_of_separable` | The v24 headline: axiom-free conditional Λ-uniqueness |
| link_i, root | The i-th hash-chain entry and the Merkle commitment to a receipt batch |
| sorry-free | A Lean development with no `sorry`; the kernel checks every step |
| CI-green | The real CI `lake build` (a full kernel check) passes at the pinned commit |
| axiom-gated | Sorry-free given an explicitly declared, disclosed idealizing axiom |
| `#print axioms` | Lean command listing the trusted axiom base of a theorem |
| locked-five | The exactly five kernel-verified formulas {F1,F11,F12,F18,F19} at `c7c0ba17` |
| experimental tier | The separate CI-green corpus (~185 kernel-clean thms; drift 1323/23/307 at `ba1050b7`), never folded into the locked-five |
| CUT-1 | The Aczél quasi-arithmetic representation theorem (Waves 18–22), closed on its stated hypotheses; sharpens the conditional Λ result, does not make Λ unconditional |
| `cut1_sharp_conditional_lambda` | The sharpest conditional Λ-uniqueness theorem on {A1–A5} + separability + slice-multiplicativity + slice-monotonicity |
| Conjecture 1 | The open claim that Λ is the correct unique governed aggregator; never a theorem |

---

## References

1. J. Aczél. *On mean values.* Bulletin of the American Mathematical Society, 54(4):392–400, 1948. https://eudml.org/doc/296298
2. J. Aczél. *Lectures on Functional Equations and Their Applications.* Academic Press, 1966.
3. J. Aczél and T. L. Saaty. *Procedures for synthesizing ratio judgements.* Journal of Mathematical Psychology, 27(1):93–102, 1983.
4. S. Bai, J. Z. Kolter, V. Koltun. *Deep equilibrium models.* NeurIPS 2019. arXiv:1909.01377. https://arxiv.org/abs/1909.01377
5. T. M. Cover and J. A. Thomas. *Elements of Information Theory.* 2nd ed., Wiley, 2006.
6. E. H. Clarke. *Multipart pricing of public goods.* Public Choice, 11:17–33, 1971.
7. T. Groves. *Incentives in teams.* Econometrica, 41(4):617–631, 1973.
8. N. J. Higham. *Accuracy and Stability of Numerical Algorithms.* 2nd ed., SIAM, 2002.
9. G. Klein et al. *seL4: Formal verification of an OS kernel.* SOSP 2009.
10. The mathlib Community. *The Lean Mathematical Library.* CPP 2020.
11. L. de Moura and S. Ullrich. *The Lean 4 Theorem Prover and Programming Language.* CADE 2021.
12. N. Nisan, T. Roughgarden, É. Tardos, V. Vazirani (eds). *Algorithmic Game Theory.* Cambridge, 2007.
13. K. Plofker. *Mathematics in India.* Princeton University Press, 2009.
14. I. S. Reed and G. Solomon. *Polynomial codes over certain finite fields.* J. SIAM, 8(2):300–304, 1960.
15. R. C. Singleton. *Maximum distance q-nary codes.* IEEE Trans. Inf. Theory, 10(2):116–118, 1964.
16. W. Vickrey. *Counterspeculation, auctions, and competitive sealed tenders.* J. Finance, 16(1):8–37, 1961.
17. P. Burai, G. Kiss, P. Szokol. *Generalized bisymmetry equation and quasi-arithmetic means.* arXiv:2107.07391. https://arxiv.org/abs/2107.07391
18. P. Burai, G. Kiss, P. Szokol. *On the uniqueness of quasi-arithmetic means under a bisymmetry-type condition.* arXiv:2208.07083. https://arxiv.org/abs/2208.07083
19. P. Burai, G. Kiss, P. Szokol. *n-ary regularity-free characterization of quasi-arithmetic means.* arXiv:2606.05221. https://arxiv.org/abs/2606.05221
20. J. Aczél and J. Dhombres. *Functional Equations in Several Variables.* Cambridge University Press, 1989 (pp. 287–290).
21. S. P. Lutar Jr. *The Ouroboros Thesis (Lean development).* SZL Holdings. Concept DOI [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926); repository [github.com/szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean).

*Full bibliographic detail with all URLs is in `refs.bib` and the typeset PDF bibliography.*
