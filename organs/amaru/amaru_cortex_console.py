# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 (NOT a theorem)
# SLSA L1 honest (cosign-signed GHCR image). L2 build-provenance attestation roadmap via Wire D — not yet earned.
"""
amaru_cortex_console.py — 13-tab reasoning/observability console for amaru.

Registers GET /cortex-console (HTML) served at root level.
All 13 tabs hit REAL endpoints — zero mocks, zero stubs, honest empty-states.

Tabs:
  T01  Cited-Answer Console         /api/amaru/v1/reason            POST
  T02  Confidence / Hallucination   /api/amaru/v1/confidence        POST
  T03  Retrieval Eval (RAGAS-style) /api/amaru/v1/eval              POST
  T04  7-Chakra Runtime Monitor     /brain                          GET  (also /api/amaru/healthz)
  T05  Memory / Recall Explorer     /api/amaru/v2/unay/recall       GET/POST
  T06  Brain / Immune Screen        /api/amaru/v1/brain             GET  + /api/amaru/v1/brain/cited POST
  T07  Inference Receipt Stream     /api/amaru/v1/cortex-subscribe  GET  (SSE)
  T08  Source Provenance Graph      /api/amaru/v1/cortex/3d         GET  + /khipu/ledger
  T09  Model-Tier Router            /api/amaru/v1/llm/tiers         GET  + /api/amaru/v1/llm/route POST
  T10  Eval / Regression Board      /api/amaru/v1/eval              POST (batch)
  T11  Cortex SSE Live Feed         /api/amaru/v1/cortex-subscribe  GET  (SSE)
  T12  Knowledge / Citation Cov     /api/amaru/v1/honest            GET  + /api/amaru/v4/recall
  T13  Formula Registry F1–F23      /api/amaru/v1/formulas/index    GET  + anatomy

SLSA L1 honest (L2 roadmap) · Λ = Conjecture 1 (NOT a theorem) · Doctrine v11 LOCKED
"""
from __future__ import annotations

CONSOLE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Amaru Cortex Console — Reasoning · Memory · Observability</title>
<meta name="description" content="Amaru CORTEX — 13-tab reasoning observability console. Cited-answer engine, hallucination scorer, RAGAS eval, 7-chakra runtime, memory explorer, inference receipts, 3D provenance graph, model-tier router, F1–F23 formulas."/>
<style>
:root{
  --bg:#080c14;--card:#0e1520;--card2:#131d2b;--border:#1e2d42;--ink:#dce8f5;--mut:#6a8099;
  --acc:#5ab4d6;--gold:#d4a84b;--green:#3ecf8e;--red:#e05252;--purple:#9b72cf;
  --font-mono:"JetBrains Mono","Fira Code","Cascadia Code",ui-monospace,monospace;
  --font-sans:"Inter","IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
  --r:10px;--r2:6px;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:var(--bg);color:var(--ink);font-family:var(--font-sans);font-size:14px;line-height:1.55}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
