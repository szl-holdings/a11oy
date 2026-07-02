# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by A11oy Full-Stack Team (closeout). Co-Authored-By: Perplexity Computer Agent.
"""a11oy_formulas_page — ADDITIVE Formulas section for the SPA navigation.

Renders GET /formulas/wired : a premium (Inca-palette) page that lists EACH live
formula from a11oy_formula_endpoints._INDEX with:
  * its thesis citation (thesis_v22.pdf §2),
  * a Lean permalink (github.com/szl-holdings/lutar-lean @ locked SHA c7c0ba17),
  * a "Try it" button that calls the LIVE per-formula endpoint and shows the JSON.

Honesty: the page reads the SAME _INDEX the JSON API serves (no duplicate list).
The "Try it" buttons hit the real /api/a11oy/v1/formulas/<name> endpoints; if an
endpoint is not GET-able (e.g. welford/bloom are POST), the button is labelled
accordingly. Reidemeister is shown as v15 scaffolding (not a proved theorem) and
Quorum carries its honest "Conjecture 2" label. Doctrine v11 LOCKED 749/14/163,
Λ = Conjecture 1 — UNCHANGED. Registered BEFORE the SPA catch-all. try/except in
serve.py guarantees a missing dep can never take down the Space.
"""
from __future__ import annotations

import json
import html as _html

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

LEAN_REPO = "https://github.com/szl-holdings/lutar-lean"
LEAN_SHA = "c7c0ba17"
DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1"}

# Per-formula live endpoint: (method, query-string). The endpoints are mounted at
# /api/<ns>/v1/formula/<name> (SINGULAR `formula`); the index is the only plural
# path. All "Try it" buttons use GET with sensible default query params so they
# return a real computed value (kalman REQUIRES ?z=; quorum/holevo/bloom take
# optional params). welford/bloom also expose POST mutators, but GET snapshots are
# the honest, side-effect-free demo.
_METHOD = {
    "pacbayes": ("GET", ""),
    "welford": ("GET", ""),               # GET = running-variance snapshot
    "quorum": ("GET", "?n=5&f=1"),
    "holevo": ("GET", "?dim=2&snr=1.0"),
    "bloom": ("GET", "?key=a11oy"),
    "kalman": ("GET", "?z=1.0"),         # z is required
    "bls": ("GET", ""),
    "reidemeister": ("GET", ""),
    "hnsw": ("GET", ""),
    # Wave15-18 additions (CF-22 / CF-23 / R–J aftershock).
    "kl": ("POST", ""),                  # CF-22: POST {p,q} simplex vectors
    "pinsker": ("GET", "?p=0.6&q=0.5"),  # CF-23: binary Pinsker margin
    "aftershock": ("GET", "?mainshock_mag=6.0&target_mag=5.0&days=1.0"),  # R–J live-data
}

# Default JSON bodies for POST "Try it" buttons (honest, side-effect-free demos).
_POST_BODY = {
    "kl": {"p": [0.5, 0.3, 0.2], "q": [0.4, 0.4, 0.2]},
}

# Maturity tier label per formula (honest doctrine tiers). Absent = legacy/proved.
_TIER = {
    "kl": "experimental",
    "pinsker": "experimental",
    "aftershock": "live-data",
}

# Lean file path per formula (relative inside lutar-lean), parsed from _INDEX label.
_LEAN_PATH = {
    "pacbayes": "Lutar/PACBayes.lean",
    "welford": "Lutar/FrontierWelfordVariance.lean",
    "quorum": "Lutar/KhipuConsensus.lean",
    "holevo": "Lutar/QuantumHolevoReceipt.lean",
    "bloom": "Lutar/FrontierBloomCacheBypass.lean",
    "kalman": "Lutar/FrontierKalmanGain.lean",
    "bls": "Lutar/FrontierBLSAggregation.lean",
    "reidemeister": "Lutar/KnotCalculus.lean",
    "hnsw": "Lutar/FrontierHNSWNavigability.lean",
    "kl": "Lutar/Wave15/DPOKLSimplex.lean",        # CF-22
    "pinsker": "Lutar/Wave17/BinaryPinsker.lean",  # CF-23
    # aftershock has NO Lean theorem (generic-parameter R–J model) -> repo root link.
}


def _index() -> list[dict]:
    try:
        import a11oy_formula_endpoints as _fe
        return list(_fe._INDEX)
    except Exception:
        return []


def _lean_permalink(name: str) -> str:
    path = _LEAN_PATH.get(name, "")
    if not path:
        return LEAN_REPO
    return f"{LEAN_REPO}/blob/{LEAN_SHA}/{path}"


