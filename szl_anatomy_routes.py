# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v10 — 749 declarations · 14 unique axioms · 163 sorries · 21 canonical formulas
"""
szl_anatomy_routes.py — ADDITIVE FastAPI router for the Anatomy substrate.
"""
from __future__ import annotations

import inspect
from hashlib import sha256
from typing import Any, Dict, List

import szl_formulas as S

try:
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse
except Exception:
    Request = HTMLResponse = JSONResponse = None  # type: ignore

REPO = "https://github.com/szl-holdings/szl-cookbook/tree/main/recipes"
FORMULA_SRC = f"{REPO}/canonical-formulas-v1/code/python/formulas.py"
COMPOSER_SRC = f"{REPO}/codex-kernel-composer-v1/code/python/composer.py"

CHAKRAS: List[Dict[str, Any]] = [
    {"n": 1, "name": "Muladhara", "en": "root", "quechua": "KALLPA-TAKI",
     "formula": "lambda_bounded", "role": "A4 grounding — Λ bounded by max axis",
     "sample": {"args": [[0.82, 0.91, 0.77]]}},
    {"n": 2, "name": "Svadhisthana", "en": "sacral", "quechua": "PAQARICHIQ",
     "formula": "pac_bayes_mcallester", "role": "generative bound (McAllester 1999)",
     "sample": {"args": [0.08, 1.5, 2000, 0.05]}},
    {"n": 3, "name": "Manipura", "en": "solar plexus", "quechua": "K'ANCHARIQ",
     "formula": "lambda_homogeneous", "role": "A2 scaling — positive homogeneity",
     "sample": {"args": [2.0, [0.6, 0.8, 0.9]]}},
    {"n": 4, "name": "Anahata", "en": "heart", "quechua": "YUYAY",
     "formula": "fisher_rao_distance", "role": "axis-manifold metric (Rao 1945)",
     "sample": {"args": [[0.4, 0.6], [0.45, 0.55]]}},
    {"n": 5, "name": "Vishuddha", "en": "throat", "quechua": "RIMAQ",
     "formula": "dsse_envelope", "role": "truthful expression — DSSE receipt",
     "sample": {"args": ["chakra5-payload", "amaru-key-1"]}},
    {"n": 6, "name": "Ajna", "en": "third-eye", "quechua": "QHAWAQ",
     "formula": "gleason_quantum_lambda", "role": "perception — Gleason purity",
     "sample": {"args": [[[0.5, 0.0], [0.0, 0.5]]]},
     "also": "kochen_specker_18vector_witness"},
    {"n": 7, "name": "Sahasrara", "en": "crown", "quechua": "KHIPU",
     "formula": "khipu_merkle_root", "role": "transcendent unification — Merkle DAG root",
     "sample": {"args": [[{"decision_id": "d1", "value": 10}, {"decision_id": "d2", "value": 20}]]}},
    {"n": 8, "name": "Bindu", "en": "DINN", "quechua": "HUKLLA-DINN",
     "formula": "two_witness_ks18_soundness", "role": "doctrine DINN loss / two-witness soundness",
     "sample": {"args": [True, True]}},
]
CHAKRA_BY_N = {c["n"]: c for c in CHAKRAS}

def _coerce(name: str, args: List[Any]) -> List[Any]:
    out = list(args)
    if name in ("dsse_envelope",) and out and isinstance(out[0], str):
        out[0] = out[0].encode()
    if name == "css_ingress_verify" and len(out) > 1 and isinstance(out[1], str):
        out[1] = bytes.fromhex(out[1]) if all(c in "0123456789abcdef" for c in out[1].lower()) else out[1].encode()
    return out

def _jsonify(v: Any) -> Any:
    if isinstance(v, bytes):
        return v.hex()
    if isinstance(v, dict):
        return {k: _jsonify(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonify(x) for x in v]
    return v

def run_one(name: str, args: List[Any], kwargs: Dict[str, Any] | None = None) -> Dict[str, Any]:
    fn = S.REGISTRY.get(name)
    if fn is None:
        return {"ok": False, "error": f"unknown formula: {name}"}
    a = _coerce(name, args or [])
    try:
        out = fn(*a, **(kwargs or {}))
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
    jr = _jsonify(out)
    receipt = sha256(f"{name}|{args}|{jr}".encode()).hexdigest()
    return {
        "ok": True, "formula": name, "args": args, "result": jr,
        "proof_status": S.PROOF_STATUS.get(name, "?"),
        "lambda_receipt": receipt, "source": FORMULA_SRC,
    }

def registry_json() -> List[Dict[str, Any]]:
    chakra_of = {c["formula"]: c["n"] for c in CHAKRAS}
    rows = []
    for name, fn in S.REGISTRY.items():
        sig = str(inspect.signature(fn))
        rows.append({
            "name": name, "signature": sig,
            "proof_status": S.PROOF_STATUS.get(name, "?"),
            "doc": (fn.__doc__ or "").strip().split("\n")[0],
            "chakra": chakra_of.get(name),
        })
    return rows

def register(app, ns: str, api_app=None, html_app=None):
    try:
        from szl_anatomy_alias_bind import bind_ptg_redirect
        bind_ptg_redirect()
    except Exception:
        pass
    html = html_app or app
    api = api_app if api_app is not None else app
    P = "" if api_app is not None else f"/api/{ns}"
    paths: List[str] = []

    @html.get("/formulas", response_class=HTMLResponse)
    async def _formulas_page():
        return HTMLResponse("<p>formulas</p>")
    paths.append("/formulas")

    @api.get(f"{P}/v1/formulas")
    async def _formulas_list():
        return JSONResponse({"count": S.registry_count(), "formulas": registry_json()})
    paths.append(f"/api/{ns}/v1/formulas")
    return paths
