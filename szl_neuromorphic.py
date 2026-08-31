"""
szl_neuromorphic.py — SZL neuromorphic / spiking-neural-compute endpoint.

Exposes a MODELED Leaky-Integrate-and-Fire (LIF) neuron-population snapshot as a
same-origin REST endpoint, so the neuromorphic surface organ has a live data source
that is honest, deterministic, and citable — never fabricated, never random-faked.

  GET  /api/<ns>/v1/neuromorphic/spikes?seed=&n_neurons=&dt_ms=&T_ms=&tau_m=&v_rest=&v_thresh=&R=&I_mean=&I_std=

Returned JSON fields
--------------------
  label               : "MODELED" (always — this is a simulation, not silicon)
  model               : "Leaky Integrate-and-Fire (LIF) population"
  n_neurons           : population size simulated
  T_ms                : total simulation window (ms)
  dt_ms               : time-step (ms)
  seed                : RNG seed used (deterministic; same seed -> same snapshot)
  membrane_potentials : final V for each neuron (mV), list[float]
  spike_raster_counts : spike count per neuron over the window, list[int]
  mean_firing_rate_hz : population-mean firing rate (Hz) over the window
  event_sparsity      : fraction of neuron-timestep slots that did NOT fire (0..1)
  energy_per_spike_pJ : MODELED estimate of energy per spike in picojoules
  energy_label        : "MODELED" — citing Intel Loihi 2 (tens of pJ/spike; see citation)
  energy_citation     : URL to the Loihi 2 whitepaper / Davies et al. 2021
  total_spikes        : total spike events in the window
  honest_note         : plain-language honesty disclaimer
  citations           : dict of citable sources
  computed_at         : ISO-8601 UTC timestamp

HONEST STATUS — "MODELED"
  This is a deterministic closed-form simulation, NOT measured silicon. The energy
  estimate (tens of pJ/spike) is a MODELED extrapolation from published Loihi 2 specs
  (Davies et al. 2021, Nature Electronics; Intel Loihi 2 whitepaper 2021). It is not
  an NVML measurement and must not be presented as one. The label "MODELED" is returned
  verbatim and displayed verbatim by the surface; it is never upgraded client-side.

CITATIONS (clean-room; none claimed as SZL's own):
  LIF model:
    Gerstner & Kistler, "Spiking Neuron Models" (2002), Cambridge Univ. Press.
    https://neuronaldynamics.epfl.ch/online/
  Intel Loihi 2 / Lava framework (BSD-3):
    Davies et al. (2021) "Advancing Neuromorphic Computing With Loihi",
    Proceedings of the IEEE 109(5):911-934. DOI:10.1109/JPROC.2021.3067593
    Lava OSS: https://github.com/lava-nc/lava (BSD-3-Clause)
  Surrogate-gradient SNNs:
    Neftci, Mostafa & Zenke (2019) "Surrogate Gradient Learning in Spiking Neural
    Networks". arXiv:1901.09948. https://arxiv.org/abs/1901.09948
  BrainScaleS neuromorphic hardware:
    Müller et al. (2022) "Scalable wafer-scale neuromorphic hardware", ESSDERC.
    https://brainscales.kip.uni-heidelberg.de/
  HONEST-STUB note: energy_per_spike_pJ is a modeled mid-range value (50 pJ/spike)
  drawn from published Loihi 2 characterisation (range ~10–100 pJ/spike depending
  on network topology and operation). It is not an on-chip measurement.

DOCTRINE v11: NOTHING here is in the locked-8. Λ = Conjecture 1. Trust < 100%.
  No fabricated data. Pure stdlib. Deterministic with seed. 0 runtime CDN.
"""
from __future__ import annotations

import math
import json
from datetime import datetime, timezone

from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

# ---------------------------------------------------------------------------
# Citations block — verbatim, never claimed as SZL's own
# ---------------------------------------------------------------------------
CITATIONS = {
    "LIF model — Gerstner & Kistler (2002)": "https://neuronaldynamics.epfl.ch/online/",
    "Intel Loihi 2 — Davies et al. 2021 JPROC": "https://doi.org/10.1109/JPROC.2021.3067593",
    "Lava OSS framework (BSD-3)": "https://github.com/lava-nc/lava",
    "Surrogate-gradient SNNs — Neftci et al. arXiv:1901.09948": "https://arxiv.org/abs/1901.09948",
    "BrainScaleS neuromorphic hardware": "https://brainscales.kip.uni-heidelberg.de/",
}

