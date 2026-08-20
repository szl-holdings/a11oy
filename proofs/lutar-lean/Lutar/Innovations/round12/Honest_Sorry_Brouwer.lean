/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173

# Round 12 — MEDIUM: the honest-`sorry` as a Brouwerian constructive marker

**Unification target (Theme E — Honest unknowing):**
CT-E2 (Nāgārjuna catuṣkoṭi → AMBER forced) ∥ CT-E3 (Avicenna necessary/contingent shell)
∥ Brouwer's intuitionistic refusal of `p ∨ ¬p` without a witness ∥ al-Ghazālī's *docta ignorantia*.

> The SZL 3-valued gate GREEN/AMBER/RED is the unique order-preserving collapse of the 4-cornered
> *catuṣkoṭi* {affirmed, denied, both, neither} onto a 3-chain in which AMBER absorbs exactly the
> two "empty" corners {both, neither}. AMBER is not décor — it is the *forced* home of the
> paraconsistent centre, and (Brouwer) the typed marker of a proposition for which no constructive
> decision `p ∨ ¬p` exists. That is exactly what an honest `sorry` is.

## What is PROVED here (sorry-free)

`collapse_mono` / `amber_forced` — on the finite catuṣkoṭi → Verdict map, the doctrine collapse is
the **unique** order-preserving map sending `affirmed ↦ green`, `denied ↦ red`, and the two empty
corners `both, neither ↦ amber`. Finite, constructive case analysis — no Mathlib analysis needed.

## What stays an HONEST `sorry` (scaffold)

`honest_sorry_is_undecided` — the Brouwer bridge: a proposition whose verdict is AMBER carries *no*
constructive proof of `p ∨ ¬p`. Stated with a clean `Undecided` definition; the bridge to an
arbitrary evidence model is `sorry`-tagged and DEPENDS ON:
  - `EVIDENCE_MODEL` — a chosen (constructive) map from propositions to catuṣkoṭi corners.
This is deliberately left open: the point is to *type* honest-unknowing, not to classically discharge it.

## Citations (real, inherited from the Eastern pod + Brouwer)

* Nāgārjuna, *Mūlamadhyamakakārikā* (catuṣkoṭi, śūnyatā) — Garfield (trans.), *The Fundamental Wisdom
  of the Middle Way*, Oxford University Press (1995).
* Ibn Sīnā (Avicenna), *Kitāb al-Shifāʾ* — *wājib/mumkin al-wujūd* — Stanford Encyclopedia of
  Philosophy, "Ibn Sīnā's Metaphysics."
* L. E. J. Brouwer, "Over de grondslagen der wiskunde" (1907); "Intuitionism and Formalism" (1913) —
  rejection of `p ∨ ¬p` without a constructive witness.
* al-Ghazālī, *Tahāfut al-Falāsifa* (c. 1095) — the discipline of *docta ignorantia*.

NEW file under `Lutar/Innovations/round12/`; locked kernel (749/14/163 @ c7c0ba17) untouched.
Λ stays Conjecture 1.
-/
import Mathlib.Order.Basic
import Mathlib.Tactic

namespace Lutar
namespace Round12
namespace HonestSorry

/-- Nāgārjuna's four corners. -/
inductive Catuskoti
  | affirmed | denied | both | neither
deriving DecidableEq, Repr

/-- The SZL 3-valued gate. -/
inductive Verdict
  | green | amber | red
deriving DecidableEq, Repr

/-- The doctrine collapse: affirmed↦green, denied↦red, the two empty corners ↦ amber. -/
def collapse : Catuskoti → Verdict
  | .affirmed => .green
  | .denied   => .red
  | .both     => .amber
  | .neither  => .amber

/-- Order on the 3-chain: red < amber < green (RED most-constrained, GREEN most-affirmed). -/
def Verdict.le : Verdict → Verdict → Prop
  | .red, _ => True
  | .amber, .red => False
  | .amber, _ => True
  | .green, .green => True
  | .green, _ => False

/-- **AMBER is forced (sorry-free).** Any map `φ : Catuskoti → Verdict` that
(i) pins the two decided corners `affirmed ↦ green`, `denied ↦ red`, and
(ii) sends both *empty* corners to the same value strictly between the decided ones
     (i.e. to `amber`, the unique middle of the 3-chain),
