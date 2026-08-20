# SPDX-License-Identifier: MIT
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by A11oy Full-Stack Team. Co-Authored-By: Perplexity Computer Agent.
#
# THIRD-PARTY PATTERN ADOPTION (fashion-thinking, NOTICE attribution):
#   ngraph.leiden — anvaka/ngraph.leiden — MIT License —
#   https://github.com/anvaka/ngraph.leiden
#   We adopt the PATTERN of fast, DETERMINISTIC community detection (Leiden/Louvain
#   modularity optimization) on a graph. We EVOLVE it from a generic graph utility
#   into "Consensus Clusters": we build a similarity graph over the substrate's
#   governed DECISION NODES (edges weighted by shared sensitivity class, mission
#   tier and chosen-model family) and run a clean-room Louvain modularity optimizer
#   to surface clusters of mutually-reinforcing decisions — and the isolated
#   OUTLIERS that warrant operator attention. Original, dependency-free
#   implementation (no ngraph/JS source, no torch/numpy). Rendered with the
#   ALREADY-VENDORED cytoscape.min.js (/vendor/*, 0 CDN). Λ = Conjecture 1.
"""szl_consensus_clusters — ADDITIVE decision-node clustering tab + API.

Endpoints (mounted before the SPA catch-all):
  GET  /consensus-clusters                          — operator tab (HTML, cytoscape 0 CDN)
  GET  /api/a11oy/v1/clusters/graph                  — clustered decision graph (cytoscape elements)
  GET  /api/a11oy/v1/clusters/summary                — modularity, cluster sizes, outliers

Decision nodes come from the REAL governance Khipu chain (szl_khipu). If no
decisions exist yet, a small in-substrate seed graph (the doctrine relationships)
is clustered so the algorithm is demonstrably real. Doctrine v11 LOCKED 749/14/163.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1"}


# ---------------------------------------------------------------------------
# Build a weighted similarity graph over governed decisions.
# ---------------------------------------------------------------------------
def _decision_nodes() -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    try:
        import szl_khipu  # type: ignore
        dag = szl_khipu.get_dag("governance-gateway", ns="a11oy")
        for r in dag.tail(200):
            nodes.append({
                "id": (r.get("digest") or "")[:16] or f"seq{r.get('seq')}",
                "label": f"#{r.get('seq','?')}",
                "sens": str(r.get("sensitivity") or r.get("class") or "PUBLIC"),
                "tier": str(r.get("min_tier") or r.get("zone") or "T?"),
                "model": str(r.get("chosen") or "—"),
            })
    except Exception:
        pass
    if nodes:
        return nodes
    # Honest seed: the substrate's own doctrine relationships (so clustering is real
    # even before decisions are driven). Three natural families.
    return [
        {"id": "d-airgap", "label": "air-gap", "sens": "SECRET", "tier": "T2", "model": "olmo"},
        {"id": "d-classified", "label": "classified", "sens": "SECRET", "tier": "T2", "model": "deepseek"},
        {"id": "d-restricted", "label": "restricted", "sens": "RESTRICTED", "tier": "T1", "model": "qwen3"},
        {"id": "d-internal", "label": "internal", "sens": "INTERNAL", "tier": "T2", "model": "claude"},
        {"id": "d-roadmap", "label": "roadmap", "sens": "INTERNAL", "tier": "T2", "model": "claude"},
        {"id": "d-public", "label": "public", "sens": "PUBLIC", "tier": "T5", "model": "gemini"},
        {"id": "d-triage", "label": "triage", "sens": "PUBLIC", "tier": "T1", "model": "qwen3"},
        {"id": "d-research", "label": "research", "sens": "PUBLIC", "tier": "T5", "model": "gemini"},
    ]


def _build_weighted_graph() -> tuple[list[dict[str, Any]], dict[tuple[str, str], float]]:
    nodes = _decision_nodes()
    weights: dict[tuple[str, str], float] = {}
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            w = 0.0
            if a["sens"] == b["sens"]:
                w += 1.5
            if a["tier"] == b["tier"]:
                w += 1.0
            if a["model"] == b["model"] and a["model"] != "—":
                w += 1.0
            if w > 0:
                weights[(a["id"], b["id"])] = w
    return nodes, weights


# ---------------------------------------------------------------------------
# Clean-room Louvain modularity optimization (deterministic single pass + refine).
# ---------------------------------------------------------------------------
def _louvain(nodes: list[dict[str, Any]],
             weights: dict[tuple[str, str], float]) -> dict[str, int]:
    ids = [n["id"] for n in nodes]
    adj: dict[str, dict[str, float]] = {i: {} for i in ids}
    m2 = 0.0  # 2m (sum of all edge weights, counted once per pair → 2x in degree sums)
    for (u, v), w in weights.items():
        adj[u][v] = adj[u].get(v, 0.0) + w
        adj[v][u] = adj[v].get(u, 0.0) + w
        m2 += 2 * w
    if m2 == 0:
        return {i: idx for idx, i in enumerate(ids)}
    k = {i: sum(adj[i].values()) for i in ids}
    comm = {i: idx for idx, i in enumerate(ids)}  # start: singleton communities
    sigma_tot: dict[int, float] = {idx: k[i] for idx, i in enumerate(ids)}

    improved = True
    passes = 0
    while improved and passes < 20:
        improved = False
        passes += 1
        for i in ids:
            ci = comm[i]
            # remove i from its community
            sigma_tot[ci] -= k[i]
            # weight from i to each neighboring community
            wj: dict[int, float] = {}
            for j, w in adj[i].items():
                wj[comm[j]] = wj.get(comm[j], 0.0) + w
            best_c, best_gain = ci, 0.0
            for c, wic in wj.items():
                gain = wic - sigma_tot.get(c, 0.0) * k[i] / m2
                if gain > best_gain:
                    best_gain, best_c = gain, c
            # also consider staying (gain of own community already removed)
            comm[i] = best_c
            sigma_tot[best_c] = sigma_tot.get(best_c, 0.0) + k[i]
            if best_c != ci:
                improved = True
    # relabel communities 0..N-1 deterministically
    relabel: dict[int, int] = {}
    for i in ids:
        c = comm[i]
        if c not in relabel:
            relabel[c] = len(relabel)
        comm[i] = relabel[c]
    return comm


def _modularity(nodes, weights, comm) -> float:
    ids = [n["id"] for n in nodes]
    m2 = 2 * sum(weights.values())
    if m2 == 0:
        return 0.0
    k: dict[str, float] = {i: 0.0 for i in ids}
    for (u, v), w in weights.items():
        k[u] += w
        k[v] += w
    q = 0.0
    for (u, v), w in weights.items():
        if comm[u] == comm[v]:
            q += 2 * (w - k[u] * k[v] / m2)
    # diagonal (self) terms are zero here (no self-loops)
    return round(q / m2, 4)


_PALETTE = ["#3fb950", "#1f6feb", "#d9b46a", "#f85149", "#a371f7", "#db61a2", "#56d4dd", "#e3b341"]


def build_graph() -> dict[str, Any]:
    nodes, weights = _build_weighted_graph()
    comm = _louvain(nodes, weights)
    cy_nodes = []
    for n in nodes:
        c = comm[n["id"]]
        cy_nodes.append({"data": {
            "id": n["id"], "label": n["label"], "cluster": c,
            "color": _PALETTE[c % len(_PALETTE)],
            "sens": n["sens"], "tier": n["tier"], "model": n["model"]}})
    cy_edges = []
    for (u, v), w in weights.items():
        intra = comm[u] == comm[v]
        cy_edges.append({"data": {
            "id": f"e-{u}-{v}", "source": u, "target": v,
            "weight": w, "intra": intra}})
    return {"nodes": cy_nodes, "edges": cy_edges, "communities": comm,
            "node_count": len(cy_nodes), "edge_count": len(cy_edges)}


def summarize() -> dict[str, Any]:
    nodes, weights = _build_weighted_graph()
    comm = _louvain(nodes, weights)
    sizes: dict[int, int] = {}
    for c in comm.values():
        sizes[c] = sizes.get(c, 0) + 1
    outliers = [nid for nid, c in comm.items() if sizes[c] == 1]
    q = _modularity(nodes, weights, comm)
    seeded = not _has_live_decisions()
    return {
        "node_count": len(nodes), "edge_count": len(weights),
        "cluster_count": len(sizes), "modularity": q,
        "cluster_sizes": [{"cluster": c, "size": s} for c, s in sorted(sizes.items())],
        "consensus_clusters": sum(1 for s in sizes.values() if s >= 2),
        "outliers": outliers,
        "algorithm": "Louvain modularity optimization (clean-room, deterministic), evolved from anvaka/ngraph.leiden (MIT)",
        "seeded": seeded,
        "hint": ("clustering the in-substrate doctrine seed graph — drive /governance-gateway to cluster real decisions"
                 if seeded else None),
    }


def _has_live_decisions() -> bool:
    try:
        import szl_khipu  # type: ignore
        dag = szl_khipu.get_dag("governance-gateway", ns="a11oy")
        return len(dag.tail(1)) > 0
    except Exception:
        return False


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/clusters/graph", include_in_schema=False)
    async def _graph() -> JSONResponse:
        g = build_graph()
        return JSONResponse({"doctrine": DOCTRINE, "nodes": g["nodes"], "edges": g["edges"],
                             "node_count": g["node_count"], "edge_count": g["edge_count"],
                             "pattern_source": "anvaka/ngraph.leiden (MIT) — community detection, evolved to consensus clusters"})

    @app.get(f"/api/{ns}/v1/clusters/summary", include_in_schema=False)
    async def _summary() -> JSONResponse:
        return JSONResponse({"doctrine": DOCTRINE, **summarize()})

    @app.get("/consensus-clusters", include_in_schema=False)
    async def _page() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML)

    return f"consensus-clusters mounted: GET /consensus-clusters + /api/{ns}/v1/clusters/(graph|summary)"


_PAGE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>a11oy · Consensus Clusters</title>
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
#cy{width:100%;height:460px;background:#0d141c;border:1px solid var(--line);border-radius:10px}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.green{background:rgba(63,185,80,.15);color:var(--green)}
.blue{background:rgba(31,111,235,.18);color:#79b8ff}
pre{background:#0d141c;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;font-size:12.5px;white-space:pre-wrap}
.foot{color:var(--muted);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:12px}
code{color:var(--gold)}
</style></head>
<body><div class="wrap">
<h1>Consensus Clusters <span class="pill blue">Louvain</span></h1>
<p class="sub">Builds a similarity graph over governed <b>decision nodes</b> (edges weighted by shared
sensitivity, mission tier and model family) and runs modularity optimization to surface
<b>consensus clusters</b> of mutually-reinforcing decisions — and the isolated <b>outliers</b>
worth an operator's attention. Pattern from <code>anvaka/ngraph.leiden</code> (MIT), evolved.
Rendered with vendored cytoscape (0&nbsp;CDN).</p>

<div class="card">
<div class="row" style="justify-content:space-between">
<div id="legend" class="row"></div>
<button id="ref">Recompute clusters</button>
</div>
<div id="cy" style="margin-top:12px"></div>
<pre id="sum" style="margin-top:12px">Computing communities…</pre>
</div>

<p class="foot">a11oy · Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 ·
pattern: anvaka/ngraph.leiden (MIT), evolved · sovereign 0-CDN (vendored cytoscape).</p>
</div>
<script>
const $=s=>document.querySelector(s);
let cy=null;
async function load(){
  const g=await(await fetch('/api/a11oy/v1/clusters/graph')).json();
  const s=await(await fetch('/api/a11oy/v1/clusters/summary')).json();
  if(cy)cy.destroy();
  cy=cytoscape({container:$('#cy'),elements:[].concat(g.nodes,g.edges),
    style:[
      {selector:'node',style:{'background-color':'data(color)','label':'data(label)',
        'color':'#e8eef5','font-size':'10px','text-valign':'top','width':24,'height':24,
        'border-width':2,'border-color':'#0b0f14'}},
      {selector:'edge[?intra]',style:{'line-color':'#3fb950','width':'mapData(weight,0,3,1,5)','opacity':0.7,'curve-style':'haystack'}},
      {selector:'edge[!intra]',style:{'line-color':'#33425a','width':1,'opacity':0.35,'line-style':'dotted','curve-style':'haystack'}}
    ],
    layout:{name:'cose',animate:false,padding:24,nodeRepulsion:9000,idealEdgeLength:70}});
  const leg=$('#legend');leg.innerHTML='';
  const colors=[...new Set(g.nodes.map(n=>n.data.color))];
  colors.forEach((c,i)=>{const sp=document.createElement('span');sp.className='pill';
    sp.style.background=c+'33';sp.style.color=c;sp.textContent='cluster '+i;leg.appendChild(sp);
    leg.appendChild(document.createTextNode(' '));});
  $('#sum').textContent='nodes='+s.node_count+'  edges='+s.edge_count
    +'  clusters='+s.cluster_count+'  modularity Q='+s.modularity
    +'  consensus_clusters='+s.consensus_clusters+'  outliers='+(s.outliers.length)
    +'\\n'+s.algorithm+(s.seeded?('\\n\\nNOTE: '+s.hint):'')
    +'\\n\\ncluster sizes:\\n'+JSON.stringify(s.cluster_sizes,null,2)
    +(s.outliers.length?('\\noutliers: '+s.outliers.join(', ')):'');
}
$('#ref').addEventListener('click',load);
load();
</script>
</body></html>"""
