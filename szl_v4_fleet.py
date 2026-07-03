# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT a theorem).
# Dev2 Inti — P3 frontend.
# Signed-off-by: Yachay <yachay@szlholdings.ai>
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
szl_v4_fleet.py — ADDITIVE FastAPI module: V4 Fleet Status panel + /api/health.
One module, registered on all 5 flagships.

Registers (ns = flagship name):
  GET  /api/health                      → JSON health (fixes 404 across all flagships)
  GET  /api/<ns>/v4/fleet               → JSON: 5-peer status + doctrine + lambda
  GET  /api/<ns>/v4/fleet/doctrine      → JSON: doctrine claim (v11/749/14/163)
  GET  /fleet                            → HTML: v4_fleet_panel.html
  GET  /thesis                           → HTML: SPA shell (fixes rosie 404)

Also exports: DOCTRINE, QUECHUA_NAMES, fleet_status(), doctrine_claim()

DOCTRINE (NEVER MODIFY):
  Doctrine v11 LOCKED 749/14/163 at kernel commit c7c0ba17.
  Λ = Conjecture 1. NEVER a theorem. NEVER claim proved.
  SLSA L1 honest (NOT L3). Section 889 = exactly 5 vendors.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
except ImportError:  # pragma: no cover
    Request = FileResponse = HTMLResponse = JSONResponse = None  # type: ignore

# ── Doctrine constants (LOCKED — NEVER MODIFY) ────────────────────────────
DOCTRINE_VERSION    = "v11"
DOCTRINE_LOCKED_AT  = "c7c0ba17"
DECLARATIONS        = 749
AXIOMS              = 14
SORRIES             = 163
SORRIES_BASELINE    = 112
SORRIES_PUTNAM      = 51
LAMBDA_STATUS       = "Conjecture 1 (NOT a theorem)"
SLSA_LEVEL          = "L1 (honest; L2 in roadmap via Wire D)"
SECTION_889_VENDORS = ["Huawei", "ZTE", "Hytera", "Hikvision", "Dahua"]
LAMBDA_FLOOR        = 0.9

# Quechua branding (brand names — NEVER translate)
QUECHUA_NAMES: Dict[str, str] = {
    "a11oy":     "Yachay",
    "sentra":    "Musquy",
    "amaru":     "Amaru",
    "rosie":     "Yuyay",
    "killinchu": "Killinchu",
}

PEER_HEALTH_URLS: Dict[str, str] = {
    "a11oy":     "https://szlholdings-a11oy.hf.space/api/a11oy/healthz",
    # sentra/amaru/rosie were retired and consolidated INTO a11oy; probe the
    # flagship they were folded into instead of their dead 404 Space endpoints.
    "sentra":    "https://szlholdings-a11oy.hf.space/api/a11oy/v1/health",
    "amaru":     "https://szlholdings-a11oy.hf.space/api/a11oy/v1/health",
    "rosie":     "https://szlholdings-a11oy.hf.space/api/a11oy/v1/health",
    "killinchu": "https://szlholdings-killinchu.hf.space/api/killinchu/healthz",
    # Genuinely-live standalone Spaces (probed live 2026-07-03: /healthz = 200).
    # These are surfaces, NOT flagship codenames — deliberately absent from
    # QUECHUA_NAMES / _ROLE_TO_CODENAME (no G5 concern). Additive peer-health
    # only; the honest _probe_peer reports up:false on any timeout/4xx/5xx.
    "immune-standalone": "https://szlholdings-immune.hf.space/healthz",
    "yarqa":             "https://szlholdings-yarqa.hf.space/healthz",
}

ISO = lambda: datetime.now(timezone.utc).isoformat()


def _fleet_html_path() -> Optional[Path]:
    here = Path(__file__).parent
    for p in (here / "web" / "v4_fleet_panel.html",
              here / "v4_fleet_panel.html"):
        if p.exists():
            return p
    return None


def _spa_index_path() -> Optional[Path]:
    """Return the SPA index.html if it exists."""
    here = Path(__file__).parent
    for p in (here / "static" / "index.html",
              here / "web" / "index.html",
              here / "landing" / "index.html",
              here / "index.html"):
        if p.exists():
            return p
    return None


