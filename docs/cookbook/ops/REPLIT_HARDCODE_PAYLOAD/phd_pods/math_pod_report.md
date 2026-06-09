# PhD Math Pod — Formal Verification Review Report
## `szl-holdings/lutar-lean` · Branch `feat/th8/lean-v2-close-7-sorries` · PR #18

**Reviewer grade:** PhD-level Mathematical Logic + Formal Verification  
**Doctrine:** V6 — strict, evidence-only, no hallucinations  
**Review date:** 2026-05-16  
**Branch examined:** `feat/th8/lean-v2-close-7-sorries` (commit `08cf857`)  
**Lean / Mathlib:** `leanprover/lean4:v4.13.0` / Mathlib `v4.13.0`

---

## 1. Sorry / Axiom Census

### 1.1 Actual `sorry` in proof positions (kernel-level blockers)

| # | File | Line | Theorem | Notes |
|---|---|---|---|---|
| S-K1 | `Lutar/Uniqueness.lean` | 36 | `lutar_unique` | Core headline theorem — sorry in proof body |
| S-K2 | `Lutar/Uniqueness.lean` | 42 | `lutar_is_geomean` | Corollary — sorry in proof body |
| S-K3 | `Lutar/Bound.lean` | 25 | `Λ_le_max` | Upper bound — sorry in proof body |
| S-K4 | `Lutar/Bound.lean` | 30 | `min_le_Λ` | Lower bound — sorry in proof body |

**Total sorry in kernel-compiled library: 4**

These four sorries are in the `Lutar/` directory and ARE compiled by `lake build` / `lake exe check`. The CI grep script (`lean.yml`) counts them; CI currently reports **4 remaining sorries** in `Lutar/*.lean`. The thesis claims "sorry-count = 0" — **this claim is false for the current state of the repository.**

### 1.2 `sorry` in TH8 proof files (NOT kernel-compiled)

The `TH8/lean_v2/` directory is **not declared** in `lakefile.lean` and is **not imported** by `Lutar.lean`. The lake build does not compile these files. Therefore, even if they were sorry-free, they provide zero kernel-level guarantee.

Within the TH8 files themselves, there are zero `sorry` keywords in proof positions. However, there is:

| # | File | Line | Item | Notes |
|---|---|---|---|---|
| T-S1 | `TH8/lean_v2/GLR.lean` | 200 | `noncomputable def Term.instantiate := fun body _ => body -- stub; sorry` | A definition stub that silently drops the argument; `body.instantiate arg` is defined as `body`, ignoring the substitution. This makes the beta-reduction rule `Reduce.beta` semantically incorrect. |

### 1.3 Non-Mathlib `axiom` declarations

| # | File | Lines | Axiom | Classification |
|---|---|---|---|---|
| A1 | `TH8/lean_v2/LinearReceipt.lean` | 63 | `axiom sha256 : List UInt8 → ReceiptHash` | Post-Lean-core cryptographic assumption — introduces an unverified constant |
| A2 | `TH8/lean_v2/LinearReceipt.lean` | 64 | `axiom sha256_inj : ∀ x y, sha256 x = sha256 y → x = y` | Cryptographic injectivity assumption — models SHA-256 as injective, which is an **unproven conjecture** (only computationally infeasible to violate, not mathematically injective) |

**Note on A2:** `sha256_inj` asserts mathematical injectivity of SHA-256. This conflates computational collision resistance with mathematical injectivity. In Lean's foundational sense, `sha256_inj` is an `axiom` that could be used to derive `False` if collisions exist (they cannot be ruled out formally). A reviewer would insist this be reframed as a hypothesis, not an axiom.

### 1.4 Tautological / vacuous axiom field

| # | File | Line | Item | Notes |
|---|---|---|---|---|
| T-A1 | `Lutar/Axioms.lean` | 42 | `weight_eq : (1 : ℚ) / (k : ℚ) = (1 : ℚ) / (k : ℚ)` | **Self-referential tautology** — states `1/k = 1/k`, which is true by `rfl`. This field purports to encode A3 (Egyptian-exact weights) but carries no content. It does not prove the actual constraint needed (that the weight vector sums to 1 and each weight equals `1/k`). |

### 1.5 Summary table

| Category | Count | Kernel-visible? |
|---|---|---|
| `sorry` in proof body (Lean library) | **4** | Yes |
| `sorry` in TH8 files (not in build) | **0** | No — not compiled |
| `stub` function silently corrupting semantics | **1** (`Term.instantiate`) | No — not compiled |
| New non-Mathlib `axiom` | **2** (`sha256`, `sha256_inj`) | No — not compiled |
| Tautological axiom field | **1** (`weight_eq`) | Yes (field exists; semantically vacuous) |

---

## 2. Theorem Catalog with Classification

**Classification key:**
- **(A)** Trivial / definitional — follows from `rfl`, `simp`, `trivial`, or direct constructor application
- **(B)** Constructive proof — genuine mathematical content, proof tactics beyond `rfl`/`simp`
- **(C)** Classical — uses `Classical.choice`, `Decidable.em`, or LEM
- **(D)** Depends on unproven axiom or sorry

### 2.1 Core `Lutar/` library (kernel-compiled)

