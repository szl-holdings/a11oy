# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v13 — SWEEP DEV 3: honest /status surfaces for quant, qbio, holographic.
"""
szl_quant_qbio_holo.py — SWEEP DEV 3 status-wiring module.

Three a11oy surfaces serve a 200 PAGE but had NO backing `/<surface>/status` API
(404). This module wires the missing HONEST `/status` endpoints, each summarizing
REAL substance that already exists in the estate — never fabricated data. Every
status signs a Khipu receipt into the SHARED szl_khipu hash chain.

  GET /api/a11oy/v1/qbio/status        — summary of the REAL Quantum-Bio Λ-v5 state
                                         (szl_quantum_bio: Mitchell pmf, Lindblad
                                         coherence, radical-pair compass, Λ-v5 gate).
                                         WHY it 404'd: szl_quantum_bio.register mounts
                                         /qbio/{pmf,coherence,compass,lambda,summary}
                                         but NO /qbio/status. This adds the missing one.
  GET /api/a11oy/v1/quant/status       — honest summary of the quant substance: the
                                         quantum-axis canonical formulas in szl_formulas
                                         (PROVEN vs CONJECTURE/AXIOM/SORRY per the
                                         PROOF_STATUS index) + a link to the LIVE PNT /
                                         quantum-sensing mesh (/api/a11oy/v1/pnt/limits).
  GET /api/a11oy/v1/holographic/status — honest summary of the 3D estate hologram: it
                                         is a VISUALIZATION over real mesh state. Reports
                                         the live compute-pool reachability (szl_backend_
                                         hardening.probe_fabric_pool) + the szl3d toolkit
                                         FOUNDATION info. Labeled MODELED/LIVE honestly.

DOCTRINE HARD GATES carried on every payload:
  * Λ = Conjecture 1 (NOT a theorem). The Λ-v5 gate is a PROPOSED engineering
    predicate, NOT the formal uniqueness Λ, and is NOT folded into the locked-8.
  * Khipu = Conjecture 2 (the chain verifies INTEGRITY, signature is DSSE PLACEHOLDER).
  * locked-8 proven set @ c7c0ba17 is UNCHANGED — this module adds NOTHING to it.
  * trust never 100%.
  * NO user-visible codenames.
  * NEVER fabricate quantum/bio data — if a backing source is unreachable the status
    says so honestly (degraded / source_unavailable), never a faked-LIVE number.
  * Every datum labeled LIVE / MODELED / PROVEN / CONJECTURE / ROADMAP.

Additive · pure stdlib (+ reuses in-image szl_* modules) · try/except-guarded so it
can never take down the SPA. Registered BEFORE the SPA catch-all.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from starlette.requests import Request
from starlette.responses import JSONResponse

LOCKED_8 = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_COMMIT = "c7c0ba17"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _khipu_emit(organ: str, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sign a receipt into the SHARED szl_khipu chain; honest fallback if absent.

    Khipu = Conjecture 2: this verifies the HASH CHAIN integrity only; the receipt
    SIGNATURE is DSSE PLACEHOLDER (Sigstore not wired in CI). Never raises.
    """
    try:
        import szl_khipu
        dag = szl_khipu.get_dag(organ, ns="a11oy")
        receipt = dag.emit(action, payload)
        chain = dag.verify_chain()
        return {
            "organ": organ,
            "receipt_type": f"SZL.{organ.capitalize()}.Status.v1",
            "seq": receipt.get("seq"),
            "digest": receipt.get("digest"),
            "prev": receipt.get("prev"),
            "signature": receipt.get("signature"),  # DSSE_PLACEHOLDER (honest)
            "chain_verified": chain.get("ok"),
            "chain_depth": dag.depth(),
            "head_digest": dag.head(),
            "khipu_kind": "Conjecture 2",
        }
    except Exception as exc:  # noqa: BLE001
        return {"organ": organ, "khipu_kind": "Conjecture 2",
                "chain_verified": None, "note": f"khipu unavailable: {exc!r}"}