def _card(item: dict, ns: str) -> str:
    name = item.get("name", "")
    citation = item.get("citation", "")
    theorem = item.get("lean_theorem", "")
    method, qs = _METHOD.get(name, ("GET", ""))
    ep = f"/api/{ns}/v1/formula/{name}{qs}"
    perm = _lean_permalink(name)
    # Honest maturity badge. _INDEX may carry an explicit tier (Wave15-18 cards);
    # else infer from the theorem label (scaffolding/conjecture => not-proved).
    tier = (item.get("tier") or _TIER.get(name) or "").lower()
    scaffold = "scaffolding" in theorem.lower() or "conjecture" in theorem.lower()
    if tier == "experimental":
        badge = '<span class="badge exp">experimental (CI-green, not in locked-8)</span>'
    elif tier == "live-data":
        badge = '<span class="badge live">live-data (generic-parameter, not a theorem)</span>'
    elif scaffold:
        badge = '<span class="badge warn">honest: not a proved theorem</span>'
    else:
        badge = '<span class="badge ok">proved</span>'
    # POST endpoints carry their demo body inline so the button can replay it.
    body = _POST_BODY.get(name)
    body_attr = (f' data-body=\'{_html.escape(json.dumps(body))}\'' if body else "")
    return f"""
    <article class="fcard" id="f-{_html.escape(name)}">
      <header><h3>{_html.escape(name)}</h3>{badge}</header>
      <p class="cite">📄 {_html.escape(citation)}</p>
      <p class="lean">∎ <code>{_html.escape(theorem)}</code></p>
      <div class="row">
        <a class="lean-link" href="{_html.escape(perm)}" target="_blank" rel="noopener">Lean permalink ↗</a>
        <button class="tryit" data-ep="{_html.escape(ep)}" data-method="{method}"{body_attr}>Try it ({method})</button>
      </div>
      <pre class="out" id="out-{_html.escape(name)}" hidden></pre>
    </article>"""


def _page_html(ns: str) -> str:
    items = _index()
    cards = "\n".join(_card(it, ns) for it in items)
    n = len(items)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>A11oy — Formulas ({n} live)</title>