| Theorem / def | File | Line(s) | Class | Notes |
|---|---|---|---|---|
| `Axes k` | `Lutar/Axioms.lean` | 22 | A | `abbrev` — definitional alias |
| `Aggregator k` | `Lutar/Axioms.lean` | 25 | A | `abbrev` — definitional alias |
| `IsMonotone` | `Lutar/Axioms.lean` | 28–29 | A | `def` — Prop-level definition |
| `IsHomogeneous` | `Lutar/Axioms.lean` | 33–34 | A | `def` — Prop-level definition |
| `IsEgyptianExact` | `Lutar/Axioms.lean` | 39–42 | A | `structure` — contains tautological `weight_eq` field |
| `IsBounded` | `Lutar/Axioms.lean` | 49–51 | A | `def` — Prop-level definition |
| `LutarAxioms` | `Lutar/Axioms.lean` | 55–59 | A | `structure` collecting A1..A4 |
| `unitWeight` | `Lutar/Egyptian.lean` | 20 | A | `def` — simple piecewise function |
| `unitWeight_sum_eq_one` | `Lutar/Egyptian.lean` | 23–28 | B | Full proof: `field_simp` closes after `simp`; genuine arithmetic |
| `unitWeight_unique` | `Lutar/Egyptian.lean` | 33–37 | B | Proof by `field_simp` + `exact_mod_cast`; correct arithmetic |
| `Λ` (Lutar Invariant def) | `Lutar/Invariant.lean` | 21–25 | A | `noncomputable def` — geometric mean via `Finset.prod` + `NNReal.rpow` |
| `Λ_def` | `Lutar/Invariant.lean` | 28–30 | A | Follows immediately from `simp [Λ, hk.ne']` |
| `lutar_unique` | `Lutar/Uniqueness.lean` | 31–36 | **D** | **sorry** in proof; headline theorem |
| `lutar_is_geomean` | `Lutar/Uniqueness.lean` | 39–42 | **D** | **sorry** in proof |
| `Λ_le_max` | `Lutar/Bound.lean` | 23–25 | **D** | **sorry** in proof |
| `min_le_Λ` | `Lutar/Bound.lean` | 28–30 | **D** | **sorry** in proof |

### 2.2 DoctrineV3 — `Lutar/DoctrineV3/` (kernel-compiled, imported by `Lutar.lean`)

| Theorem / def | File | Line(s) | Class | Notes |
|---|---|---|---|---|
| `HarmCategory` | `MoralGrounding.lean` | 59–72 | A | Inductive type — 6 constructors |
| `Fintype HarmCategory` instance | `MoralGrounding.lean` | 74–85 | B | Uses `cases h <;> simp`; legitimate exhaustive proof |
| `Output` | `MoralGrounding.lean` | 98–106 | A | `structure` — definitional |
| `violates` | `MoralGrounding.lean` | 110–111 | A | `def` — trivial unwrap |
| `P_moral` | `MoralGrounding.lean` | 115–116 | A | `def` — universal quantification |
| `MoralGroundingTheorem` | `MoralGrounding.lean` | 145–151 | B | Proof by `intro`, `simp [violates]`, hypothesis contradiction; genuine but trivial |
| `P_moral_iff_conjunction` | `MoralGrounding.lean` | 158–176 | B | Forward: direct application. Backward: `cases hc with` for all 6 constructors |
| `ReceiptSlot` | `MeasurabilityHonesty.lean` | 61–64 | A | Two-constructor inductive |
| `MeasurabilityHonestyTheorem` | `MeasurabilityHonesty.lean` | 89–93 | B | `cases r` with two cases; correct |
| `ReceiptSlot.verified_ne_markedUnverifiable` | `MeasurabilityHonesty.lean` | 99–103 | A | `ReceiptSlot.noConfusion` — trivially follows from `noConfusion` principle |

### 2.3 TH8 — `TH8/lean_v2/` (NOT kernel-compiled; module path `Lutar.GLR.*` cannot resolve)

| Theorem / def | File | Line(s) | Class | Notes |
|---|---|---|---|---|
| `GradeVec` structure | `GradedSemiring.lean` | 49–53 | A | Structure — definitional |
| `GradeVec.ext` | `GradedSemiring.lean` | 95–96 | B | `funext` — genuine extensionality |
| `GradeVec.add_comm` | `GradedSemiring.lean` | 100–101 | B | `simp [add, sup_comm]` — correct |
| `CommSemiring GradeVec` instance | `GradedSemiring.lean` | 139–153 | B | Full semiring proof via component-wise operations |
| `floorVec` | `GradedSemiring.lean` | 160–166 | A | `noncomputable def` — numeric literal values |
| `gatePass` | `GradedSemiring.lean` | 169 | A | `def` — component-wise ≤ |
| `gradeOneClosed_iff` | `GradedSemiring.lean` | 177–181 | B | Genuine iff proof |
| `mul_le_left`, `mul_le_right` | `GradedSemiring.lean` | 192–199 | B | `NNReal.mul_le_of_le_one_right/left` |
| `decEq_receipt_hash` | `LinearReceipt.lean` | 55–56 | C | Uses `Decidable.em` (classical LEM) — correctly labelled as tautology |
| `consumeEntry_decrements` | `LinearReceipt.lean` | 143–195 | B | Full list induction; plausible but has TODO_VERIFY flags on `simp` calls |
| `consumeEntry_none_iff` | `LinearReceipt.lean` | 201–241 | B | Full list induction; plausible; similar TODO_VERIFY flags |
| `consume_unavailable_means_no_receipt` | `LinearReceipt.lean` | 250–272 | B | Relies on S02; uses `omega` for arithmetic |
| `at_most_one_consume` | `LinearReceipt.lean` | 301–330 | **D** | **SKELETON**: requires extra hypothesis `hLinear : lookupCount ctx h = some 1` not derivable from stated premises alone |
| `TH8a` | `GLR.lean` | 259–280 | **D** | **SKELETON**: requires `hSD` (linear discipline soundness) as extra hypothesis; not a self-contained proof |
| `TH8b` | `GLR.lean` | 310–335 | **D** | **SKELETON**: ⇒ direction has `TODO_VERIFY` for `cases ht`; depends on unaxiomatized `hA12` |
| `TH8b_monad_identity` | `GLR.lean` | 340–344 | A | `Reduce.replay_derelict t` — trivial constructor application |
| `TH8c` | `GLR.lean` | 380–408 | B | Both directions proven; ⇐ by explicit construction; ⇒ by `cases hpass` |
| `TH8c_defn` | `GLR.lean` | 413–414 | A | `Iff.rfl` — definitional |
| `TH8_C1_composition_safety` | `GLR.lean` | 425–429 | A | **TRIVIAL RESTATEMENT** — conclusion equals hypothesis `hProd` |
| `TH8_C2_economic_grounding` | `GLR.lean` | 436–438 | A | **TRIVIAL RESTATEMENT** — conclusion equals hypothesis `hBudget` |
| `TH8_C3_entropy_monotonicity` | `GLR.lean` | 455–465 | **D** | `hA12 (replays i) (replays j)` — trivial given `hA12 : ∀ h₁ h₂, h₁ = h₂`. The hypothesis `hA12` asserts that **all receipt hashes are equal**, which is a catastrophically strong assumption (it would collapse the entire hash space to a singleton) |
| `TH8b_strong_monad_identity` | `StrongMonadIdentity.lean` | 122–126 | B | `simp` with monad laws; correct |
| `TH8b_right_unit` | `StrongMonadIdentity.lean` | 129–133 | **D** | Uses `List.join_singleton_iff.mpr` — **lemma name unverified in Mathlib 4.13**; may not exist |
| `replay5_all_eq` | `StrongMonadIdentity.lean` | 161–164 | B | `List.get_replicate` — plausible but Lean 4.13 name unverified |
| `TH8b_five_fold_replay` | `StrongMonadIdentity.lean` | 169–178 | **D** | Trivial given `hA12 : ∀ h₁ h₂, h₁ = h₂`; same pathological collapse as TH8_C3 |
| `TH8b_grade_one_unique` | `StrongMonadIdentity.lean` | 140–149 | A | `trivial` — vacuously proves `True`; not the claimed uniqueness |

