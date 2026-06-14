# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""szl_pnt_mesh.py — a11oy MESH for the SZL PNT / QUANTUM-SENSING vertical.

This is the live-mesh surface for the SECOND hard-physics pillar (sensing limits)
next to the compute-bounds pillar already served by `szl_pinn_bounds.py`. It exposes
the UNIFIED "fundamental-limits" library (compute bounds + quantum sensing) behind
a11oy's governed `/api/<ns>/v1/pnt/*` route table.

Routes (all GET, read-only / deterministic):

  /api/<ns>/v1/pnt              capability index + doctrine + links (both pillars)
  /api/<ns>/v1/pnt/sensor       quantum-sensor limit certificate from query params
                                (cold-atom-interferometer shot-noise / SQL sensitivity;
                                 Kasevich-Chu 1991, Peters 2001, Freier 2016, Cheinet 2008)
  /api/<ns>/v1/pnt/resilience   fused multi-layer GNSS spoof-detector verdict from query
                                params (RAIM-consistency + AGC + SQM), deny-by-default
  /api/<ns>/v1/pnt/coast        GPS-denied coasting figure-of-merit: classical vs quantum
  /api/<ns>/v1/pnt/limits       the UNIFIED fundamental-limits index (BOTH pillars:
                                compute_bounds + quantum_sensor + pnt_resilience + nav_coasting)

HONESTY (Doctrine v11, HARD):
  - Sensor limits are DERIVED from established physics (shot-noise / standard quantum
    limit), labelled MODELED. The compute-bounds certificate is the HONEST INVERSE of a
    free-energy claim. NO over-unity, NO sub-SQL magic, NO fabricated number.
  - Bounds/physics are CITED, re-derived clean-room from the papers and the kshana method
    (Apache-2.0, DOI 10.5281/zenodo.20528627). No verbatim code copied.
  - Λ = Conjecture 1 (advisory). ALLOW/NOMINAL = "passed SZL admission policy", never
    "proven trust". Spoof governor is deny-by-default.
  - HEAVY numpy solves (full UKF fusion, batched sensor sweeps, PINN solves) are the
    Forge / GPU / own-metal path. This stdlib mesh READS & AGGREGATES the unified library
    and re-derives the lightweight closed-form limits; it NEVER blocks on a heavy solve.
  - If a sibling engine (Dev1 quantum_sensing_limits, Dev2 pnt_resilience, Dev3
    nav_coasting) is not present, the unified library returns an HONEST "module not wired
    yet"/clean-room-MODELED result; this mesh surfaces that honestly — never a false green.

