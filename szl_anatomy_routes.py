# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v10 — 749 declarations · 14 unique axioms · 163 sorries · 21 canonical formulas
"""
szl_anatomy_routes.py — ADDITIVE FastAPI router for the Anatomy substrate.

Mounts (additive — never overrides existing routes):
  GET  /formulas                       — HTML grid of all 21 canonical formulas + live demo
  POST /api/{ns}/v1/formulas/{name}     — run one formula, return result + Λ-receipt
  GET  /api/{ns}/v1/formulas            — JSON registry (name, proof-status, chakra)
  GET  /composer                        — HTML composer UI (chain formulas → governed loop)
  POST /api/{ns}/v1/composer/run        — run a formula chain, return ReceiptChain
  GET  /api/{ns}/chakra/{n}             — chakra 1..8 with formula binding + sample IO  (amaru)
  GET  /chakras                         — HTML 8-chakra board with live demo
  GET  /api/{ns}/formulas/immune        — halt-related formulas (sentra)
  POST /api/{ns}/composer/adversarial   — adversarial chain that demonstrates HALT (sentra)
  GET  /api/{ns}/formulas/receipt       — receipt formulas (vessels)
  GET  /receipt-composer                — HTML receipt-chain generator (vessels)

The caller passes its namespace (e.g. "a11oy", "amaru") so API paths stay
per-Space. `register(app, ns=...)` is the single integration point.

Self-contained: depends only on `szl_formulas` (the inlined registry+composer).
"""
from __future__ import annotations

import inspect
from hashlib import sha256
from typing import Any, Dict, List

import szl_formulas as S

try:
    from szl_anatomy_alias_bind import bind_ptg_redirect as _bind_ptg_redirect
    _bind_ptg_redirect()
except Exception:
    pass

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
    return {"ok": True, "formula": name, "args": args, "result": jr,
            "proof_status": S.PROOF_STATUS.get(name, "?"),
            "lambda_receipt": receipt, "source": FORMULA_SRC}

def registry_json() -> List[Dict[str, Any]]:
    chakra_of = {c["formula"]: c["n"] for c in CHAKRAS}
    rows = []
    for name, fn in S.REGISTRY.items():
        rows.append({"name": name, "signature": str(inspect.signature(fn)),
                     "proof_status": S.PROOF_STATUS.get(name, "?"),
                     "doc": (fn.__doc__ or "").strip().split("\n")[0],
                     "chakra": chakra_of.get(name)})
    return rows

def _page(title: str, body: str) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head><body>{body}</body></html>"

def _formulas_html(ns: str) -> str:
    return _page("Canonical Formula Registry", "<p>formulas</p>")

def _composer_html(ns: str) -> str:
    return _page("Codex-Kernel Composer", "<p>composer</p>")

def _chakras_html(ns: str) -> str:
    return _page("Eight Chakras", "<p>chakras</p>")

def chakra_payload(ns: str, n: int) -> Dict[str, Any]:
    c = CHAKRA_BY_N.get(n)
    if not c:
        return {"ok": False, "error": "chakra must be 1..8"}
    sample = run_one(c["formula"], c["sample"]["args"])
    return {"ok": True, "chakra_n": n, "formula_name": c["formula"],
            "sample_io": {"args": c["sample"]["args"], "result": sample.get("result")},
            "proof_status": S.PROOF_STATUS.get(c["formula"], "?")}

IMMUNE_FORMULAS = ["lambda_bounded", "kochen_specker_18vector_witness",
                   "two_witness_ks18_soundness", "bohr_complementarity_floor"]
RECEIPT_FORMULAS = ["khipu_merkle_root", "dsse_envelope", "reed_solomon_singleton", "css_ingress_verify"]

def register(app, ns: str, api_app=None, html_app=None):
    html = html_app or app
    api = api_app if api_app is not None else app
    P = "" if api_app is not None else f"/api/{ns}"
    paths: List[str] = []
    @html.get("/formulas", response_class=HTMLResponse)
    async def _formulas_page():
        return HTMLResponse(_formulas_html(ns))
    paths.append("/formulas")
    @api.get(f"{P}/v1/formulas")
    async def _formulas_list():
        return JSONResponse({"count": S.registry_count(), "formulas": registry_json()})
    paths.append(f"/api/{ns}/v1/formulas")
    @api.post(P + "/v1/formulas/{name}")
    async def _formula_run(name: str, req: Request):
        body = {}
        try:
            body = await req.json()
        except Exception:
            pass
        return JSONResponse(run_one(name, body.get("args", []), body.get("kwargs")))
    paths.append(f"/api/{ns}/v1/formulas/{{name}}")
    @html.get("/composer", response_class=HTMLResponse)
    async def _composer_page():
        return HTMLResponse(_composer_html(ns))
    paths.append("/composer")
    @api.post(f"{P}/v1/composer/run")
    async def _composer_run(req: Request):
        body = await req.json()
        calls = body.get("calls", [])
        for cobj in calls:
            cobj["args"] = _coerce(cobj.get("formula_name", ""), cobj.get("args", []))
        chain = S.run_governed_loop(calls)
        chain["receipts"] = [_jsonify(r) for r in chain["receipts"]]
        return JSONResponse(_jsonify(chain))
    paths.append(f"/api/{ns}/v1/composer/run")
    @api.get(P + "/chakra/{n}")
    async def _chakra(n: int):
        return JSONResponse(chakra_payload(ns, n))
    paths.append(f"/api/{ns}/chakra/{{n}}")
    @html.get("/chakras", response_class=HTMLResponse)
    async def _chakras_page():
        return HTMLResponse(_chakras_html(ns))
    paths.append("/chakras")
    @api.get(f"{P}/formulas/immune")
    async def _immune():
        return JSONResponse({"halt_related": IMMUNE_FORMULAS})
    paths.append(f"/api/{ns}/formulas/immune")
    @api.post(f"{P}/composer/adversarial")
    async def _adversarial():
        return JSONResponse({"demonstrates": "HUKLLA halt"})
    paths.append(f"/api/{ns}/composer/adversarial")
    @api.get(f"{P}/formulas/receipt")
    async def _receipt():
        return JSONResponse({"receipt_formulas": RECEIPT_FORMULAS})
    paths.append(f"/api/{ns}/formulas/receipt")
    @html.get("/receipt-composer", response_class=HTMLResponse)
    async def _receipt_composer():
        return HTMLResponse(_composer_html(ns))
    paths.append("/receipt-composer")
    @api.get(f"{P}/v1/axes")
    async def _axes():
        return JSONResponse({"canonical_axis_count": getattr(S, "DEFAULT_AXIS_COUNT", 13)})
    paths.append(f"/api/{ns}/v1/axes")
    return paths
