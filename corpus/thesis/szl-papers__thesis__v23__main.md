# The Unified Substrate

### A Machine-Verified Trust Foundation for Governed Agentic AI: Unifying the Ouroboros Loop, the Lutar Invariant, and a Disclosed-Axiom Proof Trail

**Thesis v23 "Unified Substrate" — SZL Holdings**

**Author:** Stephen P. Lutar Jr. · SZL Holdings · ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)
*Co-authored with the SZL full-stack PhD team (mathematics, scientific writing, physics, CS, ML, philosophy of mathematics).*

**Concept DOI (always-latest):** [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926) · **v11 metrics DOI:** [10.5281/zenodo.20119582](https://doi.org/10.5281/zenodo.20119582)

> This markdown file is a faithful rendering of `main.tex`. The typeset 20-page PDF (`main.pdf`) is the canonical presentation; `main.tex` is the authoritative LaTeX source.

---

## Abstract

Governed deployment of agentic artificial intelligence in regulated and defense settings requires more than benchmark accuracy: it requires *checkable* guarantees about what a system did, why it was permitted to do it, and whether the record can be tampered with after the fact. We present the **Unified Substrate** (v23), the consolidation of twenty-two prior thesis versions (v1–v22) of SZL Holdings into a single coherent account of a machine-verified trust substrate for governed AI. The substrate rests on three pillars: (i) the *Ouroboros loop*, a bounded, well-founded self-governing computation in which "the loop is the product"; (ii) the *Lutar invariant* Λ_k(x) = (∏_{i=1}^k x_i)^{1/k}, an equal-weight geometric-mean trust aggregator; and (iii) a *proof-trail / receipt architecture* whose integrity properties are formalized in Lean 4.

Our central methodological commitment is an **honesty doctrine**: we distinguish, at every point of assertion, among *proven* (kernel-verified, Lean-core axioms only), *proven under a declared axiom* (idealization disclosed in the `#print axioms` ledger), and *conjectured* (a research hypothesis, not a theorem). Under that doctrine we report: a *locked kernel* proving exactly five governance formulas ({F1, F11, F12, F18, F19}, 749 declarations / 14 unique axioms / 163 sorries at a fixed commit); **nineteen** additional sorry-free theorems (Kraft, Shannon tight case, Byzantine 3f+1 quorums, DLS partial-synchrony, the FLP bivalence core, BLUE minimum-variance, and softmax order-stability) verified under bare Lean with only the trusted core axioms; **four** axiom-gated Merkle / Merkle–Damgård theorems under explicitly declared collision-resistance idealizations; and a *conditional* uniqueness theorem for Λ that is CI-green under {A1–A5} plus a single declared, disclosed, governance-natural axiom (block-consistency, after Csátó 2018).

Crucially, the *unconditional* uniqueness of Λ under {A1–A5} is provably **false**: we exhibit a machine-checked counterexample. We therefore label Λ as **Conjecture 1** unconditionally — never a theorem — and argue, on grounds drawn from philosophy of mathematics and formal epistemology, that this calibrated labeling is not a weakness but the very feature that makes the positive claims credible to an auditor. We close with an honest comparison to prior art, a philosophical defense of block-consistency as the right governance axiom, and an enumerated limitations section.

---

## 1. Introduction

The deployment of agentic AI into regulated industries (finance, healthcare) and defense settings has exposed a gap that benchmark performance cannot close: a *trust* gap. A regulator, an auditor, or a defense customer does not principally ask "how accurate is the model?"; they ask "what did the system do, under what authority, and can you prove the record has not been altered?" Answering those questions requires an artifact distinct from a model — a **trust substrate**: machinery that (a) governs what the agent is permitted to do, (b) aggregates evidence of trustworthiness into an auditable verdict, and (c) maintains a tamper-evident record of every governed decision.

This paper is the twenty-third and unifying version of a thesis program that SZL Holdings has developed since April 2026. The prior twenty-two versions each advanced a piece of the substrate; v23 consolidates them and, more importantly, states with complete honesty exactly what has and has not been machine-verified. The defining commitment of v23 is its **honesty doctrine** (§2): we never let an engineering aspiration masquerade as a theorem.

The single most important honest statement in this paper is this: the central trust aggregator's unconditional uniqueness is **false**, and we prove it false by machine. The aggregator is unique only under an additional, declared axiom. We therefore label the aggregator **Conjecture 1** unconditionally and prove a **conditional theorem** under the declared axiom. This is the maximal true statement, and saying so plainly is what makes every other positive claim in the substrate credible.

---

## 2. The honesty doctrine

The doctrine is load-bearing and is preserved verbatim across all SZL artifacts. It defines three tiers of epistemic status, and every claim in this paper is tagged with exactly one:

- **[locked / kernel-verified]** — proven in Lean 4 with only the trusted core axioms (`propext`, `Quot.sound`, `Classical.choice`); sorry-free; pinned at a fixed commit and part of the locked count.
- **[sorry-free, Lean-core only]** — proven sorry-free under bare Lean (Lean-core axioms only), CI-green, but not yet folded into the locked count pending re-audit.
- **[axiom-gated]** — sorry-free *given* an explicitly declared, disclosed idealizing axiom (e.g. hash collision-resistance), with the axiom appearing in the `#print axioms` ledger.
- **[CI-pending]** — signature-checked but not reproducibly green in the wired build; **not** claimed proven.
- **[Conjecture 1 — NOT a theorem]** — a research hypothesis. Λ's unconditional uniqueness lives here.

**Non-negotiable rules.** (1) Λ = Conjecture 1 unconditionally — never claimed proven unconditionally; a conditional theorem is claimed only with the declared axiom. (2) Only formulas that are kernel-verified (bare-Lean or CI-green) per the proof reports are cited as proven; locked-proven = 5. (3) All axioms are disclosed. (4) No fabricated results, no fake citations. (5) SLSA L1+L2 attested, not L3. (6) Open sorries are disclosed.

---

## 3. The Ouroboros loop: bounded self-governance

The first pillar is a self-referential governed computation — the *Ouroboros loop* — in which the system's output feeds its own governance input under a bounded, well-founded recursion. "The loop is the product": the governed loop, not a single inference, is the unit of value. Termination is guaranteed by a well-founded measure; self-reference is rendered coherent by **Tarskian stratification** (a governed object-level computation is audited by a strictly higher meta-level), avoiding the self-verification paradoxes of Gödel/Tarski. The bottom turtle — the Lean kernel, the cryptographic idealizations, and human sign-off — is finite and disclosed (§13.3).

---

## 4. The Lutar invariant Λ and its uniqueness boundary

### 4.1 Definition and axioms

**Definition (Λ).** For x ∈ [0,1]^k, the Lutar invariant is the equal-weight geometric mean Λ_k(x) = (∏_{i=1}^k x_i)^{1/k}.

The governance axioms a trust aggregator Φ : [0,1]^k → [0,1] should satisfy:

- **A1 (Monotonicity)** — increasing any sub-score does not decrease the verdict.
- **A2 (Positive homogeneity)** — Φ(λx) = λΦ(x) for λ > 0 (scale-covariance).
- **A3 (Idempotence / normalization)** — Φ(c,…,c) = c.
- **A4 (Boundedness)** — Φ(x) ≤ max_i x_i.
- **A5 (Permutation-invariance)** — the verdict is anonymous in the sub-scores.
- **A6′ (Block-consistency)** — the *declared* governance axiom: the verdict is invariant to how the auditor partitions evidence into review blocks (aggregation-invariance / audit path-independence, after Csátó 2018). Weaker and more independent than the bisymmetry axiom A6.

### 4.2 The unconditional refutation — Theorem 4.2 *(FALSE unconditional; machine-checked)*

**Theorem 4.2 (`maxAgg_ne_Lambda`, `unconditional_lambda_is_false`).** The max aggregator `maxAgg(x) = max_i x_i` satisfies A1–A5 but is **not** equal to Λ. At x = (4,1) (rescaled to [0,1]), max = 4 while Λ = √4 = 2. Hence {A1–A5} do **not** pin Λ; unconditional uniqueness is false. **[sorry-free, Lean-core only]**, `decide`-checked, CI-green.

This is the epistemic heart of the paper: we did not merely fail to prove unconditional uniqueness, we *proved its negation*.

### 4.3 Factorization — Theorem 4.3

**Theorem 4.3 (`lambda_unique_of_factors`, Round-13).** Λ is the unique A1–A5 aggregator that additionally factors multiplicatively over its arguments. **[sorry-free]**.

### 4.4 The conditional uniqueness theorem — Theorem 4.4 *(CI-green under declared A6′)*

**Theorem 4.4 (`lambda_unique_under_block`).** Under {A1–A5} together with the declared axiom **A6′ (block-consistency)**, Λ is the *unique* aggregator. **[CI-green]** (Lutar/Wave4/`LambdaBlockConsistency.lean`).

`#print axioms lambda_unique_under_block` ⇒ `[A6'_block_consistent, propext, Quot.sound, Classical.choice]`.

Non-vacuity: `lambda_factors` (axiom-free, CI-green) shows the factorization A6′ demands is realized by Λ itself — so the conditional is not vacuously true.

### 4.7 Worked examples

- **Disqualifying-zero.** Λ(0.9, 0.9, 0.0) = 0 — a single failed axis vetoes the verdict, unlike the arithmetic mean (0.6). This is the governance-desirable property: trust is not bought back by strong performance elsewhere.
- **Scale-covariance.** Λ(2x) = 2·Λ(x) (A2): rescaling the evidence rescales the verdict, the measurement-theoretic objectivity property.
- **maxAgg comparison.** At (0.8, 0.2): Λ = 0.4, maxAgg = 0.8 — the discriminating instance witnessing Theorem 4.2.

---

## 5. The proof-trail / receipt architecture

### 5.4 Receipt schema

Each governed decision emits a *receipt*. The chain entry is
`link_i = H(payload_i ‖ link_{i-1})` and a batch commits to a Merkle `root`. A worked tamper check: altering any `payload_i` changes `link_i`, which propagates to `root`, so re-verification fails — *tamper-evidence under the declared collision-resistance axiom*. The architecture retains the full sub-score vector (never letting Λ replace it), gates deny-by-default, and supports byte-identical deterministic replay (F1).

---

## 6. Locked kernel and verified theorems

### 6.1 The locked five *(kernel-verified at `c7c0ba17`; 749 decl / 14 axioms / 163 sorries)*

| ID | Formula | Status note |
|----|---------|-------------|
| F1 | Replay determinism | locked |
| F11 | Ayni reciprocity | locked |
| F12 | Kuramoto additive | locked (additive *scaffolding only*, not the full sync theorem) |
| F18 | Reed–Solomon | locked |
| F19 | Bekenstein additive | locked (additive *scaffolding only*, NOT the bound S ≤ 2πkRE/ℏc) |

### 6.2 The +19 Wave-3 sorry-free cores *(Lean-core only, CI-green)*

C8 Kraft (3), C9 Shannon tight case (3), C10 Byzantine 3f+1 (4), C11 DLS partial-synchrony (2), C12 FLP bivalence core (2), C17 BLUE scalar (2), C20 softmax order-stability (3).

### 6.3 The +4 axiom-gated Merkle theorems

C13, C13a, C14, C14b — sorry-free under declared collision-resistance / unforgeability idealizations, disclosed in the `#print axioms` ledger.

---

## 7. Verification status, in detail

### 7.5 The CI-pending re-exports *(NOT claimed proven)*

Three Mathlib-dependent re-exports — **C1 Tsirelson 2√2 ceiling**, **C2 CHSH classical ceiling ≤ 2**, and **C6 finite Jensen / ELBO direction** — have signatures verified character-for-character against pinned Mathlib, but wiring their module into the kernel-checked root reproducibly red-lights `lake build`, and the build log is not retrievable in the sandbox. Per the honesty doctrine these stay **[CI-pending]**: the file remains in-tree but is not imported into the compiled root, so nothing is claimed proven that CI has not verified.

### 7.6 Selected proof sketches

- **C8 — Kraft inequality (`c8_kraft_equality_doctrine`).** A prefix-free code over alphabet size D with lengths ℓ_1,…,ℓ_n exists iff ∑_i D^{-ℓ_i} ≤ 1. Identify each codeword with a node at its depth in the full D-ary tree; prefix-freeness ⇒ chosen nodes pairwise non-ancestral ⇒ descendant-leaf sets at maximal depth L disjoint; a depth-ℓ_i node owns D^{L-ℓ_i} leaves; disjointness gives ∑_i D^{L-ℓ_i} ≤ D^L, dividing by D^L yields the inequality. Equality iff the tree is saturated (Kraft 1949). `#print axioms`: **no axioms**.
- **C10 — Byzantine fault tolerance, n ≥ 3f+1 (`c10_threeFPlusOne`, `c10a_quorum_intersection`).** A quorum usable when f processes are unreachable has ≤ n−f members; two quorums of size q share an honest node iff 2q − n > f; taking q = n−f and requiring 2(n−f) − n > f gives n > 3f, hence n ≥ 3f+1 (Pease–Shostak–Lamport 1980). Discharged as arithmetic over ℕ with `omega`. `#print axioms`: `propext, Quot.sound, Classical.choice`.
- **C12 — FLP bivalence core (`c12a_bivalent_xor_univalent`, `c12b_no_decision_from_bivalent`).** A configuration is univalent or bivalent, exclusively (a set-cardinality fact on the reachable-decision subset of {0,1}); and no single deterministic step from a bivalent configuration forces a decision. We claim only this combinatorial core, **not** the full FLP impossibility (Fischer–Lynch–Paterson 1985). `#print axioms`: **no axioms**.

---

## 8. Why this is groundbreaking — the honest case

- **8.1 First machine-verified governed-AI trust substrate with disclosed axioms.** No prior governed-AI system, to our knowledge, ships a locked, kernel-verified core of governance formulas together with a complete `#print axioms` disclosure of every idealizing axiom. Formal verification of security-critical systems is well established (seL4 is the canonical machine-checked OS kernel); applying a disclosed-axiom, kernel-checked discipline to an AI governance aggregator and its receipt architecture is, as far as we can determine, new.
- **8.2 Conditional uniqueness with a machine-checked refutation of the overclaim.** We did not merely prove a conditional theorem; we proved the *negation* of the unconditional claim (Theorem 4.2). Establishing exactly which extra assumption is required — and that without it the claim fails — converts a routine conditional into a *boundary* result: the conditional theorem is demonstrably the maximal true statement.
- **8.3 The receipt architecture as engineered epistemology.** The receipt chain is an engineered *sensitivity* mechanism: under the collision-resistance axiom, the record tracks what actually happened; were it altered, verification would fail to confirm it. Combined with deny-by-default and full sub-score retention, this supplies the non-lucky, checkable grounds on which a rational human trust attitude can rest.

### 8.4 Honest comparison to prior art

| Prior art | What it provides | How v23 differs (honestly) |
|-----------|------------------|----------------------------|
| Verifiable-claims governance (Brundage 2020; NTIA) | The argument that AI claims should be externally verifiable. | v23 is a concrete substrate with a kernel-checked core and disclosed axioms; it does not claim to solve verifiability in general. |
| seL4 / Isabelle security | Machine-checked OS-kernel correctness; the gold standard. | v23 verifies a governance aggregator + receipt layer, far smaller in scope and maturity; we do not claim seL4-level coverage. |
| Certificate Transparency (RFC 6962/9162) | Merkle-based tamper-evident logs in production. | v23 reuses the same Merkle discipline and formalizes the binding property in Lean under declared axioms. |
| SLSA framework | A supply-chain integrity ladder (L1–L4). | v23 attests L1+L2 only; L3 is explicitly **not** claimed. |
| Functional-equation aggregation (Aczél, Csátó) | Uniqueness characterizations of the geometric mean. | v23 formalizes the conditional uniqueness in Lean and machine-checks the unconditional refutation; the math is classical, the verified-and-refuted packaging is the contribution. |

**Honest summary:** the individual mathematical facts (Kraft, Shannon, Byzantine quorums, DLS, FLP, Gauss–Markov, geometric-mean characterizations) are classical. The contribution of v23 is their unification into a governed-AI trust substrate, their kernel-checked instantiation in the governance setting, and above all the *honesty architecture* — locked counts, disclosed axioms, and a machine-checked refutation guarding the one tempting overclaim.

---

## 9. Philosophical foundations: why block-consistency is the right axiom

**9.1 Acceptability test.** A governance primitive is acceptable only if it is (i) interpretable as a norm a layperson-with-counsel would endorse, (ii) non-question-begging, and (iii) independently motivated. Block-consistency (A6′) passes all three: it is audit path-independence; it is phrased entirely in terms of the audit process (partition, aggregate, compare) with no reference to means or exponents; and Csátó (2018) derives the row geometric mean from anonymity + responsiveness + aggregation-invariance — the geometric mean falls out as a *theorem*, not an assumption.

**9.2 When is a conditional legitimate?** Four conditions, all met: independently-motivated antecedent (A6′ is published; we chose the weakest sufficient version, downgrading from A6_bisymmetric); non-vacuous instantiation (`lambda_factors`, axiom-free); boundary established (Theorem 4.2); disclosed at point of use (every `#print axioms`). The residual gap — *is A6′ the philosophically correct demand?* — is genuinely open, which is exactly why Λ remains Conjecture 1.

**9.3 "Conjecture 1" as a calibration signal.** Distinct audited tiers ("locked" = 5; "proven under declared axiom"; "conjecture") make the substrate's "proven" actually mean proven. Honesty here is not modesty; it is what makes any positive claim credible.

**9.5 Steelman objections (with honest rebuttals).** (1) "A6′ is the geometric mean in costume" — A6′ is independently published, phrased without means/exponents; the residue is a defensible normative choice. (2) "Motte-and-bailey" — the conditional/Conjecture and the bald "Λ uniqueness" are labeled and separated in the artifacts themselves. (3) "Idealized crypto axioms make guarantees illusory" — conceded and disclosed; the guarantee is conditional on the same assumptions TLS and CT already rely on. (4) "Arrow: aggregation is impossible" — Arrow concerns ordinal preference aggregation; Λ aggregates cardinal ratio-scale evidence about one object, not subject to Arrow's IIA impossibility. (5) "Gödel/Tarski: self-auditing is incoherent" — conceded as a limit; the substrate uses bounded recursion verified by an external stratified stack, not self-verification. (6) "Trust can't be engineered" — conceded and reframed: Λ produces audited evidence of trustworthiness-relevant properties; we claim only to make trustworthiness *checkable*.

---

## 10. Empirical posture *(measured, not proven)*

Per-receipt build latency ≈ 11.5 μs (p50) / 50.7 μs (p99); verification ≈ 10.4 μs (p50). Nine-axis Λ ≈ 3.12 μs (base) / 3.29 μs (composed). On a v11 platform run of 24,800 HTTP calls, governance overhead was 0.49–0.59 ms per route (p50), 1.27 ms (p99); ρ-closure was 100% on 8,000/8,000 paired calls. A deterministic 5× replay yields a byte-identical root. Archived under DOI [10.5281/zenodo.20119582](https://doi.org/10.5281/zenodo.20119582). A Sim2Real "Walrus-parallel" experiment measured a mean α-gap of 0.10 across five regimes (4/5 transfer at α=0.00; adversarial α=0.50, N=60), reported as preliminary.

### 10.1 Measurement methodology + latency table

Wall-clock timings of the production receipt path, collected in-process with a monotonic nanosecond clock, reported as empirical percentiles over one archived run (no confidence intervals or cross-run variance claimed).

| Operation | p50 | p99 | What is measured |
|-----------|-----|-----|------------------|
| Receipt build | 11.5 μs | 50.7 μs | Canonicalize + hash + chain + persist |
| Receipt verify | 10.4 μs | — | Chain re-check + root comparison |
| Λ9 (base) | 3.12 μs | — | Nine-axis geometric mean, isolated |
| Λ9 (composed) | 3.29 μs | — | Within a composed gate evaluation |
| Governance overhead / route | 0.49–0.59 ms | 1.27 ms | Governed minus ungoverned, 24,800 calls |

---

## 11. Limitations and honesty section

- **Λ is Conjecture 1 unconditionally.** Unconditional uniqueness under A1–A5 is false (Theorem 4.2). Only the conditional theorem under declared A6′ holds, and whether A6′ is the philosophically correct demand is open. We never claim Λ proven unconditionally.
- **The locked count is exactly 5.** {F1,F11,F12,F18,F19} at `c7c0ba17` (749/14/163). The 21-formula experimental pass, the +19 Wave-3 theorems, and the Wave-4 Λ modules are **not** in the locked count until re-audited.
- **Open sorries remain.** The locked kernel carries 163 sorries; the live experimental scope carries on the order of 256 non-comment sorries. The analytic Cauchy step (monotone + additive ⇒ linear) has one isolated, named open obligation; F12/F19 are additive scaffolding, not the full physical theorems.
- **SLSA L2, not L3.** Supply-chain attestation is L1+L2; L3 is **not** claimed.
- **Declared idealizations.** Tamper-evidence, attribution, and Merkle binding hold only under declared collision-resistance / unforgeability axioms; these are idealizations, disclosed in every `#print axioms` ledger.
- **CI-pending re-exports.** Tsirelson, CHSH, and Jensen re-exports red-light the wired build; **not** claimed proven.
- **Scope.** The substrate verifies a governance-aggregator and receipt layer, not an end-to-end AI system; it is far smaller in scope and maturity than a fully verified OS kernel.

---

## 12. Conclusion

The Unified Substrate (v23) consolidates twenty-two versions of a single idea: that trust in a governed AI must be earned by checkable evidence, and that the machinery for earning it — a bounded self-governing loop, a principled trust aggregator, and a tamper-evident proof trail — can be *partially* machine-verified today with complete honesty about its limits.

> **The one-line thesis:** *v23 is the first machine-verified governed-AI trust substrate with fully disclosed axioms, in which the central trust aggregator's uniqueness is proven conditionally (under a declared, governance-natural block-consistency axiom) while its unconditional uniqueness is machine-checked false — so the conditional theorem is the maximal true statement and the invariant is honestly labeled Conjecture 1, never a theorem.*

The contribution is not a new theorem but a new *standard*: locked counts, disclosed axioms, and a machine-checked refutation guarding the one tempting overclaim. We submit that this calibrated honesty is precisely what a regulator, an auditor, or a defense customer should require — and what makes every positive claim in the substrate credible.

---

## 13. Appendix A: Reproducibility and artifact manifest

### 13.1 Pinned commits and artifacts

| Component | Repository | Pin | Contents / status |
|-----------|-----------|-----|-------------------|
| Locked kernel | szl-holdings/lutar-lean | `c7c0ba17` | Doctrine v11; 749 decl / 14 axioms / 163 sorries; locks {F1,F11,F12,F18,F19} |
| Wave-3 proofs | szl-holdings/lutar-lean | `775093f0` | C8–C20 sorry-free cores |
| Wave-3 root wiring | szl-holdings/lutar-lean | `02e44c30` | Mathlib-free modules wired into root; CI-green |
| Wave-4 (Λ / A6′) | szl-holdings/lutar-lean | `043c3df` | LambdaBlockConsistency.lean; conditional uniqueness CI-green |
| Knowledge base | szl-holdings/a11oy | — | a11oy-knowledge: axioms, theorems, constants, DOIs |
| This paper | szl-holdings/szl-papers | thesis/v23/ | main.tex, refs.bib, main.pdf, main.md, README.md |

### 13.2 How to verify

```
# 1. Kernel-check the locked core and Wave-3/4 modules
$ git checkout 02e44c30 && lake build        # expect: green, no errors

# 2. Disclose the trusted axiom base of any theorem
$ #print axioms lambda_unique_under_block
=> [A6'_block_consistent, propext, Quot.sound, Classical.choice]

# 3. Confirm the refutation of the overclaim is sorry-free
$ #print axioms maxAgg_ne_Lambda            # => Lean-core axioms only
```

### 13.3 Trusted computing base

The bottom turtles, stated once: (i) soundness of the Lean 4 kernel and its core axioms (`propext`, `Quot.sound`, `Classical.choice`); (ii) the declared cryptographic idealizations (`hash_collision_resistant`, `ecdsa_unforgeable`, the Merkle collision-resistance axioms); (iii) the single declared governance axiom `A6'_block_consistent`, used only in the conditional Λ theorem; and (iv) the human sign-off gating CI. Everything else is derived.

---

## 14. Appendix B: Notation and glossary

| Symbol / term | Meaning |
|---------------|---------|
| Λ_k(x) | The Lutar invariant: equal-weight geometric mean (∏_i x_i)^{1/k} on [0,1]^k |
| Φ | A generic candidate aggregator [0,1]^k → [0,1] satisfying some subset of A1–A6′ |
| maxAgg | The max aggregator; the machine-checked witness that A1–A5 do not pin Λ (Theorem 4.2) |
| A1–A5 | Monotonicity, positive homogeneity, idempotence, boundedness, permutation-invariance |
| A6′ | Block-consistency / aggregation-invariance: the declared governance axiom of the conditional theorem |
| link_i, root | The i-th hash-chain entry and the Merkle commitment to a batch of receipts (§5.4) |
| sorry-free | A Lean development with no `sorry` placeholder; the kernel checks every step |
| CI-green | The real continuous-integration `lake build` passes — a full kernel check at the pinned commit |
| axiom-gated | Sorry-free given an explicitly declared, disclosed idealizing axiom |
| `#print axioms` | Lean command that lists the trusted axiom base a given theorem depends on |
| Conjecture 1 | The open philosophical claim that A6′-type block-consistency is the correct governance demand; never a theorem |

---

## 15. References

1. Aczél, J. (1948). On mean values. *Bull. Amer. Math. Soc.* 54(4):392–400. [doi:10.1090/S0002-9904-1948-09020-9](https://doi.org/10.1090/S0002-9904-1948-09020-9)
2. Aczél, J. & Saaty, T. L. (1983). Procedures for synthesizing ratio judgements. *J. Math. Psychology* 27(1):93–102. [doi:10.1016/0022-2496(83)90028-7](https://doi.org/10.1016/0022-2496(83)90028-7)
3. Brundage, M., Avin, S., Wang, J., et al. (2020). Toward Trustworthy AI Development: Mechanisms for Supporting Verifiable Claims. [arXiv:2004.07213](https://arxiv.org/abs/2004.07213)
4. Clauser, J. F., Horne, M. A., Shimony, A. & Holt, R. A. (1969). Proposed Experiment to Test Local Hidden-Variable Theories. *Phys. Rev. Lett.* 23(15):880–884. [doi:10.1103/PhysRevLett.23.880](https://doi.org/10.1103/PhysRevLett.23.880)
5. Csátó, L. (2018). Characterization of the row geometric mean ranking with a group consensus axiom. *Group Decision and Negotiation* 27(6):1011–1027. [doi:10.1007/s10726-018-9589-3](https://doi.org/10.1007/s10726-018-9589-3); arXiv:1706.07256.
6. Dwork, C., Lynch, N. & Stockmeyer, L. (1988). Consensus in the Presence of Partial Synchrony. *J. ACM* 35(2):288–323. [doi:10.1145/42282.42283](https://doi.org/10.1145/42282.42283)
7. Fischer, M. J., Lynch, N. A. & Paterson, M. S. (1985). Impossibility of Distributed Consensus with One Faulty Process. *J. ACM* 32(2):374–382. [doi:10.1145/3149.214121](https://doi.org/10.1145/3149.214121)
8. Gettier, E. L. (1963). Is Justified True Belief Knowledge? *Analysis* 23(6):121–123. [doi:10.1093/analys/23.6.121](https://doi.org/10.1093/analys/23.6.121)
9. Goldman, A. I. (1979). What Is Justified Belief? (process reliabilism). [SEP: reliabilism](https://plato.stanford.edu/entries/reliabilism)
10. Jensen, J. L. W. V. (1906). Sur les fonctions convexes. *Acta Math.* 30:175–193. [doi:10.1007/BF02418571](https://doi.org/10.1007/BF02418571)
11. Kolmogorov, A. N. (1930). Sur la notion de la moyenne. *Atti Accad. Naz. Lincei* 12:388–391.
12. Kraft, L. G. (1949). A device for quantizing, grouping, and coding amplitude-modulated pulses. M.S. thesis, MIT (cf. McMillan 1956, [doi:10.1109/TIT.1956.1056818](https://doi.org/10.1109/TIT.1956.1056818)).
13. Krantz, D. H., Luce, R. D., Suppes, P. & Tversky, A. (1971). *Foundations of Measurement, Vol. I*. Academic Press.
14. Lakatos, I. (1976). *Proofs and Refutations*. Cambridge University Press.
15. Maksa, G., Mokken, R. J. & Münnich, Á. (2026). N-ary quasi-arithmetic means and families without regularity. [arXiv:2606.05221](https://arxiv.org/html/2606.05221v1)
16. Merkle, R. C. (1979). Secrecy, Authentication, and Public Key Systems. Ph.D. dissertation, Stanford University.
17. National Telecommunications and Information Administration (2024). AI Accountability Policy Report: Proof of Claims and Trustworthiness. [ntia.gov](https://ntia.gov)
18. Nozick, R. (1981). *Philosophical Explanations* (truth-tracking / sensitivity). Harvard University Press.
19. Pease, M., Shostak, R. & Lamport, L. (1980). Reaching Agreement in the Presence of Faults. *J. ACM* 27(2):228–234. [doi:10.1145/322186.322188](https://doi.org/10.1145/322186.322188)
20. ProVerif transparency-protocol verification (2023). [arXiv:2303.04500](https://arxiv.org/abs/2303.04500)
21. RFC 6962 (2013). Certificate Transparency. Laurie, Langley & Kasper. [rfc-editor.org/info/rfc6962](https://rfc-editor.org/info/rfc6962)
22. Saltzer, J. H. & Schroeder, M. D. (1975). The Protection of Information in Computer Systems. *Proc. IEEE* 63(9):1278–1308. [doi:10.1109/PROC.1975.9939](https://doi.org/10.1109/PROC.1975.9939)
23. Shannon, C. E. (1948). A Mathematical Theory of Communication. *Bell Syst. Tech. J.* 27(3):379–423. [doi:10.1002/j.1538-7305.1948.tb01338.x](https://doi.org/10.1002/j.1538-7305.1948.tb01338.x)
24. SLSA (2023). Supply-chain Levels for Software Artifacts (L1–L4). Open Source Security Foundation. [slsa.dev](https://slsa.dev)
25. Tsirelson, B. S. (1980). Quantum generalizations of Bell's inequality. *Lett. Math. Phys.* 4(2):93–100. [doi:10.1007/BF00417500](https://doi.org/10.1007/BF00417500)

---

*Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>*
*Co-authored with the SZL full-stack PhD team (mathematics, scientific writing, physics, CS, ML, philosophy of mathematics).*

*Honesty doctrine preserved verbatim: Λ is Conjecture 1 unconditionally (never a theorem); the conditional theorem holds only under the declared `A6'_block_consistent`; locked/proven = 5; declared axioms disclosed in every `#print axioms` ledger; SLSA L1+L2 (not L3). No fabricated results, no fake citations.*
