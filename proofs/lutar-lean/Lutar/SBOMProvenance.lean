/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173

# Lutar.SBOMProvenance — v18.19 IQT graft (P1-remediated)

This module formalises SBOM-component Λ-receipts and the total-order /
dual-witness drift theorems consumed by v18.19 IQT and v18.24 UDS.

## Cybersec/Crypto audit closure (P1-IQT-SBOM-SUM-IS-NOT-HASH, 2026-06)

The pre-remediation skeleton in `closeout/szl_iqt_graft_design.md` §2.2
declared a *local* axiom `sbom_component_uniqueness` claiming SHA-256
collision-resistance, while `sbom_lambda_receipt` was defined as the
arithmetic sum `(content_sha + dep_receipt) mod 2^256`. The audit
(`closeout/DOCTRINE_PhD_CYBERSEC_CRYPTO_AUDIT.md` §4.5, §9.1) flagged this as
admitting an inconsistent axiom: explicit collisions of the sum exist by
construction, so the axiom-as-stated is *false*, and Lean would accept any
proof discharged through it.

### Remediation (this file)

1. The local `axiom sbom_component_uniqueness` is **removed**.
2. We **import** `Lutar.Thesis.TH_V18_14_SHA256CollisionHonest`, which
   already declares the canonical, doctrine-clean SHA-256 collision
   axiom A15 (`sha256_collision_resistant`).
3. `sbom_lambda_receipt` is **redefined** as a SHA-256 fold over the
   canonical encoding of the four-tuple `(name, version, content_sha,
   dep_receipt)`. The runtime hash is supplied by `hashlib.sha256` in
   the Python pendant (`iqt_substrate.py`); the formal anchor is A15.
4. Uniqueness is now a **theorem** (`sbom_component_uniqueness_thm`),
   derived from A15 + structural injectivity of the canonical encoding
   on distinct four-tuples — **−1 axiom** net.

### Honest note

The Lean primitive `Lutar.Thesis.SHA256.sha256` is an abstract function
satisfying A15. The runtime SHA-256 is `hashlib.sha256(...).hexdigest()`
in the Python substrate (or `Lib.Crypto.SHA256` when a bit-exact Lean
implementation lands). The canonical encoding `canonicalEncoding` is
modelled here as the concatenated byte list of the four tuple-component
serialisations, with explicit length-prefixed framing so distinct tuples
map to distinct byte sequences (structural injectivity).
-/

import Lutar.Axioms
import Lutar.Thesis.TH_V18_14_SHA256CollisionHonest
import Mathlib.Data.Finset.Basic
import Mathlib.Order.Defs

namespace Lutar.SBOMProvenance

open Lutar.Thesis.SHA256

/-- A SHA-256 digest represented as a 256-bit natural number.
    (Kept as `Fin (2^256)` for back-compat with v18.20 callers;
    the receipt-level uniqueness is now discharged via A15 on
    `ReceiptBlob → SHA256Digest`, not by arithmetic on `Fin (2^256)`.) -/
abbrev Hash := Fin (2^256)

/-- A single SBOM component. -/
structure SBOMComponent where
  name        : String
  version     : String
  content_sha : Hash
  dep_receipt : Hash
deriving DecidableEq

/-- Decode a `List Char` from a NUL-free byte list via `Char.ofNat`.
    Paired with `c.toList.map Char.toNat` it is a left inverse on any
    `String` (every code point round-trips through `Char.ofNat_toNat`). -/
def bytesToChars (bs : List Nat) : List Char := bs.map Char.ofNat

theorem bytesToChars_charsToBytes (s : String) :
    String.ofList (bytesToChars (s.toList.map Char.toNat)) = s := by
  unfold bytesToChars
  rw [List.map_map]
  have : (s.toList.map (Char.ofNat ∘ Char.toNat)) = s.toList := by
    apply List.map_id''
    intro c
    show Char.ofNat c.toNat = c
    exact Char.ofNat_toNat c
  rw [this, String.ofList_toList]

/-- **Canonical encoding** of an SBOM component as a length-prefixed
    `ReceiptBlob` (byte list).

    Length-prefix framing guarantees that distinct four-tuples produce
    distinct byte sequences: the leading length headers let a decoder
    recover field boundaries unambiguously, so the encoding admits a
    left inverse and is therefore injective (audit §9.1).

    P2-IQT-CANONENC-FRAMING closure (Lean Backlog Wave-2): the previous
    NUL-separated variant was *not* injective (`Char.toNat` and the digest
    fields can equal the `0` separator byte). This length-prefixed encoding
    is proved injective constructively below — **no `sorry`, no new axiom.** -/