---

## 3. Mathlib Version Pin Audit

| Item | Value | Assessment |
|---|---|---|
| `lean-toolchain` | `leanprover/lean4:v4.13.0` | **Pinned to a release tag** ✓ |
| Mathlib version in `lakefile.lean` | `"v4.13.0"` (tag reference via `git @ "v4.13.0"`) | **Pinned to a release tag** ✓ |
| Pin type | `git @ "v4.13.0"` — a tag, not a SHA | **Moderate risk**: tags are mutable (can be force-pushed). For reproducibility, a SHA pin is stronger. No lake-manifest.json committed to the repo (listed in `.gitignore`). |
| Floating deps | None beyond Mathlib | No floating deps ✓ |
| `lake-manifest.json` | **Excluded from git** (in `.gitignore`) | **Reproducibility gap**: without a committed manifest, `lake update` resolves Mathlib at build time. Different CI runs could theoretically resolve different Mathlib commits if the `v4.13.0` tag is not immutable. CI runs `lake update -R` at build time to generate the manifest. |
| Lean 4 pin | `v4.13.0` toolchain tag | Same tag-vs-SHA caveat applies |

**Verdict:** Version pinning is adequate for practical reproducibility but falls short of the cryptographic commitment required for formal reproducibility. A production formal proof repository should commit `lake-manifest.json` to the repo.

---

## 4. Λ Formalization Verdict

### 4.1 Is Λ defined on 9 axes as a structure or product type?

**No.** The Lean `Λ` is defined in `Lutar/Invariant.lean` as:

```lean
-- Lutar/Invariant.lean:21–25
noncomputable def Λ (k : ℕ) (x : Axes k) : NNReal :=
  if hk : k = 0 then 0
  else ((Finset.univ : Finset (Fin k)).prod x) ^ ((1 : ℝ) / (k : ℝ))
```

This is parameterized by `k` and works for **any** `k`. There is no special 9-axis structure, no product type with 9 named fields, no type `Λ9 : Fin 9 → NNReal`. The thesis's nine named axes (`cleanliness`, `horizon`, `resonance`, `frustum`, `gaussClosure`, `invariance`, `moralGrounding`, `ontologicalGrounding`, `measurabilityHonesty`) **do not appear anywhere in the Lean code** except as informal comments.

The `GradeVec` structure in `TH8/lean_v2/GradedSemiring.lean` provides a `Fin 9 → NNReal` representation with explicit per-axis thresholds, but (a) it is not in the kernel-compiled library and (b) the axis names are identified only by index in comments.

### 4.2 Is conjunctive MIN defined and proved monotone, idempotent?

**No.** The Lean codebase has:
- `IsMonotone` defined as a `def` (Prop, not proved for `Λ` specifically) — `Lutar/Axioms.lean:28`
- No theorem proving `Λ k` satisfies `IsMonotone` in a kernel-compiled file
- No `def` for a conjunctive MIN operation
- No idempotence proof

The thesis (§2 of doctrine_v3, `03_lambda.tex`) defines the PASS predicate as conjunctive AND/MIN (`⋀ αᵢ ≥ τᵢ`), but this predicate is **not formalized in Lean at all** in the kernel-compiled library. `GradeVec.gatePass` provides a component-wise `≤` test (effectively the conjunction), but it is in uncompiled TH8 code.

### 4.3 Is the threshold theorem proven?

**No.** The thesis claims:
> Λ ≥ 0.90 ⟺ all 9 axes ≥ 0.90

