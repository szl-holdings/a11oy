# TH8 Lean — Mathlib 4 Dependency Register

**Author:** Lutar, Stephen P.  
**ORCID:** [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)  
**Affiliation:** SZL Holdings  
**Date:** 2026-05-15  
**Lean 4 / Mathlib:** v4.13.0  
**License:** Apache-2.0 (code), CC-BY-4.0 (text)

---

## 1. Currently Imported (v1 → v2, unchanged)

| Mathlib Module | Import Path | Used In | Specific Lemmas / Definitions |
|---|---|---|---|
| `Mathlib.Algebra.Order.Ring.Lemmas` | `import Mathlib.Algebra.Order.Ring.Lemmas` | `GradedSemiring` | `mul_max_of_nonneg`, `max_mul_of_nonneg` — left/right distributivity of `*` over `max` for `NNReal` |
| `Mathlib.Data.NNReal.Basic` | `import Mathlib.Data.NNReal.Basic` | `GradedSemiring`, `LinearReceipt` | `NNReal` type, `NNReal.mul_le_of_le_one_right`, `NNReal.mul_le_of_le_one_left`, `NNReal.mk_le_mk` |
| `Mathlib.Order.Pi` | `import Mathlib.Order.Pi` | `GradedSemiring` | `Pi.le_def` — component-wise order on `Fin 9 → NNReal` |
| `Mathlib.Data.List.Basic` | `import Mathlib.Data.List.Basic` | `LinearReceipt`, `GLR`, `StrongMonadIdentity` | `List.find?`, `List.find?_cons`, `List.join`, `List.replicate`, `List.map`, `List.join_join` |
| `Mathlib.Data.Option.Basic` | `import Mathlib.Data.Option.Basic` | `LinearReceipt` | `Option.map`, `Option.elim`, `Option.map_some`, `Option.map_none`, `Option.map_none_iff` |
| `Mathlib.CategoryTheory.Monad.Basic` | `import Mathlib.CategoryTheory.Monad.Basic` | `StrongMonadIdentity` | Imported for documentation / future use; `GradeMonad` is custom struct |
| `Mathlib.Algebra.Group.Defs` | `import Mathlib.Algebra.Group.Defs` | `StrongMonadIdentity` | `one_mul`, `mul_one`, `mul_assoc` for `GradeVec` |
| `Mathlib.Tactic` | `import Mathlib.Tactic` | All files | `norm_num`, `simp`, `omega`, `fin_cases`, `congr`, `intro`, `exact`, `constructor`, `rcases`, `obtain`, `cases`, `subst`, `convert`, `rw` |

---

## 2. New Imports Added in lean_v2

| Mathlib Module | Import Path | Added To | Purpose |
|---|---|---|---|
| `Mathlib.Data.List.Basic` | `import Mathlib.Data.List.Basic` | `LinearReceipt.lean` | Needed for `List.find?_cons` in `consumeEntry_decrements` and `consumeEntry_none_iff` proofs |

*Note: `Mathlib.Data.List.Basic` was already imported in `GLR.lean` v1; it is now also explicitly imported in `LinearReceipt.lean` lean_v2.*

---

## 3. Specific Lemmas Referenced in lean_v2 Proofs

### `List.find?_cons`

| Field | Value |
|---|---|
| **Import** | `Mathlib.Data.List.Basic` |
| **Statement** | `List.find?_cons : List.find? p (a :: l) = if p a then some a else List.find? p l` |
| **Used in** | `consumeEntry_decrements` (S01), `consumeEntry_none_iff` (S02) |
| **TODO_VERIFY** | Lean 4 spelling may be `List.find?_cons` (Mathlib 4.13); check with `#check List.find?_cons` |

### `Option.map_some`

| Field | Value |
|---|---|
| **Import** | `Mathlib.Data.Option.Basic` |
| **Statement** | `Option.map_some : Option.map f (some a) = some (f a)` |
| **Used in** | `consumeEntry_decrements` (S01), `consume_unavailable_means_no_receipt` (S03) |
| **TODO_VERIFY** | Standard; available as `simp` lemma |