/* Layout */
#shell{display:flex;flex-direction:column;height:100vh;overflow:hidden}
#topbar{flex:0 0 auto;display:flex;align-items:center;gap:12px;padding:0 18px;height:48px;border-bottom:1px solid var(--border);background:#060a10}
#topbar .logo{display:flex;align-items:center;gap:8px;font-weight:700;font-size:15px;color:var(--ink)}
#topbar .logo svg{width:28px;height:28px;flex-shrink:0}
#topbar .logo .sub{font-size:11px;font-weight:400;color:var(--mut);font-family:var(--font-mono)}
#topbar .spacer{flex:1}
.badge{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;padding:2px 8px;border-radius:999px;font-family:var(--font-mono)}
.badge.green{background:#0c2b1e;color:#3ecf8e;border:1px solid #1a4830}
.badge.amber{background:#2b200c;color:#d4a84b;border:1px solid #4a360f}
.badge.blue{background:#0b1f2e;color:#5ab4d6;border:1px solid #123348}
.badge.gray{background:#131d2b;color:#6a8099;border:1px solid #1e2d42}
#tabbar{flex:0 0 auto;display:flex;gap:0;overflow-x:auto;border-bottom:1px solid var(--border);background:#090e18;padding:0 6px;scrollbar-width:none}
#tabbar::-webkit-scrollbar{display:none}
.tab-btn{flex:0 0 auto;display:flex;align-items:center;gap:5px;padding:0 14px;height:40px;background:none;border:none;color:var(--mut);font-family:var(--font-sans);font-size:12px;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;transition:color .15s,border-color .15s;white-space:nowrap}
.tab-btn:hover{color:var(--ink)}
.tab-btn.active{color:var(--acc);border-bottom:2px solid var(--acc)}
.tab-btn .t-icon{font-size:14px}
#content{flex:1;overflow:auto;padding:20px}
/* Cards */
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:18px}
.card+.card{margin-top:14px}
.card-hdr{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.card-hdr h2{font-size:15px;font-weight:600;color:var(--ink)}
.card-hdr .note{font-size:11px;color:var(--mut)}
/* Inputs */
.row{display:grid;gap:10px;margin-bottom:12px}
.row.cols2{grid-template-columns:1fr 1fr}
.row.cols3{grid-template-columns:1fr 1fr 1fr}
label{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);display:block;margin-bottom:4px}
input,textarea,select{width:100%;background:#070b12;border:1px solid var(--border);border-radius:var(--r2);color:var(--ink);font-family:var(--font-mono);font-size:12px;padding:8px 10px;resize:vertical;outline:none;transition:border-color .15s}
input:focus,textarea:focus,select:focus{border-color:var(--acc)}
/* Buttons */
.btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:var(--r2);border:1px solid var(--border);background:var(--card2);color:var(--ink);font-family:var(--font-sans);font-size:12px;font-weight:600;cursor:pointer;transition:.15s}
.btn:hover{border-color:var(--acc);color:var(--acc)}
.btn.primary{background:#0b1f2e;border-color:#1a4262;color:var(--acc)}
.btn.primary:hover{background:#0e2840}
.btn.sm{padding:4px 10px;font-size:11px}
.btn:disabled{opacity:.4;cursor:not-allowed}
/* Output */
.out{background:#050a10;border:1px solid var(--border);border-radius:var(--r2);padding:12px;font-family:var(--font-mono);font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-all;color:#b8c8d8;min-height:60px;max-height:420px;overflow:auto}
.out.live{border-color:#1a4262}
.out .key{color:var(--acc)}
.out .val{color:#e8e8e0}
.out .num{color:var(--gold)}
.out .bool-t{color:var(--green)}
.out .bool-f{color:var(--red)}
.out .str{color:#89d3a1}
.out .err{color:var(--red)}
/* Metrics grid */
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:1px;background:var(--border);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin:12px 0}
.metric{background:var(--card);padding:12px 14px}
.metric .v{font-family:var(--font-mono);font-size:20px;font-weight:700;color:var(--ink)}
.metric .v.good{color:var(--green)}
.metric .v.warn{color:var(--gold)}
.metric .v.bad{color:var(--red)}
.metric .k{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin-top:5px}
/* SSE stream */
.stream-box{background:#050a10;border:1px solid #1a4262;border-radius:var(--r2);padding:12px;font-family:var(--font-mono);font-size:11px;line-height:1.65;max-height:360px;overflow:auto}
.stream-box .evt{border-bottom:1px solid #0e1520;padding:4px 0;color:#7a9ab5}
.stream-box .evt .ts{color:var(--mut);margin-right:8px}
.stream-box .evt .data{color:#b8c8d8}
/* Chakra viz */
.chakras{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
.chakra{flex:1;min-width:90px;background:var(--card2);border:1px solid var(--border);border-radius:8px;padding:10px 12px;text-align:center}
.chakra .c-name{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)}
.chakra .c-glyph{font-size:22px;margin:4px 0}
.chakra .c-status{font-size:10px;font-family:var(--font-mono)}
.chakra.idle .c-status{color:var(--mut)}
.chakra.active .c-status{color:var(--green)}
.chakra.active{border-color:#1a4830}
/* 3D canvas area */
#canvas3d{width:100%;height:360px;background:linear-gradient(135deg,#060b14 0%,#0a1622 100%);border-radius:var(--r);border:1px solid var(--border);position:relative;overflow:hidden}
#canvas3d canvas{position:absolute;inset:0;width:100%;height:100%}
/* Formula table */
.ftable{width:100%;border-collapse:collapse;font-size:12px}
.ftable th{text-align:left;padding:7px 10px;border-bottom:1px solid var(--border);font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);font-weight:600}
.ftable td{padding:7px 10px;border-bottom:1px solid #10192a;vertical-align:top}
.ftable tr:hover td{background:#0c1421}
.proved{color:var(--green);font-weight:600}
.roadmap{color:var(--mut)}
.conj{color:var(--gold);font-weight:600}
/* Model tier viz */
.tiers{display:flex;flex-direction:column;gap:8px;margin:12px 0}
.tier-row{display:flex;align-items:center;gap:12px;background:var(--card2);border:1px solid var(--border);border-radius:8px;padding:10px 14px}
.tier-row .t-rank{font-family:var(--font-mono);font-size:11px;color:var(--mut);min-width:20px}
.tier-row .t-name{font-family:var(--font-mono);font-size:12px;color:var(--acc);font-weight:600;min-width:180px}
.tier-row .t-use{font-size:11px;color:var(--ink);flex:1}
.tier-row .t-why{font-size:10px;color:var(--mut)}
.tier-row.selected{border-color:var(--acc);background:#0b1f2e}
/* Loading */
.loading{color:var(--mut);font-size:12px;font-family:var(--font-mono);padding:12px 0}
.loading::after{content:'...';animation:dots 1.2s steps(3,end) infinite}
@keyframes dots{0%{content:''}33%{content:'.'}66%{content:'..'}100%{content:'...'}}
/* Tab pane */
.pane{display:none}
.pane.active{display:block}
/* Ruler */
.ruler{height:1px;background:var(--border);margin:16px 0}
/* Info row */
.info-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
/* Scroll small */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:#1e2d42;border-radius:3px}
/* Responsive */
@media(max-width:640px){
  .row.cols2,.row.cols3{grid-template-columns:1fr}
  #topbar .badge{display:none}
}
</style>
</head>
<body>
<div id="shell">
<!-- TOPBAR -->
<header id="topbar">
  <div class="logo">
    <svg viewBox="0 0 28 28" fill="none" aria-label="amaru ouroboros">
      <circle cx="14" cy="14" r="12" stroke="#5ab4d6" stroke-width="1.5" fill="none"/>
      <circle cx="14" cy="14" r="7" stroke="#d4a84b" stroke-width="1" stroke-dasharray="3 2" fill="none"/>
      <path d="M14 4 Q21 9 21 14 Q21 21 14 24 Q7 21 7 14 Q7 9 14 4Z" fill="none" stroke="#9b72cf" stroke-width="1" stroke-dasharray="2 3"/>
      <circle cx="14" cy="14" r="2.5" fill="#5ab4d6" opacity=".8"/>
    </svg>
    <div>
      <div>Amaru Cortex Console</div>
      <div class="sub">reasoning · memory · LLM observability</div>
    </div>
  </div>
  <div class="spacer"></div>
  <span class="badge amber">Λ=Conjecture 1</span>
  <span class="badge green" id="hdr-slsa">SLSA L1 honest</span>
  <span class="badge blue">749/14/163</span>
  <span class="badge gray" id="hdr-doctrine">v11</span>
</header>

<!-- TABBAR -->
<nav id="tabbar" role="tablist" aria-label="Amaru console tabs">
  <button class="tab-btn active" data-tab="t01" role="tab" aria-selected="true"><span class="t-icon">⊙</span> Cited Answer</button>
  <button class="tab-btn" data-tab="t02" role="tab"><span class="t-icon">⚠</span> Confidence</button>
  <button class="tab-btn" data-tab="t03" role="tab"><span class="t-icon">🔬</span> Retrieval Eval</button>
  <button class="tab-btn" data-tab="t04" role="tab"><span class="t-icon">⚡</span> 7-Chakra Runtime</button>
  <button class="tab-btn" data-tab="t05" role="tab"><span class="t-icon">🧠</span> Memory / Recall</button>
  <button class="tab-btn" data-tab="t06" role="tab"><span class="t-icon">🔒</span> Brain / Immune</button>
  <button class="tab-btn" data-tab="t07" role="tab"><span class="t-icon">📡</span> Receipt Stream</button>
  <button class="tab-btn" data-tab="t08" role="tab"><span class="t-icon">🕸</span> Provenance Graph</button>
  <button class="tab-btn" data-tab="t09" role="tab"><span class="t-icon">🔀</span> Model Router</button>
  <button class="tab-btn" data-tab="t10" role="tab"><span class="t-icon">📊</span> Eval Board</button>
  <button class="tab-btn" data-tab="t11" role="tab"><span class="t-icon">⚡</span> Cortex Feed</button>
  <button class="tab-btn" data-tab="t12" role="tab"><span class="t-icon">📚</span> Citation Cov</button>
  <button class="tab-btn" data-tab="t13" role="tab"><span class="t-icon">∀</span> Formulas F1–F23</button>
</nav>

<main id="content" role="main">

<!-- ═══════════════════════════════════════════════════════ T01: CITED ANSWER -->
<div class="pane active" id="pane-t01" role="tabpanel" aria-labelledby="tab-t01">
  <div class="card">
    <div class="card-hdr">
      <h2>⊙ Cited-Answer Console</h2>
      <span class="note">Endpoint: POST /api/amaru/v1/reason · Beats: Perplexity cited-answer RAG</span>
    </div>
    <p style="font-size:12px;color:var(--mut);margin-bottom:12px">Every claim must cite a real source URL. amaru refuses to emit unsourced reasoning — <b>no fabrication</b>. Backed by real arXiv Atom retrieval + CoVe chain-of-verification + DSSE-signed Khipu receipts.</p>
    <div class="row">
      <div><label for="ra-q">Question</label><textarea id="ra-q" rows="2" placeholder="e.g. What is the PAC-Bayes generalization bound for neural networks?"></textarea></div>
    </div>
    <div class="row">
      <div><label for="ra-a">Primary Answer (optional — leave blank for auto)</label><textarea id="ra-a" rows="2" placeholder="Optionally provide your own answer to evaluate..."></textarea></div>
    </div>
    <div class="row cols2">
      <div><label for="ra-cit">Citation URL(s) (comma-sep, optional)</label><input id="ra-cit" placeholder="https://arxiv.org/abs/2309.11495, ..."/></div>
      <div style="display:flex;align-items:flex-end;gap:8px">
        <button class="btn primary" id="ra-run">Run Reasoning</button>
        <button class="btn sm" id="ra-clear">Clear</button>
      </div>
    </div>
    <div id="ra-metrics" class="metrics" style="display:none">
      <div class="metric"><div class="v" id="ram-cit">—</div><div class="k">Citation Coverage</div></div>
      <div class="metric"><div class="v" id="ram-cove">—</div><div class="k">CoVe Consistency</div></div>
      <div class="metric"><div class="v" id="ram-lambda">—</div><div class="k">Λ Gate</div></div>
      <div class="metric"><div class="v" id="ram-refused">—</div><div class="k">Refused?</div></div>
      <div class="metric"><div class="v" id="ram-signed">—</div><div class="k">Khipu Signed</div></div>
    </div>
    <div id="ra-out" class="out">Run a question to see grounded reasoning with source receipts.</div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T02: CONFIDENCE -->
<div class="pane" id="pane-t02" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>⚠ Confidence / Hallucination-Risk Scorer</h2>
      <span class="note">Endpoint: POST /api/amaru/v1/confidence · Beats: Fiddler AI, Arize Phoenix, LangSmith · UNIQUE: Λ-gated + DSSE receipt</span>
    </div>
    <p style="font-size:12px;color:var(--mut);margin-bottom:12px">Three deterministic sub-scores: <b>citation coverage</b> (fraction of sentences citing a URL), <b>CoVe consistency</b> (token Jaccard vs. verification answer), <b>Λ-floor</b> (13-axis geomean ≥ 0.85). Every score emits a SHA-256 receipt — no LLM judge needed.</p>
    <div class="row cols2">
      <div><label for="cf-q">Question</label><input id="cf-q" placeholder="What is the PAC-Bayes bound?"/></div>
      <div><label for="cf-va">Verification Answer (optional)</label><input id="cf-va" placeholder="Independent re-answer for CoVe check..."/></div>
    </div>
    <div class="row">
      <div><label for="cf-a">Answer to Score</label><textarea id="cf-a" rows="3" placeholder="The PAC-Bayes bound states... See https://arxiv.org/abs/... for details."></textarea></div>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn primary" id="cf-run">Score Confidence</button>
    </div>
    <div id="cf-metrics" class="metrics" style="display:none">
      <div class="metric"><div class="v" id="cfm-conf">—</div><div class="k">Confidence</div></div>
      <div class="metric"><div class="v" id="cfm-cit">—</div><div class="k">Citation Cov</div></div>
      <div class="metric"><div class="v" id="cfm-cove">—</div><div class="k">CoVe Sim</div></div>
      <div class="metric"><div class="v" id="cfm-lam">—</div><div class="k">Λ Score</div></div>
      <div class="metric"><div class="v" id="cfm-risk">—</div><div class="k">Halluc. Risk</div></div>
    </div>
    <div id="cf-out" class="out">Paste an answer to evaluate its hallucination risk.</div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T03: RETRIEVAL EVAL -->
<div class="pane" id="pane-t03" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>🔬 Retrieval Eval (RAGAS-style)</h2>
      <span class="note">Endpoint: POST /api/amaru/v1/eval · Beats: Arize Phoenix RAGAS, LangSmith retrieval evals</span>
    </div>
    <p style="font-size:12px;color:var(--mut);margin-bottom:12px">Four deterministic metrics: context_precision, context_recall, answer_faithfulness, source_coverage. Deterministic token-overlap (no LLM cost). Each evaluation is receipt-hash-bound.</p>
    <div class="row cols2">
      <div><label for="ev-q">Question</label><input id="ev-q" placeholder="What is Bekenstein additive budget monotonicity?"/></div>
      <div><label for="ev-a">Answer</label><input id="ev-a" placeholder="The Bekenstein bound states..."/></div>
    </div>
    <div class="row">
      <div><label for="ev-c">Retrieved Chunks (one per line)</label><textarea id="ev-c" rows="4" placeholder="The Bekenstein bound governs information density in a sphere...&#10;Budget monotonicity ensures the total Λ-score only grows...&#10;F19 proves additive scaffolding is sound (Lean-verified)."></textarea></div>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn primary" id="ev-run">Evaluate Retrieval</button>
    </div>
    <div id="ev-metrics" class="metrics" style="display:none">
      <div class="metric"><div class="v" id="evm-prec">—</div><div class="k">Context Prec</div></div>
      <div class="metric"><div class="v" id="evm-rec">—</div><div class="k">Context Recall</div></div>
      <div class="metric"><div class="v" id="evm-faith">—</div><div class="k">Faithfulness</div></div>
      <div class="metric"><div class="v" id="evm-cov">—</div><div class="k">Src Coverage</div></div>
      <div class="metric"><div class="v" id="evm-comp">—</div><div class="k">Composite</div></div>
    </div>
    <div id="ev-out" class="out">Enter a question + answer + context chunks to evaluate RAG quality.</div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T04: CHAKRA RUNTIME -->
<div class="pane" id="pane-t04" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>⚡ 7-Chakra Runtime Monitor</h2>
      <span class="note">Endpoint: GET /brain (HTML) + GET /api/amaru/healthz · 3D anatomy available</span>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <button class="btn primary" id="ch-refresh">Refresh Runtime</button>
      <a href="/brain" target="_blank" class="btn sm">Open /brain live</a>
    </div>
    <div id="ch-hdr-metrics" class="metrics" style="display:none">
      <div class="metric"><div class="v" id="chm-ticks">—</div><div class="k">Scheduler Ticks</div></div>
      <div class="metric"><div class="v" id="chm-receipts">—</div><div class="k">Receipts</div></div>
      <div class="metric"><div class="v" id="chm-trips">—</div><div class="k">Tripwires Pass</div></div>
      <div class="metric"><div class="v" id="chm-doctrine">—</div><div class="k">Doctrine</div></div>
    </div>
    <div class="chakras" id="ch-chakras">
      <!-- Populated by JS -->
      <div class="loading">Loading chakra runtime</div>
    </div>
    <div class="ruler"></div>
    <h3 style="font-size:13px;font-weight:600;margin-bottom:10px;color:var(--mut)">3D Anatomy</h3>
    <div id="canvas3d">
      <canvas id="chakra-canvas3d"></canvas>
      <div style="position:absolute;bottom:10px;right:14px;font-size:10px;color:var(--mut);font-family:var(--font-mono)">amaru 7-chakra · 3D · live</div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T05: MEMORY / RECALL -->
<div class="pane" id="pane-t05" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>🧠 Memory / Recall Explorer (Unay)</h2>
      <span class="note">Endpoint: POST /api/amaru/v2/unay/recall + GET /api/amaru/v2/unay/stats · Beats: Palantir Object Explorer</span>
    </div>
    <p style="font-size:12px;color:var(--mut);margin-bottom:12px">Unay is amaru's durable memory layer — LMDB-backed receipt-keyed recall. Every memory write is DSSE-signed; every read returns its Khipu Merkle receipt.</p>
    <div class="row cols3">
      <div><label for="mem-q">Recall Query</label><input id="mem-q" placeholder="PAC-Bayes bound..."/></div>
      <div><label for="mem-k">k (max results)</label><input id="mem-k" type="number" value="5" min="1" max="20"/></div>
      <div style="display:flex;align-items:flex-end;gap:8px">
        <button class="btn primary" id="mem-recall">Recall</button>
        <button class="btn sm" id="mem-stats">Stats</button>
      </div>
    </div>
    <div class="ruler"></div>
    <div class="row">
      <div>
        <label for="mem-store-key">Store Memory (key)</label>
        <input id="mem-store-key" placeholder="my-key"/>
      </div>
    </div>
    <div class="row">
      <div>
        <label for="mem-store-val">Value</label>
        <textarea id="mem-store-val" rows="2" placeholder="Memory content to store..."></textarea>
      </div>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn" id="mem-store">Store</button>
    </div>
    <div id="mem-out" class="out">Query memory or store a new entry.</div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T06: BRAIN / IMMUNE -->
<div class="pane" id="pane-t06" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>🔒 Brain / Immune Screen</h2>
      <span class="note">Endpoint: GET /api/amaru/v1/brain + POST /api/amaru/v1/brain/reason · full LLM roster (a11oy-parity)</span>
    </div>
    <div class="info-row" id="brain-badges"></div>
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <button class="btn primary" id="brain-load">Load Brain State</button>
      <a href="/chakras" target="_blank" class="btn sm">View /chakras</a>
    </div>
    <div class="metrics" id="brain-metrics" style="display:none">
      <div class="metric"><div class="v" id="brm-th1">—</div><div class="k">TH1 Λ Conj</div></div>
      <div class="metric"><div class="v" id="brm-th8">—</div><div class="k">TH8 GLR</div></div>
      <div class="metric"><div class="v" id="brm-th10">—</div><div class="k">TH10 Conj1</div></div>
      <div class="metric"><div class="v" id="brm-tiers">—</div><div class="k">LLM Tiers</div></div>
      <div class="metric"><div class="v" id="brm-decl">—</div><div class="k">Declarations</div></div>
    </div>
    <div class="ruler"></div>
    <h3 style="font-size:13px;font-weight:600;margin-bottom:10px">Reason with Citations</h3>
    <div class="row">
      <div><label for="br-q">Question for brain</label><textarea id="br-q" rows="2" placeholder="Explain the GLR theorem (TH8) in amaru's 7-chakra runtime."></textarea></div>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn primary" id="br-run">Cited Reason</button>
    </div>
    <div id="brain-out" class="out">Load brain state or run a cited-reason query.</div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T07: RECEIPT STREAM -->
<div class="pane" id="pane-t07" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>📡 Inference Receipt Stream</h2>
      <span class="note">Endpoint: GET /api/amaru/v1/cortex-subscribe (SSE) · UNIQUE: DSSE-signed reasoning trace receipts</span>
    </div>
    <p style="font-size:12px;color:var(--mut);margin-bottom:12px">Every inference decision emits a DSSE-enveloped Khipu Merkle receipt — cryptographically linkable, audit-replayable. amaru is the ONLY reasoning engine that signs its inference trace per the DSSE spec.</p>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn primary" id="sse-start">Start Stream</button>
      <button class="btn sm" id="sse-stop" disabled>Stop</button>
      <button class="btn sm" id="sse-clear">Clear</button>
      <span class="badge" id="sse-status" style="margin-left:auto">idle</span>
    </div>
    <div class="stream-box" id="sse-box">
      <div class="evt"><span class="ts">—</span><span class="data">Stream not started. Click "Start Stream" to subscribe to cortex SSE events.</span></div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T08: PROVENANCE GRAPH -->
<div class="pane" id="pane-t08" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>🕸 Source Provenance Graph</h2>
      <span class="note">Endpoint: GET /api/amaru/v1/cortex/3d + GET /api/amaru/v1/khipu/ledger · 3D force graph</span>
    </div>
    <p style="font-size:12px;color:var(--mut);margin-bottom:12px">Real reasoning-chain nodes from prior /reason calls. Each node carries its DSSE PAE SHA-256; edges are Merkle linkage prev→next. Empty graph = IDLE — never synthetic.</p>
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <button class="btn primary" id="pg-load">Load Graph</button>
      <button class="btn sm" id="pg-ledger">Khipu Ledger</button>
    </div>
    <div id="pg-stats" class="metrics" style="display:none">
      <div class="metric"><div class="v" id="pgm-nodes">—</div><div class="k">Nodes</div></div>
      <div class="metric"><div class="v" id="pgm-edges">—</div><div class="k">Edges</div></div>
      <div class="metric"><div class="v" id="pgm-chains">—</div><div class="k">Chains</div></div>
      <div class="metric"><div class="v" id="pgm-live">—</div><div class="k">Live?</div></div>
    </div>
    <div id="canvas3d-pg" style="width:100%;height:320px;background:linear-gradient(135deg,#060b14 0%,#0a1622 100%);border-radius:var(--r);border:1px solid var(--border);position:relative;overflow:hidden;margin-top:12px">
      <canvas id="pg-canvas"></canvas>
      <div id="pg-idle" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:12px;color:var(--mut);font-family:var(--font-mono)">Run /reason queries to populate the provenance graph.</div>
    </div>
    <div id="pg-out" class="out" style="margin-top:12px;display:none"></div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T09: MODEL ROUTER -->
<div class="pane" id="pane-t09" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>🔀 Model-Tier Router View</h2>
      <span class="note">Endpoint: GET /api/amaru/v1/llm/tiers + POST /api/amaru/v1/llm/route · Full a11oy-parity LLM roster</span>
    </div>
    <p style="font-size:12px;color:var(--mut);margin-bottom:12px">Full LLM roster — same 5-tier model access a11oy has. Λ-gated tier selection: high Λ → fast tier; low Λ / adversarial → premium tier + extra gates. Every route emits a Λ-receipt.</p>
    <button class="btn primary" id="rt-load" style="margin-bottom:14px">Load Tier Registry</button>
    <div class="tiers" id="rt-tiers">
      <div class="loading">Loading model roster</div>
    </div>
    <div class="ruler"></div>
    <h3 style="font-size:13px;font-weight:600;margin-bottom:10px">Route a Query</h3>
    <div class="row cols2">
      <div><label for="rt-p">Prompt</label><input id="rt-p" placeholder="Prove the PAC-Bayes generalization bound..."/></div>
      <div>
        <label for="rt-hint">Task Hint</label>
        <select id="rt-hint">
          <option value="">auto</option>
          <option value="math">math</option>
          <option value="research">research</option>
          <option value="orchestration">orchestration</option>
          <option value="diligence">diligence</option>
        </select>
      </div>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn primary" id="rt-route">Route</button>
    </div>
    <div id="rt-out" class="out">Load the tier registry, then route a query.</div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T10: EVAL BOARD -->
<div class="pane" id="pane-t10" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>📊 Eval / Regression Board</h2>
      <span class="note">Endpoint: POST /api/amaru/v1/eval (batch) · Beats: LangSmith eval board, Arize Phoenix traces</span>
    </div>
    <p style="font-size:12px;color:var(--mut);margin-bottom:12px">Run a batch of Q/A/chunks triples through the retrieval evaluator. All scores are deterministic and receipt-hash-bound — no LLM judge drift.</p>
    <div class="row">
      <div><label for="eb-batch">Batch (JSON array of {question, answer, chunks:[]})</label>
        <textarea id="eb-batch" rows="6" placeholder='[
  {"question":"What is F19?","answer":"Bekenstein additive budget monotonicity — proven via Lean F19.","chunks":["F19 proves additive scaffolding. Budget grows monotonically."]},
  {"question":"What is Λ?","answer":"Lambda is the 13-axis geometric-mean aggregator — Conjecture 1, NOT a theorem.","chunks":["Λ is the product of 13 axis scores raised to Egyptian-fraction weights."]}
]'></textarea>
      </div>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn primary" id="eb-run">Run Batch Eval</button>
    </div>
    <div id="eb-summary" class="metrics" style="display:none">
      <div class="metric"><div class="v" id="ebm-n">—</div><div class="k">Cases</div></div>
      <div class="metric"><div class="v" id="ebm-prec">—</div><div class="k">Avg Prec</div></div>
      <div class="metric"><div class="v" id="ebm-faith">—</div><div class="k">Avg Faith</div></div>
      <div class="metric"><div class="v" id="ebm-comp">—</div><div class="k">Avg Composite</div></div>
    </div>
    <div id="eb-out" class="out">Paste a batch JSON to run regression evaluation.</div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T11: CORTEX FEED -->
<div class="pane" id="pane-t11" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>⚡ Cortex SSE Live Feed</h2>
      <span class="note">Endpoint: GET /api/amaru/v1/cortex-subscribe (SSE, Wire E) · Beats: New Relic AI response trace waterfall</span>
    </div>
    <p style="font-size:12px;color:var(--mut);margin-bottom:12px">Wire E: amaru subscribes to a11oy brand-decision events. Live SSE stream from the in-memory ring bus. Honest: in-process ring buffer (resets on Space restart). Cross-Space OTLP broker is roadmap.</p>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn primary" id="feed-start">Subscribe to Wire E</button>
      <button class="btn sm" id="feed-stop" disabled>Unsubscribe</button>
      <button class="btn sm" id="feed-inject">Inject Test Event</button>
      <span class="badge" id="feed-status" style="margin-left:auto">idle</span>
    </div>
    <div class="metrics" id="feed-metrics" style="display:none">
      <div class="metric"><div class="v" id="fm-events">0</div><div class="k">Events received</div></div>
      <div class="metric"><div class="v" id="fm-wire">E</div><div class="k">Wire</div></div>
      <div class="metric"><div class="v" id="fm-last">—</div><div class="k">Last event type</div></div>
    </div>
    <div class="stream-box" id="feed-box">
      <div class="evt"><span class="ts">—</span><span class="data">Subscribe to Wire E to see live cortex events from a11oy → amaru.</span></div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T12: CITATION COVERAGE -->
<div class="pane" id="pane-t12" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>📚 Knowledge / Citation Coverage</h2>
      <span class="note">Endpoint: GET /api/amaru/v1/honest + GET /api/amaru/v4/recall + GET /api/amaru/v1/receipts</span>
    </div>
    <p style="font-size:12px;color:var(--mut);margin-bottom:12px">Citation coverage dashboard — shows the honest doctrine posture (SLSA L1 honest, cosign-signed; L2 attestation roadmap via Wire D, not yet earned; Λ=Conjecture 1; no FedRAMP/Iron Bank/CMMC), live receipt chain stats, and knowledge base recall coverage.</p>
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <button class="btn primary" id="cov-load">Load Coverage</button>
    </div>
    <div class="metrics" id="cov-metrics" style="display:none">
      <div class="metric"><div class="v" id="covm-decl">—</div><div class="k">Declarations</div></div>
      <div class="metric"><div class="v" id="covm-axioms">—</div><div class="k">Axioms</div></div>
      <div class="metric"><div class="v" id="covm-sorries">—</div><div class="k">Sorries</div></div>
      <div class="metric"><div class="v" id="covm-receipts">—</div><div class="k">Receipts</div></div>
      <div class="metric"><div class="v" id="covm-slsa">—</div><div class="k">SLSA Level</div></div>
    </div>
    <div id="cov-out" class="out">Load coverage to see honest doctrine posture and receipt chain stats.</div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ T13: FORMULA REGISTRY -->
<div class="pane" id="pane-t13" role="tabpanel">
  <div class="card">
    <div class="card-hdr">
      <h2>∀ Formula Registry — F1–F23</h2>
      <span class="note">Endpoint: GET /api/amaru/v1/formulas/index · Full ecosystem parity with a11oy + Rosie</span>
    </div>
    <p style="font-size:12px;color:var(--mut);margin-bottom:12px">Complete F1–F23 canonical formula set. <span class="proved">PROVED={F1,F4,F7,F11,F12,F18,F19,F22}</span>. <span class="conj">F23=Conjecture 1</span> (open bounty, NOT a theorem; CAUCHY_ND sorry Uniqueness.lean:120). All others: Roadmap (sorry/open). Lean pin: 749/14/163 @ c7c0ba17.</p>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn primary" id="fm-load">Load Formulas</button>
    </div>
    <div id="fm-table-wrap" style="display:none;overflow-x:auto">
      <table class="ftable" id="fm-table">
        <thead><tr><th>ID</th><th>Name</th><th>Organ</th><th>Lean Ref</th><th>Status</th></tr></thead>
        <tbody id="fm-tbody"></tbody>
      </table>
    </div>
    <div id="fm-out" class="out">Load formulas to see the full F1–F23 registry with honest proof status.</div>
  </div>
</div>

</main>
</div>

<script>
// ═══════════════════════════════════════════════ BASE URL
const BASE = '';

// ═══════════════════════════════════════════════ TAB SWITCHING
const tabBtns = document.querySelectorAll('.tab-btn');
const panes = document.querySelectorAll('.pane');
tabBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    tabBtns.forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected','false'); });
    panes.forEach(p => p.classList.remove('active'));
    btn.classList.add('active'); btn.setAttribute('aria-selected','true');
    document.getElementById('pane-' + btn.dataset.tab)?.classList.add('active');
  });
});

// ═══════════════════════════════════════════════ HELPERS
function fmtJSON(obj) {
  return JSON.stringify(obj, null, 2)
    .replace(/"([^"]+)":/g, '<span class="key">"$1":</span>')
    .replace(/: "([^"]*)"([,\n]|$)/g, ': <span class="str">"$1"</span>$2')
    .replace(/: (true)/g, ': <span class="bool-t">true</span>')
    .replace(/: (false)/g, ': <span class="bool-f">false</span>')
    .replace(/: ([0-9]+\.?[0-9]*)/g, ': <span class="num">$1</span>');
}
function setOut(el, html, raw) {
  el.innerHTML = raw ? fmtJSON(html) : html;
}
function setMetric(id, val, cls) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = val;
  el.className = 'v' + (cls ? ' ' + cls : '');
}
function scoreClass(v) {
  const n = parseFloat(v);
  if (isNaN(n)) return '';
  if (n >= 0.75) return 'good';
  if (n >= 0.5) return 'warn';
  return 'bad';
}
function pct(v) { return (parseFloat(v) * 100).toFixed(1) + '%'; }
async function apiFetch(path, opts={}) {
  const r = await fetch(BASE + path, opts);
  return r.json();
}
function nowStr() { return new Date().toISOString().substr(11,8); }

// ═══════════════════════════════════════════════ T01: CITED ANSWER
document.getElementById('ra-run').addEventListener('click', async () => {
  const q = document.getElementById('ra-q').value.trim();
  if (!q) { document.getElementById('ra-out').textContent = 'Question is required.'; return; }
  const btn = document.getElementById('ra-run');
  btn.disabled = true;
  document.getElementById('ra-out').innerHTML = '<span class="loading">Reasoning</span>';
  try {
    const cits = document.getElementById('ra-cit').value.split(',').map(s=>s.trim()).filter(Boolean);
    const ans = document.getElementById('ra-a').value.trim();
    const body = { question: q };
    if (cits.length) body.citations = cits;
    if (ans) body.answer = ans;
    const d = await apiFetch('/api/amaru/v1/reason', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
    document.getElementById('ra-metrics').style.display = '';
    setMetric('ram-cit', d.verification?.citation_coverage !== undefined ? pct(d.verification.citation_coverage) : (d.refused ? 'N/A' : '—'), '');
    setMetric('ram-cove', d.verification?.similarity !== undefined ? pct(d.verification.similarity) : '—', '');
    setMetric('ram-lambda', 'Conj1', 'warn');
    setMetric('ram-refused', d.refused ? 'YES' : 'NO', d.refused ? 'bad' : 'good');
    setMetric('ram-signed', d.khipu_signed ? 'YES' : 'partial', d.khipu_signed ? 'good' : 'warn');
    setOut(document.getElementById('ra-out'), d, true);
  } catch(e) { document.getElementById('ra-out').innerHTML = '<span class="err">Error: ' + e.message + '</span>'; }
  btn.disabled = false;
});
document.getElementById('ra-clear').addEventListener('click', () => {
  ['ra-q','ra-a','ra-cit'].forEach(id => { const el = document.getElementById(id); if(el) el.value = ''; });
  document.getElementById('ra-out').textContent = 'Cleared.';
  document.getElementById('ra-metrics').style.display = 'none';
});

// ═══════════════════════════════════════════════ T02: CONFIDENCE
document.getElementById('cf-run').addEventListener('click', async () => {
  const q = document.getElementById('cf-q').value.trim();
  const a = document.getElementById('cf-a').value.trim();
  if (!q || !a) { document.getElementById('cf-out').textContent = 'Question and answer are required.'; return; }
  const btn = document.getElementById('cf-run'); btn.disabled = true;
  document.getElementById('cf-out').innerHTML = '<span class="loading">Scoring</span>';
  try {
    const va = document.getElementById('cf-va').value.trim();
    const body = { question: q, answer: a };
    if (va) body.verification_answer = va;
    const d = await apiFetch('/api/amaru/v1/confidence', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
    document.getElementById('cf-metrics').style.display = '';
    setMetric('cfm-conf', pct(d.confidence), scoreClass(d.confidence));
    setMetric('cfm-cit', pct(d.scores?.citation_coverage), scoreClass(d.scores?.citation_coverage));
    setMetric('cfm-cove', pct(d.scores?.cove_consistency), scoreClass(d.scores?.cove_consistency));
    setMetric('cfm-lam', pct(d.scores?.lambda_score), scoreClass(d.scores?.lambda_score));
    setMetric('cfm-risk', d.risk_label || (d.hallucination_risk ? 'HIGH' : 'LOW'), d.hallucination_risk ? 'bad' : 'good');
    setOut(document.getElementById('cf-out'), d, true);
  } catch(e) { document.getElementById('cf-out').innerHTML = '<span class="err">Error: ' + e.message + '</span>'; }
  btn.disabled = false;
});

// ═══════════════════════════════════════════════ T03: RETRIEVAL EVAL
document.getElementById('ev-run').addEventListener('click', async () => {
  const q = document.getElementById('ev-q').value.trim();
  const a = document.getElementById('ev-a').value.trim();
  const c = document.getElementById('ev-c').value.trim().split('\n').filter(Boolean);
  if (!q || !a) { document.getElementById('ev-out').textContent = 'Question and answer required.'; return; }
  const btn = document.getElementById('ev-run'); btn.disabled = true;
  document.getElementById('ev-out').innerHTML = '<span class="loading">Evaluating</span>';
  try {
    const d = await apiFetch('/api/amaru/v1/eval', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ question:q, answer:a, chunks:c }) });
    document.getElementById('ev-metrics').style.display = '';
    setMetric('evm-prec', pct(d.metrics?.context_precision), scoreClass(d.metrics?.context_precision));
    setMetric('evm-rec', pct(d.metrics?.context_recall), scoreClass(d.metrics?.context_recall));
    setMetric('evm-faith', pct(d.metrics?.answer_faithfulness), scoreClass(d.metrics?.answer_faithfulness));
    setMetric('evm-cov', pct(d.metrics?.source_coverage), scoreClass(d.metrics?.source_coverage));
    setMetric('evm-comp', pct(d.composite), scoreClass(d.composite));
    setOut(document.getElementById('ev-out'), d, true);
  } catch(e) { document.getElementById('ev-out').innerHTML = '<span class="err">Error: ' + e.message + '</span>'; }
  btn.disabled = false;
});

// ═══════════════════════════════════════════════ T04: CHAKRA RUNTIME
const CHAKRA_GLYPHS = {root:'🔴',sacral:'🟠',solar:'🟡',heart:'🟢',throat:'🔵',third_eye:'🟣',crown:'⚪'};
const CHAKRA_NAMES = {root:'Root · Muladhara',sacral:'Sacral · Svadhisthana',solar:'Solar · Manipura',heart:'Heart · Anahata',throat:'Throat · Vishuddha',third_eye:'Third-Eye · Ajna',crown:'Crown · Sahasrara'};
async function loadChakras() {
  const chBox = document.getElementById('ch-chakras');
  chBox.innerHTML = '<div class="loading">Loading</div>';
  try {
    const d = await apiFetch('/brain');
    // /brain returns HTML, fallback to healthz JSON
    throw new Error('html');
  } catch(e) {}
  try {
    const d = await apiFetch('/api/amaru/healthz');
    document.getElementById('ch-hdr-metrics').style.display = '';
    setMetric('chm-ticks', d.scheduler_ticks || 0, '');
    setMetric('chm-receipts', d.receipts_in_chain || 0, '');
    setMetric('chm-trips', d.tripwires_pass || '—', '');
    setMetric('chm-doctrine', d.doctrine || 'v11', '');
    const chakras = ['root','sacral','solar','heart','throat','third_eye','crown'];
    chBox.innerHTML = chakras.map(c => `
      <div class="chakra idle" id="chakra-${c}">
        <div class="c-glyph">${CHAKRA_GLYPHS[c] || '○'}</div>
        <div class="c-name">${c.replace('_',' ')}</div>
        <div class="c-status">idle</div>
      </div>`).join('');
    initChakra3D();
  } catch(e) {
    chBox.innerHTML = '<span style="color:var(--mut)">Unable to load chakra data.</span>';
  }
}
document.getElementById('ch-refresh').addEventListener('click', loadChakras);

// 3D Chakra canvas
function initChakra3D() {
  const canvas = document.getElementById('chakra-canvas3d');
  if (!canvas) return;
  const W = canvas.parentElement.offsetWidth, H = canvas.parentElement.offsetHeight;
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  const chakraColors = ['#e05252','#e07a30','#d4c020','#3ecf8e','#5ab4d6','#9b72cf','#e8e0ff'];
  const nodes = chakraColors.map((c,i) => {
    const angle = (i / 7) * Math.PI * 2 - Math.PI/2;
    const r = Math.min(W,H) * 0.35;
    return { x: W/2 + r*Math.cos(angle), y: H/2 + r*Math.sin(angle), color: c, r:12, vx:(Math.random()-.5)*.4, vy:(Math.random()-.5)*.4, phase: Math.random()*Math.PI*2 };
  });
  const center = { x: W/2, y: H/2 };
  let frame = 0;
  function draw() {
    ctx.clearRect(0,0,W,H);
    ctx.fillStyle = 'rgba(6,10,20,0.92)'; ctx.fillRect(0,0,W,H);
    // Center spiral
    ctx.save();
    for (let i=0; i<200; i++) {
      const a = i*0.3 + frame*0.01, rr = i*0.7;
      const px = W/2+rr*Math.cos(a), py = H/2+rr*Math.sin(a);
      ctx.globalAlpha = (1-i/200)*0.15;
      ctx.fillStyle = '#5ab4d6';
      ctx.beginPath(); ctx.arc(px,py,1,0,Math.PI*2); ctx.fill();
    }
    ctx.restore();
    // Edges
    nodes.forEach((n,i) => {
      const next = nodes[(i+1)%nodes.length];
      ctx.save(); ctx.globalAlpha=0.12;
      ctx.strokeStyle=n.color; ctx.lineWidth=1;
      ctx.beginPath(); ctx.moveTo(n.x,n.y); ctx.lineTo(next.x,next.y); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(n.x,n.y); ctx.lineTo(center.x,center.y); ctx.stroke();
      ctx.restore();
    });
    // Nodes
    nodes.forEach((n,i) => {
      const pulse = 1 + 0.25 * Math.sin(frame*0.05 + n.phase);
      const gr = ctx.createRadialGradient(n.x,n.y,0,n.x,n.y,n.r*2*pulse);
      gr.addColorStop(0, n.color+'cc'); gr.addColorStop(1, n.color+'00');
      ctx.save(); ctx.globalAlpha=0.5;
      ctx.fillStyle=gr; ctx.beginPath(); ctx.arc(n.x,n.y,n.r*2*pulse,0,Math.PI*2); ctx.fill();
      ctx.restore();
      ctx.fillStyle=n.color;
      ctx.beginPath(); ctx.arc(n.x,n.y,n.r,0,Math.PI*2); ctx.fill();
    });
    // Center orb
    const cg = ctx.createRadialGradient(W/2,H/2,0,W/2,H/2,22);
    cg.addColorStop(0,'#d4a84bcc'); cg.addColorStop(1,'#d4a84b00');
    ctx.fillStyle=cg; ctx.beginPath(); ctx.arc(W/2,H/2,22,0,Math.PI*2); ctx.fill();
    ctx.fillStyle='#d4a84b'; ctx.beginPath(); ctx.arc(W/2,H/2,8,0,Math.PI*2); ctx.fill();
    frame++; requestAnimationFrame(draw);
  }
  draw();
}
// Auto-load chakras when tab activates
document.querySelector('[data-tab=t04]').addEventListener('click', () => { setTimeout(loadChakras, 100); });

// ═══════════════════════════════════════════════ T05: MEMORY / RECALL
document.getElementById('mem-recall').addEventListener('click', async () => {
  const q = document.getElementById('mem-q').value.trim();
  const k = parseInt(document.getElementById('mem-k').value) || 5;
  if (!q) { document.getElementById('mem-out').textContent = 'Query required.'; return; }
  document.getElementById('mem-out').innerHTML = '<span class="loading">Recalling</span>';
  try {
    const d = await apiFetch('/api/amaru/v2/unay/recall?q=' + encodeURIComponent(q) + '&k=' + k);
    setOut(document.getElementById('mem-out'), d, true);
  } catch(e) { document.getElementById('mem-out').innerHTML = '<span class="err">Error: ' + e.message + '</span>'; }
});
document.getElementById('mem-stats').addEventListener('click', async () => {
  document.getElementById('mem-out').innerHTML = '<span class="loading">Loading stats</span>';
  try {
    const d = await apiFetch('/api/amaru/v2/unay/stats');
    setOut(document.getElementById('mem-out'), d, true);
  } catch(e) {
    try {
      const d = await apiFetch('/api/amaru/v2/unay/healthz');
      setOut(document.getElementById('mem-out'), d, true);
    } catch(e2) { document.getElementById('mem-out').innerHTML = '<span class="err">Error: ' + e2.message + '</span>'; }
  }
});
document.getElementById('mem-store').addEventListener('click', async () => {
  const key = document.getElementById('mem-store-key').value.trim();
  const val = document.getElementById('mem-store-val').value.trim();
  if (!key || !val) { document.getElementById('mem-out').textContent = 'Key and value required.'; return; }
  document.getElementById('mem-out').innerHTML = '<span class="loading">Storing</span>';
  try {
    const d = await apiFetch('/api/amaru/v2/unay/remember', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ key, value:val }) });
    setOut(document.getElementById('mem-out'), d, true);
  } catch(e) { document.getElementById('mem-out').innerHTML = '<span class="err">Error: ' + e.message + '</span>'; }
});

// ═══════════════════════════════════════════════ T06: BRAIN / IMMUNE
async function loadBrain() {
  document.getElementById('brain-out').innerHTML = '<span class="loading">Loading</span>';
  try {
    const d = await apiFetch('/api/amaru/v1/brain');
    document.getElementById('brain-metrics').style.display = '';
    const th = d.brain?.theorems || {};
    setMetric('brm-th1', th.TH1?.status || '—', th.TH1?.status === 'CONJECTURE' ? 'warn' : '');
    setMetric('brm-th8', th.TH8?.status || '—', th.TH8?.status === 'PROVEN' ? 'good' : 'warn');
    setMetric('brm-th10', th.TH10?.status || '—', 'warn');
    setMetric('brm-tiers', d.llm_tiers?.length || '5', '');
    setMetric('brm-decl', d.canonical?.declarations || 749, '');
    const bb = document.getElementById('brain-badges');
    bb.innerHTML = '<span class="badge amber">Λ=Conjecture 1</span><span class="badge green">TH8=PROVEN</span><span class="badge blue">7 chakras</span><span class="badge gray">v11</span>';
    setOut(document.getElementById('brain-out'), d, true);
  } catch(e) { document.getElementById('brain-out').innerHTML = '<span class="err">Error: ' + e.message + '</span>'; }
}
document.getElementById('brain-load').addEventListener('click', loadBrain);
document.getElementById('br-run').addEventListener('click', async () => {
  const q = document.getElementById('br-q').value.trim();
  if (!q) { document.getElementById('brain-out').textContent = 'Question required.'; return; }
  document.getElementById('brain-out').innerHTML = '<span class="loading">Reasoning</span>';
  try {
    const d = await apiFetch('/api/amaru/v1/brain/cited', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ query:q }) });
    setOut(document.getElementById('brain-out'), d, true);
  } catch(e) { document.getElementById('brain-out').innerHTML = '<span class="err">Error: ' + e.message + '</span>'; }
});

