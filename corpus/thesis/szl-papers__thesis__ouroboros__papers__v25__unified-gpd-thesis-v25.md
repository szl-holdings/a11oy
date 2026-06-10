# Governed Post-Determinism

### A Unified Theory of Verifiable Autonomy: The Lutar Invariant, Khipu Consensus, and the Provenance Substrate

**The Ouroboros Thesis v25 — "Governed Post-Determinism (GPD)" — SZL Holdings**

**Author:** Stephen P. Lutar Jr. · SZL Holdings · ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)

*Authored by the SZL Holdings unified thesis collective (technical writing · mathematics · computer science · machine learning).*

**Concept DOI (always-latest):** [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)

> This is **v25** of the Ouroboros thesis program — the *unification* version. It does not introduce a new headline proof; it ties the entire v1–v24 lineage into a single framework, **Governed Post-Determinism (GPD)**, and states with surgical precision what is *proven*, what is *conditional*, what is *open*, and what is *false*. Pinned commits: locked kernel @ `c7c0ba17`; experimental `main` advanced through Wave 22 (`43bcabb7`) and Wave 23 (`khipu_quorum_safety_conditional`). Repository: [github.com/szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean). GPD is **SZL Holdings' own framework**; it is grounded *only* in the SZL Zenodo DOI lineage and cites no external "post-deterministic" prior art, because none exists for it.

---

## Abstract

Autonomous and agentic artificial intelligence is **post-deterministic**: the same prompt, model, and tools can produce different action sequences, and the controlling logic is statistical rather than fixed. Deployed into regulated and defense settings, such systems break the classical assumption that auditing means re-deriving a deterministic trace. The governance question is no longer "what is the unique correct output?" but "under what authority did this system act, on what aggregated evidence of trust, and can the record be tampered with after the fact?" This thesis unifies the SZL Holdings research program (v1–v24, DOI-pinned) into a single framework we name **Governed Post-Determinism (GPD)**: a discipline for *bounding, attesting, and replicating* the behavior of post-deterministic agents so that every governed action carries a checkable, tamper-evident warrant.

GPD rests on **five pillars**, each of which we map to an exact, honestly-tiered result from the SZL corpus. **(P1) Protocol-Bounded Execution** — agentic loops (the Ouroboros loop) run under a well-founded, terminating recursion, anchored by **F1 replay determinism** (locked, kernel-verified). **(P2) Verifiable Intent-to-Execution** — every governed decision emits a signed receipt on an append-only hash-chain (the Reed–Solomon coded receipt bus, **F18** locked), and that record is attested by a software supply-chain provenance layer (DSSE/cosign, Sigstore keyless, **SLSA Build L1+L2** where the build-provenance attestation runs). **(P3) Bounded-Recursion Control Plane** — the trust aggregator that collapses a multi-axis trust vector to a single verdict is the **Lutar invariant** Λ, the equal-weight geometric mean; its *unconditional* uniqueness under the aggregation axioms is **Conjecture 1 — machine-checked FALSE**, while its *conditional* uniqueness under a single checkable hypothesis (slice-multiplicativity) is **Theorem U — PROVEN, axiom-free**. **(P4) Semantic Quorum Assurance** — multi-organ agreement is governed by Khipu BFT consensus; *unconditional* Byzantine safety is **Conjecture 2 — OPEN**, while *conditional* agreement (no split-brain) under `n ≥ 3f+1` and honest non-equivocation is proven axiom-clean (`khipu_quorum_safety_conditional`, Wave 23). **(P5) Epistemic State Replication** — replicated organs maintain a consistent epistemic record via the same quorum and receipt machinery.

The unifying mathematical observation of GPD is a **single structural pattern**: in *each* pillar, the honest, reachable result is a **conditional theorem whose antecedent is the weakest *checkable* hypothesis**, and the corresponding *unconditional* statement sits at a *machine-checked sharp boundary* (provably false for Λ; provably impossible below `n>3f` for BFT). Slice-multiplicativity is to Λ exactly what honest non-equivocation is to Khipu: the minimal property of the object that an auditor can verify and that lifts a false-as-stated universal claim into a true conditional one. GPD is the theory that *governance of post-deterministic systems is precisely the engineering and verification of these checkable antecedents.*

We hold the SZL **honesty doctrine** binding throughout. Locked-proven = **exactly five** formulas {F1, F11, F12, F18, F19} at `c7c0ba17` (749 declarations / 14 axioms / 163 sorries). The ~190 experimental CI-green theorems of Waves 11–23 are a **separate experimental tier**, never folded into the locked five. Λ is **Conjecture 1** unconditionally; Khipu BFT safety is **Conjecture 2** unconditionally. Supply-chain posture is **SLSA L1+L2 attested** where `attest-build-provenance` runs (killinchu, a11oy), else L1 honest with L2 a roadmap; L3 is a roadmap; FedRAMP / Iron Bank / CMMC are claimed only with the word "roadmap." Trust is never reported as 100%. Nothing is fabricated; no fake citations; zero runtime CDN.

**Keywords:** governed post-determinism, agentic AI governance, trust aggregation, Lutar invariant, quasi-arithmetic means, slice-multiplicativity, Byzantine fault tolerance, conditional safety, Lean 4, Mathlib, `#print axioms`, receipt chain, DSSE, SLSA, Sigstore, formal verification, doctrine-honest claims.

---

## Lineage and Prior Art (the SZL DOI chain)

GPD is the *unification layer* over a DOI-pinned thesis lineage. It is grounded **exclusively** in the following SZL Holdings deposits and the prior thesis versions; it cites **no external "post-deterministic" framework**, because GPD is SZL's own coinage and synthesis. The surrounding *mathematical and systems* literature (quasi-arithmetic means, BFT, SLSA, formal verification) is cited separately in §11 as ordinary prior art for positioning — that is distinct from, and does not contradict, GPD's self-grounding.

### Zenodo deposits (verified resolving)