This theorem does not exist anywhere in the Lean codebase. The formalization in `lutar-lean` is a **geometric mean** (not a conjunctive AND gate). There is a fundamental semantic gap: the thesis uses Λ as both (a) a geometric mean aggregator (for uniqueness proofs) and (b) a conjunctive AND gate (for the pass/fail predicate). These are different functions. The Lean code formalizes only (a); the pass predicate (b) is an informal prose claim.

### 4.4 Do `moralGrounding` and `measurabilityHonesty` have separate ≥ 0.95 thresholds proven?

**Partially.** `floorVec` in `TH8/lean_v2/GradedSemiring.lean` (line 160–166) encodes:
- Axes indexed 1 and 2 at 0.95 (labeled "A2 moralGrounding" and "A3 measurabilityHonesty" in comments)
- All others at 0.90

However:
1. **Not in kernel-compiled library** — this is in `TH8/lean_v2/` which `lake build` does not process
2. **Axis labeling mismatch**: the thesis §2 (`02_axes.tex`) names axis 7 as `moralGrounding` and axis 9 as `measurabilityHonesty`. `GradedSemiring.lean` assigns indices 1 and 2 to these axes. These index assignments are inconsistent.
3. **No threshold theorem**: there is no theorem of the form `gatePass g ↔ (g.val 7 ≥ 0.95 ∧ g.val 9 ≥ 0.95 ∧ ∀ i ∉ {7,9}, g.val i ≥ 0.90)`.

The `MoralGroundingTheorem` and `MeasurabilityHonestyTheorem` in `Lutar/DoctrineV3/` prove structural decomposition properties (finitely-many harm categories, two-valued receipt slot), but these **do not mention the 0.95 threshold at all**. The probabilistic statement `A₇(o) ≥ 0.95 ⟹ P_moral(o)` is explicitly disclaimed as out of scope (both files, lines 28–39 / 20–30).

### 4.5 Λ Formalization Verdict Summary

| Claim | Lean Status |
|---|---|
| 9 named axes as typed structure | **NOT FORMALIZED** |
| Conjunctive MIN defined | **NOT FORMALIZED** |
| Conjunctive MIN monotone | **NOT FORMALIZED** |
| Conjunctive MIN idempotent | **NOT FORMALIZED** |
| Threshold theorem (Λ ≥ 0.90 ⟺ all axes ≥ 0.90) | **NOT FORMALIZED** |
| moralGrounding ≥ 0.95 threshold proven | **NOT FORMALIZED** (only in uncompiled TH8 code, with index mismatch) |
| measurabilityHonesty ≥ 0.95 threshold proven | **NOT FORMALIZED** (same issues) |
| Geometric mean Λ_k defined (k arbitrary) | ✅ Defined, `Lutar/Invariant.lean:21` |
| Geometric mean Λ_k satisfies A1 monotonicity | ❌ Stated only, sorry |
| Geometric mean Λ_k satisfies A4 bounded | ❌ Stated only, sorry |
| Geometric mean Λ_k unique under A1-A4 | ❌ Stated only, sorry |

---

## 5. PR #18 — Proof Quality Audit (Per-Sorry)

**Context:** PR #18 adds `TH8/lean_v2/` (a new directory) and `Lutar/DoctrineV3/` (two new files). No existing sorries in `Lutar/` are touched. The "7 sorries closed" refers to 7 of 9 planned sorry placeholders in the *newly added* TH8 files.

### PR diff summary

| File | Added lines | Status |
|---|---|---|
| `Lutar/DoctrineV3/MoralGrounding.lean` | 178 | New file — no sorry |
| `Lutar/DoctrineV3/MeasurabilityHonesty.lean` | 105 | New file — no sorry |
| `TH8/lean_v2/GLR.lean` | 467 | New file — no sorry in proof; has `Term.instantiate` stub |
| `TH8/lean_v2/GradedSemiring.lean` | 208 | New file — no sorry |
| `TH8/lean_v2/LinearReceipt.lean` | 347 | New file — no sorry |
| `TH8/lean_v2/StrongMonadIdentity.lean` | 196 | New file — no sorry |
| `TH8/lean_v2/CLOSE_REPORT.md` | 335 | Documentation only |
| `TH8/lean_v2/MATHLIB_DEPS.md` | 181 | Documentation only |

### Per-sorry audit

**S01 — `consumeEntry_decrements` (`LinearReceipt.lean`, ~line 143)**

*Claimed:* CLOSED_PROPOSED, confidence: high  
*Assessment:* **CLOSED_PROPOSED (not kernel-verified)**. The proof is a genuine list induction with by-cases on hash equality. It carries three `TODO_VERIFY` flags: the `simp [List.find?_cons]` call with `decide_true`/`decide_false` may fail in Lean 4.13.0 depending on whether `List.find?_cons` is a `simp` lemma in that exact Mathlib version. The overall proof structure is mathematically sound.  
*Proof quality:* **B — Constructive** (if `simp` calls compile); **not yet kernel-verified**.

**S02 — `consumeEntry_none_iff` (`LinearReceipt.lean`, ~line 201)**

*Claimed:* CLOSED_PROPOSED, confidence: high  
*Assessment:* **CLOSED_PROPOSED (not kernel-verified)**. Similar structure to S01. The `Option.elim` unfolding and the `rw [show ...]` at line 238 are non-trivial `simp`-based steps with TODO_VERIFY notes. Proof structure is correct; compilation uncertain.  
*Proof quality:* **B** (if compiles).

**S03 — `consume_unavailable_means_no_receipt` (`LinearReceipt.lean`, ~line 250)**

*Claimed:* CLOSED_PROPOSED, confidence: high  
*Assessment:* **CLOSED_PROPOSED (not kernel-verified)**. Uses `consumeEntry_none_iff` (S02) as a rewrite, then case-splits on `find?`. The final step `omega` closes `0 ≠ 1` — correct. Depends on S02 compiling.  
*Proof quality:* **B** (if S02 compiles).

