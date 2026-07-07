#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 - Doctrine v11
"""
ollama_energy_probe.py — REAL per-inference GPU energy for a local Ollama model.

Measures the joules a single Ollama generate call actually draws on the GPU by
bracketing the blocking HTTP request with an NVML energy read, then divides by the
model's own reported output-token count to get joules/token. Writes the latest
reading to a JSON file the omen-joule-exporter merges into its meter payload as a
`models[]` entry, so the a11oy energy surface can show the GLM-4.7-Flash node's
MEASURED joules/token instead of UNAVAILABLE.

HONESTY (doctrine v11 — never fabricate a joule):
  * energy is read ONLY from the real GPU via NVML. Two methods, best available first:
      1. counter-delta  : nvmlDeviceGetTotalEnergyConsumption (Volta+, on-die
                          hardware energy accumulator, mJ). label MEASURED*.
      2. power-integral : nvmlDeviceGetPowerUsage (mW) polled in a thread +
                          trapezoidal integral. Used only when (1) is not supported.
                          Still MEASURED* (lower fidelity), source noted explicitly.
    If nvmlInit fails entirely (no NVIDIA driver / pynvml) -> label UNAVAILABLE and
    NO number is emitted. We never guess.
  * GPU-exclusivity honesty: NVML counts the WHOLE GPU, not one process. Unless you
    assert OLLAMA_GPU_EXCLUSIVE=1 (you know nothing else uses that GPU during the
    window), the label is MEASURED_SHARED_BOUNDED — a real counter delta that may
    include co-tenant energy (an upper bound), never the clean MEASURED.
  * idle baseline (optional): idle GPU power is sampled ~5s while Ollama is
    loaded-but-idle; both gross energy (raw delta) and idle-subtracted net energy
    are reported as SEPARATE labeled fields. Neither is folded silently into the other.

LABELS (verbatim, never upgraded):
  MEASURED                 counter/power delta, GPU asserted exclusive (OLLAMA_GPU_EXCLUSIVE=1)
  MEASURED_SHARED_BOUNDED  real counter/power delta, GPU exclusivity NOT asserted (default)
  UNAVAILABLE              NVML unreachable -> no number emitted

RUN (on the box, GPU running Ollama):
  # one reading, default model + prompt, write to ~/.a11oy_ollama_energy.json
  python ollama_energy_probe.py --once

  # continuous refresh every 60s (what the persist task runs)
  python ollama_energy_probe.py --loop 60

  # assert the GPU is exclusive to Ollama during the window (clean MEASURED)
  OLLAMA_GPU_EXCLUSIVE=1 python ollama_energy_probe.py --loop 60

ENV:
  OLLAMA_URL           base Ollama URL           (default http://localhost:11434)
  OLLAMA_MODEL         model tag to generate with (default glm-4.7-flash:latest)
  OLLAMA_ENERGY_PROMPT probe prompt               (default a short deterministic prompt)
  OLLAMA_GPU_INDEX     NVML GPU index Ollama uses (default 0)
  OLLAMA_GPU_EXCLUSIVE 1 => assert exclusive => clean MEASURED (default 0 => BOUNDED)
  OLLAMA_ENERGY_JSON   output file (default ~/.a11oy_ollama_energy.json)
  OLLAMA_ENERGY_IDLE_S idle-baseline sample seconds, 0 disables (default 5.0)
  OLLAMA_ENERGY_TIMEOUT generate HTTP timeout seconds (default 600)

METHOD SOURCES (the field-standard approach — Zeus / ML.ENERGY / MELODI):
  * Zeus (ML.ENERGY leaderboard's engine): You et al., NSDI'23, arXiv:2208.06102
    https://github.com/ml-energy/zeus
  * ML.ENERGY "Measuring GPU Energy: Best Practices" (exact counter-delta pattern):
    https://ml.energy/blog/energy/measurement/measuring-gpu-energy-best-practices/
  * MELODI, "The Price of Prompting" (wraps a local Ollama call the same way):
    arXiv:2407.16893 — https://github.com/ejhusom/MELODI
  * NVIDIA NVML API Reference (nvmlDeviceGetTotalEnergyConsumption is Volta+):
    https://docs.nvidia.com/deploy/pdf/NVML_API_Reference_Guide.pdf

Pure stdlib + optional pynvml. No other pip installs.
"""
import argparse
import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "glm-4.7-flash:latest")
OLLAMA_ENERGY_PROMPT = os.environ.get(
    "OLLAMA_ENERGY_PROMPT",
    "In one short paragraph, explain what a joule measures.",
)
GPU_INDEX = int(os.environ.get("OLLAMA_GPU_INDEX", "0"))
GPU_EXCLUSIVE = os.environ.get("OLLAMA_GPU_EXCLUSIVE", "0").strip() in ("1", "true", "True", "yes")
IDLE_SAMPLE_S = float(os.environ.get("OLLAMA_ENERGY_IDLE_S", "5.0"))
GENERATE_TIMEOUT_S = float(os.environ.get("OLLAMA_ENERGY_TIMEOUT", "600"))

