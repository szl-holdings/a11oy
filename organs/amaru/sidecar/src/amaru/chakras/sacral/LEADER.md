# LEADER — sacral chakra (svadhisthana)

**Role:** generative flow.

**Status:** LIVE. `kernel.evaluate` (proof `amaru.sacral.v1`) computes
`flow = clamp(0.6 * fluency + 0.4 * novelty, 0, 1)` and emits
`verdict ∈ {"generate", "rest"}` (threshold 0.4). Fluency is weighted
above novelty so unrefined ideation cannot dominate.

**Minimization proof:** `proof.json` — `proof_id=amaru.sacral.v1`,
`sha256` is the canonical hash of `kernel.py` source bytes (re-pin via
`pin_proofs.py`).

**Canonical output shape:** `{ chakra: "sacral", flow: ∈[0,1],
verdict, inputs: { novelty, fluency } }` — see `result.json`.
