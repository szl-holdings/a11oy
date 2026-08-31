# LEADER — third-eye chakra (ajna)

**Role:** predictive insight.

**Status:** LIVE. `kernel.evaluate` (proof `amaru.third_eye.v1`)
computes `insight = clamp(pattern_strength * (1 - uncertainty), 0, 1)`
and emits a three-band verdict: `foresee` (≥0.5), `peek` (≥0.25),
else `blind`. High pattern strength under high uncertainty self-
discounts to honest blindness.

**Minimization proof:** `proof.json` — `proof_id=amaru.third_eye.v1`,
`sha256` is the canonical hash of `kernel.py` source bytes (re-pin via
`pin_proofs.py`).

**Canonical output shape:** `{ chakra: "third_eye", insight: ∈[0,1],
verdict, inputs: { pattern_strength, uncertainty } }` — see
`result.json`.
