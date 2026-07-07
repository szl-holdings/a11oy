#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
#
# szl_governed_ipinn.py — Governed wrapper + HTTP surface for the SZL Inverse-PINN
# engine (szl_pinn_inverse). Taxonomy: services (frontier discovery) + provenance.
#
# Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Lambda = Conjecture 1 (advisory).
#
# WHAT THIS ADDS over the bare engine
#   1. governed_discover(spec): runs the engine and returns, PER discovered
#      parameter: value, 95% CI, a three-state convergence label (GREEN/YELLOW/
#      RED) with the EXACT numeric criteria, the physics residual, and a
#      Bekenstein/F19 information-cost ratio (PHYSICALLY_PLAUSIBLE / IMPLAUSIBLE).
#      A parameter the data cannot identify is RED/UNIDENTIFIABLE and the engine
#      REFUSES to assert a value for it (value withheld, reason given).
#   2. A Lambda advisory (Conjecture 1) in [0, 0.99] — NEVER 1.0.
#   3. A DSSE-signable receipt dict (organ="a11oy-pinn"); signed with the real
#      cosign key when present, otherwise an HONEST UNSIGNED envelope (never a
#      fabricated signature). The ledger write itself is NOT done here — we call
#      record_pinn_receipt(receipt), a no-op-safe hook that Dev C wires to
#      szl_lake_ingest.record_receipt.
#   4. POST /api/a11oy/v1/pinn/identify — the endpoint. A built-in demo
#      ("demo":"duffing") returns a real GREEN alpha ~ 1.0 out of the box.
#
# HONEST LABELS: all discovered values are MODELED (a fit to data), never
#   MEASURED. F19 (Bekenstein bound) is one of the 8 locked-proven inequalities
#   {F1,F4,F7,F11,F12,F18,F19,F22}@c7c0ba17 — a PROVEN inequality, never an
#   assertion; its APPLICATION to an information-cost ratio here is MODELED.
#   The locked-proven count is 8. Lambda = Conjecture 1. No user-visible codenames.

import math
import time
import json

import numpy as np

from szl_pinn_inverse import (
    SZLInversePINN, SZLInversePINNTrainer, SZLSpectralSurrogate,
    duffing_residual, integrate_duffing,
    CAUSAL_GREEN, CAUSAL_RED, GRAD_GREEN, KAPPA_IDENT, KAPPA_RED, FISHER_FLOOR,
    MIN_DATA_POINTS,
)

# Governed CALPHAD inverse-discovery system (materials-by-design vertical). Imported
# GUARDED: a failure here must NEVER break the live Duffing path — _CALPHAD stays
# None and the endpoint serves Duffing exactly as before.
try:
    import szl_calphad_inverse as _CALPHAD  # type: ignore
    _CALPHAD_KEYS = {"calphad", "redlich_kister", "redlich-kister", "rk"}
except Exception as _calphad_e:  # noqa: BLE001 — honest degrade, never fatal
    _CALPHAD = None
    _CALPHAD_KEYS = set()
    _CALPHAD_IMPORT_ERROR = repr(_calphad_e)

RECEIPT_SCHEMA = "szl.lake.receipt/v1"
RECEIPT_ORGAN = "a11oy-pinn"
RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.ipinn+json"
LOCKED_PROVEN = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
LOCKED_PROVEN_AT = "c7c0ba17"

# Built-in, code-safe systems. We NEVER eval user-supplied residual source — a
# request selects a named built-in physics, or passes data to identify against
# one. (Security rule: no arbitrary code-as-action on this path.)
_BUILTIN_SYSTEMS = {
    "duffing": {
        "residual": duffing_residual,
        "unknowns": ["alpha"],
        "linear": ["alpha"],
        "bounds": {"alpha": (-10.0, 10.0)},
        "inits": {"alpha": 0.4},
        "truth": {"alpha": 1.0},
        "desc": "Duffing oscillator m x'' + c x' + delta x + alpha x^3 = F cos(omega t)",
    },
}


