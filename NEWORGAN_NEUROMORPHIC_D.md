<!-- SPDX-License-Identifier: Apache-2.0 (c) 2026 Lutar, Stephen P. - SZL Holdings -->

# NEWORGAN\_NEUROMORPHIC\_D — Neuromorphic / Spiking Neural Compute Organ

**Dev:** Opus 4.8 Dev D · SZL a11oy frontier team  
**Wave:** 2026-06-30  
**Doctrine:** v11 — NOTHING here is in the locked-8. Λ = Conjecture 1. Trust < 100%.

---

## 1. Files Added

| File | Role |
|------|------|
| `szl_neuromorphic.py` | Endpoint module — LIF population simulation, `register(app, ns)` |
| `static/3d/surfaces/neuromorphic.js` | Standalone surface organ — 3D LIF lattice, polls live endpoint |
| `NEWORGAN_NEUROMORPHIC_D.md` | This document |

**Files changed:** None — additive only.  
**Existing organ files untouched:** `frontier.js`, `anatomy.js`, `counter-uas.js`, `energy.js`, `estate.js`, `fabric.js`, `governance.js`, `pinn.js`, `pnt.js`, `router.js` — all 9 verified unmodified (`git diff --stat` returns empty).

---

## 2. Exact Wire-Up Lines

### 2a. `serve.py` — add ONE import+register block (before the `if __name__ == "__main__":` block):

```python
# ADDITIVE (NEUROMORPHIC ORGAN, 2026-06-30, Dev D): deterministic LIF spiking-neural-compute
# snapshot. MODELED label (simulation, not silicon). Citations: Gerstner & Kistler 2002;
# Davies et al. 2021 JPROC DOI:10.1109/JPROC.2021.3067593; Neftci et al. arXiv:1901.09948.
# Registers GET /api/a11oy/v1/neuromorphic/spikes. Additive, try/except-guarded.
try:
    import szl_neuromorphic as _szl_neuromorphic
    _szl_neuromorphic.register(app, ns="a11oy")
    print("[a11oy] Neuromorphic spikes registered: /api/a11oy/v1/neuromorphic/spikes", file=__import__("sys").stderr)
except Exception as _szl_neuro_e:  # pragma: no cover
    print(f"[a11oy] Neuromorphic spikes NOT registered: {_szl_neuro_e!r}", file=__import__("sys").stderr)
```

Recommended insertion point: immediately after the `szl_neuroplasticity` block (line ~1291 in current `serve.py`).

### 2b. `Dockerfile` — add ONE `COPY` line (inside the bulk `COPY ... ./` block near the end):

```dockerfile
COPY szl_neuromorphic.py ./
```

Or append `szl_neuromorphic.py` to the existing long `COPY ... szl_quantum_bio.py ... szl_neuroplasticity.py ... ./` line.

### 2c. `static/3d/surfaces/neuromorphic.js` — standalone, no changes to `frontier.js`.

The surface organ can be loaded independently (standalone demo page or mounted by the ring router):

```javascript
import NeuromorphicOrgan from "/static/3d/surfaces/neuromorphic.js";
NeuromorphicOrgan.mount(ctx);  // ctx = { stage, container, live, label, THREE, szl3d }
```

To add it to the frontier ring (`frontier.js`), insert it as organ index 9 (making N_ORG = 10) following the existing ring/POS pattern — but the task specifies a standalone module preferred, and the 9 existing organs must remain untouched.

---

## 3. Endpoint Specification

```
GET /api/a11oy/v1/neuromorphic/spikes
```

**Query params (all optional):**

| Param | Default | Range | Meaning |
|-------|---------|-------|---------|
| `seed` | 42 | int | Deterministic RNG seed |
| `n_neurons` | 64 | 4–256 | Population size |
| `dt_ms` | 0.5 | 0.1–5.0 | Time step (ms) |
| `T_ms` | 100.0 | 10–1000 | Window duration (ms) |
| `tau_m` | 20.0 | 1–200 | Membrane time constant (ms) |
| `v_rest` | -65.0 | float | Resting potential (mV) |
| `v_thresh` | -50.0 | float | Spike threshold (mV) |
| `R` | 10.0 | 0.1–100 | Membrane resistance (MΩ) |
| `I_mean` | 1.5 | float | Mean input current (nA) |
| `I_std` | 0.5 | 0–5 | Per-neuron input heterogeneity (nA) |

**Returns JSON:** `label`, `model`, `membrane_potentials[]`, `spike_raster_counts[]`, `mean_firing_rate_hz`, `event_sparsity`, `energy_per_spike_pJ`, `energy_label`, `total_spikes`, `honest_note`, `citations`, `computed_at`.