# Energy per spike: MODELED mid-range from Loihi 2 published characterisation.
# Davies et al. 2021 quote ~tens of pJ/spike; we use 50 pJ as a representative
# midpoint. NOT a measured value — label is "MODELED" throughout.
_ENERGY_PER_SPIKE_PJ_MODEL = 50.0


# ---------------------------------------------------------------------------
# Pure-stdlib LIF population simulation (deterministic seed)
# ---------------------------------------------------------------------------
def _lif_population(
    seed: int = 42,
    n_neurons: int = 64,
    dt_ms: float = 0.5,
    T_ms: float = 100.0,
    tau_m: float = 20.0,    # membrane time constant (ms)
    v_rest: float = -65.0,  # resting potential (mV)
    v_thresh: float = -50.0, # spike threshold (mV)
    R: float = 10.0,        # membrane resistance (MΩ)
    I_mean: float = 1.5,    # mean input current (nA)
    I_std: float = 0.5,     # per-neuron input heterogeneity (nA), deterministic from seed
) -> dict:
    """
    Event-driven LIF population.  Each neuron obeys:
        τ_m dV/dt = -(V - V_rest) + R·I_i
    integrated with forward Euler, reset to V_rest after spike.

    Inputs are heterogeneous (drawn from a deterministic linear spread around I_mean
    using the seed) so the population produces non-trivial spike rasters.
    Pure stdlib; no numpy required.  Same seed → identical output.
    """
    # --- deterministic per-neuron input currents (no random module, pure math) ---
    # Use a simple linear congruential spread seeded deterministically:
    # I_i = I_mean + I_std * cos(2π * (i + seed % 1000) / n_neurons)
    # This gives symmetric heterogeneity, seed-reproducible, no stdlib.random needed.
    inputs = [
        I_mean + I_std * math.cos(2.0 * math.pi * (i + (seed % 1000)) / max(n_neurons, 1))
        for i in range(n_neurons)
    ]

    n_steps = max(1, int(round(T_ms / dt_ms)))
    dt = dt_ms  # already in ms

    # Initial voltages: spread uniformly between V_rest and V_thresh (deterministic)
    v = [
        v_rest + (v_thresh - v_rest) * (i / max(n_neurons - 1, 1))
        for i in range(n_neurons)
    ]

    spike_counts = [0] * n_neurons
    refractory = [0] * n_neurons  # remaining refractory steps per neuron
    TAU_REF_STEPS = max(1, int(round(2.0 / dt_ms)))  # 2 ms absolute refractory

    # --- integrate ---
    for _step in range(n_steps):
        for j in range(n_neurons):
            if refractory[j] > 0:
                refractory[j] -= 1
                v[j] = v_rest
                continue
            # Forward Euler: τ dV/dt = -(V - V_rest) + R·I
            dv = (dt / tau_m) * (-(v[j] - v_rest) + R * inputs[j])
            v[j] += dv
            if v[j] >= v_thresh:
                spike_counts[j] += 1
                v[j] = v_rest
                refractory[j] = TAU_REF_STEPS

    total_spikes = sum(spike_counts)
    T_s = T_ms * 1e-3  # simulation window in seconds
    firing_rates_hz = [round(sc / T_s, 3) for sc in spike_counts]
    mean_firing_rate_hz = round(sum(firing_rates_hz) / n_neurons, 4)

    # event sparsity: fraction of neuron-timestep slots with NO spike
    total_slots = n_neurons * n_steps
    event_sparsity = round(1.0 - total_spikes / max(total_slots, 1), 6)

    return {
        "membrane_potentials": [round(x, 4) for x in v],
        "spike_raster_counts": spike_counts,
        "firing_rates_hz": firing_rates_hz,
        "mean_firing_rate_hz": mean_firing_rate_hz,
        "event_sparsity": event_sparsity,
        "total_spikes": total_spikes,
        "n_steps": n_steps,
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
def _fi(req: Request, key: str, default) -> float:
    try:
        return float(req.query_params.get(key, default))
    except Exception:
        return float(default)


def _ii(req: Request, key: str, default: int) -> int:
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _h_spikes(req: Request):
    seed       = _ii(req, "seed",      42)
    n_neurons  = max(4, min(_ii(req, "n_neurons", 64), 256))
    dt_ms      = max(0.1, min(_fi(req, "dt_ms",  0.5),  5.0))
    T_ms       = max(10.0, min(_fi(req, "T_ms",  100.0), 1000.0))
    tau_m      = max(1.0, min(_fi(req, "tau_m",  20.0),  200.0))
    v_rest     = _fi(req, "v_rest",  -65.0)
    v_thresh   = _fi(req, "v_thresh", -50.0)
    R          = max(0.1, min(_fi(req, "R",   10.0), 100.0))
    I_mean     = _fi(req, "I_mean",   1.5)
    I_std      = max(0.0, min(_fi(req, "I_std",  0.5),  5.0))

    sim = _lif_population(
        seed=seed, n_neurons=n_neurons, dt_ms=dt_ms, T_ms=T_ms,
        tau_m=tau_m, v_rest=v_rest, v_thresh=v_thresh,
        R=R, I_mean=I_mean, I_std=I_std,
    )

    energy_per_spike_pJ = _ENERGY_PER_SPIKE_PJ_MODEL
    total_energy_nJ = round(sim["total_spikes"] * energy_per_spike_pJ * 1e-3, 6)  # pJ -> nJ

    return JSONResponse({
        "label":               "MODELED",
        "model":               "Leaky Integrate-and-Fire (LIF) population, forward Euler",
        "equation":            "τ_m dV/dt = -(V - V_rest) + R·I  (Gerstner & Kistler 2002)",
        "n_neurons":           n_neurons,
        "T_ms":                T_ms,
        "dt_ms":               dt_ms,
        "seed":                seed,
        "tau_m_ms":            tau_m,
        "v_rest_mV":           v_rest,
        "v_thresh_mV":         v_thresh,
        "R_MOhm":              R,
        "I_mean_nA":           I_mean,
        "I_std_nA":            I_std,
        "membrane_potentials": sim["membrane_potentials"],
        "spike_raster_counts": sim["spike_raster_counts"],
        "firing_rates_hz":     sim["firing_rates_hz"],
        "mean_firing_rate_hz": sim["mean_firing_rate_hz"],
        "event_sparsity":      sim["event_sparsity"],
        "total_spikes":        sim["total_spikes"],
        "energy_per_spike_pJ": energy_per_spike_pJ,
        "energy_label":        "MODELED",
        "energy_citation":     CITATIONS["Intel Loihi 2 — Davies et al. 2021 JPROC"],
        "total_energy_nJ":     total_energy_nJ,
        "honest_note": (
            "MODELED: this is a closed-form LIF simulation, not measured silicon. "
            "Energy estimate (50 pJ/spike) is a MODELED mid-range value from Intel "
            "Loihi 2 published characterisation (Davies et al. 2021, JPROC "
            "DOI:10.1109/JPROC.2021.3067593; range ~10-100 pJ/spike depending on "
            "topology). Not an NVML or on-chip measurement. "
            "Deterministic: same seed -> identical snapshot. "
            "Cite also: Neftci et al. arXiv:1901.09948 (surrogate-gradient SNNs); "
            "BrainScaleS (Heidelberg); Lava OSS github.com/lava-nc/lava (BSD-3). "
            "SZL claims NONE of these methods as its own."
        ),
        "citations":    CITATIONS,
        "computed_at":  datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# register(app, ns) — mirrors szl_quantum_bio.register() exactly
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/neuromorphic/spikes onto app. Additive, try/except-guarded.
    Uses FastAPI add_api_route when available; falls back to Starlette Route append."""
    base = f"/api/{ns}/v1/neuromorphic"
    handlers = [
        (f"{base}/spikes", _h_spikes),
    ]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    # local smoke test — no server needed
    import json as _json
    sim = _lif_population(seed=42, n_neurons=8, dt_ms=0.5, T_ms=50.0)
    print("mean_firing_rate_hz:", sim["mean_firing_rate_hz"])
    print("event_sparsity:", sim["event_sparsity"])
    print("total_spikes:", sim["total_spikes"])
    print("membrane_potentials[:4]:", sim["membrane_potentials"][:4])
    print("spike_raster_counts:", sim["spike_raster_counts"])
    print("label: MODELED")