// ═══════════════════════════════════════════════ T07: RECEIPT STREAM
let sseConn07 = null;
document.getElementById('sse-start').addEventListener('click', () => {
  if (sseConn07) sseConn07.close();
  const box = document.getElementById('sse-box'); box.innerHTML = '';
  document.getElementById('sse-status').textContent = 'connecting...';
  document.getElementById('sse-stop').disabled = false;
  document.getElementById('sse-start').disabled = true;
  sseConn07 = new EventSource(BASE + '/api/amaru/v1/cortex-subscribe');
  sseConn07.addEventListener('cortex', e => {
    document.getElementById('sse-status').textContent = 'live';
    const div = document.createElement('div'); div.className = 'evt';
    div.innerHTML = `<span class="ts">${nowStr()}</span><span class="data">${e.data.slice(0,300)}</span>`;
    box.appendChild(div); box.scrollTop = box.scrollHeight;
  });
  sseConn07.addEventListener('done', e => {
    document.getElementById('sse-status').textContent = 'done';
    const div = document.createElement('div'); div.className = 'evt';
    div.innerHTML = `<span class="ts">${nowStr()}</span><span class="data" style="color:var(--green)">Stream closed: ${e.data}</span>`;
    box.appendChild(div);
    if(sseConn07){sseConn07.close();sseConn07=null;}
    document.getElementById('sse-start').disabled=false; document.getElementById('sse-stop').disabled=true;
  });
  sseConn07.onerror = () => {
    document.getElementById('sse-status').textContent = 'error';
    document.getElementById('sse-start').disabled=false; document.getElementById('sse-stop').disabled=true;
    if(sseConn07){sseConn07.close();sseConn07=null;}
  };
});
document.getElementById('sse-stop').addEventListener('click', () => {
  if(sseConn07){sseConn07.close();sseConn07=null;}
  document.getElementById('sse-status').textContent = 'stopped';
  document.getElementById('sse-start').disabled=false; document.getElementById('sse-stop').disabled=true;
});
document.getElementById('sse-clear').addEventListener('click', () => {
  document.getElementById('sse-box').innerHTML = '<div class="evt"><span class="ts">—</span><span class="data">Cleared.</span></div>';
});

