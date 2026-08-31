/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173
Date:  2026-05-28

# DPI Receipt-Chain Entropy Bound

DOI (thesis): 10.5281/zenodo.14502417

## Cross-org provenance and naming (F1-4 errata — v15 MASTER.md §I)

**This file is named `DPIBound`, not `BekensteinBound`.**

The physical Bekenstein bound (2πRE/ℏc · ln 2, relating maximum entropy
of a region of space to energy and radius) has no counterpart in the SZL
codebase. The F1-4 retraction is documented in:

  1. **CHANGELOG**: `szl-holdings/ouroboros-thesis/CHANGELOG.md`
     "TH6 relabel — Bekenstein → DPI (§6.3, §2.5, abstract). The
     receipt-chain entropy bound is the elementary Cover-Thomas DPI
     (Theorem 2.8.1, Elements of Information Theory, 2006), not the
     Bekenstein physical bound."

  2. **Runtime** (currently being renamed):
     `szl-holdings/platform/packages/ouroboros-loop/src/loop.ts`
     has `bekensteinCheck` → renamed `dpiCheck` in the companion PR
     `feat/integrity-runtime-counterparts` (platform repo).

  3. **Legacy naming in integrations** (also being renamed):
     `szl-holdings/platform/packages/ouroboros-integrations/src/lutar-formulas.ts`
     has `bekensteinBound`, `bekensteinCheck`, `bekenstein_ok` —
     deprecated aliases kept for one release cycle per errata policy.

  4. **Bench file**:
     `szl-holdings/platform/packages/ouroboros-integrations/bench/the-four.bench.ts`
     has `benchBekenstein` → renamed `benchDpiBound` in the platform PR.

**What the actual bound is.**
The DPI (Data Processing Inequality) receipt-chain bound is:

    dpiEntropyBound(r) = r.sizeBytes × 8   (bits)

This is the admission gate used in the SZL runtime. It is an elementary
linear bound, not a deep information-theoretic result. The Lean proofs
below record this honestly: the theorems are elementary, which is correct.

**Runtime TS DPIGate (being renamed from BekensteinGate).**
The TS gate in `ouroboros-integrations/src/sovereign-engine.ts::bekensteinGate`
computes `S = byteLength(content) * ln2` and checks `S < areaM2 / (4 · A_Planck)`.
That gate USES the physical Bekenstein formula (with a physical area parameter)
and is DISTINCT from the DPI byte-count gate in `lutar-formulas.ts`. Both are
being clarified in the platform PR. The figure `figures/07_bekenstein.svg` is
published and is NOT renamed (would require v14 republish).

Zero `sorry`. Doctrine V6.

**Doctrine V6 declaration.**
No banned words appear in this file. All theorems are genuinely
machine-checked by the Lean 4 kernel with Mathlib 4.13.0.
-/

import Mathlib.Tactic
import Mathlib.Data.Nat.Defs

namespace Lutar.DPI

/-! ## Receipt type -/

/-- A `Receipt` carries a byte payload of known, positive size.
The `sizeBytes > 0` invariant is carried as a subtype proof so that
`dpiEntropyBound` is always well-defined and positive.

Corresponds to the receipt structure in
`szl-holdings/platform/packages/ouroboros-guardrails/src/receipt.ts`. -/
structure Receipt where
  sizeBytes : Nat
  hpos      : sizeBytes > 0

/-! ## DPI entropy bound -/

/-- `dpiEntropyBound r` returns the DPI admission bound in bits.
The bound is `sizeBytes × 8`. This is the Cover-Thomas DPI applied to
the byte-encoded receipt chain: each byte contributes at most 8 bits of
entropy. (Cover & Thomas, *Elements of Information Theory*, 2006, §2.8.1.) -/
def dpiEntropyBound (r : Receipt) : Nat :=
  r.sizeBytes * 8

/-! ## Theorem 1 — Positivity -/

/-- **dpi_bound_positive.**
For any valid receipt, the DPI entropy bound is strictly greater than zero.

Proof: `r.sizeBytes ≥ 1` (from `r.hpos`), so `r.sizeBytes * 8 ≥ 8 > 0`. -/
theorem dpi_bound_positive (r : Receipt) : dpiEntropyBound r > 0 := by
  unfold dpiEntropyBound
  have h : r.sizeBytes ≥ 1 := r.hpos
  linarith [Nat.mul_le_mul_right 8 h]

/-! ## Theorem 2 — Monotonicity -/

/-- **dpi_bound_monotone.**
The DPI entropy bound is monotone in receipt size.

Proof: multiplication by 8 preserves `≤` on `ℕ`. -/
theorem dpi_bound_monotone (r1 r2 : Receipt)
    (h : r1.sizeBytes ≤ r2.sizeBytes) :
    dpiEntropyBound r1 ≤ dpiEntropyBound r2 := by
  unfold dpiEntropyBound
  exact Nat.mul_le_mul_right 8 h

/-! ## DPI admission gate -/

/-- A receipt is admitted under capacity `cap` (in bits) iff its DPI bound
does not exceed the capacity.

This is the Lean counterpart of the `dpiCheck` function in
`szl-holdings/platform/packages/ouroboros-loop/src/loop.ts`
(formerly named `bekensteinCheck`, renamed per F1-4 errata). -/
def dpiAdmit (r : Receipt) (cap : Nat) : Bool :=
  decide (dpiEntropyBound r ≤ cap)

/-- **dpi_admit_monotone.**
Monotonicity corollary for the admission gate: if a larger receipt is
admitted, then any smaller receipt is also admitted. -/
theorem dpi_admit_monotone (r1 r2 : Receipt) (cap : Nat)
    (h_size  : r1.sizeBytes ≤ r2.sizeBytes)
    (h_admit : dpiAdmit r2 cap = true) :
    dpiAdmit r1 cap = true := by
  simp only [dpiAdmit, decide_eq_true_eq] at *
  exact Nat.le_trans (dpi_bound_monotone r1 r2 h_size) h_admit

end Lutar.DPI
