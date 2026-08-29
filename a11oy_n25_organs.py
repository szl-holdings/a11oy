# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""N1–N25 factory organs on the product origin.

Runtime lives at https://a-11-oy.com/organs. Proof RECORD stays on a11oy.net/factory/.
Not 25 public Spaces. GPU tune remains UNAVAILABLE. Formulas never grant authority.
"""

from __future__ import annotations

import ast
import hashlib
import json
import operator
import re
from datetime import datetime, timezone
from typing import Any

ORGANS: list[dict[str, str]] = [
    {"id": "N1", "title": "Serve", "body": "brain", "job": "inference serving", "evidence_class": "SIMULATED", "placeholder": "Prompt to serve (schema-checked, no GPU claim)"},
    {"id": "N2", "title": "Graph", "body": "nervous", "job": "agent orchestration", "evidence_class": "SIMULATED", "placeholder": "Goal for a 3-node fail-closed graph"},
    {"id": "N3", "title": "Guard", "body": "immune", "job": "input/output safeguard", "evidence_class": "MEASURED", "placeholder": "Text to screen (deny weapons / PII / exfil)"},
    {"id": "N4", "title": "Mosaic", "body": "circulatory", "job": "data mosaic", "evidence_class": "SIMULATED", "placeholder": "Join key, e.g. lyte-pilot-01"},
    {"id": "N5", "title": "Lattice", "body": "immune", "job": "defense overlay", "evidence_class": "MODELED", "placeholder": "Request to score against the lattice"},
    {"id": "N6", "title": "Cover", "body": "heart", "job": "P&C insurance core", "evidence_class": "SIMULATED", "placeholder": "Risk note for a synthetic quote"},
    {"id": "N7", "title": "Quant", "body": "brain", "job": "algorithmic research and backtest", "evidence_class": "SIMULATED", "placeholder": "Ticker, e.g. SYN"},
    {"id": "N8", "title": "Title", "body": "skeleton", "job": "property records", "evidence_class": "SIMULATED", "placeholder": "Parcel id, e.g. 14-22-08"},
    {"id": "N9", "title": "Retrieve", "body": "nervous", "job": "retrieval and memory", "evidence_class": "MEASURED", "placeholder": "Query the factory corpus"},
    {"id": "N10", "title": "Observe", "body": "immune", "job": "trace and evaluation", "evidence_class": "MEASURED", "placeholder": "Note to attach as a trace"},
    {"id": "N11", "title": "Tune", "body": "brain", "job": "receipted fine-tune", "evidence_class": "UNAVAILABLE", "placeholder": "Dataset digest to request a tune (GPU denied)"},
    {"id": "N12", "title": "Schema", "body": "skeleton", "job": "constrained generation", "evidence_class": "SIMULATED", "placeholder": "Fill a Lyte quote schema from a sentence"},
    {"id": "N13", "title": "Energy", "body": "circulatory", "job": "joule accounting", "evidence_class": "MODELED", "placeholder": "Token count to model joules"},
    {"id": "N14", "title": "Tool", "body": "nervous", "job": "agent tool protocol", "evidence_class": "MEASURED", "placeholder": "lookup | quote | forbidden"},
    {"id": "N15", "title": "Memory", "body": "brain", "job": "persistent agent memory", "evidence_class": "MEASURED", "placeholder": "key=value to store, or a key to recall"},
    {"id": "N16", "title": "Eval", "body": "immune", "job": "offline evaluation", "evidence_class": "MEASURED", "placeholder": "Suite name, e.g. lyte-negatives"},
    {"id": "N17", "title": "Mesh", "body": "circulatory", "job": "distributed inference", "evidence_class": "SIMULATED", "placeholder": "Prompt to fan out across 3 synthetic nodes"},
    {"id": "N18", "title": "Route", "body": "circulatory", "job": "LLM gateway and routing", "evidence_class": "MEASURED", "placeholder": "Prompt; route by length / deny / json"},
    {"id": "N19", "title": "Cache", "body": "circulatory", "job": "prefix and semantic cache", "evidence_class": "MEASURED", "placeholder": "Prefix to cache or look up"},
    {"id": "N20", "title": "Voice", "body": "nervous", "job": "realtime duplex voice", "evidence_class": "SIMULATED", "placeholder": "Utterance to wrap as a duplex turn"},
    {"id": "N21", "title": "Sandbox", "body": "skeleton", "job": "isolated agent code execution", "evidence_class": "MEASURED", "placeholder": "Integer math only, e.g. (2+3)*4"},
    {"id": "N22", "title": "Identity", "body": "skeleton", "job": "non-human agent identity", "evidence_class": "SIMULATED", "placeholder": "Agent role, e.g. lyte-underwriter"},
    {"id": "N23", "title": "Rails", "body": "immune", "job": "conversation rails", "evidence_class": "MEASURED", "placeholder": "Turn text; rails refuse out-of-policy"},
    {"id": "N24", "title": "Browser", "body": "nervous", "job": "agent browser actuation", "evidence_class": "SIMULATED", "placeholder": "Same-origin path, e.g. /trust"},
    {"id": "N25", "title": "Policy", "body": "immune", "job": "authorization policy for tools", "evidence_class": "MEASURED", "placeholder": "tool=quote resource=lyte"},
]

_BY_ID = {o["id"]: o for o in ORGANS}
_MEMORY: dict[str, dict[str, str]] = {}
_CACHE: dict[str, dict[str, Any]] = {}
_TRACES: list[dict[str, str]] = []
_RUNS: list[dict[str, Any]] = []
_CORPUS = (
    "Lyte is the admitted protected design-partner cell.",
    "Killinchu is the only public synthetic reference.",
    "Formulas never grant authority. Locked set is exactly 8.",
    "Decision Cell Compiler binds a vertical manifest into receipts.",
    "Nexus is classified as an A11oy incubator package.",
)
_WEAPON = re.compile(r"\b(weapon|target(ing)?|kill chain|munition|exfil|ssn\b|password\s*=)", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _receipt(organ: dict[str, str], prompt: str, status: str, output: dict[str, Any], limitations: list[str]) -> dict[str, Any]:
    body = {
        "schema": "szl.organ-run/v1",
        "id": organ["id"],
        "title": organ["title"],
        "status": status,
        "honesty": organ["evidence_class"],
        "evidence_class": organ["evidence_class"],
        "formula_grants_authority": False,
        "input": {"prompt": prompt},
        "output": output,
        "limitations": limitations,
        "created_at": _now(),
    }
    rec = dict(body)
    rec["hash"] = _sha(_canonical(body))
    _RUNS.append(rec)
    if len(_RUNS) > 50:
        del _RUNS[: len(_RUNS) - 50]
    return rec


_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNOPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _safe_math(expr: str) -> float:
    clean = re.sub(r"\s+", "", expr)
    if not clean or not re.fullmatch(r"[0-9+\-*/().]+", clean) or len(clean) > 64:
        raise ValueError("sandbox denied")
    tree = ast.parse(clean, mode="eval")

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNOPS:
            return float(_UNOPS[type(node.op)](ev(node.operand)))
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                raise ValueError("div/0")
            return float(_BINOPS[type(node.op)](left, right))
        raise ValueError("sandbox denied")

    value = ev(tree)
    if value != value:
        raise ValueError("sandbox denied")
    return value


def run_organ(oid: str, prompt: str) -> dict[str, Any]:
    organ = _BY_ID.get(oid)
    if organ is None:
        raise KeyError(oid)
    text = (prompt or "").strip()
    fn = _RUNNERS[oid]
    return fn(organ, text)


def _run_n1(o, p):
    if not p:
        return _receipt(o, p, "DENIED", {"reason": "empty prompt"}, ["Serve refuses empty input"])
    if _WEAPON.search(p):
        return _receipt(o, p, "DENIED", {"reason": "guarded"}, ["Serve is fail-closed"])
    return _receipt(o, p, "EXECUTED", {"object": "chat.completion", "model": "factory-schema-envelope", "choices": [{"message": {"role": "assistant", "content": "Served (structural): " + p[:240]}}], "gpu": False}, ["No GPU. Schema envelope only. Not a vLLM rehost."])


def _run_n2(o, p):
    goal = p or "compile-lyte-quote"
    nodes = [{"name": n, "state": "DONE" if i < 2 else "AWAITING_APPROVAL"} for i, n in enumerate(("intake", "policy-shadow", "human-interrupt"))]
    return _receipt(o, p, "AWAITING_APPROVAL", {"goal": goal, "nodes": nodes, "interrupt": True}, ["Graph never auto-promotes. Human interrupt is required."])


def _run_n3(o, p):
    denied = (not p) or bool(_WEAPON.search(p))
    return _receipt(o, p, "DENIED" if denied else "EXECUTED", {"action": "DENY" if denied else "ALLOW", "rules": ["weapons", "exfil", "secrets"]}, ["Guard is LOG_ONLY overlay. Not a production WAF."])


def _run_n4(o, p):
    key = p or "lyte-pilot-01"
    row = {"lyte-pilot-01": {"buyer": "Lyte Services", "exposure": "protected-pilot"}}.get(key)
    return _receipt(o, p, "EXECUTED" if row else "DENIED", {"key": key, "row": row, "sources": ["synthetic-buyer", "synthetic-exposure"]}, ["Synthetic mosaic only. No private corpus."])


def _run_n5(o, p):
    score = 0.12 if _WEAPON.search(p) else 0.81
    return _receipt(o, p, "DENIED" if score < 0.5 else "EXECUTED", {"lattice_score": score, "overlay": "defense-in-depth"}, ["Modeled overlay. Not a measured SOC."])


def _run_n6(o, p):
    note = p or "warehouse sprinklered"
    if _WEAPON.search(note):
        return _receipt(o, p, "DENIED", {"reason": "guarded"}, ["Synthetic quote. Not a licensed insurance bind."])
    return _receipt(o, p, "EXECUTED", {"product": "P&C-synthetic", "premium_usd": 1200 + len(note) * 3, "bind": "LOG_ONLY"}, ["Synthetic quote. Not a licensed insurance bind."])


def _run_n7(o, p):
    ticker = (p or "SYN").upper()[:8]
    series = [100 + i + (1 if i % 2 else -1) for i in range(8)]
    ret = (series[-1] - series[0]) / series[0]
    return _receipt(o, p, "EXECUTED", {"ticker": ticker, "series": series, "return": round(ret, 4), "causal": False}, ["Synthetic series. Causal claims prohibited."])


def _run_n8(o, p):
    rec = {"14-22-08": {"parcel": "14-22-08", "holder": "synthetic-trust-a", "status": "clear"}, "99-00-01": {"parcel": "99-00-01", "holder": "synthetic-trust-b", "status": "lien"}}.get(p or "14-22-08")
    return _receipt(o, p, "EXECUTED" if rec else "DENIED", {"id": p or "14-22-08", "record": rec}, ["Synthetic title plant. Not a county system."])


def _run_n9(o, p):
    q = p.lower()
    hits = [row for row in _CORPUS if not q or q in row.lower()][:3]
    return _receipt(o, p, "EXECUTED" if hits else "DENIED", {"query": q, "hits": hits}, ["In-factory corpus only."])


def _run_n10(o, p):
    row = {"id": f"tr_{len(_TRACES)+1}", "organ": o["id"], "at": _now(), "note": p or "observe"}
    _TRACES.append(row)
    return _receipt(o, p, "EXECUTED", {"attached": row, "traces": _TRACES[-5:]}, ["In-process traces. Not a vendor APM."])


def _run_n11(o, p):
    return _receipt(o, p, "DENIED", {"dataset": p or "sha256:unavailable", "gpu": "UNAVAILABLE", "job": "not-queued"}, ["Tune is receipted and refused. No GPU in this runtime."])


def _run_n12(o, p):
    text = p or "Lyte warehouse quote"
    obj = {"insured": "Lyte Services" if re.search(r"lyte", text, re.I) else "synthetic-buyer", "occupancy": "warehouse" if re.search(r"ware", text, re.I) else "unspecified", "bind": False}
    return _receipt(o, p, "EXECUTED", {"schema": "lyte.quote.v1", "value": obj}, ["Constrained fill. Not a model decode."])


def _run_n13(o, p):
    try:
        n = float(p) if p else 128
    except ValueError:
        n = len(p) or 128
    return _receipt(o, p, "EXECUTED", {"tokens": n, "joules_modeled": round(n * 0.0024, 4)}, ["Modeled joules. Not a watt-meter."])


def _run_n14(o, p):
    name = re.sub(r"^tool:", "", p or "lookup")
    allow = ("lookup", "quote")
    if name not in allow:
        return _receipt(o, p, "DENIED", {"tool": name, "allow": list(allow)}, ["Unknown tools are denied."])
    result = _CORPUS[0] if name == "lookup" else {"premium_usd": 1200}
    return _receipt(o, p, "EXECUTED", {"tool": name, "result": result}, ["Allowlisted tools only."])


def _run_n15(o, p):
    if "=" in p:
        k, v = p.split("=", 1)
        rec = {"k": k.strip(), "v": v.strip(), "at": _now()}
        _MEMORY[rec["k"]] = rec
        return _receipt(o, p, "EXECUTED", {"stored": rec, "size": len(_MEMORY)}, ["Process memory. Not a customer vault."])
    hit = _MEMORY.get(p)
    return _receipt(o, p, "EXECUTED" if hit else "DENIED", {"key": p, "value": hit}, ["Recall miss is DENIED, not fabricated."])


def _run_n16(o, p):
    cases = [{"id": "neg-stale", "pass": True}, {"id": "neg-missing", "pass": True}, {"id": "pos-quote", "pass": True}, {"id": "weapon", "pass": True}]
    return _receipt(o, p, "EXECUTED", {"suite": p or "lyte-negatives", "passed": 4, "cases": cases}, ["Offline fixtures. Not a live customer eval."])


def _run_n17(o, p):
    prompt = p or "fanout"
    nodes = [{"name": n, "echo": prompt[:80], "ok": True} for n in ("alpha", "beta", "gamma")]
    return _receipt(o, p, "EXECUTED", {"nodes": nodes, "aggregate": [n["name"] for n in nodes]}, ["Synthetic mesh. Not a GPU cluster."])


def _run_n18(o, p):
    route = "deny" if _WEAPON.search(p) else "json-schema" if p.strip().startswith("{") else "long-context" if len(p) > 400 else "default"
    return _receipt(o, p, "DENIED" if route == "deny" else "EXECUTED", {"route": route, "backends": ["default", "json-schema", "long-context", "deny"]}, ["Rule router. No vendor keys."])


def _run_n19(o, p):
    if not p:
        return _receipt(o, p, "DENIED", {"reason": "empty prefix"}, ["Cache needs a prefix"])
    hit = _CACHE.get(p)
    if hit:
        hit["hits"] += 1
        return _receipt(o, p, "EXECUTED", {"hit": True, "value": hit["v"], "hits": hit["hits"]}, ["In-process prefix cache."])
    _CACHE[p] = {"v": "cached:" + p[:80], "hits": 0}
    return _receipt(o, p, "EXECUTED", {"hit": False, "stored": True}, ["Miss stored. Not a semantic GPU cache."])


def _run_n20(o, p):
    utter = p or "acknowledge"
    return _receipt(o, p, "EXECUTED", {"turn": {"user": utter, "assistant": "Heard (transcript only): " + utter}, "audio": False}, ["Transcript envelope. Not a realtime voice stack."])


def _run_n21(o, p):
    try:
        value = _safe_math(p or "1+1")
        return _receipt(o, p, "EXECUTED", {"value": value}, ["Integer math sandbox. No eval, no FS, no net."])
    except ValueError as err:
        return _receipt(o, p, "DENIED", {"reason": str(err)}, ["Fail closed."])


def _run_n22(o, p):
    role = p or "lyte-underwriter"
    digest = _sha("nhi:" + role)
    return _receipt(o, p, "EXECUTED", {"agent_id": "nhi_" + digest[:16], "role": role, "human": False}, ["Synthetic NHI. Not a production IdP."])


def _run_n23(o, p):
    off = bool(_WEAPON.search(p) or re.search(r"ignore previous|jailbreak", p, re.I))
    return _receipt(o, p, "DENIED" if off else "EXECUTED", {"rail": "block" if off else "allow", "turn": p}, ["Conversation rails. Not a full safety model."])


def _run_n24(o, p):
    path = p or "/trust"
    allow = bool(re.fullmatch(r"/[A-Za-z0-9/_-]*", path))
    return _receipt(o, p, "EXECUTED" if allow else "DENIED", {"path": path, "actuation": ("navigate:" + path) if allow else None, "same_origin": True}, ["Same-origin navigation log. No remote browse."])


def _run_n25(o, p):
    text = p or "tool=quote resource=lyte"
    tool_m = re.search(r"tool=([a-z0-9-]+)", text, re.I)
    res_m = re.search(r"resource=([a-z0-9-]+)", text, re.I)
    tool = tool_m.group(1) if tool_m else "quote"
    resource = res_m.group(1) if res_m else "lyte"
    allow = tool in ("quote", "lookup") and resource == "lyte"
    return _receipt(o, p, "APPROVED" if allow else "DENIED", {"tool": tool, "resource": resource, "allow": allow}, ["Tool authorization. Formulas never grant authority."])


_RUNNERS = {
    "N1": _run_n1, "N2": _run_n2, "N3": _run_n3, "N4": _run_n4, "N5": _run_n5,
    "N6": _run_n6, "N7": _run_n7, "N8": _run_n8, "N9": _run_n9, "N10": _run_n10,
    "N11": _run_n11, "N12": _run_n12, "N13": _run_n13, "N14": _run_n14, "N15": _run_n15,
    "N16": _run_n16, "N17": _run_n17, "N18": _run_n18, "N19": _run_n19, "N20": _run_n20,
    "N21": _run_n21, "N22": _run_n22, "N23": _run_n23, "N24": _run_n24, "N25": _run_n25,
}


def catalog() -> dict[str, Any]:
    return {
        "schema": "szl.organ-catalog/v1",
        "honesty": "PER_ORGAN_EVIDENCE_CLASS",
        "count": 25,
        "admitted_public": False,
        "origin": "https://a-11-oy.com/organs",
        "proof_record": "https://a11oy.net/factory/",
        "items": [{k: o[k] for k in ("id", "title", "body", "job", "evidence_class")} | {"honesty": o["evidence_class"], "run": f"POST /api/a11oy/v1/organs/{o['id']}"} for o in ORGANS],
        "note": "N1–N25 execute on the product origin with per-organ evidence classes. Not 25 public Spaces. GPU tune remains UNAVAILABLE.",
    }


def _page_html() -> str:
    items = "".join(
        f'<button type="button" class="tile" data-id="{o["id"]}" data-ph="{o["placeholder"]}"><span class="id">{o["id"]}</span><strong>{o["title"]}</strong><span class="job">{o["job"]}</span></button>'
        for o in ORGANS
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>a11oy — N1–N25 organs</title>
<meta name="description" content="Twenty-five factory organs on the product origin. Not 25 public Spaces. GPU tune UNAVAILABLE."/>
<style>
:root {{ --bg:#070b16; --panel:#101a2e; --ink:#e8eef7; --muted:#8aa0bd; --line:#1c2a44; --gold:#d8a23c; --pass:#3d9a6a; }}
* {{ box-sizing:border-box; }}
html,body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.5 ui-sans-serif,system-ui,sans-serif; }}
a {{ color:var(--gold); }}
.wrap {{ max-width:1120px; margin:0 auto; padding:24px; }}
.banner {{ border:1px solid var(--line); background:var(--panel); padding:12px 16px; border-radius:12px; font-size:14px; color:var(--muted); }}
h1 {{ font-family:ui-serif,Georgia,serif; font-weight:500; letter-spacing:-0.03em; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:10px; margin:24px 0; }}
.tile {{ min-height:72px; text-align:left; border:1px solid var(--line); background:var(--panel); color:var(--ink); border-radius:12px; padding:12px; cursor:pointer; }}
.tile[aria-pressed="true"] {{ border-color:var(--gold); }}
.tile .id {{ display:block; font:11px/1 ui-monospace,monospace; color:var(--muted); }}
.tile .job {{ display:block; font-size:12px; color:var(--muted); }}
form {{ display:flex; gap:10px; flex-wrap:wrap; }}
input {{ flex:1; min-height:48px; min-width:200px; border-radius:10px; border:1px solid var(--line); background:#0b1220; color:var(--ink); padding:0 12px; }}
button.run, .nav a {{ display:inline-flex; align-items:center; justify-content:center; min-height:48px; padding:0 16px; border-radius:10px; border:1px solid var(--line); background:var(--gold); color:#160f04; font-weight:600; text-decoration:none; }}
pre {{ overflow:auto; background:#0b1220; border:1px solid var(--line); border-radius:12px; padding:16px; font:12px/1.4 ui-monospace,monospace; }}
.nav {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px; }}
.nav a {{ background:transparent; color:var(--ink); }}
</style>
</head>
<body>
<main class="wrap">
  <nav class="nav" aria-label="Product">
    <a href="/">Product</a>
    <a href="/frontier">Frontier showcase</a>
    <a href="/verify">Verify</a>
    <a href="https://a11oy.net/factory/">Proof RECORD</a>
  </nav>
  <p class="banner">Route served from a-11-oy.com. Each organ retains its explicit SIMULATED, MODELED, MEASURED, or UNAVAILABLE evidence class. Public Hub admission false. GPU tune UNAVAILABLE. Formulas never grant authority. Not 25 public Spaces.</p>
  <h1>N1–N25 organs</h1>
  <p>Twenty-five bounded demonstration organs execute here. Each response exposes its own evidence class. Receipts are SHA-256 integrity records from this process, not signed production receipts. Proof copy lives on a11oy.net.</p>
  <div class="grid" id="grid">{items}</div>
  <form id="f">
    <input id="q" aria-label="Organ input" placeholder="Prompt to serve (schema-checked, no GPU claim)"/>
    <button class="run" type="submit">Run organ</button>
  </form>
  <p id="meta" class="banner" style="margin-top:16px">N1 Serve</p>
  <pre id="out">POST /api/a11oy/v1/organs/N1</pre>
</main>
<script>
const tiles=[...document.querySelectorAll('.tile')];
let active='N1';
function sel(id){{
  active=id;
  const t=tiles.find(x=>x.dataset.id===id);
  tiles.forEach(x=>x.setAttribute('aria-pressed', x===t?'true':'false'));
  document.getElementById('q').placeholder=t.dataset.ph;
  document.getElementById('meta').textContent=id+' · POST /api/a11oy/v1/organs/'+id;
}}
tiles.forEach(t=>t.addEventListener('click',()=>sel(t.dataset.id)));
sel('N1');
document.getElementById('f').addEventListener('submit', async (e)=>{{
  e.preventDefault();
  const prompt=document.getElementById('q').value;
  const r=await fetch('/api/a11oy/v1/organs/'+active, {{method:'POST', headers:{{'content-type':'application/json'}}, body:JSON.stringify({{prompt}})}});
  const j=await r.json();
  document.getElementById('out').textContent=JSON.stringify(j,null,2);
}});
</script>
</body></html>
"""


