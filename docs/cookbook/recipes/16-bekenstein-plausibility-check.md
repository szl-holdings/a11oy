# Recipe 16 — Bekenstein/F19 Plausibility Check

> **Apply the Bekenstein bound as an honest physics-plausibility advisory on any
> information-theoretic claim. Computes I_η / I_max with APPLIED label; never re-claims
> the external inequality as SZL's own result.**

This recipe uses the `/api/a11oy/v1/formula-surfaces/bekenstein-plausibility` endpoint
to check whether a measured or estimated information gain is physically plausible under
the Bekenstein bound (Bekenstein 1981, Phys. Rev. D 23:287).

**Doctrine:** F19 is one of 8 locked-proven formulas @ `c7c0ba17`. The endpoint
**APPLIES** the proven inequality — it is NOT a new SZL claim. Label is always
`MODELED` (caller-supplied R/E) or `SAMPLE` (defaults).

---

## Prerequisites

```bash
# no credentials required — public endpoint
curl --version  # or: python3 -c "import urllib.request"
```

---

## Quickstart (default SAMPLE parameters)

```bash
curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/bekenstein-plausibility"
```

Expected response shape:

```json
{
  "surface": "bekenstein-plausibility",
  "info_bits": 10.0,
  "bekenstein_max_bits": 2.867e+26,
  "ratio": 3.49e-26,
  "plausibility_label": "PHYSICALLY_PLAUSIBLE",
  "data_label": "SAMPLE",
  "radius_m": 1.0,
  "energy_j": 1.0,
  "basis": "F19 Bekenstein bound = PROVEN external inequality (Bekenstein 1981...)"
}
```

`ratio ≤ 1.0` → `PHYSICALLY_PLAUSIBLE`. Any claimed information gain that exceeds
I_max for the given physical system would be `PHYSICALLY_IMPLAUSIBLE`.

---

## Caller-supplied values (MODELED label)

Supply the physical system radius and energy for a real computation:

```bash
# 1 micron radius object, 1 nJ energy, 50 bits gained
curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/bekenstein-plausibility\
?bits_gained=50&radius_m=1e-6&energy_j=1e-9"
```

Or using sigma (prior/posterior std) to compute bits gained from a Bayesian update:

```bash
curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/bekenstein-plausibility\
?sigma_prior=1.0&sigma_posterior=0.1&radius_m=1e-6&energy_j=1e-9"
```

---

## Python integration

```python
import urllib.request, json

url = ("https://szlholdings-a11oy.hf.space"
       "/api/a11oy/v1/formula-surfaces/bekenstein-plausibility"
       "?bits_gained=50&radius_m=1e-6&energy_j=1e-9")

with urllib.request.urlopen(url, timeout=15) as r:
    data = json.load(r)

assert data["plausibility_label"] in ("PHYSICALLY_PLAUSIBLE", "PHYSICALLY_IMPLAUSIBLE")
assert data["data_label"] in ("SAMPLE", "MODELED")
print("ratio:", data["ratio"])
print("label:", data["plausibility_label"])
print("basis:", data["basis"])
```

---

## Doctrine notes

- **F19 APPLIED, not re-claimed.** This endpoint applies an external, peer-reviewed
  proven inequality. It adds zero to the SZL locked-proven count (still exactly 8).
- **No half-state.** If inputs are missing the response is `SAMPLE` with default
  R=1m, E=1J — never a fabricated tight bound.
- **Λ = Conjecture 1** for any downstream trust aggregation over this result.

*Doctrine v11 LOCKED — kernel `c7c0ba17` — 8 locked-proven {F1,F4,F7,F11,F12,F18,F19,F22}*
*Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>*
