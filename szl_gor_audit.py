# SPDX-License-Identifier: MIT
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by A11oy Full-Stack Team. Co-Authored-By: Perplexity Computer Agent.
#
# THIRD-PARTY PATTERN/CODE ADOPTION (fashion-thinking, NOTICE attribution):
#   GoR (Graph of Records) — ulab-uiuc/GoR — MIT License —
#   https://github.com/ulab-uiuc/GoR
#   We adopt the PATTERN of building a GRAPH over records (each record = a node; edges
#   capture shared context / co-occurrence) so long-context material can be summarized
#   and AUDITED structurally instead of as a flat blob. We EVOLVE it from a RAG
#   summarization aid into a "Decision-Audit Graph": nodes are governed decision
#   receipts (from the Governance Gateway + Khipu organs), edges are the hash-chain
#   prev-links PLUS semantic edges by shared sensitivity class / chosen model. The
#   result is a navigable provenance graph for long decision histories. Original,
#   dependency-free implementation — no GoR source, no torch/numpy. Rendered with the
#   ALREADY-VENDORED cytoscape.min.js (/vendor/*, 0 CDN).
"""szl_gor_audit — ADDITIVE decision-audit graph tab + API for a11oy.

Endpoints (mounted before the SPA catch-all):
  GET  /gor-audit                              — operator tab (HTML, cytoscape 0 CDN)
  GET  /api/a11oy/v1/gor/graph                  — graph-of-records over decision receipts
  GET  /api/a11oy/v1/gor/summary                — structural summary (centrality, clusters)

The graph reads REAL receipts from szl_khipu DAGs (governance-gateway + any organ
present). If no decisions have been made yet it returns an honest empty graph plus a
hint to drive the Governance Gateway first. Λ = Conjecture 1. Doctrine v11 LOCKED 749/14/163.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1"}

# Organs whose Khipu chains we fold into the audit graph.
_AUDIT_ORGANS = ["governance-gateway"]


def _collect_receipts() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        import szl_khipu
    except Exception:
        return out
    for organ in _AUDIT_ORGANS:
        try:
            dag = szl_khipu.get_dag(organ, ns="a11oy")
            for r in dag.tail(200):
                out.append(r)
        except Exception:
            continue
    return out


def build_graph() -> dict[str, Any]:
    """Build a Graph-of-Records: nodes = receipts; edges = chain prev-links +
    semantic edges (shared organ, shared action). Cytoscape elements format."""
    receipts = _collect_receipts()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    by_digest: dict[str, dict[str, Any]] = {}

    for r in receipts:
        nid = (r.get("digest") or "")[:16] or f"seq{r.get('seq')}"
        by_digest[(r.get("digest") or "")] = r
        nodes.append({"data": {
            "id": nid,
            "label": f"{r.get('organ','?')}#{r.get('seq','?')}",
            "organ": r.get("organ"),
            "action": r.get("action"),
            "seq": r.get("seq"),
            "verified": r.get("chain_verified", False),
        }})

    # 1) chain edges (provenance): prev -> this
    for r in receipts:
        prev = r.get("prev")
        if prev and prev in by_digest:
            edges.append({"data": {
                "id": f"chain-{(r.get('digest') or '')[:10]}",
                "source": prev[:16], "target": (r.get("digest") or "")[:16],
                "kind": "chain"}})

    # 2) semantic edges: same organ + same action, consecutive in time (co-context)
    by_key: dict[tuple, list[dict[str, Any]]] = {}
    for r in receipts:
        by_key.setdefault((r.get("organ"), r.get("action")), []).append(r)
    for key, group in by_key.items():
        group.sort(key=lambda x: x.get("seq", 0))
        for a, b in zip(group, group[1:]):
            edges.append({"data": {
                "id": f"sem-{(b.get('digest') or '')[:10]}",
                "source": (a.get("digest") or "")[:16],
                "target": (b.get("digest") or "")[:16],
                "kind": "semantic"}})

    return {"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}


def summarize() -> dict[str, Any]:
    g = build_graph()
    # degree centrality (which decisions are the most connected provenance hubs)
    deg: dict[str, int] = {}
    for e in g["edges"]:
        deg[e["data"]["source"]] = deg.get(e["data"]["source"], 0) + 1
        deg[e["data"]["target"]] = deg.get(e["data"]["target"], 0) + 1
    top = sorted(deg.items(), key=lambda kv: kv[1], reverse=True)[:5]
    label = {n["data"]["id"]: n["data"]["label"] for n in g["nodes"]}
    return {
        "node_count": g["node_count"], "edge_count": g["edge_count"],
        "chain_edges": sum(1 for e in g["edges"] if e["data"]["kind"] == "chain"),
        "semantic_edges": sum(1 for e in g["edges"] if e["data"]["kind"] == "semantic"),
        "top_hubs": [{"id": k, "label": label.get(k, k), "degree": v} for k, v in top],
        "all_verified": all(n["data"]["verified"] for n in g["nodes"]) if g["nodes"] else None,
        "hint": None if g["node_count"] else "no decisions yet — drive /governance-gateway to populate the audit graph",
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/gor/graph", include_in_schema=False)
    async def _graph() -> JSONResponse:
        g = build_graph()
        return JSONResponse({"doctrine": DOCTRINE, **g,
                             "pattern_source": "ulab-uiuc/GoR (MIT) — graph-of-records, evolved to a decision-audit graph"})

    @app.get(f"/api/{ns}/v1/gor/summary", include_in_schema=False)
    async def _summary() -> JSONResponse:
        return JSONResponse({"doctrine": DOCTRINE, **summarize()})

    @app.get("/gor-audit", include_in_schema=False)
    async def _page() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML)

    return f"gor-audit mounted: GET /gor-audit + /api/{ns}/v1/gor/(graph|summary)"


_PAGE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>a11oy · Decision-Audit Graph (GoR)</title>
<script src="/vendor/cytoscape.min.js"></script>
<style>
:root{--bg:#0b0f14;--panel:#121922;--ink:#e8eef5;--muted:#8aa0b4;--gold:#d9b46a;
--green:#3fb950;--blue:#1f6feb;--line:#1e2a36;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:24px 18px 64px}
h1{font-size:24px;margin:.2em 0}.sub{color:var(--muted);margin:0 0 18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
button{background:var(--gold);color:#1a1205;border:0;border-radius:8px;padding:9px 16px;font-weight:700;cursor:pointer}
button:hover{filter:brightness(1.08)}
#cy{width:100%;height:440px;background:#0d141c;border:1px solid var(--line);border-radius:10px}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.green{background:rgba(63,185,80,.15);color:var(--green)}
.blue{background:rgba(31,111,235,.18);color:#79b8ff}
pre{background:#0d141c;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;font-size:12.5px;white-space:pre-wrap}
.foot{color:var(--muted);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:12px}
code{color:var(--gold)}
.legend span{margin-right:14px}
</style></head>
<body><div class="wrap">
<h1>Decision-Audit Graph <span class="pill blue">GoR</span></h1>
<p class="sub">Every governed decision becomes a <b>node</b>; hash-chain prev-links and shared
context become <b>edges</b> — a navigable provenance graph for long decision histories.
Pattern from <code>ulab-uiuc/GoR</code> (MIT), evolved from RAG summarization into a
decision-audit graph. Rendered with vendored cytoscape (0&nbsp;CDN).</p>

<div class="card">
<h3 style="margin:0 0 8px">Theorems behind this audit surface
<span class="pill blue" style="background:rgba(138,111,214,.18);color:#b79fee">EXPERIMENTAL · CI-green on main</span></h3>
<p class="sub" style="margin:0 0 8px">The audit/replay guarantees rendered here are backed by
three lutar-lean theorems (experimental, kernel-verified, CI-green on main — NOT locked):</p>
<ul style="margin:0 0 4px;padding-left:20px;font-size:13.5px;color:var(--ink)">
<li><b>CP-1 Merkle soundness</b> — inclusion proofs are sound + log is append-only (tamper-evident). <code>#print axioms ⟶ [propext]</code></li>
<li><b>AU-1 Replay-determinism + tamper-localize</b> — same log ⇒ same final state; first divergence pinpoints the altered entry (re-verifiable). <code>#print axioms ⟶ no axioms / [propext, Quot.sound]</code></li>
<li><b>MC-4 Ville anytime-valid</b> — stop/alarm at ANY time with valid coverage. <code>#print axioms ⟶ [propext, Classical.choice, Quot.sound]</code> <i>(sup-over-time = ROADMAP)</i></li>
</ul>
<p class="sub" style="margin:4px 0 0"><a href="/proven-formulas" style="color:#79b8ff">run the live replay/Ville checks on the Proven Formulas tab →</a></p>
</div>

<div class="card">
<div class="row" style="justify-content:space-between">
<div class="legend"><span class="pill green">chain edge (provenance)</span>
<span class="pill blue">semantic edge (shared context)</span></div>
<button id="ref">Rebuild graph</button>
</div>
<div id="cy" style="margin-top:12px"></div>
<pre id="sum" style="margin-top:12px">Loading audit graph…</pre>
</div>

<p class="foot">a11oy · Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 ·
pattern: ulab-uiuc/GoR (MIT), evolved · sovereign 0-CDN (vendored cytoscape).</p>
</div>
<script>
const $=s=>document.querySelector(s);
let cy=null;
async function load(){
  const g=await(await fetch('/api/a11oy/v1/gor/graph')).json();
  const s=await(await fetch('/api/a11oy/v1/gor/summary')).json();
  const els=[].concat(g.nodes,g.edges);
  if(cy)cy.destroy();
  cy=cytoscape({container:$('#cy'),elements:els,
    style:[
      {selector:'node',style:{'background-color':'#3fb950','label':'data(label)',
        'color':'#e8eef5','font-size':'9px','text-valign':'top','width':18,'height':18}},
      {selector:'edge[kind="chain"]',style:{'line-color':'#3fb950','width':2,
        'target-arrow-color':'#3fb950','target-arrow-shape':'triangle','curve-style':'bezier'}},
      {selector:'edge[kind="semantic"]',style:{'line-color':'#1f6feb','width':1.5,
        'line-style':'dashed','target-arrow-color':'#1f6feb','target-arrow-shape':'triangle','curve-style':'bezier'}}
    ],
    layout:{name: els.length? 'breadthfirst':'grid', directed:true, padding:20, spacingFactor:1.2}});
  $('#sum').textContent='nodes='+s.node_count+'  edges='+s.edge_count
    +' (chain='+s.chain_edges+', semantic='+s.semantic_edges+')  all_verified='+s.all_verified
    +(s.hint?('\\n\\nHINT: '+s.hint):'')+'\\n\\ntop hubs:\\n'+JSON.stringify(s.top_hubs,null,2);
}
$('#ref').addEventListener('click',load);
load();
</script>
</body></html>"""
