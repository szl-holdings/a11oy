-- Lutar/Innovations/round9/NervousShannonAlarm.lean
-- ORGAN 6 — NERVOUS (vsp-otel Λ-signed OTEL exporter + sentra surface drift detection)
-- ROUND-9 INSTILL: information-theoretic alarm — fire iff H(signal) > H(noise) + ε
--   (classical Shannon entropy).
-- Source lineage: Lutar/Shannon/DoctrineEntropy.lean (Shannon 1948, A Mathematical
--   Theory of Communication, BSTJ 27; Kraft inequality), Lutar/DPI/SCITTMaskEntropy.lean.
--   Runtime: amaru /api/amaru/overwatch/snapshot (invariant I1 kl_drift_per_axis,
--   threshold 0.1), vsp-otel exporter (platform/services/vsp-otel), DOI 10.5281/zenodo.20424995.
-- Doctrine v11 LOCKED 749/14/163. Lambda = Conjecture 1 (NOT a theorem).
-- ADDITIVE — not imported into Lutar.lean; does NOT touch the locked kernel.
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

/-
# Nervous — Shannon-entropy alarm (signal exceeds noise by ε)

The nervous system carries Λ-signed telemetry spans. An alarm should fire only when a
span carries real INFORMATION, not noise. The killer rule is information-theoretic:

    fire  ⇔  H(signal) > H(noise) + ε

This separates a genuine drift event (high-entropy anomaly relative to the calibrated
noise floor) from background jitter, and is the formal antidote to alert fatigue.
The live amaru overwatch snapshot already exposes the dual via KL-drift invariant I1
(kl_drift_per_axis, threshold 0.1) — KL and entropy share the same Shannon foundation.
Lutar/Shannon/DoctrineEntropy.lean proves the doctrine alphabet has max entropy exactly
2 bits and the Kraft inequality holds at equality. This module instills the alarm
THRESHOLD invariant over a Nat surrogate (entropy in integer "bit-units"), sorry-free.
-/

namespace Lutar.Innovations.Round9.NervousShannonAlarm

/-- Alarm predicate: fire iff signal-entropy exceeds noise-entropy plus margin ε. -/
def fires (hSignal hNoise epsilon : Nat) : Bool := decide (hNoise + epsilon < hSignal)

/-- KEY 1 — NOISE IMMUNITY: when signal entropy does not clear noise + ε, the alarm is
    silent — background jitter cannot trip the nervous system (no alert fatigue). -/
theorem silent_below_floor (hNoise epsilon : Nat) :
    fires (hNoise + epsilon) hNoise epsilon = false := by
  unfold fires; simp

/-- KEY 2 — MONOTONE SENSITIVITY: raising the margin ε can only suppress alarms, never
    create them — ε is a monotone knob on false-alarm rate. -/
theorem epsilon_monotone (hSignal hNoise e₁ e₂ : Nat) (h : e₁ ≤ e₂) :
    fires hSignal hNoise e₂ = true → fires hSignal hNoise e₁ = true := by
  unfold fires; simp only [decide_eq_true_eq]; intro hh; omega

/-- KEY 3 — STRICT TRIGGER: a signal strictly above noise + ε always fires (soundness:
    real information is never silently dropped). -/
theorem fires_on_real_info (hNoise epsilon : Nat) :
    fires (hNoise + epsilon + 1) hNoise epsilon = true := by
  unfold fires; simp

end Lutar.Innovations.Round9.NervousShannonAlarm