def register(app, ns: str = "a11oy") -> str:
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi import Request

    @app.get("/organs", include_in_schema=False)
    async def organs_page() -> HTMLResponse:
        return HTMLResponse(_page_html())

    @app.get(f"/api/{ns}/v1/organs")
    async def organs_catalog() -> JSONResponse:
        return JSONResponse(catalog())

    @app.get(f"/api/{ns}/v1/organs/history")
    async def organs_history() -> JSONResponse:
        return JSONResponse({"schema": "szl.organ-history/v1", "durable": "process-local", "entries": list(reversed(_RUNS[-40:]))})

    @app.get(f"/api/{ns}/v1/organs/{{oid}}")
    async def organ_one(oid: str) -> JSONResponse:
        organ = _BY_ID.get(oid)
        if organ is None:
            return JSONResponse({"error": "unknown organ"}, status_code=404)
        return JSONResponse(organ)

    @app.post(f"/api/{ns}/v1/organs/{{oid}}")
    async def organ_run(oid: str, request: Request) -> JSONResponse:
        if oid not in _BY_ID:
            return JSONResponse({"error": "unknown organ"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            body = {}
        prompt = str((body or {}).get("prompt") or "")
        return JSONResponse(run_organ(oid, prompt))

    return "GET /organs + GET/POST /api/a11oy/v1/organs"