# ---------------------------------------------------------------------------
# Bekenstein / F19 information-cost ratio.
#   I_eta   = log2(sigma_prior / sigma_posterior)         bits of info gained
#   I_max   = 2*pi*R*E / (hbar*c) / ln(2)                 Bekenstein bound (bits)
#   ratio   = I_eta / I_max                               > 1 => IMPLAUSIBLE
# F19 is the PROVEN Bekenstein inequality (locked-8). The numbers below are a
# MODELED application with SAMPLE R, E unless the caller supplies real ones.
# ---------------------------------------------------------------------------
_HBAR = 1.054571817e-34   # J*s
_C = 2.99792458e8         # m/s


def bekenstein_ratio(sigma_prior, sigma_posterior, radius_m=1.0, energy_j=1.0):
    sp = max(float(sigma_prior), 1e-30)
    sq = max(float(sigma_posterior), 1e-30)
    info_bits = math.log2(sp / sq) if sp > sq else 0.0
    i_max = (2.0 * math.pi * float(radius_m) * float(energy_j)) / (_HBAR * _C) / math.log(2.0)
    ratio = info_bits / i_max if i_max > 0 else float("inf")
    return {
        "info_bits": info_bits,
        "bekenstein_max_bits": i_max,
        "ratio": ratio,
        "label": "PHYSICALLY_PLAUSIBLE" if ratio <= 1.0 else "PHYSICALLY_IMPLAUSIBLE",
        "radius_m": float(radius_m),
        "energy_j": float(energy_j),
        "basis": ("F19 Bekenstein bound = PROVEN inequality (locked-8 @ %s); "
                  "this application is MODELED with SAMPLE R,E unless supplied"
                  % LOCKED_PROVEN_AT),
    }


# ---------------------------------------------------------------------------
# Lambda advisory (Conjecture 1) — weighted geometric mean of honest factors,
# HARD-capped at 0.99. Never 1.0, never presented as proven.
# ---------------------------------------------------------------------------
def compute_lambda(label, frac_asserted, data_rms, delta_param_rel):
    f_label = {"GREEN": 0.9, "YELLOW": 0.6, "RED": 0.2}.get(label, 0.2)
    f_ident = 0.05 + 0.95 * float(np.clip(frac_asserted, 0.0, 1.0))
    f_data = float(np.clip(math.exp(-5.0 * max(data_rms, 0.0)), 0.05, 1.0))
    f_stab = float(np.clip(1.0 / (1.0 + max(delta_param_rel, 0.0)), 0.05, 1.0))
    geom = (f_label * f_ident * f_data * f_stab) ** 0.25
    return {
        "value": round(min(geom, 0.99), 4),
        "status": "ADVISORY",
        "basis": "Lambda = Conjecture 1 (advisory, capped <= 0.99; NEVER a proof)",
        "factors": {"label": f_label, "identifiable": round(f_ident, 4),
                    "data_fit": round(f_data, 4), "stability": round(f_stab, 4)},
    }


# ---------------------------------------------------------------------------
# JSON-safe coercion. Starlette's JSONResponse uses allow_nan=False, so a
# non-finite float (e.g. kappa(FIM)=inf — the honest non-identifiable signal)
# would 500 the response. We convert non-finite floats to honest string tokens
# and numpy scalars to plain Python, so the receipt and the wire agree.
# ---------------------------------------------------------------------------
def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float):
        if math.isinf(obj):
            return "Infinity" if obj > 0 else "-Infinity"
        if math.isnan(obj):
            return "NaN"
    return obj


