/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173

# Round 11 — Frontier F3: BLS aggregate-signature verification (amaru cortex)

amaru verifies a DSSE chain of `N` organ receipts (a11oy + sentra + amaru + killinchu …).
Verifying each signature separately costs `2N` pairings.  With BLS **aggregation** over a
common message (the chain root) the whole batch verifies with **two** pairings:
`e(σ, g₂) = e(H(m), Σ pkᵢ)`, where `σ = Σ σᵢ` and `σᵢ = [skᵢ] H(m)`.

This file formalises the **algebraic core** of BLS aggregation in an additive abstraction
of the pairing groups: the aggregate of the per-organ signatures equals the signature
that the aggregate key would produce, so a single pairing check accepts the whole batch.
It underwrites the runtime `BLSAggregateVerifier` (`amaru/szl_bls_aggregate.py`).

## The correspondence (the frontier formalism)

| BLS aggregation (Boneh–Lynch–Shacham; BDN'18) | amaru DSSE chain verification                 |
|-----------------------------------------------|-----------------------------------------------|
| group `G₁` (signatures) — modelled additively | abstract additive group `S`                   |
| hashed message `H(m) ∈ G₁`                    | the chain-root hash point `h`                 |
| secret keys `skᵢ`, signature `σᵢ = skᵢ·h`     | each organ's signature                        |
| aggregate `σ = Σ σᵢ`                          | `BLSAggregateVerifier.aggregate`              |
| aggregate key `apk = Σ pkᵢ` (here `Σ skᵢ`)    | sum of organ public keys                      |
| accept iff `e(σ,g₂)=e(h, apk)` ⇔ `σ = sk·h`  | one pairing check accepts all `N` receipts    |

## Citations

* D. Boneh, B. Lynch, H. Shacham, "Short signatures from the Weil pairing", J.
  Cryptology 17(4):297–319 (2004).
* D. Boneh, M. Drijvers, G. Neven, "BLS Multi-Signatures With Public-Key Aggregation"
  (2018). https://crypto.stanford.edu/~dabo/pubs/papers/BLSmultisig
* Eth2 Book §2.9.1 (verify N aggregated signatures in 2 / N+1 pairings vs 2N).
  https://eth2book.info/latest/part2/building_blocks/signatures/
* Coordinates with runtime: `szl-holdings/amaru/szl_bls_aggregate.py`.

## What is proved (fully, no sorry)

* `agg_sig_eq_agg_key_sig` — the sum of per-organ signatures equals the signature the
  *summed* secret key would produce on the common message: `Σ (skᵢ · h) = (Σ skᵢ) · h`.
  This is precisely the identity that lets one pairing check `e(σ,g₂)=e(h,Σpkᵢ)` accept
  all `N` receipts at once (same-message aggregation).
* `aggregate_verify` — given that identity, the aggregate verification predicate
  (aggregate signature equals aggregate-key signature) holds, so the batch is accepted.
* `pairing_count_savings` — the bookkeeping inequality `2 ≤ 2 * N` for `N ≥ 1`: two
  pairings never exceed the `2N` of naïve per-signature verification.

We model the pairing groups additively over a commutative ring `R` acting on an additive
commutative group via scalar multiplication, capturing exactly the bilinear identity
used (`(a+b)·h = a·h + b·h`).  The pairing `e` is abstracted as injectivity of the check.

NEW file under `Lutar/Innovations/round11/`; locked kernel untouched.
-/
import Mathlib.Algebra.BigOperators.Basic
import Mathlib.Algebra.Module.Basic
import Mathlib.Tactic

namespace Lutar
namespace Round11
namespace BLS

open scoped BigOperators

/-- Abstract signature group: an additive commutative group `S` that is a module over the
scalar ring `R` of secret keys.  `skᵢ • h` is organ `i`'s signature on hashed message
`h : S`; `•` is the bilinear group action standing in for `[sk] H(m)` in `G₁`. -/
variable {R : Type} [CommRing R] {S : Type} [AddCommGroup S] [Module R S]

/-- The aggregate signature: the group-sum of each organ's signature on the common
hashed message `h`.  Mirrors `BLSAggregateVerifier.aggregate` (point addition in `G₁`). -/
def aggSig (sk : Fin n → R) (h : S) : S := ∑ i, (sk i • h)

/-- The aggregate key applied to the message: `(Σ skᵢ) • h`.  Mirrors verifying against
the summed public key `Σ pkᵢ`. -/
def aggKeySig (sk : Fin n → R) (h : S) : S := (∑ i, sk i) • h

/-- **Same-message aggregation identity.**  The sum of the per-organ signatures equals
the signature produced by the summed key on the common message.  This is the linear
(bilinear) core that lets a single pairing check accept the whole batch. -/
theorem agg_sig_eq_agg_key_sig {n : Nat} (sk : Fin n → R) (h : S) :
    aggSig sk h = aggKeySig sk h := by
  unfold aggSig aggKeySig
  rw [Finset.sum_smul]

/-- The aggregate **verification predicate** the runtime evaluates with one pairing:
the aggregate signature matches the aggregate-key signature on the chain root. -/
def aggregateVerify {n : Nat} (sk : Fin n → R) (h : S) (σ : S) : Prop :=
  σ = aggKeySig sk h

/-- **Aggregate verification accepts the honest batch.**  When `σ` is the true aggregate
of the organ signatures, the single aggregate check passes — so verifying `N` receipts
costs the *one* aggregate pairing check rather than `N` separate ones. -/
theorem aggregate_verify {n : Nat} (sk : Fin n → R) (h : S) :
    aggregateVerify sk h (aggSig sk h) := by
  unfold aggregateVerify
  exact agg_sig_eq_agg_key_sig sk h

/-- **Pairing-count savings.**  Same-message aggregation uses `2` pairings; naïve
per-signature verification uses `2N`.  For any non-empty chain (`N ≥ 1`) the aggregate
cost never exceeds the naïve cost (and is strictly less for `N ≥ 2`). -/
theorem pairing_count_savings (N : Nat) (hN : 1 ≤ N) : 2 ≤ 2 * N := by
  omega

/-- **Strict savings for multi-organ chains.**  For `N ≥ 2` organ receipts the aggregate
(`2` pairings) is strictly cheaper than naïve (`2N`).  A 4-organ chain: `2 < 8`. -/
theorem pairing_strict_savings (N : Nat) (hN : 2 ≤ N) : 2 < 2 * N := by
  omega

/-! ### Correspondence summary

`agg_sig_eq_agg_key_sig` is the bilinearity identity that makes BLS aggregation work:
`Σ (skᵢ·h) = (Σ skᵢ)·h`.  `aggregate_verify` shows the runtime's single aggregate check
accepts an honest `N`-organ DSSE chain, and `pairing_count_savings` /
`pairing_strict_savings` record that this replaces `2N` pairings with `2` (same message).
This is the throughput win for amaru's cortex when sustaining cross-organ chain
verification — pairings dominate cost; point additions are ~free.

Reference: Boneh–Lynch–Shacham (2004); Boneh–Drijvers–Neven (2018); Eth2 Book §2.9.1. -/

end BLS
end Round11
end Lutar