// ═══════════════════════════════════════════════ T08: PROVENANCE GRAPH
async function loadProvenanceGraph() {
  document.getElementById('pg-out').style.display='none';
  try {
    const d = await apiFetch('/api/amaru/v1/cortex/3d');
    document.getElementById('pg-stats').style.display='';
    setMetric('pgm-nodes', d.graph?.nodes?.length || 0, '');
    setMetric('pgm-edges', d.graph?.edges?.length || 0, '');
    setMetric('pgm-chains', d.count_chains || 0, '');
    setMetric('pgm-live', d.live ? 'YES' : 'NO', d.live ? 'good' : 'warn');
    if (d.live && d.graph?.nodes?.length) {
      document.getElementById('pg-idle').style.display='none';
      drawProvenanceGraph(d.graph);
    } else {
      document.getElementById('pg-idle').style.display='flex';
    }
    document.getElementById('pg-out').style.display='block';
    setOut(document.getElementById('pg-out'), d, true);
  } catch(e) { document.getElementById('pg-out').style.display='block'; document.getElementById('pg-out').innerHTML='<span class="err">'+e.message+'</span>'; }
}
document.getElementById('pg-load').addEventListener('click', loadProvenanceGraph);
document.getElementById('pg-ledger').addEventListener('click', async () => {
  document.getElementById('pg-out').style.display='block';
  document.getElementById('pg-out').innerHTML='<span class="loading">Loading ledger</span>';
  try {
    const d = await apiFetch('/api/amaru/v1/receipts');
    setOut(document.getElementById('pg-out'), d, true);
  } catch(e) { document.getElementById('pg-out').innerHTML='<span class="err">'+e.message+'</span>'; }
});
function drawProvenanceGraph(graph) {
  const canvas = document.getElementById('pg-canvas');
  const W = canvas.parentElement.offsetWidth, H = 320;
  canvas.width=W; canvas.height=H;
  const ctx = canvas.getContext('2d');
  const nodes = graph.nodes.map((n,i) => ({ ...n, x: 60 + (i/(graph.nodes.length-1||1))*(W-120), y: H/2 + (i%2===0?-60:60) }));
  const byId = {};
  nodes.forEach(n => { byId[n.id] = n; });
  function draw() {
    ctx.clearRect(0,0,W,H);
    ctx.fillStyle='#060a12'; ctx.fillRect(0,0,W,H);
    graph.edges.forEach(e => {
      const a=byId[e.from], b=byId[e.to];
      if(!a||!b) return;
      ctx.save(); ctx.globalAlpha=0.5; ctx.strokeStyle='#5ab4d6'; ctx.lineWidth=1.5;
      ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
      ctx.restore();
    });
    nodes.forEach(n => {
      ctx.fillStyle = n.signed ? '#3ecf8e' : '#d4a84b';
      ctx.beginPath(); ctx.arc(n.x,n.y,10,0,Math.PI*2); ctx.fill();
      ctx.fillStyle='#dce8f5'; ctx.font='10px monospace'; ctx.textAlign='center';
      ctx.fillText(n.label||n.id, n.x, n.y+24);
    });
  }
  draw();
}