LABEL_MEASURED = "MEASURED"
LABEL_BOUNDED = "MEASURED_SHARED_BOUNDED"
LABEL_UNAVAILABLE = "UNAVAILABLE"


def _default_out_path() -> str:
    return os.environ.get(
        "OLLAMA_ENERGY_JSON",
        os.path.join(os.path.expanduser("~"), ".a11oy_ollama_energy.json"),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# NVML capability probe. Decides counter-delta vs power-integral vs UNAVAILABLE.
# ---------------------------------------------------------------------------
class _Nvml:
    """Thin honest wrapper over pynvml. Never fabricates: if init or a read fails,
    the caller falls back or emits UNAVAILABLE — no synthetic numbers."""

    def __init__(self, index: int):
        self.ok = False
        self.energy_counter = False
        self.name = None
        self.reason = None
        self._pynvml = None
        self._handle = None
        try:
            import pynvml
        except Exception as e:  # noqa: BLE001 — no pynvml => honest UNAVAILABLE
            self.reason = f"pynvml import failed: {type(e).__name__}"
            return
        try:
            pynvml.nvmlInit()
        except Exception as e:  # noqa: BLE001 — no driver => honest UNAVAILABLE
            self.reason = f"nvmlInit failed: {type(e).__name__}"
            return
        self._pynvml = pynvml
        try:
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            raw = pynvml.nvmlDeviceGetName(self._handle)
            self.name = raw.decode() if isinstance(raw, bytes) else str(raw)
        except Exception as e:  # noqa: BLE001
            self.reason = f"handle/name failed: {type(e).__name__}"
            return
        # Pre-flight the Volta+ energy counter to decide MEASURED method honestly.
        try:
            pynvml.nvmlDeviceGetTotalEnergyConsumption(self._handle)
            self.energy_counter = True
        except Exception:  # noqa: BLE001 — NotSupported (pre-Volta) => power-integral
            self.energy_counter = False
        self.ok = True

    def energy_mj(self):
        """Cumulative on-die energy counter in millijoules (Volta+). None on failure."""
        try:
            return int(self._pynvml.nvmlDeviceGetTotalEnergyConsumption(self._handle))
        except Exception:  # noqa: BLE001
            return None

    def power_w(self):
        """Instantaneous board power in watts. None on failure."""
        try:
            return self._pynvml.nvmlDeviceGetPowerUsage(self._handle) / 1000.0  # mW -> W
        except Exception:  # noqa: BLE001
            return None

    def shutdown(self):
        try:
            if self._pynvml is not None:
                self._pynvml.nvmlShutdown()
        except Exception:  # noqa: BLE001
            pass


class _PowerIntegrator:
    """Background power poller + trapezoidal integral, for the pre-Volta fallback.
    Energy E = integral P dt approx sum (P_i + P_{i+1})/2 * (t_{i+1}-t_i)."""

    def __init__(self, nvml: "_Nvml", every_s: float = 0.05):
        self._nvml = nvml
        self._every = every_s
        self._stop = threading.Event()
        self._samples = []  # (t, power_w)
        self._thread = None

    def _run(self):
        while not self._stop.is_set():
            p = self._nvml.power_w()
            if p is not None:
                self._samples.append((time.perf_counter(), p))
            time.sleep(self._every)

    def start(self):
        self._samples = []
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop_and_integrate(self) -> float:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        s = self._samples
        if len(s) < 2:
            return 0.0
        joules = 0.0
        for (t0, p0), (t1, p1) in zip(s, s[1:]):
            joules += (p0 + p1) / 2.0 * (t1 - t0)
        return joules


def _sample_idle_watts(nvml: "_Nvml", seconds: float) -> float | None:
    """Average board power over `seconds` while Ollama is loaded but idle. None if
    no power reading was obtained (honest — no fabricated baseline)."""
    if seconds <= 0:
        return None
    vals = []
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        p = nvml.power_w()
        if p is not None:
            vals.append(p)
        time.sleep(0.1)
    return (sum(vals) / len(vals)) if vals else None


# ---------------------------------------------------------------------------
# The one measured Ollama call, bracketed by the NVML read.
# ---------------------------------------------------------------------------
def _ollama_generate(model: str, prompt: str, timeout: float) -> dict:
    """POST /api/generate {stream:false}. The blocking response IS the sync boundary
    (measuring process has no CUDA context, so no cuda-sync needed). Returns the
    parsed response dict (with eval_count etc.). Raises on transport/HTTP error."""
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        OLLAMA_URL + "/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — local Ollama
        return json.loads(r.read().decode("utf-8", "replace"))


def measure_once(model: str = None, prompt: str = None) -> dict:
    """Measure ONE real Ollama inference's GPU energy. Returns a reading dict written
    verbatim to the output JSON. Honest by construction: energy is null + label
    UNAVAILABLE when NVML cannot read; joules_per_token is null when output tokens
    are unknown."""
    model = model or OLLAMA_MODEL
    prompt = prompt or OLLAMA_ENERGY_PROMPT
    nvml = _Nvml(GPU_INDEX)

    reading = {
        "model": model,
        "ts": time.time(),
        "ts_iso": _now_iso(),
        "gpu_index": GPU_INDEX,
        "gpu_name": nvml.name,
        "exclusive": bool(GPU_EXCLUSIVE),
        "energy_joules": None,
        "energy_joules_idle_subtracted": None,
        "duration_s": None,
        "output_tokens": None,
        "joules_per_token": None,
        "avg_watts": None,
        "idle_watts": None,
        "measurement_method": None,
        "label": LABEL_UNAVAILABLE,
        "source": None,
    }

    if not nvml.ok:
        # No NVML — emit NO number. Honest UNAVAILABLE (doctrine v11).
        reading["note"] = f"NVML unavailable ({nvml.reason}) — energy NOT fabricated"
        return reading

    # Choose the honest label up front: exclusivity asserted => clean MEASURED, else BOUNDED.
    label = LABEL_MEASURED if GPU_EXCLUSIVE else LABEL_BOUNDED

    # Optional idle baseline while Ollama is loaded-but-idle (before the request).
    idle_watts = _sample_idle_watts(nvml, IDLE_SAMPLE_S)

    try:
        if nvml.energy_counter:
            method = "counter-delta"
            source = "pynvml.nvmlDeviceGetTotalEnergyConsumption"
            e0 = nvml.energy_mj()
            t0 = time.perf_counter()
            resp = _ollama_generate(model, prompt, GENERATE_TIMEOUT_S)
            t1 = time.perf_counter()
            e1 = nvml.energy_mj()
            if e0 is None or e1 is None:
                reading["note"] = "energy counter read failed mid-window — energy NOT fabricated"
                return reading
            energy_joules = (e1 - e0) / 1000.0  # mJ -> J
        else:
            method = "power-integral"
            source = "pynvml.nvmlDeviceGetPowerUsage (trapezoidal integral)"
            integ = _PowerIntegrator(nvml)
            integ.start()
            t0 = time.perf_counter()
            resp = _ollama_generate(model, prompt, GENERATE_TIMEOUT_S)
            t1 = time.perf_counter()
            energy_joules = integ.stop_and_integrate()
    except Exception as e:  # noqa: BLE001 — Ollama down/failed => honest, no fake number
        reading["note"] = f"ollama generate failed ({type(e).__name__}) — energy NOT fabricated"
        return reading
    finally:
        nvml.shutdown()

    duration_s = t1 - t0
    output_tokens = resp.get("eval_count")
    jpt = (energy_joules / output_tokens) if (output_tokens and output_tokens > 0) else None
    avg_watts = (energy_joules / duration_s) if duration_s > 0 else None
    net = None
    if idle_watts is not None:
        net = energy_joules - idle_watts * duration_s
        net = net if net > 0 else 0.0

    reading.update({
        "energy_joules": round(energy_joules, 6),
        "energy_joules_idle_subtracted": (round(net, 6) if net is not None else None),
        "duration_s": round(duration_s, 6),
        "output_tokens": output_tokens,
        "joules_per_token": (round(jpt, 8) if jpt is not None else None),
        "avg_watts": (round(avg_watts, 4) if avg_watts is not None else None),
        "idle_watts": (round(idle_watts, 4) if idle_watts is not None else None),
        "measurement_method": method,
        "label": label,
        "source": source,
        "note": (
            "GPU energy MEASURED via %s; label=%s (exclusive=%s). NVML counts the whole "
            "GPU, not one process." % (source, label, GPU_EXCLUSIVE)
        ),
    })
    return reading


def _write(reading: dict, path: str):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reading, f, indent=2)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description="Measure real per-inference GPU energy for a local Ollama model.")
    ap.add_argument("--once", action="store_true", help="take a single reading and exit")
    ap.add_argument("--loop", type=float, metavar="N", help="refresh every N seconds")
    ap.add_argument("--model", default=None, help="Ollama model tag (default OLLAMA_MODEL)")
    ap.add_argument("--prompt", default=None, help="probe prompt (default OLLAMA_ENERGY_PROMPT)")
    ap.add_argument("--out", default=_default_out_path(), help="output JSON path (default OLLAMA_ENERGY_JSON)")
    args = ap.parse_args()

    def _tick():
        reading = measure_once(args.model, args.prompt)
        _write(reading, args.out)
        print("[ollama-energy-probe] %s label=%s j/token=%s -> %s" % (
            reading.get("model"), reading.get("label"),
            reading.get("joules_per_token"), args.out))
        return reading

    if args.loop:
        print("[ollama-energy-probe] loop every %.1fs, out=%s" % (args.loop, args.out))
        while True:
            try:
                _tick()
            except Exception as e:  # noqa: BLE001 — never let the loop die on one error
                print("[ollama-energy-probe] tick error: %s" % (type(e).__name__,))
            time.sleep(max(1.0, args.loop))
    else:
        # default (and --once) => single reading
        _tick()


if __name__ == "__main__":
    main()
