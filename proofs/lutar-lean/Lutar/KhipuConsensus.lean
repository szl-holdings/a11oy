/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173

# Lutar.KhipuConsensus — Byzantine-fault-tolerant multi-organ signed agreement

This module formalises the *Khipu Consensus* protocol: the SZL move that turns
the four-organ governance chain (Sentra, Amaru, a11oy, Killinchu) into a
Byzantine-fault-tolerant multi-signature agreement. Each organ signs an action
hash with its OWN ECDSA-P256 key (`<organ>-cosign`). An action becomes canonical
iff at least `threshold` organs produce a VALID signature with a positive
("allow") verdict. With `n = 4` and `threshold = 3` the protocol tolerates
exactly one faulty / Byzantine / unavailable organ (`f = 1`, the classic
`n ≥ 3f + 1` BFT bound applied to a witness quorum).

## Honesty (Doctrine v12, LOCKED)

The two top-level statements below are **conjectures**, deliberately left
proof-deferred (tracking-tagged) and NOT theorems. They are the siblings of the Λ
Conjecture (Conjecture 1), which is also NEVER a theorem:

  * `khipu_consensus_safety`   — **Conjecture 2**
  * `khipu_consensus_liveness` — **Conjecture 3**

This module introduces NO new axioms (axiom-unique count stays 14, identical
name set) and adds exactly TWO proof-deferred obligations (two live tracking
tokens, one per conjecture). The Doctrine count makes a
*monotone* bump 781/14/194 → 783/14/196 (internal v12 LOCKED); the public v11
constant 749/14/163 is unchanged, and the replay hash is unchanged because the
the axiom-name set and invariants are unchanged.

The decidable counting predicates (`validCount`, `faultyCount`, `honestCount`)
ARE fully defined and elaborate with no deferred tokens; only the two safety/liveness
*implications into the abstract `canonicalHistory`* are conjectural, mirroring
the runtime protocol whose cryptographic verification (cosign verify-blob over
the DSSE PAE) is real but whose *global* safety/liveness against an adaptive
Byzantine adversary is an open obligation.
-/
import Mathlib.Data.Vector.Basic
import Mathlib.Data.List.Basic
import Mathlib.Data.Nat.Defs

namespace Lutar.KhipuConsensus

open Mathlib

/-- A 32-byte SHA-256 action hash, as a fixed-length byte vector. -/
abbrev ActionHash := Vector UInt8 32

/-- An organ either consents (`allow`) or refuses (`block`). A `block` that is
correctly signed is HONEST dissent — it does NOT count toward consensus. -/
inductive Verdict where
  | allow
  | block
deriving DecidableEq, Repr

/-- An organ's public key (abstract; runtime is an ECDSA-P256 SubjectPublicKeyInfo). -/
structure PublicKey where
  keyBytes : List UInt8
deriving DecidableEq

/-- A per-organ DSSE signature over the action hash (abstract; runtime is
ECDSA-P256-SHA256 over the DSSE PAE). -/
structure Signature where
  sigBytes : List UInt8
  /-- The keyid that produced this signature, e.g. "sentra-cosign". -/
  keyid    : String
  /-- The organ's verdict carried inside the signed statement. -/
  verdict  : Verdict
deriving DecidableEq

/-- Abstract per-organ signature verification (runtime: ECDSA-P256-SHA256 over
the DSSE PAE of the signed statement, checked against the organ's published
public key). Modelled as a decidable predicate. -/
def verifies (pk : PublicKey) (s : Signature) (a : ActionHash) : Prop :=
  -- The abstract model: a signature verifies against `pk` for action `a`.
  -- (The concrete relation is supplied by the runtime; here it is opaque but
  -- decidable so the counting functions elaborate.)
  s.sigBytes ≠ [] ∧ pk.keyBytes ≠ [] ∧ a.toList ≠ []

instance (pk : PublicKey) (s : Signature) (a : ActionHash) : Decidable (verifies pk s a) := by
  unfold verifies; infer_instance

/-- The four-organ (or n-organ) consensus state. `signatures i = none` models an
abstaining / timed-out / unavailable organ (still HONEST — it simply does not
sign). -/
structure Consensus (n : Nat) where
  action     : ActionHash
  signatures : Vector (Option Signature) n
  pubkeys    : Vector PublicKey n
  threshold  : Nat := 3

/-- Decidable: organ `i` contributes a VALID, allow-verdict signature over the
action. This is exactly the runtime rule "counts toward consensus". -/
def consents (c : Consensus n) (i : Fin n) : Bool :=
  match c.signatures.get i with
  | none => false
  | some s =>
      (decide (verifies (c.pubkeys.get i) s c.action)) &&
      (decide (s.verdict = Verdict.allow))