**S04 — `at_most_one_consume` (`LinearReceipt.lean`, ~line 301)**

*Claimed:* SKELETON_WRITTEN, confidence: med  
*Assessment:* **NOT CLOSED — SKELETON WITH EXTRA HYPOTHESIS.** The theorem statement has been augmented with an additional hypothesis `hLinear : lookupCount ctx h = some 1` that is not derivable from the stated premises. This is the "context-formation invariant" which requires a `HasType` subject-reduction proof (estimated 1 day). The proof given is correct *given the extra hypothesis* but the hypothesis itself is unproven. This is a deliberate disclosure; the claim is honest but this is not a closed sorry.  
*Proof quality:* **D — depends on unproven hypothesis**.

**S05 — `TH8a` (capability revocation, `GLR.lean`, ~line 259)**

*Claimed:* CLOSED_PROPOSED, confidence: high  
*Assessment:* **NOT CLOSED — HYPOTHESIS-PADDED.** The theorem has been augmented with `hSD : ∀ r, HasType Γ' r (lReceipt g) g → ∀ b ∈ Γ', b.hash = h → b.count ≥ 1` as an extra hypothesis. This is the "linear discipline soundness" lemma that requires `HasType` induction to prove. Given `hSD` and `hConsumed`, the proof closes by `omega` (0 ≥ 1 is a contradiction). The `omega` step is correct. The extra hypothesis is explicitly labeled `TODO_VERIFY` and acknowledged as a gap. This is not a fully closed sorry; it has shifted the obligation to a different unproven lemma.  
*Proof quality:* **D — hypothesis-padded; linear discipline soundness unproven**.

**S06 — `TH8b` (deterministic replay biconditional, `GLR.lean`, ~line 310)**

*Claimed:* SKELETON_WRITTEN, confidence: med  
*Assessment:* **PARTIALLY CLOSED.**  
- ⇐ direction: `HasType.replay_rule Γ τ t n ht hCtx` — **direct constructor application, trivially correct** (A-class).  
- ⇒ direction: uses `cases ht with | replay_rule ...`. In Lean 4.13, `cases` on an inductive `HasType` should work if elaboration can distinguish term shapes. This has a `TODO_VERIFY` flag because: (a) `HasType` uses `Γ ++ Δ` in `app_rule`, and Lean 4's pattern matching on `HasType Γ (Term.replay t n) ...` requires all other constructors to fail syntactically due to the `Term.replay` shape — this is valid but depends on Lean not confusing it with a `Term.var`. The TODO is legitimate.  
- The `hA12` hypothesis (grade-1 scorer determinism) is a premise, not an axiom. This makes TH8b conditional on an unaxiomatized assumption.  
*Proof quality:* **D — ⇒ direction unverified; hA12 unaxiomatized**.

**S07 — `TH8c` core iff (gate-pass as linear-logic provability, `GLR.lean`, ~line 380)**

*Claimed:* CLOSED_PROPOSED (core iff), BLOCKED (full adjunction)  
*Assessment:* **CLOSED_PROPOSED (core iff).** Both directions have real proofs:  
- ⇒: `cases hpass with | pass_rule ...` — extracts `hFloor : gatePass g`. Similar `TODO_VERIFY` as TH8b ⇒.  
- ⇐: Explicitly constructs `([], Term.intro 0 g, intro_rule [] 0 g, pass_rule [] g ...)`. Clean construction.  
The "full adjunction" (GΛR ↔ ILL_{g_min}) is honestly disclosed as blocked, estimated 3–4 weeks.  
*Proof quality:* **B** (core iff directions, if `cases` fires) + **blocked** (full adjunction).

**S08 — `TH8_C3_entropy_monotonicity` (`GLR.lean`, ~line 455)**

*Claimed:* CLOSED_PROPOSED, confidence: high  
*Assessment:* **CLOSED BUT TRIVIALLY VACUOUS.** The proof is `exact hA12 (replays i) (replays j)`. This is mathematically correct given `hA12 : ∀ h₁ h₂ : ReceiptHash, h₁ = h₂`. However, `hA12` as stated asserts that **all receipt hashes are identical** — there is only one hash value in the universe. This collapses the entire receipt model: every receipt would be indistinguishable from every other. This hypothesis is not stated as an axiom `A12` but as a theorem parameter. A reviewer would classify this as a **trivial proof of a consequence of a contradiction** (since hash distinctness is essential to the receipt model). Entropy monotonicity does not require this strong assumption; the claim is grossly over-hypothesized.  
*Proof quality:* **A — trivial given hA12, but hA12 is pathological**.

### PR #18 Proof Quality Summary

| Sorry | Actual status | Proof mechanism | Kernel-verified? |
|---|---|---|---|
| S01 `consumeEntry_decrements` | Plausible proof written | List induction + simp | **No** (TH8 not in build) |
| S02 `consumeEntry_none_iff` | Plausible proof written | List induction + simp | **No** |
| S03 `consume_unavailable_means_no_receipt` | Plausible proof written | Relies on S02 + omega | **No** |
| S04 `at_most_one_consume` | Skeleton with extra hypothesis | Uses unproven hLinear | **No** |
| S05 `TH8a` | Skeleton with extra hypothesis | Uses unproven hSD | **No** |
| S06 `TH8b` | Partial (⇐ only real) | ⇒ unverified + unaxiomatized hA12 | **No** |
| S07 `TH8c` core | Plausible proof written | Cases inversion + construction | **No** |
| S08 `TH8_C3` | Trivial given pathological hA12 | 1-line application | **No** |
| DoctrineV3 theorems | Genuine structural proofs | `cases`, `simp`, `omega` | **Yes** ✓ |

