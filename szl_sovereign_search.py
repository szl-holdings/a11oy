# SPDX-License-Identifier: MIT
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by A11oy Full-Stack Team. Co-Authored-By: Perplexity Computer Agent.
#
# THIRD-PARTY PATTERN ADOPTION (fashion-thinking, NOTICE attribution):
#   tantivy-wasm — phiresky/tantivy-wasm — MIT License —
#   https://github.com/phiresky/tantivy-wasm
#   We adopt the PATTERN of a SOVEREIGN, in-deployment full-text search engine that
#   needs NO external Elasticsearch/Meilisearch service and NO network egress — the
#   index lives with the data and queries are answered locally. tantivy-wasm proves
#   this by running the Rust Tantivy engine in WASM and fetching index segments via
#   HTTP range requests. We EVOLVE the IDEA into a dependency-free, stdlib-only
#   server-side BM25 engine that indexes the a11oy GOVERNANCE CORPUS (decision
#   receipts, model catalog, doctrine docs, gates manifest) so an operator can run
#   sub-second relevance search over the entire governed-AI substrate with ZERO
#   backend service and ZERO CDN — the literal air-gap requirement. Original,
#   clean-room implementation; no Tantivy/Rust/WASM code; no torch/numpy.
"""szl_sovereign_search — ADDITIVE in-substrate full-text search tab + API.

Endpoints (mounted before the SPA catch-all):
  GET  /sovereign-search                           — operator tab (HTML, 0 CDN)
  GET  /api/a11oy/v1/search/corpus                  — corpus stats (docs, terms)
  GET  /api/a11oy/v1/search/query?q=...&k=...        — BM25 ranked results
  GET  /api/a11oy/v1/search/reindex                  — rebuild the index from live sources

The corpus is assembled from REAL a11oy substrate:
  • the live governance model catalog (szl_governance_gateway, if present)
  • governance decision receipts (szl_khipu DAG, if present)
  • doctrine / disclosure snippets shipped in-image
The BM25 ranker is a textbook Okapi BM25 (k1=1.5, b=0.75) computed over the live
corpus — no external service. Λ = Conjecture 1. Doctrine v11 LOCKED 749/14/163.
"""
from __future__ import annotations

import math
import re
import time
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1"}

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-_.]*")
# Minimal English stop list — keeps the index lean without external NLTK data.
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on",
    "with", "as", "by", "at", "be", "this", "that", "it", "from", "we", "our",
}


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOP and len(t) > 1]


# ---------------------------------------------------------------------------
# Corpus assembly — every document is sourced from a REAL a11oy substrate.
# ---------------------------------------------------------------------------
def _corpus() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []

    # 1) Governance model catalog (the routing decision substrate).
    try:
        import szl_governance_gateway as _gg  # type: ignore
        for m in getattr(_gg, "CATALOG", []) or []:
            docs.append({
                "id": f"model:{m.get('id')}",
                "kind": "model",
                "title": f"{m.get('id')} · {m.get('tier','?')}/{m.get('zone','?')}",
                "body": " ".join(str(v) for v in m.values()),
                "ref": "/governance-gateway",
            })
    except Exception:
        pass

    # 2) Governance decision receipts (real Khipu hash-chain).
    try:
        import szl_khipu  # type: ignore
        dag = szl_khipu.get_dag("governance-gateway", ns="a11oy")
        for r in dag.tail(200):
            docs.append({
                "id": f"receipt:{(r.get('digest') or '')[:16]}",
                "kind": "receipt",
                "title": f"decision #{r.get('seq','?')} · {r.get('action','?')}",
                "body": " ".join(str(v) for v in r.values()),
                "ref": "/gor-audit",
            })
    except Exception:
        pass

    # 3) Doctrine / disclosure corpus shipped in-image (always available — gives the
    #    search engine a non-empty corpus even before any decision is driven).
    docs.extend(_DOCTRINE_DOCS)
    return docs


# Curated, in-image doctrine snippets (the substrate's own governed knowledge).
_DOCTRINE_DOCS: list[dict[str, Any]] = [
    {"id": "doc:airgap", "kind": "doctrine", "title": "Air-gap sovereignty floor", "ref": "/governance-gateway",
     "body": "RESTRICTED and SECRET classified data force air-gap routing and may never leave for cloud "
             "endpoints. The sovereign floor guarantees governed decisions on classified material run on "
             "self-hosted, clean-lineage weights with zero network egress."},
    {"id": "doc:khipu", "kind": "doctrine", "title": "Khipu hash-chained receipts", "ref": "/gor-audit",
     "body": "Every governed decision is signed as a hash-chained Khipu receipt with sequence, digest and "
             "prev-link so the entire decision history is tamper-evident and replayable for audit."},
    {"id": "doc:lambda", "kind": "doctrine", "title": "Lambda is Conjecture 1", "ref": "/",
     "body": "The Lambda quantity is labelled Conjecture 1 — an honest, unproven conjecture. The doctrine "
             "locks exactly the proven formulas and never overstates the proof status of any claim."},
    {"id": "doc:budget", "kind": "doctrine", "title": "Budget-tier decision routing", "ref": "/budget-router",
     "body": "Mission constraints map to budget tiers: Tactical demands sub-second low-tier inference, "
             "Operational allows mid-tier reasoning, Strategic permits high-tier chain-of-thought. The router "
             "selects the cheapest tier that satisfies the decision risk so sovereign hardware is never choked."},
    {"id": "doc:consensus", "kind": "doctrine", "title": "Consensus clusters of decisions", "ref": "/consensus-clusters",
     "body": "Related governed-AI decision nodes are grouped into consensus clusters by community detection so "
             "operators can see which decisions reinforce one another and which are isolated outliers."},
    {"id": "doc:mission-ledger", "kind": "doctrine", "title": "Mission Ledger knowledge graph", "ref": "/mission-ledger",
     "body": "The Mission Ledger links documents, mission objectives and the resulting AI decisions into one "
             "heterogeneous knowledge graph so the provenance from source material to governed action is explicit."},
]