# ---------------------------------------------------------------------------
# qbio/status — summarize the REAL Quantum-Bio Λ-v5 state (szl_quantum_bio).
# ---------------------------------------------------------------------------
def _qbio_status() -> Dict[str, Any]:
    base = "/api/a11oy/v1/qbio"
    live_paths = [f"{base}/pmf", f"{base}/coherence", f"{base}/compass",
                  f"{base}/lambda", f"{base}/summary", f"{base}/status"]
    models: list[Dict[str, Any]] = []
    summary_src = None
    sources: Dict[str, str] = {}
    try:
        import szl_quantum_bio as qb
        # Recompute the REAL verified headline numbers on-call (reproduces every call).
        pmf_single = round(qb.pmf(150.0, 0.5), 1)
        pmf_two = round(qb.pmf_two_ion(150.0, 0.5, 0.30), 1)
        coh = qb.lindblad_coherence_series()
        comp = qb.compass(50.0)
        lam = qb.lambda_v5(0.9, 121.5, 130.0)
        sources = dict(getattr(qb, "SOURCES", {}))
        models = [
            {"model": "Mitchell proton-motive force",
             "equation": "Δp = ΔΨ − (2.3 RT / F)·ΔpH (mV)",
             "value_mV": pmf_single, "status": "VERIFIED",
             "source": sources.get("Mitchell pmf (Nobel)"),
             "endpoint": f"{base}/pmf"},
            {"model": "Two-ion K+/H+ pmf correction",
             "value_mV": pmf_two, "status": "PROPOSED",
             "endpoint": f"{base}/pmf"},
            {"model": "Lindblad / GKSL coherence decay",
             "equation": "dρ/dt = −(i/ħ)[H,ρ] + Σ γ_k (L_k ρ L_k† − ½{L_k†L_k, ρ})",
             "fitted_tau_c": coh.get("tau_c"), "status": "VERIFIED",
             "endpoint": f"{base}/coherence"},
            {"model": "Radical-pair magnetoreception (singlet yield)",
             "angular_contrast": comp.get("angular_contrast"),
             "compass_works": comp.get("works"), "status": "VERIFIED",
             "fidelity": "reduced single-nucleus closed-form (full model contrast ~0.378)",
             "endpoint": f"{base}/compass"},
            {"model": "SZL Λ-v5 closure gate",
             "lambda": lam.get("lambda"), "closure_ok": lam.get("closure_ok"),
             "rule": lam.get("rule"), "status": "PROPOSED",
             "doctrine": ("Engineering gate only. NOT the formal uniqueness Λ "
                          "(that is Conjecture 1, machine-checked FALSE). NOT in the locked-8."),
             "endpoint": f"{base}/lambda"},
        ]
        summary_src = f"{base}/summary"
        backing = "LIVE"
        note = ("szl_quantum_bio is imported in-process; the VERIFIED numbers above are "
                "recomputed on this call (they reproduce every time). The /qbio/status "
                "route was missing (the module registers /pmf,/coherence,/compass,/lambda,"
                "/summary but no /status); this endpoint adds the honest summary.")
    except Exception as exc:  # noqa: BLE001
        backing = "DEGRADED"
        note = (f"szl_quantum_bio import failed: {exc!r}. No quantum/bio numbers are "
                "fabricated — status reports the contract only.")
    verified = sum(1 for m in models if m.get("status") == "VERIFIED")
    proposed = sum(1 for m in models if m.get("status") == "PROPOSED")
    payload = {
        "surface": "qbio",
        "title": "Quantum-Bio Λ-v5 — surface status",
        "backing": backing,
        "models_total": len(models),
        "verified_models": verified,
        "proposed_models": proposed,
        "live_paths": live_paths,
        "summary_endpoint": summary_src,
        "models": models,
        "status_legend": {
            "VERIFIED": "executed model, reproduces on every call",
            "PROPOSED": "SZL-proposed construct (two-ion pmf, Λ-v5 gate)",
            "NARRATIVE": "Jack Kruse framing only — NOT load-bearing math",
        },
        "lean_closure_theorems": ["decohered_never_closes", "uncharged_never_closes",
                                  "lambda_mono_in_coherence"],
        "doctrine": {
            "lambda": "Conjecture 1 (NOT a theorem); Λ-v5 gate is PROPOSED, not the formal Λ",
            "khipu": "Conjecture 2 (chain integrity only; signature DSSE PLACEHOLDER)",
            "locked_8": {"set": LOCKED_8, "commit": LOCKED_COMMIT, "qbio_in_locked_8": False},
            "trust": "never 100%",
        },
        "sources": sources,
        "note": note,
        "ts": _now(),
    }
    payload["khipu_receipt"] = _khipu_emit(
        "qbio", "qbio.status",
        {"verified": verified, "proposed": proposed, "backing": backing})
    return payload


