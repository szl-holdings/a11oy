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

# Imported at module level so FastAPI's type-hint introspection (which uses the
# enclosing function's __globals__ = this module) can resolve `Request`.
try:  # pragma: no cover - only present when a FastAPI Space imports us
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse
except Exception:  # allows pure-Python (Gradio) import without FastAPI
    Request = HTMLResponse = JSONResponse = None  # type: ignore

REPO = "https://github.com/szl-holdings/szl-cookbook/tree/main/recipes"
FORMULA_SRC = f"{REPO}/canonical-formulas-v1/code/python/formulas.py"
COMPOSER_SRC = f"{REPO}/codex-kernel-composer-v1/code/python/composer.py"

# 8-chakra → formula binding (matches anatomy-evolved-v1; chakra 8 = Bindu/DINN).
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

# Coerce JSON-friendly args (bytes for dsse, etc.).
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
    """Run a single formula, return result + a Λ-receipt (hash of name|args|result)."""
    fn = S.REGISTRY.get(name)
    if fn is None:
        return {"ok": False, "error": f"unknown formula: {name}"}
    a = _coerce(name, args or [])
    try:
        out = fn(*a, **(kwargs or {}))
    except Exception as exc:  # honest error surface
        return {"ok": False, "error": str(exc)}
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


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · SZL Anatomy</title>
<style>
 body{{background:#1a0d2e;color:#ece6f5;font-family:Inter,system-ui,sans-serif;margin:0;padding:24px}}
 h1{{font-family:Cinzel,Georgia,serif;color:#ff7a59;font-weight:700}}
 a{{color:#9d7bff}} code,pre{{background:#241640;border-radius:6px;padding:2px 6px;font-family:ui-monospace,monospace}}
 table{{border-collapse:collapse;width:100%;margin-top:16px}} th,td{{border:1px solid #3a2a5a;padding:8px 10px;text-align:left;font-size:14px}}
 th{{background:#241640;color:#ffb59c}} .ps{{font-size:12px;color:#a9f5c9}} .sorry{{color:#ffd27a}} .conj{{color:#ff9d9d}}
 .card{{background:#221440;border:1px solid #3a2a5a;border-radius:12px;padding:16px;margin:12px 0}}
 button{{background:#ff7a59;color:#1a0d2e;border:0;border-radius:8px;padding:8px 14px;font-weight:700;cursor:pointer}}
 textarea,input{{width:100%;background:#150a26;color:#ece6f5;border:1px solid #3a2a5a;border-radius:8px;padding:8px;font-family:ui-monospace,monospace}}
 .chip{{display:inline-block;background:#2c1a52;border:1px solid #4a3470;border-radius:999px;padding:4px 10px;margin:3px;font-size:13px}}
 pre.out{{white-space:pre-wrap;max-height:320px;overflow:auto}}
</style></head><body><h1>{title}</h1>{body}
<p style="margin-top:32px;color:#8a7aa8;font-size:12px">SZL Holdings · Anatomy substrate · Doctrine v10 (749/14/163) · 21 canonical formulas ·
<a href="{FORMULA_SRC}">formulas.py</a> · <a href="{COMPOSER_SRC}">composer.py</a> · Hatun-Willay</p>
</body></html>"""


def _formulas_html(ns: str) -> str:
    rows = registry_json()
    trs = ""
    for r in rows:
        ps = r["proof_status"]
        cls = "sorry" if "SORRY" in ps else ("conj" if "CONJECTURE" in ps else "ps")
        trs += (f"<tr><td><code>{r['name']}</code></td>"
                f"<td>{r['doc']}</td>"
                f"<td class='{cls}'>{ps}</td>"
                f"<td>{'chakra '+str(r['chakra']) if r['chakra'] else '—'}</td></tr>")
    demo = f"""<div class="card"><b>Live demo</b> — run any formula:
 <p><input id="fn" placeholder="formula name e.g. lambda_bounded"/></p>
 <p><textarea id="args" rows="2">[[0.8,0.9,0.7]]</textarea></p>
 <button onclick="runF()">Run → Λ-receipt</button>
 <pre class="out" id="out">result appears here</pre></div>
 <script>
 async function runF(){{
   const fn=document.getElementById('fn').value.trim();
   let args; try{{args=JSON.parse(document.getElementById('args').value)}}catch(e){{document.getElementById('out').textContent='bad JSON args';return}}
   const r=await fetch('/api/{ns}/v1/formulas/'+encodeURIComponent(fn),{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{args}})}});
   document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2);
 }}</script>"""
    table = ("<table><tr><th>formula</th><th>summary</th><th>proof status</th><th>chakra</th></tr>"
             + trs + "</table>")
    return _page("Canonical Formula Registry", demo + table)


def _composer_html(ns: str) -> str:
    default = (
        '[\n {"formula_name":"lambda_bounded","args":[[0.82,0.91,0.77,0.88]]},\n'
        ' {"formula_name":"pac_bayes_mcallester","args":[0.08,1.5,2000,0.05]},\n'
        ' {"formula_name":"lambda_homogeneous","args":[2.0,[0.6,0.8,0.9]]},\n'
        ' {"formula_name":"fisher_rao_distance","args":[[0.4,0.6],[0.45,0.55]]},\n'
        ' {"formula_name":"dsse_envelope","args":["chakra5-payload","amaru-key-1"]}\n]'
    )
    body = f"""<div class="card"><b>Codex-Kernel Composer</b> — chain formulas into a hash-chained
 governed loop (4 hard-stop validators: state_transition, drift_bounds, human_gate, axis_floor).
 <p><textarea id="chain" rows="9">{default}</textarea></p>
 <button onclick="runC()">Run governed loop → ReceiptChain</button>
 <pre class="out" id="out">ReceiptChain appears here</pre></div>
 <script>
 async function runC(){{
   let chain; try{{chain=JSON.parse(document.getElementById('chain').value)}}catch(e){{document.getElementById('out').textContent='bad JSON';return}}
   const r=await fetch('/api/{ns}/v1/composer/run',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{calls:chain}})}});
   document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2);
 }}</script>"""
    return _page("Codex-Kernel Composer", body)


def _chakras_html(ns: str) -> str:
    cards = ""
    for c in CHAKRAS:
        cards += (f"<div class='card'><b>Chakra {c['n']} · {c['name']} ({c['en']}) · {c['quechua']}</b>"
                  f"<p>{c['role']}</p>"
                  f"<span class='chip'>formula: <code>{c['formula']}</code></span>"
                  f"<span class='chip'>{S.PROOF_STATUS.get(c['formula'],'?')}</span>"
                  f"<p><button onclick=\"demoC({c['n']})\">live demo</button> "
                  f"<a href='/api/{ns}/chakra/{c['n']}'>/api/{ns}/chakra/{c['n']}</a></p>"
                  f"<pre class='out' id='c{c['n']}'></pre></div>")
    body = cards + f"""<script>
 async function demoC(n){{
   const r=await fetch('/api/{ns}/chakra/'+n);const j=await r.json();
   const run=await fetch('/api/{ns}/v1/formulas/'+j.formula_name,{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{args:j.sample_io.args}})}});
   document.getElementById('c'+n).textContent=JSON.stringify(await run.json(),null,2);
 }}</script>"""
    return _page("Eight Chakras — Anatomy Board", body)


def chakra_payload(ns: str, n: int) -> Dict[str, Any]:
    c = CHAKRA_BY_N.get(n)
    if not c:
        return {"ok": False, "error": "chakra must be 1..8"}
    sample = run_one(c["formula"], c["sample"]["args"])
    return {
        "ok": True, "chakra_n": n, "organ_name_quechua": c["quechua"],
        "chakra_sanskrit": c["name"], "en": c["en"], "role": c["role"],
        "formula_name": c["formula"],
        "formula_python_source_link": FORMULA_SRC,
        "live_demo_endpoint": f"/api/{ns}/v1/formulas/{c['formula']}",
        "sample_io": {"args": c["sample"]["args"], "result": sample.get("result"),
                      "lambda_receipt": sample.get("lambda_receipt")},
        "proof_status": S.PROOF_STATUS.get(c["formula"], "?"),
    }


# Sentra immune + vessels receipt subsets.
IMMUNE_FORMULAS = ["lambda_bounded", "kochen_specker_18vector_witness",
                   "two_witness_ks18_soundness", "bohr_complementarity_floor"]
RECEIPT_FORMULAS = ["khipu_merkle_root", "dsse_envelope", "reed_solomon_singleton", "css_ingress_verify"]


def register(app, ns: str, api_app=None, html_app=None):
    """ADDITIVE: attach all anatomy routes. Never replaces existing routes.

    app      — the top-level FastAPI app (used for HTML pages by default).
    ns       — namespace, e.g. "a11oy" / "amaru".
    api_app  — OPTIONAL sub-app mounted at /api/{ns}. If provided, the JSON API
               routes are registered THERE with mount-relative paths
               (e.g. /chakra/{n} → served at /api/{ns}/chakra/{n}); this avoids
               colliding with an existing /api/{ns} mount. If None, API routes
               are registered on `app` with absolute /api/{ns}/... paths.
    html_app — OPTIONAL app for HTML pages (defaults to `app`).
    Returns the list of externally-visible paths for smoke-logging.
    """
    html = html_app or app
    api = api_app if api_app is not None else app
    # When routing through a sub-app mounted at /api/{ns}, the prefix is empty.
    P = "" if api_app is not None else f"/api/{ns}"
    paths: List[str] = []

    @html.get("/formulas", response_class=HTMLResponse)
    async def _formulas_page():  # noqa
        return _formulas_html(ns)
    paths.append("/formulas")

    @api.get(f"{P}/v1/formulas")
    async def _formulas_list():  # noqa
        return JSONResponse({"count": S.registry_count(), "formulas": registry_json()})
    paths.append(f"/api/{ns}/v1/formulas")

    @api.post(P + "/v1/formulas/{name}")
    async def _formula_run(name: str, req: Request):  # noqa
        body = {}
        try:
            body = await req.json()
        except Exception:
            pass
        return JSONResponse(run_one(name, body.get("args", []), body.get("kwargs")))
    paths.append(f"/api/{ns}/v1/formulas/{{name}}")

    @html.get("/composer", response_class=HTMLResponse)
    async def _composer_page():  # noqa
        return _composer_html(ns)
    paths.append("/composer")

    @api.post(f"{P}/v1/composer/run")
    async def _composer_run(req: Request):  # noqa
        body = await req.json()
        calls = body.get("calls", [])
        for cobj in calls:
            cobj["args"] = _coerce(cobj.get("formula_name", ""), cobj.get("args", []))
        chain = S.run_governed_loop(calls)
        chain["receipts"] = [_jsonify(r) for r in chain["receipts"]]
        return JSONResponse(_jsonify(chain))
    paths.append(f"/api/{ns}/v1/composer/run")

    @api.get(P + "/chakra/{n}")
    async def _chakra(n: int):  # noqa
        return JSONResponse(chakra_payload(ns, n))
    paths.append(f"/api/{ns}/chakra/{{n}}")

    @html.get("/chakras", response_class=HTMLResponse)
    async def _chakras_page():  # noqa
        return _chakras_html(ns)
    paths.append("/chakras")

    @api.get(f"{P}/formulas/immune")
    async def _immune():  # noqa
        return JSONResponse({"halt_related": IMMUNE_FORMULAS,
                             "details": [{"name": f, "proof_status": S.PROOF_STATUS.get(f)} for f in IMMUNE_FORMULAS]})
    paths.append(f"/api/{ns}/formulas/immune")

    @api.post(f"{P}/composer/adversarial")
    async def _adversarial():  # noqa
        calls = [
            {"formula_name": "lambda_bounded", "args": [[0.9, 0.9]]},
            {"formula_name": "bohr_complementarity_floor", "args": [0.01, 0.01]},
            {"formula_name": "khipu_merkle_root", "args": [[{"decision_id": "x", "value": 1}]]},
        ]
        chain = S.run_governed_loop(calls)
        chain["receipts"] = [_jsonify(r) for r in chain["receipts"]]
        return JSONResponse({"demonstrates": "HUKLLA halt on adversarial input",
                             "chain": _jsonify(chain)})
    paths.append(f"/api/{ns}/composer/adversarial")

    @api.get(f"{P}/formulas/receipt")
    async def _receipt():  # noqa
        return JSONResponse({"receipt_formulas": RECEIPT_FORMULAS,
                             "khipu_root_demo": run_one("khipu_merkle_root",
                                                        [[{"decision_id": "d1", "value": 10},
                                                          {"decision_id": "d2", "value": 20}]]),
                             "singleton_demo": run_one("reed_solomon_singleton", [255, 223])})
    paths.append(f"/api/{ns}/formulas/receipt")

    @html.get("/receipt-composer", response_class=HTMLResponse)
    async def _receipt_composer():  # noqa
        return _composer_html(ns)
    paths.append("/receipt-composer")

    @api.get(f"{P}/v1/axes")
    async def _axes():  # noqa
        # Canonical Lutar trust-axis schema (yuyay_v3, replay hash bacf5443...631fc5):
        # 13 axes = 2 sacred (>=0.95) + 7 structural (>=0.90) + 4 introspection
        # (HUKLLA T03/T04/T09/T10). The 9-axis vector is the legacy HATUN-RAID envelope.
        return JSONResponse({
            "canonical_axis_count": getattr(S, "DEFAULT_AXIS_COUNT", 13),
            "legacy_axis_count": getattr(S, "LEGACY_AXIS_COUNT", 9),
            "legacy_label": "HATUN-RAID envelope (deprecated default)",
            "bands": getattr(S, "AXIS_BANDS", {}),
            "floors_13": (S.axis_floors() if hasattr(S, "axis_floors") else None),
            "source": "founder yuyay_v3 LinkedIn; replay bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5",
        })
    paths.append(f"/api/{ns}/v1/axes")

    return paths