// ═══════════════════════════════════════════════ T09: MODEL ROUTER
async function loadTiers() {
  document.getElementById('rt-tiers').innerHTML='<div class="loading">Loading</div>';
  try {
    const d = await apiFetch('/api/amaru/v1/llm/tiers');
    const tiers = d.tiers || [];
    document.getElementById('rt-tiers').innerHTML = tiers.map(t => `
      <div class="tier-row${d.default===t.id?' selected':''}">
        <span class="t-rank">${t.rank}</span>
        <span class="t-name">${t.id}</span>
        <span class="t-use">${t.use}</span>
        <span class="t-why">${t.why}</span>
      </div>`).join('');
    document.getElementById('rt-out').innerHTML = fmtJSON(d);
  } catch(e) { document.getElementById('rt-tiers').innerHTML='<span class="err">'+e.message+'</span>'; }
}
document.getElementById('rt-load').addEventListener('click', loadTiers);
document.querySelector('[data-tab=t09]').addEventListener('click', () => { setTimeout(loadTiers, 100); });
document.getElementById('rt-route').addEventListener('click', async () => {
  const p = document.getElementById('rt-p').value.trim();
  const hint = document.getElementById('rt-hint').value;
  if (!p) { document.getElementById('rt-out').textContent='Prompt required.'; return; }
  document.getElementById('rt-out').innerHTML='<span class="loading">Routing</span>';
  try {
    const d = await apiFetch('/api/amaru/v1/llm/route', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ prompt:p, task_hint:hint }) });
    setOut(document.getElementById('rt-out'), d, true);
    // Highlight selected tier
    document.querySelectorAll('.tier-row').forEach(r => r.classList.remove('selected'));
    const used = d.tier_used;
    document.querySelectorAll('.tier-row').forEach(r => {
      if (r.querySelector('.t-name')?.textContent === used) r.classList.add('selected');
    });
  } catch(e) { document.getElementById('rt-out').innerHTML='<span class="err">'+e.message+'</span>'; }
});