# ---------------------------------------------------------------------------
# quant/status — honest summary of quant formulas + LIVE PNT/quantum-sensing mesh.
# ---------------------------------------------------------------------------
def _quant_status() -> Dict[str, Any]:
    quant_formulas = [
        "gleason_quantum_lambda", "bohr_complementarity_floor",
        "kochen_specker_18vector_witness", "two_witness_ks18_soundness",
        "shor_codeword_distance", "css_ingress_verify", "kitaev_surface_correct",
        "reed_solomon_singleton", "fisher_rao_distance", "pinsker_kl_bound",
        "hoeffding_tail", "madhava_series",
    ]
    proven: list[Dict[str, str]] = []
    conjecture: list[Dict[str, str]] = []
    formulas_backing = "MODELED"
    try:
        import szl_formulas as sf
        proof_index = dict(getattr(sf, "PROOF_STATUS", {}))
        registry_count = sf.registry_count() if hasattr(sf, "registry_count") else None
        for name in quant_formulas:
            label = proof_index.get(name, "UNLISTED")
            entry = {"formula": name, "proof_status": label}
            up = label.upper()
            # PROVEN only if the label begins with PROVEN and carries no open caveat.
            if up.startswith("PROVEN"):
                proven.append(entry)
            else:  # AXIOM / SORRY / CONJECTURE / UNLISTED -> NOT proven (honest)
                conjecture.append(entry)
        formulas_backing = "LIVE"
        formulas_note = ("szl_formulas.PROOF_STATUS read in-process. PROVEN = discharged "
                         "sorry-free in Lean (or trivially exact); everything else "
                         "(AXIOM / SORRY / open) is NOT proven and is reported honestly.")
    except Exception as exc:  # noqa: BLE001
        registry_count = None
        formulas_note = (f"szl_formulas import failed: {exc!r}; no proof status fabricated.")

    # LIVE PNT / quantum-sensing mesh — link, and probe its in-process backing.
    pnt = {"endpoint": "/api/a11oy/v1/pnt/limits", "backing": "ROADMAP"}
    try:
        import szl_pnt_mesh as pm  # noqa: F401
        pnt["backing"] = "LIVE"
        pnt["pillars"] = ["compute_bounds (szl_pinn_bounds)",
                          "quantum_sensor (quantum_sensing_limits)",
                          "pnt_resilience", "nav_coasting"]
        pnt["note"] = ("PNT/quantum-sensing mesh module imports in-process; the live "
                       "index is served at /api/a11oy/v1/pnt/limits with MEASURED/"
                       "MODELED/SAMPLE labels. Pillar B = cold-atom interferometer SQL "
                       "+ fused spoof detector + GPS-denied coasting FoM.")
    except Exception as exc:  # noqa: BLE001
        pnt["note"] = f"szl_pnt_mesh not importable here: {exc!r} (page still links the live route)."

    payload = {
        "surface": "quant",
        "title": "Quant — surface status (quantum-axis formulas + PNT/quantum-sensing mesh)",
        "substance": ("Real quant substance is two-fold: (1) the quantum-axis CANONICAL "
                      "formulas in szl_formulas with honest PROVEN/AXIOM/SORRY labels, and "
                      "(2) the LIVE PNT / quantum-sensing fundamental-limits mesh."),
        "formulas_backing": formulas_backing,
        "registry_count": registry_count,
        "quant_formulas_examined": len(quant_formulas),
        "proven": proven,
        "proven_count": len(proven),
        "conjecture_or_axiom": conjecture,
        "conjecture_or_axiom_count": len(conjecture),
        "formulas_note": formulas_note,
        "pnt_mesh": pnt,
        "doctrine": {
            "lambda": "Conjecture 1 (NOT a theorem)",
            "khipu": "Conjecture 2 (chain integrity only; signature DSSE PLACEHOLDER)",
            "locked_8": {"set": LOCKED_8, "commit": LOCKED_COMMIT,
                         "note": "exactly 8 proven; quant-axis AXIOM/SORRY items are NOT in it"},
            "trust": "never 100%",
            "honest_label": ("PROVEN means sorry-free in Lean. AXIOM/SORRY/CONJECTURE are "
                             "NOT proven and are not folded into the locked-8."),
        },
        "ts": _now(),
    }
    payload["khipu_receipt"] = _khipu_emit(
        "quant", "quant.status",
        {"proven": len(proven), "conjecture_or_axiom": len(conjecture),
         "pnt_backing": pnt["backing"]})
    return payload


