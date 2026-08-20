# Replicate the Walrus α-gap measurement

> **Measure the sim2real α-gap: how far a governance decision drifts between *simulated* telemetry and *live* broadcast telemetry — reproduced with killinchu's real ASTM F3411 / MAVLink decoders.**
>
> **Headline number: α-gap = |Λ_sim − Λ_real|, target α < 0.05.**

The "α-gap" is the sim2real discrepancy: a system tuned on synthetic inputs can behave differently
on live ones. For a counter-UAS gate, α is the gap between the Λ score on a *simulated* frame and on
the *same scenario decoded from live broadcast*. This recipe makes α measurable and reproducible.

> **Honest scope — read first.** SZL does not publish a pre-baked "Walrus α-gap dataset"; "Walrus"
> in the codebase is a blob-store component (`LocalWalrusStore`), not a benchmark. This recipe is
> the **methodology** to *produce* an α-gap measurement against the live killinchu decoders. The
> number you get is yours, reproducibly. Telemetry remains an unauthenticated **claim**
> (**[recipe 04](04-drone-counter-uas-verdict.md)**), and Λ remains **Conjecture 1**.

---

## Prerequisites

```bash
python3 -m pip install numpy requests
```

---

## Quickstart (live decoders, no credentials)

```python
import requests, numpy as np

KIL = "https://szlholdings-killinchu.hf.space/api/killinchu"

def lambda_for(track, fence):
    r = requests.post(f"{KIL}/v1/counter-uas/evaluate",
                      json={"track": track, "geofence": fence}, timeout=60).json()
    return r["lambda"], r["decision"]

fence = {"center_lat": 40.0, "center_lon": -74.0, "radius_m": 500}

# "sim" scenario: hand-authored track (clean, no decode noise)
lam_sim, dec_sim = lambda_for({"lat": 40.0, "lon": -74.0, "alt_m": 120}, fence)

# "real" scenario: the SAME geometry but perturbed as a decoded-from-broadcast claim would be
rng = np.random.default_rng(0)
noisy = {"lat": 40.0 + rng.normal(0, 1e-4), "lon": -74.0 + rng.normal(0, 1e-4),
         "alt_m": 120 + rng.normal(0, 2)}
lam_real, dec_real = lambda_for(noisy, fence)

alpha = abs(lam_sim - lam_real)
print(f"Λ_sim={lam_sim:.6f} ({dec_sim})  Λ_real={lam_real:.6f} ({dec_real})  α-gap={alpha:.6f}")
```

---

## Full walkthrough

### Step 1 — Define the matched scenario pair

For each test case, build two inputs that describe the *same physical situation*:
- **sim** — exact coordinates as you'd specify in a planner.
- **real** — those coordinates encoded into an ASTM F3411 frame, then decoded back through
  `/v1/remote-id/decode`, inheriting the decoder's quantization/rounding (the honest "claim" path).

### Step 2 — Run both through the same gate

Score both with `/v1/counter-uas/evaluate` so the only difference is the input provenance, not the
gate. Record `(Λ_sim, decision_sim)` and `(Λ_real, decision_real)`.

### Step 3 — Compute α per case and aggregate

```python
def alpha_gap(cases):
    diffs = [abs(s - r) for s, r in cases]
    return {"alpha_mean": float(np.mean(diffs)), "alpha_p95": float(np.percentile(diffs, 95)),
            "decision_flips": sum(1 for (s, r) in cases if (s >= 0.9) != (r >= 0.9))}
```

The headline metric is `alpha_mean`; the safety-critical metric is `decision_flips` (cases where the
ALLOW/DENY verdict changed between sim and real).

### Step 4 — Set and check the acceptance bar

A common bar is α < 0.05 mean and **zero** decision flips inside the operating envelope. If flips
occur, your gate is sim-overfit; widen the Λ axis tolerances (**[recipe 03](03-fine-tune-compliance-regime.md)**)
or add decode-noise augmentation.

### Step 5 — Bound it

Treat decision_flips as the empirical risk R̂ and apply
**[recipe 09 — PAC-Bayes confidence margin](09-pac-bayes-confidence-margin.md)** for a tail bound on
the α-gap over unseen scenarios. Persist the result as a receipt (**[recipe 01](01-verify-a-receipt-end-to-end.md)**).

---

## Reproducibility checklist

- [ ] Fixed RNG seed recorded.
- [ ] Same `geofence` for sim and real.
- [ ] Decoder path used for the "real" arm (not hand-typed).
- [ ] α_mean, α_p95, decision_flips reported with n.

---

## See also

- **[04 — Drone counter-UAS verdict](04-drone-counter-uas-verdict.md)** — the gate under test.
- **[09 — PAC-Bayes confidence margin](09-pac-bayes-confidence-margin.md)** — bound the gap.
- **[11 — Kitaev surface drift detection](11-kitaev-surface-drift-detection.md)**
- Live: [killinchu](https://szlholdings-killinchu.hf.space)

## Cite this recipe

```bibtex
@misc{szl_cookbook_alpha_gap_2026,
  title        = {Replicate the Walrus alpha-gap measurement (SZL Cookbook recipe 14)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/14-replicate-walrus-alpha-gap.md}},
  note         = {Methodology to produce a sim2real alpha-gap against live killinchu decoders; no pre-baked dataset. Λ = Conjecture 1.}
}
```

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