# ---------------------------------------------------------------------------
# BM25 index (Okapi BM25, stdlib-only).
# ---------------------------------------------------------------------------
class _Bm25Index:
    K1 = 1.5
    B = 0.75

    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []
        self.tokens: list[list[str]] = []
        self.df: dict[str, int] = {}
        self.avgdl: float = 0.0
        self.built_at: float = 0.0

    def build(self) -> None:
        self.docs = _corpus()
        self.tokens = [_tokenize(d["title"] + " " + d["body"]) for d in self.docs]
        self.df = {}
        for toks in self.tokens:
            for t in set(toks):
                self.df[t] = self.df.get(t, 0) + 1
        n = len(self.tokens)
        self.avgdl = (sum(len(t) for t in self.tokens) / n) if n else 0.0
        self.built_at = time.time()

    def _idf(self, term: str) -> float:
        n = len(self.docs)
        df = self.df.get(term, 0)
        # BM25 idf with +1 to keep it non-negative.
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def query(self, q: str, k: int = 8) -> list[dict[str, Any]]:
        qterms = _tokenize(q)
        if not qterms or not self.docs:
            return []
        scored: list[tuple[float, int, list[str]]] = []
        for i, toks in enumerate(self.tokens):
            if not toks:
                continue
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            dl = len(toks)
            score = 0.0
            hits: list[str] = []
            for term in qterms:
                f = tf.get(term, 0)
                if f == 0:
                    continue
                hits.append(term)
                idf = self._idf(term)
                denom = f + self.K1 * (1 - self.B + self.B * dl / (self.avgdl or 1))
                score += idf * (f * (self.K1 + 1)) / (denom or 1)
            if score > 0:
                scored.append((score, i, hits))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[dict[str, Any]] = []
        for score, i, hits in scored[:k]:
            d = self.docs[i]
            out.append({
                "id": d["id"], "kind": d["kind"], "title": d["title"], "ref": d.get("ref"),
                "score": round(score, 4), "matched_terms": hits,
                "snippet": _snippet(d["body"], hits),
            })
        return out

    def stats(self) -> dict[str, Any]:
        kinds: dict[str, int] = {}
        for d in self.docs:
            kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
        return {
            "doc_count": len(self.docs),
            "unique_terms": len(self.df),
            "avg_doc_len": round(self.avgdl, 2),
            "by_kind": kinds,
            "built_at": self.built_at,
            "ranker": "Okapi BM25 (k1=1.5, b=0.75), stdlib-only, 0 service",
        }


def _snippet(body: str, hits: list[str]) -> str:
    low = body.lower()
    pos = -1
    for h in hits:
        p = low.find(h)
        if p >= 0:
            pos = p
            break
    if pos < 0:
        return body[:160]
    start = max(0, pos - 60)
    return ("…" if start else "") + body[start:start + 200] + ("…" if start + 200 < len(body) else "")


_INDEX = _Bm25Index()


def register(app: FastAPI, ns: str = "a11oy") -> str:
    _INDEX.build()

    @app.get(f"/api/{ns}/v1/search/corpus", include_in_schema=False)
    async def _corpus_stats() -> JSONResponse:
        if not _INDEX.docs:
            _INDEX.build()
        return JSONResponse({"doctrine": DOCTRINE, **_INDEX.stats(),
                             "pattern_source": "phiresky/tantivy-wasm (MIT) — sovereign in-deployment search, evolved to stdlib BM25"})

    @app.get(f"/api/{ns}/v1/search/query", include_in_schema=False)
    async def _query(q: str = "", k: int = 8) -> JSONResponse:
        if not _INDEX.docs:
            _INDEX.build()
        k = max(1, min(int(k or 8), 25))
        results = _INDEX.query(q, k)
        return JSONResponse({"doctrine": DOCTRINE, "query": q, "k": k,
                             "result_count": len(results), "results": results})

    @app.get(f"/api/{ns}/v1/search/reindex", include_in_schema=False)
    async def _reindex() -> JSONResponse:
        _INDEX.build()
        return JSONResponse({"doctrine": DOCTRINE, "reindexed": True, **_INDEX.stats()})

    @app.get("/sovereign-search", include_in_schema=False)
    async def _page() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML)

    return f"sovereign-search mounted: GET /sovereign-search + /api/{ns}/v1/search/(corpus|query|reindex)"