<style>
  :root {{ --bg:#0a0f1e; --panel:#111a2e; --ink:#e8eef7; --muted:#8aa0bd;
           --indigo:#4d8fcc; --terra:#c8643c; --gold:#d8a23c; --ok:#3fae7a; --warn:#c8893c; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;
          background:radial-gradient(1200px 600px at 70% -10%, #16223c, var(--bg)); color:var(--ink); }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:2.5rem 1.25rem 4rem; }}
  .plaque {{ font-family:ui-monospace,monospace; font-size:.72rem; letter-spacing:.12em;
             color:var(--muted); text-transform:uppercase; }}
  .plaque b {{ color:var(--gold); }}
  h1 {{ font-size:clamp(1.8rem,4vw,2.8rem); margin:.4rem 0 0; }}
  h1 .accent {{ color:var(--terra); }}
  .sub {{ color:var(--muted); max-width:60ch; line-height:1.55; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(310px,1fr)); gap:1rem; margin-top:1.75rem; }}
  .fcard {{ background:var(--panel); border:1px solid #21304d; border-radius:12px; padding:1.1rem 1.15rem;
            box-shadow:0 1px 0 rgba(255,255,255,.03), 0 18px 40px -28px #000; }}
  .fcard header {{ display:flex; align-items:center; justify-content:space-between; gap:.5rem; }}
  .fcard h3 {{ margin:0; font-family:ui-monospace,monospace; color:var(--indigo); font-size:1.05rem; }}
  .badge {{ font-size:.62rem; padding:.18rem .5rem; border-radius:999px; letter-spacing:.06em; text-transform:uppercase; }}
  .badge.ok {{ background:rgba(63,174,122,.16); color:var(--ok); border:1px solid rgba(63,174,122,.4); }}
  .badge.warn {{ background:rgba(200,137,60,.16); color:var(--warn); border:1px solid rgba(200,137,60,.4); }}
  .badge.exp {{ background:rgba(120,140,210,.16); color:#9fb0e6; border:1px solid rgba(120,140,210,.45); }}
  .badge.live {{ background:rgba(63,174,122,.12); color:#6fc79a; border:1px solid rgba(63,174,122,.35); }}
  .cite {{ color:var(--muted); font-size:.82rem; margin:.65rem 0 .25rem; }}
  .lean code {{ color:var(--gold); font-size:.78rem; word-break:break-word; }}
  .row {{ display:flex; gap:.6rem; align-items:center; margin-top:.85rem; flex-wrap:wrap; }}
  .lean-link {{ color:var(--indigo); text-decoration:none; font-size:.8rem; border-bottom:1px dotted; }}
  .tryit {{ background:var(--terra); color:#0a0f1e; border:0; border-radius:8px; padding:.45rem .8rem;
            font-weight:700; cursor:pointer; font-size:.8rem; }}
  .tryit:hover {{ filter:brightness(1.08); }}
  .out {{ background:#070c17; border:1px solid #1a2742; border-radius:8px; padding:.6rem .7rem; margin-top:.7rem;
          font-size:.72rem; color:#bcd; overflow:auto; max-height:220px; white-space:pre-wrap; }}
  a.back {{ color:var(--muted); text-decoration:none; font-size:.85rem; }}
</style></head>
<body>
  <main class="wrap" id="main">
    <div class="plaque">SZL HOLDINGS / A11OY / DOCTRINE <b>V11 · LOCKED</b> / 749·14·163 / Λ = CONJECTURE 1</div>
    <h1>The <span class="accent">formulas</span> are live.</h1>
    <p class="sub">{n} thesis-v22 formulas wired to real, no-mock endpoints. Each card cites
       its source and links the exact Lean declaration at the locked SHA {LEAN_SHA}. "Try it"
       calls the live endpoint and shows the raw signed JSON. <a class="back" href="/">← back to console</a></p>
    <section class="grid">{cards}</section>
    <section id="genome" style="margin-top:1.6rem">
      <h2 style="font-size:1.05rem;margin:0 0 .3rem">Genome — formula registry <span class="badge" id="gtier">…</span></h2>
      <p class="sub" style="margin:0 0 .5rem">Live honesty-tier counts read from
        <code>/api/{ns}/v1/genome</code>, the single machine-checkable registry. Shown honestly:
        if the endpoint is unavailable it says so rather than fabricating a count.</p>
      <pre id="genome-out" style="white-space:pre-wrap;margin:.2rem 0 0;font-size:.8rem"></pre>
    </section>
  </main>
<script>
document.querySelectorAll('.tryit').forEach(function(btn) {{
  btn.addEventListener('click', async function() {{
    var ep = btn.getAttribute('data-ep');
    var method = btn.getAttribute('data-method') || 'GET';
    var name = ep.split('/').pop().split('?')[0];
    var out = document.getElementById('out-' + name);
    out.hidden = false; out.textContent = 'calling ' + method + ' ' + ep + ' …';
    try {{
      var opts = {{ method: method, headers: {{ 'Accept': 'application/json' }} }};
      var bodyAttr = btn.getAttribute('data-body');
      if (method === 'POST' && bodyAttr) {{
        opts.headers['Content-Type'] = 'application/json';
        opts.body = bodyAttr;
      }}
      var r = await fetch(ep, opts);
      var t = await r.text();
      try {{ out.textContent = '[' + r.status + '] ' + JSON.stringify(JSON.parse(t), null, 2); }}
      catch (e) {{ out.textContent = '[' + r.status + '] ' + t.slice(0, 800); }}
    }} catch (e) {{ out.textContent = 'error: ' + e; }}
  }});
}});
(async function() {{
  var gt = document.getElementById('gtier');
  var gout = document.getElementById('genome-out');
  try {{
    var r = await fetch('/api/{ns}/v1/genome', {{ headers: {{ 'Accept': 'application/json' }} }});
    var g = await r.json();
    var d = (g && g.data && typeof g.data === 'object') ? g.data : g;
    var tc = d.tier_counts || d.tiers || {{}};
    var keys = Object.keys(tc);
    var lp = tc['LOCKED-PROVEN'];
    gt.textContent = (typeof lp === 'number') ? (lp + ' locked-proven') : ('live (' + r.status + ')');
    gt.className = 'badge ok';
    gout.textContent = keys.length
      ? keys.map(function(k) {{ return k + ': ' + tc[k]; }}).join('\\n')
      : ('[' + r.status + '] ' + JSON.stringify(d).slice(0, 600));
  }} catch (e) {{
    gt.textContent = 'unavailable'; gt.className = 'badge warn';
    gout.textContent = 'genome registry unavailable right now — shown honestly, not faked.';
  }}
}})();
</script>
</body></html>"""


def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Mount GET /formulas/wired (HTML) + GET /api/<ns>/v1/formulas/page-manifest (JSON).
    ADDITIVE — registered before the SPA catch-all; touches no existing route."""

    @app.get("/formulas/wired", include_in_schema=False)
    async def formulas_wired_page() -> HTMLResponse:  # noqa: ANN202
        return HTMLResponse(_page_html(ns))

    @app.get(f"/api/{ns}/v1/formulas/page-manifest", include_in_schema=False)
    async def formulas_page_manifest() -> JSONResponse:  # noqa: ANN202
        items = _index()
        return JSONResponse({
            "section": "Formulas",
            "count": len(items),
            "doctrine": DOCTRINE,
            "lean_repo": LEAN_REPO,
            "lean_sha": LEAN_SHA,
            "formulas": [{
                "name": it.get("name"),
                "citation": it.get("citation"),
                "lean_theorem": it.get("lean_theorem"),
                "lean_permalink": _lean_permalink(it.get("name", "")),
                "endpoint": f"/api/{ns}/v1/formula/{it.get('name')}{_METHOD.get(it.get('name', ''), ('GET', ''))[1]}",
                "method": _METHOD.get(it.get("name", ""), ("GET", ""))[0],
            } for it in items],
        })

    return f"formulas-page mounted: GET /formulas/wired + page-manifest ({len(_index())} formulas)"