# ---------------------------------------------------------------------------
# The no-op-safe ledger hook. Dev C wires this to szl_lake_ingest.record_receipt;
# until then (and when running standalone) it degrades honestly to not-recorded.
# ---------------------------------------------------------------------------
def record_pinn_receipt(receipt):
    """Hook for Dev C. Signature: record_pinn_receipt(receipt: dict) -> dict.
    Attempts an in-process ledger append via szl_lake_ingest.record_receipt with
    organ="a11oy-pinn"; never raises, returns a status dict."""
    try:
        import szl_lake_ingest  # type: ignore
        res = szl_lake_ingest.record_receipt(receipt, organ=RECEIPT_ORGAN)
        return {"recorded": True, "backend": "szl_lake_ingest.record_receipt",
                "result": res if isinstance(res, dict) else str(res)}
    except Exception as e:  # noqa: BLE001 — honest degrade, never fatal
        return {"recorded": False, "reason": "ledger hook not wired (%r)" % e,
                "note": "Dev C wires record_pinn_receipt -> szl_lake_ingest"}


def build_ipinn_receipt(system, method, params_block, convergence, lambda_adv, sign=True):
    payload = {
        "schema": RECEIPT_SCHEMA,
        "organ": RECEIPT_ORGAN,
        "kind": "inverse_pinn_identify",
        "ts": time.time(),
        "system": system,
        "method": method,
        "label_provenance": "MODELED (fit to data; not MEASURED)",
        "discovered": params_block,
        "convergence": convergence,
        "lambda_advisory": lambda_adv,
        "doctrine": {
            "locked_proven_count": 8,
            "locked_proven": list(LOCKED_PROVEN),
            "locked_at": LOCKED_PROVEN_AT,
            "lambda": "Conjecture 1",
            "f19": "Bekenstein bound = PROVEN inequality (locked-8); application MODELED",
        },
    }
    receipt = {"payload": payload}
    if sign:
        try:
            try:
                from szl_substrate import szl_dsse  # type: ignore  # single source of truth (pkg)
            except Exception:
                import szl_dsse  # type: ignore  # local vendored fallback (byte-identical)
            env = szl_dsse.sign_payload(payload, RECEIPT_PAYLOAD_TYPE)
            receipt["dsse"] = env
            receipt["signed"] = bool(env.get("signatures"))
        except Exception as e:  # noqa: BLE001
            receipt["dsse"] = {"signed": False,
                               "reason": "szl_dsse unavailable (%r)" % e}
            receipt["signed"] = False
    else:
        receipt["signed"] = False
    return receipt


# ---------------------------------------------------------------------------
# The governed discovery orchestrator.
# ---------------------------------------------------------------------------
def _coerce_data(spec):
    """Return (t, y, noise_sigma, system_key, used_demo). Either a built-in demo
    ('demo':'duffing') generating synthetic data, or caller-supplied
    {'data': {'t': [...], 'x': [...]}, 'system': 'duffing'}."""
    demo = spec.get("demo")
    system_key = (spec.get("system") or demo or "duffing")
    if isinstance(system_key, str):
        system_key = system_key.strip().lower()
    if system_key not in _BUILTIN_SYSTEMS:
        raise ValueError("unsupported system %r; supported: %s (or pass demo='duffing')"
                         % (system_key, list(_BUILTIN_SYSTEMS)))
    data = spec.get("data")
    if demo or not data:
        opts = spec.get("options") or {}
        n = int(opts.get("n_points", 160))
        n = max(MIN_DATA_POINTS, min(n, 600))
        t1 = float(opts.get("t_max", 10.0))
        t = np.linspace(0.0, t1, n)
        truth = _BUILTIN_SYSTEMS[system_key]["truth"]
        x = integrate_duffing(t, alpha=truth.get("alpha", 1.0))
        noise = float(opts.get("noise", 0.0))
        if noise > 0:
            x = x + np.random.default_rng(0).normal(0.0, noise, size=x.shape)
        return t, x, max(noise, 1e-3), system_key, True
    # caller-supplied data
    t = np.asarray(data["t"], float).reshape(-1)
    y = np.asarray(data.get("x", data.get("y")), float).reshape(-1)
    if t.shape[0] != y.shape[0]:
        raise ValueError("data.t and data.x must have equal length")
    return t, y, 1e-3, system_key, False