**Critical finding:** None of the 7 TH8 "closed sorries" are kernel-verified. The TH8 files are not part of the `lake build` compilation target. The CI `sorry` count step (`grep -rn '\bsorry\b' Lutar/*.lean Main.lean`) **does not scan `TH8/`**, so these files are invisible to the build system's sorry counter.

---

## 6. Build Reproducibility

### 6.1 CI workflow analysis (`lean.yml`)

| Step | Implementation | Assessment |
|---|---|---|
| `lake build` | ✅ Present | Builds entire `Lutar` library |
| `lake exe check` | ✅ Present | Runs `Main.lean` which prints status |
| `lake exe lean4checker` | ❌ **Absent** | Not used; only `lake exe check` (a custom executable, not the formal checker) |
| `lean4checker` (separate tool) | ❌ **Absent** | The formal Lean 4 kernel checker is not invoked |
| Sorry count scan | Present but **incomplete** | Scans `Lutar/*.lean Main.lean` — misses `TH8/` entirely |
| Mathlib cache | ✅ `use-mathlib-cache: true` | Cache for `leanprover/lean-action@v1.4.0` |
| Nix/deterministic build | ❌ Absent | No Nix flake or reproducible build envelope |

### 6.2 `lake exe lean4checker` vs. `lake exe check`

The CI uses `lake exe check` which runs the custom `Main.lean` executable that simply prints messages. It does **not** invoke `lean4checker` (the separate tool for exhaustive axiom tracing). A Heather Macbeth–tier reviewer would insist on `lean4checker` to verify that no undesired axioms are smuggled in through `Classical`, `propext`, or `funext`.

### 6.3 `lake-manifest.json` excluded from git

The `.gitignore` includes `/.lake`, meaning `lake-manifest.json` is regenerated at build time. This means:
- `lake update -R` in CI resolves Mathlib at build time from the `v4.13.0` tag
- If the `v4.13.0` tag were updated (force-pushed), CI builds would silently change
- Fully reproducible builds require either committing `lake-manifest.json` or using a SHA pin

### 6.4 `lean-action` pin quality

The `lean-action` step uses `leanprover/lean-action@38fbc41a8c28c4cbaec22d7f7de508ec2e7c0dd9 # v1.4.0` — pinned to a SHA. This is good practice. The `actions/checkout` and `step-security/harden-runner` are also SHA-pinned. Supply chain hygiene is adequate.

---

## 7. Thesis Claim → Lean Theorem Mapping

### Major thesis claims with Lean status

| Thesis claim | Lean location | Status |
|---|---|---|
| **Theorem 1 (Λ Uniqueness, sorry-count = 0)** The weighted geometric mean is the unique function satisfying A1–A4. | `Lutar/Uniqueness.lean:31–36` (`lutar_unique`) | **UNMAPPED** — `sorry` in proof. Thesis claims sorry=0; false. |
| **Theorem 2 (Λ Bounds, sorry-count = 0)** `min_i ≤ Λ_k ≤ max_i` | `Lutar/Bound.lean:23–30` | **UNMAPPED** — two `sorry`s in proofs. |
| **Theorem (Λ Uniqueness — corollary)** Λ = weighted geometric mean | `Lutar/Uniqueness.lean:39–42` (`lutar_is_geomean`) | **UNMAPPED** — `sorry`. |
| **Egyptian exactness** `unitWeight_sum_eq_one` | `Lutar/Egyptian.lean:23–28` | ✅ **MAPPED** — genuine proof |
| **Unit weight uniqueness** `unitWeight_unique` | `Lutar/Egyptian.lean:33–37` | ✅ **MAPPED** — genuine proof |
| **Moral Grounding Theorem** (structural: P_moral decomposes into 6-fold conjunction) | `Lutar/DoctrineV3/MoralGrounding.lean:145–151` | ✅ **MAPPED** — kernel-compiled, sorry-free; but only structural core, not the A₇ ≥ 0.95 probabilistic claim |
| **Measurability Honesty** (structural: receipt slot is verified ∨ unverifiable) | `Lutar/DoctrineV3/MeasurabilityHonesty.lean:89–93` | ✅ **MAPPED** — kernel-compiled, sorry-free; but not the A₉ ≥ 0.95 probabilistic claim |
| **9-axis conjunctive pass predicate PASS(α) = ⋀ αᵢ ≥ τᵢ** | None in `Lutar/` | **UNMAPPED** — no formal definition in kernel-compiled code |
| **moralGrounding floor = 0.95** | `GradedSemiring.lean:163` (TH8, uncompiled) | **UNMAPPED** (in uncompiled code + index mismatch) |
| **measurabilityHonesty floor = 0.95** | `GradedSemiring.lean:164` (TH8, uncompiled) | **UNMAPPED** (same) |
| **TH8a (Capability Revocation)** No well-typed second pass | `TH8/lean_v2/GLR.lean:259` | **UNMAPPED** — uncompiled + hypothesis-padded |
| **TH8b (Deterministic Replay)** Grade-1 iff replayable | `TH8/lean_v2/GLR.lean:310` | **UNMAPPED** — uncompiled + partial proof |
| **TH8c (Λ-Floor as ILL)** Gate-pass ↔ ILL provability | `TH8/lean_v2/GLR.lean:380` | **UNMAPPED** (uncompiled); full adjunction **BLOCKED** |
| **TH4 (Λ-Category Composability)** Monoidal functor | `lutar-lean/Lutar/LaxFunctor.lean` | **UNMAPPED** — file does not exist |
| **TH5 (Chain Confluence)** Cofree comonad coalgebra | None | **UNMAPPED** — not in repo |
| **TH6 (Bekenstein via DPI)** Receipt-chain entropy bounded | None | **UNMAPPED** — not in repo |
| **TH7 (Curry-Howard)** Receipt types are proofs | None | **UNMAPPED** — not in repo |
| **T1 (Composability, TH1)** Doctrine-locked composition | None | **UNMAPPED** — not in repo |
| **Adversarial Robustness (A13)** Gate stable under ε=0.05 | None | **UNMAPPED** — not in repo |
| **Theorem 5 (ρ-Closure Composability)** | None | **UNMAPPED** — not in repo |