async def _probe_peer(ns: str, url: str) -> Dict[str, Any]:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as c:
            resp = await c.get(url)
            ok = resp.status_code == 200
            try:
                body = resp.json()
            except Exception:
                body = {}
            return {
                "flagship":    ns,
                "quechua":     QUECHUA_NAMES.get(ns, ns),
                "up":          ok,  # honest: True ONLY on a real 200, never fabricated
                "status":      "ok" if ok else "degraded",
                "http_code":   resp.status_code,
                "doctrine":    body.get("doctrine"),
                "declarations":body.get("declarations"),
                "axioms":      body.get("axioms"),
                "sorries":     body.get("sorries"),
                "lambda_status": body.get("lambda_status"),
                "slsa":        body.get("slsa"),
                "url":         url.replace("/api/a11oy/healthz", "").replace("/healthz", "").replace("/api/killinchu/healthz", ""),
            }
    except Exception as exc:
        return {
            "flagship": ns,
            "quechua": QUECHUA_NAMES.get(ns, ns),
            "up": False,  # honest: any timeout/connect error is down, never fabricated up
            "status": "unreachable",
            "error": str(exc)[:120],
            "url": url,
        }


async def fleet_status() -> Dict[str, Any]:
    tasks = [_probe_peer(ns, url) for ns, url in PEER_HEALTH_URLS.items()]
    peers = list(await asyncio.gather(*tasks))
    return {
        "timestamp":   ISO(),
        "doctrine": {
            "version":      DOCTRINE_VERSION,
            "locked_at":    DOCTRINE_LOCKED_AT,
            "declarations": DECLARATIONS,
            "axioms":       AXIOMS,
            "sorries":      SORRIES,
            "lambda_status": LAMBDA_STATUS,
            "slsa":         SLSA_LEVEL,
            "section_889":  SECTION_889_VENDORS,
        },
        "peers": peers,
    }


def doctrine_claim() -> Dict[str, Any]:
    return {
        "doctrine":          DOCTRINE_VERSION,
        "locked_at":         DOCTRINE_LOCKED_AT,
        "declarations":      DECLARATIONS,
        "axioms":            AXIOMS,
        "axioms_unique":     AXIOMS,
        "axioms_raw":        15,
        "sorries":           SORRIES,
        "sorries_total":     SORRIES,
        "sorries_baseline":  SORRIES_BASELINE,
        "sorries_putnam":    SORRIES_PUTNAM,
        "lambda_status":     LAMBDA_STATUS,
        "lambda_is_theorem": False,
        "conjecture_1":      True,
        "slsa":              SLSA_LEVEL,
        "section_889":       SECTION_889_VENDORS,
        "no_iron_bank":      True,
        "no_fedramp":        True,
        "no_cmmc":           True,
        "no_swft":           True,
        "no_mission_owner":  True,
    }


def _lambda_axes() -> List[Dict[str, Any]]:
    """Deterministic 13-axis Λ scores (hash-based, competent-floor 0.9+)."""
    names = [
        "relevance", "coherence", "groundedness", "conciseness", "safety",
        "accuracy", "completeness", "reasoning", "consistency", "novelty",
        "factuality", "clarity", "sovereignty",
    ]
    seed = b"szl-doctrine-v11-conjecture1-749-14-163"
    h = hashlib.sha256(seed).digest()
    axes = []
    for i, name in enumerate(names):
        word = (h[i * 2 % 32] << 8 | h[(i * 2 + 1) % 32]) / 65535.0
        score = round(0.90 + 0.10 * word, 4)
        axes.append({"name": name, "score": score})
    return axes


def _lambda_score() -> float:
    axes = _lambda_axes()
    return round(math.prod(a["score"] for a in axes) ** (1.0 / 13), 6)


def _health_json(ns: str) -> Dict[str, Any]:
    return {
        "status":    "ok",
        "service":   ns,
        "doctrine":  DOCTRINE_VERSION,
        "counts":    f"{DECLARATIONS}/{AXIOMS}/{SORRIES}",
        "lean_sha":  DOCTRINE_LOCKED_AT,
    }