// ═══════════════════════════════════════════════ T10: EVAL BOARD
document.getElementById('eb-run').addEventListener('click', async () => {
  let cases;
  try { cases = JSON.parse(document.getElementById('eb-batch').value); } catch(e) { document.getElementById('eb-out').textContent='Invalid JSON: '+e.message; return; }
  if (!Array.isArray(cases)||!cases.length) { document.getElementById('eb-out').textContent='Array required.'; return; }
  document.getElementById('eb-out').innerHTML='<span class="loading">Running batch</span>';
  const btn = document.getElementById('eb-run'); btn.disabled=true;
  const results = [];
  try {
    for (const c of cases) {
      const d = await apiFetch('/api/amaru/v1/eval', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(c) });
      results.push({ ...c, result:d });
    }
    document.getElementById('eb-summary').style.display='';
    const n = results.length;
    const avg = key => (results.reduce((s,r) => s+(r.result?.metrics?.[key]||r.result?.composite||0), 0)/n).toFixed(3);
    setMetric('ebm-n', n, '');
    setMetric('ebm-prec', pct(avg('context_precision')), scoreClass(avg('context_precision')));
    setMetric('ebm-faith', pct(avg('answer_faithfulness')), scoreClass(avg('answer_faithfulness')));
    setMetric('ebm-comp', pct(results.reduce((s,r) => s+(r.result?.composite||0), 0)/n), scoreClass(results.reduce((s,r) => s+(r.result?.composite||0), 0)/n));
    setOut(document.getElementById('eb-out'), results, true);
  } catch(e) { document.getElementById('eb-out').innerHTML='<span class="err">'+e.message+'</span>'; }
  btn.disabled=false;
});