### Structural observations

The thesis freely mixes two different notions of Λ:
1. **Geometric mean** (what Lean formalizes): `Λ_k(x) = (∏ xᵢ)^{1/k}` — a real-valued score in [0,1]
2. **Conjunctive AND gate** (what the production system uses): `PASS(α) = ⋀ αᵢ ≥ τᵢ` — a Boolean threshold

These are different mathematical objects. The uniqueness theorem (Theorem 1) applies to the geometric mean. The pass predicate is a conjunctive AND. The Lean formalization of the geometric mean does not imply anything about the conjunctive AND gate. The thesis presents them as if the Lean proofs apply to both.

---

## 8. Reviewer-Tier Defects (Heather Macbeth Standard)

The following are defects a Lean community reviewer of Heather Macbeth's caliber would raise as blocking issues:

### BLOCK-1: Headline theorem is a sorry (Critical)
`lutar_unique` (`Lutar/Uniqueness.lean:36`) and `lutar_is_geomean` (line 42) are both `sorry`. The thesis claims "sorry-count = 0" in this file. This is false. A reviewer would reject any paper or PR that claims machine-verified uniqueness when the proof is a sorry.

### BLOCK-2: Bound theorems are sorries (Critical)
`Λ_le_max` and `min_le_Λ` (`Lutar/Bound.lean:25,30`) are both `sorry`. Theorem 2 ("Λ Bounds, sorry-count = 0") is false.

### BLOCK-3: TH8 files not in build (Critical)
The entire `TH8/lean_v2/` directory is not declared in `lakefile.lean` and is not imported by the library. No Lake target compiles these files. Any "sorry-free" status for TH8 is unverifiable by `lake build`. The CI `sorry` counter explicitly excludes this directory. PR #18 is advertising "7 sorries closed" for files that are not kernel-compiled.

### BLOCK-4: `Term.instantiate` stub corrupts beta semantics (Critical)
`noncomputable def Term.instantiate : Term → Term → Term := fun body _ => body` (`GLR.lean:200`) defines substitution as the identity function (ignores the argument to be substituted). This means the beta-reduction rule `Reduce.beta` does not actually model beta reduction — `(λx. body) arg` reduces to `body` with no substitution, making the entire GΛR calculus semantically unsound as an operational semantics. This is acknowledged as a "stub" but makes every reduction-based result vacuous or incorrect (archived red-team note).

### BLOCK-5: `sha256_inj` is a false mathematical axiom (Serious)
`axiom sha256_inj : ∀ x y, sha256 x = sha256 y → x = y` asserts mathematical injectivity of SHA-256. SHA-256 maps arbitrary-length inputs to 256-bit outputs; by pigeonhole, it is provably not injective. The intended claim is *computational collision resistance* (infeasibility of finding collisions), which is a computational complexity assumption, not a provable mathematical fact. Using this as a Lean `axiom` introduces an inconsistency relative to the mathematical reality of hash functions. A reviewer would require this be rephrased as a hypothesis `(hSHA256 : Injective sha256)` in each theorem that uses it, not a global `axiom`.

### BLOCK-6: `weight_eq` in `IsEgyptianExact` is a tautology (Serious)
`weight_eq : (1 : ℚ) / (k : ℚ) = (1 : ℚ) / (k : ℚ)` (`Axioms.lean:42`) states `1/k = 1/k`. This is provable by `rfl` and carries no mathematical content. The A3 axiom as implemented does not constrain the weight function at all. The actual Egyptian-exactness constraint needed for the uniqueness proof is that *the weights must equal 1/k* — this is not encoded. `Egyptian.lean` does prove `unitWeight_sum_eq_one` and `unitWeight_unique`, but these are not connected to `LutarAxioms.A3`.

### BLOCK-7: `TH8_C1` and `TH8_C2` are trivial self-implications (Moderate)
`TH8_C1_composition_safety` concludes `gatePass (g₁ * g₂)` with hypothesis `hProd : gatePass (g₁ * g₂)` and proof term `hProd`. `TH8_C2_economic_grounding` similarly. These are bare hypothesis restatements — `id`-type proofs. They appear as named theorems in the CLOSE_REPORT but are mathematically empty.

### BLOCK-8: `hA12` in TH8b/TH8_C3 is pathologically strong (Moderate)
The hypothesis `hA12 : ∀ (h₁ h₂ : ReceiptHash), h₁ = h₂` asserts all natural numbers are equal — since `ReceiptHash := Nat` and `Nat` is infinite, this is equivalent to adding `False` as a hypothesis (from which anything follows). Theorems proved from this hypothesis are trivially true and carry no content. The actual A12 axiom (constructiveTransparency) should state determinism of the scorer, not collapse of the hash space.

### BLOCK-9: `TH8b_grade_one_unique` proves `True` (Moderate)
`TH8b_grade_one_unique` (`StrongMonadIdentity.lean:140`) has proof `trivial` and conclusion `True`. The claimed theorem is "Grade 1 is the unique grade for which the monad unit is an isomorphism." What is proved is nothing. This should be flagged as a non-theorem masquerading as a theorem.