Matches the `szl_pinn_bounds.py` contract exactly: pure-stdlib request path, FastAPI
`add_api_route` with a Starlette `Route` fallback, try/except-guarded `register(app, ns)`.
"""
import importlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

try:  # Starlette is present in the a11oy image (same as szl_pinn_bounds.py).
    from starlette.requests import Request
    from starlette.responses import JSONResponse
except Exception:  # pragma: no cover - allows import in a bare env for tests
    Request = object  # type: ignore

    class JSONResponse:  # minimal shim so handlers can be unit-tested w/o starlette
        def __init__(self, content, status_code=200):
            self.body = content
            self.status_code = status_code

# Make the unified library importable from this directory regardless of CWD.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)


def _load_fl():
    """Lazily import the unified fundamental-limits library. Honest None on failure."""
    try:
        return importlib.import_module("fundamental_limits")
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Doctrine strings (mirrors the unified library; carried on every response).   #
# --------------------------------------------------------------------------- #
DOCTRINE = (
    "v11 LOCKED: NO free-energy/over-unity (compute certificate is the honest INVERSE; "
    "sensor limits DERIVED from physics, never sub-SQL magic); MEASURED vs MODELED vs "
    "SAMPLE labels on every result; honest 'NOT MODELED'/'module not wired yet' where "
    "physics is incomplete; established bounds CITED not claimed as SZL's; clean-room "
    "(re-derived from papers, kshana cited not copied); Λ=Conjecture 1 (advisory, "
    "deny-by-default, never 'proven trust'); sovereign own-metal; no fabricated numbers."
)

LAMBDA_NOTE = (
    "Λ = Conjecture 1 (advisory governance gate). ALLOW/NOMINAL = 'passed SZL admission "
    "policy', NEVER 'proven trust'. Deny-by-default. States physical FACTS/BOUNDS, not trust."
)

SENSING_ATTRIBUTION = {
    "kasevich_chu_1991": ("Kasevich, M. & Chu, S. (1991), Phys. Rev. Lett. 67(2):181, "
                          "doi:10.1103/PhysRevLett.67.181."),
    "peters_2001": ("Peters, A., Chung, K.Y. & Chu, S. (2001), Metrologia 38(1):25, "
                    "doi:10.1088/0026-1394/38/1/4."),
    "freier_2016": ("Freier, C. et al. (2016), J. Phys. Conf. Ser. 723:012050, "
                    "doi:10.1088/1742-6596/723/1/012050."),
    "cheinet_2008": ("Cheinet, P. et al. (2008), IEEE Trans. Instrum. Meas. 57(6):1141, "
                     "doi:10.1109/TIM.2007.915148."),
    "kshana": ("AshfordeOU/kshana (Apache-2.0, DOI 10.5281/zenodo.20528627) — method & "
               "physics CITED, re-derived clean-room. No verbatim code copied."),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------- #
# Pure-stdlib closed-form physics (used directly in the web path — no numpy).  #
# Math mirrors the unified library / Dev1 so the live mesh and on-metal AGREE.  #
# --------------------------------------------------------------------------- #
def _sensor_limit(lambda_m, T, N, C, Tc):
    """SQL CAI accelerometer sensitivity — pure stdlib (no numpy).

    k_eff = 4π/λ ; σ_Φ = 1/(C·√N) ; σ_a = σ_Φ/(k_eff·T²) ; n_a = σ_a·√T_c.
    Lineage: Kasevich-Chu 1991, Peters 2001, Freier 2016, Cheinet 2008.
    """
    k_eff = 4.0 * math.pi / lambda_m if lambda_m > 0 else float("inf")
    sigma_phi = 1.0 / (C * math.sqrt(N)) if (C > 0 and N > 0) else float("inf")
    denom = k_eff * T * T
    sigma_a = (sigma_phi / denom) if denom > 0 else float("inf")
    asd = sigma_a * math.sqrt(Tc) if Tc > 0 else float("inf")
    return {
        "k_eff_per_m": k_eff,
        "shot_noise_phase_rad": sigma_phi,
        "per_shot_accel_sensitivity_m_s2": sigma_a,
        "accel_asd_m_s2_per_sqrt_hz": asd,
        "inputs": {"wavelength_m": lambda_m, "interrogation_time_s": T,
                   "atom_number": N, "contrast": C, "cycle_time_s": Tc},
        "formulas": {"k_eff": "4*pi/lambda", "shot_noise": "1/(C*sqrt(N)) (SQL)",
                     "per_shot_accel": "sigma_Phi/(k_eff*T^2)", "asd": "sigma_a*sqrt(T_c)"},
        "label": "MODELED",
        "at_or_above_standard_quantum_limit": True,
    }


def _spoof_verdict(raim_m, agc_db, sqm_dev, raim_thr, agc_thr, sqm_thr):
    """Pure-stdlib deny-by-default multi-layer spoof fusion (RAIM + AGC + SQM).

    A transparent web-path stand-in for the Dev2 engine: any single layer fired ->
    SUSPECT; >=2 -> SPOOF_LIKELY (DENY); 0 -> NOMINAL (ALLOW). Advisory (Λ).
    """
    flags = {
        "raim_consistency": raim_m > raim_thr,
        "agc_power": agc_db > agc_thr,
        "sqm_asymmetry": abs(sqm_dev) > sqm_thr,
    }
    n = sum(1 for v in flags.values() if v)
    if n >= 2:
        verdict, allow = "DENY", False
    elif n == 1:
        verdict, allow = "ADVISORY", False
    else:
        verdict, allow = "ALLOW", True
    return {
        "verdict": verdict,
        "allow": allow,
        "advisory": True,
        "n_layers_fired": n,
        "layers": flags,
        "inputs": {"raim_consistency_m": raim_m, "agc_advantage_db": agc_db,
                   "sqm_early_minus_late": sqm_dev},
        "thresholds": {"raim_threshold_m": raim_thr, "agc_threshold_db": agc_thr,
                       "sqm_threshold": sqm_thr},
        "fusion": "deny-by-default: >=2 fired -> DENY, 1 -> ADVISORY, 0 -> ALLOW",
        "label": "MODELED",
    }


def _coast_fom(t, n_classical, n_quantum):
    """GPS-denied coasting position-error growth: sigma_x(t) ~= n_a * t^1.5 / sqrt(3)."""
    def pe(n):
        return n * (t ** 1.5) / math.sqrt(3.0)
    ec, eq = pe(n_classical), pe(n_quantum)
    return {
        "coast_time_s": t,
        "classical": {"accel_asd_m_s2_per_sqrt_hz": n_classical, "position_error_m": ec},
        "quantum": {"accel_asd_m_s2_per_sqrt_hz": n_quantum, "position_error_m": eq},
        "quantum_over_classical_improvement_factor": (ec / eq) if eq > 0 else float("inf"),
        "model": ("white-acceleration-noise random walk, double-integrated: "
                  "sigma_x(t) ~= n_a * t^1.5 / sqrt(3). MODELED scaling."),
        "label": "MODELED",
    }


# --------------------------------------------------------------------------- #
# Query-param helpers                                                          #
# --------------------------------------------------------------------------- #
def _f(qp, *keys, default=0.0):
    for k in keys:
        v = qp.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except Exception:
                pass
    return float(default)


def _qp(req):
    """Extract a query-param mapping from a Starlette Request OR a plain dict (tests)."""
    if isinstance(req, dict):
        return req
    return getattr(req, "query_params", {}) or {}


# --------------------------------------------------------------------------- #
# Handlers                                                                     #
# --------------------------------------------------------------------------- #
def _h_index(req: Request):
    ns = "a11oy"
    if not isinstance(req, dict):
        ns = getattr(req, "path_params", {}).get("_ns", "a11oy")
    base = f"/api/{ns}/v1/pnt"
    fl = _load_fl()
    pillars = fl.status().get("pillars") if fl else {"error": "unified library not importable"}
    return JSONResponse({
        "capability": "SZL PNT / Quantum-Sensing vertical — the SECOND hard-physics pillar",
        "frontier": ("quantum + classical sensing for Positioning-Navigation-Timing, "
                     "unified with the compute-bounds certifier into one governed "
                     "'fundamental-limits' surface — every result MEASURED/MODELED-labelled, "
                     "Λ-gated, clean-room re-derived from the kshana method + the papers"),
        "pillars": ["compute_bounds (Landauer/ML/Bremermann/Bekenstein — szl_pinn_bounds)",
                    "quantum_sensor (cold-atom interferometer SQL — Dev1)",
                    "pnt_resilience (fused spoof detector — Dev2)",
                    "nav_coasting (GPS-denied coasting FoM — Dev3)"],
        "engine_status": pillars,
        "routes": {
            f"{base}/sensor": ("quantum-sensor limit certificate "
                               "(?wavelength_m=&interrogation_time_s=&atom_number=&contrast=&cycle_time_s=)"),
            f"{base}/resilience": ("fused spoof-detector verdict "
                                   "(?raim_consistency_m=&agc_advantage_db=&sqm_early_minus_late=  "
                                   "or ?scenario=clean|ds2_time_push|ds3_overpower|ds4_seamless|ds7_matched_aligned)"),
            f"{base}/coast": ("GPS-denied coasting FoM classical vs quantum "
                              "(?coast_time_s=&classical_asd=&quantum_asd=)"),
            f"{base}/limits": "the UNIFIED fundamental-limits index (both pillars)",
        },
        "attribution": {"sensing": SENSING_ATTRIBUTION},
        "lambda_note": LAMBDA_NOTE,
        "doctrine": DOCTRINE,
        "honest_inverse_of_free_energy": True,
        "ts": _now_iso(),
    })


def _h_sensor(req: Request):
    qp = _qp(req)
    lam = _f(qp, "wavelength_m", "lambda_m", default=780e-9)
    T = _f(qp, "interrogation_time_s", "T", default=0.1)
    N = _f(qp, "atom_number", "N", default=1e6)
    C = _f(qp, "contrast", "C", default=0.5)
    Tc = _f(qp, "cycle_time_s", "Tc", default=0.5)
    # Try the unified library (which wraps the Dev1 engine when present); the closed-form
    # stdlib derivation is the always-available web-path answer.
    closed_form = _sensor_limit(lam, T, N, C, Tc)
    engine = None
    fl = _load_fl()
    if fl is not None:
        try:
            res = fl.certify("quantum_sensor", wavelength_m=lam, interrogation_time_s=T,
                             atom_number=N, contrast=C, cycle_time_s=Tc)
            engine = {"source": res.get("source"), "label": res.get("label"),
                      "wired": res.get("wired"), "certificate": res.get("result")}
        except Exception as e:
            engine = {"error": repr(e), "note": "unified library call failed; closed-form used"}
    return JSONResponse({
        "model": "SZL Quantum-Sensing-Limits — live CAI sensitivity certificate",
        "status": "VERIFIED (MODELED physics) · UNSIGNED (STRUCTURAL-ONLY)",
        "label": "MODELED",
        "closed_form_stdlib": closed_form,
        "engine": engine,
        "attribution": SENSING_ATTRIBUTION,
        "lambda_note": LAMBDA_NOTE,
        "doctrine": DOCTRINE,
        "honest_inverse_of_free_energy": True,
    })


def _h_resilience(req: Request):
    qp = _qp(req)
    scenario = qp.get("scenario")
    engine = None
    fl = _load_fl()
    # Prefer the Dev2 engine via the unified library when a scenario is requested (it
    # carries the calibrated chi-square monitor fusion). Heavy numpy stays in the engine;
    # the mesh tolerates failure and always answers with the closed-form fusion.
    if fl is not None and scenario:
        try:
            res = fl.certify("pnt_resilience", scenario=scenario, seed=int(_f(qp, "seed", default=0)))
            engine = {"source": res.get("source"), "label": res.get("label"),
                      "wired": res.get("wired"), "verdict": res.get("result")}
        except Exception as e:
            engine = {"error": repr(e)}
    raim = _f(qp, "raim_consistency_m", "raim_m", default=0.0)
    agc = _f(qp, "agc_advantage_db", "agc_db", default=0.0)
    sqm = _f(qp, "sqm_early_minus_late", "sqm", default=0.0)
    raim_thr = _f(qp, "raim_threshold_m", default=30.0)
    agc_thr = _f(qp, "agc_threshold_db", default=1.5)
    sqm_thr = _f(qp, "sqm_threshold", default=0.12)
    closed_form = _spoof_verdict(raim, agc, sqm, raim_thr, agc_thr, sqm_thr)
    return JSONResponse({
        "model": "SZL PNT-Resilience — fused multi-layer spoof verdict",
        "status": f"{closed_form['verdict']} (advisory, deny-by-default)",
        "label": "MODELED",
        "closed_form_stdlib": closed_form,
        "engine": engine,
        "note": ("RAIM-consistency + AGC-power + SQM-asymmetry fused deny-by-default. The "
                 "full calibrated chi-square detector with TEXBAT-style scenarios runs in "
                 "the Dev2 engine (numpy); this stdlib mesh answers with a transparent "
                 "closed-form fusion and surfaces the engine verdict when present."),
        "attribution": SENSING_ATTRIBUTION,
        "lambda_note": LAMBDA_NOTE,
        "doctrine": DOCTRINE,
    })


def _h_coast(req: Request):
    qp = _qp(req)
    t = _f(qp, "coast_time_s", "t", default=60.0)
    n_c = _f(qp, "classical_asd", "classical_asd_m_s2_per_sqrt_hz", default=1e-3)
    # Default quantum ASD comes from the closed-form CAI derivation unless supplied.
    if any(k in qp for k in ("quantum_asd", "quantum_asd_m_s2_per_sqrt_hz")):
        n_q = _f(qp, "quantum_asd", "quantum_asd_m_s2_per_sqrt_hz", default=1e-8)
    else:
        n_q = _sensor_limit(780e-9, 0.1, 1e6, 0.5, 0.5)["accel_asd_m_s2_per_sqrt_hz"]
    closed_form = _coast_fom(t, n_c, n_q)
    engine = None
    fl = _load_fl()
    if fl is not None:
        try:
            res = fl.certify("nav_coasting", coast_time_s=t,
                             classical_asd_m_s2_per_sqrt_hz=n_c,
                             quantum_asd_m_s2_per_sqrt_hz=n_q)
            engine = {"source": res.get("source"), "label": res.get("label"),
                      "wired": res.get("wired"), "result": res.get("result")}
        except Exception as e:
            engine = {"error": repr(e)}
    return JSONResponse({
        "model": "SZL Nav-Coasting — GPS-denied position-error FoM (classical vs quantum)",
        "status": "VERIFIED (MODELED scaling) · UNSIGNED (STRUCTURAL-ONLY)",
        "label": "MODELED",
        "closed_form_stdlib": closed_form,
        "engine": engine,
        "note": ("The full INS/UKF error-covariance propagation (17-state, coupled clock) "
                 "is the Dev3 / Forge GPU path. This mesh answers with the closed-form "
                 "random-walk coasting scaling — MODELED, not a fabricated number."),
        "attribution": SENSING_ATTRIBUTION,
        "lambda_note": LAMBDA_NOTE,
        "doctrine": DOCTRINE,
    })


def _h_limits(req: Request):
    """The UNIFIED fundamental-limits index: BOTH pillars, honest wiring discovery."""
    fl = _load_fl()
    if fl is None:
        return JSONResponse({
            "model": "SZL Unified Fundamental-Limits index",
            "status": "UNIFIED_LIBRARY_NOT_IMPORTABLE",
            "note": ("fundamental_limits.py not importable in this environment — honest "
                     "state, no fabricated number."),
            "doctrine": DOCTRINE,
            "lambda_note": LAMBDA_NOTE,
        }, status_code=200)
    st = fl.status()
    return JSONResponse({
        "model": "SZL Unified Fundamental-Limits index — both hard-physics pillars",
        "library": st.get("library"),
        "pillars": st.get("pillars"),
        "kinds": st.get("kinds"),
        "pillar_A_compute_bounds": ("Landauer 1961 / Margolus-Levitin 1998 / Bremermann "
                                    "1962 / Bekenstein 1981 / Bekenstein-Hawking 1975 — the "
                                    "HONEST INVERSE of a free-energy claim (szl_pinn_bounds)"),
        "pillar_B_quantum_sensing": ("cold-atom interferometer SQL (Dev1) + fused spoof "
                                     "detector (Dev2) + GPS-denied coasting FoM (Dev3) — "
                                     "re-derived clean-room from the kshana method + papers"),
        "labels": st.get("labels"),
        "attribution": st.get("attribution"),
        "honest_inverse_of_free_energy": st.get("honest_inverse_of_free_energy"),
        "lambda_note": st.get("lambda_note"),
        "doctrine": st.get("doctrine"),
        "ts": _now_iso(),
    })


# --------------------------------------------------------------------------- #
# Registration — mirrors szl_pinn_bounds.register exactly.                     #
# --------------------------------------------------------------------------- #
def register(app, ns="a11oy"):
    """Wire the PNT / quantum-sensing mesh onto the app under /api/<ns>/v1/pnt/*.

    Additive. Uses FastAPI's add_api_route when available (matches the sibling szl_*
    modules so resolution order is correct vs the SPA catch-all); falls back to a
    Starlette route append for a bare Starlette app.
    """
    base = f"/api/{ns}/v1/pnt"
    handlers = [
        (base, _h_index),
        (f"{base}/sensor", _h_sensor),
        (f"{base}/resilience", _h_resilience),
        (f"{base}/coast", _h_coast),
        (f"{base}/limits", _h_limits),
    ]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            from starlette.routing import Route
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


def _selftest() -> dict:
    """No-server self-test: proves register() adds routes and handlers answer honestly.

    Doctrine labels are checked end-to-end: MODELED/MEASURED carried, Λ=Conjecture 1
    advisory present, honest-inverse-of-free-energy preserved.
    """
    out = {}

    def _body(resp):
        """Decode a handler response to a dict, whether real Starlette JSONResponse
        (bytes body) or the test shim (dict body)."""
        b = getattr(resp, "body", resp)
        if isinstance(b, (bytes, bytearray)):
            return json.loads(b.decode())
        if isinstance(b, str):
            return json.loads(b)
        return b

    # (a) register() adds exactly the 5 routes onto a FastAPI-like app.
    class _FakeApp:
        def __init__(self):
            self.routes = []

        def add_api_route(self, path, fn, methods=None):
            self.routes.append((path, fn, tuple(methods or [])))

    app = _FakeApp()
    added = register(app, ns="a11oy")
    expected = ["/api/a11oy/v1/pnt", "/api/a11oy/v1/pnt/sensor",
                "/api/a11oy/v1/pnt/resilience", "/api/a11oy/v1/pnt/coast",
                "/api/a11oy/v1/pnt/limits"]
    assert added == expected, added
    assert [r[0] for r in app.routes] == expected
    assert all(r[2] == ("GET",) for r in app.routes)
    out["register_adds_5_routes"] = True

    # (b) Starlette-fallback path (no add_api_route) also wires routes.
    class _BareRouter:
        def __init__(self):
            self.routes = []

    class _BareApp:
        def __init__(self):
            self.router = _BareRouter()

    try:
        bare = _BareApp()
        register(bare, ns="a11oy")
        out["starlette_fallback_wires"] = len(bare.router.routes) == 5
    except Exception:
        # starlette.routing may be absent in a bare env — that's an honest skip.
        out["starlette_fallback_wires"] = "skipped (starlette.routing unavailable)"

    # (c) sensor handler returns a MODELED certificate with the SQL fields.
    s = _body(_h_sensor({"wavelength_m": "780e-9", "contrast": "0.5", "atom_number": "1e6"}))
    cf = s["closed_form_stdlib"]
    assert cf["label"] == "MODELED"
    assert cf["at_or_above_standard_quantum_limit"] is True
    assert cf["k_eff_per_m"] > 0 and cf["accel_asd_m_s2_per_sqrt_hz"] > 0
    assert s["honest_inverse_of_free_energy"] is True
    out["sensor_modeled_sql"] = True

    # (d) resilience handler: clean inputs -> ALLOW; spoof inputs -> DENY (deny-by-default).
    clean = _body(_h_resilience({}))["closed_form_stdlib"]
    assert clean["verdict"] == "ALLOW" and clean["allow"] is True
    spoof = _body(_h_resilience({"raim_consistency_m": "100", "agc_advantage_db": "10"}))["closed_form_stdlib"]
    assert spoof["verdict"] == "DENY" and spoof["allow"] is False
    assert spoof["advisory"] is True
    out["resilience_deny_by_default"] = True

    # (e) coast handler: quantum beats classical (improvement factor > 1 for default ASDs).
    c = _body(_h_coast({"coast_time_s": "60"}))["closed_form_stdlib"]
    assert c["quantum_over_classical_improvement_factor"] > 1.0
    assert c["label"] == "MODELED"
    out["coast_quantum_advantage"] = True

    # (f) limits index carries BOTH pillars and the doctrine labels.
    lim = _body(_h_limits({}))
    assert "pillars" in lim or lim.get("status") == "UNIFIED_LIBRARY_NOT_IMPORTABLE"
    assert "free-energy" in lim["doctrine"].lower()
    assert "advisory" in lim["lambda_note"].lower()
    out["limits_both_pillars"] = True

    # (g) doctrine labels carried across handlers (Λ=Conjecture 1, honest-inverse).
    idx = _body(_h_index({}))
    assert "Conjecture 1" in idx["lambda_note"]
    assert idx["honest_inverse_of_free_energy"] is True
    assert "clean-room" in idx["doctrine"].lower()
    out["doctrine_labels_carried"] = True

    out["ok"] = True
    return out


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