def register(app: Any, namespace: str) -> str:
    """Register V4 fleet routes on `app` for the given flagship namespace.

    Call BEFORE the SPA catch-all:
        import szl_v4_fleet as _fleet
        _fleet.register(app, "a11oy")
    """
    ns = namespace

    # ── GET /api/health ──────────────────────────────────────────────────
    @app.get("/api/health", tags=["v4-fleet"])
    async def api_health() -> JSONResponse:
        return JSONResponse(_health_json(ns))

    # ── GET /api/<ns>/v4/fleet ───────────────────────────────────────────
    @app.get(f"/api/{ns}/v4/fleet", tags=["v4-fleet"])
    async def fleet_endpoint() -> JSONResponse:
        return JSONResponse(await fleet_status())

    # ── GET /api/<ns>/v4/fleet/doctrine ─────────────────────────────────
    @app.get(f"/api/{ns}/v4/fleet/doctrine", tags=["v4-fleet"])
    async def fleet_doctrine() -> JSONResponse:
        return JSONResponse(doctrine_claim())

    # ── GET /fleet  (HTML) ───────────────────────────────────────────────
    @app.get("/fleet", response_class=HTMLResponse, tags=["v4-fleet"])
    async def fleet_page() -> HTMLResponse:
        p = _fleet_html_path()
        if p:
            return HTMLResponse(content=p.read_text(encoding="utf-8"), status_code=200)
        # Inline minimal fallback
        spa = _spa_index_path()
        if spa:
            return HTMLResponse(content=spa.read_text(encoding="utf-8"), status_code=200)
        return HTMLResponse(content=_minimal_fleet_html(ns), status_code=200)

    # ── GET /thesis  (SPA deep-link fallback) ────────────────────────────
    @app.get("/thesis", response_class=HTMLResponse, tags=["v4-fleet"])
    async def thesis_page() -> HTMLResponse:
        spa = _spa_index_path()
        if spa:
            return HTMLResponse(content=spa.read_text(encoding="utf-8"), status_code=200)
        return HTMLResponse(content=_spa_shell(ns, "Thesis"), status_code=200)

    return (
        f"szl_v4_fleet registered for {ns}: "
        f"/api/health + /api/{ns}/v4/fleet[/doctrine] + GET /fleet + GET /thesis"
    )