### BLOCK-10: Λ-as-Boolean-gate vs Λ-as-real-aggregator conflation (Conceptual)
The formal verification system at no point proves a theorem of the form "the conjunctive AND gate with thresholds τᵢ is the unique monotone Boolean threshold function satisfying some axioms." The uniqueness theorem applies to the geometric mean. The pass predicate is separately defined (in Doctrine V3 prose) but never formally proven to be uniquely determined by any axioms in Lean. This conflation is the most significant conceptual gap between the thesis claims and the formal content.

### BLOCK-11: `lean4checker` not invoked in CI (Minor but significant for publications)
For publication-grade formal verification, the CI should invoke `lean4checker` to trace all axioms used and confirm no undesired dependencies. Currently only `lake exe check` (the custom executable) is used.

---

## 9. Top Recommendations for Full Formal Closure

Listed in priority order:

### P1 (Critical — must close before any "sorry-count = 0" claim)
1. **Prove `Λ_le_max` and `min_le_Λ`** in `Lutar/Bound.lean`. The required Mathlib lemmas are `Finset.prod_le_pow_card` and `NNReal.rpow_le_rpow`. Estimated: 1–2 days.
2. **Prove `lutar_unique` and `lutar_is_geomean`** in `Lutar/Uniqueness.lean`. The proof requires: (a) showing homogeneity forces `Λ` on the unit cube; (b) using `unitWeight_unique` from `Egyptian.lean`; (c) applying monotonicity + boundedness to identify the geometric mean. Estimated: 2–4 weeks.

### P2 (Critical — for TH8 to be meaningful)
3. **Declare TH8 as a lake library** in `lakefile.lean`. Create `Lutar/GLR/` directory, move `TH8/lean_v2/*.lean` there (the import paths `Lutar.GLR.*` will then resolve). Add `lean_lib «LutarGLR»` to lakefile. Without this, no TH8 proof is kernel-verified.
4. **Fix `Term.instantiate`**: Implement actual de Bruijn substitution for `Term`. Until this is done, all theorems involving `Reduce.beta` are proved in a calculus where beta-reduction does not substitute.

### P3 (Architecture — for honest axiom accounting)
5. **Replace `axiom sha256_inj` with a hypothesis**: Change to `variable (sha256_inj : ∀ x y, sha256 x = sha256 y → x = y)` or use a typeclass. Add a note that this is modeled as injective for formalization purposes.
6. **Fix `weight_eq` in `IsEgyptianExact`**: Replace the tautological `1/k = 1/k` with the actual content: `weight_eq : ∀ i : Fin k, unitWeight k i = 1 / k` (importing from `Egyptian.lean`). This makes A3 encode the actual constraint.

### P4 (Lean hygiene)
7. **Prove or remove TH8b_grade_one_unique**: The current `trivial` proof of `True` should either be removed or replaced with a genuine uniqueness argument.
8. **Weaken `hA12`**: Replace `∀ h₁ h₂ : ReceiptHash, h₁ = h₂` with the intended determinism statement: for a fixed input, the scorer always produces the same hash. The current formulation is inconsistent with a nontrivial hash universe.
9. **Add `lean4checker` to CI**: Invoke `lean4checker Lutar` after `lake build` to trace axioms. Publish the axiom list.
10. **Commit `lake-manifest.json`**: Either commit it or pin Mathlib by SHA in `lakefile.lean` instead of by tag.

### P5 (Research completeness — the actual Λ formalization)
11. **Formalize the conjunctive AND gate**: Define `def Λ9_pass (x : Fin 9 → NNReal) : Prop := ...` with named axes, explicit thresholds, and prove it is distinct from the geometric mean. State and prove the relationship (if any) between the two.
12. **Connect `LutarAxioms.A3` to `Egyptian.lean`**: Make `IsEgyptianExact` a real proposition (not a tautological field) by importing and using `unitWeight_unique`.
13. **Add HasType discipline lemmas** (`HasType_uses_binding_count_ge_one`, `HasType_linear_count_one`) as standalone proved lemmas so TH8a and `at_most_one_consume` can remove their extra hypotheses.

---

## Appendix: File Inventory Summary

| File | In lake build? | Sorries | Axioms (non-Mathlib) |
|---|---|---|---|
| `Lutar/Axioms.lean` | ✅ | 0 | Tautological `weight_eq` field |
| `Lutar/Egyptian.lean` | ✅ | 0 | 0 |
| `Lutar/Invariant.lean` | ✅ | 0 | 0 |
| `Lutar/Uniqueness.lean` | ✅ | **2** | 0 |
| `Lutar/Bound.lean` | ✅ | **2** | 0 |
| `Lutar/DoctrineV3/MoralGrounding.lean` | ✅ | 0 | 0 |
| `Lutar/DoctrineV3/MeasurabilityHonesty.lean` | ✅ | 0 | 0 |
| `Main.lean` | ✅ (exe) | 0 | 0 |
| `MainRef.lean` / `RefVectors.lean` | ✅ (exe) | 0 | 0 |
| `TH8/lean_v2/GradedSemiring.lean` | ❌ | 0 | 0 |
| `TH8/lean_v2/LinearReceipt.lean` | ❌ | 0 | **2** (`sha256`, `sha256_inj`) |
| `TH8/lean_v2/GLR.lean` | ❌ | 0 | 1 stub def |
| `TH8/lean_v2/StrongMonadIdentity.lean` | ❌ | 0 | 0 |

**Effective kernel-verified sorry count: 4** (S-K1 through S-K4)  
**Thesis-claimed sorry count: 0** (INCORRECT)

---

*Report prepared by PhD Math Pod agent — Doctrine V6 · Read-only · No push to lutar-lean*
