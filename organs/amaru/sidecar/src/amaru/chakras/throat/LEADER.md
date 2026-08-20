# LEADER — throat chakra (vishuddha)

**Role:** expressive fidelity.

**Status:** LIVE. `kernel.evaluate` (proof `amaru.throat.v1`) computes
`fidelity = clamp(sqrt(clarity * truth), 0, 1)` and emits
`verdict ∈ {"speak", "hold"}` (threshold 0.5). The geometric mean
penalises one-sided expression — eloquent untruth and clumsy truth
both score low.

**Minimization proof:** `proof.json` — `proof_id=amaru.throat.v1`,
`sha256` is the canonical hash of `kernel.py` source bytes (re-pin via
`pin_proofs.py`).

**Canonical output shape:** `{ chakra: "throat", fidelity: ∈[0,1],
verdict, inputs: { clarity, truth } }` — see `result.json`.