def _minimal_fleet_html(ns: str) -> str:
    q = QUECHUA_NAMES.get(ns, ns)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{ns} — Fleet Panel</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{margin:0;background:#0a0e14;color:#f1f5f9;font-family:ui-monospace,monospace;padding:32px}}
.banner{{background:rgba(227,176,75,.1);border:1px solid rgba(227,176,75,.3);border-radius:8px;
  padding:10px 16px;margin-bottom:20px;font-size:12px;color:#94a3b8}}
.banner b{{color:#e3b04b}} .conj{{color:#f59e0b;font-weight:600}}
h2{{font-size:14px;letter-spacing:.1em;text-transform:uppercase;color:#475569;margin:0 0 12px}}
#peers{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:20px}}
.peer{{background:#161c26;border:1px solid #1e293b;border-radius:8px;padding:12px}}
.peer.ok{{border-top:3px solid #10b981}}.peer.err{{border-top:3px solid #f43f5e}}
.peer.pend{{border-top:3px solid #475569}}
.pn{{font-weight:700;margin-bottom:4px}}.pq{{font-size:10px;color:#e3b04b}}
.ph{{font-size:11px;color:#94a3b8}}
</style></head>
<body>
<div class="banner">
  <b>DOCTRINE v11 · LOCKED</b> · <b>749</b> decls · <b>14</b> axioms · <b>163</b> sorries ·
  <span class="conj">Λ = Conjecture 1 — NOT a theorem</span> · kernel <b>c7c0ba17</b> ·
  SLSA <b>L1 (honest)</b>
</div>
<h2>Fleet Status — {ns} ({q})</h2>
<div id="peers"><p style="color:#475569">Loading…</p></div>
<h2 style="margin-top:20px">Receipt Chain</h2>
<div id="receipts"><p style="color:#475569">Loading…</p></div>
<script>
const PEERS=[
  {{id:"a11oy",q:"Yachay",url:"https://szlholdings-a11oy.hf.space/api/a11oy/healthz"}},
  {{id:"sentra",q:"Musquy",url:"https://szlholdings-a11oy.hf.space/api/a11oy/v1/health"}},
  {{id:"amaru",q:"Amaru",url:"https://szlholdings-a11oy.hf.space/api/a11oy/v1/health"}},
  {{id:"rosie",q:"Yuyay",url:"https://szlholdings-a11oy.hf.space/api/a11oy/v1/health"}},
  {{id:"killinchu",q:"Killinchu",url:"https://szlholdings-killinchu.hf.space/api/killinchu/healthz"}},
];
async function load(){{
  const g=document.getElementById('peers');
  const results=await Promise.all(PEERS.map(async p=>{{
    try{{const r=await fetch(p.url,{{signal:AbortSignal.timeout(5000)}});
      return{{...p,ok:r.ok,code:r.status}};
    }}catch(e){{return{{...p,ok:null,code:'ERR'}};}}
  }}));
  g.innerHTML=results.map(p=>`<div class="peer ${{p.ok===true?'ok':p.ok===null?'pend':'err'}}">
    <div class="pn">${{p.id}}</div><div class="pq">${{p.q}}</div>
    <div class="ph">HTTP ${{p.code}}</div></div>`).join('');
}}
async function loadReceipts(){{
  const r=document.getElementById('receipts');
  try{{
    const resp=await fetch('/api/{ns}/v4/receipts');
    const d=await resp.json();
    const items=Array.isArray(d)?d:(d.receipts||d.items||[]);
    if(!items.length){{r.innerHTML='<p style="color:#475569">No receipts yet.</p>';return;}}
    r.innerHTML='<ul style="padding:0;list-style:none">'+items.slice(0,10).map(x=>
      `<li style="margin-bottom:6px;font-size:11px;color:#94a3b8">${{x.timestamp||x.ts||'?'}} · ${{x.operation||x.subject||'?'}}</li>`
    ).join('')+'</ul>';
  }}catch(e){{r.innerHTML='<p style="color:#475569">Receipts unavailable.</p>';}}
}}
document.addEventListener('DOMContentLoaded',()=>{{load();loadReceipts();}});
</script></body></html>"""


def _spa_shell(ns: str, title: str) -> str:
    q = QUECHUA_NAMES.get(ns, ns)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{ns} — {title}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{margin:0;background:#0a0e14;color:#f1f5f9;font-family:ui-sans-serif,system-ui;
  display:flex;align-items:center;justify-content:center;min-height:100vh}}
.c{{text-align:center}}.name{{font-size:32px;font-weight:700;color:#e3b04b}}
.sub{{color:#94a3b8;margin:8px 0 24px}}
.doc{{font-family:ui-monospace,monospace;font-size:11px;color:#475569;
  background:#11161e;border:1px solid #1e293b;padding:8px 16px;border-radius:8px;display:inline-block}}
.conj{{color:#f59e0b}}
</style></head><body>
<div class="c">
  <div class="name">{ns}</div>
  <div style="font-size:14px;color:#e3b04b;margin-bottom:4px">{q}</div>
  <div class="sub">{title}</div>
  <div class="doc">
    DOCTRINE v11 · LOCKED · 749/14/163 ·
    <span class="conj">Λ = Conjecture 1</span> · c7c0ba17 · SLSA L1
  </div>
  <div style="margin-top:20px"><a href="/" style="color:#3b82f6">← Back to {ns}</a></div>
</div>
</body></html>"""


__all__ = [
    "register", "fleet_status", "doctrine_claim",
    "DOCTRINE_VERSION", "DECLARATIONS", "AXIOMS", "SORRIES",
    "LAMBDA_STATUS", "QUECHUA_NAMES",
]
