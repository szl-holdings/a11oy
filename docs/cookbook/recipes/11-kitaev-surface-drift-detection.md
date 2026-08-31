# Kitaev surface drift detection

> **Encode a stream of trust-axis scores as a Kitaev surface-code lattice, inject synthetic drift, and watch the stabilizer syndrome flag it — drift detection as quantum-error-correction on the governance signal.**
>
> **Headline number: 1 injected drift event → 1 non-trivial stabilizer syndrome.**

Drift — the slow degradation of a model's trust-axis scores — is the governance equivalent of a
qubit error. SZL borrows [Kitaev's surface code](https://doi.org/10.1016/S0003-4916(02)00018-0):
lay the 13 axes on a lattice, define stabilizers over neighborhoods, and a non-trivial syndrome
means the surface has drifted.

> **Honest scope.** This is a *classical analogy* used as a detector, not a physical quantum code.
> The KS-18 / QEC structure has Lean scaffolding in `lutar-lean`, but the detector here is a
> deterministic syndrome check on real-valued axis scores. Λ remains **Conjecture 1**.

---

## Prerequisites

```bash
python3 -m pip install numpy requests
```

---

## Quickstart (runnable, no credentials)

```python
import numpy as np, requests

# 1. Pull the live 13-axis baseline (the "ground state" surface).
axes = requests.get("https://szlholdings-killinchu.hf.space/api/killinchu/v1/lambda", timeout=60).json()
base = np.array([a["score"] for a in axes["axes"]])     # 13 axis scores, ~0.90–0.95

# 2. Define stabilizers: each is the parity of a windowed deviation from baseline.
def syndrome(scores, ref, tol=0.03):
    dev = np.abs(scores - ref) > tol                     # which axes drifted past tolerance
    # plaquette/star stabilizers over sliding windows of 3 axes
    return [int(dev[i] ^ dev[i+1] ^ dev[i+2]) for i in range(len(scores) - 2)]

print("clean syndrome:", syndrome(base, base))           # all zeros => no drift

# 3. Inject synthetic drift on 'calibration' and re-measure.
drift = base.copy(); drift[1] -= 0.08                    # calibration sags
print("drift syndrome:", syndrome(drift, base))          # non-zero => detected
```

A clean surface yields an all-zero syndrome; injected drift lights up the stabilizers whose window
contains the drifted axis.

---

## Full walkthrough

### Step 1 — Define the lattice

Place the 13 yuyay_v3 axes on a 1-D ring (or a 2-D lattice for richer neighborhoods). Each axis is a
"data qubit"; its value is its current trust score.

### Step 2 — Choose stabilizers

A stabilizer is a parity check over a neighborhood: "did an odd number of axes in this window drift
past tolerance?" Star (vertex) and plaquette (face) operators in the surface code map to
overlapping windows here. Overlap is what localizes the drift.

### Step 3 — Measure the syndrome over time

Stream successive `/v1/lambda` snapshots and compute the syndrome each tick. A persistent
non-trivial syndrome — not a single noisy blip — is the drift signal. Decode (minimum-weight
matching, conceptually) to localize the most likely drifted axis.

### Step 4 — Route the alert to sentra

A confirmed drift syndrome is an action; feed it to sentra's `/v1/verdict` so the response is itself
gated and receipted (**[recipe 04](04-drone-counter-uas-verdict.md)** shows the verdict shape).

### Step 5 — Tie drift to the PAC-Bayes margin

Drift erodes the confidence margin from **[recipe 09](09-pac-bayes-confidence-margin.md)**:
recompute R̂ after a syndrome fires and confirm the bound still clears the Λ floor.

---

## See also

- **[09 — PAC-Bayes confidence margin](09-pac-bayes-confidence-margin.md)** — quantify the erosion.
- **[03 — Fine-tune a compliance regime](03-fine-tune-compliance-regime.md)** — set the tolerances.
- **[04 — Drone counter-UAS verdict](04-drone-counter-uas-verdict.md)** — gate the alert.
- Live: [killinchu Λ axes](https://szlholdings-killinchu.hf.space/api/killinchu/v1/lambda)

## Cite this recipe

```bibtex
@misc{szl_cookbook_kitaev_drift_2026,
  title        = {Kitaev surface drift detection (SZL Cookbook recipe 11)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/11-kitaev-surface-drift-detection.md}},
  note         = {Classical surface-code analogy used as a drift detector. Λ = Conjecture 1.}
}
```

Reference: Kitaev 2003, *Annals of Physics* 303:2–30 (fault-tolerant computation by anyons).

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