_PAGE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>a11oy · Sovereign Corpus Search</title>
<style>
:root{--bg:#0b0f14;--panel:#121922;--ink:#e8eef5;--muted:#8aa0b4;--gold:#d9b46a;
--green:#3fb950;--blue:#1f6feb;--line:#1e2a36;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:920px;margin:0 auto;padding:24px 18px 64px}
h1{font-size:24px;margin:.2em 0}.sub{color:var(--muted);margin:0 0 18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input{flex:1;min-width:200px;background:#0d141c;border:1px solid var(--line);border-radius:8px;
color:var(--ink);padding:10px 12px;font-size:15px}
button{background:var(--gold);color:#1a1205;border:0;border-radius:8px;padding:10px 16px;font-weight:700;cursor:pointer}
button:hover{filter:brightness(1.08)}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.green{background:rgba(63,185,80,.15);color:var(--green)}
.blue{background:rgba(31,111,235,.18);color:#79b8ff}
.res{border-top:1px solid var(--line);padding:12px 0}
.res:first-child{border-top:0}
.res .t{font-weight:700}.res .m{color:var(--muted);font-size:13px}
.kind{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--gold)}
.sc{float:right;color:var(--green);font-variant-numeric:tabular-nums}
a{color:#79b8ff}
.foot{color:var(--muted);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:12px}
code{color:var(--gold)}
.stat{color:var(--muted);font-size:13px;margin-top:8px}
.chips{margin-top:10px}.chip{display:inline-block;margin:2px 4px 2px 0;padding:4px 10px;border:1px solid var(--line);
border-radius:999px;font-size:12px;color:var(--muted);cursor:pointer;background:#0d141c}
.chip:hover{border-color:var(--gold);color:var(--gold)}
</style></head>
<body><div class="wrap">
<h1>Sovereign Corpus Search <span class="pill green">0 CDN · 0 service</span></h1>
<p class="sub">Sub-second BM25 relevance search over the entire a11oy governed-AI substrate —
model catalog, decision receipts and doctrine — answered <b>locally</b>, with no Elasticsearch,
no Meilisearch and no network egress. Pattern from <code>phiresky/tantivy-wasm</code> (MIT),
evolved into a dependency-free server-side Okapi&nbsp;BM25 engine (the air-gap search story).</p>

<div class="card">
<div class="row">
<input id="q" placeholder="search the governance corpus (e.g. air-gap classified, budget tier, khipu receipt)…" />
<button id="go">Search</button>
<button id="rx" style="background:#1f6feb;color:#fff">Reindex</button>
</div>
<div class="chips" id="chips">
<span class="chip">air-gap classified</span>
<span class="chip">budget tier mission</span>
<span class="chip">khipu hash-chain receipt</span>
<span class="chip">consensus cluster</span>
<span class="chip">conjecture lambda</span>
</div>
<div class="stat" id="stat">Building index…</div>
</div>

<div class="card" id="resCard" style="display:none">
<div id="res"></div>
</div>

<p class="foot">a11oy · Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 ·
pattern: phiresky/tantivy-wasm (MIT), evolved · sovereign 0-CDN (no JS deps at all).</p>
</div>
<script>
const $=s=>document.querySelector(s);
async function stats(){
  const s=await(await fetch('/api/a11oy/v1/search/corpus')).json();
  const bk=Object.entries(s.by_kind||{}).map(([k,v])=>k+'='+v).join(', ');
  $('#stat').textContent='index ready · '+s.doc_count+' docs ('+bk+') · '
    +s.unique_terms+' unique terms · '+s.ranker;
}
async function run(q){
  if(!q){return}
  const d=await(await fetch('/api/a11oy/v1/search/query?q='+encodeURIComponent(q)+'&k=8')).json();
  const box=$('#res'); box.innerHTML='';
  $('#resCard').style.display='block';
  if(!d.results.length){box.innerHTML='<div class="res m">No matches in the governed corpus for “'+q+'”.</div>';return}
  for(const r of d.results){
    const el=document.createElement('div');el.className='res';
    el.innerHTML='<span class="sc">'+r.score.toFixed(3)+'</span>'
      +'<div class="kind">'+r.kind+'</div>'
      +'<div class="t">'+r.title+'</div>'
      +'<div class="m">'+r.snippet+'</div>'
      +'<div class="m">matched: '+r.matched_terms.join(', ')
      +(r.ref?(' · <a href="'+r.ref+'">'+r.ref+'</a>'):'')+'</div>';
    box.appendChild(el);
  }
}
$('#go').addEventListener('click',()=>run($('#q').value));
$('#q').addEventListener('keydown',e=>{if(e.key==='Enter')run($('#q').value)});
$('#rx').addEventListener('click',async()=>{await fetch('/api/a11oy/v1/search/reindex');stats();});
document.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>{
  $('#q').value=c.textContent;run(c.textContent);}));
stats();
</script>
</body></html>"""