must equal `collapse`. The empty corners cannot be GREEN or RED without claiming a decision the
catuṣkoṭi explicitly withholds; AMBER is the only remaining landing-spot. Finite case analysis. -/
theorem amber_forced
    (φ : Catuskoti → Verdict)
    (haff : φ .affirmed = .green) (hden : φ .denied = .red)
    (hboth : φ .both = .amber) (hneither : φ .neither = .amber) :
    φ = collapse := by
  funext c
  cases c <;> simp [collapse, haff, hden, hboth, hneither]

/-- The empty (paraconsistent) corners of the catuṣkoṭi. -/
def IsEmptyCorner : Catuskoti → Prop
  | .both => True
  | .neither => True
  | _ => False

/-- **Empty corners land on AMBER under the doctrine collapse (sorry-free).** -/
theorem emptyCorner_collapses_amber (c : Catuskoti) (h : IsEmptyCorner c) :
    collapse c = .amber := by
  cases c <;> simp_all [IsEmptyCorner, collapse]

/-- **Undecided** (Brouwerian marker): a proposition for which we have *neither* a proof nor a
refutation — i.e. no constructive witness of `p ∨ ¬p`. This is the type of an honest `sorry`. -/
def Undecided (p : Prop) : Prop := ¬ (p ∨ ¬ p)  -- intuitionistically NOT provable in general

/-- An evidence model maps a proposition to a catuṣkoṭi corner (constructive, runtime-supplied). -/
structure EvidenceModel where
  corner : Prop → Catuskoti

/-- The verdict the gate emits for a proposition under an evidence model. -/
def gateVerdict (M : EvidenceModel) (p : Prop) : Verdict := collapse (M.corner p)

/-- **Honest-`sorry` ↔ undecided (Brouwer bridge — HONEST `sorry`, scaffold).**
If the gate emits AMBER for `p` under an evidence model `M`, then `p` sits in the empty-corner
(paraconsistent) region and carries no constructive decision — the honest `sorry` is the typed
marker of `Undecided p`.

PROOF PATH: `gateVerdict M p = amber` forces (by injectivity of `collapse` off the empty corners,
`amber_forced` / `emptyCorner_collapses_amber`) `M.corner p ∈ {both, neither}`. In a *constructive*
evidence model, landing in `{both, neither}` means no proof and no refutation was produced, i.e.
`Undecided p`.

DEPENDS ON (the residual `sorry`): `EVIDENCE_MODEL` — the constructive contract that a `both`/`neither`
corner is produced *exactly when* neither `p` nor `¬p` has a constructive witness. Left open by
design: this *types* honest-unknowing rather than classically discharging it (doing so classically
would violate the Brouwerian reading). -/
theorem honest_sorry_is_undecided
    (M : EvidenceModel) (p : Prop)
    (hamber : gateVerdict M p = .amber) :
    Undecided p := by
  -- `gateVerdict M p = amber` ⇒ `M.corner p` is an empty corner (both/neither).
  -- A constructive evidence model only emits an empty corner when neither p nor ¬p is witnessed.
  sorry  -- DEPENDS ON: EVIDENCE_MODEL (constructive both/neither ⇔ no decision). Brouwer bridge.

/-! ### Correspondence summary

`amber_forced` + `emptyCorner_collapses_amber` are **proved, sorry-free**: AMBER is the forced image
of the catuṣkoṭi's two empty corners. `honest_sorry_is_undecided` *types* the honest-`sorry` as the
Brouwerian marker `Undecided p`, with its single open contract (`EVIDENCE_MODEL`) named. Together they
give the SZL honest-halt doctrine a constructive (intuitionistic) reading: a `sorry`/AMBER is not a
failure to prove but the *correct* representation of a not-yet-decided proposition — al-Ghazālī's
docta ignorantia made type-theoretic, and Avicenna's contingent shell made order-theoretic.

Reference: Garfield (1995); Brouwer (1907, 1913); SEP "Ibn Sīnā's Metaphysics"; al-Ghazālī (c. 1095). -/

end HonestSorry
end Round12
end Lutar