def _is_calphad_request(spec):
    if _CALPHAD is None:
        return False
    key = (spec.get("system") or spec.get("demo") or "")
    if isinstance(key, str) and key.strip().lower() in _CALPHAD_KEYS:
        return True
    return False


def governed_calphad_discover(spec):
    """Governed Redlich-Kister inverse-discovery. Rides the SAME receipt + honesty
    contract as Duffing: per-param 95% CI, FIM self-doubt gate (RED/REFUSE when a
    parameter is unidentifiable), convex-hull stability plausibility check, F19
    Bekenstein info-cost (APPLIED), Lambda advisory (<=0.99), signed receipt."""
    spec = dict(spec or {})
    opts = dict(spec.get("options") or {})
    case = spec.get("case") or opts.get("case") or "identifiable"

    data = spec.get("data")
    if data and not spec.get("demo"):
        try:
            x = np.asarray(data["x"], float).reshape(-1)
            h = np.asarray(data.get("h", data.get("H", data.get("y"))), float).reshape(-1)
        except (KeyError, TypeError, ValueError) as ce:
            return {"ok": False, "error": "calphad data needs {'x':[...], 'h':[...]} (%s)"
                    % ce, "honesty": _honesty()}
        if x.shape[0] != h.shape[0]:
            return {"ok": False, "error": "data.x and data.h must have equal length",
                    "honesty": _honesty()}
        order = int(opts.get("order", _CALPHAD.RK_SYSTEMS["redlich_kister"]["order"]))
        T = float(opts.get("T", _CALPHAD.RK_SYSTEMS["redlich_kister"]["T"]))
        truth = opts.get("truth")
        sigma = float(opts["noise"]) if opts.get("noise") else None
        desc = _CALPHAD.RK_SYSTEMS["redlich_kister"]["desc"]
        used_demo, data_label, case = False, "caller-supplied", "caller_data"
    else:
        x, h, sigma, truth, T, order, desc, used_demo, data_label, case = \
            _CALPHAD.make_calphad_data(case, opts)

    if x.shape[0] < MIN_DATA_POINTS:
        return {"ok": False,
                "error": "need >= %d data points (got %d)" % (MIN_DATA_POINTS, x.shape[0]),
                "honesty": _honesty()}

    try:
        res = _CALPHAD.solve_redlich_kister(x, h, order, sigma)
        ci = _CALPHAD.ensemble_ci_rk(x, h, order, sigma,
                                     n_restarts=int(opts.get("restarts", 24)))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "calphad solve failed: %r" % e,
                "honesty": _honesty()}

    blocks = _CALPHAD.param_results_rk(res, ci, truth=truth)
    min_fisher = float(np.min(res.fisher_diag)) if res.fisher_diag.size else 0.0
    norm_resid = res.data_rms / max(res.data_scale, 1e-9)
    label, crit = _CALPHAD.classify_calphad(res.kappa_fim, min_fisher, norm_resid)

    n_asserted = 0
    discovered = []
    for blk in blocks:
        k = int(blk["name"][1:])
        lo, hi = (-1e5, 1e5)
        sigma_prior = (hi - lo) / math.sqrt(12.0)
        sigma_post = (blk["std"] if blk["std"] and blk["std"] > 0
                      else max(abs(res.ci_high[k] - res.ci_low[k]) / 3.92, 1e-6))
        bek = bekenstein_ratio(sigma_prior, sigma_post,
                               radius_m=float(opts.get("radius_m", 1.0)),
                               energy_j=float(opts.get("energy_j", 1.0)))
        blk["bekenstein"] = bek
        blk["convergence_label"] = label if blk["asserted"] else "RED"
        if blk["asserted"]:
            n_asserted += 1
        discovered.append(blk)

    stability = _CALPHAD.convex_hull_stability(list(res.L), T)

    convergence = {
        "label": label,
        "criteria": crit,
        "kappa_fim": res.kappa_fim,
        "min_fisher": min_fisher,
        "normal_eq_residual": res.normal_eq_resid,
        "residual_rms": round(res.data_rms, 6),
        "normalised_data_rms": round(norm_resid, 6),
        "noise_sigma": round(res.sigma, 6),
        "n_points": int(x.shape[0]),
        "rk_order": int(order),
        "thresholds": {
            "kappa_ident": KAPPA_IDENT, "kappa_red": KAPPA_RED,
            "fisher_floor": FISHER_FLOOR,
        },
    }
    convergence = _json_safe(convergence)
    discovered = _json_safe(discovered)
    stability = _json_safe(stability)

    frac_asserted = n_asserted / max(1, len(blocks))
    lambda_adv = compute_lambda(label, frac_asserted, norm_resid, 0.0)
    method = {
        "engine": "szl_calphad_inverse.solve_redlich_kister",
        "model": "Redlich-Kister excess Gibbs energy G_xs = x(1-x) sum_k L_k (1-2x)^k",
        "param_solve": ("exact regularised least squares (linear-in-L_k) with EXACT "
                        "covariance sigma^2 (Phi^T Phi)^{-1} and EXACT FIM; FIM "
                        "self-doubt identifiability gate (same contract as Duffing)"),
        "uq": "analytic 95% CI + bootstrap-ensemble 95% credible interval",
        "stability_check": "convex-hull / common-tangent PLAUSIBILITY check (not a guarantee)",
        "data_label": data_label,
        "system": desc,
        "isothermal_T_kelvin": float(T),
        "citations": list(_CALPHAD.CALPHAD_CITATIONS),
        "case": case,
    }
    honesty = _honesty()
    honesty["calphad"] = (
        "MODELED fit to SYNTHETIC data in a governed-discovery DEMO. This is NOT a "
        "validated materials prediction and NOT the discovery of a real new alloy. "
        "Discovered L_k are MODELED with uncertainty; convex-hull stability is a "
        "PLAUSIBILITY check, not a guarantee. DO NOT OVERCLAIM.")

    sys_block = {"key": "redlich_kister", "desc": desc, "vertical": "materials-by-design"}
    receipt = build_ipinn_receipt(sys_block, method, discovered, convergence, lambda_adv,
                                  sign=bool(opts.get("sign", True)))
    receipt["payload"]["stability"] = stability
    ledger = record_pinn_receipt(receipt)

    return {
        "ok": True,
        "system": "redlich_kister",
        "vertical": "materials-by-design",
        "convergence": convergence,
        "discovered": discovered,
        "stability": stability,
        "lambda_advisory": lambda_adv,
        "receipt": receipt,
        "ledger": ledger,
        "method": method,
        "honesty": honesty,
    }


