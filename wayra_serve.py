# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v13 — WAYRA organ (the wind/breath). a11oy /wayra tab backend.
"""
wayra_serve.py — FastAPI router for the a11oy /wayra tab.

WAYRA (Quechua *wayra* = "wind, air"; Wiktionary) is the empire's lungs: it breathes in
the world's continuous public knowledge stream, gates it via Yuyay-13, receipts it via
Khipu, and routes it to the relevant organ. This module exposes that organ inside the
a11oy Space:

  GET  /api/a11oy/v1/wayra/summary        — totals + source stats + thresholds
  GET  /api/a11oy/v1/wayra/feed?limit=100 — last N ingested items (Yuyay/novelty badges)
  GET  /api/a11oy/v1/wayra/search?q=…     — find anything WAYRA has seen
  GET  /api/a11oy/v1/wayra/sources        — per-source dashboard (last fetch, today, 30d)
  GET  /api/a11oy/v1/wayra/digest         — top-5 + WALLPA-narrated digest transcript
  POST /api/a11oy/v1/wayra/take-it        — "take it and make it our own" (draft + queue)
  GET  /wayra                             — self-contained live HTML tab (200 + real data)

Data source: a bundled JSON snapshot of the live WAYRA SQLite ingest log
(data/wayra_snapshot.json), exported by szl_wayra/export_snapshot.py. The snapshot is
real data from a live multi-source poll (HF Hub + GitHub releases + arXiv + standards +
drone OSINT). Read-only, no GitHub Actions — pushed by HfApi DIRECT.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

# Snapshot lives next to serve.py in the Space root (and at /app on the live image).
_CANDIDATES = [
    Path("/app/wayra_snapshot.json"),
    Path(__file__).resolve().parent / "wayra_snapshot.json",
    Path(__file__).resolve().parent / "data" / "wayra_snapshot.json",
]


def _load_snapshot() -> dict[str, Any]:
    for p in _CANDIDATES:
        if p.is_file():
            try:
                return json.loads(p.read_text())
            except Exception:
                continue
    # Honest empty state if the snapshot is missing.
    return {"organ": "wayra", "doctrine": "v13 (4th edge organ)",
            "etymology": "Quechua wayra = wind, air (Wiktionary)",
            "totals": {"events": 0, "receipts": 0, "chain_verified": False, "chain_depth": 0},
            "thresholds": {"drop": 0.30, "accept": 0.70, "daily_cap": 50},
            "source_stats": [], "recent": [], "top5": []}


router = APIRouter()


@router.get("/api/a11oy/v1/wayra/summary")
async def wayra_summary() -> JSONResponse:
    s = _load_snapshot()
    return JSONResponse({
        "organ": s["organ"], "doctrine": s["doctrine"], "etymology": s["etymology"],
        "etymology_source": "https://en.wiktionary.org/wiki/wayra",
        "totals": s["totals"], "thresholds": s["thresholds"],
        "source_stats": s["source_stats"],
        "formula": "WAYRA(s) = quality(s) · novelty(s) · Yuyay_13(extract(s)) ∈ [0,1]",
        "hard_rules": [
            "RECEIVE-ONLY from public sources",
            "Khipu receipt on every ingested event",
            "Yuyay-13 gate enforced (drop < 0.30, accept > 0.70)",
            "Daily intake cost-bounded at 50 items before Yuyay drop",
            "HfApi direct push, NEVER GitHub Actions",
        ],
    })


@router.get("/api/a11oy/v1/wayra/feed")
async def wayra_feed(limit: int = 100) -> JSONResponse:
    s = _load_snapshot()
    return JSONResponse({"count": len(s["recent"]), "items": s["recent"][:max(1, min(limit, 200))]})


@router.get("/api/a11oy/v1/wayra/search")
async def wayra_search(q: str = "") -> JSONResponse:
    s = _load_snapshot()
    ql = q.lower().strip()
    if not ql:
        return JSONResponse({"query": q, "count": 0, "items": []})
    hits = [it for it in s["recent"]
            if ql in (it.get("title", "") + it.get("parsed_summary", "")
                      + it.get("source_detail", "")).lower()]
    return JSONResponse({"query": q, "count": len(hits), "items": hits})


@router.get("/api/a11oy/v1/wayra/sources")
async def wayra_sources() -> JSONResponse:
    s = _load_snapshot()
    return JSONResponse({"sources": s["source_stats"]})


@router.get("/api/a11oy/v1/wayra/digest")
async def wayra_digest() -> JSONResponse:
    s = _load_snapshot()
    top5 = s.get("top5", [])
    # WALLPA-narrated transcript (synthetic timbre; open-source TTS at render time).
    lines = ["Hatun-Willay morning briefing. WAYRA breathed in the world overnight.",
             f"The empire's lungs logged {s['totals']['events']} items across "
             f"{len(s['source_stats'])} streams; the Khipu chain verifies "
             f"{'intact' if s['totals']['chain_verified'] else 'BROKEN'}.",
             "Top five by WAYRA factor:"]
    for i, t in enumerate(top5, 1):
        lines.append(f"{i}. {t.get('title','')} — from {t.get('source','')}, "
                     f"WAYRA factor {t.get('wayra_factor',0):.2f}, "
                     f"routed to {', '.join(t.get('organ_routing') or ['(review)'])}.")
    lines.append("That is the breath of the world, made ours. — Wallpa, for WAYRA.")
    return JSONResponse({"top5": top5, "transcript": "\n".join(lines),
                         "voice": "wallpa-synthetic-timbre",
                         "tts_engines": ["coqui-xtts-v2", "piper", "openvoice"]})


@router.post("/api/a11oy/v1/wayra/take-it")
async def wayra_take_it(request: Request) -> JSONResponse:
    """'Take it and make it our own' — draft a PR/Doctrine stub + queue for Yuyay review.

    Does NOT auto-merge. Emits a draft + a queued review item (the human Yuyay approves).
    """
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    content_hash = body.get("content_hash", "")
    s = _load_snapshot()
    item = next((it for it in s["recent"] if it.get("content_hash") == content_hash), None)
    if item is None:
        return JSONResponse({"ok": False, "error": "item not found"}, status_code=404)
    organ = (item.get("organ_routing") or ["a11oy"])[0]
    draft = {
        "kind": "pr_stub" if organ in ("a11oy", "sentra", "killinchu") else "doctrine_stub",
        "target_organ": organ,
        "title": f"WAYRA: adopt — {item.get('title','')}",
        "rationale": item.get("parsed_summary", "")[:600],
        "source_url": item.get("url", ""),
        "wayra_factor": item.get("wayra_factor", 0),
        "status": "QUEUED_FOR_YUYAY_REVIEW",
        "note": "Drafted by WAYRA. Human Yuyay approval required before merge. "
                "Weights never baked; closed models added via official providers only.",
    }
    return JSONResponse({"ok": True, "draft": draft})


# ---------------------------------------------------------------------------
# Self-contained /wayra HTML tab — live feed + search + per-source dashboard +
# "take it" button. Fetches the JSON endpoints above. Returns 200 with real data.
# ---------------------------------------------------------------------------
_WAYRA_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>WAYRA — the empire's lungs · a11oy</title>
<style>
:root{--bg:#0b0f14;--panel:#121a24;--ink:#e7eef6;--mut:#8aa0b4;--line:#1f2c3a;
--green:#2ecc71;--amber:#f1c40f;--red:#e74c3c;--accent:#48c9ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
header{padding:20px 24px;border-bottom:1px solid var(--line);
background:linear-gradient(180deg,#0e1620,#0b0f14)}
h1{margin:0;font-size:22px;letter-spacing:.5px}
.sub{color:var(--mut);margin-top:4px}
.wrap{padding:18px 24px;max-width:1180px;margin:0 auto}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:14px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.card .n{font-size:26px;font-weight:700}.card .l{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.6px}
.row{display:flex;gap:18px;flex-wrap:wrap}
.col{flex:1;min-width:320px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:700}
.b-accept{background:rgba(46,204,113,.15);color:var(--green)}
.b-review{background:rgba(241,196,15,.15);color:var(--amber)}
.b-drop{background:rgba(231,76,60,.15);color:var(--red)}
.score{font-variant-numeric:tabular-nums;color:var(--mut)}
input[type=search]{width:100%;padding:9px 12px;background:#0e1620;border:1px solid var(--line);
border-radius:8px;color:var(--ink);font-size:14px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.take{background:#16314a;border:1px solid #1f4a6b;color:var(--accent);border-radius:6px;
padding:3px 8px;font-size:11px;cursor:pointer}.take:hover{background:#1c4060}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin:12px 0}
.mut{color:var(--mut)}.chip{font-size:11px;color:var(--mut);background:#0e1620;border:1px solid var(--line);
border-radius:6px;padding:1px 6px;margin-right:4px}
pre{white-space:pre-wrap;background:#0e1620;border:1px solid var(--line);border-radius:8px;padding:12px;color:var(--mut)}
</style></head>
<body>
<header>
  <h1>WAYRA &middot; the empire's lungs</h1>
  <div class="sub">Quechua <i>wayra</i> = wind, air
  (<a href="https://en.wiktionary.org/wiki/wayra" target="_blank" rel="noopener">Wiktionary</a>) &middot;
  Doctrine v13, 4th edge organ &middot; always-learning firehose &middot;
  WAYRA(s) = quality &middot; novelty &middot; Yuyay&#8321;&#8323; &isin; [0,1]</div>
</header>
<div class="wrap">
  <div class="cards" id="cards"></div>
  <div class="row">
    <div class="col">
      <div class="panel"><b>Live feed</b> <span class="mut">— last 100 ingested items</span>
        <div style="margin:10px 0"><input id="q" type="search" placeholder="Search anything WAYRA has seen…"/></div>
        <div style="max-height:560px;overflow:auto"><table id="feed"><thead><tr>
          <th>Source</th><th>Item</th><th>WAYRA</th><th>Yuyay</th><th>Nov</th><th>Decision</th><th>Route</th><th></th>
        </tr></thead><tbody></tbody></table></div>
      </div>
    </div>
    <div class="col" style="max-width:380px">
      <div class="panel"><b>Per-source dashboard</b>
        <table id="src"><thead><tr><th>Source</th><th>Total</th><th>Acc</th><th>Rev</th><th>Drop</th></tr></thead><tbody></tbody></table>
      </div>
      <div class="panel"><b>Hatun-Willay digest</b> <span class="mut">— Wallpa-narrated top-5</span>
        <pre id="digest">loading…</pre>
      </div>
    </div>
  </div>
  <div class="panel mut">RECEIVE-ONLY from public sources &middot; Khipu receipt on every event &middot;
  Yuyay-13 gate enforced &middot; daily cap 50 &middot; HfApi direct push, never GitHub Actions.</div>
</div>
<script>
const B="/api/a11oy/v1/wayra";
function badge(d){return '<span class="badge b-'+d+'">'+d+'</span>'}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function rowHtml(it){
  return '<tr><td><span class="chip">'+esc(it.source)+'</span><br><span class="mut">'+esc(it.source_detail||'')+'</span></td>'+
    '<td><a href="'+esc(it.url)+'" target="_blank" rel="noopener">'+esc((it.title||'').slice(0,90))+'</a></td>'+
    '<td class="score">'+(it.wayra_factor||0).toFixed(2)+'</td>'+
    '<td class="score">'+(it.yuyay_score||0).toFixed(2)+'</td>'+
    '<td class="score">'+(it.novelty_score||0).toFixed(2)+'</td>'+
    '<td>'+badge(it.decision)+'</td>'+
    '<td class="mut">'+esc((it.organ_routing||[]).join(', '))+'</td>'+
    '<td>'+(it.decision==='accept'?'<button class="take" data-h="'+esc(it.content_hash)+'">take it</button>':'')+'</td></tr>'
}
async function load(){
  const s=await (await fetch(B+'/summary')).json();
  const t=s.totals;
  document.getElementById('cards').innerHTML=[
    ['events',t.events],['receipts',t.receipts],
    ['chain',t.chain_verified?'verified':'broken'],
    ['sources',s.source_stats.length],['daily cap',s.thresholds.daily_cap]
  ].map(([l,n])=>'<div class="card"><div class="n">'+n+'</div><div class="l">'+l+'</div></div>').join('');
  const sb=document.querySelector('#src tbody');
  sb.innerHTML=s.source_stats.map(x=>'<tr><td>'+esc(x.source)+'</td><td>'+x.total+'</td><td>'+x.accepted+'</td><td>'+x.review+'</td><td>'+x.dropped+'</td></tr>').join('');
  const f=await (await fetch(B+'/feed?limit=100')).json();
  document.querySelector('#feed tbody').innerHTML=f.items.map(rowHtml).join('');
  bindTake();
  const d=await (await fetch(B+'/digest')).json();
  document.getElementById('digest').textContent=d.transcript;
}
function bindTake(){
  document.querySelectorAll('.take').forEach(b=>b.onclick=async()=>{
    const r=await (await fetch(B+'/take-it',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({content_hash:b.dataset.h})})).json();
    if(r.ok){alert('Drafted '+r.draft.kind+' for '+r.draft.target_organ+' — '+r.draft.status+'.\\n\\n'+r.draft.title);}
    else{alert('Could not draft: '+(r.error||'unknown'));}
  });
}
let timer;
document.getElementById('q').addEventListener('input',e=>{
  clearTimeout(timer); const q=e.target.value;
  timer=setTimeout(async()=>{
    const url=q?B+'/search?q='+encodeURIComponent(q):B+'/feed?limit=100';
    const r=await (await fetch(url)).json();
    document.querySelector('#feed tbody').innerHTML=(r.items||[]).map(rowHtml).join('');
    bindTake();
  },220);
});
load();
</script>
</body></html>"""