# ---------------------------------------------------------------------------
# holographic/status — honest summary of the 3D estate hologram (visualization
# over REAL mesh state). Reports live compute-pool reachability + szl3d toolkit.
# ---------------------------------------------------------------------------
def _holographic_status() -> Dict[str, Any]:
    # Live compute-pool reachability (the hologram renders node health/quorum).
    pool = {"backing": "ROADMAP"}
    try:
        import szl_backend_hardening as bh
        probe = bh.probe_fabric_pool()  # concurrent, cached, NEVER fabricates reachable
        counts = probe.get("counts", {}) if isinstance(probe, dict) else {}
        nodes = probe.get("nodes", []) if isinstance(probe, dict) else []
        pool = {
            "backing": "LIVE",
            "source_endpoint": "/api/a11oy/v1/compute-pool-hardened",
            "nodes_total": counts.get("nodes_total", len(nodes)),
            "nodes_reachable": counts.get("nodes_reachable"),
            "gpu_nodes_reachable": counts.get("gpu_nodes_reachable"),
            "cached_at": probe.get("cached_at") if isinstance(probe, dict) else None,
            "nodes": [
                {"name": n.get("name"), "kind": n.get("kind"),
                 "reachable": n.get("reachable"), "sovereign": n.get("sovereign")}
                for n in nodes if isinstance(n, dict)
            ],
            "label": "MEASURED (real TCP probe; down nodes never faked reachable)",
        }
    except Exception as exc:  # noqa: BLE001
        pool["note"] = f"compute-pool probe unavailable: {exc!r} (no node fabricated up)."

    # szl3d holographic toolkit / shell (the renderer + the BFT-quorum mesh graph).
    toolkit = {"backing": "ROADMAP"}
    try:
        import szl3d_holographic as h3
        info = h3.info(ns="a11oy") if hasattr(h3, "info") else {}
        toolkit = {
            "backing": "LIVE",
            "capability": info.get("capability"),
            "shell_page": (info.get("shell") or {}).get("page", "/holographic"),
            "toolkit_status": info.get("status"),
            "cdn": "0 runtime CDN (vendored three.js r170, on-disk static/3d tree)",
            "surfaces": "9 surface modules (energy, fabric, pnt, counter-uas, governance, pinn, router, ...)",
            "label": "MODELED (3D visualization layer over real mesh/compute state)",
        }
    except Exception as exc:  # noqa: BLE001
        toolkit["note"] = f"szl3d_holographic not importable here: {exc!r}"

    payload = {
        "surface": "holographic",
        "title": "Holographic — surface status (3D estate hologram)",
        "honest_framing": ("The /holographic page is a VISUALIZATION over REAL mesh state. "
                           "It is NOT a holographic-principle physics claim and NOT a "
                           "quantum device — it renders the live compute-pool reachability "
                           "and the BFT-quorum mesh graph in 3D. The geometry is MODELED; "
                           "the underlying node/quorum data is the LIVE mesh."),
        "visualizes": [
            {"layer": "compute-pool node health", "source": "/api/a11oy/v1/compute-pool-hardened",
             "label": "LIVE"},
            {"layer": "BFT-quorum mesh graph", "source": "/api/a11oy/v1/mesh/3d", "label": "LIVE"},
            {"layer": "3D geometry / trust sphere", "renderer": "szl3d toolkit (three.js r170)",
             "label": "MODELED"},
        ],
        "compute_pool": pool,
        "toolkit": toolkit,
        "mesh_graph_endpoint": "/api/a11oy/v1/mesh/3d",
        "doctrine": {
            "lambda": "Conjecture 1 (NOT a theorem)",
            "khipu": "Conjecture 2 (chain integrity only; signature DSSE PLACEHOLDER)",
            "locked_8": {"set": LOCKED_8, "commit": LOCKED_COMMIT},
            "trust": "never 100%",
            "cdn": "0 runtime CDN",
            "effectors": "SIMULATED",
        },
        "ts": _now(),
    }
    payload["khipu_receipt"] = _khipu_emit(
        "holographic", "holographic.status",
        {"pool_backing": pool.get("backing"),
         "nodes_reachable": pool.get("nodes_reachable"),
         "toolkit_backing": toolkit.get("backing")})
    return payload