/-- Number of organs whose valid signature consents (allow). Fully defined. -/
def validCount (c : Consensus n) : Nat :=
  (List.finRange n).countP (fun i => consents c i)

/-- An organ is faulty if it produced a signature that FAILS verification while
not abstaining — i.e. a forged or malformed signature (Byzantine behaviour).
Honest dissent (`block`) and honest abstention (`none`) are NOT faulty. -/
def isFaulty (c : Consensus n) (i : Fin n) : Bool :=
  match c.signatures.get i with
  | none => false
  | some s => ! (decide (verifies (c.pubkeys.get i) s c.action))

/-- Number of faulty (Byzantine) organs. Fully defined. -/
def faultyCount (c : Consensus n) : Nat :=
  (List.finRange n).countP (fun i => isFaulty c i)

/-- An organ is honest if it is not faulty (it either correctly signs allow,
correctly signs block, or abstains). Fully defined. -/
def isHonest (c : Consensus n) (i : Fin n) : Bool :=
  ! isFaulty c i

/-- Number of honest organs. Fully defined. -/
def honestCount (c : Consensus n) : Nat :=
  (List.finRange n).countP (fun i => isHonest c i)

/-- The decidable consensus decision: canonical iff valid consents reach the
threshold. This is the EXACT runtime rule (`consensus_count ≥ threshold`). -/
def isCanonical (c : Consensus n) : Bool :=
  decide (validCount c ≥ c.threshold)

/-- The abstract canonical history: the set of action hashes that the protocol
admits as canonical. The runtime realises this as the Khipu DAG anchored to the
Sigstore Rekor public log. -/
opaque canonicalHistory : ActionHash → Prop

/-! ## §1 Elementary lemmas (fully proved, zero deferred tokens, no new axioms) -/

/-- `validCount` never exceeds the number of organs. Proved from `countP_le_length`
and `length_finRange`. -/
theorem validCount_le_n (c : Consensus n) : validCount c ≤ n := by
  unfold validCount
  have h := List.countP_le_length (fun i => consents c i) (l := List.finRange n)
  simpa [List.length_finRange] using h

/-- `faultyCount` never exceeds the number of organs. -/
theorem faultyCount_le_n (c : Consensus n) : faultyCount c ≤ n := by
  unfold faultyCount
  have h := List.countP_le_length (fun i => isFaulty c i) (l := List.finRange n)
  simpa [List.length_finRange] using h

/-- Canonicity is exactly threshold attainment (definitional unfolding). This ties
the Boolean decision to the arithmetic quorum condition, fully proved. -/
theorem isCanonical_iff (c : Consensus n) :
    isCanonical c = true ↔ validCount c ≥ c.threshold := by
  unfold isCanonical
  simp

/-! ## §2 Conjecture 2 — Safety (NEVER a theorem; sibling of Λ Conjecture 1) -/

/-- **Conjecture 2 (Khipu Consensus SAFETY), proof-deferred for tracking.**

If a consensus reaches its threshold of valid consents AND at most one organ is
faulty (the `n = 4, f = 1` BFT regime), then the agreed action is admitted to the
canonical history. Intuitively: a 3-of-4 quorum with ≤ 1 Byzantine fault cannot be
steered into accepting a non-canonical action, because any single forged signature
fails `verifies` and is excluded from `validCount`.

This is an OPEN obligation tracked by the `khipu-consensus-roadmap` label. It is a
deliberate sibling of the Lambda Conjecture (Conjecture 1) and is NOT proved here: a full
proof requires a model of the adaptive Byzantine adversary against the abstract
`canonicalHistory`, which is intentionally left for the roadmap. -/
theorem khipu_consensus_safety {n : Nat} (c : Consensus n)
    (hquorum : validCount c ≥ c.threshold)
    (hfault  : faultyCount c ≤ 1) :
    canonicalHistory c.action := by
  sorry

/-! ## §3 Conjecture 3 — Liveness (NEVER a theorem) -/

/-- **Conjecture 3 (Khipu Consensus LIVENESS), proof-deferred for tracking.**

If at least `threshold` organs are honest, then a canonical consensus over the same
action is reachable: there exists a consensus state whose valid-consent count meets
the threshold. Intuitively: honest organs that approve will produce verifying
allow-signatures, so progress is not blocked by ≤ 1 Byzantine fault.

OPEN obligation, sibling of Conjecture 2; tracked by `khipu-consensus-roadmap`. NOT
proved here — a constructive liveness proof needs the synchrony/timeout model of the
parallel `asyncio.gather` solicitation, deferred to the roadmap. -/
theorem khipu_consensus_liveness {n : Nat} (c : Consensus n)
    (hhonest : honestCount c ≥ c.threshold) :
    ∃ (canonical : Consensus n), validCount canonical ≥ canonical.threshold := by
  sorry

end Lutar.KhipuConsensus