---

## 4. Honesty Labels Used

| Field | Value | Meaning |
|-------|-------|---------|
| `label` | `MODELED` | Closed-form LIF simulation — not measured silicon |
| `energy_label` | `MODELED` | Energy/spike estimate from Loihi 2 published specs — not an NVML reading |

Both labels are returned **verbatim** from the JSON and displayed **verbatim** on the surface. Neither is upgraded or softened client-side. Per doctrine v11 honesty-label read protocol in `szl3d_live.js` (`readHonestyLabel`).

Valid doctrine honesty tokens include: `MEASURED / MODELED / ROADMAP / SAMPLE / VERIFIED / CONJECTURE / HONEST-STUB`. This organ uses `MODELED` throughout.

---

## 5. Citations (URLs)

All cited openly; none claimed as SZL's own.

| Source | URL |
|--------|-----|
| Gerstner & Kistler "Spiking Neuron Models" (2002) — LIF model | https://neuronaldynamics.epfl.ch/online/ |
| Davies et al. 2021 "Advancing Neuromorphic Computing With Loihi" JPROC 109(5):911-934 | https://doi.org/10.1109/JPROC.2021.3067593 |
| Lava OSS framework (BSD-3-Clause), Intel | https://github.com/lava-nc/lava |
| Neftci, Mostafa & Zenke "Surrogate Gradient Learning in SNNs" arXiv:1901.09948 | https://arxiv.org/abs/1901.09948 |
| BrainScaleS neuromorphic hardware, Heidelberg | https://brainscales.kip.uni-heidelberg.de/ |

Energy model note: `energy_per_spike_pJ = 50.0` is a MODELED mid-range value from Loihi 2 published characterisation (range ~10–100 pJ/spike depending on topology and operation). It is never presented as a measured value.

---

## 6. Local Test Commands

### Smoke-test Python (no server):
```bash
python3 szl_neuromorphic.py
# Expected output:
# mean_firing_rate_hz: 12.5
# event_sparsity: 0.99375
# total_spikes: 5
# membrane_potentials[:4]: [-51.1928, -54.2768, -55.4544, -53.936]
# spike_raster_counts: [0, 0, 0, 0, 0, 1, 2, 2]
# label: MODELED
```

### AST parse check:
```bash
python3 -c "import ast; ast.parse(open('szl_neuromorphic.py').read()); print('OK')"
```

### Curl the endpoint (once serve.py import+register line is added):
```bash
curl -s "http://localhost:7860/api/a11oy/v1/neuromorphic/spikes?seed=42&n_neurons=64" | python3 -m json.tool | grep -E '"label"|"mean_firing_rate_hz"|"event_sparsity"|"energy_per_spike_pJ"'
# Expected:
#     "label": "MODELED",
#     "mean_firing_rate_hz": 12.5,
#     "event_sparsity": 0.99375,
#     "energy_per_spike_pJ": 50.0,
```

### Determinism check (same seed must give identical results):
```bash
curl -s "http://localhost:7860/api/a11oy/v1/neuromorphic/spikes?seed=99&n_neurons=32" | python3 -m json.tool | grep total_spikes
curl -s "http://localhost:7860/api/a11oy/v1/neuromorphic/spikes?seed=99&n_neurons=32" | python3 -m json.tool | grep total_spikes
# Both lines must be identical
```

---

## 7. Design Notes

- **No numpy required.** Pure stdlib: `math`, `datetime`, `json`, `starlette`. Mirrors `szl_neuroplasticity.py` constraint.
- **Deterministic.** Per-neuron inputs use `I_mean + I_std * cos(2π * (i + seed%1000) / n_neurons)` — no `random` module, same seed → same output always.
- **Standalone surface.** `neuromorphic.js` is a clean `export default { id, title, mount, unmount }` module. It does not import or modify `frontier.js`. The 9 existing organs are completely untouched.
- **Colour discipline.** Purple (`0x8a6bff`) used only for spike-flash data-viz (per `C_SPIKE`). Base node colour is lattice-blue (`0x5b8dee`). No purple backgrounds or structural elements.
- **Honesty label read verbatim.** `_onSpikes` reads `j.label` and assigns it to `S.label` with `.toUpperCase()` only; the painter writes it to the DOM with `_set("nm-label", S.label)` — no substitution.
- **Graceful degradation.** On 404/error/missing state, all nodes render in `C_DIM` (grey), overlay shows `NO-LIVE-DATA`/`OFFLINE`, and the honesty label chip still renders `MODELED` from the last known payload (or `MODELED` as default).