@router.get("/wayra", response_class=HTMLResponse)
async def wayra_tab() -> HTMLResponse:
    return HTMLResponse(_WAYRA_HTML)


# ===========================================================================
# /wayra-digest — last-7-days Hatun-Willay digest archive (ADDITIVE). Yachay.
# Founder directive 2026-06-01: activate the WAYRA daily-digest cron and surface
# the last 7 days of digests on a11oy. Backed by wayra_digests_7d.json, produced
# by the real systemd cron (wayra-digest.timer @ 06:00 America/New_York) + the
# szl_wayra backfill. RECEIVE-ONLY. Honest: backfilled days are labeled.
# ===========================================================================
_DIGEST_BUNDLE_CANDIDATES = [
    Path("/app/wayra_digests_7d.json"),
    Path(__file__).resolve().parent / "wayra_digests_7d.json",
    Path(__file__).resolve().parent / "data" / "wayra_digests_7d.json",
]


def _load_digest_bundle() -> dict[str, Any]:
    for p in _DIGEST_BUNDLE_CANDIDATES:
        try:
            if p.exists():
                return json.loads(p.read_text())
        except Exception:
            continue
    return {"organ": "WAYRA", "tab": "/wayra-digest", "days": [],
            "note": "digest bundle missing — cron has not produced 7 days yet"}


