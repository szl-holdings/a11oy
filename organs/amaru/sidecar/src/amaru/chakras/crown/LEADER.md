# LEADER — crown chakra (sahasrara)

**Role:** closure / ouroboros.

**Status:** LIVE. `kernel.evaluate` (proof `amaru.crown.v1`) aggregates
upstream scalar readings into `closure = clamp(mean(upstream
scalars), 0, 1)` and emits `verdict ∈ {"close", "spin"}` (threshold
0.5) plus a fixed `handoff = { to: "root", via: "ouroboros" }` so the
scheduler closes the loop deterministically.

**Minimization proof:** `proof.json` — `proof_id=amaru.crown.v1`,
`sha256` is the canonical hash of `kernel.py` source bytes (re-pin via
`pin_proofs.py`).

**Canonical output shape:** `{ chakra: "crown", closure: ∈[0,1],
verdict, n_upstream_scalars, handoff: { to: "root", via: "ouroboros" }
}` — see `result.json`.
