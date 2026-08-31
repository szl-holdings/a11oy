# Recipe 18 — Science Formula Surfaces (Kalman, Hoeffding, BFT Quorum, Yarqa CFD)

> **Access the dormant science-corpus formulas as live honest endpoints: Kalman filter
> step, Hoeffding tail bound, Byzantine quorum check, and Yarqa plug-flow CFD
> compartmentalization. Each carries its doctrine label (LIVE / ENGINEERING-METHOD-CFD)
> and Lean theorem reference.**

This recipe covers the four science-corpus surfaces added in the
`/api/a11oy/v1/formula-surfaces/science/*` namespace.

---

## Prerequisites

```bash
curl --version
```

No credentials required.

---

## 1. Science formula index

```bash
curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/science"
```

Returns the full index of wired science formulas with endpoints, labels, and corpus refs.

---

## 2. Kalman filter step (K-25 — LIVE, PROVEN)

Kalman update: given prior mean + variance and an observation, returns the posterior.
Gain K ∈ [0,1] and variance reduction are **sorry-free PROVEN** in
`FrontierKalmanGain.lean`.

```bash
# prior_mean=0, prior_var=2, observation=3, obs_noise_var=1
curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/science/kalman\
?prior_mean=0&prior_var=2&observation=3&obs_noise_var=1"
```

Expected:

```json
{
  "surface": "science/kalman",
  "kalman_gain": 0.666667,
  "posterior_mean": 2.0,
  "posterior_var": 0.666667,
  "variance_reduced": true,
  "label": "LIVE",
  "lean_theorems": [
    "FrontierKalmanGain.lean::gain_in_unit_interval (sorry-free)",
    "FrontierKalmanGain.lean::posterior_le_prior (sorry-free)"
  ]
}
```

---

## 3. Hoeffding tail bound (K-11 — LIVE, PROVEN)

For n i.i.d. bounded [0,1] samples, the probability the sample mean deviates by ≥ t
from the true mean is at most 2·exp(−2nt²).

```bash
# n=500 samples, t=0.05 deviation
curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/science/hoeffding\
?n=500&t=0.05"
```

Expected:

```json
{
  "surface": "science/hoeffding",
  "n": 500,
  "t": 0.05,
  "tail_bound": 0.082085,
  "interpretation": "P(|sample_mean - true_mean| ≥ 0.05) ≤ 0.082085",
  "label": "LIVE"
}
```

---

## 4. Byzantine quorum check (K-24 — faultyCount PROVEN; safety = Conjecture 2)

Computes the BFT quorum threshold and checks whether n ≥ 3f+1.

```bash
# 7 validators, tolerance for 2 faults
curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/science/byzantine-quorum\
?n=7&f=2"
```

Expected:

```json
{
  "surface": "science/byzantine-quorum",
  "n_validators": 7,
  "f_faulty_tolerated": 2,
  "min_n_required": 7,
  "quorum_threshold": 5,
  "n_satisfies_3f_plus_1": true,
  "verdict": "QUORUM_ACHIEVABLE",
  "honesty": "...BFT safety = CONJECTURE 2 (NOT a theorem)..."
}
```

**Important:** `khipu_consensus_safety` = Conjecture 2 (open sorry). The quorum math
is exact; the safety proof is not complete.

---

## 5. Yarqa plug-flow CFD compartmentalization (Y-01/Y-02 — ENGINEERING-METHOD-CFD)

Grows compartments from a seed cell through velocity-aligned face-neighbors.

```bash
# Default demo (5 synthetic cells)
curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/yarqa-plug-flow"
```

Custom mesh via POST:

```bash
curl -X POST \
  "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/yarqa-plug-flow" \
  -H "Content-Type: application/json" \
  -d '{
    "cells": [
      {"id": "s",  "velocity": [1,0,0], "position": [0,0,0]},
      {"id": "a",  "velocity": [0.9,0.1,0], "position": [1,0,0]},
      {"id": "b",  "velocity": [0,1,0], "position": [0,2,0]}
    ]
  }'
```

Expected:

```json
{
  "surface": "yarqa-plug-flow",
  "compartments": [...],
  "n_compartments": 2,
  "label": "ENGINEERING-METHOD-CFD",
  "honesty": "NOT a locked theorem. NOT folded into the locked-8 set."
}
```

---

## Module health check

```bash
curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/healthz"
```

---

## Python batch example

```python
import urllib.request, json

BASE = "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces"

for path, label in [
    ("/science/kalman?prior_mean=0&prior_var=1&observation=2&obs_noise_var=0.5", "Kalman"),
    ("/science/hoeffding?n=1000&t=0.02", "Hoeffding"),
    ("/science/byzantine-quorum?n=10&f=3", "BFT Quorum"),
    ("/yarqa-plug-flow", "Plug-flow CFD"),
]:
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        d = json.load(r)
    print(f"{label}: label={d.get('label','?')}, surface={d.get('surface','?')}")
```

---

## Doctrine notes

- **LIVE** surfaces compute exact results with no approximation.
- **ENGINEERING-METHOD-CFD** (Yarqa) is a validated engineering method, NOT a locked theorem.
- **BFT quorum math is LIVE; BFT safety is Conjecture 2** — never conflate.
- **Λ = Conjecture 1** for any downstream governance aggregation.

*Doctrine v11 LOCKED — kernel `c7c0ba17` — 8 locked-proven {F1,F4,F7,F11,F12,F18,F19,F22}*
*Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>*
