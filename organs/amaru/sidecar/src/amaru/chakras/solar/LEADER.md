# LEADER — solar chakra (manipura)

**Role:** will / decisive action.

**Status:** LIVE. `kernel.evaluate` (proof `amaru.solar.v1`) computes
`will = clamp(intent * agency - friction, 0, 1)` and emits a
three-band verdict: `act` (≥0.5), `defer` (≥0.2), else `block`.
Multiplicative `intent * agency` means either being zero collapses
will; friction subtracts so environmental drag is honest.

**Minimization proof:** `proof.json` — `proof_id=amaru.solar.v1`,
`sha256` is the canonical hash of `kernel.py` source bytes (re-pin via
`pin_proofs.py`).

**Canonical output shape:** `{ chakra: "solar", will: ∈[0,1],
verdict, inputs: { intent, agency, friction } }` — see `result.json`.