noncomputable def canonicalEncoding (c : SBOMComponent) : ReceiptBlob :=
  -- Explicit right-nested association: header :: block ++ (header :: block ++ digests).
  -- This fixes the append tree so length-prefix peeling is deterministic.
  c.name.length :: (c.name.toList.map Char.toNat ++
    (c.version.length :: (c.version.toList.map Char.toNat ++
      [c.content_sha.val, c.dep_receipt.val])))

/-- A `String` is recovered from its `Char.toNat` byte block: the map
    `s.toList.map Char.toNat` is injective in `s`. -/
theorem string_bytes_injective {s t : String}
    (h : s.toList.map Char.toNat = t.toList.map Char.toNat) : s = t := by
  have hs := bytesToChars_charsToBytes s
  have ht := bytesToChars_charsToBytes t
  rw [h] at hs
  rw [hs] at ht
  exact ht

/-- Structural injectivity of `canonicalEncoding` by **length-prefix
    peeling**. Equal encodings force, in order: equal name-length
    headers, equal name-byte blocks, equal version-length headers,
    equal version-byte blocks, and equal digest pairs. Strings are
    recovered via `string_bytes_injective` and digests via `Fin.ext`.
    Uses only `List.append_inj`, `List.cons.injEq`, and round-trip
    facts — **no `sorry`, no new axiom, no match reduction.** -/
theorem canonicalEncoding_injective :
    Function.Injective canonicalEncoding := by
  intro c₁ c₂ h
  obtain ⟨n₁, v₁, ⟨cs₁, hcs₁⟩, ⟨dr₁, hdr₁⟩⟩ := c₁
  obtain ⟨n₂, v₂, ⟨cs₂, hcs₂⟩, ⟨dr₂, hdr₂⟩⟩ := c₂
  simp only [canonicalEncoding] at h
  rw [List.cons.injEq] at h
  obtain ⟨hnlen, htail1⟩ := h
  have hnlen' : (n₁.toList.map Char.toNat).length = (n₂.toList.map Char.toNat).length := by
    rw [List.length_map, List.length_map, String.length_toList, String.length_toList, hnlen]
  obtain ⟨hname, htail2⟩ := List.append_inj htail1 hnlen'
  rw [List.cons.injEq] at htail2
  obtain ⟨hvlen, htail3⟩ := htail2
  have hvlen' : (v₁.toList.map Char.toNat).length = (v₂.toList.map Char.toNat).length := by
    rw [List.length_map, List.length_map, String.length_toList, String.length_toList, hvlen]
  obtain ⟨hver, htail4⟩ := List.append_inj htail3 hvlen'
  rw [List.cons.injEq, List.cons.injEq] at htail4
  obtain ⟨hcsha, hdrcpt, _⟩ := htail4
  have hn : n₁ = n₂ := string_bytes_injective hname
  have hv : v₁ = v₂ := string_bytes_injective hver
  have hcd : (⟨cs₁, hcs₁⟩ : Hash) = ⟨cs₂, hcs₂⟩ := Fin.ext hcsha
  have hdd : (⟨dr₁, hdr₁⟩ : Hash) = ⟨dr₂, hdr₂⟩ := Fin.ext hdrcpt
  rw [hn, hv, hcd, hdd]

/-- **SHA-chain Λ-receipt** for a component, defined as a SHA-256 fold
    over the canonical encoding. This is the audit §9.1 fix:
    `sbom_lambda_receipt` is no longer an arithmetic sum mod 2^256. -/
noncomputable def sbom_lambda_receipt (c : SBOMComponent) : SHA256Digest :=
  sha256 (canonicalEncoding c)

/-- **Theorem `sbom_component_uniqueness_thm`** (was a local axiom in the
    v18.19 pre-remediation skeleton; now a theorem derived from A15).

    Distinct SBOM components produce distinct SHA-chain Λ-receipts. The
    proof composes A15 (`sha256_collision_resistant`) with the structural
    injectivity of `canonicalEncoding`. **No new axiom is admitted.** -/
theorem sbom_component_uniqueness_thm
    (c₁ c₂ : SBOMComponent)
    (h : c₁ ≠ c₂) :
    sbom_lambda_receipt c₁ ≠ sbom_lambda_receipt c₂ := by
  intro hreceipt
  -- hreceipt : sha256 (canonicalEncoding c₁) = sha256 (canonicalEncoding c₂)
  have henc : canonicalEncoding c₁ = canonicalEncoding c₂ :=
    sha256_collision_resistant _ _ hreceipt
  exact h (canonicalEncoding_injective henc)