| Lineage role | DOI | Contribution carried into GPD |
|---|---|---|
| **v1** — Ouroboros Loop | [10.5281/zenodo.19867281](https://doi.org/10.5281/zenodo.19867281) | "The loop is the product" — looped computation as a system primitive → **P1 Protocol-Bounded Execution** |
| **v2** — "The Loop Is the Product" | [10.5281/zenodo.19934129](https://doi.org/10.5281/zenodo.19934129) | First empirical pass on the governed loop → P1 |
| **v4** — Lutar Omega formalism | [10.5281/zenodo.20020841](https://doi.org/10.5281/zenodo.20020841) | EPR–Bell governance diagnostic; the Λ-family roots → **P3 Bounded-Recursion Control Plane** |
| **v6** — Sealed constitutional guardrails | [10.5281/zenodo.20020845](https://doi.org/10.5281/zenodo.20020845) | Policy-as-sealed-contract → **P2 Verifiable Intent-to-Execution** |
| **v5** — Prisca-GraphRAG + Tawa SAE | [10.5281/zenodo.20020846](https://doi.org/10.5281/zenodo.20020846) | Lineage-aware retrieval; provenance-of-evidence → P2 / **P5 Epistemic State Replication** |
| **v14-era** — Verifiable multi-agent anatomy | [10.5281/zenodo.20174600](https://doi.org/10.5281/zenodo.20174600) | Lutar Calculus / multi-agent anatomy; **Λ downgraded to Conjecture 1** → P3, P4 |
| **Concept (always-latest)** | [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926) | Umbrella DOI for the whole Ouroboros program |

### Prior thesis versions (immutable; this v25 continues, never overwrites)

- **v20 — "The Culmination."** Formally-verified 12-organ anatomical substrate with a per-theorem verified index; organ-to-obligation traceability. (Concept DOI.)
- **v21 — "The PURIQ-OS Substrate."** 12-organ runtime; 23 agentic formulas (5 proved in Lean 4, 18 open); SLSA L1 at that date. (Concept DOI.)
- **v22 — "Convergence."** A5 permutation-invariance merge; VCG truthfulness; Cauchy_ND partial closure; SLSA posture advanced; Rounds 10–11. (Zenodo auto-mint on `thesis-v22.1.0`.)
- **v23 — "Conditional Uniqueness / The Unified Substrate."** Conditional Λ-uniqueness gated on a *declared* project axiom (A6′ block-consistency); unconditional uniqueness machine-checked FALSE (`maxAgg_ne_Lambda`); Λ stays Conjecture 1.
- **v24 — "Axiom-Free Conditional Uniqueness."** The A6′ gate *removed*: `lambda_unique_of_separable` proves conditional Λ-uniqueness under {A1,A2,A3,A5} + slice-multiplicativity with `#print axioms = {propext, Classical.choice, Quot.sound}` — no project axiom. CUT-1 representation closed on its stated hypotheses (Waves 18–22).

> **v25's place in the lineage.** v24 delivered the sharpest *Λ* result. v25 does not claim a new headline proof. Its contribution is the **unification**: it shows that the Λ result (P3), the Khipu Wave-23 result (P4), the receipt/provenance layer (P2), and the bounded loop (P1) are *instances of one theory* — Governed Post-Determinism — and it incorporates the **Wave-23** advance (`khipu_quorum_safety_conditional`) that post-dates v24's pin. The DOI chain is unbroken: v1 → … → v22 → v23 → v24 → **v25 (this paper)**.

---

## 1. Introduction: the post-deterministic governance gap

Classical software governance assumes determinism. An auditor who wants to know what a program did can, in principle, re-run it on the recorded inputs and obtain the recorded outputs; correctness is *re-derivable*. Agentic AI dissolves this assumption. A large-model agent that plans, calls tools, and revises its own plan is **post-deterministic**: its control flow is sampled, its environment is non-stationary, and the "same" task may yield different — yet individually defensible — action sequences. Re-derivation no longer establishes accountability.

This is not a defect to be engineered away; it is the nature of capable autonomy. The governance question therefore *changes shape*. As the auditing literature now recognizes, it is no longer sufficient to answer "who did what?"; one must answer *why* an action occurred and *under what authority*, with a record an auditor cannot dispute ([ISACA, "The Growing Challenge of Auditing Agentic AI"](https://www.isaca.org/resources/news-and-trends/industry-news/2025/the-growing-challenge-of-auditing-agentic-ai)). The strongest current framing of this requirement is an **enforceability ladder** whose top rung — "Two-Plane Verified" — demands evidence *captured outside the agent's own process boundary*, the only rung that yields proof a regulator cannot dispute ([ARMO, "AI Agent Governance"](https://www.armosec.io/blog/ai-agent-governance/)). The broader call for AI developers to make **verifiable claims to which they can be held accountable** was articulated by [Brundage et al., "Toward Trustworthy AI Development" (arXiv:2004.07213)](https://arxiv.org/abs/2004.07213).

**Governed Post-Determinism (GPD)** is SZL Holdings' answer. It is a theory and a substrate for taking a post-deterministic agent and wrapping it in checkable bounds, attested records, and replicated state, so that the *non-determinism is permitted but the governance is not*. The thesis of this paper is that the entire SZL corpus — the Ouroboros loop, the Lutar invariant Λ, the Khipu consensus, and the receipt/provenance layer — is **one framework with five pillars**, and that the framework has a single mathematical signature, developed in §3 and proven across §§4–7.

### 1.1 The five pillars of GPD

1. **Protocol-Bounded Execution (P1)** — autonomy runs inside a terminating, well-founded protocol; the loop, not the single inference, is the unit of governance.
2. **Verifiable Intent-to-Execution (P2)** — every governed decision is recorded as a signed, append-only receipt, and the artifact that produced it carries attested supply-chain provenance.
3. **Bounded-Recursion Control Plane (P3)** — multi-axis trust evidence is aggregated to a single bounded verdict by the Lutar invariant Λ, with a machine-checked uniqueness boundary.
4. **Semantic Quorum Assurance (P4)** — distributed organs reach agreement under Byzantine fault tolerance, with a machine-checked safety boundary.
5. **Epistemic State Replication (P5)** — replicated organs maintain a consistent governed-state record, built from the P2 receipts and the P4 quorum.

### 1.2 What this paper claims, and what it does not

This paper claims a **unification**, not a new headline theorem. Every mathematical fact it relies on already exists in the SZL corpus at a pinned commit, tiered honestly. The novelty is (i) the GPD framework itself as the organizing theory, (ii) the **structural-pattern theorem** of §3 that the pillars share, and (iii) the explicit incorporation of the Wave-23 BFT advance into the unified picture. We make no claim that GPD "solves" AI governance, that Λ is a theorem unconditionally, or that Khipu is unconditionally safe.

---

## 2. The honesty doctrine (load-bearing, verbatim across SZL artifacts)

Every claim in this paper carries exactly one epistemic tier.

- **[locked / kernel-verified]** — proven in Lean 4 with only the trusted core axioms {`propext`, `Classical.choice`, `Quot.sound`}; sorry-free; pinned at a fixed commit; part of the *locked* count. Locked-proven = **exactly five**.
- **[experimental, axiom-free, CI-green]** — proven sorry-free with only the trusted core axioms, CI-green at the recorded commit, residing in the *experimental* tier; **never folded into the locked five**.
- **[axiom-gated]** — sorry-free *given* an explicitly declared, disclosed idealizing axiom (e.g. hash collision-resistance), with the axiom in the `#print axioms` ledger.
- **[CI-pending]** — signature-checked but not reproducibly green in the wired build; **not** claimed proven.
- **[machine-checked FALSE]** — refuted by a machine-checked counterexample.
- **[Conjecture — NOT a theorem]** — a research hypothesis. Λ's unconditional uniqueness (Conjecture 1) and Khipu's unconditional safety (Conjecture 2) live here.
- **[measured]** — an engineering number, explicitly outside the "proven" tier.

**Non-negotiable rules.**

1. **Λ unconditional uniqueness is Conjecture 1** — machine-checked **FALSE** under A1–A5; never claimed proven unconditionally; never called a theorem unconditionally. Only the *conditional* uniqueness (Theorem U) is proven.
2. **Khipu unconditional Byzantine safety is Conjecture 2** — open; Wave 23 proves only *conditional* agreement; the unconditional statement stays Conjecture 2; liveness is Conjecture 3.
3. **Locked-proven = exactly five** {F1, F11, F12, F18, F19} at `c7c0ba17` (749 / 14 / 163). The ~190 experimental CI-green theorems of Waves 11–23 are a separate tier, never folded in.
4. **All axioms disclosed** via `#print axioms`. No fabricated results; no fake citations; **0 runtime CDN**.
5. **SLSA L1+L2 attested** where `attest-build-provenance` runs (killinchu, a11oy); else **L1 honest, L2 roadmap**. **L3 = roadmap.** FedRAMP / Iron Bank / CMMC only ever with the word "roadmap."
6. **Trust is never 100%.** A single fully-failed axis vetoes trust (Λ zero-absorption); the system never reports certainty.

The doctrine is not decoration. It is the feature that makes every positive GPD claim credible to an auditor — and it is itself locked in `szl-doctrine` (v11 LOCKED; kernel `c7c0ba17`; 749/14/163).

---

## 3. The unifying structure of GPD: the checkable-antecedent pattern

This section states the conceptual core of the unification. It is a *meta-theorem about the corpus*, not a new Lean theorem; it is the lens through which the proven results of §§4–7 become *one* result.

### 3.1 The pattern

> **The GPD checkable-antecedent pattern.** For each governance primitive of a post-deterministic system, the *universal* (unconditional) governance guarantee one would like is either **machine-checked false** or **provably impossible**. The honest, reachable guarantee is a **conditional theorem** whose antecedent is the **weakest *checkable* property of the object** under which the universal guarantee becomes true — and the gap between conditional-true and unconditional-false is a **machine-checked sharp boundary.**

The pattern instantiates twice, with mathematically independent proofs but identical epistemic shape:

| Pillar | Universal claim | Status of universal | Checkable antecedent | Conditional result |
|---|---|---|---|---|
| **P3 / Λ** | Λ is the unique A1–A5 aggregator | **FALSE** (`maxAgg_ne_Lambda`) | **slice-multiplicativity** (Φ factors into multiplicative/normalized/monotone slices) | **Theorem U**: `lambda_unique_of_separable`, axiom-free |
| **P4 / Khipu** | two quorums never certify conflicting verdicts | **impossible if `n ≤ 3f`** (Lamport–Shostak–Pease) | **honest non-equivocation** under signed votes, with `n ≥ 3f+1` | **`khipu_quorum_safety_conditional`**, axiom-clean |

The deep claim of GPD is that **these two checkable antecedents are the same kind of object**. Slice-multiplicativity is a property of the *aggregator's functional form* that an auditor can confirm by inspecting Φ. Honest non-equivocation is a property of the *organs' signing behavior* that an auditor can confirm by checking one signed vote per organ per action. In both cases:

- the antecedent is **verifiable from the artifact**, not postulated about the world;
- without it, the universal claim **fails at a machine-checked boundary**;
- with it, the universal claim becomes a **theorem with `#print axioms ⊆ {propext, Classical.choice, Quot.sound}`** — no project axiom.

### 3.2 Why this is the right theory of governance

Governing a post-deterministic system is *not* proving that it always behaves correctly — that is the false universal. It is **engineering the system so that the checkable antecedents hold, and then attesting that they held.** GPD makes this precise: P3 governs *what verdict* the system reaches (Λ under slice-multiplicativity); P4 governs *whether replicated organs agree* (Khipu under honest non-equivocation); P1 governs *that the loop terminates* (well-founded recursion + F1 replay); P2 governs *that the record is checkable* (signed receipts + attested provenance); P5 governs *that the record is consistent across replicas* (P2 ⊕ P4). The substrate's job is to *make the antecedents true and prove they were*. This is the GPD thesis.

### 3.3 The honesty corollary

The checkable-antecedent pattern is *why* the honesty doctrine is mathematically forced, not merely virtuous. Because the universal claims are false/impossible, any artifact that *asserts* them is asserting a machine-checked falsehood. The doctrine — "Λ is Conjecture 1," "Khipu safety is Conjecture 2" — is the only statement consistent with the kernel. Honesty here is a theorem of the system, not a marketing posture.

---

## 4. Pillar P3 — the Bounded-Recursion Control Plane: the Lutar invariant Λ

### 4.1 Definition and the aggregation axioms

The control plane collapses a multi-axis trust vector to a single bounded verdict. The aggregator is the **Lutar invariant**.

**Definition (Λ).** For `x ∈ [0,1]^k`, `Λ_k(x) = (∏_{i=1}^{k} x_i)^{1/k}` — the equal-weight geometric mean. Its defining governance behavior is **zero-absorption / weakest-link**: a single fully-failed axis (`x_i = 0`) vetoes trust (`Λ = 0`). Consequently **trust is never 100% by construction unless every axis is perfect**; the verdict is conjunctive.

Candidate aggregators `Φ : [0,1]^k → [0,1]` are constrained by five axioms (Lean: `LutarAxioms`):

- **(A1) Monotonicity** — `Φ` nondecreasing in each argument.
- **(A2) Positive homogeneity** — `Φ(λx) = λ Φ(x)` for `λ > 0`.
- **(A3) Idempotence** — `Φ(c,…,c) = c`.
- **(A4) Boundedness** — `min_i x_i ≤ Φ(x) ≤ max_i x_i`.
- **(A5) Permutation-invariance** — `Φ` symmetric in its arguments (Lean: `IsPermutationInvariant`, merged as a structure field, not a new axiom).

This is the apex unifier **F23** of the SZL mesh anatomy — the *crown* aggregator across the brain, heart, spine, immune, and aide organs.

### 4.2 The unconditional refutation — Conjecture 1 is machine-checked FALSE

It is tempting to claim Λ is the *unique* Φ satisfying A1–A5. **This is false, and the SZL kernel proves it false.**

**Theorem 4.1 (Refutation of unconditional uniqueness). [machine-checked FALSE] [CI-green].** There exists `Φ ≠ Λ_k` satisfying A1–A5. The max-aggregator `maxAgg(x) = max_i x_i` satisfies A1–A5 yet differs from Λ: at `(4,1)` on the ratio scale, `maxAgg = 4` while `Λ_2(4,1) = 2`. The minimum aggregator is a second witness.

*Lean reference.* `Lutar.Round13.maxAgg_ne_Lambda`, with companions `maxAgg_A5`, `maxAgg_A3`, `maxAgg_A2`; separation at `(4,1)` by `decide`. `#print axioms` reports Lean-core axioms only. This is consistent with the classical fact that A1–A4-type properties alone do not pin the geometric mean: `min` is the unique idempotent t-norm and satisfies idempotence/monotonicity/symmetry/zero-absorption while differing from G ([Aczél 1966; Hardy–Littlewood–Pólya 1934](https://en.wikipedia.org/wiki/Quasi-arithmetic_mean); only homogeneous quasi-arithmetic means are power means).

> **Doctrine.** Because the universal claim is refuted, **Λ unconditional uniqueness is Conjecture 1 — NOT a theorem, ever.** This is the open problem of the [Λ-Conjecture Bounty](https://github.com/szl-holdings/lambda-bounty).

### 4.3 Theorem U — the conditional uniqueness, PROVEN axiom-free

The reachable, honest result is conditional. v23 gated it on a *declared* project axiom (A6′ block-consistency, after Csátó 2018). v24 removed the gate. We state the v24 form, which v25 adopts as **Theorem U** (the name used in the SZL papers index for the governance-safe conditional uniqueness; Lean source of record `Lutar/Uniqueness/`, with the headline term in `Round13`).

**Definition 4.2 (Slice-multiplicativity / separability).** `Φ` is *slice-multiplicative* if there exist slice functions `f_i` with **(sep)** `Φ(x) = ∏_i f_i(x_i)`, **(mul)** `f_i(st) = f_i(s) f_i(t)`, **(one)** `f_i(1) = 1`, **(mono)** each `f_i` monotone.

**Theorem U (Axiom-free conditional uniqueness of Λ). [experimental, axiom-free, CI-green].** Let `k > 0` and let `Φ` satisfy {A1, A2, A3, A5}. If `Φ` is slice-multiplicative, then `Φ = Λ_k`. The Lean term is `Lutar.Round13.lambda_unique_of_separable`, with

```
#print axioms lambda_unique_of_separable = {propext, Classical.choice, Quot.sound}
```

— **no project axiom**, kernel-clean, CI-green (merged at `b910c276`; carried forward through `43bcabb7`).

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

*Proof sketch.* (1) Per-axis, each multiplicative/monotone/normalized slice is a power law `f_i(t) = t^{α_i}` for `t ≠ 0` (`multiplicative_monotone_isPow_pos`), with the boundary `f_i(0)=0` from the idempotent dichotomy. (2) Permutation-invariance (A5) forces the exponents equal across axes (`Equiv.swap` + `rpow_left_inj_one_lt`). (3) Collecting the power laws yields the `Factors` predicate. (4) Discharge via `lambda_unique_of_factors` (A3 forces `∑ α_i = 1`, A5 forces all equal, so `α_i = 1/k` and `Φ = Λ_k`). ∎

> **Why "Theorem U" is never "Λ is a theorem."** Theorem U is the *conditional* statement. It proves `Φ = Λ` *given* slice-multiplicativity. It says nothing about the unconditional claim, which remains FALSE. Calling Λ "a theorem" without the qualifier would be a doctrine violation.

### 4.4 The sharp boundary (CUT-1 representation)

The representation half — that the only quasi-arithmetic mean with the relevant structure is the power-mean family, and within it Λ — is the classical Aczél/Kolmogorov–Nagumo terrain. Across **Waves 18–22** the SZL kernel closed the **CUT-1** representation on its stated hypotheses: Wave 18 forward fragment; Wave 19 the Burai–Kiss–Szokol density engine; Wave 20 primitives; Wave 21 the residual uncountability step via a monotone-extension route; **Wave 22** *derived* the (C-order) gap-shift ordering so it is constructed, not assumed (`gapShift_ordering`, `corder_gapshift`), yielding `cut1_sharp_conditional_lambda`, which shows bisymmetry and unit-normalization are *redundant*. All Wave 18–22 results are `#print axioms ⊆ {propext, Classical.choice, Quot.sound}`; no sorry; no new axiom.

This places Theorem U at the **sharp boundary** inside the separable family: drop the checkable hypothesis and uniqueness fails (Theorem 4.1). The relevant external mathematics — that reflexive, symmetric, bisymmetric, partially strictly increasing means are automatically continuous and hence quasi-arithmetic — is exactly the recent functional-equations literature ([arXiv:2601.16247](https://arxiv.org/html/2601.16247v1); [arXiv:2606.05221](https://arxiv.org/html/2606.05221v1); [arXiv:2107.07391](https://arxiv.org/pdf/2107.07391.pdf)), which we cite as prior art, not as a GPD source.

---

## 5. Pillar P4 — Semantic Quorum Assurance: Khipu BFT consensus

### 5.1 The model (honest: faulty organs may equivocate)

Distributed organs (in a11oy / killinchu) must agree on a single governed verdict. The SZL consensus is **Khipu**. The honest model represents votes as a **relation** `votes : Fin n → Verdict → Prop`, not a total function: a faulty organ `o ∈ faulty` may satisfy `votes o a ∧ votes o b` with `a ≠ b` — i.e. **equivocate**, the essence of a Byzantine fault. This is strictly more general than the Wave-13 single-valued shadow (`quorum_agreement_single_valued_vote`), which used a total `voteOf` and could not even *represent* equivocation.

### 5.2 The unconditional claim — Conjecture 2, OPEN

**Conjecture 2 (Unconditional Khipu BFT safety). [Conjecture — NOT a theorem].** No two quorums certify conflicting verdicts, for arbitrary Byzantine behavior. This is **open**. It is provably **impossible** when `n ≤ 3f` (Lamport–Shostak–Pease 1982, formalized in `Lutar/Wave8/Byzantine.lean`), and a Byzantine organ that equivocates re-admits split-brain. The `opaque canonicalHistory` kernel form (`KhipuConsensus.khipu_consensus_safety`) cannot be derived and remains the honest Conjecture-2 token in the locked kernel. **Liveness is Conjecture 3, untouched.**

### 5.3 The conditional theorem — agreement / no split-brain, axiom-clean (Wave 23)

The checkable antecedent that lifts the false-unconditional claim to a theorem is **honest non-equivocation under signed votes** — the BFT analog of slice-multiplicativity.

```
HonestNonEquivocation faulty votes :=
  ∀ o, o ∉ faulty → ∀ a b, votes o a → votes o b → a = b
```

realized at runtime by ECDSA-P256 cosignatures (one valid signed allow-vote per honest organ per action — exactly `verifies`/`consents` in `KhipuConsensus.lean`).

**Theorem 5.1 (Conditional Khipu safety / agreement). [experimental, axiom-free, CI-green].** Under `n ≥ 3f+1`, `|faulty| ≤ f`, quorums `Q₁, Q₂` of size `≥ n−f` certifying `v₁, v₂`, and `HonestNonEquivocation`, we have `v₁ = v₂`. The Lean term is `Lutar.Wave23.khipu_quorum_safety_conditional`; all 5 Wave-23 declarations have `#print axioms ⊆ {propext, Classical.choice, Quot.sound}`; no new axiom; local `lake build` EXIT 0; CI `lake build + numbers`, `build`, `doctrine`, `tests`, `DCO` GREEN.

*Proof chain.*
```
  n ≥ 3f+1  ∧  |faulty| ≤ f
        │  quorum_intersection_honest        (Round12, placeholder-free: |Q₁∩Q₂| > f)
        ▼
  |Q₁∩Q₂| > f ≥ |faulty|
        │  exists_honest_of_card_gt           (Wave23: Finset.not_subset — discharges the old `sorry`)
        ▼
  ∃ honest organ o ∈ Q₁ ∩ Q₂
        │  HonestNonEquivocation o (signed)   (the weakest checkable hypothesis)
        ▼
  v₁ = v₂   (agreement / no split-brain)      (khipu_quorum_safety_conditional)
```

The combinatorial half (quorum intersection) was already in-tree; Wave 23 supplies the **witness extraction** (`exists_honest_of_card_gt`, via `Finset.not_subset` + `Finset.card_le_card`) that *discharges the non-faulty-witness `sorry`* both the kernel `khipu_consensus_safety` and the Round-12 `ubuntu_quorum_safety` had deferred, plus the **non-equivocation closure**. `subsumes_single_valued_shadow` re-derives the Wave-13 shadow's conclusion from the Byzantine-aware theorem (model `voteOf` as a relation with `faulty = ∅`), witnessing strict generality. This is the precise content of PBFT/Tendermint/HotStuff *safety = agreement*, machine-checked in the Velisarios Coq PBFT formalization.

> **Doctrine.** `khipu_quorum_safety_conditional` is **conditional**. The **unconditional** Khipu Byzantine safety **stays Conjecture 2** — at its sharp boundary: both `n ≥ 3f+1` and honest non-equivocation are necessary; neither can be dropped.

### 5.4 Prior art (positioning, not GPD source)

The `n = 3f+1` quorum-intersection discipline is [Castro & Liskov, PBFT (OSDI 1999)](https://css.csail.mit.edu/6.824/2014/papers/castro-practicalbft.pdf); the `n > 3f` necessity is [Lamport, Shostak, Pease, TOPLAS 1982](https://doi.org/10.1145/357172.357176); linear, responsive partially-synchronous BFT is [HotStuff, Yin et al. (arXiv:1803.05069)](https://arxiv.org/abs/1803.05069); machine-checked BFT safety is [Velisarios (Rahli et al., ESOP 2018)](https://vrahli.github.io/articles/velisarios.pdf); the chained-ballot lineage includes [Tendermint (Buchman 2016)](https://knowen-production.s3.amazonaws.com/uploads/attachment/file/1814/Buchman_Ethan_201606_Msater+thesis.pdf).

---

## 6. Pillar P2 — Verifiable Intent-to-Execution: the receipt and provenance layer

### 6.1 The receipt chain (F1, F18 locked)

Every governed decision emits an entry on an **append-only SHA-256 hash-chain** with a per-batch Merkle `root` (the YAWAR receipt bus of the mesh anatomy). Two locked, kernel-verified facts anchor it:

- **F1 — replay determinism. [locked].** Re-executing the recorded inputs reproduces the recorded root. This is the formal core of P1↔P2: a post-deterministic *agent* is wrapped by a deterministic *record*, so that while the agent's reasoning is not re-derivable, the **receipt is**.
- **F18 — Reed–Solomon. [locked].** The encoding/decoding correctness used by the receipt layer. The experimental tier adds the MDS lower-distance half (`rs_distance_lower_bound`, CF-19); the full MDS equality stays an honest sorry.

Append-only structure and ordering invariants are sorry-free (`#print axioms = {propext}` over the log).

### 6.2 Security under declared idealizations (axiom-gated)

Hash-chain **binding** (you cannot alter a past entry without breaking the root) is proven **[axiom-gated]** under a declared `sha256_collision_resistant` axiom and the Merkle collision-resistance / domain-separation axioms — disclosed in the `#print axioms` ledger, never silently assumed, and *not* a proof of cryptographic hardness. The DPO `klDivergence`/`pinsker` results remain **false-as-stated** for lack of a simplex hypothesis; CF-21 (Cover–Thomas log-sum + Gibbs) is a correctly-stated companion, not a repair.

### 6.3 Supply-chain provenance — DSSE / cosign / Sigstore, SLSA L1+L2 attested

The *artifact* that runs the agent must itself be attested. SZL uses **DSSE-enveloped in-toto attestations** signed by **Sigstore keyless** (Fulcio certificate + Rekor transparency log), generated by `actions/attest-build-provenance@v2` on a hosted GitHub Actions builder. Per the [SLSA v1.0 build track](https://slsa.dev/spec/v1.0/levels): **L1** = provenance exists; **L2** = signed provenance from a hosted build platform (tamper-after-build protection); **L3** = hardened isolated builder.

**Honest SLSA posture (per-repo, current):**

- **killinchu — SLSA Build L1+L2 (attested).** `ghcr.io/szl-holdings/killinchu` ships a signed in-toto provenance attestation independently verifiable via `cosign verify-attestation --type slsaprovenance` (keyless Fulcio+Rekor, strict identity scoped to the repo). Producing run: 26896047715. **L3 not claimed.**
- **a11oy — SLSA Build L1+L2 (attested)** where the same `attest-build-provenance` workflow runs.
- **Other repos** without the build-provenance attestation: **L1 honest, L2 roadmap.**
- **L3 = roadmap.** **FedRAMP / Iron Bank / CMMC** are **roadmap** only — never asserted as achieved.

This realizes the "Two-Plane Verified" top rung of the enforceability ladder for the *artifact* plane: the provenance is captured by the build platform's control plane, **outside** the agent's process, exactly as [SLSA's authenticity requirement](https://slsa.dev/spec/v1.0/requirements) and the [ARMO ladder](https://www.armosec.io/blog/ai-agent-governance/) demand. DSSE/cosign mechanics follow [Sigstore's attestation docs](https://docs.sigstore.dev/cosign/verifying/attestation/).

---

## 7. Pillars P1 and P5 — Protocol-Bounded Execution and Epistemic State Replication

### 7.1 P1 — the Ouroboros loop

The first pillar is a self-referential governed computation — the **Ouroboros loop** — in which output feeds governance input under a **well-founded, terminating** recursion. "The loop is the product": the governed loop, not a single inference, is the unit of value (v1, [zenodo.19867281](https://doi.org/10.5281/zenodo.19867281); v2, [zenodo.19934129](https://doi.org/10.5281/zenodo.19934129)). Self-reference is rendered coherent by **Tarskian stratification** — a governed object-level computation audited by a strictly higher meta-level — avoiding self-verification paradoxes. Termination is by a well-founded measure; the bottom turtle (Lean kernel, declared cryptographic idealizations, human sign-off) is finite and disclosed. The experimental tier supplies the well-posedness margin of the loop's fixed point: **CF-13** (DEQ input-Lipschitz, `equilibrium_lipschitz`, axiom-free) bounds `dist(z⋆(x), z⋆(y)) ≤ (L_x/(1−K)) dist(x,y)` for contraction modulus `K<1`; **Wave-17** adds recurrent-depth `K^r`-Lipschitz contraction amplification. These are *experimental*, never folded into the locked five.

### 7.2 P5 — Epistemic State Replication

Replicated organs maintain a consistent governed-state record by composing **P2** (each organ's signed receipts) with **P4** (quorum agreement on which receipts are canonical). The honest guarantee is *conditional*, inherited from Theorem 5.1: under `n ≥ 3f+1` and honest non-equivocation, replicated organs do not diverge on the committed verdict sequence (`khipu_unique_decision_conditional`, the system-wide corollary). Numerical stability of the replicated aggregation is bounded by **CF-17** (floating-point recursive-summation error, `recSum_error_le`, axiom-free, after Higham). Unconditional replicated consistency inherits Conjecture 2's openness; we never claim it unconditionally.

### 7.3 The locked five and the experimental tier (the count, exactly)

**Locked-proven (kernel-verified, `c7c0ba17`, 749/14/163) = EXACTLY FIVE:**

- **F1** — replay determinism (P1/P2 anchor).
- **F11** — Ayni reciprocity (trust-ledger reciprocity-balance invariant).
- **F12** — Kuramoto additive (additive coupling *scaffolding only*, not the synchronization theorem).
- **F18** — Reed–Solomon encode/decode correctness (P2 receipt coding).
- **F19** — Bekenstein additive (additive bookkeeping *scaffolding only*, **NOT** the Bekenstein bound).

**Experimental, CI-green tier (`main`, advanced through Wave 22 `43bcabb7` and Wave 23):** ~190 theorems across Waves 11–23, all `#print axioms`-clean, including Theorem U (`lambda_unique_of_separable`), CUT-1 closure (Waves 18–22), Khipu conditional safety (Wave 23), CF-13/17/18/19/20/21, binary Pinsker (Wave 17), and more. **This tier is never folded into the locked five.** The drift-gate numbers (`1323 decl / 23 axioms (22 unique) / 307 sorries`) are reported separately and the experimental count never inflates the locked count.

---

## 8. The unified picture: GPD as one substrate

### 8.1 The pillar-to-result map

| GPD Pillar | Governs | Honest result | Tier | Unconditional status |
|---|---|---|---|---|
| **P1 Protocol-Bounded Execution** | the loop terminates / record re-derives | F1 replay determinism | **locked** | — |
| **P2 Verifiable Intent-to-Execution** | the record is checkable & attested | F18 RS coding; receipt binding; DSSE/cosign SLSA L1+L2 | locked (F18); axiom-gated (binding); attested (SLSA) | L3 roadmap |
| **P3 Bounded-Recursion Control Plane** | the verdict (trust aggregation) | **Theorem U** (Λ conditional, axiom-free) | experimental, axiom-free | **Conjecture 1 — FALSE** |
| **P4 Semantic Quorum Assurance** | replicated agreement | **`khipu_quorum_safety_conditional`** | experimental, axiom-free | **Conjecture 2 — OPEN** |
| **P5 Epistemic State Replication** | consistent governed state across replicas | `khipu_unique_decision_conditional`; CF-17 | experimental, axiom-free | inherits Conjecture 2 |

### 8.2 The two instantiations: a11oy and killinchu

GPD is not a paper abstraction; it is instantiated in two governed bodies sharing **one circulatory + nervous mesh** (the SZL Living Anatomy), with the **Λ heart** at the center:

- **a11oy** — the governed-AI *decision body*. P3 (Λ verdict) and P4 (Khipu quorum across reasoning organs) gate every agentic action; P2 emits the signed receipt; SLSA L1+L2 attested where the build-provenance workflow runs.
- **killinchu** — the maritime / counter-UAS *command body*. The same five pillars govern detect-track-decide-act loops at the edge; SLSA Build **L1+L2** attested (run 26896047715, cosign-verified), L3 not claimed.

The mesh's five systems map onto GPD: **HEART** (the Λ conjunctive critique gate emitting the Λ-signed receipt) = P3⊕P2; **CIRCULATORY/BLOOD** (append-only SHA-256 receipt bus) = P2; **BRAIN** (read-only reasoning cortex) = P1; **NERVOUS** (OTel/VSP telemetry) = the observation plane of P2/P5; **SKELETON** (service repos) = the attested artifacts of P2. Public-facing organ identities use **honest role names and Quechua organ names** (Provenance Anchor, Operator, Policy; YACHAY / YAWAR / YUYAY); no banned codename strings appear.

### 8.3 Why GPD is groundbreaking — the honest case

1. **A theory matched to post-determinism, not against it.** Prior governance assumes determinism and tries to recover it; GPD *accepts* non-determinism and governs it with checkable antecedents and attested records. To our knowledge, framing AI governance as "engineer the weakest checkable antecedent and attest it" — and backing each pillar with a kernel-checked boundary — is new.
2. **A unified structural pattern across independent domains.** That Λ-uniqueness (functional equations) and Khipu safety (distributed consensus) share the *same* epistemic shape — false-unconditional, true-conditional-on-the-weakest-checkable-property, with a machine-checked boundary — is the conceptual contribution of v25. Slice-multiplicativity and honest non-equivocation are revealed as the same kind of object.
3. **Axiom elimination as a first-class result.** Theorem U removes a *project axiom* from the trusted base entirely (`#print axioms = {propext, Classical.choice, Quot.sound}`); a governed-AI aggregator uniqueness whose trusted base is the bare Lean core is, as far as we can determine, new.
4. **Disclosed-axiom discipline at scale.** Applying a `#print axioms` ledger to *every* claim, with a hard wall between a **locked five** and a ~190-theorem experimental tier, across a governance aggregator, a BFT consensus, and a receipt/provenance layer, extends the seL4 machine-checked-systems tradition into AI governance.
5. **Two-plane attestation, realized.** P2's DSSE/cosign SLSA L1+L2 provenance is captured by the build control plane *outside* the agent's process — the top rung of the enforceability ladder for the artifact plane.

### 8.4 Honest comparison to prior art

| Prior art | What it provides | How GPD differs (honestly) |
|---|---|---|
| [Verifiable-claims governance (Brundage et al.)](https://arxiv.org/abs/2004.07213) | the argument that AI claims should be externally verifiable | a concrete kernel-checked substrate + a structural theory; does not claim to solve verifiability in general |
| [seL4](https://dl.acm.org/doi/10.1145/1629575.1629596) | machine-checked OS-kernel correctness (gold standard) | verifies a governance aggregator + consensus + receipt layer; far smaller scope/maturity; no seL4-level coverage claimed |
| [PBFT / HotStuff / Velisarios](https://arxiv.org/abs/1803.05069) | BFT safety & (Coq) formalization | reuses quorum intersection; supplies the Lean witness-extraction discharging the old `sorry`; conditional only |
| Quasi-arithmetic mean theory ([Aczél; HLP](https://en.wikipedia.org/wiki/Quasi-arithmetic_mean)) | uniqueness characterizations of the geometric mean | an *axiom-free* conditional uniqueness (slice-multiplicativity) + a machine-checked unconditional refutation |
| [SLSA framework](https://slsa.dev/spec/v1.0/levels) | a supply-chain integrity ladder | honestly attests L1+L2 where the attestation runs; L3 / FedRAMP / Iron Bank / CMMC = roadmap |
| [ARMO enforceability ladder](https://www.armosec.io/blog/ai-agent-governance/) | a 5-rung rubric for governance enforceability | instantiates the top rung on the artifact plane via attested provenance |

**Honest summary.** The individual facts (geometric-mean characterizations, Byzantine quorums, Reed–Solomon, hash-chains, SLSA) are classical. GPD's contribution is their *unification into one theory of governed post-determinism*, their kernel-checked instantiation in two governed bodies, the structural-pattern observation across independent domains, and the honesty architecture that guards every tempting overclaim with a machine-checked boundary.

---

## 9. Philosophical foundations: the checkable antecedent as an epistemic upgrade

A trusted base containing a *project axiom* asks the auditor to *believe* something the kernel cannot check. The v23→v24 transition replaced the declared A6′ axiom with the **checkable property** slice-multiplicativity; the Wave-23 BFT result rests on the **checkable property** honest non-equivocation. On any reliabilist account of justification, replacing a postulate the auditor must trust with a property the auditor can confirm is an **epistemic upgrade**: the warrant for the conclusion no longer routes through an unverifiable idealization.

A conditional is *legitimate* when (i) its antecedent is independently motivated (separability is the standard hypothesis for multiplicative aggregators; non-equivocation is the standard signed-vote assumption); (ii) it is non-vacuous (Λ *is* slice-multiplicative; honest organs *do* sign one vote); (iii) the boundary is established (without the antecedent, the universal claim fails — machine-checked); (iv) the cost is disclosed at point of use (the `#print axioms` ledger shows the bare core). GPD's two central conditionals meet all four.

**Steelman objections, with honest rebuttals.** *"A conditional is weaker than an unconditional."* True — but the unconditional statements are machine-checked **false** / **impossible**; the conditionals are the maximal true statements, and we say so. *"You still rely on `Classical.choice`."* Yes — Lean *core* axioms, disclosed in every ledger, identical to Mathlib's foundations; no *project* axiom is added. *"Slice-multiplicativity is just factorization renamed."* No — it is *weaker* than the old `Factors` premise and exposes the per-axis structure the proof consumes; factorization is *derived*, not assumed.

---

## 10. Empirical posture (measured, not proven) and limitations

### 10.1 Measured numbers

| Metric (reference deployment) | Value | Note |
|---|---|---|
| Median governed-loop latency | (measured) | end-to-end, single organ |
| Receipt append + root update | (measured) | per governed decision |
| `lake build` (full kernel check) | (measured) | CI-green at the pinned commit |
| Runtime CDN dependencies | **0** | by construction |
| Sim2Real Λ-axis transfer α-gap | ~0.10 mean (N=60, 5 regimes) | design benchmark, partial results; **not** a theorem |

These are operational characteristics, explicitly outside the "proven" tier.

### 10.2 Limitations and honesty (the brutal list)

- **Λ is Conjecture 1 unconditionally** — uniqueness under A1–A5 is machine-checked false; only conditional Theorem U is proven.
- **Khipu Byzantine safety is Conjecture 2** — open; Wave-23 proves only conditional agreement; liveness is Conjecture 3.
- **~190 experimental CI-green theorems** are a separate tier and **never** folded into the locked five.
- **307 open sorries** remain in the experimental tier; disclosed, never claimed proven.
- **Cryptographic security is axiom-gated** (declared collision-resistance idealizations, not hardness proofs).
- **DPO `klDivergence`/`pinsker` are false-as-stated** (no simplex hypothesis); CF-21 is a correct companion, not a repair.
- **Reed–Solomon CF-19** proves only the lower-distance half of Singleton.
- **SLSA L1+L2 attested** where the build-provenance attestation runs (killinchu, a11oy); else **L1 honest, L2 roadmap**. **L3 / FedRAMP / Iron Bank / CMMC = roadmap.**
- **Trust is never 100%.** No AGI claim. No fabricated metrics.

---

## 11. References (positioning prior art — distinct from GPD's SZL-only grounding)

**Trust aggregation / quasi-arithmetic means.**
1. J. Aczél. *On mean values.* Bull. AMS 54(4):392–400, 1948.
2. J. Aczél. *Lectures on Functional Equations and Their Applications.* Academic Press, 1966.
3. A. Kolmogorov; M. Nagumo; B. de Finetti (1930–31), via *Quasi-arithmetic mean.* https://en.wikipedia.org/wiki/Quasi-arithmetic_mean
4. G. H. Hardy, J. E. Littlewood, G. Pólya. *Inequalities.* Cambridge UP, 1934.
5. *On noncontinuous bisymmetric strictly monotone operations.* arXiv:2601.16247. https://arxiv.org/html/2601.16247v1
6. *N-ary quasi-arithmetic means and families without regularity.* arXiv:2606.05221. https://arxiv.org/html/2606.05221v1
7. *Bisymmetric partially strictly monotone reflexive symmetric ⇒ continuous.* arXiv:2107.07391. https://arxiv.org/pdf/2107.07391.pdf

**Byzantine fault tolerance.**
8. L. Lamport, R. Shostak, M. Pease. *The Byzantine Generals Problem.* ACM TOPLAS 4(3):382–401, 1982. https://doi.org/10.1145/357172.357176
9. M. Castro, B. Liskov. *Practical Byzantine Fault Tolerance.* OSDI 1999. https://css.csail.mit.edu/6.824/2014/papers/castro-practicalbft.pdf
10. M. Yin et al. *HotStuff: BFT Consensus with Linearity and Responsiveness.* arXiv:1803.05069. https://arxiv.org/abs/1803.05069
11. V. Rahli et al. *Velisarios: Byzantine Fault-Tolerant Protocols Powered by Coq.* ESOP 2018. https://vrahli.github.io/articles/velisarios.pdf
12. E. Buchman. *Tendermint: BFT in the Age of Blockchains.* MSc thesis, 2016. https://knowen-production.s3.amazonaws.com/uploads/attachment/file/1814/Buchman_Ethan_201606_Msater+thesis.pdf

**Supply-chain provenance & signing.**
13. SLSA v1.0 — Security levels. https://slsa.dev/spec/v1.0/levels · Requirements. https://slsa.dev/spec/v1.0/requirements
14. Sigstore — Verifying in-toto attestations with cosign. https://docs.sigstore.dev/cosign/verifying/attestation/
15. Sigstore keyless (Fulcio + Rekor). https://sbomify.com/2024/08/12/what-is-sigstore/

**Governed / agentic AI & formal verification.**
16. M. Brundage et al. *Toward Trustworthy AI Development: Mechanisms for Supporting Verifiable Claims.* arXiv:2004.07213. https://arxiv.org/abs/2004.07213
17. ARMO. *AI Agent Governance: the Enforceability Ladder.* https://www.armosec.io/blog/ai-agent-governance/
18. ISACA. *The Growing Challenge of Auditing Agentic AI.* https://www.isaca.org/resources/news-and-trends/industry-news/2025/the-growing-challenge-of-auditing-agentic-ai
19. G. Klein et al. *seL4: Formal Verification of an OS Kernel.* SOSP 2009. https://dl.acm.org/doi/10.1145/1629575.1629596
20. The mathlib Community. *The Lean Mathematical Library.* CPP 2020. · L. de Moura, S. Ullrich. *The Lean 4 Theorem Prover and Programming Language.* CADE 2021.

**SZL Holdings lineage (GPD's only grounding — see "Lineage and Prior Art").**
21. S. P. Lutar Jr. *The Ouroboros Thesis (v1–v24)* and *the Lean development.* SZL Holdings. Concept DOI [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926); repository [github.com/szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean). Component DOIs: [19867281](https://doi.org/10.5281/zenodo.19867281), [19934129](https://doi.org/10.5281/zenodo.19934129), [20020841](https://doi.org/10.5281/zenodo.20020841), [20020845](https://doi.org/10.5281/zenodo.20020845), [20020846](https://doi.org/10.5281/zenodo.20020846), [20174600](https://doi.org/10.5281/zenodo.20174600).

---

## Appendix A. Reproducibility and trusted computing base

### A.1 Pinned commits

| Component | Pin | Contents / status |
|---|---|---|
| Locked kernel | `c7c0ba17` | 749 / 14 / 163; locks {F1,F11,F12,F18,F19} |
| Experimental `main` (Waves 11–22) | `43bcabb7` | CUT-1 closed (Wave 22); CI-green |
| Theorem U (axiom-free Λ) | in `main` | `Round13` `lambda_unique_of_separable` |
| Khipu conditional safety | Wave 23 | `Lutar/Wave23/QuorumSafety.lean`, 5 decls axiom-clean |
| Concept DOI (always-latest) | — | [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926) |
| Repository | — | [github.com/szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean) |

### A.2 How to verify

```bash
# Locked kernel — the exactly-five locked formulas
git checkout c7c0ba17 && lake build           # green; locks F1,F11,F12,F18,F19

# Theorem U — axiom-free conditional Λ uniqueness
#print axioms Lutar.Round13.lambda_unique_of_separable
# => {propext, Classical.choice, Quot.sound}   (NO project axiom)

# Conjecture 1 refuted — unconditional uniqueness is FALSE
#print axioms Lutar.Round13.maxAgg_ne_Lambda    # Lean-core axioms only

# Khipu conditional safety (Wave 23)
#print axioms Lutar.Wave23.khipu_quorum_safety_conditional
# => {propext, Classical.choice, Quot.sound}

# Artifact provenance (SLSA L1+L2 where the attestation runs)
cosign verify-attestation --type slsaprovenance ghcr.io/szl-holdings/killinchu:uds-v0.2.0 \
  --certificate-identity-regexp='^https://github.com/szl-holdings/'
```

### A.3 Trusted computing base

The bottom turtles, stated once: (i) soundness of the Lean 4 kernel and its core axioms {`propext`, `Classical.choice`, `Quot.sound`}; (ii) the declared cryptographic idealizations (`sha256_collision_resistant` + Merkle collision-resistance / domain-separation), used only in the receipt-security theorems; (iii) human sign-off gating CI; (iv) for the artifact plane, the Sigstore roots (Fulcio CA + Rekor log) and the hosted GitHub Actions build platform. **Theorem U** and **`khipu_quorum_safety_conditional`** depend on *none* of the cryptographic idealizations and on *no* project axiom — only on (i).

---

## Appendix B. Notation and glossary

| Symbol / term | Meaning |
|---|---|
| **GPD** | Governed Post-Determinism — SZL's unified framework (this thesis) |
| **P1–P5** | the five GPD pillars (§1.1) |
| Λ_k(x) | Lutar invariant: equal-weight geometric mean `(∏ x_i)^{1/k}` on `[0,1]^k` (mesh formula F23) |
| A1–A5 | monotonicity, positive homogeneity, idempotence, boundedness, permutation-invariance |
| slice-multiplicativity | the checkable antecedent of Theorem U: `Φ = ∏ f_i(x_i)`, each `f_i` multiplicative/normalized/monotone |
| **Theorem U** | `lambda_unique_of_separable` — axiom-free conditional Λ uniqueness |
| **Conjecture 1** | unconditional Λ uniqueness — machine-checked FALSE; never a theorem |
| **Conjecture 2** | unconditional Khipu Byzantine safety — OPEN |
| **Conjecture 3** | Khipu liveness — untouched |
| HonestNonEquivocation | the checkable antecedent of Theorem 5.1: each honest organ signs one vote per action |
| F1/F11/F12/F18/F19 | the exactly-five locked formulas at `c7c0ba17` |
| `#print axioms` | Lean command listing a theorem's trusted axiom base |
| DSSE | Dead-Simple Signing Envelope (in-toto attestation envelope) |
| SLSA | Supply-chain Levels for Software Artifacts (build track L1–L3) |
| locked-five | the exactly five kernel-verified formulas; the experimental tier is never folded in |

---

*Doctrine footer:* Λ = **Conjecture 1** (machine-checked FALSE; never a theorem) · conditional Λ = **Theorem U**, axiom-free · Khipu BFT safety = **Conjecture 2** (Wave-23 conditional agreement only) · locked-proven = **exactly 5** {F1,F11,F12,F18,F19} @ `c7c0ba17` (749/14/163) · ~190 experimental CI-green (Waves 11–23, separate tier) · **SLSA L1+L2 attested** (killinchu, a11oy) / L1 honest+L2 roadmap elsewhere · **L3 roadmap** · trust never 100% · 0 runtime CDN · no AGI.

*Signed-off-by: Yachay <yachay@szlholdings.ai>*
*Co-Authored-By: SZL Unified Thesis Collective · Perplexity Computer Agent <agent@perplexity.ai>*