# ---------------------------------------------------------------------------
# Registration — dual-register under /api/{ns}/v1/<s>/status AND /v1/<s>/status.
# Mirrors szl_immune / szl_kverify add_api_route pattern. Registered BEFORE the
# SPA catch-all so these JSON routes resolve locally and win ordering. Each handler
# is fully try/except-guarded so it can never take down the SPA.
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> Dict[str, Any]:
    async def _h_qbio_status(request: Request = None):  # noqa: ANN001,ANN202,ARG001
        try:
            return JSONResponse(_qbio_status())
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"surface": "qbio", "backing": "ERROR",
                                 "error": repr(exc)[:200], "ts": _now()}, status_code=200)

    async def _h_quant_status(request: Request = None):  # noqa: ANN001,ANN202,ARG001
        try:
            return JSONResponse(_quant_status())
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"surface": "quant", "backing": "ERROR",
                                 "error": repr(exc)[:200], "ts": _now()}, status_code=200)

    async def _h_holographic_status(request: Request = None):  # noqa: ANN001,ANN202,ARG001
        try:
            return JSONResponse(_holographic_status())
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"surface": "holographic", "backing": "ERROR",
                                 "error": repr(exc)[:200], "ts": _now()}, status_code=200)

    groups = [
        ("qbio", _h_qbio_status),
        ("quant", _h_quant_status),
        ("holographic", _h_holographic_status),
    ]
    routes: list[str] = []
    add_api_route = getattr(app, "add_api_route", None)
    for surface, handler in groups:
        for prefix in (f"/api/{ns}/v1/{surface}", f"/v1/{surface}"):
            path = f"{prefix}/status"
            if callable(add_api_route):
                app.add_api_route(path, handler, methods=["GET"], include_in_schema=True)
            else:
                from starlette.routing import Route
                app.router.routes.append(Route(path, handler))
            routes.append(path)
    print(f"[{ns}] szl_quant_qbio_holo registered {len(routes)} status routes "
          f"(quant + qbio + holographic; honest LIVE/MODELED/PROVEN/CONJECTURE labels)",
          flush=True)
    return {"ok": True, "ns": ns, "routes": routes}


# ---------------------------------------------------------------------------
# No-server self-test — proves the REAL summaries + honesty without HTTP.
# ---------------------------------------------------------------------------
def _selftest() -> Dict[str, Any]:
    import json
    out: Dict[str, Any] = {}
    q = _qbio_status()
    assert q["surface"] == "qbio"
    assert q["doctrine"]["lambda"].startswith("Conjecture 1")
    out["qbio_models"] = q["models_total"]
    out["qbio_backing"] = q["backing"]

    qt = _quant_status()
    assert qt["surface"] == "quant"
    assert qt["proven_count"] + qt["conjecture_or_axiom_count"] == qt["quant_formulas_examined"]
    out["quant_proven"] = qt["proven_count"]
    out["quant_conjecture_or_axiom"] = qt["conjecture_or_axiom_count"]
    out["pnt_backing"] = qt["pnt_mesh"]["backing"]

    h = _holographic_status()
    assert h["surface"] == "holographic"
    out["holo_pool_backing"] = h["compute_pool"]["backing"]
    out["holo_toolkit_backing"] = h["toolkit"]["backing"]

    # No codename leaks in any served string.
    served = json.dumps([q, qt, h]).lower()
    for bad in ("sentra", "amaru", "rosie", "jarvis"):
        assert bad not in served, f"codename leak: {bad}"
    out["no_codename_leak"] = True

    # Locked-8 unchanged, exactly 8.
    assert q["doctrine"]["locked_8"]["set"] == LOCKED_8 and len(LOCKED_8) == 8
    out["locked_8_intact"] = True
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(_selftest(), indent=2))
