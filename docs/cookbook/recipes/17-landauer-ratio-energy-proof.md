# Recipe 17 — Landauer Ratio: Honest Anti-Free-Energy Proof

> **Prove that a compute job is physically bounded by computing the ratio of actual
> energy used to the Landauer thermodynamic minimum. ratio ≫ 1 is the HONEST INVERSE
> of a free-energy claim. MEASURED label only with real NVML joules.**

This recipe uses the `/api/a11oy/v1/formula-surfaces/landauer` endpoint to surface the
Landauer ratio alongside any energy receipt.

**Doctrine:** Landauer (1961) is an established external result (CITED, not claimed).
`MEASURED` label requires `nvml_measured=true` (real NVML exporter < 120s).
`SAMPLE` otherwise. Never fabricated.

---

## Prerequisites

```bash
curl --version  # or python3
```

---

## Quickstart (UNAVAILABLE — no joules supplied, honest)

```bash
curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/landauer"
```

Returns `joules_label: "UNAVAILABLE"` — this is correct and honest. The endpoint
requires `actual_joules` to compute a ratio.

---

## With estimated joules (SAMPLE label)

```bash
# 1e9 bits erased (typical small LLM inference), 1 µJ actual energy
curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/landauer\
?actual_joules=1e-6&bits_erased=1e9"
```

Expected shape:

```json
{
  "surface": "landauer",
  "actual_joules": 1e-6,
  "joules_label": "SAMPLE",
  "bits_erased": 1e9,
  "bits_label": "MODELED",
  "e_min_per_bit_j_sci": "2.870979e-21",
  "e_min_total_j": 2.870979e-12,
  "ratio": 348313.25,
  "ratio_label": "SAMPLE",
  "physical_interpretation": "ratio ≫ 1 → job is PHYSICALLY BOUNDED (honest inverse of free-energy claim)"
}
```

`ratio ≫ 1` is the proof that no perpetual-motion or free-energy claim is possible.

---

## With NVML-measured joules (MEASURED label)

```bash
# Pair with a real NVML joule reading from /api/a11oy/v1/energy/live
JOULES=$(curl -s "https://szlholdings-a11oy.hf.space/api/a11oy/v1/energy/live" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_joules') or '')")

# If NVML is live, compute the Landauer ratio with MEASURED label
if [ -n "$JOULES" ]; then
  curl "https://szlholdings-a11oy.hf.space/api/a11oy/v1/formula-surfaces/landauer\
?actual_joules=${JOULES}&nvml_measured=true&bits_erased=1e12"
else
  echo "NVML not available — joules UNAVAILABLE (honest)"
fi
```

---

## Python integration (pair with energy receipt)

```python
import urllib.request, json

BASE = "https://szlholdings-a11oy.hf.space"

# 1. Get current energy reading
with urllib.request.urlopen(BASE + "/api/a11oy/v1/energy/live", timeout=15) as r:
    energy = json.load(r)

total_j = energy.get("total_joules")
nvml_live = energy.get("joules_label") == "MEASURED"

if total_j is None:
    print("NVML not available — Landauer ratio UNAVAILABLE (honest)")
else:
    # 2. Compute Landauer ratio with honest label
    url = (BASE + "/api/a11oy/v1/formula-surfaces/landauer"
           + f"?actual_joules={total_j}&nvml_measured={'true' if nvml_live else 'false'}"
           + "&bits_erased=1e12")
    with urllib.request.urlopen(url, timeout=15) as r:
        landauer = json.load(r)
    print("Joules label:", landauer["joules_label"])
    print("Ratio:", landauer.get("ratio"))
    print("Interpretation:", landauer.get("physical_interpretation"))
```

---

## Doctrine notes

- **MEASURED requires real NVML joules** (`nvml_measured=true`). Never pass `nvml_measured=true`
  with a fabricated or estimated joule count.
- **ratio ≫ 1** proves the computation consumed real thermodynamic work. This is the
  engine's anti-perpetual-motion proof, not a performance metric.
- **Landauer 1961 is CITED, not SZL's claim.** k_B = 1.380649×10⁻²³ J/K (exact, SI 2019).

*Doctrine v11 LOCKED — kernel `c7c0ba17` — 8 locked-proven {F1,F4,F7,F11,F12,F18,F19,F22}*
*Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>*
