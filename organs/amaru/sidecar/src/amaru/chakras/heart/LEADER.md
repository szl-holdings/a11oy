# LEADER — heart chakra (anahata)

**Role:** coherence / harm avoidance.

**Status:** LIVE. `kernel.evaluate` (proof `amaru.heart.v1`) computes
`coherence = clamp(care - harm, 0, 1)` and emits
`verdict ∈ {"open", "guard"}` (threshold 0.3). Harm subtracts from
care so the chakra cannot rationalise high-care / high-harm action.

**Minimization proof:** `proof.json` — `proof_id=amaru.heart.v1`,
`sha256` is the canonical hash of `kernel.py` source bytes (re-pin via
`pin_proofs.py`).

**Canonical output shape:** `{ chakra: "heart", coherence: ∈[0,1],
verdict, inputs: { care, harm } }` — see `result.json`.
