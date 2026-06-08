# SPDX-License-Identifier: MIT
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by A11oy Full-Stack Team. Co-Authored-By: Perplexity Computer Agent.
#
# THIRD-PARTY PATTERN ADOPTION (fashion-thinking, NOTICE attribution):
#   research-arcade — ulab-uiuc/research-arcade — MIT License —
#   https://github.com/ulab-uiuc/research-arcade
#   We adopt the PATTERN of a HETEROGENEOUS GRAPH interface that unifies disparate
#   structured sources (papers, reviews, authors) into one graph with typed nodes
#   and graph-like CRUD. We EVOLVE it into a live "Mission Ledger": a heterogeneous
#   knowledge graph over THREE a11oy node types — DOCUMENTS (governed source
#   material), OBJECTIVES (mission goals) and DECISIONS (governed AI outputs, drawn
#   from the real Khipu chain) — with typed edges (cites, supports, resulted_in) so
#   the provenance from source material → mission objective → governed action is
#   explicit and auditable. Original, dependency-free implementation (no
#   research-arcade source, no SQL backend, no torch/numpy). Rendered with the
#   ALREADY-VENDORED cytoscape.min.js (/vendor/*, 0 CDN). Λ = Conjecture 1.
"""szl_mission_ledger — ADDITIVE heterogeneous knowledge-graph tab + API.

Endpoints (mounted before the SPA catch-all):
  GET  /mission-ledger                              — operator tab (HTML, cytoscape 0 CDN)
  GET  /api/a11oy/v1/ledger/graph                    — heterogeneous KG (cytoscape elements)
  GET  /api/a11oy/v1/ledger/summary                  — node/edge type counts, coverage

DECISION nodes are pulled from the REAL governance Khipu chain when present and
linked into the document/objective scaffold. Doctrine v11 LOCKED 749/14/163.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1"}

# In-substrate scaffold: documents + objectives (the governed mission context).
# These are real a11oy doctrine artifacts; decisions are appended from the live chain.
_DOCUMENTS = [
    {"id": "doc-roe", "label": "Rules of Engagement", "type": "document", "tag": "RESTRICTED"},
    {"id": "doc-airgap", "label": "Air-Gap Sovereignty Spec", "type": "document", "tag": "doctrine"},
    {"id": "doc-intel", "label": "Maritime Intel Brief", "type": "document", "tag": "RESTRICTED"},
    {"id": "doc-policy", "label": "Governance Policy Manifest", "type": "document", "tag": "doctrine"},
]
_OBJECTIVES = [
    {"id": "obj-sovereign", "label": "Run classified decisions air-gapped", "type": "objective"},
    {"id": "obj-audit", "label": "Keep every decision tamper-evident", "type": "objective"},
    {"id": "obj-cost", "label": "Minimize compute on time-critical calls", "type": "objective"},
]
# Static provenance edges in the scaffold (documents → objectives).
_SCAFFOLD_EDGES = [
    ("doc-roe", "obj-sovereign", "supports"),
    ("doc-airgap", "obj-sovereign", "cites"),
    ("doc-intel", "obj-sovereign", "supports"),
    ("doc-policy", "obj-audit", "cites"),
    ("doc-policy", "obj-cost", "supports"),
]
# Which objective a decision serves, inferred from its governance fields.
def _objective_for(rec: dict[str, Any]) -> str:
    sens = str(rec.get("sensitivity") or rec.get("class") or "").upper()
    if sens in ("RESTRICTED", "SECRET") or rec.get("airgap_required"):
        return "obj-sovereign"
    if str(rec.get("min_tier") or "").upper() in ("T0", "T1"):
        return "obj-cost"
    return "obj-audit"


def _decisions() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        import szl_khipu  # type: ignore
        dag = szl_khipu.get_dag("governance-gateway", ns="a11oy")
        for r in dag.tail(60):
            out.append(r)
    except Exception:
        pass
    return out


def build_graph() -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for d in _DOCUMENTS:
        nodes.append({"data": {**d}})
    for o in _OBJECTIVES:
        nodes.append({"data": {**o}})
    for (s, t, rel) in _SCAFFOLD_EDGES:
        edges.append({"data": {"id": f"e-{s}-{t}", "source": s, "target": t, "rel": rel}})

    decs = _decisions()
    for r in decs:
        did = "dec-" + ((r.get("digest") or "")[:12] or f"seq{r.get('seq')}")
        nodes.append({"data": {
            "id": did, "label": f"decision #{r.get('seq','?')}", "type": "decision",
            "model": str(r.get("chosen") or "—"), "sens": str(r.get("sensitivity") or "?")}})
        obj = _objective_for(r)
        edges.append({"data": {"id": f"e-{did}-{obj}", "source": obj, "target": did, "rel": "resulted_in"}})

    return {"nodes": nodes, "edges": edges,
            "node_count": len(nodes), "edge_count": len(edges),
            "decision_count": len(decs)}


def summarize() -> dict[str, Any]:
    g = build_graph()
    by_type: dict[str, int] = {}
    for n in g["nodes"]:
        t = n["data"].get("type", "?")
        by_type[t] = by_type.get(t, 0) + 1
    by_rel: dict[str, int] = {}
    for e in g["edges"]:
        rl = e["data"].get("rel", "?")
        by_rel[rl] = by_rel.get(rl, 0) + 1
    return {
        "node_count": g["node_count"], "edge_count": g["edge_count"],
        "node_types": by_type, "edge_types": by_rel,
        "decision_count": g["decision_count"],
        "structure": "heterogeneous KG — documents → objectives → decisions",
        "hint": (None if g["decision_count"]
                 else "scaffold only — drive /governance-gateway to attach real decisions to the ledger"),
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/ledger/graph", include_in_schema=False)
    async def _graph() -> JSONResponse:
        g = build_graph()
        return JSONResponse({"doctrine": DOCTRINE, **g,
                             "pattern_source": "ulab-uiuc/research-arcade (MIT) — heterogeneous graph interface, evolved to Mission Ledger"})

    @app.get(f"/api/{ns}/v1/ledger/summary", include_in_schema=False)
    async def _summary() -> JSONResponse:
        return JSONResponse({"doctrine": DOCTRINE, **summarize()})

    @app.get("/mission-ledger", include_in_schema=False)
    async def _page() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML)

    return f"mission-ledger mounted: GET /mission-ledger + /api/{ns}/v1/ledger/(graph|summary)"


_PAGE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>a11oy · Mission Ledger</title>
<script src="/vendor/cytoscape.min.js"></script>
<style>
:root{--bg:#0b0f14;--panel:#121922;--ink:#e8eef5;--muted:#8aa0b4;--gold:#d9b46a;
--green:#3fb950;--blue:#1f6feb;--purple:#a371f7;--line:#1e2a36;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:24px 18px 64px}
h1{font-size:24px;margin:.2em 0}.sub{color:var(--muted);margin:0 0 18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
button{background:var(--gold);color:#1a1205;border:0;border-radius:8px;padding:9px 16px;font-weight:700;cursor:pointer}
button:hover{filter:brightness(1.08)}
#cy{width:100%;height:460px;background:#0d141c;border:1px solid var(--line);border-radius:10px}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.doc{background:rgba(31,111,235,.18);color:#79b8ff}
.obj{background:rgba(217,180,106,.18);color:var(--gold)}
.dec{background:rgba(63,185,80,.15);color:var(--green)}
pre{background:#0d141c;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;font-size:12.5px;white-space:pre-wrap}
.foot{color:var(--muted);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:12px}
code{color:var(--gold)}
.legend span{margin-right:6px}
</style></head>
<body><div class="wrap">
<h1>Mission Ledger <span class="pill dec">knowledge graph</span></h1>
<p class="sub">A heterogeneous knowledge graph linking <span class="pill doc">documents</span>
(governed source material) → <span class="pill obj">objectives</span> (mission goals) →
<span class="pill dec">decisions</span> (governed AI outputs from the real Khipu chain), with typed
edges (<code>cites</code>, <code>supports</code>, <code>resulted_in</code>) so provenance from source
to action is explicit. Pattern from <code>ulab-uiuc/research-arcade</code> (MIT), evolved.
Rendered with vendored cytoscape (0&nbsp;CDN).</p>

<div class="card">
<div class="row" style="justify-content:space-between">
<div class="legend"><span class="pill doc">document</span><span class="pill obj">objective</span><span class="pill dec">decision</span></div>
<button id="ref">Refresh ledger</button>
</div>
<div id="cy" style="margin-top:12px"></div>
<pre id="sum" style="margin-top:12px">Loading mission ledger…</pre>
</div>

<p class="foot">a11oy · Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 ·
pattern: ulab-uiuc/research-arcade (MIT), evolved · sovereign 0-CDN (vendored cytoscape).</p>
</div>
<script>
const $=s=>document.querySelector(s);
let cy=null;
const COLOR={document:'#1f6feb',objective:'#d9b46a',decision:'#3fb950'};
async function load(){
  const g=await(await fetch('/api/a11oy/v1/ledger/graph')).json();
  const s=await(await fetch('/api/a11oy/v1/ledger/summary')).json();
  if(cy)cy.destroy();
  cy=cytoscape({container:$('#cy'),elements:[].concat(g.nodes,g.edges),
    style:[
      {selector:'node',style:{'background-color':ele=>COLOR[ele.data('type')]||'#888',
        'label':'data(label)','color':'#e8eef5','font-size':'9px','text-valign':'bottom',
        'text-margin-y':3,'width':22,'height':22}},
      {selector:'node[type="objective"]',style:{'shape':'round-rectangle','width':30,'height':22}},
      {selector:'node[type="decision"]',style:{'shape':'diamond'}},
      {selector:'edge',style:{'line-color':'#33425a','width':1.6,'curve-style':'bezier',
        'target-arrow-shape':'triangle','target-arrow-color':'#33425a','label':'data(rel)',
        'font-size':'7px','color':'#8aa0b4','text-rotation':'autorotate'}}
    ],
    layout:{name:'breadthfirst',directed:true,padding:24,spacingFactor:1.25}});
  $('#sum').textContent='nodes='+s.node_count+'  edges='+s.edge_count
    +'  decisions='+s.decision_count+'\\nnode types: '+JSON.stringify(s.node_types)
    +'\\nedge types: '+JSON.stringify(s.edge_types)
    +(s.hint?('\\n\\nHINT: '+s.hint):'');
}
$('#ref').addEventListener('click',load);
load();
</script>
</body></html>"""