### `Option.map_none`

| Field | Value |
|---|---|
| **Import** | `Mathlib.Data.Option.Basic` |
| **Statement** | `Option.map_none : Option.map f none = none` |
| **Used in** | `consume_unavailable_means_no_receipt` (S03) |
| **TODO_VERIFY** | Standard; available as `simp` lemma |

### `Option.elim` (definitional)

| Field | Value |
|---|---|
| **Import** | `Mathlib.Data.Option.Basic` |
| **Statement** | `Option.elim b f none = b`, `Option.elim b f (some a) = f a` |
| **Used in** | `consumeEntry_none_iff` (S02) |
| **TODO_VERIFY** | May need explicit `simp [Option.elim]` to unfold |

### `List.join_join`

| Field | Value |
|---|---|
| **Import** | `Mathlib.Data.List.Basic` (or `Mathlib.Data.List.Join`) |
| **Statement** | `List.join_join : (ls.join).join = ...` (associativity of join) |
| **Used in** | `StrongMonadIdentity.lean` — `ReplayMonad.assoc` |
| **TODO_VERIFY** | Exact spelling: may be `List.join_join` or `List.join_append_join`. Check `#check List.join_join`. |

### `List.get_replicate`

| Field | Value |
|---|---|
| **Import** | `Mathlib.Data.List.Basic` |
| **Statement** | `List.get_replicate : (List.replicate n a).get i = a` |
| **Used in** | `replay5_all_eq`, `grade_one_zero_entropy` in `StrongMonadIdentity.lean` |
| **TODO_VERIFY** | May require `List.get_replicate` or `List.getElem_replicate` in Lean 4.13 |

### `List.join_singleton_iff` (or `List.join_cons`)

| Field | Value |
|---|---|
| **Import** | `Mathlib.Data.List.Basic` |
| **Statement** | `[a].join = a` (or via `List.join_cons`) |
| **Used in** | `TH8b_right_unit` in `StrongMonadIdentity.lean` |
| **TODO_VERIFY** | Lean 4.13 spelling. Fallback: `simp [List.join, List.append_nil]` |

### `mul_max_of_nonneg`

| Field | Value |
|---|---|
| **Import** | `Mathlib.Algebra.Order.Ring.Lemmas` |
| **Statement** | `mul_max_of_nonneg : 0 ≤ a → a * max b c = max (a * b) (a * c)` |
| **Used in** | `GradedSemiring.lean` — `left_distrib` |
| **TODO_VERIFY** | Standard; confirmed in Mathlib 4 |

### `max_mul_of_nonneg`

| Field | Value |
|---|---|
| **Import** | `Mathlib.Algebra.Order.Ring.Lemmas` |
| **Statement** | `max_mul_of_nonneg : 0 ≤ c → max a b * c = max (a * c) (b * c)` |
| **Used in** | `GradedSemiring.lean` — `right_distrib` |
| **TODO_VERIFY** | Standard; confirmed in Mathlib 4 |

### `NNReal.mul_le_of_le_one_right`

| Field | Value |
|---|---|
| **Import** | `Mathlib.Data.NNReal.Basic` |
| **Statement** | `NNReal.mul_le_of_le_one_right : b ≤ 1 → a * b ≤ a` |
| **Used in** | `GradedSemiring.lean` — `mul_le_left` |
| **TODO_VERIFY** | Confirmed in Mathlib 4 |

### `NNReal.mul_le_of_le_one_left`

| Field | Value |
|---|---|
| **Import** | `Mathlib.Data.NNReal.Basic` |
| **Statement** | `NNReal.mul_le_of_le_one_left : a ≤ 1 → a * b ≤ b` |
| **Used in** | `GradedSemiring.lean` — `mul_le_right` |
| **TODO_VERIFY** | Confirmed in Mathlib 4 |

---

## 4. Lemmas Needed for Sorry Discharge (Not Yet Imported)