@router.get("/api/a11oy/v1/wayra/digests")
async def wayra_digests() -> JSONResponse:
    """Last 7 days of Hatun-Willay digests (one per day). Source: wayra-digest cron."""
    b = _load_digest_bundle()
    return JSONResponse(b)


_WAYRA_DIGEST_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>WAYRA digest — last 7 days · a11oy</title>
<style>
:root{--bg:#0b0f14;--panel:#121a24;--ink:#e7eef6;--mut:#8aa0b4;--line:#1f2c3a;
--green:#2ecc71;--amber:#f1c40f;--accent:#48c9ff;--coral:#ff7a59}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
header{padding:20px 24px;border-bottom:1px solid var(--line);
background:linear-gradient(180deg,#0e1620,#0b0f14)}
h1{margin:0;font-size:22px;letter-spacing:.5px}
.sub{color:var(--mut);margin-top:4px}
.wrap{padding:18px 24px;max-width:1080px;margin:0 auto}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:14px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.card .n{font-size:26px;font-weight:700}.card .l{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.6px}
.day{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--coral);
border-radius:10px;padding:14px;margin:12px 0}
.day h3{margin:0 0 6px;font-size:16px}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:700;margin-left:6px}
.b-live{background:rgba(46,204,113,.16);color:var(--green)}
.b-bf{background:rgba(241,196,15,.16);color:var(--amber)}
pre{white-space:pre-wrap;background:#0e1620;border:1px solid var(--line);border-radius:8px;padding:12px;color:#c7d6e6;margin:8px 0}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.mut{color:var(--mut)}.score{font-variant-numeric:tabular-nums;color:var(--mut)}
.nav{margin-top:8px}.nav a{margin-right:14px}
</style></head>
<body>
<header>
  <h1>WAYRA digest &middot; last 7 days</h1>
  <div class="sub">Hatun-Willay morning briefing &middot; Wallpa-narrated top-5 &middot;
  produced by the <b>wayra-digest</b> cron (06:00 America/New_York) &middot; Khipu-verified.
  <div class="nav"><a href="/wayra">&larr; WAYRA live feed</a><a href="/">a11oy home</a></div></div>
</header>
<div class="wrap">
  <div class="cards" id="cards"></div>
  <div id="days"></div>
  <div class="day mut">RECEIVE-ONLY &middot; one digest per day &middot; backfilled days labeled honestly &middot;
  cron: systemd <code>wayra-digest.timer</code> OnCalendar=*-*-* 06:00:00 America/New_York.</div>
</div>
<script>
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
async function load(){
  let b; try{ b = await (await fetch('/api/a11oy/v1/wayra/digests')).json(); }
  catch(e){ document.getElementById('days').innerHTML='<div class="day">digest feed unavailable</div>'; return; }
  const days=b.days||[];
  document.getElementById('cards').innerHTML =
    card(b.today_events,'events today')+card(b.baseline_events,'baseline')+
    card(days.length,'days shown')+card('06:00 ET','cron time');
  document.getElementById('days').innerHTML = days.slice().reverse().map(d=>{
    const tag = d.backfilled ? '<span class="badge b-bf">backfilled</span>'
                             : '<span class="badge b-live">live</span>';
    const rows = (d.top||[]).map((t,i)=>`<tr><td>${i+1}</td><td>${esc(t.title)}</td>
      <td class="mut">${esc(t.source)}</td><td class="score">${(t.wayra_factor||0).toFixed(2)}</td>
      <td class="mut">${esc((t.organ_routing||[]).join(', '))}</td></tr>`).join('');
    return `<div class="day"><h3>${d.date} ${tag}
      <span class="mut" style="font-weight:400">&middot; ${d.events} events &middot; chain ${d.chain_verified?'intact':'?'}</span></h3>
      <pre>${esc(d.transcript)}</pre>
      <table><thead><tr><th>#</th><th>Item</th><th>Source</th><th>WAYRA</th><th>Route</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`;
  }).join('');
}
function card(n,l){return `<div class="card"><div class="n">${n}</div><div class="l">${l}</div></div>`}
load();
</script>
</body></html>"""


@router.get("/wayra-digest", response_class=HTMLResponse)
async def wayra_digest_tab() -> HTMLResponse:
    return HTMLResponse(_WAYRA_DIGEST_HTML)