def governed_discover(spec):
    spec = dict(spec or {})
    if _is_calphad_request(spec):
        return governed_calphad_discover(spec)
    try:
        t, y, noise_sigma, system_key, used_demo = _coerce_data(spec)
    except (ValueError, KeyError, TypeError) as ce:
        return {"ok": False, "error": str(ce), "honesty": _honesty()}
    if t.shape[0] < MIN_DATA_POINTS:
        return {"ok": False,
                "error": "need >= %d data points (got %d)" % (MIN_DATA_POINTS, t.shape[0]),
                "honesty": _honesty()}
    sysdef = _BUILTIN_SYSTEMS[system_key]
    requested = spec.get("unknowns") or list(sysdef["unknowns"])
    # the residual only knows about its own params; unknowns not in the residual
    # (e.g. "ghost") are admitted on purpose so the self-doubt gate can REFUSE them.
    inits = dict(sysdef["inits"])
    bounds = dict(sysdef["bounds"])
    linear = list(sysdef["linear"])
    for nm in requested:
        if nm not in inits:
            inits[nm] = 0.4
            bounds.setdefault(nm, (-10.0, 10.0))
            linear.append(nm)   # treat unknowns as linear unless engine proves otherwise

    opts = spec.get("options") or {}
    n_modes = int(opts.get("n_modes", 24))
    epochs = int(opts.get("epochs", 50))
    restarts = int(opts.get("restarts", 6))

    surrogate = SZLSpectralSurrogate(n_modes=n_modes, poly_deg=3)
    model = SZLInversePINN(sysdef["residual"], {k: inits[k] for k in requested},
                           surrogate=surrogate, param_bounds=bounds,
                           linear_params=[k for k in linear if k in requested])
    trainer = SZLInversePINNTrainer(model, t, y, t, noise_sigma=noise_sigma, seed=1)
    try:
        record = trainer.fit(epochs=epochs)
    except ValueError as ve:
        return {"ok": False, "error": str(ve), "honesty": _honesty()}
    results = trainer.param_results(n_restarts=restarts, epochs=max(20, epochs // 2))

    # prior std per param (for the Bekenstein info-gain): uniform-prior std over bounds.
    discovered = []
    n_asserted = 0
    for pr in results:
        lo, hi = bounds.get(pr.name, (-10.0, 10.0))
        sigma_prior = (hi - lo) / math.sqrt(12.0) if math.isfinite(hi - lo) else 10.0
        sigma_post = pr.std if pr.std > 0 else max(abs(pr.ci_high - pr.ci_low) / 3.92, 1e-6)
        bek = bekenstein_ratio(sigma_prior, sigma_post,
                               radius_m=float(opts.get("radius_m", 1.0)),
                               energy_j=float(opts.get("energy_j", 1.0)))
        block = {
            "name": pr.name,
            "asserted": pr.asserted,
            "value": (round(pr.value, 6) if pr.asserted else None),
            "ci95": ([round(pr.ci_low, 6), round(pr.ci_high, 6)] if pr.asserted else None),
            "std": round(pr.std, 6),
            "fisher_information": pr.fisher,
            "identifiable": pr.identifiable,
            "convergence_label": record.label if pr.asserted else "RED",
            "bekenstein": bek,
            "label": "MODELED",
        }
        if not pr.asserted:
            if pr.fisher < FISHER_FLOOR:
                why = ("Fisher information %.2e is below the floor %.0e — the data carry "
                       "no information about this parameter" % (pr.fisher, FISHER_FLOOR))
            else:
                why = ("the FIM is ill-conditioned (kappa=%.2e >= %.0e) — the parameters "
                       "are jointly non-identifiable" % (record.kappa_fim, KAPPA_RED))
            block["refusal"] = ("UNIDENTIFIABLE: %s. The engine REFUSES to assert this "
                                "parameter." % why)
        else:
            n_asserted += 1
        discovered.append(block)

    frac_asserted = n_asserted / max(1, len(results))
    convergence = {
        "label": record.label,
        "criteria": record.criteria,
        "min_causal_weight": round(record.min_causal_weight, 6),
        "grad_norm": record.grad_norm,
        "kappa_fim": record.kappa_fim,
        "residual_rms": round(record.residual_rms, 6),
        "data_rms": round(record.data_rms, 6),
        "epochs_run": record.epochs_run,
        "thresholds": {
            "causal_green": CAUSAL_GREEN, "causal_red": CAUSAL_RED,
            "grad_green": GRAD_GREEN, "kappa_ident": KAPPA_IDENT, "kappa_red": KAPPA_RED,
        },
    }
    convergence = _json_safe(convergence)
    discovered = _json_safe(discovered)
    lambda_adv = compute_lambda(record.label, frac_asserted,
                                record.data_rms, record.delta_param_rel)
    method = {
        "engine": "szl_pinn_inverse.SZLInversePINN",
        "surrogate": "spectral basis (Fourier %d modes + poly deg 3), exact analytic "
                     "derivatives; NumPy-only (no torch/DeepXDE)" % n_modes,
        "param_solve": "exact least-squares for linear params; Adam GD on physics "
                       "residual for nonlinear; FIM identifiability self-doubt gate",
        "data_label": "MODELED synthetic (demo)" if used_demo else "caller-supplied",
        "system": sysdef["desc"],
    }
    receipt = build_ipinn_receipt({"key": system_key, "desc": sysdef["desc"]},
                                  method, discovered, convergence, lambda_adv,
                                  sign=bool(opts.get("sign", True)))
    ledger = record_pinn_receipt(receipt)

    return {
        "ok": True,
        "system": system_key,
        "convergence": convergence,
        "discovered": discovered,
        "lambda_advisory": lambda_adv,
        "receipt": receipt,
        "ledger": ledger,
        "method": method,
        "honesty": _honesty(),
    }


def _honesty():
    return {
        "values": "MODELED (fit to data; not MEASURED)",
        "locked_proven_count": 8,
        "locked_proven": list(LOCKED_PROVEN),
        "lambda": "Conjecture 1 (advisory, <= 0.99)",
        "f19": "Bekenstein bound = PROVEN inequality (locked-8); application MODELED",
        "self_doubt_gate": ("a non-identifiable parameter (Fisher < %.0e or kappa(FIM) "
                            ">= %.0e) is labelled RED/UNIDENTIFIABLE and NOT asserted"
                            % (FISHER_FLOOR, KAPPA_RED)),
    }


# ---------------------------------------------------------------------------
# HTTP surface — POST /api/a11oy/v1/pinn/identify (+ GET health/info).
# Registered BEFORE the SPA catch-all (front-inserted by serve.py).
# ---------------------------------------------------------------------------
def register(app, ns="a11oy"):
    from fastapi.responses import JSONResponse
    from fastapi import Request

    async def _identify(request: Request):
        try:
            try:
                spec = await request.json()
            except Exception:
                spec = {}
            if not isinstance(spec, dict):
                spec = {}
            if not spec:
                spec = {"demo": "duffing"}
            out = governed_discover(spec)
            code = 200 if out.get("ok") else 400
            label = out.get("convergence", {}).get("label", "NA")
            return JSONResponse(out, status_code=code,
                                headers={"x-szl-pinn-label": str(label),
                                         "x-szl-organ": RECEIPT_ORGAN})
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": "%r" % e, "honesty": _honesty()},
                                status_code=500)

    async def _health():
        systems = list(_BUILTIN_SYSTEMS)
        demos = {"duffing": "POST {\"demo\":\"duffing\"} -> GREEN alpha ~ 1.0"}
        if _CALPHAD is not None:
            systems += list(_CALPHAD.RK_SYSTEMS)
            demos["calphad"] = ("POST {\"demo\":\"calphad\"} -> GREEN Redlich-Kister "
                                "L0,L1,L2 ~ ground truth; "
                                "{\"demo\":\"calphad\",\"case\":\"ill_posed\"} -> RED/REFUSE")
        return JSONResponse({
            "ok": True, "organ": RECEIPT_ORGAN,
            "endpoint": "POST /api/%s/v1/pinn/identify" % ns,
            "supported_systems": systems,
            "verticals": (["physics(duffing)", "materials-by-design(redlich_kister/CALPHAD)"]
                          if _CALPHAD is not None else ["physics(duffing)"]),
            "calphad_available": _CALPHAD is not None,
            "demos": demos,
            "honesty": _honesty(),
        })

    prefixes = ["/api/%s/v1/pinn" % ns, "/v1/pinn"]
    routes = []
    for p in prefixes:
        app.add_api_route("%s/identify" % p, _identify, methods=["POST", "GET"],
                          include_in_schema=True)
        app.add_api_route("%s/health" % p, _health, methods=["GET"],
                          include_in_schema=True)
        routes += ["%s/identify" % p, "%s/health" % p]
    return routes


if __name__ == "__main__":
    out = governed_discover({"demo": "duffing"})
    print(json.dumps({k: out[k] for k in ("ok", "system", "convergence", "discovered",
                                          "lambda_advisory", "ledger")},
                     indent=2, default=float)[:2000])