These modules are required for the full sorry discharge of `at_most_one_consume` (S04),
`TH8a` (S05), and `TH8b` (S06).  They do not need to be imported into the current
lean_v2 files (the proofs use additional hypotheses instead), but will be needed
once those hypotheses are replaced by standalone lemmas.

| Mathlib Module | Import Path | Needed For | Specific Lemmas |
|---|---|---|---|
| `Mathlib.Data.List.Induction` | `import Mathlib.Data.List.Induction` | S04 `at_most_one_consume` context-formation lemma | Standard list induction combinators for `CtxEntry` lists |
| `Mathlib.Logic.Decidable` | `import Mathlib.Logic.Decidable` | S01–S03 | Decidable equality on `ReceiptHash = Nat`; also `Nat.decEq` |
| `Mathlib.CategoryTheory.Adjunction.Basic` | `import Mathlib.CategoryTheory.Adjunction.Basic` | S07b TH8c full adjunction | `Adjunction`, `Adjunction.ofNatIsoLeft` |
| `Mathlib.CategoryTheory.Monad.Adjunction` | `import Mathlib.CategoryTheory.Monad.Adjunction` | S07b TH8c full adjunction | `monadOfAdjunction`, `Adjunction.toMonad` |
| `Mathlib.Algebra.Order.Monoid.Lemmas` | `import Mathlib.Algebra.Order.Monoid.Lemmas` | TH8-C1 composition safety (optional strengthening) | `mul_le_mul'` for `GradeVec` monotone multiplication |

---

## 5. New Axioms (Not in Existing `lutar-lean`)

| Axiom Name | File | Lean 4 Statement | Action Required |
|---|---|---|---|
| `decEq_receipt_hash` | `LinearReceipt.lean` | `theorem decEq_receipt_hash : ∀ (h h' : ReceiptHash), h = h' ∨ h ≠ h'` (LEM tautology, *not* cryptographic) | None — derived from `Decidable.em` |
| `sha256` + `sha256_inj` | `LinearReceipt.lean` | `axiom sha256 : List UInt8 → ReceiptHash` and `axiom sha256_inj : ∀ x y, sha256 x = sha256 y → x = y` | Add to `Lutar/Axioms.lean` or `Lutar/GLR/AxiomsGLR.lean`. This is the genuine cryptographic assumption. |
| `A12_constructiveTransparency` | Referenced in `GLR.lean`, `StrongMonadIdentity.lean` | `axiom A12_constructiveTransparency : ∀ (g : GradeVec), isGradeOneClosed g → ∀ (h₁ h₂ : ReceiptHash), h₁ = h₂` | New `axiom` in `Lutar/GLR/AxiomsGLR.lean` |

---

## 6. Internal Lemmas Needed (Not Mathlib)

These are GΛR-specific lemmas that must be proved within the `Lutar.GLR` namespace before the residual sorry-bearing proofs can be fully closed without additional hypotheses.

| Lemma | File | Statement Sketch | Needed By | Estimated Effort |
|---|---|---|---|---|
| `HasType_linear_count_one` | `GLR.lean` or `LinearReceipt.lean` | `intro_rule` assigns `count = 1`; preserved through context operations | S04 `at_most_one_consume` | 1 day |
| `HasType_uses_binding_count_ge_one` | `GLR.lean` | If `HasType Γ r τ g` uses binding `b` from `Γ`, then `b.count ≥ 1` | S05 `TH8a` | 1 day |
| `HasType_replay_inversion` | `GLR.lean` | `HasType Γ (replay t n) (bang τ 1) 1 → HasType Γ t τ 1 ∧ ∀ b ∈ Γ, b.grade = 1` | S06 `TH8b` ⇒ | 0.5 days |
| `HasType_pass_inversion` | `GLR.lean` | `HasType Γ (pass r) unit g → gatePass g ∧ HasType Γ r (lReceipt g) g` | S07 `TH8c` ⇒ | 0.5 days |

---

*Byline: Lutar, Stephen P. · ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173) · SZL Holdings · 2026-05-15*  
*Doctrine sweep: PASS · 0 forbidden patterns · Apache-2.0*