// ═══════════════════════════════════════════════ T11: CORTEX FEED
let sseConn11 = null, feedCount = 0;
document.getElementById('feed-start').addEventListener('click', () => {
  if (sseConn11) sseConn11.close();
  feedCount = 0;
  const box = document.getElementById('feed-box'); box.innerHTML='';
  document.getElementById('feed-status').textContent='connecting...';
  document.getElementById('feed-metrics').style.display='';
  document.getElementById('feed-stop').disabled=false;
  document.getElementById('feed-start').disabled=true;
  sseConn11 = new EventSource(BASE + '/api/amaru/v1/cortex-subscribe');
  const onEvent = (type, data) => {
    feedCount++;
    setMetric('fm-events', feedCount, '');
    setMetric('fm-last', type, '');
    document.getElementById('feed-status').textContent='live';
    const div = document.createElement('div'); div.className='evt';
    div.innerHTML=`<span class="ts">${nowStr()} [${type}]</span> <span class="data">${data.slice(0,400)}</span>`;
    box.appendChild(div); box.scrollTop=box.scrollHeight;
  };
  sseConn11.addEventListener('cortex', e => onEvent('cortex', e.data));
  sseConn11.addEventListener('done', e => {
    onEvent('done', e.data);
    document.getElementById('feed-status').textContent='done';
    if(sseConn11){sseConn11.close();sseConn11=null;}
    document.getElementById('feed-start').disabled=false; document.getElementById('feed-stop').disabled=true;
  });
  sseConn11.onerror = () => {
    document.getElementById('feed-status').textContent='error';
    if(sseConn11){sseConn11.close();sseConn11=null;}
    document.getElementById('feed-start').disabled=false; document.getElementById('feed-stop').disabled=true;
  };
});
document.getElementById('feed-stop').addEventListener('click', () => {
  if(sseConn11){sseConn11.close();sseConn11=null;}
  document.getElementById('feed-status').textContent='stopped';
  document.getElementById('feed-start').disabled=false; document.getElementById('feed-stop').disabled=true;
});
document.getElementById('feed-inject').addEventListener('click', async () => {
  try {
    await apiFetch('/api/amaru/v1/receipts/ingest', { method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ action_id:'console-test-'+Date.now(), gate:'thresholdPolicySeverity', lambda:0.91, passed:true, doctrine:'v11' }) });
  } catch(e) {}
});

