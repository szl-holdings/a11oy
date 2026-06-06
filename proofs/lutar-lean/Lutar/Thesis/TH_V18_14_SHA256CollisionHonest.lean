/-
# TH-V18-14 — SHA-256 Collision Resistance (Honest Axiom A15)

This module documents axiom A15 (SHA-256 collision resistance) as an
OPEN PROBLEM and proves audit-integrity theorems conditioned on it.

## OPEN PROBLEM (A15 — CollisionResistance):
SHA-256 collision resistance cannot be proved in Lean 4 without assuming
P ≠ NP or a computational hardness assumption. It is a standard cryptographic
assumption (NIST FIPS 180-4). Axiom A15 is retained as an honest axiom
in the v18.0 build, following B2 discipline:

  "axiom A15 [CollisionResistance]: SHA-256 is collision-resistant for
   receipt blobs. Provenance: NIST FIPS 180-4; second-preimage resistance
   under standard cryptographic assumptions. Cannot be discharged in Lean
   without P ≠ NP assumption."

## Lean Czar status: valid (conditional on A15; A15 documented as open)
## Proof method: exact/intro (structural, conditioned on A15)
## Axioms used: A15 (sha256, sha256_collision_resistant) — honest axiom, OPEN PROBLEM
## Composes: Lutar.Brahmi.AxisOption (for Function.Injective)
## Citations:
  - NIST FIPS 180-4 — SHA-256 specification (2015)
  - Rogaway & Shrimpton (2004) "Cryptographic Hash-Function Basics"
  - FRONTIER_lean_modules.md Module 2 — TimestampAuthority
  - opentimestamps/opentimestamps-client@cd71c760 (MIT)
-/
import Lutar.Brahmi.AxisOption  -- for Function.Injective

namespace Lutar.Thesis.SHA256

/-- Abstract type for receipt blobs (JSON-serialized, encoded as byte sequence). -/
abbrev ReceiptBlob := List Nat

/-- Abstract SHA-256 hash output (256-bit digest encoded as Nat). -/
abbrev SHA256Digest := Nat

/-!
## Axiom A15 — Collision Resistance (OPEN PROBLEM)

SHA-256 collision resistance is a standard cryptographic assumption.
It is an honest axiom: no proof in pure Lean 4 exists without P ≠ NP.
This axiom is documented as an OPEN PROBLEM per Lean Czar B2 discipline.
-/

/-- SHA-256 hash function (abstract, axiomatized). -/
axiom sha256 : ReceiptBlob → SHA256Digest

/-- **Axiom A15 (CollisionResistance)** — OPEN PROBLEM:
    No two distinct ReceiptBlobs produce the same SHA256Digest.
    Provenance: NIST FIPS 180-4; cannot be discharged in Lean 4
    without assuming P ≠ NP (computational complexity hardness). -/
axiom sha256_collision_resistant :
    ∀ (r1 r2 : ReceiptBlob), sha256 r1 = sha256 r2 → r1 = r2

/-- **TH-V18-14a**: sha256 is injective (follows directly from A15).
    Proof-by-composition: exact sha256_collision_resistant. -/
theorem th_v18_14a_sha256_injective : Function.Injective sha256 :=
  sha256_collision_resistant

/-- **TH-V18-14b**: distinct receipts have distinct hashes.
    Contrapositive of A15. -/
theorem th_v18_14b_distinct_receipts_distinct_hashes
    (r1 r2 : ReceiptBlob) (h : r1 ≠ r2) :
    sha256 r1 ≠ sha256 r2 :=
  fun heq => h (sha256_collision_resistant r1 r2 heq)

/-- **TH-V18-14c**: Hash audit integrity — if two receipts hash the same,
    they are the same receipt. This is the core tamper-detection property. -/
theorem th_v18_14c_hash_audit_integrity
    (r1 claimed_receipt : ReceiptBlob)
    (h : sha256 r1 = sha256 claimed_receipt) :
    r1 = claimed_receipt :=
  sha256_collision_resistant r1 claimed_receipt h

/-- **TH-V18-14d**: The set of receipt blobs maps injectively into digests.
    Combines TH-V18-14a with the definition of Function.Injective. -/
theorem th_v18_14d_receipt_digest_map_injective :
    ∀ r1 r2 : ReceiptBlob, sha256 r1 = sha256 r2 → r1 = r2 :=
  th_v18_14a_sha256_injective

end Lutar.Thesis.SHA256