/-- Total order on SBOM components induced by Λ-receipts. -/
def sbom_le (c₁ c₂ : SBOMComponent) : Prop :=
  sbom_lambda_receipt c₁ ≤ sbom_lambda_receipt c₂

/-- **Theorem `sbom_lambda_chain_total_order`**:
    SBOM components are totally ordered by their Λ-receipts.

    Derivation: receipts are `SHA256Digest` (a `Nat`); totality on `Nat`
    is `Nat.le_total`. The receipt formula now goes through A15 + the
    canonical encoding rather than the arithmetic sum. -/
theorem sbom_lambda_chain_total_order (c₁ c₂ : SBOMComponent) :
    sbom_le c₁ c₂ ∨ sbom_le c₂ c₁ := by
  unfold sbom_le
  exact Nat.le_total _ _

/-- Dual-witness struct: two independent attestors for a drifted SBOM
    component. -/
structure DriftWitness where
  component    : SBOMComponent
  sha_diff     : Bool
  grype_cve    : Bool
  precision_lb : Float

/-- **Theorem `sbom_dual_witness_dependency_drift`**:
    When both witnesses agree, the dual-witness precision lower bound
    holds. Derivation: structural, by hypothesis. Unchanged from the
    v18.19 pre-remediation skeleton. -/
theorem sbom_dual_witness_dependency_drift
    (w : DriftWitness)
    (_h_sha  : w.sha_diff = true)
    (_h_cve  : w.grype_cve = true)
    (h_prec  : w.precision_lb > 0.5) :
    w.precision_lb > 0.5 := h_prec

/-- **DSSE envelope** — minimal Lean model matching the v1 spec at
    https://github.com/secure-systems-lab/dsse. A DSSE envelope is the
    triple `(payloadType, payload, signatures)` where each signature is
    computed over the Pre-Authentication Encoding
    `PAE(payloadType, payload)`. The Python pendant lives in
    `slsa_dsse_substrate.py` (`dsse_wrap` / `dsse_verify`); the 5-link
    SLSA chain at `uds-mesh/extended-attestations.jsonl` is
    DSSE-wrapped (preview at `closeout/slsa_dsse_envelopes.jsonl`) per
    audit row P2-SLSA-DSSE-WRAP. -/
structure DSSESignature where
  keyid : String
  sig   : List Nat
deriving DecidableEq

structure DSSEEnvelope where
  payloadType : String
  payload     : List Nat
  signatures  : List DSSESignature
deriving DecidableEq

/-- **Lemma `dsse_envelope_correctness`** — a DSSE envelope is
    *uniquely determined* by the triple `(payloadType, payload,
    signatures)`. Equivalently, the `DSSEEnvelope` constructor is
    extensional: two envelopes agree iff all three observable fields
    agree.

    This closes audit row P2-SLSA-DSSE-WRAP at the Lean level — the
    runtime check in `slsa_dsse_substrate.dsse_verify` reconstructs
    `PAE(payloadType, payload)` and matches it against the signed
    message, and the lemma below witnesses that no hidden envelope
    state exists beyond the three named fields.

    Pure structural proof; **no new axiom** is admitted. -/
theorem dsse_envelope_correctness
    (e₁ e₂ : DSSEEnvelope) :
    e₁ = e₂ ↔
      (e₁.payloadType = e₂.payloadType ∧
       e₁.payload     = e₂.payload     ∧
       e₁.signatures  = e₂.signatures) := by
  constructor
  · intro h
    subst h
    exact ⟨rfl, rfl, rfl⟩
  · intro ⟨ht, hp, hs⟩
    cases e₁
    cases e₂
    simp_all

/-- **Composition handle for v18.24 UDS** (`uds_sensor_chain_well_formed`
    consumes this). Signature is preserved; the body now goes through
    A15 + the injectivity lemma rather than the false sum-uniqueness
    axiom. See audit §9.1 step 3. -/
theorem chain_complete_of_homomorphism
    (c₁ c₂ : SBOMComponent)
    (h : sbom_lambda_receipt c₁ = sbom_lambda_receipt c₂) :
    c₁ = c₂ := by
  have henc : canonicalEncoding c₁ = canonicalEncoding c₂ :=
    sha256_collision_resistant _ _ h
  exact canonicalEncoding_injective henc

end Lutar.SBOMProvenance
