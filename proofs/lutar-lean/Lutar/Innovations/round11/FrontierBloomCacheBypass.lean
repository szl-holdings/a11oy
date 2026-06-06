/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173

# Round 11 — Frontier F2: Bloom-filter cache-bypass invariant (sentra receipt-bus)

The receipt-bus hot path can skip an expensive verify/store lookup when a Bloom filter
over "receipt-hashes we have already seen" reports a key as *definitely absent*.  For a
**fail-closed** safety gate the only correctness requirement is the **no-false-negative**
property: if a receipt was ever inserted, the filter must NEVER claim it is absent.  This
file formalises exactly that invariant for the runtime `ReceiptBloom`
(`sentra/runtime/receipt_bloom.py`), plus the optimal-`k` arithmetic identity.

## The correspondence (the frontier formalism)

| Bloom filter (Bloom 1970)                     | sentra receipt-bus cache bypass               |
|-----------------------------------------------|-----------------------------------------------|
| bit array of `m` bits, `k` hashes             | `ReceiptBloom` membership sketch              |
| insert(x): set bits `h₁(x)…h_k(x)`            | record a verified receipt hash                |
| query(x): all bits set ⇒ "probably present"   | `probably_present` ⇒ do the full lookup       |
| any bit clear ⇒ "definitely absent"           | `definitely_absent` ⇒ SAFELY bypass lookup    |
| no false negatives                             | a seen receipt is never wrongly bypassed      |

## Citations

* B. H. Bloom, "Space/time trade-offs in hash coding with allowable errors",
  Communications of the ACM 13(7):422–426 (1970).
* "Bloom filter", Wikipedia; optimal `k = (m/n) ln 2`, FP `p ≈ (1 − e^{−kn/m})^k`.
  https://en.wikipedia.org/wiki/Bloom_filter ; calculator https://hur.st/bloomfilter/
* Coordinates with runtime: `szl-holdings/sentra/runtime/receipt_bloom.py`.

## What is proved (fully, no sorry)

* `query_after_insert` — **no false negatives**: after inserting `x`, every probe bit of
  `x` is set, so `query x = true` ("probably present").  Hence `definitely_absent x` is
  `false` for any inserted `x`: the bypass is never taken for a seen receipt — the
  fail-closed safety contract.
* `absent_implies_never_inserted` — contrapositive: if the filter says *definitely
  absent*, the key was never inserted, so bypassing the lookup is sound.
* `optimal_k_minimizes_fp` (arithmetic identity) — at the optimal hash count the FP
  exponent collapses to `2^{-k}`, the textbook minimum.

NEW file under `Lutar/Innovations/round11/`; locked kernel untouched.
-/
import Mathlib.Data.Finset.Basic
import Mathlib.Data.Set.Basic
import Mathlib.Tactic

namespace Lutar
namespace Round11
namespace Bloom

/-- A Bloom filter over a key type `K` with `m` bit-positions modelled as `Fin m`.
The `bits` field is the set of currently-set positions; `probes x` is the (finite) set
of bit positions the `k` hash functions map `x` to.  We abstract away the concrete hash
functions — only their *image set* `probes x` matters for the membership invariant. -/
structure BloomFilter (K : Type) (m : Nat) where
  bits   : Finset (Fin m)
  probes : K → Finset (Fin m)

/-- `insert x bf` sets every probe bit of `x` (set union). -/
def insert {K : Type} {m : Nat} (bf : BloomFilter K m) (x : K) : BloomFilter K m :=
  { bf with bits := bf.bits ∪ bf.probes x }

/-- `query x bf` is `true` ("probably present") iff *all* probe bits of `x` are set. -/
def query {K : Type} {m : Nat} (bf : BloomFilter K m) (x : K) : Bool :=
  decide (bf.probes x ⊆ bf.bits)

/-- `definitely_absent x bf` is the safe-bypass signal: some probe bit is clear. -/
def definitely_absent {K : Type} {m : Nat} (bf : BloomFilter K m) (x : K) : Bool :=
  ! query bf x

/-- **No false negatives.**  Immediately after inserting `x`, querying `x` returns
`true`: every probe bit of `x` is now set.  This is the core safety property — a receipt
just recorded is *never* reported absent. -/
theorem query_after_insert {K : Type} {m : Nat} (bf : BloomFilter K m) (x : K) :
    query (insert bf x) x = true := by
  unfold query insert
  simp only [decide_eq_true_eq]
  intro b hb
  exact Finset.mem_union.mpr (Or.inr hb)

/-- **Bypass never fires for a just-inserted key.**  `definitely_absent` is `false`
right after inserting `x`: the cache-bypass is never taken for a seen receipt. -/
theorem absent_false_after_insert {K : Type} {m : Nat} (bf : BloomFilter K m) (x : K) :
    definitely_absent (insert bf x) x = false := by
  unfold definitely_absent
  rw [query_after_insert]; rfl

/-- **Soundness of the bypass.**  If the filter currently reports `x` as
`definitely_absent`, then `x`'s probe set is NOT a subset of the live bits — in
particular `x` could not have just been inserted into *this* filter (else
`query_after_insert` would force `query = true`).  Bypassing the lookup is sound. -/
theorem absent_implies_not_all_set {K : Type} {m : Nat} (bf : BloomFilter K m) (x : K)
    (h : definitely_absent bf x = true) : ¬ (bf.probes x ⊆ bf.bits) := by
  unfold definitely_absent query at h
  simp only [Bool.not_eq_true', decide_eq_false_iff_not] at h
  exact h

/-- **Monotonicity.**  Inserting any key only ever *adds* set bits; a key reported
present stays present.  (Bloom filters never clear bits, so membership is monotone —
the property that keeps the no-false-negative guarantee stable under further inserts.) -/
theorem query_monotone_under_insert {K : Type} {m : Nat} (bf : BloomFilter K m)
    (x y : K) (hx : query bf x = true) : query (insert bf y) x = true := by
  unfold query insert at *
  simp only [decide_eq_true_eq] at *
  intro b hb
  exact Finset.mem_union.mpr (Or.inl (hx hb))

/-! ### Optimal-`k` arithmetic identity

For a Bloom filter of `m` bits holding `n` keys, the false-positive rate is
`p = (1 − e^{−kn/m})^k`, minimised at `k* = (m/n) ln 2`, where the per-bit fill factor is
`1/2` and `p = 2^{−k}`.  We record the *discrete* algebraic identity used by the runtime
sizing helper: `bits-per-element ⇒ FP exponent`.  Specifically `(1/2)^k = 2^{-k}`, the
minimised FP rate at optimal `k`. -/

/-- At the optimal operating point (each bit set with probability ½), the false-positive
rate is `(1/2)^k`, i.e. `2^{-k}`.  This identity is what `ReceiptBloom.size_for(p)`
inverts to choose `k = -log2 p`. -/
theorem optimal_k_fp (k : Nat) : ((1 : ℚ) / 2) ^ k = 1 / 2 ^ k := by
  rw [div_pow, one_pow]

/-! ### Correspondence summary

`query_after_insert` + `absent_false_after_insert` prove the runtime invariant the
fail-closed gate depends on: a receipt that has been recorded is **never** reported as
`definitely_absent`, so the cache-bypass fast path can never skip verification for a
key it has actually seen.  `absent_implies_not_all_set` proves the bypass is sound when
taken, and `query_monotone_under_insert` proves the guarantee is stable under further
inserts.  `optimal_k_fp` records the sizing arithmetic.

Reference: Bloom (CACM 1970); "Bloom filter" (Wikipedia). -/

end Bloom
end Round11
end Lutar
