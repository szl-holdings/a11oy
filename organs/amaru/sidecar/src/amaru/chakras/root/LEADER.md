# LEADER — root chakra (muladhara)

**Role:** substrate grounding.

**Status:** LIVE. `kernel.evaluate` (proof `amaru.root.v1`) computes
`stability = clamp((grounded + integrity) / 2, 0, 1)` and emits
`verdict ∈ {"ground", "destabilize"}` (threshold 0.5).

**Minimization proof:** `proof.json` — `proof_id=amaru.root.v1`,
`sha256` is the canonical hash of `kernel.py` source bytes. Re-pin
via `services/amaru/scripts/pin_proofs.py` on every kernel edit so the
shipped proof never drifts from the executing code.

**Canonical output shape:** `{ chakra: "root", stability: ∈[0,1],
verdict, inputs: { grounded, integrity } }` — see `result.json` for
the canonical (input, output) pair pinned by `pin_results.py`.