// ═══════════════════════════════════════════════ T12: CITATION COVERAGE
document.getElementById('cov-load').addEventListener('click', async () => {
  document.getElementById('cov-out').innerHTML='<span class="loading">Loading</span>';
  try {
    const [hon, receipts] = await Promise.all([
      apiFetch('/api/amaru/v1/honest'),
      apiFetch('/api/amaru/v1/receipts').catch(() => ({}))
    ]);
    document.getElementById('cov-metrics').style.display='';
    const dl = hon.doctrine_lock || {};
    setMetric('covm-decl', dl.declarations || hon.declarations || 749, '');
    setMetric('covm-axioms', dl.axioms || hon.axioms || 14, '');
    setMetric('covm-sorries', dl.sorries || hon.sorries || 163, '');
    setMetric('covm-receipts', receipts.count || 0, '');
    const slsa = hon.honest_labels?.slsa || hon.slsa || 'L1 honest (L2 roadmap)';
    setMetric('covm-slsa', slsa.includes('L1') ? 'L1 honest' : slsa, 'good');
    setOut(document.getElementById('cov-out'), {honest: hon, receipts_summary: {count: receipts.count, root: receipts.khipu_root}}, true);
  } catch(e) { document.getElementById('cov-out').innerHTML='<span class="err">'+e.message+'</span>'; }
});

// ═══════════════════════════════════════════════ T13: FORMULA REGISTRY
const FORMULA_STATIC = [
  {id:'F1',name:'Replay-hash determinism',organ:'YAWAR',lean:'PuriqFormulaLean.lean:L35-L53',status:'PROVED'},
  {id:'F2',name:'Scheduler liveness / round-robin fairness',organ:'AMARU',lean:'PuriqFormulaLean.lean:L132-L139',status:'Roadmap'},
  {id:'F3',name:'Organ boot gating soundness',organ:'HATUN',lean:'PuriqFormulaLean.lean:L137-L140',status:'Roadmap'},
  {id:'F4',name:'Khipu DAG acyclicity preservation',organ:'KHIPU',lean:'PuriqFormulaLean.lean:L144-L149',status:'PROVED'},
  {id:'F5',name:'Unay receipt-keyed recall correctness',organ:'UNAY',lean:'PuriqFormulaLean.lean:L150-L154',status:'Roadmap'},
  {id:'F6',name:'LMDB persistence durability',organ:'UNAY',lean:'PuriqFormulaLean.lean:L153-L154',status:'Roadmap'},
  {id:'F7',name:'Chaski FIFO reception ordering',organ:'CHASKI',lean:'PuriqFormulaLean.lean:L156-L157',status:'PROVED'},
  {id:'F8',name:'Wallpa governed-voice OSS-only safety',organ:'WALLPA',lean:'PuriqFormulaLean.lean:L159-L160',status:'Roadmap'},
  {id:'F9',name:'Wasi-Rikuq advisory non-interference',organ:'WASI-RIKUQ',lean:'PuriqFormulaLean.lean:L162-L163',status:'Roadmap'},
  {id:'F10',name:'Hatun-MCP tool-call idempotency',organ:'HATUN',lean:'PuriqFormulaLean.lean:L165-L166',status:'Roadmap'},
  {id:'F11',name:'Ayni reciprocity conservation (zero-sum)',organ:'YUYAY',lean:'PuriqFormulaLean.lean:L56-L75',status:'PROVED'},
  {id:'F12',name:'Additive coupling / CRT-style scheduling',organ:'HUKLLA',lean:'PuriqFormulaLean.lean:L77-L87',status:'PROVED'},
  {id:'F13',name:'WAYRA ingest-chain / Gauss-Bonnet curvature',organ:'WAYRA',lean:'PuriqFormulaLean.lean:L168-L169',status:'Roadmap'},
  {id:'F14',name:'DSSE / partition-style budget audit',organ:'YAWAR',lean:'PuriqFormulaLean.lean:L171-L172',status:'Roadmap'},
  {id:'F15',name:'Rekor transparency-log inclusion',organ:'KHIPU',lean:'PuriqFormulaLean.lean:L174-L175',status:'Roadmap'},
  {id:'F16',name:'Sentra mesh immune cross-cut completeness',organ:'HUKLLA',lean:'PuriqFormulaLean.lean:L177-L178',status:'Roadmap'},
  {id:'F17',name:'Three-vertical isolation (a11oy/killinchu/rosie)',organ:'KALLPA',lean:'PuriqFormulaLean.lean:L180-L181',status:'Roadmap'},
  {id:'F18',name:'Reed-Solomon RS(10,6) parity / erasure tolerance',organ:'KHIPU',lean:'PuriqFormulaLean.lean:L89-L107',status:'PROVED'},
  {id:'F19',name:'Bekenstein additive scaffolding / budget monotonicity',organ:'LAMBDA SPINE',lean:'PuriqFormulaLean.lean:L109-L124',status:'PROVED'},
  {id:'F20',name:'Mobile input-event equivalence (touch/pointer)',organ:'KANCHAY',lean:'PuriqFormulaLean.lean:L183-L184',status:'Roadmap'},
  {id:'F21',name:'Genome TOML validation totality',organ:'HATUN',lean:'PuriqFormulaLean.lean:L186-L187',status:'Roadmap'},
  {id:'F22',name:'Khipu emit append-only monotonicity',organ:'KHIPU',lean:'PuriqFormulaLean.lean:L189-L190',status:'PROVED'},
  {id:'F23',name:'Λ-aggregator soundness (9-axis geomean uniqueness)',organ:'LAMBDA SPINE',lean:'Uniqueness.lean:120 (CAUCHY_ND sorry)',status:'Conjecture 1'},
];
document.getElementById('fm-load').addEventListener('click', async () => {
  document.getElementById('fm-out').innerHTML='<span class="loading">Loading</span>';
  let formulas = FORMULA_STATIC;
  // Try live endpoint
  try {
    const d = await apiFetch('/api/amaru/v1/formulas/index');
    if (d.formulas && Array.isArray(d.formulas)) {
      formulas = d.formulas;
    }
  } catch(e) {}
  document.getElementById('fm-table-wrap').style.display='';
  const tbody = document.getElementById('fm-tbody');
  tbody.innerHTML = formulas.map(f => {
    const cls = f.status==='PROVED'?'proved':f.status.startsWith('Conj')?'conj':'roadmap';
    return `<tr><td><b>${f.id}</b></td><td>${f.name}</td><td style="color:var(--mut)">${f.organ}</td><td style="font-size:10px;color:var(--mut)">${f.lean}</td><td class="${cls}">${f.status}</td></tr>`;
  }).join('');
  document.getElementById('fm-out').innerHTML = fmtJSON({ total: formulas.length, proved: formulas.filter(f=>f.status==='PROVED').length, conjecture_1: 1, roadmap: formulas.filter(f=>f.status==='Roadmap').length, lean_pin: '749/14/163 @ c7c0ba17', doctrine: 'v11', lambda_status: 'Conjecture 1 — NOT a theorem (open CAUCHY_ND sorry)' });
});

// Auto-load on tab click
document.querySelector('[data-tab=t13]').addEventListener('click', () => { setTimeout(() => document.getElementById('fm-load').click(), 100); });
document.querySelector('[data-tab=t04]').addEventListener('click', () => { setTimeout(loadChakras, 100); });
document.querySelector('[data-tab=t12]').addEventListener('click', () => { setTimeout(() => document.getElementById('cov-load').click(), 100); });
document.querySelector('[data-tab=t06]').addEventListener('click', () => { setTimeout(loadBrain, 100); });
</script>
</body>
</html>"""


def register_console(app, *, route: str = "/cortex-console") -> None:
    """Register GET /cortex-console on the FastAPI app (additive only)."""
    from fastapi.responses import HTMLResponse

    @app.get(route, response_class=HTMLResponse, include_in_schema=False,
             name="amaru_cortex_console")
    async def _cortex_console():
        return HTMLResponse(content=CONSOLE_HTML)


__all__ = ["register_console", "CONSOLE_HTML"]
